import json

import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings
from src.store import GatewayStore
from tests.seed import seed_token

TOKEN = {"X-Internal-Token": "tok"}
BODY = {"content": "Hello", "thinking": None, "tool_calls": [], "finish_reason": "stop", "model": "lfm3", "usage": {"input_tokens": 3, "output_tokens": 2}}


def upstream(request):
    if str(request.url).endswith("/health"):
        return httpx.Response(200, json={"ready": True})
    if json.loads(request.content).get("stream"):
        lines = [{"type": "content", "text": "Hel"}, {"type": "content", "text": "lo"}, {"type": "done", **BODY, "content": "Hello"}]
        return httpx.Response(200, content="\n".join(map(json.dumps, lines)).encode())
    return httpx.Response(200, json=BODY)


@pytest.fixture
def settings(tmp_path):
    GatewayStore(tmp_path / "gateways.json").put("lfm3", {"provider": "scuti", "url": "http://127.0.0.1:29202", "token": "secret-tok"})
    return seed_token(Settings(data_dir=tmp_path, admin_password="pw"))


@pytest.fixture
def client(settings):
    return TestClient(build_app(settings, transport=httpx.MockTransport(upstream)))


def post(client, headers=TOKEN, **extra):
    return client.post("/api/chat", headers=headers, json={"gateway": "lfm3", "messages": [{"role": "user", "content": "Hi"}], **extra})


def test_health_needs_no_token(client):
    assert client.get("/health").json() == {"ok": True, "ready": True}


def test_api_needs_a_token(client):
    assert post(client, headers={}).status_code == 401
    assert client.get("/api/gateways").status_code == 401


def test_chat_json(client):
    reply = post(client)
    assert reply.status_code == 200 and reply.json()["content"] == [{"type": "text", "text": "Hello"}]


def test_chat_stream_is_ndjson(client):
    reply = post(client, stream=True)
    lines = [json.loads(line) for line in reply.text.splitlines()]
    assert reply.headers["content-type"].startswith("application/x-ndjson")
    assert [x["type"] for x in lines] == ["text", "text", "done"] and lines[-1]["streamed"] is True


def test_errors_use_the_error_body(client):
    reply = post(client, gateway="nope")
    assert reply.status_code == 422 and reply.json()["error"]["code"] == "unknown_gateway"
    assert client.post("/api/chat", headers=TOKEN, content=b"not json").json()["error"]["code"] == "invalid_request"
    assert post(client, tools=[{"name": "t"}]).json()["error"]["code"] == "tools_unsupported"


def test_upstream_rate_limit_keeps_retry_after(settings):
    app = build_app(settings, transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"detail": "slow"}, headers={"retry-after": "4"})))
    reply = post(TestClient(app))
    assert reply.status_code == 429 and reply.headers["retry-after"] == "4" and reply.json()["error"]["kind"] == "rate_limit"


def test_too_large_body(client):
    reply = client.post("/api/chat", headers={**TOKEN, "content-length": str(65 * 1024 * 1024)}, content=b"{}")
    assert reply.status_code == 413


def test_stream_error_after_start_is_a_line(settings):
    def broken(request):
        return httpx.Response(200, content=json.dumps({"type": "content", "text": "x"}).encode())

    reply = post(TestClient(build_app(settings, transport=httpx.MockTransport(broken))), stream=True)
    lines = [json.loads(line) for line in reply.text.splitlines()]
    assert lines[0]["type"] == "text" and lines[-1]["type"] == "error" and lines[-1]["error"]["kind"] == "unavailable"


def test_gateways_list_has_no_secrets(client):
    reply = client.get("/api/gateways", headers=TOKEN)
    assert reply.status_code == 200 and "secret-tok" not in reply.text
    row = reply.json()["gateways"][0]
    assert row["id"] == "lfm3" and row["has_token"] is True and row["reachable"] is True and row["images"] is False


def test_validate(client):
    ok = client.post("/api/validate", headers=TOKEN, json={"gateway": "lfm3", "messages": [{"role": "user", "content": "Hi"}]})
    assert ok.json() == {"ok": True}
    bad = client.post("/api/validate", headers=TOKEN, json={"gateway": "lfm3", "messages": []})
    assert bad.status_code == 422
    cap = client.post("/api/validate", headers=TOKEN, json={"gateway": "lfm3", "messages": [{"role": "user", "content": "Hi"}], "tools": [{"name": "t"}]})
    assert cap.json()["error"]["code"] == "tools_unsupported"
