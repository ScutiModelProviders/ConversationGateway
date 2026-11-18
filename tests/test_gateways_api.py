import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings

PW = {"X-Admin-Password": "pw"}


@pytest.fixture
def client(tmp_path):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"ready": True, "models": []}))
    return TestClient(build_app(Settings(data_dir=tmp_path, admin_password="pw"), transport=transport))


def test_needs_the_admin_password(client):
    assert client.get("/admin/gateways").status_code == 401
    assert client.put("/admin/gateways/x", json={}).status_code == 401


def test_create_list_test_delete(client):
    created = client.put("/admin/gateways/jev", headers=PW, json={"provider": "anthropic", "api_key": "sk-secret", "model": "jev-latest"})
    assert created.status_code == 200 and created.json()["has_api_key"] is True and "sk-secret" not in created.text
    listing = client.get("/admin/gateways", headers=PW)
    assert [g["id"] for g in listing.json()["gateways"]] == ["jev"] and "sk-secret" not in listing.text
    assert "anthropic" in listing.json()["form"]["providers"] and "choices" in listing.json()["form"] and "gemini" in listing.json()["presets"]
    assert client.put("/admin/gateways/local", headers=PW, json={"provider": "scuti", "url": "http://127.0.0.1:29202"}).status_code == 200
    probe = client.post("/admin/gateways/local/test", headers=PW).json()
    assert probe["ok"] is True and "ready" in probe["message"]
    assert client.delete("/admin/gateways/jev", headers=PW).status_code == 200
    assert client.delete("/admin/gateways/jev", headers=PW).status_code == 404


def test_bad_input_is_422_with_a_safe_message(client):
    response = client.put("/admin/gateways/jev", headers=PW, json={"provider": "anthropic", "model": "m"})
    assert response.status_code == 422 and "API key" in response.json()["detail"]
    assert client.post("/admin/gateways/missing/test", headers=PW).status_code == 404


def test_page_is_served(client):
    assert "Gateways" in client.get("/admin/gateways.html").text


def test_saved_gateway_changes_next_public_listing(client):
    from tests.seed import seed_token
    # A separate loopback app has auth disabled; upstream remains MockTransport.
    assert client.put("/admin/gateways/local", headers=PW, json={"provider": "scuti", "url": "http://127.0.0.1:29202"}).status_code == 200
    first = client.get("/admin/gateways", headers=PW).json()["gateways"][0]
    assert first["tools"] is False
    assert client.put("/admin/gateways/local", headers=PW, json={"provider": "scuti", "capabilities": {"tools": True}}).status_code == 200
    assert client.get("/admin/gateways", headers=PW).json()["gateways"][0]["tools"] is True


def test_failed_probe_reports_safe_detail(tmp_path):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"ready": False}))
    c = TestClient(build_app(Settings(data_dir=tmp_path, admin_password="pw"), transport=transport))
    c.put("/admin/gateways/local", headers=PW, json={"provider": "scuti", "url": "http://127.0.0.1:29202"})
    result = c.post("/admin/gateways/local/test", headers=PW).json()
    assert result["ok"] is False and "not ready" in result["detail"]

def test_models_route_refuses_a_service_with_no_list_and_needs_the_password(client):
    client.put("/admin/gateways/local", headers=PW, json={"provider": "scuti", "url": "http://127.0.0.1:29202"})
    assert client.get("/admin/gateways/local/models").status_code == 401
    reply = client.get("/admin/gateways/local/models", headers=PW).json()
    assert reply["ok"] is False and "no model list" in reply["detail"]
    assert client.get("/admin/gateways/nope/models", headers=PW).status_code == 404
