"""Source manifest, fetching and hash-pinned cache (L1 §5.1, FR-1)."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import httpx

from labelclaim.errors import ManifestError, SourceIntegrityError, SourceUnavailableError

Kind = Literal["insecticide", "fungicide", "restrictions"]
Fetcher = Callable[[str], bytes]

KINDS: tuple[Kind, ...] = ("insecticide", "fungicide", "restrictions")
DEFAULT_CACHE = Path.home() / ".cache" / "labelclaim"
USER_AGENT = "labelclaim-build/0.0.1 (register build; contact via repository)"
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class SourceDocument:
    id: str
    kind: Kind
    url: str
    sha256: str
    register_date: str
    pages: int
    expected_sections: Mapping[str, tuple[int, int]] = field(default_factory=dict)


def load_manifest(path: Path) -> tuple[SourceDocument, ...]:
    """Parse and validate `data/sources.toml`. Raises ManifestError with the offending field."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc
    entries = raw.get("document")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest has no [[document]] entries")
    docs: list[SourceDocument] = []
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        docs.append(_parse_entry(i, entry))
        if docs[-1].id in seen:
            raise ManifestError(f"duplicate document id {docs[-1].id!r}")
        seen.add(docs[-1].id)
    return tuple(docs)


def _parse_entry(i: int, entry: object) -> SourceDocument:
    if not isinstance(entry, dict):
        raise ManifestError(f"document #{i} is not a table")

    def text(key: str) -> str:
        value = entry.get(key)
        if not isinstance(value, str) or not value:
            raise ManifestError(f"document #{i}: missing or empty {key}")
        return value

    doc_id, kind, url, sha = text("id"), text("kind"), text("url"), text("sha256")
    if kind not in KINDS:
        raise ManifestError(f"document {doc_id}: kind {kind!r} not in {KINDS}")
    if not url.startswith("https://"):
        raise ManifestError(f"document {doc_id}: url must be https")
    if not _SHA256.fullmatch(sha):
        raise ManifestError(f"document {doc_id}: sha256 must be 64 lowercase hex characters")
    register_date = text("register_date")
    try:
        date.fromisoformat(register_date)
    except ValueError as exc:
        raise ManifestError(f"document {doc_id}: register_date is not ISO 8601") from exc
    pages = entry.get("pages")
    if not isinstance(pages, int) or pages < 1:
        raise ManifestError(f"document {doc_id}: pages must be a positive integer")
    sections: dict[str, tuple[int, int]] = {}
    for name, span in (entry.get("expected_sections") or {}).items():
        if not (isinstance(span, list) and len(span) == 2 and all(isinstance(p, int) for p in span)):
            raise ManifestError(f"document {doc_id}: expected_sections.{name} must be [first, last]")
        sections[name] = (span[0], span[1])
    return SourceDocument(doc_id, kind, url, sha, register_date, pages, sections)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_cached(
    doc: SourceDocument,
    cache_dir: Path = DEFAULT_CACHE,
    fetch: Fetcher | None = None,
    *,
    offline: bool = False,
) -> Path:
    """Return the path of the verified PDF, fetching it on a cache miss (fail closed on any mismatch)."""
    target = cache_dir / f"{doc.sha256}.pdf"
    if target.exists():
        actual = sha256_of(target.read_bytes())
        if actual != doc.sha256:
            raise SourceIntegrityError(
                f"{doc.id}: cached file {target} has sha256 {actual}; delete it and refetch"
            )
        return target
    if offline:
        raise SourceUnavailableError(f"{doc.id}: not in cache {cache_dir} and --offline was given")
    data = fetch_with_retries(doc.url, fetch or httpx_fetcher())
    actual = sha256_of(data)
    if actual != doc.sha256:
        raise SourceIntegrityError(f"{doc.id}: downloaded sha256 {actual} != pinned {doc.sha256}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache_dir, prefix=".partial-", suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)  # atomic on POSIX: readers see the old state or the complete file
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def fetch_with_retries(
    url: str,
    fetch: Fetcher,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """Call `fetch`, retrying transport errors and 5xx with exponential backoff (1 s, 2 s, ...)."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetch(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise SourceUnavailableError(f"{url}: HTTP {exc.response.status_code}") from exc
            last = exc
        except httpx.TransportError as exc:
            last = exc
        if attempt < attempts - 1:
            sleep(float(2**attempt))
    raise SourceUnavailableError(f"{url}: failed after {attempts} attempts: {last}") from last


def httpx_fetcher(transport: httpx.BaseTransport | None = None, timeout: float = 60.0) -> Fetcher:
    """A fetcher over HTTPS with a descriptive User-Agent; raises httpx errors for the retry policy."""

    def fetch(url: str) -> bytes:
        with httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    return fetch
