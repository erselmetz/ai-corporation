from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.application.services.owned_chat import ChatConflict, ChatLimit, ChatNotFound
from app.local import create_local_app
from app.providers import AIProvider
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
        permissions = frozenset({"chat:read", "chat:start", "chat:send", "chat:close"})
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
        messages = client.get(path, headers={"x-test-owner": "alice"}).json()["conversation"]["messages"]
        assert len(messages) == 1 and messages[0]["status"] == "failed"
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
    provider.block = True
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(chat.send, "alice", identifier, "First")
        try:
            assert provider.entered.wait(3)
            for operation in [lambda: chat.send("alice", identifier, "Duplicate"),
                              lambda: chat.get("alice", identifier), lambda: chat.close("alice", identifier)]:
                with pytest.raises(ChatConflict, match="busy"):
                    operation()
            with pytest.raises(ChatNotFound):
                chat.get("bob", identifier)
        finally:
            provider.finish.set()
        assert len(pending.result(timeout=3)["conversation"].messages) == 2
    assert chat.close("alice", identifier)["conversation"].status.value == "closed"
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
