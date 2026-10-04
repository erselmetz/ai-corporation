from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.application.services.owned_chat import ChatConflict
from app.local import create_local_app
from app.providers import AIProvider, OllamaProvider
from app.providers.inventory import LocalModelInventory
from app.runtime.factory import create_corporation_runtime
from app.resources import ResourceLimits, ProviderLimit, ModelLimit


class FakeLocal(AIProvider):
    def __init__(self):
        self.models = ("llama3.2:3b", "second:local")
        self.checks = 0
        self.entered, self.release = Event(), Event()
        self.block = False
        self.fail = False
        self.calls = []

    def local_model_inventory(self):
        self.checks += 1
        return LocalModelInventory("available", self.models, True, source="fake-local", reason=None)

    def generate(self, model, prompt):
        self.calls.append(model)
        self.entered.set()
        if self.block and not self.release.wait(5):
            raise RuntimeError("Test did not release provider")
        if self.fail:
            raise RuntimeError("private-provider-error")
        return "deterministic reply"


def setup():
    runtime = create_corporation_runtime()
    provider = FakeLocal()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    return runtime, provider


def local_client(runtime):
    app = create_local_app(password="test-owner-passphrase", application_service=runtime.application_service)
    client = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    return client


def sign_in(client):
    origin = "http://127.0.0.1:8000"
    assert client.post("/api/local/login", json={"password": "test-owner-passphrase"}, headers={"Origin": origin}).status_code == 200
    return {"Origin": origin, "X-Local-CSRF": client.get("/api/local/session").json()["csrf"]}


def test_inventory_and_selection_preserve_history_and_other_authority():
    runtime, provider = setup()
    service = runtime.application_service
    tasks = service.list_tasks()
    resource = service.resource_manager(ResourceLimits(1, (ProviderLimit("ollama", 1),),
        (ModelLimit("ollama", "llama3.2:3b", 1),)))
    capacity = resource.snapshot()
    with local_client(runtime) as client:
        assert client.get("/api/local/models/local_worker").status_code == 401
        headers = sign_in(client)
        old = service.owned_chat().start("local-owner", "local_worker")["conversation"].id
        observed = client.get("/api/local/models/local_worker").json()
        assert observed["configured_installed"] is True
        assert observed["execution_readiness"] == "unknown"
        assert observed["inventory"]["source"] == "fake-local"
        assert datetime.fromisoformat(observed["inventory"]["checked_at"]).utcoffset() == timedelta(0)
        assert provider.calls == []
        result = client.put("/api/local/models/local_worker", headers=headers,
                            json={"provider_id": "ollama", "model_id": "second:local"})
        assert result.status_code == 200
        assert provider.checks == 2  # Fresh observation at selection, not cached browser evidence.
        assert result.json()["model_id"] == "second:local"
        with pytest.raises(ChatConflict, match="start a new conversation"):
            service.owned_chat().send("local-owner", old, "hello")
        assert service.owned_chat().get("local-owner", old)["coordinator"].model == "llama3.2:3b"
        new = service.owned_chat().start("local-owner", "local_worker")["conversation"].id
        service.owned_chat().send("local-owner", new, "hello")
        assert provider.calls == ["second:local"]
        assert client.put("/api/models/local_worker", headers=headers,
                          json={"provider_id": "ollama", "model_id": "other"}).status_code == 403
        assert client.post("/api/tasks", headers=headers, json={"title": "x", "description": "y"}).status_code == 403
    assert service.list_tasks() == tasks
    assert resource.snapshot() == capacity


def test_stale_missing_unsupported_and_permission_denial_do_not_mutate():
    runtime, provider = setup()
    original = runtime.application_service.get_model_assignment("local_worker")
    with local_client(runtime) as client:
        headers = sign_in(client)
        provider.models = ()
        assert client.get("/api/local/models/local_worker").json()["configured_installed"] is False
        body = {"provider_id": "ollama", "model_id": "second:local"}
        assert client.put("/api/local/models/local_worker", headers=headers, json=body).status_code == 409
        assert client.put("/api/local/models/local_worker", json=body, headers={"Origin": headers["Origin"]}).status_code == 403
        assert client.put("/api/local/models/local_worker", headers=headers, json={**body, "extra": "secret"}).status_code == 422
        assert client.get("/api/local/models/missing").status_code == 404
        runtime.providers.remove("ollama")
        runtime.providers.register("ollama", Unsupported())
        observed = client.get("/api/local/models/local_worker").json()
        assert observed["inventory"]["state"] == "unknown"
        assert observed["configured_installed"] is None
        assert client.put("/api/local/models/local_worker", headers=headers, json=body).status_code == 503
        backend = client.app.state.authentication_backend
        backend.principal = AuthenticatedPrincipal("local-owner", frozenset({"model:read"}))
        assert client.put("/api/local/models/local_worker", headers=headers, json=body).status_code == 403
        runtime.providers.remove("ollama")
        assert client.get("/api/local/models/local_worker").status_code == 404
    assert runtime.application_service.get_model_assignment("local_worker") == original
    with TestClient(create_app(application_service=runtime.application_service)) as client:
        assert client.put("/api/local/models/local_worker", json=body).status_code == 404
        assert client.get("/api/models").status_code == 401


class Unsupported(AIProvider):
    def generate(self, model, prompt):
        raise AssertionError("Inventory must not generate")


@pytest.mark.parametrize("fail", [False, True])
def test_active_send_blocks_selection_and_cleanup_allows_later_selection(fail):
    runtime, provider = setup()
    service = runtime.application_service
    chat = service.owned_chat()
    identifier = chat.start("owner", "local_worker")["conversation"].id
    provider.block, provider.fail = True, fail
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(chat.send, "owner", identifier, "hello")
        try:
            assert provider.entered.wait(2)
            with pytest.raises(ChatConflict, match="busy"):
                service.select_local_model("local_worker", "ollama", "second:local")
            assert provider.checks == 0
            assert service.get_agent("local_worker").model == "llama3.2:3b"
        finally:
            provider.release.set()
        if fail:
            with pytest.raises(RuntimeError):
                pending.result()
        else:
            pending.result()
    assert service.select_local_model("local_worker", "ollama", "second:local").model_id == "second:local"


def test_selection_guard_rejects_new_sends_starts_and_duplicate_selection():
    runtime, _ = setup()
    service = runtime.application_service
    chat = service.owned_chat()
    identifier = chat.start("owner", "local_worker")["conversation"].id
    with chat.configuration_change("local_worker"):
        with pytest.raises(ChatConflict):
            chat.send("owner", identifier, "hello")
        with pytest.raises(ChatConflict):
            chat.start("owner", "local_worker")
        with pytest.raises(ChatConflict):
            service.select_local_model("local_worker", "ollama", "second:local")
    assert chat.send("owner", identifier, "hello")["conversation"].messages


def transport_inventory(monkeypatch, handler, url="http://127.0.0.1:11434"):
    real_client = httpx.Client
    def factory(**kwargs):
        assert kwargs == {"timeout": 2.0, "trust_env": False, "follow_redirects": False}
        return real_client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr("app.providers.ollama.httpx.Client", factory)
    return OllamaProvider(url).local_model_inventory()


def test_ollama_inventory_is_bounded_and_deterministic(monkeypatch):
    requests = []
    def response(request):
        requests.append(request)
        return httpx.Response(200, json={"models": [{"name": "installed:one"}]})
    result = transport_inventory(monkeypatch, response)
    assert result.models == ("installed:one",)
    assert result.state == "available" and result.supported
    assert result.checked_at.utcoffset().total_seconds() == 0
    assert len(requests) == 1 and requests[0].url.path == "/api/tags"


@pytest.mark.parametrize("body", [b"not-json", b"[]", b'{"models":null}',
    b'{"models":[{}]}', b'{"models":[{"name":"a"},{"name":"a"}]}',
    b'{"models":[{"name":""}]}', b"x" * 262145],
    ids=["invalid-json", "wrong-root", "null-models", "missing-name", "duplicate", "blank", "oversized"])
def test_malformed_or_oversized_inventory_is_unknown_without_raw_body(monkeypatch, body):
    result = transport_inventory(monkeypatch, lambda _: httpx.Response(200, content=body))
    assert result.state == "unknown" and not result.models
    assert len(result.reason) < 100


@pytest.mark.parametrize("failure", ["timeout", "connection", "redirect", "server"])
def test_provider_failure_and_redirect_are_sanitized(monkeypatch, failure):
    def response(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-token", request=request)
        if failure == "connection":
            raise httpx.ConnectError("secret-token", request=request)
        return httpx.Response(302 if failure == "redirect" else 500,
                              headers={"Location": "https://external.test/secret-token"})
    result = transport_inventory(monkeypatch, response)
    assert result.state == "unavailable"
    assert "secret-token" not in str(result)


@pytest.mark.parametrize("url", ["https://external.test", "http://127.0.0.1:11434/private", "http://user:secret@localhost:11434"])
def test_non_loopback_or_sensitive_config_is_not_contacted(monkeypatch, url):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network must not be used")
    monkeypatch.setattr("app.providers.ollama.httpx.Client", forbidden)
    result = OllamaProvider(url).local_model_inventory()
    assert result.state == "unknown" and not result.supported
    assert "secret" not in str(result)
