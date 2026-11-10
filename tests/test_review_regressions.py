"""Spec regressions found during Task 12; upstream traffic always uses MockTransport."""
import asyncio
import base64
import json
from dataclasses import replace

import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings
from src.contract import Limits, parse_request
from src.errors import GatewayError
from src.failure import upstream_error
from src.gateways import build_gateway
from src.gateways.anthropic import message_params
from src.service import ChatService
from src.store import GatewayStore
from tests.helpers import chat, LIMITS
from tests.test_anthropic import ENTRY, MESSAGE, sse
from tests.test_openai import CHAT, RESPONSES, COMPLETION, RESP
from tests.test_scuti import PLAIN, BODY


@pytest.mark.parametrize("fields", [
    {"messages": [{"role": [], "content": "x"}]},
    {"messages": [{"role": "user", "content": [{"type": []}]}]},
    {"messages": [{"role": "user", "content": [{"type": "image", "media_type": [], "data": "aGk="}]}]},
    {"tools": [{"name": "t"}], "tool_choice": {"name": []}},
])
def test_malformed_field_types_are_422(fields):
    with pytest.raises(GatewayError) as error:
        chat(**fields)
    assert error.value.status == 422


@pytest.mark.parametrize("data", [{"provider": []}, {"provider": "openai", "auth": []}])
def test_malformed_gateway_enums_are_safe(tmp_path, data):
    with pytest.raises(ValueError):
        GatewayStore(tmp_path / "g.json").put("g", data)


def test_image_boundary_counts_decoded_bytes():
    small = replace(LIMITS, max_image_bytes=4)
    parse_request({"gateway": "g", "messages": [{"role": "user", "content": [
        {"type": "image", "media_type": "image/png", "data": base64.b64encode(b"1234").decode()}]}]}, small)


@pytest.mark.parametrize("header", ["inf", "-inf", "nan", "garbage"])
def test_bad_retry_after_never_escapes(header):
    assert 1 <= upstream_error(429, "slow", header).retry_after <= 60


@pytest.mark.parametrize("entry,reply,field", [(ENTRY, MESSAGE, "max_tokens"), (CHAT, COMPLETION, "max_tokens"),
                                                (RESPONSES, RESP, "max_output_tokens"), (PLAIN, BODY, "max_tokens")])
async def test_ceiling_applies_when_request_omits_max_tokens(tmp_path, entry, reply, field):
    store = GatewayStore(tmp_path / "g.json")
    store.put("g", {**entry, "max_tokens_limit": 100})
    seen = {}
    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=reply)
    svc = ChatService(store, Settings(), httpx.MockTransport(handler))
    await svc.chat(chat())
    assert seen[field] <= 100
    await svc.aclose()


@pytest.mark.parametrize("effort", ["medium", "high"])
def test_anthropic_thinking_default_allows_budget(effort):
    params = message_params(chat(reasoning={"effort": effort}), "m", 4096)
    assert params["max_tokens"] > params["thinking"]["budget_tokens"]


def test_anthropic_insufficient_explicit_budget_is_refused():
    gateway = build_gateway("g", ENTRY, httpx.MockTransport(lambda r: None))
    with pytest.raises(GatewayError) as error:
        gateway.validate(chat(reasoning={"budget_tokens": 2000}, max_tokens=100))
    assert error.value.status == 422


@pytest.mark.parametrize("choice", ["none", "required", {"name": "t"}])
async def test_scuti_tool_choice_is_not_silently_dropped(choice):
    calls = []
    gateway = build_gateway("g", PLAIN, httpx.MockTransport(lambda r: calls.append(r)))
    with pytest.raises(GatewayError) as error:
        gateway.validate(chat(tools=[{"name": "t"}], tool_choice=choice))
    assert error.value.status == 422 and calls == []


async def test_anthropic_signature_chunks_accumulate():
    events = [
        {"type": "message_start", "message": {**MESSAGE, "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "first"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "second"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
        {"type": "message_stop"},
    ]
    g = build_gateway("g", ENTRY, httpx.MockTransport(lambda r: httpx.Response(200, content=sse(events))))
    result = [i async for i in g.stream(chat(stream=True))][-1][1]
    assert json.loads(result.reasoning_state)[0]["signature"] == "firstsecond"


async def test_anthropic_invalid_streamed_tool_json_is_safe():
    events = [
        {"type": "message_start", "message": {**MESSAGE, "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "c", "name": "t", "input": {}}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "{"}},
        {"type": "message_stop"},
    ]
    g = build_gateway("g", ENTRY, httpx.MockTransport(lambda r: httpx.Response(200, content=sse(events))))
    with pytest.raises(GatewayError) as error:
        [i async for i in g.stream(chat(stream=True))]
    assert error.value.kind == "unavailable"


@pytest.mark.parametrize("entry", [ENTRY, CHAT, RESPONSES, PLAIN])
async def test_empty_upstream_object_is_unusable(entry):
    g = build_gateway("g", entry, httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(GatewayError) as error:
        await g.complete(chat())
    assert error.value.kind == "unavailable"


@pytest.mark.parametrize("entry,reply", [
    (CHAT, {**COMPLETION, "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": None, "refusal": "No"}}]}),
    (RESPONSES, {**RESP, "output": [{"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "No"}]}]}),
])
async def test_provider_refusal_is_normalized(entry, reply):
    g = build_gateway("g", entry, httpx.MockTransport(lambda r: httpx.Response(200, json=reply)))
    assert (await g.complete(chat())).stop_reason == "refusal"


@pytest.mark.parametrize("entry", [ENTRY, CHAT, PLAIN])
async def test_timeout_is_504_and_no_retry(entry):
    calls = []
    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("test timeout", request=request)
    g = build_gateway("g", entry, httpx.MockTransport(timeout))
    with pytest.raises(GatewayError) as error:
        await g.complete(chat())
    assert error.value.status == 504 and error.value.kind == "unavailable" and len(calls) == 1


async def test_chunked_body_stops_reading_at_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("src.app.MAX_BODY", 4)
    app = build_app(Settings(data_dir=tmp_path))
    consumed = []
    async def receive():
        consumed.append(1)
        if len(consumed) > 1:
            raise AssertionError("read past body limit")
        return {"type": "http.request", "body": b"12345", "more_body": True}
    sent = []
    async def send(message):
        sent.append(message)
    await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
               "path": "/api/chat", "raw_path": b"/api/chat", "query_string": b"", "headers": [],
               "server": ("test", 80), "client": ("test", 1), "root_path": ""}, receive, send)
    assert sent[0]["status"] == 413 and len(consumed) == 1


async def test_concurrent_cap_and_cancel_release(tmp_path):
    store = GatewayStore(tmp_path / "g.json")
    store.put("g", PLAIN)
    entered, release = asyncio.Event(), asyncio.Event()
    async def handler(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json=BODY)
    svc = ChatService(store, Settings(max_inflight=1), httpx.MockTransport(handler))
    first = asyncio.create_task(svc.chat(chat()))
    await entered.wait()
    with pytest.raises(GatewayError) as error:
        await svc.chat(chat())
    assert error.value.status == 429
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert svc._inflight == 0
    await svc.aclose()


async def test_gateway_replacement_delete_and_shutdown_close_clients(tmp_path):
    store = GatewayStore(tmp_path / "g.json")
    store.put("g", PLAIN)
    svc = ChatService(store, Settings(), httpx.MockTransport(lambda r: httpx.Response(200, json=BODY)))
    old = await svc._gateway("g")
    await asyncio.to_thread(store.put, "g", {**PLAIN, "label": "changed"})
    current = await svc._gateway("g")
    assert old.http.is_closed and current is not old
    await asyncio.to_thread(store.delete, "g")
    with pytest.raises(GatewayError):
        await svc._gateway("g")
    assert current.http.is_closed
    await asyncio.to_thread(store.put, "g", ENTRY)
    sdk = await svc._gateway("g")
    await svc.aclose()
    assert sdk.http.is_closed and sdk.client.is_closed()


def test_runtime_limits_apply_to_next_validation(tmp_path):
    store = GatewayStore(tmp_path / "gateways.json")
    store.put("g", PLAIN)
    c = TestClient(build_app(Settings(data_dir=tmp_path, admin_password="pw"), transport=httpx.MockTransport(lambda r: None)))
    assert c.put("/admin/settings", headers={"X-Admin-Password": "pw"}, json={"values": {"max_messages": 1}}).status_code == 200
    from tests.seed import seed_token
    seed_token(Settings(data_dir=tmp_path, admin_password="pw"))
    r = c.post("/api/validate", headers={"X-Internal-Token": "tok"}, json={"gateway": "g", "messages": [{"role": "user", "content": "Hi"}] * 2})
    assert r.status_code == 422

@pytest.mark.parametrize("status,kind", [(429, "rate_limit"), (402, "quota"), (401, "auth"), (503, "unavailable")])
async def test_scuti_stream_error_keeps_upstream_failure_kind(status, kind):
    line = json.dumps({"type": "error", "status": status, "message": "upstream mini_tok"})
    g = build_gateway("g", {**PLAIN, "token": "mini_tok"}, httpx.MockTransport(lambda r: httpx.Response(200, content=line.encode())))
    with pytest.raises(GatewayError) as error:
        [i async for i in g.stream(chat(stream=True))]
    assert error.value.kind == kind and "mini_tok" not in error.value.message


@pytest.mark.parametrize("field", ["model", "api_key"])
def test_required_provider_fields_cannot_be_whitespace(tmp_path, field):
    entry = {**ENTRY, field: "   "}
    with pytest.raises(ValueError):
        GatewayStore(tmp_path / "g.json").put("g", entry)


class FixtureStream(httpx.AsyncByteStream):
    """Track lifecycle of actual SDK response streams without network."""
    def __init__(self, data):
        self.data, self.closed = data, False

    async def __aiter__(self):
        yield self.data
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("entry,data", [
    (ENTRY, sse([{"type": "message_start", "message": {**MESSAGE, "content": []}},
                 {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                 {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "x"}}])),
    (CHAT, b'data: {"id":"c","object":"chat.completion.chunk","created":1,"model":"m","choices":[{"index":0,"delta":{"content":"x"},"finish_reason":null}]}\n\n'),
    (RESPONSES, b'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","sequence_number":1,"item_id":"m","output_index":0,"content_index":0,"delta":"x"}\n\n'),
])
async def test_sdk_stream_closes_on_consumer_disconnect(entry, data):
    wire = FixtureStream(data)
    g = build_gateway("g", entry, httpx.MockTransport(lambda r: httpx.Response(200, stream=wire)))
    items = g.stream(chat(stream=True))
    assert (await anext(items))[0] == "text"
    await items.aclose()
    assert wire.closed
    await g.aclose()


async def test_replacement_does_not_close_active_chat(tmp_path):
    store = GatewayStore(tmp_path / "g.json")
    store.put("g", PLAIN)
    entered, release = asyncio.Event(), asyncio.Event()
    async def handler(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json=BODY)
    svc = ChatService(store, Settings(), httpx.MockTransport(handler))
    old = await svc._gateway("g")
    task = asyncio.create_task(svc.chat(chat()))
    await entered.wait()
    await asyncio.to_thread(store.put, "g", {**PLAIN, "label": "new"})
    await svc._gateway("g")
    assert not old.http.is_closed
    release.set()
    assert (await task)["stop_reason"] == "end"
    assert old.http.is_closed
    await svc.aclose()


async def test_bedrock_variant_uses_signed_sdk_request():
    seen = {}
    def handler(request):
        seen.update(url=str(request.url), body=json.loads(request.content), signed=request.headers.get("authorization", "").startswith("AWS4-HMAC-SHA256"))
        return httpx.Response(200, json=MESSAGE)
    entry = {"provider": "anthropic", "auth": "bedrock", "model": "anthropic.test", "aws_region": "us-east-1",
             "aws_access_key_id": "fixture-access", "aws_secret_access_key": "fixture-secret"}
    g = build_gateway("g", entry, httpx.MockTransport(handler))
    assert (await g.complete(chat())) .stop_reason == "end"
    assert seen["signed"] and "/model/anthropic.test/invoke" in seen["url"] and "model" not in seen["body"]
    await g.aclose()


async def test_vertex_variant_uses_sdk_path_with_fixture_token():
    seen = {}
    def handler(request):
        seen.update(url=str(request.url), body=json.loads(request.content))
        return httpx.Response(200, json=MESSAGE)
    g = build_gateway("g", {"provider": "anthropic", "auth": "vertex", "model": "claude-test", "project_id": "fixture-project", "region": "us-east5"}, httpx.MockTransport(handler))
    g.client.access_token = "fixture-token"
    assert (await g.complete(chat())).stop_reason == "end"
    assert "/projects/fixture-project/locations/us-east5/publishers/anthropic/models/claude-test:rawPredict" in seen["url"]
    assert "model" not in seen["body"]
    await g.aclose()


async def test_azure_responses_uses_sdk_path():
    seen = {}
    def handler(request):
        seen.update(url=str(request.url))
        return httpx.Response(200, json=RESP)
    entry = {"provider": "openai", "auth": "azure", "api": "responses", "azure_endpoint": "https://fixture.openai.azure.com",
             "api_version": "2024-10-21", "api_key": "fixture-key", "model": "fixture-deployment"}
    g = build_gateway("g", entry, httpx.MockTransport(handler))
    assert (await g.complete(chat())).stop_reason == "tool_call"
    assert "/responses?api-version=2024-10-21" in seen["url"]
    await g.aclose()


async def test_redacted_reasoning_state_roundtrip():
    reply = {**MESSAGE, "content": [{"type": "redacted_thinking", "data": "opaque"}, {"type": "text", "text": "x"}]}
    seen = {}
    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=reply)
    g = build_gateway("g", ENTRY, httpx.MockTransport(handler))
    result = await g.complete(chat())
    await g.complete(chat(messages=[{"role": "assistant", "content": "x", "reasoning_state": result.reasoning_state}, {"role": "user", "content": "next"}]))
    assert seen["messages"][0]["content"][0] == {"type": "redacted_thinking", "data": "opaque"}
    await g.aclose()

async def test_provider_logs_exclude_chat_contents(caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    g = build_gateway("g", CHAT, httpx.MockTransport(lambda r: httpx.Response(200, json=COMPLETION)))
    await g.complete(chat(messages=[{"role": "user", "content": "private-prompt-marker"}], tools=[{"name": "private-tool-marker"}]))
    assert "private-prompt-marker" not in caplog.text and "private-tool-marker" not in caplog.text
    await g.aclose()


async def test_deleted_gateway_during_listing_does_not_break_response(tmp_path):
    class DeletingStore(GatewayStore):
        def public(self):
            rows = super().public()
            self.delete("g")
            return rows
    store = DeletingStore(tmp_path / "g.json")
    store.put("g", PLAIN)
    svc = ChatService(store, Settings(), httpx.MockTransport(lambda r: httpx.Response(200, json={"ready": True})))
    rows = await svc.gateways()
    assert isinstance(rows, list)
    await svc.aclose()


async def test_chat_does_not_store_content(tmp_path):
    store = GatewayStore(tmp_path / "g.json")
    store.put("g", PLAIN)
    before = {p.name for p in tmp_path.iterdir()}
    svc = ChatService(store, Settings(data_dir=tmp_path), httpx.MockTransport(lambda r: httpx.Response(200, json=BODY)))
    await svc.chat(chat())
    assert {p.name for p in tmp_path.iterdir()} == before
    await svc.aclose()


@pytest.mark.parametrize("choice", ["auto", "none", "required", {"name": "t"}])
def test_tool_choice_mappings_cover_all_choices(choice):
    from src.gateways.openai import chat_params, responses_params
    request = chat(tools=[{"name": "t"}], tool_choice=choice)
    anthropic = message_params(request, "m", 4096)["tool_choice"]
    if isinstance(choice, str):
        assert anthropic == {"type": {"auto": "auto", "none": "none", "required": "any"}[choice]}
        assert chat_params(request, "m", {})["tool_choice"] == choice
        assert responses_params(request, "m", {})["tool_choice"] == choice
    else:
        assert anthropic == {"type": "tool", "name": "t"}
        assert chat_params(request, "m", {})["tool_choice"] == {"type": "function", "function": {"name": "t"}}
        assert responses_params(request, "m", {})["tool_choice"] == {"type": "function", "name": "t"}


async def test_chat_stream_refusal_is_normalized():
    from tests.test_openai import sse as chat_sse
    chunks = [{"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m",
               "choices": [{"index": 0, "delta": {"refusal": "No"}, "finish_reason": "stop"}]}]
    g = build_gateway("g", CHAT, httpx.MockTransport(lambda r: httpx.Response(200, content=chat_sse(chunks))))
    result = [i async for i in g.stream(chat(stream=True))][-1][1]
    assert result.stop_reason == "refusal"
    await g.aclose()


async def test_malformed_usage_is_safe_gateway_error(tmp_path):
    store = GatewayStore(tmp_path / "g.json")
    store.put("g", PLAIN)
    svc = ChatService(store, Settings(), httpx.MockTransport(lambda r: httpx.Response(200, json={**BODY, "usage": {"input_tokens": "invalid"}})))
    with pytest.raises(GatewayError) as error:
        await svc.chat(chat())
    assert error.value.kind == "unavailable"
    await svc.aclose()