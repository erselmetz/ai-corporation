from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.local import create_local_app
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
from app.providers import OllamaProvider
from app.runtime.factory import create_corporation_runtime

ORIGIN = "http://127.0.0.1:8000"
PASSWORD = "test-only-owner-passphrase"


def _proposal_body(message_id, project_id, **updates):
    body = {
        "source_message_id": message_id,
        "objective": "Prepare a reviewed project report",
        "project_id": project_id,
        "agent_id": "local_worker",
        "expected_outcome": "A report meeting the requested scope",
        "verification_method": "The owner reviews the saved report",
        "expected_evidence": "A review record linked to the report",
    }
    body.update(updates)
    return body


def _login(client):
    assert client.post(
        "/api/local/login",
        json={"password": PASSWORD},
        headers={"Origin": ORIGIN},
    ).status_code == 200
    session = client.get("/api/local/session").json()
    headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}
    return session, headers


def _start_chat(client, headers):
    started = client.post(
        "/api/chat/conversations",
        json={"agent_id": "local_worker"},
        headers=headers,
    )
    assert started.status_code == 200
    identifier = started.json()["conversation"]["id"]
    sent = client.post(
        f"/api/chat/conversations/{identifier}/messages",
        json={"text": "Please propose a scoped report."},
        headers=headers,
    )
    assert sent.status_code == 200
    source = next(
        message for message in sent.json()["conversation"]["messages"]
        if message["role"] == "assistant" and message["status"] == "completed"
    )
    return identifier, source["id"]


def test_reviewed_owner_proposal_creates_one_pending_task_without_provider_execution(
    monkeypatch,
):
    provider_calls = []
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda *args, **kwargs: provider_calls.append((args, kwargs)) or "Coordinator proposal.",
    )
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Reviewed project", "")
    app = create_local_app(
        password=PASSWORD,
        application_service=runtime.application_service,
    )
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        session, headers = _login(client)
        assert "chat-task:create" in session["permissions"]
        assert "task:create" not in session["permissions"]
        conversation_id, message_id = _start_chat(client, headers)

        now = datetime.now(timezone.utc)
        ConversationMemoryStore().retain(
            MemoryRecord(
                "scope-note",
                "local-owner",
                MemoryScope.CONVERSATION,
                conversation_id,
                MemoryType.NOTE,
                "Approved scope includes a report for the project owner.",
                "source-record",
                now,
                now + timedelta(hours=1),
                True,
            ),
            now=now,
        )
        body = _proposal_body(
            message_id,
            project.id,
            context_query="approved scope report",
            context_scope="conversation",
            context_scope_id=conversation_id,
        )
        before = len(runtime.tasks.all())
        response = client.post(
            f"/api/chat/conversations/{conversation_id}/task-proposals",
            json=body,
            headers=headers,
        )
        assert response.status_code == 200, response.text
        proposal = response.json()
        assert proposal["objective"] == body["objective"]
        assert proposal["confirmation_identity"] == "local-owner"
        assert proposal["responsible_agent"]["id"] == "local_worker"
        assert proposal["authorized_context"]["hits"][0]["content"].startswith("Approved scope")
        assert proposal["outcome"]["expected_evidence"] == body["expected_evidence"]
        assert proposal["task"]["title"] == body["objective"]
        assert len(runtime.tasks.all()) == before

        confirm_url = (
            f"/api/chat/conversations/{conversation_id}/task-proposals/"
            f"{proposal['proposal_id']}/confirm"
        )
        mismatch = client.post(
            confirm_url,
            json={"proposal_digest": "0" * 64, "confirmed": True},
            headers=headers,
        )
        assert mismatch.status_code == 409
        confirmed = client.post(
            confirm_url,
            json={
                "proposal_digest": proposal["proposal_digest"],
                "confirmed": True,
            },
            headers=headers,
        )
        assert confirmed.status_code == 200
        result = confirmed.json()
        assert result["status"] == "pending"
        assert result["confirmed_by"] == "local-owner"
        task = runtime.application_service.get_task(result["task_id"])
        assert task.status == "pending"
        assert task.assigned_agent == "local_worker"
        assert "Expected evidence:" + " " + body["expected_evidence"] in task.description
        assert "scope-note" in task.description
        assert len(runtime.tasks.all()) == before + 1
        assert len(provider_calls) == 1

        replay = client.post(
            confirm_url,
            json={
                "proposal_digest": proposal["proposal_digest"],
                "confirmed": True,
            },
            headers=headers,
        )
        assert replay.status_code == 404
        duplicate = client.post(
            f"/api/chat/conversations/{conversation_id}/task-proposals",
            json=body,
            headers=headers,
        )
        assert duplicate.status_code == 409
        assert len(runtime.tasks.all()) == before + 1
        generic_task_creation = client.post(
            "/api/tasks",
            json={"title": "Unreviewed", "description": "No", "project_id": project.id},
            headers=headers,
        )
        assert generic_task_creation.status_code == 403
        assert len(provider_calls) == 1


def test_closed_conversation_makes_a_prepared_proposal_stale_without_creation(monkeypatch):
    monkeypatch.setattr(OllamaProvider, "generate", lambda *args, **kwargs: "Proposal.")
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        _, headers = _login(client)
        conversation_id, message_id = _start_chat(client, headers)
        proposal_response = client.post(
            f"/api/chat/conversations/{conversation_id}/task-proposals",
            json=_proposal_body(message_id, project.id),
            headers=headers,
        )
        assert proposal_response.status_code == 200, proposal_response.text
        proposal = proposal_response.json()
        assert client.post(
            f"/api/chat/conversations/{conversation_id}/close",
            json={},
            headers=headers,
        ).status_code == 200
        confirmed = client.post(
            f"/api/chat/conversations/{conversation_id}/task-proposals/"
            f"{proposal['proposal_id']}/confirm",
            json={"proposal_digest": proposal["proposal_digest"], "confirmed": True},
            headers=headers,
        )
        assert confirmed.status_code == 409
        assert runtime.tasks.all() == []


def test_proposal_routes_require_the_narrow_confirmation_permission():
    class Reader:
        def authenticate(self, _request):
            return AuthenticatedPrincipal("reader", frozenset({"chat:read"}))

    runtime = create_corporation_runtime()
    app = create_app(
        application_service=runtime.application_service,
        authentication_backend=Reader(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/conversations/conversation/task-proposals",
            json=_proposal_body("message", "project"),
        )
        assert response.status_code == 403
        assert runtime.tasks.all() == []


def test_proposals_cannot_cross_owner_scope_or_project_context_scope(monkeypatch):
    monkeypatch.setattr(OllamaProvider, "generate", lambda *args, **kwargs: "Proposal.")
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        _, headers = _login(client)
        conversation_id, message_id = _start_chat(client, headers)
        backend = client.app.state.authentication_backend
        owner = backend.principal
        backend.principal = AuthenticatedPrincipal("other-owner", owner.permissions)
        denied = client.post(
            f"/api/chat/conversations/{conversation_id}/task-proposals",
            json=_proposal_body(message_id, project.id),
            headers=headers,
        )
        assert denied.status_code == 404
        backend.principal = owner

        mismatched_scope = client.post(
            f"/api/chat/conversations/{conversation_id}/task-proposals",
            json=_proposal_body(
                message_id,
                project.id,
                context_query="approved",
                context_scope=MemoryScope.PROJECT.value,
                context_scope_id="different-project",
            ),
            headers=headers,
        )
        assert mismatched_scope.status_code == 422
        assert runtime.tasks.all() == []
