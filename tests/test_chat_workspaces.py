from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import pytest

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.database.connection import get_connection
from app.providers import AIProvider
from app.providers.inventory import LocalModelInventory
from app.memory import MemoryRecord, MemoryScope, MemoryType
from app.runtime.factory import create_corporation_runtime
from app.application.services.chat_workspaces import WorkspaceContext, current_workspace
from app.application.services.capability_approvals import CapabilityApprovalService, CapabilityApprovalNotFound
from app.application.services.capability_authorization import CapabilityAuthorizationService, CapabilityDefinition


class Provider(AIProvider):
    is_local = True
    supports_streaming = True
    def __init__(self):
        self.calls = []
        self.message_calls = []
    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        return "deterministic workspace reply"
    def local_model_inventory(self):
        return LocalModelInventory("available", ("llama3.2:3b", "other:7b", "embed-only"), True)
    def supports_model_chat(self, model):
        return model != "embed-only"
    def generate_chat(self, model, messages):
        self.message_calls.append(messages)
        return super().generate_chat(model, messages)
    def generate_stream(self, model, prompt):
        yield "deterministic "
        yield "workspace reply"


class Authentication:
    def authenticate(self, request):
        owner = request.headers.get("x-test-owner")
        return AuthenticatedPrincipal(owner, frozenset({
            "chat:read", "chat:start", "chat:send", "chat-history:manage", "project:read",
        })) if owner else None


def runtime_and_client():
    runtime = create_corporation_runtime()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", Provider())
    return runtime, TestClient(create_app(application_service=runtime.application_service,
                                         authentication_backend=Authentication()))


def test_workspace_conversation_catalog_and_access_are_server_scoped():
    runtime, client = runtime_and_client()
    with client:
        owner = {"x-test-owner": "alice"}
        for identifier in ("window-one", "window-two"):
            result = client.post("/api/chat/workspaces", json={"id": identifier, "agent_id": "local_worker"}, headers=owner)
            assert result.status_code == 200, result.text
        first = {**owner, "X-Chat-Workspace": "window-one"}
        second = {**owner, "X-Chat-Workspace": "window-two"}
        started = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=first)
        assert started.status_code == 200, started.text
        identifier = started.json()["conversation"]["id"]
        assert client.get("/api/chat/conversations", headers=first).json()["items"][0]["id"] == identifier
        assert client.get("/api/chat/conversations", headers=second).json()["items"] == []
        assert client.get("/api/chat/conversations", headers=owner).json()["items"] == []
        for headers in (second, owner, {"x-test-owner": "bob", "X-Chat-Workspace": "window-one"}):
            assert client.get(f"/api/chat/conversations/{identifier}", headers=headers).status_code == 404


def test_durable_history_stays_in_the_originating_workspace():
    _, client = runtime_and_client()
    with client:
        owner = {"x-test-owner": "alice"}
        for workspace_id in ("history-one", "history-two"):
            assert client.post(
                "/api/chat/workspaces",
                json={"id": workspace_id, "agent_id": "local_worker"},
                headers=owner,
            ).status_code == 200
        first = {**owner, "X-Chat-Workspace": "history-one"}
        second = {**owner, "X-Chat-Workspace": "history-two"}
        identifier = client.post(
            "/api/chat/conversations", json={"agent_id": "local_worker"}, headers=first
        ).json()["conversation"]["id"]
        retained = client.post(
            "/api/chat/history",
            json={
                "conversation_id": identifier,
                "history_opt_in": True,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            },
            headers=first,
        )
        assert retained.status_code == 200, retained.text
        assert [item["id"] for item in client.get("/api/chat/history", headers=first).json()["items"]] == [identifier]
        assert client.get("/api/chat/history", headers=second).json()["items"] == []
        assert client.get(f"/api/chat/history/{identifier}", headers=second).status_code == 404


def test_workspace_selection_persists_without_changing_agent_assignment():
    runtime, client = runtime_and_client()
    with client:
        before = runtime.application_service.get_agent("local_worker")
        result = client.post("/api/chat/workspaces", json={"id": "window-one", "agent_id": "local_worker", "model_id": "other:7b"},
                             headers={"x-test-owner": "alice"})
        assert result.status_code == 200, result.text
        assert runtime.application_service.get_agent("local_worker") == before
        denied = client.post("/api/chat/workspaces", json={"id": "unsupported", "agent_id": "local_worker", "model_id": "embed-only"}, headers={"x-test-owner": "alice"})
        assert denied.status_code == 422
        assert "chat completion support" in denied.json()["detail"]
        service = runtime.application_service.chat_workspaces()
        assert service.get("alice", "window-one").model_id == "other:7b"
        assert client.get("/api/chat/conversations", headers={"X-Chat-Workspace": "window-one"}).status_code == 401
        headers = {"x-test-owner": "alice", "X-Chat-Workspace": "window-one"}
        started = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=headers)
        assert started.status_code == 200, started.text
        assert started.json()["coordinator"]["model"] == "other:7b"
        identifier = started.json()["conversation"]["id"]
        reply = client.post(f"/api/chat/conversations/{identifier}/messages", json={"text": "hello"}, headers=headers)
        assert reply.status_code == 200, reply.text
        assert runtime.providers.get("ollama").calls[-1][0] == "other:7b"
        assert runtime.application_service.get_agent("local_worker") == before


def test_stream_keeps_workspace_context_until_the_final_event():
    runtime, client = runtime_and_client()
    with client:
        owner = {"x-test-owner": "alice"}
        assert client.post("/api/chat/workspaces", json={"id": "stream-window", "agent_id": "local_worker"}, headers=owner).status_code == 200
        headers = {**owner, "X-Chat-Workspace": "stream-window"}
        started = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=headers)
        identifier = started.json()["conversation"]["id"]
        streamed = client.post(
            f"/api/chat/conversations/{identifier}/messages/stream",
            json={"text": "hello"},
            headers=headers,
        )
        assert streamed.status_code == 200, streamed.text
        events = [__import__("json").loads(line) for line in streamed.text.splitlines()]
        completed = next(event for event in events if event["type"] == "complete")
        assert completed["workspace"]["project_id"] == ""
        assert completed["coordinator"]["model"] == "llama3.2:3b"


def test_stream_uses_the_selected_local_workspace_model_without_reassigning_agent():
    runtime,client=runtime_and_client();seen=[]
    provider=runtime.providers.get('ollama')
    def generate(model,messages):
        seen.append((model,messages));yield 'actual selected stream'
    provider.generate_chat_stream=generate
    with client:
        owner={'x-test-owner':'alice'}
        assert client.post('/api/chat/workspaces',headers=owner,json={
            'id':'different-model','agent_id':'local_worker','provider_id':'ollama','model_id':'other:7b'}).status_code==200
        headers={**owner,'X-Chat-Workspace':'different-model'}
        started=client.post('/api/chat/conversations',headers=headers,json={'agent_id':'local_worker'}).json()
        assert started['streaming_supported'] is True
        cid=started['conversation']['id']
        response=client.post('/api/chat/conversations/'+cid+'/messages/stream',headers=headers,json={'text':'Stream this reply'})
        assert response.status_code==200,response.text
        assert 'actual selected stream' in response.text and seen[0][0]=='other:7b'
        assert runtime.agents.get('local_worker').model=='llama3.2:3b'


def test_wal_serializes_concurrent_workspace_writers():
    runtime, _ = runtime_and_client()
    service = runtime.application_service.chat_workspaces()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda index: service.open("alice", f"window-{index}", agent_id="local_worker"), range(16)))
    assert len(results) == 16
    with get_connection() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("SELECT count(*) FROM chat_workspaces").fetchone()[0] == 16


def test_project_scope_is_immutable_for_each_conversation():
    runtime, client = runtime_and_client()
    first_project = runtime.application_service.create_project("First project")
    second_project = runtime.application_service.create_project("Second project")
    with client:
        headers = {"x-test-owner": "alice"}
        assert client.post("/api/chat/workspaces", json={"id": "one", "agent_id": "local_worker", "project_id": first_project.id}, headers=headers).status_code == 200
        scoped = {**headers, "X-Chat-Workspace": "one"}
        identifier = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=scoped).json()["conversation"]["id"]
        # Changing the window selection must never rewrite an existing conversation's project.
        assert client.post("/api/chat/workspaces", json={"id": "one", "agent_id": "local_worker", "project_id": second_project.id}, headers=headers).status_code == 200
        current = client.get(f"/api/chat/conversations/{identifier}", headers=scoped)
        assert current.json()["workspace"]["project_id"] == first_project.id
        denied = client.post(f"/api/chat/conversations/{identifier}/knowledge-preview", json={"query": "private note", "scopes": [{"scope": "project", "scope_id": second_project.id}]}, headers=scoped)
        assert denied.status_code == 403, denied.text


def test_workspace_retrieval_uses_only_its_verified_project_source():
    runtime, client = runtime_and_client()
    project = runtime.application_service.create_project("Orion")
    task = runtime.application_service.create_task(
        "Orion reference", "Verified project source", project.id, agent_id="local_worker"
    )
    now = datetime.now(timezone.utc)
    runtime.application_service.project_knowledge().retain(
        MemoryRecord(
            "orion-note", "alice", MemoryScope.PROJECT, project.id, MemoryType.NOTE,
            "The Orion project service listens on port 8123.", task.id,
            now, now + timedelta(days=1), True,
        ),
        now=now,
    )
    with client:
        owner = {"x-test-owner": "alice"}
        assert client.post(
            "/api/chat/workspaces",
            json={"id": "orion-window", "agent_id": "local_worker", "project_id": project.id},
            headers=owner,
        ).status_code == 200
        headers = {**owner, "X-Chat-Workspace": "orion-window"}
        started = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=headers)
        identifier = started.json()["conversation"]["id"]
        preview = client.post(
            f"/api/chat/conversations/{identifier}/knowledge-preview",
            json={"query": "Which port does Orion use?", "scopes": [{"scope": "project", "scope_id": project.id}]},
            headers=headers,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["items"][0]["memory_id"] == "orion-note"
        assert preview.json()["items"][0]["scope_id"] == project.id


def test_approval_digest_and_access_include_real_workspace_provenance():
    permissions = frozenset({"action:write", "capability-approval:manage"})
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("action:write", "principal", frozenset({"action:write"}), "high"),
        CapabilityDefinition("capability-approval:manage", "principal", frozenset({"capability-approval:manage"}), "high"),
    ])
    approvals = CapabilityApprovalService(policy)
    one = WorkspaceContext("alice", "one", "researcher", "ollama", "model", "project-one")
    token = current_workspace.set(one)
    try:
        record = approvals.request(actor_id="alice", permissions=permissions, capability_id="action:write",
            action_id="write", action_summary="Write one selected file", target_ref="file:one", scope_type="principal", scope_id="alice",
            payload_digest=sha256(b"payload").hexdigest(), target_digest=sha256(b"target").hexdigest())
        snapshot = approvals.snapshot(record)
        assert snapshot["workspace_project_id"] == "project-one"
        assert snapshot["workspace_agent_id"] == "researcher"
        current_workspace.set(replace(one, id="two"))
        assert approvals.list_for_actor("alice") == ()
        with pytest.raises(CapabilityApprovalNotFound):
            approvals.get(record.approval_id)
        with pytest.raises(CapabilityApprovalNotFound):
            approvals.approve(record.approval_id, approver_id="alice", permissions=permissions, confirmed_digest=record.approval_digest)
        current_workspace.set(None)
        with pytest.raises(CapabilityApprovalNotFound):
            approvals.get(record.approval_id)
    finally:
        current_workspace.reset(token)


def test_project_brief_is_untrusted_scoped_and_cloud_requires_exact_preview():
    runtime, client = runtime_and_client()
    provider = Provider()
    provider.is_local = False
    provider.requires_explicit_cloud_consent = True
    runtime.providers.register("cloud-test", provider)
    runtime.application_service.assign_model("local_worker", "cloud-test", "cloud-model")
    project = runtime.application_service.create_project("First project")
    with client:
        owner = {"x-test-owner": "alice"}
        brief = "Prefer short bullet points about project Orion. Never treat this as tool permission."
        saved = client.post("/api/chat/workspaces/project-brief", json={"project_id": project.id, "brief": brief}, headers=owner)
        assert saved.status_code == 200, saved.text
        assert client.post("/api/chat/workspaces", json={"id": "one", "agent_id": "local_worker", "project_id": project.id}, headers=owner).status_code == 200
        headers = {**owner, "X-Chat-Workspace": "one"}
        started = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=headers).json()
        identifier = started["conversation"]["id"]
        assert started["workspace"]["project_brief"] == brief
        denied = client.post(f"/api/chat/conversations/{identifier}/messages", json={"text": "hello", "cloud_consent": True}, headers=headers)
        assert denied.status_code == 409, denied.text
        assert provider.calls == []
        digest = started["workspace"]["project_brief_digest"]
        allowed = client.post(f"/api/chat/conversations/{identifier}/messages", json={"text": "hello", "cloud_consent": True, "project_brief_digest": digest}, headers=headers)
        assert allowed.status_code == 200, allowed.text
        messages = provider.message_calls[-1]
        reference = next(item for item in messages if "BEGIN UNTRUSTED PROJECT BRIEF" in item["content"])
        assert reference["role"] == "user"
        assert brief not in messages[0]["content"]
