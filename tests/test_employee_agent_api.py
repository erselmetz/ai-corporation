from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.orchestrator import Orchestrator, ProjectRegistry, TaskRegistry
from app.providers import ProviderRegistry


class EmployeeAgentTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "employee-reader": frozenset({"employee:read"}),
            "employee-manager": frozenset({"employee:manage"}),
            "agent-reader": frozenset({"agent:read"}),
            "other-reader": frozenset({"task:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(identity="test-user", permissions=permissions)


@pytest.fixture
def api_context():
    agents = AgentRegistry()
    agent = Agent(
        id="agent-1",
        name="Research Agent",
        role="Researcher",
        provider="local-provider",
        model="local-model",
        capabilities=["summarization", "classification"],
        permissions=["read_files"],
    )
    agents.register(agent)

    employees = EmployeeRegistry()
    employees.register(
        Employee(
            id="employee-1",
            name="Research Employee",
            role="Researcher",
            responsibilities=["Review reports"],
            agent=agent,
        )
    )

    orchestrator = Orchestrator(
        agents=agents,
        providers=ProviderRegistry(),
        tasks=TaskRegistry(),
        projects=ProjectRegistry(),
        employees=employees,
    )
    service = CorporationApplicationService(orchestrator)
    service.list_employees = MagicMock(wraps=service.list_employees)
    service.get_employee = MagicMock(wraps=service.get_employee)
    service.create_employee = MagicMock(wraps=service.create_employee)
    service.remove_employee = MagicMock(wraps=service.remove_employee)
    service.list_agents = MagicMock(wraps=service.list_agents)
    service.get_agent = MagicMock(wraps=service.get_agent)
    application = create_app(
        service,
        EmployeeAgentTestAuthenticationBackend(),
    )
    return application, service, agents, employees


@pytest.mark.parametrize(
    ("path", "permission"),
    [
        ("/api/employees", "employee:read"),
        ("/api/employees/employee-1", "employee:read"),
        ("/api/agents", "agent:read"),
        ("/api/agents/agent-1", "agent:read"),
    ],
)
def test_employee_and_agent_reads_require_authentication_and_permission(
    api_context,
    path: str,
    permission: str,
):
    application, _, _, _ = api_context
    wrong_permission = (
        "employee-reader" if permission == "agent:read" else "agent-reader"
    )

    with TestClient(application) as client:
        unauthenticated = client.get(path)
        forbidden = client.get(
            path,
            headers={"Authorization": wrong_permission},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403


def test_employee_read_endpoints_use_service_and_return_explicit_schemas(
    api_context,
):
    application, service, _, _ = api_context

    with TestClient(application) as client:
        collection = client.get(
            "/api/employees",
            headers={"Authorization": "employee-reader"},
        )
        detail = client.get(
            "/api/employees/employee-1",
            headers={"Authorization": "employee-reader"},
        )

    expected_employee = {
        "id": "employee-1",
        "name": "Research Employee",
        "role": "Researcher",
        "responsibilities": ["Review reports"],
        "agent_id": "agent-1",
    }
    assert collection.status_code == 200
    assert collection.json() == {"items": [expected_employee]}
    assert detail.status_code == 200
    assert detail.json() == expected_employee
    assert service.list_employees.call_count == 1
    assert service.get_employee.call_args.args == ("employee-1",)
    assert "agent" not in detail.json()
    assert "registry" not in detail.json()


def test_agent_read_endpoints_use_service_and_exclude_permissions(api_context):
    application, service, _, _ = api_context

    with TestClient(application) as client:
        collection = client.get(
            "/api/agents",
            headers={"Authorization": "agent-reader"},
        )
        detail = client.get(
            "/api/agents/agent-1",
            headers={"Authorization": "agent-reader"},
        )

    expected_agent = {
        "id": "agent-1",
        "name": "Research Agent",
        "role": "Researcher",
        "provider": "local-provider",
        "model": "local-model",
        "capabilities": ["summarization", "classification"],
    }
    assert collection.status_code == 200
    assert collection.json() == {"items": [expected_agent]}
    assert detail.status_code == 200
    assert detail.json() == expected_agent
    assert service.list_agents.call_count == 1
    assert service.get_agent.call_args.args == ("agent-1",)
    assert "permissions" not in detail.json()
    assert "registry" not in detail.json()


@pytest.mark.parametrize(
    ("path", "permission"),
    [
        ("/api/employees/unknown", "employee-reader"),
        ("/api/agents/unknown", "agent-reader"),
    ],
)
def test_unknown_employee_or_agent_returns_404(api_context, path, permission):
    application, _, _, _ = api_context

    with TestClient(application) as client:
        response = client.get(path, headers={"Authorization": permission})

    assert response.status_code == 404


def test_employee_management_uses_service_permissions_and_http_semantics(
    api_context,
):
    application, service, agents, employees = api_context

    with TestClient(application) as client:
        denied = client.post(
            "/api/employees",
            headers={"Authorization": "employee-reader"},
            json={
                "id": "employee-2",
                "name": "Operations Employee",
                "role": "Operations",
                "responsibilities": ["Coordinate work"],
            },
        )
        created = client.post(
            "/api/employees",
            headers={"Authorization": "employee-manager"},
            json={
                "id": "employee-2",
                "name": "Operations Employee",
                "role": "Operations",
                "responsibilities": ["Coordinate work"],
            },
        )
        duplicate = client.post(
            "/api/employees",
            headers={"Authorization": "employee-manager"},
            json={
                "id": "employee-2",
                "name": "Duplicate",
                "role": "Operations",
            },
        )
        invalid = client.post(
            "/api/employees",
            headers={"Authorization": "employee-manager"},
            json={"id": " ", "name": "Invalid", "role": "Operations"},
        )
        delete_denied = client.delete(
            "/api/employees/employee-2",
            headers={"Authorization": "employee-reader"},
        )
        deleted = client.delete(
            "/api/employees/employee-2",
            headers={"Authorization": "employee-manager"},
        )
        missing = client.delete(
            "/api/employees/unknown",
            headers={"Authorization": "employee-manager"},
        )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.json() == {
        "id": "employee-2",
        "name": "Operations Employee",
        "role": "Operations",
        "responsibilities": ["Coordinate work"],
        "agent_id": None,
    }
    assert duplicate.status_code == 409
    assert invalid.status_code == 422
    assert delete_denied.status_code == 403
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404
    assert service.create_employee.call_count == 2
    assert service.remove_employee.call_count == 2
    assert not employees.exists("employee-2")
    assert agents.exists("agent-1")


def test_agent_detail_application_service_returns_safe_summary(api_context):
    _, service, agents, _ = api_context

    summary = service.get_agent("agent-1")

    assert summary.id == agents.get("agent-1").id
    assert summary.capabilities == ("summarization", "classification")
    assert not hasattr(summary, "permissions")
    assert not hasattr(summary, "registry")
