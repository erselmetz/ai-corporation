from fastapi.testclient import TestClient
import pytest

from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.corporation import BuiltinAgentProtected
from app.local import create_local_app
from app.runtime import create_corporation_runtime


PASSWORD = "agent-profile-test-password"
ORIGIN = "http://127.0.0.1:8000"


def client_for_runtime(runtime):
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    app.state.application_service = runtime.application_service
    app.state.capability_approval_service = CapabilityApprovalService(app.state.capability_authorization_service)
    client = TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 52100))
    assert client.post("/api/local/login", json={"password": PASSWORD},
                       headers={"Origin": ORIGIN}).status_code == 200
    csrf = client.get("/api/local/session").json()["csrf"]
    return client, {"Origin": ORIGIN, "X-Local-CSRF": csrf}


def test_builtin_profile_edit_pause_duplicate_reset_and_restart_persist():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    client, headers = client_for_runtime(runtime)
    agents = client.get("/api/agents", headers=headers).json()["items"]
    assert len(agents) == 6
    researcher = next(item for item in agents if item["id"] == "researcher")
    assert researcher["builtin"] is True
    assert "permissions" not in researcher and "system_prompt" not in researcher
    custom_response = client.post("/api/agents/researcher/duplicate", headers=headers,
                                  json={"new_id": "custom_researcher_1", "name": "My Researcher"})
    custom_summary = next(item for item in client.get("/api/agents", headers=headers).json()["items"]
                          if item["id"] == "custom_researcher_1")
    assert custom_response.status_code == 200
    assert custom_summary["builtin"] is False
    assert "permissions" not in custom_summary and "system_prompt" not in custom_summary
    researcher = client.get("/api/agents/researcher/profile", headers=headers).json()
    assert "web.research" in researcher["allowed_tools"]
    assert researcher["brain_scopes"] == ["owner"]
    edited = client.put("/api/agents/researcher/profile", headers=headers, json={
        "name": "Research lead", "role": "Researcher", "system_prompt": "Use approved sources.",
        "brain_scopes": ["owner"], "allowed_tools": ["brain.search", "web.research"],
        "permissions": ["brain:read", "web:retrieve"],
    })
    assert edited.status_code == 200
    assert edited.json()["name"] == "Research lead"
    assert client.put("/api/agents/developer/pause", headers=headers, json={"paused": True}).json()["paused"]
    duplicated = custom_response
    assert duplicated.status_code == 200
    assert duplicated.json()["builtin_key"] is None
    assert duplicated.json()["paused"] is False
    reset = client.post("/api/agents/researcher/reset", headers=headers, json={})
    assert reset.status_code == 200, reset.text
    assert reset.json()["name"] == "Researcher"
    with pytest.raises(BuiltinAgentProtected):
        runtime.application_service.remove_employee("local_employee")
    client.close()

    restarted = create_corporation_runtime(with_builtin_agent_team=True)
    assert restarted.agents.get("developer").paused is True
    assert restarted.agents.get("researcher").name == "Researcher"
    assert restarted.agents.get("custom_researcher_1").name == "My Researcher"
    assert restarted.employees.get("custom_employee_researcher_1").agent.id == "custom_researcher_1"


def test_profile_writes_require_owner_csrf_and_cannot_expand_scopes_or_permissions():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    app.state.capability_approval_service = CapabilityApprovalService(app.state.capability_authorization_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 52101)) as client:
        assert client.put("/api/agents/researcher/pause", json={"paused": True},
                          headers={"Origin": ORIGIN}).status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": ORIGIN, "X-Local-CSRF": csrf}
        no_csrf = client.put("/api/agents/researcher/pause", json={"paused": True},
                             headers={"Origin": ORIGIN})
        assert no_csrf.status_code == 403
        denied = client.put("/api/agents/researcher/profile", headers=headers, json={
            "name": "Researcher", "role": "Researcher", "system_prompt": "No broader access.",
            "brain_scopes": ["owner", "project"], "allowed_tools": ["brain.search"],
            "permissions": ["task:dispatch"],
        })
        assert denied.status_code == 409


def test_sage_core_requires_agent_and_chat_read_and_returns_only_real_trace_links():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    unauthenticated = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(unauthenticated, base_url=ORIGIN, client=("127.0.0.1", 52102)) as no_session:
        assert no_session.get("/api/local/agents/sage-core").status_code == 401
    limited = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    from app.api.security import AuthenticatedPrincipal
    class AgentOnlyBackend:
        def authenticate(self, _request):
            return AuthenticatedPrincipal("local-owner", frozenset({"agent:read"}), session_id="test-session")
    limited.state.authentication_backend = AgentOnlyBackend()
    with TestClient(limited, base_url=ORIGIN, client=("127.0.0.1", 52103)) as agent_only:
        assert agent_only.get("/api/local/agents/sage-core").status_code == 403
    client, headers = client_for_runtime(runtime)

    owner = client.get("/api/local/session").json()["identity"]
    conversation = runtime.application_service.owned_chat().start(owner, "local_worker")

    class RecordedTrace:
        def traces(self, actor, conversation_id, _now):
            assert actor == owner
            assert conversation_id == conversation["conversation"].id
            return {"reply-1": {
                "retrieved_at": "2026-10-21T00:00:00+00:00",
                "route": {"agent_id": "local_worker", "responder_agent_id": "researcher"},
                "handoff": {"status": "completed", "coordinator": {"id": "local_worker"},
                            "agent": {"id": "researcher"}},
                "sources": [{"memory_id": "brain-id", "source": "owner-note.md", "freshness": "current"}],
                "content": "private conversation text must not be returned",
            }}

    runtime.application_service.chat_knowledge = lambda: RecordedTrace()
    response = client.get("/api/local/agents/sage-core", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert {item["id"] for item in result["nodes"]} >= {"local_worker", "researcher"}
    assert result["handoffs"] == [{"id": f"{conversation['conversation'].id}:reply-1",
                                   "from": "local_worker", "to": "researcher",
                                   "state": "completed", "recorded_at": "2026-10-21T00:00:00+00:00"}]
    assert result["source_links"] == [{"id": f"{conversation['conversation'].id}:reply-1:brain-id",
                                       "agent_id": "researcher", "source_id": "brain-id",
                                       "label": "owner-note.md", "recorded_at": "2026-10-21T00:00:00+00:00"}]
    assert "content" not in response.text
    client.close()
