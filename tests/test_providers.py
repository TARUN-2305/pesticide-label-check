"""L3 §6-7: key loading and the OpenAI-compatible chat client. No network: httpx.MockTransport."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest

from labelclaim.assistant.providers import ChatClient, ProviderError, Router, ToolCall
from labelclaim.assistant.secrets import SecretsError, load_keys

TOOLS = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]


def client(handler: httpx.MockTransport | None = None, **kw: object) -> ChatClient:
    transport = handler or httpx.MockTransport(lambda r: httpx.Response(200, json=_tool_reply()))
    return ChatClient("groq", "https://api.example/v1", "SECRET-KEY", "model-a", transport=transport, **kw)  # type: ignore[arg-type]


def _tool_reply(name: str = "lookup", args: str = '{"crop": "tomato"}') -> dict[str, object]:
    call = {"id": "c1", "type": "function", "function": {"name": name, "arguments": args}}
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}  # fmt: skip


# --- keys ------------------------------------------------------------------------------------------


def test_keys_come_from_an_owner_only_file(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.write_text('GROQ_API_KEY="g-1"\nGEMINI_API_KEY=m-2\n# comment\n', encoding="utf-8")
    env.chmod(0o600)
    assert load_keys(env, environ={}) == {"GROQ_API_KEY": "g-1", "GEMINI_API_KEY": "m-2"}


def test_a_file_readable_by_others_is_refused(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.write_text("GROQ_API_KEY=g-1\n", encoding="utf-8")
    env.chmod(0o644)
    with pytest.raises(SecretsError, match="mode 644"):
        load_keys(env, environ={})


def test_environment_variables_win_and_a_missing_file_is_fine(tmp_path: Path) -> None:
    assert load_keys(tmp_path / "absent", environ={"GEMINI_API_KEY": "m-env"}) == {"GEMINI_API_KEY": "m-env"}


def test_the_error_never_contains_a_key(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.write_text("GROQ_API_KEY=very-secret\n", encoding="utf-8")
    env.chmod(0o640)
    with pytest.raises(SecretsError) as err:
        load_keys(env, environ={})
    assert "very-secret" not in str(err.value)


# --- client ----------------------------------------------------------------------------------------


def test_a_tool_call_request_and_reply() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_tool_reply())

    reply = client(httpx.MockTransport(handler), strict=True).chat(
        [{"role": "user", "content": "q"}], tools=TOOLS, tool_choice="required"
    )
    body = json.loads(seen[0].content)
    assert seen[0].url == "https://api.example/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer SECRET-KEY"
    assert body["model"] == "model-a"
    assert body["temperature"] == 0
    assert body["tool_choice"] == "required"
    assert body["tools"][0]["function"]["strict"] is True
    assert reply.tool_call == ToolCall("c1", "lookup", {"crop": "tomato"})
    assert (reply.prompt_tokens, reply.completion_tokens) == (10, 5)


def test_strict_is_not_sent_to_a_provider_that_does_not_take_it() -> None:
    seen: list[dict[str, object]] = []
    transport = httpx.MockTransport(
        lambda r: (seen.append(json.loads(r.content)), httpx.Response(200, json=_tool_reply()))[1]
    )
    client(transport, strict=False).chat(
        [{"role": "user", "content": "q"}], tools=TOOLS, tool_choice="required"
    )
    assert "strict" not in seen[0]["tools"][0]["function"]  # type: ignore[index]


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (httpx.Response(429, headers={"retry-after": "7"}, json={}), "rate_limited"),
        (httpx.Response(503, json={}), "server"),
        (httpx.Response(401, json={}), "auth"),
        (httpx.Response(200, json={"choices": []}), "bad_response"),
        (httpx.Response(200, json=_tool_reply(args="{not json")), "bad_response"),
    ],
)
def test_failures_are_typed(response: httpx.Response, kind: str) -> None:
    with pytest.raises(ProviderError) as err:
        client(httpx.MockTransport(lambda r: response)).chat([{"role": "user", "content": "q"}])
    assert err.value.kind == kind
    if kind == "rate_limited":
        assert err.value.retry_after == 7.0


def test_a_timeout_is_a_provider_error() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError) as err:
        client(httpx.MockTransport(slow)).chat([{"role": "user", "content": "q"}])
    assert err.value.kind == "timeout"


def test_the_model_check_accepts_a_models_prefix() -> None:
    listing = {"data": [{"id": "models/gemini-2.5-flash"}, {"id": "other"}]}
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=listing))
    gemini = ChatClient("gemini", "https://g.example/v1", "K", "gemini-2.5-flash", transport=transport)
    assert gemini.model_available()
    assert not ChatClient(
        "gemini", "https://g.example/v1", "K", "absent", transport=transport
    ).model_available()


def test_the_key_never_reaches_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ProviderError):
        client(httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "bad key SECRET-KEY"}))).chat(
            [{"role": "user", "content": "q"}]
        )
    assert "SECRET-KEY" not in caplog.text


# --- router ----------------------------------------------------------------------------------------


class Fake:
    def __init__(self, name: str, outcomes: list[object]) -> None:
        self.name, self.outcomes, self.calls = name, outcomes, 0

    def __call__(self) -> str:
        self.calls += 1
        result = self.outcomes.pop(0)
        if isinstance(result, ProviderError):
            raise result
        return str(result)


def test_the_router_falls_back_and_cools_down_a_rate_limited_provider() -> None:
    now = [100.0]
    router = Router(["groq", "gemini"], clock=lambda: now[0])
    groq = Fake("groq", [ProviderError("rate_limited", retry_after=30.0), "g2"])
    gemini = Fake("gemini", ["m1", "m2"])
    fns = {"groq": groq, "gemini": gemini}
    assert router.run(lambda name: fns[name]()) == ("gemini", "m1")
    now[0] = 120.0  # still cooling: groq is skipped
    assert router.run(lambda name: fns[name]()) == ("gemini", "m2")
    assert groq.calls == 1
    now[0] = 131.0
    assert router.run(lambda name: fns[name]()) == ("groq", "g2")


def test_when_every_provider_fails_the_router_says_so() -> None:
    router = Router(["groq", "gemini"])
    with pytest.raises(ProviderError) as err:
        router.run(lambda name: (_ for _ in ()).throw(ProviderError("server")))
    assert err.value.kind == "unavailable"


def test_a_listed_model_that_refuses_a_call_is_not_used() -> None:
    # Live 2026-11-15: gemini-2.5-flash was listed by GET /models but answered 404 "no longer available".
    listing = {"data": [{"id": "models/m"}]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=listing)
        return httpx.Response(404, json={"error": {"message": "no longer available"}})

    c = ChatClient("gemini", "https://g.example/v1", "K", "m", transport=httpx.MockTransport(handler))
    assert c.model_available()
    assert not c.usable()


def test_build_clients_keeps_only_usable_providers_in_order() -> None:
    from labelclaim.assistant.providers import GEMINI, build_clients  # noqa: PLC0415

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.groq.com":
            return httpx.Response(503, json={})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": f"models/{GEMINI[2]}"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    clients = build_clients(
        {"GROQ_API_KEY": "a", "GEMINI_API_KEY": "b"}, transport=httpx.MockTransport(handler)
    )
    assert list(clients) == ["gemini"]
    assert build_clients({}, transport=httpx.MockTransport(handler)) == {}


def test_fix4_a_model_that_declined_to_call_a_tool_is_typed_declined() -> None:
    body = {
        "error": {
            "code": "tool_use_failed",
            "message": "Tool choice is required, but model did not call a tool",
        }
    }
    with pytest.raises(ProviderError) as err:
        client(httpx.MockTransport(lambda r: httpx.Response(400, json=body))).chat(
            [{"role": "user", "content": "q"}]
        )
    assert err.value.kind == "declined"


def test_the_first_gemini_model_that_serves_is_used() -> None:
    # 2026-11-16..18: gemini-3.5-flash timed out on every check while gemini-3.5-flash-lite answered in 1.8 s.
    from labelclaim.assistant.providers import GEMINI_MODELS, build_clients  # noqa: PLC0415

    first, second = GEMINI_MODELS[0], GEMINI_MODELS[1]
    listing = {"data": [{"id": f"models/{m}"} for m in GEMINI_MODELS]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=listing)
        model = json.loads(request.content)["model"]
        if model == first:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    clients = build_clients({"GEMINI_API_KEY": "k"}, transport=httpx.MockTransport(handler))
    assert clients["gemini"].model == second
