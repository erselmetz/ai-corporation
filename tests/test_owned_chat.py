from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.application.services.owned_chat import ChatConflict, ChatConsentRequired, ChatLimit, ChatNotFound
from app.local import create_local_app
from app.providers import AIProvider
from app.providers.inventory import LocalModelInventory
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from app.runtime.factory import create_corporation_runtime


class Provider(AIProvider):
    def __init__(self):
        self.calls = []
        self.fail = False
        self.block = False
        self.entered = Event()
        self.finish = Event()

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        self.entered.set()
        if self.block and not self.finish.wait(5):
            raise RuntimeError("Test provider was not released")
        if self.fail:
            raise RuntimeError("secret-provider-credential")
        return "<script>alert('untrusted')</script> deterministic reply"


class StreamingProvider(Provider):
    supports_streaming = True

    def __init__(self):
        super().__init__()
        self.stream_closed = False

    def generate_stream(self, model, prompt):
        self.calls.append((model, prompt))
        try:
            yield "partial "
            self.entered.set()
            if self.block and not self.finish.wait(5):
                raise RuntimeError("Test stream was not released")
            if self.fail:
                raise RuntimeError("secret-provider-credential")
            yield "reply"
        finally:
            self.stream_closed = True


class InstalledLocalProvider(Provider):
    is_local = True

    def local_model_inventory(self):
        return LocalModelInventory("available", ("llama3.2:3b", "qwen2.5:7b"), True,
                                   source="deterministic-test-fixture", reason=None)


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    provider = Provider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    return runtime, provider


class Authentication:
    def authenticate(self, request):
        identity = request.headers.get("x-test-owner")
        if identity is None:
            return None
        permissions = frozenset({"chat:read", "chat:start", "chat:send", "chat:close", "chat-history:manage"})
        if identity == "reader":
            permissions = frozenset({"chat:read"})
        return AuthenticatedPrincipal(identity, permissions)


def client_for(runtime):
    return TestClient(create_app(application_service=runtime.application_service,
                                authentication_backend=Authentication()))


def start(client, owner="alice"):
    return client.post("/api/chat/conversations", json={"agent_id": "local_worker"},
                       headers={"x-test-owner": owner})


def test_owned_chat_roundtrip_and_no_execution_or_capacity_side_effect(setup):
    runtime, provider = setup
    resource = runtime.application_service.resource_manager(ResourceLimits(1,
        (ProviderLimit("ollama", 1),), (ModelLimit("ollama", "llama3.2:3b", 1),)))
    before = resource.snapshot()
    agents = runtime.application_service.list_agents()
    tasks = runtime.application_service.list_tasks()
    with client_for(runtime) as client:
        result = start(client)
        assert result.status_code == 200
        body = result.json()
        identifier = body["conversation"]["id"]
        assert len(identifier) == 32
        assert body["coordinator"]["model"] == "llama3.2:3b"
        assert provider.calls == []
        response = client.post(f"/api/chat/conversations/{identifier}/messages", json={"text": "Hello"},
                               headers={"x-test-owner": "alice"})
        assert response.status_code == 200
        assert [m["status"] for m in response.json()["conversation"]["messages"]] == ["completed", "completed"]
        assert len(provider.calls) == 1
        assert "Hello" in provider.calls[0][1]
        assert client.get("/api/chat/conversations", headers={"x-test-owner": "alice"}).json()["items"][0]["id"] == identifier
        assert "messages" not in client.get("/api/chat/conversations", headers={"x-test-owner": "alice"}).json()["items"][0]
        assert client.post(f"/api/chat/conversations/{identifier}/close", headers={"x-test-owner": "alice"}).json()["conversation"]["status"] == "closed"
        assert client.post(f"/api/chat/conversations/{identifier}/messages", json={"text": "Again"},
                           headers={"x-test-owner": "alice"}).status_code == 422
    assert resource.snapshot() == before
    assert runtime.application_service.list_agents() == agents
    assert runtime.application_service.list_tasks() == tasks
    assert len(provider.calls) == 1


def test_delete_requires_history_management_and_removes_owner_conversation(setup):
    runtime, _provider = setup
    with client_for(runtime) as client:
        created = start(client)
        identifier = created.json()["conversation"]["id"]
        denied = client.delete(f"/api/chat/conversations/{identifier}", headers={"x-test-owner": "reader"})
        assert denied.status_code == 403
        removed = client.delete(f"/api/chat/conversations/{identifier}", headers={"x-test-owner": "alice"})
        assert removed.status_code == 200
        assert removed.json() == {"deleted": identifier}
        assert client.get(f"/api/chat/conversations/{identifier}", headers={"x-test-owner": "alice"}).status_code == 404
        assert client.get("/api/chat/conversations", headers={"x-test-owner": "alice"}).json()["items"] == []


def test_route_suggestions_are_uncertain_local_hints_and_alternates_are_per_turn_only():
    runtime = create_corporation_runtime()
    configured = InstalledLocalProvider()
    alternate = InstalledLocalProvider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", configured)
    runtime.providers.register("ollama-secondary", alternate)
    original = runtime.application_service.get_agent("local_worker")
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        headers = {"x-test-owner": "alice"}
        easy = client.post(f"/api/chat/conversations/{identifier}/route-suggestions",
                           json={"text": "What is 2 + 2?"}, headers=headers)
        assert easy.status_code == 200
        assert easy.json()["complexity"] == "simple"
        assert easy.json()["candidates"] == []

        harder = client.post(f"/api/chat/conversations/{identifier}/route-suggestions",
                             json={"text": "Compare these designs and explain the trade-offs."},
                             headers=headers)
        assert harder.status_code == 200
        assert harder.json()["complexity"] == "complex"
        assert "uncertain" in harder.json()["reason"]
        assert harder.json()["suggested"]["model_id"] == "qwen2.5:7b"
        assert configured.calls == alternate.calls == []

        simple_route = client.post(f"/api/chat/conversations/{identifier}/messages",
                                   json={"text": "What is 2 + 2?", "route_provider_id": "ollama-secondary",
                                         "route_model_id": "qwen2.5:7b", "route_consent": True}, headers=headers)
        assert simple_route.status_code == 422
        uncertain_route = client.post(f"/api/chat/conversations/{identifier}/messages",
                                      json={"text": "Describe the current configuration in a neutral and fairly detailed way without requesting a recommendation, comparison, or implementation action, and focus only on what is already present.",
                                            "route_provider_id": "ollama-secondary",
                                            "route_model_id": "qwen2.5:7b", "route_consent": True}, headers=headers)
        assert uncertain_route.status_code == 422
        assert alternate.calls == configured.calls == []

        denied = client.post(f"/api/chat/conversations/{identifier}/messages",
                             json={"text": "Compare designs", "route_provider_id": "ollama-secondary",
                                   "route_model_id": "qwen2.5:7b"}, headers=headers)
        assert denied.status_code == 403
        assert alternate.calls == []

        unavailable = client.post(f"/api/chat/conversations/{identifier}/messages",
                                  json={"text": "Compare designs", "route_provider_id": "ollama-secondary",
                                        "route_model_id": "missing:70b", "route_consent": True}, headers=headers)
        assert unavailable.status_code == 503
        assert alternate.calls == configured.calls == []

        not_larger = client.post(
            f"/api/chat/conversations/{identifier}/messages",
            json={"text": "Compare designs", "route_provider_id": "ollama-secondary",
                  "route_model_id": "llama3.2:3b", "route_consent": True}, headers=headers)
        assert not_larger.status_code == 422
        assert alternate.calls == configured.calls == []

        cloud = Provider()
        cloud.requires_explicit_cloud_consent = True
        runtime.providers.register("gemini-test", cloud)
        cloud_denied = client.post(f"/api/chat/conversations/{identifier}/messages",
                                   json={"text": "Compare designs", "route_provider_id": "gemini-test",
                                         "route_model_id": "gemini-2.5-flash", "route_consent": True},
                                   headers=headers)
        assert cloud_denied.status_code == 403
        assert cloud.calls == []

        class GeminiConnections:
            def list(self):
                return ({"provider_id": "gemini-test", "provider_type": "gemini",
                         "state": "available", "models": ["gemini-2.5-flash"]},)

        client.app.state.provider_connections_service = GeminiConnections()
        cloud_allowed = client.post(
            f"/api/chat/conversations/{identifier}/messages",
            json={"text": "Compare designs", "route_provider_id": "gemini-test",
                  "route_model_id": "gemini-2.5-flash", "route_consent": True,
                  "cloud_consent": True}, headers=headers)
        assert cloud_allowed.status_code == 200
        assert len(cloud.calls) == 1
        trace = cloud_allowed.json()["context_trace"]
        assert trace["route"]["provider"] == "gemini-test"
        assert trace["route"]["model"] == "gemini-2.5-flash"
        assert trace["cloud"]["provider_used"] == "gemini-test"
        assert trace["cloud"]["consent_given"] is True

        sent = client.post(f"/api/chat/conversations/{identifier}/messages",
                           json={"text": "Compare designs", "route_provider_id": "ollama-secondary",
                                 "route_model_id": "qwen2.5:7b", "route_consent": True}, headers=headers)
        assert sent.status_code == 200
        assert len(alternate.calls) == 1
        assert configured.calls == []
        assert sent.json()["context_trace"]["route"]["provider"] == "ollama-secondary"
        assert sent.json()["context_trace"]["route"]["model"] == "qwen2.5:7b"
        assert "turn only" in sent.json()["context_trace"]["route"]["source"]
        assert runtime.application_service.get_agent("local_worker") == original


def test_coordinator_chat_page_exposes_explicit_route_review_controls():
    runtime = create_corporation_runtime()
    with client_for(runtime) as client:
        page = client.get("/ui/chat")
    assert page.status_code == 200
    assert 'id="chat-route-check"' in page.text
    assert 'id="chat-route-select"' in page.text
    assert 'id="chat-route-state" role="status"' in page.text
    assert "configured model remains the default" in page.text


def test_owned_chat_service_requires_explicit_route_consent_before_alternate_dispatch(setup):
    runtime, provider = setup
    owned = runtime.application_service.owned_chat()
    identifier = owned.start("alice", "local_worker")["conversation"].id
    with pytest.raises(ChatConsentRequired, match="Explicit per-turn route consent"):
        owned.send("alice", identifier, "Compare these", turn_route=("ollama", "qwen2.5:7b"))
    assert provider.calls == []


def test_suggestions_do_not_reroute_a_nonlocal_configured_coordinator():
    runtime = create_corporation_runtime()
    cloud = Provider()
    cloud.requires_explicit_cloud_consent = True
    runtime.providers.register("gemini-test", cloud)
    runtime.application_service.assign_model("local_worker", "gemini-test", "gemini-2.5-flash")
    assigned = runtime.application_service.get_agent("local_worker")
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        headers = {"x-test-owner": "alice"}
        result = client.post(f"/api/chat/conversations/{identifier}/route-suggestions",
                             json={"text": "Compare the two designs"}, headers=headers)
        assert result.status_code == 200
        assert result.json()["complexity"] == "unknown"
        assert result.json()["candidates"] == []
        rejected = client.post(f"/api/chat/conversations/{identifier}/messages",
                               json={"text": "Compare the two designs", "route_provider_id": "ollama",
                                     "route_model_id": "llama3.2:3b", "route_consent": True},
                               headers=headers)
        assert rejected.status_code == 422
        assert runtime.application_service.get_agent("local_worker") == assigned
        assert cloud.calls == []


def test_streaming_endpoint_returns_real_chunks_and_persists_only_final_reply():
    runtime = create_corporation_runtime()
    provider = StreamingProvider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        path = f"/api/chat/conversations/{identifier}"
        assert client.get(path, headers={"x-test-owner": "alice"}).json()["streaming_supported"]
        response = client.post(
            path + "/messages/stream",
            json={"text": "Hello"},
            headers={"x-test-owner": "alice"},
        )
        assert response.status_code == 200
        events = [json.loads(line) for line in response.text.splitlines()]
        assert [(event["type"], event.get("text")) for event in events] == [
            ("chunk", "partial "),
            ("chunk", "reply"),
            ("complete", None),
        ]
        messages = events[-1]["conversation"]["messages"]
        assert [(message["role"], message["status"], message["content"]) for message in messages] == [
            ("user", "completed", "Hello"),
            ("assistant", "completed", "partial reply"),
        ]
        assert events[-1]["streaming_supported"] is True
        assert provider.calls and "Hello" in provider.calls[0][1]


def test_unsupported_provider_streaming_is_rejected_before_recording_turn(setup):
    runtime, provider = setup
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        response = client.post(
            f"/api/chat/conversations/{identifier}/messages/stream",
            json={"text": "Hello"},
            headers={"x-test-owner": "alice"},
        )
        assert response.status_code == 409
        assert "does not support response streaming" in response.text
        assert client.get(
            f"/api/chat/conversations/{identifier}",
            headers={"x-test-owner": "alice"},
        ).json()["conversation"]["messages"] == []
    assert provider.calls == []


def test_stream_failure_keeps_turn_pending_and_does_not_expose_provider_error():
    runtime = create_corporation_runtime()
    provider = StreamingProvider()
    provider.fail = True
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        path = f"/api/chat/conversations/{identifier}"
        response = client.post(
            path + "/messages/stream",
            json={"text": "Hello"},
            headers={"x-test-owner": "alice"},
        )
        events = [json.loads(line) for line in response.text.splitlines()]
        assert response.status_code == 200
        assert events[0] == {"type": "chunk", "text": "partial "}
        assert events[-1]["type"] == "error"
        assert "secret-provider-credential" not in response.text
        messages = client.get(path, headers={"x-test-owner": "alice"}).json()["conversation"]["messages"]
        assert len(messages) == 1
        assert messages[0]["status"] == "pending"


def test_closing_stream_releases_provider_and_keeps_interrupted_turn_pending(setup):
    runtime = create_corporation_runtime()
    provider = StreamingProvider()
    provider.block = True
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    chat = runtime.application_service.owned_chat()
    identifier = chat.start("alice", "local_worker")["conversation"].id
    stream = chat.stream("alice", identifier, "Hello")
    assert next(stream) == {"type": "chunk", "text": "partial "}
    stream.close()
    assert provider.stream_closed
    assert chat.get("alice", identifier)["conversation"].messages[0].status.value == "pending"


def test_owner_isolation_permissions_and_default_rejecting(setup):
    runtime, provider = setup
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        for owner, status in [("bob", 404), (None, 401)]:
            headers = {"x-test-owner": owner} if owner else {}
            for method, suffix, body in [("get", "", None), ("post", "/messages", {"text": "intrusion"}), ("post", "/close", {})]:
                assert client.request(method, f"/api/chat/conversations/{identifier}{suffix}", json=body, headers=headers).status_code == status
        assert client.get("/api/chat/conversations", headers={"x-test-owner": "bob"}).json() == {"items": []}
        assert start(client, "reader").status_code == 403
        assert client.post(f"/api/chat/conversations/{identifier}/messages", json={"text": "X"}, headers={"x-test-owner": "reader"}).status_code == 403
        assert client.post("/api/chat/conversations", json={"agent_id": "local_worker", "owner": "bob"}, headers={"x-test-owner": "alice"}).status_code == 422
    with TestClient(create_app(application_service=runtime.application_service)) as client:
        assert start(client).status_code == 401
    assert provider.calls == []


def test_failed_reply_safe_history_no_retry_and_closure(setup):
    runtime, provider = setup
    provider.fail = True
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        path = f"/api/chat/conversations/{identifier}"
        response = client.post(path + "/messages", json={"text": "Hello"}, headers={"x-test-owner": "alice"})
        assert response.status_code == 502
        assert "secret-provider" not in response.text
        stored = client.get(path, headers={"x-test-owner": "alice"}).json()
        messages = stored["conversation"]["messages"]
        assert len(messages) == 1 and messages[0]["status"] == "failed"
        trace = stored["context_traces"][messages[0]["id"]]
        assert trace["outcome"] == "failed"
        assert [step["status"] for step in trace["steps"]] == ["completed", "skipped", "skipped", "failed"]
        assert trace["steps"][-1]["duration_ms"] >= 0
        assert "secret-provider" not in json.dumps(trace)
        assert "raw diagnostics are omitted" in trace["failure"]
        assert client.post(path + "/close", headers={"x-test-owner": "alice"}).status_code == 200
        assert len(provider.calls) == 1


def test_input_bounds_missing_configuration_and_assignment_change(setup):
    runtime, provider = setup
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        path = f"/api/chat/conversations/{identifier}"
        for text in (" ", "x" * 8193, "界" * 3000):
            assert client.post(path + "/messages", json={"text": text}, headers={"x-test-owner": "alice"}).status_code == 422
        response = client.post(path + "/messages", content=b"x" * 65537, headers={"x-test-owner": "alice", "Content-Type": "application/json"})
        assert response.status_code == 413
        assert client.get(path, headers={"x-test-owner": "alice"}).json()["conversation"]["messages"] == []
        assert client.post("/api/chat/conversations", json={"agent_id": "missing"}, headers={"x-test-owner": "alice"}).status_code == 503
        runtime.application_service.replace_model("local_worker", "ollama", "other-model")
        assert client.post(path + "/messages", json={"text": "Hello"}, headers={"x-test-owner": "alice"}).status_code == 409
        runtime.providers.remove("ollama")
        assert start(client).status_code == 503
    assert provider.calls == []


def test_recognized_gemini_key_paste_is_rejected_before_history_or_provider(setup):
    runtime, provider = setup
    key = "AIza" + "A" * 35
    with client_for(runtime) as client:
        identifier = start(client).json()["conversation"]["id"]
        path = f"/api/chat/conversations/{identifier}"
        for text in (key, f"GEMINI_API_KEY={key}"):
            response = client.post(path + "/messages", json={"text": text},
                                   headers={"x-test-owner": "alice"})
            assert response.status_code == 422
            assert key not in response.text
            assert "not saved or sent" in response.text
            assert "Gemini online setup" in response.text
            assert client.get(path, headers={"x-test-owner": "alice"}).json()["conversation"]["messages"] == []
    assert provider.calls == []


def test_overlapping_requests_rejected_and_lock_released(setup):
    runtime, provider = setup
    chat = runtime.application_service.owned_chat()
    assert chat is runtime.application_service.owned_chat()
    identifier = chat.start("alice", "local_worker")["conversation"].id
    assert chat.get_status("alice", identifier).value == "open"
    provider.block = True
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(chat.send, "alice", identifier, "First")
        try:
            assert provider.entered.wait(3)
            for operation in [lambda: chat.send("alice", identifier, "Duplicate"),
                              lambda: chat.get("alice", identifier),
                              lambda: chat.get_status("alice", identifier),
                              lambda: chat.close("alice", identifier)]:
                with pytest.raises(ChatConflict, match="busy"):
                    operation()
            with pytest.raises(ChatNotFound):
                chat.get("bob", identifier)
            with pytest.raises(ChatNotFound):
                chat.get_status("bob", identifier)
        finally:
            provider.finish.set()
        assert len(pending.result(timeout=3)["conversation"].messages) == 2
    assert chat.close("alice", identifier)["conversation"].status.value == "closed"
    assert chat.get_status("alice", identifier).value == "closed"
    assert len(provider.calls) == 1


def test_bounded_conversation_and_message_history(setup):
    runtime, provider = setup
    chat = runtime.application_service.owned_chat()
    identifier = None
    for _ in range(chat.MAX_CONVERSATIONS):
        identifier = chat.start("alice", "local_worker")["conversation"].id
    with pytest.raises(ChatLimit):
        chat.start("alice", "local_worker")
    for _ in range(chat.MAX_MESSAGES // 2):
        chat.send("alice", identifier, "short")
    with pytest.raises(ChatLimit):
        chat.send("alice", identifier, "overflow")
    assert len(chat.get("alice", identifier)["conversation"].messages) == 200
    assert len(provider.calls) == 100


def test_trusted_cli_chat_is_separate_and_local_csrf_applies(setup):
    runtime, provider = setup
    runtime.application_service.corporation_chat().start("cli-private", "local_worker")
    origin = "http://127.0.0.1:8000"
    app = create_local_app(password="test-only-passphrase", application_service=runtime.application_service)
    with TestClient(app, base_url=origin, client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/local/login", json={"password": "test-only-passphrase"}, headers={"Origin": origin}).status_code == 200
        assert client.get("/api/chat/conversations").json() == {"items": []}
        assert client.get("/api/chat/conversations/cli-private").status_code == 404
        assert client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers={"Origin": origin}).status_code == 403
        session = client.get("/api/local/session").json()
        assert {"chat:read", "chat:start", "chat:send", "chat:close"} <= set(session["permissions"])
        assert "task:create" not in session["permissions"]
        response = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers={"Origin": origin, "X-Local-CSRF": session["csrf"]})
        assert response.status_code == 200
        page = client.get("/ui/chat")
        assert page.status_code == 200 and "chat-history" in page.text
        assert client.get("/ui/static/chat.mjs").status_code == 200
    assert provider.calls == []
