from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.api.security import AuthenticatedPrincipal
from app.integrations.gemini_catalog import (
    GeminiCatalogAuditEvent,
    GeminiCatalogAuditStatus,
    GeminiModel,
    GeminiModelCapability,
    GeminiModelCatalogResult,
)
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
KEY = "AIza" + "A" * 35
MODEL = "gemini-test-flash"


def model_catalog():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return GeminiModelCatalogResult(
        (GeminiModel(MODEL, (GeminiModelCapability.GENERATE_CONTENT,)),), False,
        now, GeminiCatalogAuditEvent("gemini", "list_models", GeminiCatalogAuditStatus.SUCCEEDED,
                                     now, 1, 1, False, None))


def login(client):
    assert client.post("/api/local/login", json={"password": PASSWORD},
                       headers={"Origin": ORIGIN}).status_code == 200
    session = client.get("/api/local/session").json()
    return {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}


def patch_catalog(monkeypatch):
    monkeypatch.setattr("app.integrations.gemini_catalog.GeminiModelCatalogAdapter.list_models",
                        lambda _self: model_catalog())


def test_local_gemini_setup_consent_disconnect_and_assignment_restoration(monkeypatch):
    patch_catalog(monkeypatch)
    runtime = create_corporation_runtime()
    service = runtime.application_service
    original = service.get_model_assignment("local_worker")
    tasks_before = service.list_tasks()
    real_client = httpx.Client
    network_calls = []
    def handler(request):
        network_calls.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "cloud reply"}]}}]})
    def client_factory(**kwargs):
        assert kwargs == {"timeout": 20.0, "follow_redirects": False, "trust_env": False}
        return real_client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr("app.integrations.gemini_chat.httpx.Client", client_factory)
    app = create_local_app(password=PASSWORD, application_service=service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000)) as client:
        headers = login(client)
        discovery = client.post("/api/local/online-provider/catalog", headers=headers, json={"api_key": KEY})
        assert discovery.status_code == 200
        assert discovery.json()["models"] == [MODEL]
        assert KEY not in discovery.text
        assert client.put("/api/local/online-provider/connection", headers=headers,
                          json={"agent_id": "local_worker", "model_id": MODEL}).status_code == 200
        assignment = service.get_model_assignment("local_worker")
        assert (assignment.provider_id, assignment.model_id) == ("gemini", MODEL)

        started = client.post("/api/chat/conversations", headers=headers,
                              json={"agent_id": "local_worker"})
        assert started.status_code == 200
        conversation_id = started.json()["conversation"]["id"]
        denied = client.post(f"/api/chat/conversations/{conversation_id}/messages",
                             headers=headers, json={"text": "hello"})
        assert denied.status_code == 403
        assert network_calls == []
        sent = client.post(f"/api/chat/conversations/{conversation_id}/messages",
                           headers=headers, json={"text": "hello", "cloud_consent": True})
        assert sent.status_code == 200
        assert sent.json()["conversation"]["messages"][-1]["content"] == "cloud reply"
        assert len(network_calls) == 1
        assert network_calls[0].headers["x-goog-api-key"] == KEY
        assert KEY not in str(network_calls[0].url)
        assert "maxOutputTokens" in network_calls[0].content.decode()

        disconnected = client.request("DELETE", "/api/local/online-provider/connection/local_worker",
                                      headers=headers, json={})
        assert disconnected.status_code == 200
        assert service.get_model_assignment("local_worker") == original
        stale = client.post(f"/api/chat/conversations/{conversation_id}/messages",
                            headers=headers, json={"text": "again", "cloud_consent": True})
        assert stale.status_code == 409
        assert len(network_calls) == 1
        assert service.list_tasks() == tasks_before
        assert client.get("/api/local/online-provider").json()["connected"] is False


def test_staged_key_can_be_explicitly_erased_and_default_api_exposes_no_setup(monkeypatch):
    patch_catalog(monkeypatch)
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50001)) as client:
        headers = login(client)
        assert client.post("/api/local/online-provider/catalog", headers=headers,
                           json={"api_key": KEY}).status_code == 200
        erased = client.request("DELETE", "/api/local/online-provider/credential",
                                headers=headers, json={})
        assert erased.status_code == 200 and erased.json()["credential_erased"] is True
        assert client.get("/api/local/online-provider").json()["connected"] is False
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"model:read"}))
        assert client.post("/api/local/online-provider/catalog", headers=headers,
                           json={"api_key": KEY}).status_code == 403
    from app.api.app import create_app
    with TestClient(create_app(application_service=runtime.application_service)) as default:
        assert default.get("/api/local/online-provider").status_code == 404
        assert default.post("/api/chat/conversations/anything/messages",
                            json={"text": "hello", "cloud_consent": True}).status_code == 401


def test_unsupported_gemini_key_is_rejected_before_catalog_call(monkeypatch):
    catalog_calls = []
    monkeypatch.setattr(
        "app.integrations.gemini_catalog.GeminiModelCatalogAdapter.list_models",
        lambda _self: catalog_calls.append(True),
    )
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50003)) as client:
        headers = login(client)
        response = client.post("/api/local/online-provider/catalog",
                               headers=headers, json={"api_key": "unsupported-secret-format"})
    assert response.status_code == 422
    assert "unsupported-secret-format" not in response.text
    assert catalog_calls == []


def test_api_key_never_appears_in_provider_repr_errors_or_chat_history(monkeypatch):
    patch_catalog(monkeypatch)
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50002)) as client:
        headers = login(client)
        client.post("/api/local/online-provider/catalog", headers=headers, json={"api_key": KEY})
        client.put("/api/local/online-provider/connection", headers=headers,
                   json={"agent_id": "local_worker", "model_id": MODEL})
        provider = runtime.providers.get("gemini")
        assert KEY not in repr(provider)
        manager = client.app.state.gemini_connection_manager
        assert KEY not in repr(manager.connection())
        started = runtime.application_service.owned_chat().start("local-owner", "local_worker")
        snapshot = runtime.application_service.owned_chat().get("local-owner", started["conversation"].id)
        assert KEY not in repr(snapshot)
