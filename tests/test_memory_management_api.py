from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from app.api import AuthenticatedPrincipal, create_app
from app.api.memory import get_memory_now
from app.database import get_connection
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
QUERY = "scope=conversation&scope_id=chat&memory_id=memory"


class Authentication:
    def __init__(self, identity="owner", permissions=frozenset({"memory:read", "memory:manage"})):
        self.identity, self.permissions = identity, permissions
    def authenticate(self, _request):
        return AuthenticatedPrincipal(self.identity, self.permissions)


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    record = MemoryRecord("memory", "owner", MemoryScope.CONVERSATION, "chat",
                          MemoryType.NOTE, "Original note", "message", NOW,
                          NOW + timedelta(hours=1), True)
    ConversationMemoryStore().retain(record, now=NOW)
    return runtime, record


def application(runtime, auth=None):
    app = create_app(runtime.application_service, auth)
    app.dependency_overrides[get_memory_now] = lambda: NOW
    return app


def test_default_authentication_fails_closed(setup):
    runtime, _ = setup
    with TestClient(application(runtime)) as client:
        assert client.get("/api/memory?scope=conversation&scope_id=chat").status_code == 401
        assert client.get("/api/memory/record?" + QUERY).status_code == 401
        assert client.delete("/api/memory/record?" + QUERY).status_code == 401
        assert client.put("/api/memory/record?" + QUERY, json={}).status_code == 401
        assert client.get("/ui/memory").status_code == 200
        assert client.get("/ui/static/memory.mjs").status_code == 200


def test_permission_and_owner_boundaries_reject_spoofing(setup):
    runtime, _ = setup
    with TestClient(application(runtime, Authentication(permissions=frozenset()))) as client:
        assert client.get("/api/memory/record?" + QUERY).status_code == 403
    with TestClient(application(runtime, Authentication(identity="other"))) as client:
        assert client.get("/api/memory/record?" + QUERY + "&owner_id=owner").status_code == 404
        assert client.delete("/api/memory/record?" + QUERY).status_code == 404
        assert client.get("/api/memory?scope=conversation&scope_id=chat").json() == {"items": []}
    with TestClient(application(runtime, Authentication(permissions=frozenset({"memory:read"})))) as client:
        assert client.delete("/api/memory/record?" + QUERY).status_code == 403


def test_inspect_correct_retain_conflict_and_remove_round_trip(setup):
    runtime, record = setup
    with TestClient(application(runtime, Authentication())) as client:
        listing = client.get("/api/memory?scope=conversation&scope_id=chat")
        assert listing.status_code == 200
        assert "content" not in listing.json()["items"][0]
        detail = client.get("/api/memory/record?" + QUERY).json()
        body = dict(content="Corrected note", expires_at=(NOW + timedelta(hours=2)).isoformat(),
                    retention_opt_in=True, revision=detail["revision"])
        saved = client.put("/api/memory/record?" + QUERY, json=body)
        assert saved.status_code == 200
        assert saved.json()["content"] == "Corrected note"
        assert saved.json()["source_id"] == record.source_id
        assert client.put("/api/memory/record?" + QUERY, json=body).status_code == 409
        assert client.delete("/api/memory/record?" + QUERY).status_code == 204
        assert client.get("/api/memory/record?" + QUERY).status_code == 404
    with pytest.raises(KeyError):
        ConversationMemoryStore().retrieve("memory", owner_id="owner", conversation_id="chat", now=NOW)


@pytest.mark.parametrize("changes", [
    {"retention_opt_in": False}, {"retention_opt_in": 1}, {"owner_id": "other"},
    {"expires_at": NOW.isoformat()}, {"expires_at": "2026-10-03T00:00:00"},
    {"content": ""}, {"content": "\u00e9" * 8192},
])
def test_invalid_edits_preserve_original(setup, changes):
    runtime, record = setup
    with TestClient(application(runtime, Authentication())) as client:
        detail = client.get("/api/memory/record?" + QUERY).json()
        body = dict(content="Corrected", expires_at=(NOW + timedelta(hours=2)).isoformat(), retention_opt_in=True, revision=detail["revision"])
        body.update(changes)
        assert client.put("/api/memory/record?" + QUERY, json=body).status_code == 422
    assert ConversationMemoryStore().retrieve("memory", owner_id="owner", conversation_id="chat", now=NOW) == record


def test_expiry_metadata_without_content_and_owner_removal(setup):
    runtime, record = setup
    app = application(runtime, Authentication())
    app.dependency_overrides[get_memory_now] = lambda: record.expires_at
    with TestClient(app) as client:
        item = client.get("/api/memory?scope=conversation&scope_id=chat").json()["items"][0]
        assert item["expired"] is True
        assert "content" not in item
        assert client.get("/api/memory/record?" + QUERY).status_code == 410
        assert client.delete("/api/memory/record?" + QUERY).status_code == 204


def test_published_reader_cannot_correct_or_remove(setup):
    runtime, _ = setup
    runtime.application_service.corporation_knowledge().publish(
        "published", actor_id="owner", source_scope=MemoryScope.CONVERSATION,
        source_scope_id="chat", source_memory_id="memory", readers=["reader"], now=NOW, publication_opt_in=True)
    query = "scope=corporation&scope_id=corp_local&memory_id=published"
    with TestClient(application(runtime, Authentication(identity="reader"))) as client:
        detail = client.get("/api/memory/record?" + query)
        assert detail.status_code == 200
        assert detail.json()["can_manage"] is False
        body = dict(content="Changed", expires_at=(NOW + timedelta(hours=2)).isoformat(), retention_opt_in=True, revision=detail.json()["revision"])
        assert client.put("/api/memory/record?" + query, json=body).status_code == 403
        assert client.delete("/api/memory/record?" + query).status_code == 404
    with TestClient(application(runtime, Authentication())) as client:
        assert client.put("/api/memory/record?" + query, json=body).status_code == 409
        assert client.delete("/api/memory/record?" + query).status_code == 204


def test_corrupt_storage_is_a_service_failure_not_empty_success(setup):
    runtime, _ = setup
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE conversation_memory SET type='unknown'")
    finally:
        connection.close()
    with TestClient(application(runtime, Authentication())) as client:
        assert client.get("/api/memory?scope=conversation&scope_id=chat").status_code == 503
        assert client.get("/api/memory/record?" + QUERY).status_code == 503

def test_project_correction_preserves_verified_task_link(setup):
    runtime, _ = setup
    project = runtime.application_service.create_project("Project", "")
    task = runtime.application_service.create_task("Work", "Relevant", project.id, agent_id="local_worker")
    record = MemoryRecord("project-note", "owner", MemoryScope.PROJECT, project.id,
                          MemoryType.NOTE, "Original", task.id, NOW, NOW + timedelta(hours=1), True)
    runtime.application_service.project_knowledge().retain(record, now=NOW)
    query = f"scope=project&scope_id={project.id}&memory_id=project-note"
    with TestClient(application(runtime, Authentication())) as client:
        detail = client.get("/api/memory/record?" + query).json()
        body = dict(content="Corrected", expires_at=(NOW + timedelta(hours=2)).isoformat(), retention_opt_in=True, revision=detail["revision"])
        assert client.put("/api/memory/record?" + query, json=body).status_code == 200
        assert client.get("/api/memory/record?scope=project&scope_id=other&memory_id=project-note").status_code == 404
    loaded = create_corporation_runtime().application_service.project_knowledge().retrieve(
        "project-note", owner_id="owner", project_id=project.id, now=NOW)
    assert loaded.content == "Corrected"
    assert loaded.source_id == task.id


def test_corrupt_publication_provenance_is_service_failure(setup):
    runtime, _ = setup
    runtime.application_service.corporation_knowledge().publish(
        "published", actor_id="owner", source_scope=MemoryScope.CONVERSATION,
        source_scope_id="chat", source_memory_id="memory", readers=["reader"], now=NOW, publication_opt_in=True)
    connection = get_connection()
    try:
        with connection:
            connection.execute("DELETE FROM corporation_knowledge_provenance")
    finally:
        connection.close()
    with TestClient(application(runtime, Authentication(identity="reader"))) as client:
        assert client.get("/api/memory/record?scope=corporation&scope_id=corp_local&memory_id=published").status_code == 503
