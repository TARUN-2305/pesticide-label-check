"""FastAPI application factory (L2 §6).

- Sync routes run in FastAPI's thread pool; each thread gets its own read-only Engine (SQLite connections
  are not shared across threads).
- One error envelope for every failure; a lookup that finds nothing is a 200 with an outcome.
- The access log records method, path, status, latency and outcome, never the query text (NFR-5).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from labelclaim.api.ratelimit import DailyCap, TokenBucket
from labelclaim.api.schemas import (
    AskOut,
    AskRequest,
    ErrorOut,
    HealthOut,
    LookupOut,
    LookupRequest,
    NameOut,
    ProductOut,
    RegisterOut,
)
from labelclaim.assistant.loop import Assistant, Chat
from labelclaim.assistant.providers import ProviderError, Router
from labelclaim.assistant.templates import headline
from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Query as LookupQuery
from labelclaim.normalize.lexicon import key

ACCESS = logging.getLogger("labelclaim.access")
MAX_RESULTS = 20
QueryText = Annotated[str, Query(min_length=1, max_length=80)]


@dataclass(frozen=True)
class Settings:
    register: Path
    rate_per_minute: int = 60
    cors_origins: tuple[str, ...] = ()
    clock: Callable[[], float] = field(default=time.monotonic, compare=False)
    chat_clients: dict[str, Chat] = field(default_factory=dict, compare=False)  # in fallback order (L3 §6)
    web_dir: Path | None = None  # L4: the static web app, served at /
    ask_per_day: int = 800  # L4 §3: below Groq's free 1,000 requests a day
    wall_clock: Callable[[], float] = field(default=time.time, compare=False)


# L4 §3, threat T-W1: no inline script, nothing from other origins. /docs loads Swagger UI from a CDN, so the
# policy is not applied there.
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}
UNSAFE_FOR_CSP = ("/docs", "/redoc")


class Engines:
    """One Engine per worker thread, all closed at shutdown."""

    def __init__(self, register: Path) -> None:
        self.register = register
        self._local = threading.local()
        self._all: list[Engine] = []
        self._lock = threading.Lock()

    def get(self) -> Engine:
        engine: Engine | None = getattr(self._local, "engine", None)
        if engine is None:
            engine = Engine(self.register)
            self._local.engine = engine
            with self._lock:
                self._all.append(engine)
        return engine

    def close(self) -> None:
        with self._lock:
            for engine in self._all:
                engine.close()
            self._all.clear()


def _error(status: int, code: str, message: str, request_id: str) -> JSONResponse:
    body = ErrorOut.model_validate({"error": {"code": code, "message": message, "request_id": request_id}})
    return JSONResponse(body.model_dump(), status_code=status, headers={"x-request-id": request_id})


def create_app(settings: Settings) -> FastAPI:
    engines = Engines(settings.register)
    bucket = TokenBucket(settings.rate_per_minute, settings.clock)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engines.close()

    app = FastAPI(
        title="Pesticide label-claim check",
        version="0.2.0",
        description="Answers from India's CIB&RC register 'Major Uses of Pesticides', with page citations.",
        lifespan=lifespan,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def envelope_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        request.state.outcome = None
        started = time.perf_counter()
        client = request.client.host if request.client else "unknown"
        if not bucket.allow(client):
            response: Response = _error(429, "rate_limited", "too many requests; retry shortly", request_id)
            response.headers["retry-after"] = "60"
        else:
            try:
                response = await call_next(request)
            except Exception:
                logging.getLogger("labelclaim.api").exception("unhandled error (request %s)", request_id)
                response = _error(500, "internal_error", "internal error", request_id)
        response.headers["x-request-id"] = request_id
        if not request.url.path.startswith(UNSAFE_FOR_CSP):
            response.headers.update(SECURITY_HEADERS)
        if not request.url.path.startswith(("/v1/", "/healthz")) and "cache-control" not in response.headers:
            response.headers["cache-control"] = "no-cache"  # L4: revalidate the page's files after a deploy
        ACCESS.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "outcome": request.state.outcome,
                }
            )
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', ())[1:]) or 'body'}: {e.get('msg')}"
            for e in exc.errors()
        )
        return _error(422, "invalid_request", problems[:500], request.state.request_id)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(exc.status_code, code, str(exc.detail), request.state.request_id)

    @app.get("/healthz", response_model=HealthOut)
    def healthz() -> HealthOut:
        return HealthOut(status="ok", build_hash=engines.get().register_info().build_hash)

    @app.get("/v1/register", response_model=RegisterOut)
    def register_info(response: Response) -> RegisterOut:
        response.headers["cache-control"] = "public, max-age=300"
        return RegisterOut.model_validate(engines.get().register_info())

    @app.post(
        "/v1/lookup", response_model=LookupOut, responses={422: {"model": ErrorOut}, 429: {"model": ErrorOut}}
    )
    def lookup(body: LookupRequest, request: Request) -> LookupOut:
        query = LookupQuery(crop=body.crop, product=body.product, ingredient=body.ingredient, pest=body.pest)
        answer = engines.get().lookup(query)
        request.state.outcome = answer.outcome.value
        head = headline(answer, query.product or query.ingredient or "", query.crop, query.pest,
                        by_ingredient=query.product is None)  # fmt: skip
        fields = {**_plain(asdict(answer)), "conflict": answer.conflict, "headline": head}
        return LookupOut.model_validate(fields)

    _mount_assistant(app, settings, engines)

    _mount_names(app, engines)

    if settings.web_dir is not None:  # last, so every API route above wins over a file of the same name
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app


def _mount_names(app: FastAPI, engines: Engines) -> None:
    """Name suggestions for the Check form (L2 §6)."""

    @app.get("/v1/crops", response_model=list[NameOut])
    def crops(q: QueryText) -> list[NameOut]:
        names = engines.get().names
        return [NameOut(id=i, display=names.crop_display[i]) for i in _search(q, names.crop_alias)]

    @app.get("/v1/pests", response_model=list[NameOut])
    def pests(q: QueryText, crop: Annotated[str | None, Query(max_length=80)] = None) -> list[NameOut]:
        engine = engines.get()
        allowed: set[str] | None = None
        if crop:
            resolved = engine.names.crop(crop)
            allowed = engine.pest_ids_on(resolved.ids) if resolved.status == "exact" else set()
        hits = [i for i in _search(q, engine.names.pest_alias, limit=200) if allowed is None or i in allowed]
        return [NameOut(id=i, display=engine.names.pest_display[i]) for i in hits[:MAX_RESULTS]]

    @app.get("/v1/products", response_model=list[ProductOut])
    def products(q: QueryText) -> list[ProductOut]:
        needle = q.casefold().strip()
        headings = engines.get().names.heading
        hits = sorted((h, pid) for pid, h in headings.items() if needle in h.casefold())
        return [ProductOut(id=pid, heading=h) for h, pid in hits[:MAX_RESULTS]]


def _mount_assistant(app: FastAPI, settings: Settings, engines: Engines) -> None:
    """POST /v1/ask (L3): the model interprets and phrases; the engine decides."""
    router = Router(list(settings.chat_clients))
    cap = DailyCap(settings.ask_per_day, settings.wall_clock)

    @app.post(
        "/v1/ask",
        response_model=AskOut,
        responses={422: {"model": ErrorOut}, 429: {"model": ErrorOut}, 503: {"model": ErrorOut}},
    )
    def ask(body: AskRequest, request: Request) -> AskOut | JSONResponse:
        """A plain-words question (L3). The model only interprets and phrases; the engine decides."""
        if not settings.chat_clients:
            return _error(503, "assistant_unavailable", "no model is configured; use POST /v1/lookup",
                          request.state.request_id)  # fmt: skip
        if not cap.allow():  # L4 §3: the shared daily quota of the free model tier
            return _error(429, "daily_limit", "the assistant's daily limit is reached; use POST /v1/lookup",
                          request.state.request_id)  # fmt: skip
        try:
            result = Assistant(engines.get(), settings.chat_clients, router).ask(body.question, body.lang)
        except ProviderError:
            return _error(503, "assistant_unavailable", "the models are unavailable; use POST /v1/lookup",
                          request.state.request_id)  # fmt: skip
        answer = result.answer
        request.state.outcome = answer.outcome.value if answer else "CLARIFY"
        return AskOut.model_validate({
            **_plain(asdict(result)),
            "answer": {**_plain(asdict(answer)), "conflict": answer.conflict} if answer else None,
        })  # fmt: skip


def _search(q: str, aliases: dict[str, set[str]], limit: int = MAX_RESULTS) -> list[str]:
    """Ids whose alias starts with or contains the query key: prefix matches first, then alphabetical."""
    k = key(q)
    ranked = sorted((not alias.startswith(k), alias) for alias in aliases if k in alias)
    out: list[str] = []
    for _, alias in ranked:
        for target in sorted(aliases[alias]):
            if target not in out:
                out.append(target)
    return out[:limit]


def _plain(value: Any) -> Any:
    """asdict() keeps tuples; Pydantic accepts them, but enums stay as their values for the response."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def openapi_document(settings: Settings) -> dict[str, Any]:
    return create_app(settings).openapi()
