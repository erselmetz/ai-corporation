from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi.testclient import TestClient

from app.agents import Agent
from app.api import AuthenticatedPrincipal, create_app
from app.api.memory import get_memory_now
from app.application.services.knowledge_proposals import (
    KnowledgeProposalConflict,
    KnowledgeProposalService,
)
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)
SOURCE_ID = "retained-source"
SOURCE_TEXT = "The database is backed up every Friday. The owner reviews each recovery test."


class Auth:
    def __init__(self, permissions=frozenset({"memory:manage"})):
        self.permissions = permissions

    def authenticate(self, _request):
        return AuthenticatedPrincipal("owner", self.permissions)


def setup():
    runtime = create_corporation_runtime()
    source = MemoryRecord(SOURCE_ID, "owner", MemoryScope.CONVERSATION, "chat",
                          MemoryType.NOTE, SOURCE_TEXT, "message-source", NOW,
                          NOW + timedelta(days=2), True)
    ConversationMemoryStore().retain(source, now=NOW)
    generated = json.dumps({
        "content": "Backups run weekly and recovery tests receive owner review.",
        "claims": [
            {"claim": "Backups run weekly.", "excerpt": "The database is backed up every Friday."},
            {"claim": "The owner reviews recovery tests.", "excerpt": "The owner reviews each recovery test."},
        ],
    })
    prompts = []
    runtime.application_service.generate_local_knowledge_proposal = (
        lambda agent_id, prompt: prompts.append((agent_id, prompt)) or generated
    )
    service = KnowledgeProposalService(runtime.application_service, clock=lambda: NOW)
    runtime.application_service.knowledge_proposals = lambda: service
    app = create_app(runtime.application_service, Auth())
    app.dependency_overrides[get_memory_now] = lambda: NOW
    return runtime, app, service, prompts, source


def test_proposal_is_local_owner_selected_revision_bound_and_rejectable():
    runtime, app, proposals, prompts, source = setup()
    proposal = proposals.prepare("owner", source.scope, source.scope_id, source.id, "local_worker")
    assert proposal["source_revision"]
    assert proposal["destination_scope"] == "conversation"
    assert proposal["destination_scope_id"] == "chat"
    assert (proposal["provider_id"], proposal["model_id"]) == ("ollama", "llama3.2:3b")
    assert proposal["claims"][0]["excerpt"] in SOURCE_TEXT
    assert proposal["confidence_limit"] == proposals.CONFIDENCE_LIMIT
    assert "untrusted evidence" in prompts[0][1]
    assert prompts[0][0] == "local_worker"
    rejected = proposals.decide("owner", proposal["proposal_id"],
                                proposal_digest=proposal["proposal_digest"],
                                decision="reject")
    assert rejected["retained"] is False
    assert ConversationMemoryStore().retrieve(
        source.id, owner_id="owner", conversation_id="chat", now=NOW) == source


def test_acceptance_retains_exact_proposal_in_same_private_scope():
    runtime, app, proposals, _, source = setup()
    proposal = proposals.prepare("owner", source.scope, source.scope_id, source.id, "local_worker")
    accepted = proposals.decide("owner", proposal["proposal_id"],
                                proposal_digest=proposal["proposal_digest"], decision="accept")
    saved = ConversationMemoryStore().retrieve(
        accepted["memory_id"], owner_id="owner", conversation_id="chat", now=NOW)
    assert accepted["retained"] is True
    assert saved.content == proposal["content"]
    assert saved.type is MemoryType.SUMMARY
    assert saved.scope is source.scope and saved.scope_id == source.scope_id
    assert saved.source_id == source.source_id
    assert saved.expires_at == source.expires_at


def test_project_memory_proposal_keeps_the_existing_project_task_link():
    runtime, app, proposals, _, _ = setup()
    project = runtime.application_service.create_project("Knowledge proposal test")
    task = runtime.application_service.create_task(
        "Source task", "Existing source link", project.id, agent_id="local_worker")
    source = MemoryRecord("project-source", "owner", MemoryScope.PROJECT, project.id,
                          MemoryType.NOTE, SOURCE_TEXT, task.id, NOW,
                          NOW + timedelta(days=1), True)
    runtime.application_service.project_knowledge().retain(source, now=NOW)
    proposal = proposals.prepare("owner", source.scope, source.scope_id,
                                 source.id, "local_worker")
    accepted = proposals.decide("owner", proposal["proposal_id"],
                                proposal_digest=proposal["proposal_digest"], decision="accept")
    saved = runtime.application_service.project_knowledge().retrieve(
        accepted["memory_id"], owner_id="owner", project_id=project.id, now=NOW)
    assert saved.content == proposal["content"]
    assert saved.scope is MemoryScope.PROJECT and saved.scope_id == project.id
    assert saved.source_id == task.id


def test_changed_source_revision_blocks_acceptance_without_writing():
    runtime, app, proposals, _, source = setup()
    proposal = proposals.prepare("owner", source.scope, source.scope_id, source.id, "local_worker")
    runtime.application_service.memory_management().update(
        source.id, actor_id="owner", scope=source.scope, scope_id=source.scope_id,
        revision=proposal["source_revision"], content="Changed by owner",
        expires_at=source.expires_at, retention_opt_in=True, now=NOW)
    with pytest.raises(KnowledgeProposalConflict, match="Source changed"):
        proposals.decide("owner", proposal["proposal_id"],
                         proposal_digest=proposal["proposal_digest"], decision="accept")
    listing = ConversationMemoryStore().list_scoped(actor_id="owner", scope_id="chat", limit=10)
    assert len(listing) == 1


def test_generated_claims_must_cite_exact_source_and_api_is_permission_gated():
    runtime, app, proposals, _, source = setup()
    runtime.application_service.generate_local_knowledge_proposal = (
        lambda _agent, _prompt: json.dumps({
            "content": "Unsupported claim", "claims": [
                {"claim": "There are daily backups.", "excerpt": "There are daily backups."}
            ]
        })
    )
    with pytest.raises(ValueError, match="exact source excerpt"):
        proposals.prepare("owner", source.scope, source.scope_id, source.id, "local_worker")

    denied = create_app(runtime.application_service, Auth(frozenset({"memory:read"})))
    denied.dependency_overrides[get_memory_now] = lambda: NOW
    with TestClient(denied) as client:
        response = client.post("/api/memory/proposals", json={
            "scope": "conversation", "scope_id": "chat", "memory_id": SOURCE_ID,
            "agent_id": "local_worker",
        })
    assert response.status_code == 403


def test_proposal_api_requires_explicit_owner_decision_and_preserves_auth_fail_closed():
    runtime, app, proposals, _, source = setup()
    with TestClient(app) as client:
        proposal_response = client.post("/api/memory/proposals", json={
            "scope": "conversation", "scope_id": "chat", "memory_id": SOURCE_ID,
            "agent_id": "local_worker",
        })
        proposal = proposal_response.json()
        accepted = client.post(
            f"/api/memory/proposals/{proposal['proposal_id']}/decision",
            json={"proposal_digest": proposal["proposal_digest"], "decision": "accept"},
        )
    assert proposal_response.status_code == 200
    assert accepted.status_code == 200 and accepted.json()["retained"] is True

    fail_closed = create_app(runtime.application_service)
    with TestClient(fail_closed) as client:
        denied = client.post("/api/memory/proposals", json={
            "scope": "conversation", "scope_id": "chat", "memory_id": SOURCE_ID,
            "agent_id": "local_worker",
        })
    assert denied.status_code == 401


def test_application_generation_uses_pinned_loopback_ollama_assignment_only():
    runtime = create_corporation_runtime()
    calls = []
    runtime.orchestrator.run_agent = lambda agent_id, prompt, *, expected_assignment: (
        calls.append((agent_id, prompt, expected_assignment)) or '{"content":"ok","claims":[]}')
    result = runtime.application_service.generate_local_knowledge_proposal(
        "local_worker", '{"source_text":"untrusted"}')
    assert json.loads(result)["content"] == "ok"
    assert calls == [("local_worker", '{"source_text":"untrusted"}', ("ollama", "llama3.2:3b"))]
    with pytest.raises(ValueError):
        runtime.application_service.generate_local_knowledge_proposal(
            "missing-agent", "source")
    assert len(calls) == 1
    runtime.agents.register(Agent(
        id="cloud-agent", name="Cloud Agent", role="Writer", provider="gemini",
        model="cloud-model"))
    with pytest.raises(ValueError, match="configured loopback Ollama"):
        runtime.application_service.generate_local_knowledge_proposal(
            "cloud-agent", "source")
    assert len(calls) == 1
