from __future__ import annotations

import json
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


def test_startup_model_selection_prefers_installed_default_and_never_downloads():
    class Provider:
        def __init__(self, models, metadata): self.models, self.metadata, self.calls = models, metadata, []
        def local_model_inventory(self):
            return type("Inventory", (), {"state": "available", "models": self.models})()
        def _bounded_request(self, method, path, body=None, *, timeout=5.0):
            self.calls.append((method, path, body))
            if path == "/api/tags": return json.dumps({"models": self.metadata}).encode()
            return json.dumps({"capabilities": ["completion"] if body["model"] in {"small-chat", "llama3.2:3b"} else ["embedding"]}).encode()

    preferred = Provider(("large", "llama3.2:3b"), [])
    assert OllamaFirstRunService(provider=preferred).default_installed_chat_model() == ("llama3.2:3b",)
    assert preferred.calls == []
    fallback = Provider(("large", "small-chat"), [
        {"name": "large", "size": 900}, {"name": "small-chat", "size": 100},
    ])
    assert OllamaFirstRunService(provider=fallback).default_installed_chat_model() == ("small-chat",)
    assert [call[1] for call in fallback.calls] == ["/api/tags", "/api/show"]
    absent = Provider((), [])
    assert OllamaFirstRunService(provider=absent).default_installed_chat_model() == ()


def test_startup_model_selection_checks_smallest_candidates_until_chat_capable():
    class Provider:
        def local_model_inventory(self):
            return type("Inventory", (), {"state": "available", "models": ("embed", "chat")})()
        def _bounded_request(self, method, path, body=None, *, timeout=5.0):
            if path == "/api/tags": return b'{"models":[{"name":"embed","size":10},{"name":"chat","size":20}]}'
            return b'{"capabilities":["embedding"]}' if body["model"] == "embed" else b'{"capabilities":["completion"]}'
    assert OllamaFirstRunService(provider=Provider()).default_installed_chat_model() == ("chat",)


def test_desktop_startup_auto_setup_is_idempotent_and_persists_selected_model(database):
    class Provider:
        def local_model_inventory(self):
            return type("Inventory", (), {"state": "available", "models": ("small-chat",)})()
    class Setup(OllamaFirstRunService):
        def __init__(self): super().__init__(provider=Provider())
        def default_installed_chat_model(self, preferred="llama3.2:3b"): return ("small-chat",)
    class Corporation:
        def __init__(self): self.models = []; self.limits = []
        def replace_model(self, agent, provider, model): self.models.append((agent, provider, model))
        def resource_manager(self, limits): self.limits.append(limits)

    app = create_local_app(password=PASSWORD, origin=ORIGIN, desktop_mode=True, first_owner_run=True)
    app.state.first_run_ollama_service = Setup()
    corporation = Corporation()
    app.state.restore_local_first_run(corporation)
    app.state.restore_local_first_run(corporation)
    stored = app.state.first_run_setup_store.get()
    assert stored.completed is True
    assert stored.model_id == "small-chat"
    assert corporation.models == [("local_worker", "ollama", "small-chat")] * 2
    assert len(corporation.limits) == 2


def test_ollama_pull_progress_rechecks_installed_inventory_and_uses_only_the_fake_transport(monkeypatch):
    import json

    digest = "sha256:" + "b" * 64
    manifest = json.dumps({"schemaVersion": 2, "layers": [{"size": 3072}]}).encode()
    requests = []

    def dispatch(request):
        requests.append((request.method, request.url.host, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, headers={"docker-content-digest": digest}, content=manifest)
        return httpx.Response(200, content=(
            b'{"status":"pulling manifest"}\n'
            b'{"status":"downloading","completed":1536,"total":3072}\n'
            b'{"status":"success","completed":3072,"total":3072}\n'
        ))

    class Provider:
        def local_model_inventory(self):
            return type("Inventory", (), {
                "state": "available", "models": ("llama3.2:3b",),
                "source": "fake", "reason": None,
            })()

    def client_factory(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(dispatch), **kwargs)

    service = OllamaFirstRunService(provider=Provider(), client_factory=client_factory)
    monkeypatch.setattr(service, "_available_default_space", lambda: 8192)
    preview = service.preview_model()
    events = [json.loads(line) for line in service.pull(
        expected_digest=preview["manifest_digest"], expected_bytes=preview["manifest_bytes"],
    )]

    assert [event["event"] for event in events] == ["progress", "progress", "progress", "complete"]
    assert events[1]["completed"] == 1536 and events[1]["total"] == 3072
    assert events[-1]["message"] == "Ollama confirmed the recommended model is installed."
    assert requests == [
        ("GET", "registry.ollama.ai", "/v2/library/llama3.2/manifests/3b"),
        ("GET", "registry.ollama.ai", "/v2/library/llama3.2/manifests/3b"),
        ("POST", "127.0.0.1", "/api/pull"),
    ]


def test_ollama_pull_cancel_closes_response_without_claiming_completion(monkeypatch):
    digest = "sha256:" + "c" * 64
    manifest = b'{"schemaVersion":2,"layers":[{"size":3072}]}'
    closed = {"pull": False}

    class PullStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"status":"downloading","completed":10,"total":100}\n'
            yield b'{"status":"downloading","completed":20,"total":100}\n'

        def close(self):
            closed["pull"] = True

    def dispatch(request):
        if request.method == "GET":
            return httpx.Response(200, headers={"docker-content-digest": digest}, content=manifest)
        return httpx.Response(200, stream=PullStream())

    class Provider:
        def local_model_inventory(self):
            return type("Inventory", (), {
                "state": "available", "models": (), "source": "fake", "reason": None,
            })()

    service = OllamaFirstRunService(
        provider=Provider(), client_factory=lambda **kwargs: httpx.Client(
            transport=httpx.MockTransport(dispatch), **kwargs,
        ),
    )
    monkeypatch.setattr(service, "_available_default_space", lambda: 8192)
    preview = service.preview_model()
    stream = service.pull(expected_digest=preview["manifest_digest"], expected_bytes=preview["manifest_bytes"])
    assert '"event":"progress"' in next(stream)
    stream.close()
    assert closed["pull"] is True


def test_gemini_first_run_rejects_invalid_key_and_sanitizes_catalog_failure(monkeypatch, database):
    runtime = create_corporation_runtime()
    application = create_local_app(
        password=PASSWORD, origin=ORIGIN,
        application_service=runtime.application_service,
        desktop_mode=True, first_owner_run=True,
    )

    def fail_catalog(_self, _api_key):
        raise RuntimeError(f"provider rejected secret {KEY}")

    monkeypatch.setattr("app.application.services.local_online_provider.LocalOnlineProviderService.discover", fail_catalog)
    before = runtime.application_service.get_model_assignment("local_worker")
    with TestClient(application, base_url=ORIGIN, client=("127.0.0.1", 50105)) as client:
        headers = login(client)
        invalid = client.post("/api/local/first-run/gemini/complete", headers=headers,
                              json={"api_key": "not-a-google-key", "remember_key": False})
        assert invalid.status_code == 422
        rejected = client.post("/api/local/first-run/gemini/complete", headers=headers,
                               json={"api_key": KEY, "remember_key": False})
        assert rejected.status_code == 503
        assert KEY not in rejected.text
        assert "provider rejected secret" not in rejected.text
    assert runtime.application_service.get_model_assignment("local_worker") == before


def test_ollama_first_run_retry_recovers_and_pull_requires_confirmation(database):
    import json

    runtime = create_corporation_runtime()
    application = create_local_app(
        password=PASSWORD, origin=ORIGIN,
        application_service=runtime.application_service,
        desktop_mode=True, first_owner_run=True,
    )

    class Ollama:
        MODEL_ID = "llama3.2:3b"

        def __init__(self):
            self.status_calls = 0
            self.pull_calls = 0

        def status(self):
            self.status_calls += 1
            if self.status_calls == 1:
                return {"state": "unavailable", "service_running": False,
                        "model_installed": None, "source": None, "reason": "Ollama is not running."}
            return {"state": "available", "service_running": True,
                    "model_installed": False, "source": "fake", "reason": None}

        def pull(self, *, expected_digest, expected_bytes):
            self.pull_calls += 1
            assert expected_digest == "sha256:" + "e" * 64
            assert expected_bytes == 3072
            yield json.dumps({"event": "progress", "completed": 100, "total": 3072}) + "\n"
            yield json.dumps({"event": "complete", "message": "Fake model installed."}) + "\n"

    ollama = Ollama()
    application.state.first_run_ollama_service = ollama
    with TestClient(application, base_url=ORIGIN, client=("127.0.0.1", 50106)) as client:
        headers = login(client)
        failed = client.post("/api/local/first-run/ollama/status", headers=headers, json={})
        recovered = client.post("/api/local/first-run/ollama/status", headers=headers, json={})
        assert failed.status_code == recovered.status_code == 200
        assert failed.json()["state"] == "unavailable"
        assert recovered.json()["state"] == "available"
        payload = {
            "confirmed": False,
            "manifest_digest": "sha256:" + "e" * 64,
            "manifest_bytes": 3072,
        }
        denied = client.post("/api/local/first-run/ollama/pull", headers=headers, json=payload)
        assert denied.status_code == 409
        assert ollama.pull_calls == 0
        payload["confirmed"] = True
        accepted = client.post("/api/local/first-run/ollama/pull", headers=headers, json=payload)
        assert accepted.status_code == 200, accepted.text
        assert '"completed":100' in accepted.text
        assert '"setup_complete":true' in accepted.text
        assert ollama.pull_calls == 1
        assert client.get("/api/local/first-run", headers=headers).json()["completed"] is True
    assignment = runtime.application_service.get_model_assignment("local_worker")
    assert (assignment.provider_id, assignment.model_id) == ("ollama", "llama3.2:3b")


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
