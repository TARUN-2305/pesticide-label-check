"""L1 §10 `sources`: manifest parsing, hash pinning, cache, offline mode, retries (no network)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from labelclaim.errors import ManifestError, SourceIntegrityError, SourceUnavailableError
from labelclaim.sources import SourceDocument, ensure_cached, fetch_with_retries, httpx_fetcher, load_manifest

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = b"%PDF-1.7 fake register bytes"
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


def doc(sha: str = PAYLOAD_SHA) -> SourceDocument:
    return SourceDocument(
        id="d1",
        kind="insecticide",
        url="https://example.invalid/d1.pdf",
        sha256=sha,
        register_date="2026-09-30",
        pages=1,
        expected_sections={},
    )


class CountingFetcher:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(self, url: str) -> bytes:
        self.calls += 1
        return self.payload


def test_real_manifest_parses() -> None:
    docs = load_manifest(REPO / "data" / "sources.toml")
    assert [d.kind for d in docs] == ["insecticide", "fungicide", "restrictions"]
    assert docs[0].expected_sections["agri_combination"] == (54, 88)
    assert all(len(d.sha256) == 64 for d in docs)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            '[[document]]\nid="a"\nkind="insecticide"\nurl="https://x/a.pdf"\nregister_date="2026-09-30"\npages=1\n',
            "sha256",
        ),
        (
            '[[document]]\nid="a"\nkind="insecticide"\nurl="https://x/a.pdf"\nsha256="xyz"\n'
            'register_date="2026-09-30"\npages=1\n',
            "sha256",
        ),
        (
            '[[document]]\nid="a"\nkind="herbicide"\nurl="https://x/a.pdf"\nsha256="' + "0" * 64 + '"\n'
            'register_date="2026-09-30"\npages=1\n',
            "kind",
        ),
        (
            '[[document]]\nid="a"\nkind="insecticide"\nurl="http://x/a.pdf"\nsha256="' + "0" * 64 + '"\n'
            'register_date="2026-09-30"\npages=1\n',
            "https",
        ),
        (
            (
                '[[document]]\nid="a"\nkind="insecticide"\nurl="https://x/a.pdf"\nsha256="' + "0" * 64 + '"\n'
                'register_date="2026-09-30"\npages=1\n'
            )
            * 2,
            "duplicate",
        ),
    ],
)
def test_invalid_manifest_rejected(tmp_path: Path, body: str, message: str) -> None:
    path = tmp_path / "m.toml"
    path.write_text(body)
    with pytest.raises(ManifestError, match=message):
        load_manifest(path)


def test_fetch_verifies_and_caches_by_hash(tmp_path: Path) -> None:
    fetcher = CountingFetcher(PAYLOAD)
    first = ensure_cached(doc(), tmp_path, fetcher)
    assert first == tmp_path / f"{PAYLOAD_SHA}.pdf"
    assert first.read_bytes() == PAYLOAD
    second = ensure_cached(doc(), tmp_path, fetcher)
    assert second == first
    assert fetcher.calls == 1  # the cache hit made no network call


def test_hash_mismatch_keeps_nothing(tmp_path: Path) -> None:
    with pytest.raises(SourceIntegrityError):
        ensure_cached(doc(), tmp_path, CountingFetcher(b"tampered"))
    assert list(tmp_path.iterdir()) == []  # no final file, no temp file


def test_corrupted_cache_fails_closed(tmp_path: Path) -> None:
    (tmp_path / f"{PAYLOAD_SHA}.pdf").write_bytes(b"bit rot")
    fetcher = CountingFetcher(PAYLOAD)
    with pytest.raises(SourceIntegrityError):
        ensure_cached(doc(), tmp_path, fetcher)
    assert fetcher.calls == 0


def test_offline_miss_fails_without_fetching(tmp_path: Path) -> None:
    fetcher = CountingFetcher(PAYLOAD)
    with pytest.raises(SourceUnavailableError):
        ensure_cached(doc(), tmp_path, fetcher, offline=True)
    assert fetcher.calls == 0


def test_retries_with_backoff_then_succeeds() -> None:
    attempts: list[str] = []
    sleeps: list[float] = []

    def flaky(url: str) -> bytes:
        attempts.append(url)
        if len(attempts) < 3:
            raise httpx.ConnectError("down")
        return PAYLOAD

    assert fetch_with_retries("https://x/a.pdf", flaky, sleep=sleeps.append) == PAYLOAD
    assert len(attempts) == 3
    assert sleeps == [1.0, 2.0]


def test_retries_exhausted_raise_unavailable() -> None:
    def down(url: str) -> bytes:
        raise httpx.ConnectError("down")

    with pytest.raises(SourceUnavailableError):
        fetch_with_retries("https://x/a.pdf", down, sleep=lambda s: None)


def test_httpx_fetcher_rejects_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("missing.pdf"):
            return httpx.Response(404)
        return httpx.Response(200, content=PAYLOAD)

    fetch = httpx_fetcher(transport=httpx.MockTransport(handler))
    assert fetch("https://x/ok.pdf") == PAYLOAD
    with pytest.raises(httpx.HTTPStatusError):
        fetch("https://x/missing.pdf")
