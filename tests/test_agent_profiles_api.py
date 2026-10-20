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
    assert "permissions" not in researcher and "system_prompt" not in researcher
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
    duplicated = client.post("/api/agents/researcher/duplicate", headers=headers,
                             json={"new_id": "custom_researcher_1", "name": "My Researcher"})
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
