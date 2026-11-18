"""L4 (M6): the web app as served by the API. Written before running; the browser checks are in L4 §6."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from labelclaim.api.app import SECURITY_HEADERS, Settings, create_app
from labelclaim.api.ratelimit import DailyCap
from labelclaim.assistant.providers import ChatReply, ToolCall
from tests.registerkit import build_fixture

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "web"


@pytest.fixture(scope="module")
def register(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("web") / "register.sqlite"
    build_fixture(path)
    return path


@pytest.fixture
def client(register: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(register=register, rate_per_minute=1000, web_dir=WEB))) as c:
        yield c


def test_the_page_and_its_files_are_served_with_the_security_headers(client: TestClient) -> None:
    for path, kind in (("/", "text/html"), ("/app.js", "javascript"), ("/style.css", "text/css")):
        r = client.get(path)
        assert r.status_code == 200, path
        assert kind in r.headers["content-type"]
        for name, value in SECURITY_HEADERS.items():
            assert r.headers[name] == value
        assert r.headers["cache-control"] == "no-cache"  # a stale app.js after a deploy was seen 2026-11-18
    assert "script-src 'self'" in SECURITY_HEADERS["content-security-policy"]


def test_the_api_keeps_its_routes_and_its_error_envelope_next_to_the_page(client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"
    r = client.get("/no-such-file.js")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    assert client.get("/../pyproject.toml").status_code == 404  # nothing outside web/


def test_the_swagger_page_is_not_given_a_policy_it_cannot_meet(client: TestClient) -> None:
    assert "content-security-policy" not in client.get("/docs").headers


def test_the_page_never_puts_api_text_in_as_html() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")
    for sink in ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write"):
        assert sink not in script
    page = (WEB / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in page  # no inline script for the CSP to allow
    assert "onclick" not in page


def test_lookup_returns_the_same_template_headline_as_ask(client: TestClient) -> None:
    body = client.post(
        "/v1/lookup",
        json={"product": "Chlorantraniliprole 18.5% SC", "crop": "tomato", "pest": "fruit borer"},
    ).json()
    assert body["headline"].startswith("Approved")


class _Fake:
    name, model = "groq", "groq-model"

    def __init__(self) -> None:
        self.n = 0

    def chat(self, *_: Any, **__: Any) -> ChatReply:
        self.n += 1
        if self.n % 2:
            args = {
                "product": "Chlorantraniliprole 18.5% SC",
                "ingredient": None,
                "crop": "tomato",
                "pest": None,
            }
            return ChatReply(None, ToolCall("c", "lookup", args), 1, 1, 1.0)
        return ChatReply("Approved.", None, 1, 1, 1.0)


def test_the_daily_cap_stops_ask_but_not_lookup(register: Path) -> None:
    now = [86400.0 * 20000 + 10]
    settings = Settings(register=register, rate_per_minute=1000, chat_clients={"groq": _Fake()},
                        ask_per_day=2, wall_clock=lambda: now[0])  # fmt: skip
    with TestClient(create_app(settings)) as c:
        q = {"question": "coragen on tomato?"}
        assert [c.post("/v1/ask", json=q).status_code for _ in range(3)] == [200, 200, 429]
        assert c.post("/v1/ask", json=q).json()["error"]["code"] == "daily_limit"
        assert (
            c.post(
                "/v1/lookup", json={"product": "Chlorantraniliprole 18.5% SC", "crop": "tomato"}
            ).status_code
            == 200
        )
        now[0] += 86400  # the next UTC day
        assert c.post("/v1/ask", json=q).status_code == 200


def test_the_daily_cap_counts_per_utc_day() -> None:
    now = [0.0]
    cap = DailyCap(1, lambda: now[0])
    assert cap.allow()
    assert not cap.allow()
    now[0] = 86399.0
    assert not cap.allow()
    now[0] = 86400.0
    assert cap.allow()
