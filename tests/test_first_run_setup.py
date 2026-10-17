from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.application.services.first_run_setup import FirstRunSetupStore, OllamaFirstRunService
from app.database import initialize_database
from app.integrations.gemini_catalog import (
    GeminiCatalogAuditEvent, GeminiCatalogAuditStatus, GeminiModel,
    GeminiModelCapability, GeminiModelCatalogResult,
)
from app.integrations.gemini_chat import GeminiConnectionManager
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "first-run-owner-password"
ORIGIN = "http://127.0.0.1:8765"
KEY = "AIza" + "A" * 35
MODEL = "gemini-3.8-flash"


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr("app.database.connection.DATABASE_PATH", tmp_path / "app.sqlite3")
    initialize_database()


def login(client):
    response = client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    session = client.get("/api/local/session").json()
    return {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}


def test_first_run_store_persists_only_non_secret_setup_and_limits(database):
    store = FirstRunSetupStore()
    store.initialize_for_new_owner(first_owner_run=True)
    store.complete_gemini(MODEL, (MODEL,), key_persisted=False)
    stored = store.get()
    assert stored.completed and stored.provider_id == "gemini"
    assert (stored.global_slots, stored.provider_slots, stored.model_slots) == (1, 1, 1)
    connection = __import__("app.database.connection", fromlist=["get_connection"]).get_connection()
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(local_first_run)")}
        assert not {"api_key", "credential", "secret"} & columns
    finally:
        connection.close()


def test_ollama_manifest_preview_is_bounded_and_reports_exact_registry_metadata(monkeypatch):
    layers = [{"size": 1024}, {"size": 2048}]
    digest = "sha256:" + "a" * 64

    def client_factory(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"docker-content-digest": digest}, json={"schemaVersion": 2, "layers": layers},
        )), **kwargs)

    service = OllamaFirstRunService(client_factory=client_factory)
    monkeypatch.setattr(service, "_available_default_space", lambda: 1_000_000)
    preview = service.preview_model()
    assert preview["model_id"] == "llama3.2:3b"
    assert preview["manifest_digest"] == digest
    assert preview["manifest_bytes"] == 3072
    assert "OLLAMA_MODELS" in preview["destination"] or "custom" in preview["destination"]


def test_ollama_manifest_preview_hashes_received_manifest_when_registry_omits_digest(monkeypatch):
    import hashlib
    import json
    body = json.dumps({"schemaVersion": 2, "layers": [{"size": 4096}]}, separators=(",", ":")).encode()

    def client_factory(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(
            200, content=body,
        )), **kwargs)

    service = OllamaFirstRunService(client_factory=client_factory)
    monkeypatch.setattr(service, "_available_default_space", lambda: 1_000_000)
    preview = service.preview_model()
    assert preview["manifest_digest"] == "sha256:" + hashlib.sha256(body).hexdigest()
    assert preview["manifest_bytes"] == 4096


def test_ollama_success_progress_is_not_installation_confirmation():
    progress = OllamaFirstRunService._progress(b'{"status":"success","completed":3,"total":3}')
    assert progress["event"] == "progress"
    assert progress["status"] == "success"


def test_first_run_routes_exist_only_for_explicit_desktop_mode(database):
    runtime = create_corporation_runtime()
    desktop = create_local_app(password=PASSWORD, origin=ORIGIN,
                               application_service=runtime.application_service,
                               desktop_mode=True, first_owner_run=True)
    ordinary = create_local_app(password=PASSWORD, origin=ORIGIN)
    with TestClient(desktop, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        headers = login(client)
        state = client.get("/api/local/first-run", headers=headers)
        assert state.status_code == 200
        assert state.json()["enabled"] is True
        client.cookies.clear()
        denied = client.get("/api/local/first-run")
        assert denied.status_code == 401
        headers = login(client)
        skipped = client.post("/api/local/first-run/skip", headers=headers, json={})
        assert skipped.status_code == 200
        assert skipped.json() == {"skipped": True, "configured": False}
    with TestClient(ordinary, base_url=ORIGIN, client=("127.0.0.1", 50101)) as client:
        headers = login(client)
        assert client.get("/api/local/first-run", headers=headers).status_code == 404


def test_gemini_first_run_catalog_opt_in_sets_assignment_and_opens_coordinator(monkeypatch, database):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    result = GeminiModelCatalogResult(
        (GeminiModel(MODEL, (GeminiModelCapability.GENERATE_CONTENT,)),), False, now,
        GeminiCatalogAuditEvent("gemini", "list_models", GeminiCatalogAuditStatus.SUCCEEDED,
                                now, 1, 1, False, None),
    )
    monkeypatch.setattr("app.integrations.gemini_catalog.GeminiModelCatalogAdapter.list_models",
                        lambda _self: result)
    runtime = create_corporation_runtime()
    manager = GeminiConnectionManager()
    application = create_local_app(password=PASSWORD, origin=ORIGIN,
                                   application_service=runtime.application_service,
                                   desktop_mode=True, first_owner_run=True,
                                   voice_connection_manager=manager)

    class SecretStore:
        saved = None
        def save(self, secret): self.saved = secret
        def clear(self): self.saved = None

    secret_store = SecretStore()
    application.state.first_run_secret_store = secret_store
    with TestClient(application, base_url=ORIGIN, client=("127.0.0.1", 50102)) as client:
        headers = login(client)
        before = runtime.application_service.get_model_assignment("local_worker")
        response = client.post("/api/local/first-run/gemini/complete", headers=headers,
                               json={"api_key": KEY, "remember_key": True})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["setup_complete"] is True
        assert body["provider_id"] == "gemini" and body["model_id"] == MODEL
        assert KEY not in response.text
        assert secret_store.saved == KEY
        assignment = runtime.application_service.get_model_assignment("local_worker")
        assert (assignment.provider_id, assignment.model_id) == ("gemini", MODEL)
        capacity = runtime.application_service.resource_manager().snapshot().global_capacity
        assert (capacity.limit, capacity.allocated) == (1, 0)
        assert before.provider_id == "ollama"
        assert client.get("/api/local/first-run", headers=headers).json()["completed"] is True


def test_opted_in_gemini_configuration_restores_on_restart_without_catalog_network(monkeypatch, database):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    result = GeminiModelCatalogResult(
        (GeminiModel(MODEL, (GeminiModelCapability.GENERATE_CONTENT,)),), False, now,
        GeminiCatalogAuditEvent("gemini", "list_models", GeminiCatalogAuditStatus.SUCCEEDED,
                                now, 1, 1, False, None),
    )
    monkeypatch.setattr("app.integrations.gemini_catalog.GeminiModelCatalogAdapter.list_models",
                        lambda _self: result)
    saved = {"secret": None}

    class SecretStore:
        def __init__(self): pass
        def save(self, secret): saved["secret"] = secret
        def load(self): return saved["secret"]
        def clear(self): saved["secret"] = None

    monkeypatch.setattr("app.local_owner_secret.LocalOwnerSecretStore", SecretStore)
    first_runtime = create_corporation_runtime()
    first = create_local_app(password=PASSWORD, origin=ORIGIN,
                             application_service=first_runtime.application_service,
                             desktop_mode=True, first_owner_run=True,
                             voice_connection_manager=GeminiConnectionManager())
    with TestClient(first, base_url=ORIGIN, client=("127.0.0.1", 50103)) as client:
        headers = login(client)
        response = client.post("/api/local/first-run/gemini/complete", headers=headers,
                               json={"api_key": KEY, "remember_key": True})
        assert response.status_code == 200
    assert saved["secret"] == KEY

    def unexpected_catalog(_self):
        raise AssertionError("startup must not make a Gemini network request")
    monkeypatch.setattr("app.integrations.gemini_catalog.GeminiModelCatalogAdapter.list_models",
                        unexpected_catalog)
    restarted_runtime = create_corporation_runtime()
    restarted = create_local_app(password=PASSWORD, origin=ORIGIN,
                                 application_service=restarted_runtime.application_service,
                                 desktop_mode=True, first_owner_run=False,
                                 voice_connection_manager=GeminiConnectionManager())
    with TestClient(restarted, base_url=ORIGIN, client=("127.0.0.1", 50104)) as client:
        headers = login(client)
        state = client.get("/api/local/first-run", headers=headers).json()
        assignment = restarted_runtime.application_service.get_model_assignment("local_worker")
        capacity = restarted_runtime.application_service.resource_manager().snapshot().global_capacity
        assert state["completed"] is True and state["credential_needs_reentry"] is False
        assert (assignment.provider_id, assignment.model_id) == ("gemini", MODEL)
        assert (capacity.limit, capacity.allocated) == (1, 0)
