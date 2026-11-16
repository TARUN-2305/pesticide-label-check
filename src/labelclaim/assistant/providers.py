"""OpenAI-compatible chat client and the provider fallback chain (L3 §6, ADR-008).

One small httpx client speaks `POST {base}/chat/completions` for Groq and for Gemini's OpenAI endpoint.
Failures are typed so the router can fall back; nothing here logs a key, a question or a reply.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

import httpx

from labelclaim.errors import LabelClaimError

LOG = logging.getLogger("labelclaim.assistant")
T = TypeVar("T")
Kind = Literal[
    "timeout", "rate_limited", "server", "auth", "bad_response", "bad_tool_call", "declined", "unavailable"
]
GROQ = ("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b")
# Live checks, 2026-11-15 (ADR-008): gemini-2.5-flash is listed but answers 404 "no longer available to new
# users"; gemini-3.8-flash (which that error recommends) timed out at 60 s on a two-word prompt;
# gemini-3.5-flash answered in 1.3 s.
GEMINI = ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash")


class ProviderError(LabelClaimError):
    def __init__(self, kind: Kind, detail: str = "", retry_after: float | None = None) -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.retry_after = retry_after


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    raw: dict[str, Any] | None = field(
        default=None, compare=False
    )  # echoed back as sent (Gemini 3 signatures)


@dataclass(frozen=True)
class ChatReply:
    content: str | None
    tool_call: ToolCall | None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


class ChatClient:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        *,
        strict: bool = False,
        extra: dict[str, Any] | None = None,
        timeout: float = 8.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name, self.model, self.strict, self.extra = name, model, strict, dict(extra or {})
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def model_available(self) -> bool:
        """The configured model is in the provider's list (Gemini lists ids as 'models/<id>')."""
        try:
            response = self._http.get("models")
        except httpx.HTTPError:
            return False
        if response.status_code != 200:
            return False
        ids = {str(m.get("id", "")).removeprefix("models/") for m in response.json().get("data", [])}
        return self.model in ids

    def usable(self) -> bool:
        """One tiny real call: a listed model can still refuse to serve (Gemini, 2026-11-15)."""
        try:
            self.chat([{"role": "user", "content": "Reply with: ok"}], max_tokens=16)
        except ProviderError:
            return False
        return True

    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        max_tokens: int = 1024,
    ) -> ChatReply:
        body: dict[str, Any] = {"model": self.model, "messages": list(messages), "temperature": 0,
                                "max_tokens": max_tokens, **self.extra}  # fmt: skip
        if tools:
            body["tools"] = [self._tool(t) for t in tools]
            body["tool_choice"] = tool_choice or "auto"
        started = time.perf_counter()
        try:
            response = self._http.post("chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("server", f"{self.name}: {type(exc).__name__}") from exc
        latency = round((time.perf_counter() - started) * 1000, 1)
        self._raise_for_status(response)
        reply = self._parse(response, latency)
        LOG.info(
            json.dumps(
                {
                    "provider": self.name,
                    "model": self.model,
                    "latency_ms": latency,
                    "prompt_tokens": reply.prompt_tokens,
                    "completion_tokens": reply.completion_tokens,
                    "tool": reply.tool_call.name if reply.tool_call else None,
                }
            )
        )
        return reply

    def _tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        function = dict(tool["function"])
        if self.strict:
            function["strict"] = True
        else:
            function.pop("strict", None)
        return {"type": "function", "function": function}

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status == 429:
            retry = response.headers.get("retry-after")
            raise ProviderError("rate_limited", self.name, float(retry) if retry and _number(retry) else 30.0)
        if status in (401, 403):
            raise ProviderError("auth", f"{self.name} HTTP {status}")
        if status >= 500:
            raise ProviderError("server", f"{self.name} HTTP {status}")
        if (
            status == 400 and "tool_use_failed" in response.text
        ):  # the model wrote prose instead of a tool call
            raise ProviderError("declined", self.name)
        if status != 200:
            raise ProviderError("bad_response", f"{self.name} HTTP {status}")

    def _parse(self, response: httpx.Response, latency: float) -> ChatReply:
        try:
            data = response.json()
            message = data["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            call = None
            if calls:
                fn = calls[0]["function"]
                args = json.loads(fn.get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise TypeError("arguments are not an object")
                call = ToolCall(str(calls[0].get("id", "call")), str(fn["name"]), args, dict(calls[0]))
            usage = data.get("usage") or {}
            return ChatReply(message.get("content"), call, int(usage.get("prompt_tokens", 0)),
                             int(usage.get("completion_tokens", 0)), latency)  # fmt: skip
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("bad_response", f"{self.name}: {type(exc).__name__}") from exc

    def close(self) -> None:
        self._http.close()


def _number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


class Router:
    """Try providers in order, skipping any in a rate-limit cool-down; thread-safe."""

    def __init__(self, names: Sequence[str], clock: Callable[[], float] = time.monotonic) -> None:
        self.names = list(names)
        self._clock = clock
        self._until: dict[str, float] = {}
        self._lock = threading.Lock()

    def run(self, attempt: Callable[[str], T]) -> tuple[str, T]:
        errors: list[str] = []
        for name in self.names:
            with self._lock:
                if self._until.get(name, 0.0) > self._clock():
                    errors.append(f"{name}: cooling down")
                    continue
            try:
                return name, attempt(name)
            except ProviderError as exc:
                errors.append(f"{name}: {exc.kind}")
                LOG.warning(json.dumps({"provider": name, "failure": exc.kind}))
                if exc.kind == "rate_limited":
                    with self._lock:
                        self._until[name] = self._clock() + (exc.retry_after or 30.0)
        raise ProviderError("unavailable", "; ".join(errors))


def build_clients(
    keys: dict[str, str], *, check_models: bool = True, transport: httpx.BaseTransport | None = None
) -> dict[str, ChatClient]:
    """Clients in fallback order (Groq, then Gemini) for every key present whose model the provider lists.
    A provider without a key, or whose model is gone, is left out and logged (names only)."""
    plan = [
        (GROQ, "GROQ_API_KEY", {"strict": True, "extra": {"reasoning_effort": "low"}}),
        # the fallback gets a longer timeout: its free tier took > 8 s for a two-word reply (2026-11-16)
        (GEMINI, "GEMINI_API_KEY", {"strict": False, "extra": {}, "timeout": 20.0}),
    ]
    clients: dict[str, ChatClient] = {}
    for (name, base, model), key_name, options in plan:
        if not keys.get(key_name):
            LOG.warning(json.dumps({"provider": name, "disabled": "no key"}))
            continue
        client = ChatClient(name, base, keys[key_name], model, transport=transport, **options)  # type: ignore[arg-type]
        if check_models and not (client.model_available() and client.usable()):
            LOG.warning(
                json.dumps({"provider": name, "disabled": f"model {model} not listed or not serving"})
            )
            client.close()
            continue
        clients[name] = client
    return clients
