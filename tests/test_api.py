"""L2 §8 `api`: the HTTP contract over the fixture register (written before the API)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labelclaim.api.app import Settings, create_app, openapi_document
from tests.registerkit import build_fixture

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def register(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("api") / "register.sqlite"
    build_fixture(path)
    return path


@pytest.fixture
def client(register: Path) -> Iterator[TestClient]:
    with TestClient(
        create_app(Settings(register=register, rate_per_minute=1000)), raise_server_exceptions=False
    ) as c:
        yield c


def test_lookup_approved(client: TestClient) -> None:
    r = client.post(
        "/v1/lookup",
        json={"product": "Chlorantraniliprole 18.5% SC", "crop": "tomato", "pest": "fruit borer"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "APPROVED"
    assert body["conflict"] is False
    use = body["uses"][0]
    assert (use["dose_ai_raw"], use["wait_raw"], use["citation"]["page_first"]) == ("30", "3", 10)
    assert use["citation"]["url"].endswith("#page=10")
    assert "not for legal purposes" in body["disclaimer"]
    assert body["register"]["dates"] == {"ins": "2026-09-30"}
    assert r.headers["x-request-id"]


def test_not_found_answer_is_200_with_an_outcome(client: TestClient) -> None:
    r = client.post("/v1/lookup", json={"ingredient": "imaginol", "crop": "tomato"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "UNKNOWN_PRODUCT"


def test_conflict_flag_in_the_response(client: TestClient) -> None:
    body = client.post("/v1/lookup", json={"product": "Chlorpyriphos 20% EC", "crop": "citrus"}).json()
    assert body["conflict"] is True
    assert body["restrictions"][0]["names_the_crop"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"product": "X 5% EC", "ingredient": "x", "crop": "rice"},
        {"crop": "rice"},
        {"ingredient": "x"},
        {"ingredient": "x", "crop": "rice", "colour": "red"},
        {"ingredient": "x", "crop": "r" * 121},
        {"ingredient": "x", "crop": "   "},
    ],
)
def test_invalid_requests_get_422_in_the_envelope(client: TestClient, payload: dict[str, str]) -> None:
    r = client.post("/v1/lookup", json=payload)
    assert r.status_code == 422
    assert set(r.json()) == {"error"}
    assert r.json()["error"]["code"] == "invalid_request"
    assert r.json()["error"]["request_id"] == r.headers["x-request-id"]


def test_404_405_use_the_envelope(client: TestClient) -> None:
    assert client.get("/v1/nope").json()["error"]["code"] == "not_found"
    r = client.get("/v1/lookup")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"


def test_internal_errors_hide_details(register: Path) -> None:
    app = create_app(Settings(register=register))

    def boom() -> None:
        raise RuntimeError("secret detail")

    app.add_api_route("/boom", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "secret" not in r.text


def test_rate_limit_returns_429_in_the_envelope(register: Path) -> None:
    with TestClient(create_app(Settings(register=register, rate_per_minute=2))) as c:
        codes = [c.get("/v1/register").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_access_log_never_contains_the_query_text(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="labelclaim.access")
    client.post("/v1/lookup", json={"ingredient": "uniquesecretname", "crop": "tomato"})
    records = [r.getMessage() for r in caplog.records if r.name == "labelclaim.access"]
    assert records
    assert all("uniquesecretname" not in m and "tomato" not in m for m in records)
    assert json.loads(records[-1])["outcome"] == "UNKNOWN_PRODUCT"


def test_search_endpoints(client: TestClient) -> None:
    crops = client.get("/v1/crops", params={"q": "chil"}).json()
    assert {"id": "chilli", "display": "chilli"} in crops
    products = client.get("/v1/products", params={"q": "chlorant"}).json()
    assert [p["heading"] for p in products] == ["Chlorantraniliprole 0.4% GR", "Chlorantraniliprole 18.5% SC"]
    pests = client.get("/v1/pests", params={"q": "borer", "crop": "rice"}).json()
    assert [p["id"] for p in pests] == ["stem_borer"]
    assert client.get("/v1/crops", params={"q": ""}).status_code == 422


def test_health_and_register_info(client: TestClient) -> None:
    health = client.get("/healthz").json()
    assert health["status"] == "ok"
    assert len(health["build_hash"]) == 64
    assert client.get("/v1/register").headers["cache-control"].startswith("public")


def test_committed_openapi_is_fresh(register: Path) -> None:
    committed = json.loads((REPO / "openapi.json").read_text(encoding="utf-8"))
    assert committed == openapi_document(Settings(register=register)), (
        "run: python -m labelclaim.api --export-openapi openapi.json"
    )


def test_product_field_fits_the_longest_register_heading(client: TestClient) -> None:
    long_heading = (
        "Cyantraniliprole 7.3% w/w + Diafenthiuron 36.4% w/w SC " + "(note) " * 15
    )  # about 160 characters
    assert client.post("/v1/lookup", json={"product": long_heading, "crop": "tomato"}).status_code == 200
    assert client.post("/v1/lookup", json={"product": "x" * 201, "crop": "tomato"}).status_code == 422
