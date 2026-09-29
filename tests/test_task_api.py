from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.orchestrator import (
    Orchestrator,
    Project,
    ProjectRegistry,
    TaskRegistry,
    TaskStatus,
)
from app.providers import AIProvider, ProviderRegistry


class TaskTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "task-reader": frozenset({"task:read"}),
            "task-creator": frozenset({"task:create"}),
            "other-reader": frozenset({"agent:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(identity="test-user", permissions=permissions)


@pytest.fixture
def task_api():
    agents = AgentRegistry()
    agent = Agent(
        id="research-agent",
        name="Research Agent",
        role="Researcher",
        provider="test-provider",
        model="test-model",
        capabilities=["research"],
    )
    agents.register(agent)
    employees = EmployeeRegistry()
    employees.register(
        Employee(
            id="research-employee",
            name="Research Employee",
            role="Researcher",
            agent=agent,
        )
    )

    provider_registry = ProviderRegistry()
    provider = MagicMock(spec=AIProvider)
    provider.generate.side_effect = AssertionError(
        "Task API must not execute the provider"
    )
    provider_registry.register("test-provider", provider)
    projects = ProjectRegistry()
    projects.register(
        Project(
            id="project-1",
            name="Test Project",
            description="Local test project",
        )
    )
    tasks = TaskRegistry()
    orchestrator = Orchestrator(
        agents=agents,
        providers=provider_registry,
        tasks=tasks,
        projects=projects,
        employees=employees,
    )
    service = CorporationApplicationService(orchestrator)
    for method in ("list_tasks", "get_task", "create_task", "dry_run_task"):
        setattr(
            service,
            method,
            MagicMock(wraps=getattr(service, method)),
        )
    application = create_app(
        service,
        TaskTestAuthenticationBackend(),
    )
    return application, service, orchestrator, tasks, provider


def test_task_read_endpoints_require_authentication_and_read_permission(task_api):
    application, _, _, _, _ = task_api

    with TestClient(application) as client:
        unauthenticated = client.get("/api/tasks")
        forbidden = client.get(
            "/api/tasks",
            headers={"Authorization": "other-reader"},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403


def test_list_and_get_tasks_use_application_service_and_explicit_schema(task_api):
    application, service, _, _, _ = task_api
    with TestClient(application) as client:
        created = client.post(
            "/api/tasks",
            headers={"Authorization": "task-creator"},
            json={
                "title": "Research topic",
                "description": "Review source material",
                "project_id": "project-1",
                "role": "Researcher",
            },
        )
        collection = client.get(
            "/api/tasks",
            headers={"Authorization": "task-reader"},
        )
        detail = client.get(
            f"/api/tasks/{created.json()['id']}",
            headers={"Authorization": "task-reader"},
        )

    assert created.status_code == 201
    expected_task = {
        "id": created.json()["id"],
        "title": "Research topic",
        "description": "Review source material",
        "project_id": "project-1",
        "status": "pending",
        "assigned_agent": None,
        "required_role": "Researcher",
        "required_capability": None,
    }
    assert collection.status_code == 200
    assert collection.json() == {"items": [expected_task]}
    assert detail.status_code == 200
    assert detail.json() == expected_task
    assert service.list_tasks.call_count == 1
    service.get_task.assert_called_once_with(created.json()["id"])
    assert "registry" not in detail.json()
    assert "result" not in detail.json()
    assert "error" not in detail.json()


def test_unknown_task_returns_404(task_api):
    application, service, _, _, _ = task_api

    with TestClient(application) as client:
        response = client.get(
            "/api/tasks/not-a-task",
            headers={"Authorization": "task-reader"},
        )

    assert response.status_code == 404
    service.get_task.assert_called_once_with("not-a-task")


def test_task_creation_uses_service_and_core_generated_identity(task_api):
    application, service, _, tasks, _ = task_api

    with TestClient(application) as client:
        denied = client.post(
            "/api/tasks",
            headers={"Authorization": "task-reader"},
            json={
                "title": "Create task",
                "description": "Create through core",
                "project_id": "project-1",
            },
        )
        created = client.post(
            "/api/tasks",
            headers={"Authorization": "task-creator"},
            json={
                "title": "Create task",
                "description": "Create through core",
                "project_id": "project-1",
                "capability": "research",
            },
        )

    assert denied.status_code == 403
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert task_id.startswith("TASK-")
    assert task_id == tasks.get(task_id).id
    assert created.json() == {
        "id": task_id,
        "title": "Create task",
        "description": "Create through core",
        "project_id": "project-1",
        "status": "pending",
        "assigned_agent": None,
        "required_role": None,
        "required_capability": "research",
    }
    assert service.create_task.call_count == 1
    service.create_task.assert_called_once_with(
        title="Create task",
        description="Create through core",
        project_id="project-1",
        agent_id=None,
        role=None,
        capability="research",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "title": " ",
            "description": "Description",
            "project_id": "project-1",
        },
        {
            "title": "Title",
            "description": "Description",
            "project_id": "project-1",
            "status": "completed",
        },
    ],
)
def test_task_creation_rejects_invalid_or_internal_fields(task_api, payload):
    application, service, _, _, _ = task_api

    with TestClient(application) as client:
        response = client.post(
            "/api/tasks",
            headers={"Authorization": "task-creator"},
            json=payload,
        )

    assert response.status_code == 422
    service.create_task.assert_not_called()


def test_task_creation_maps_existing_domain_validation(task_api):
    application, service, _, _, _ = task_api

    with TestClient(application) as client:
        missing_project = client.post(
            "/api/tasks",
            headers={"Authorization": "task-creator"},
            json={
                "title": "No project",
                "description": "Project does not exist",
                "project_id": "unknown",
            },
        )
        conflicting_routes = client.post(
            "/api/tasks",
            headers={"Authorization": "task-creator"},
            json={
                "title": "Invalid route",
                "description": "Two mutually exclusive routes",
                "project_id": "project-1",
                "role": "Researcher",
                "capability": "research",
            },
        )

    assert missing_project.status_code == 404
    assert conflicting_routes.status_code == 400
    assert service.create_task.call_count == 2


def test_dry_run_is_read_authorized_and_does_not_mutate_or_execute(task_api):
    application, service, orchestrator, tasks, provider = task_api
    task = service.create_task(
        title="Dry-run task",
        description="Route without execution",
        project_id="project-1",
        role="Researcher",
    )
    initial = tasks.get(task.id)
    initial_state = (
        initial.status,
        initial.assigned_agent,
        initial.result,
        initial.error,
    )

    with TestClient(application) as client:
        denied = client.post(
            f"/api/tasks/{task.id}/dry-run",
            headers={"Authorization": "other-reader"},
        )
        preview = client.post(
            f"/api/tasks/{task.id}/dry-run",
            headers={"Authorization": "task-reader"},
        )
        missing = client.post(
            "/api/tasks/unknown/dry-run",
            headers={"Authorization": "task-reader"},
        )

    assert denied.status_code == 403
    assert preview.status_code == 200
    assert preview.json() == {
        "task_id": task.id,
        "task_title": "Dry-run task",
        "task_description": "Route without execution",
        "selected_agent_id": "research-agent",
        "selected_agent_name": "Research Agent",
        "selected_agent_role": "Researcher",
        "selected_employee_id": "research-employee",
        "selected_employee_name": "Research Employee",
        "provider": "test-provider",
        "model": "test-model",
        "routing_method": "employee_role",
        "status": "ready",
    }
    assert missing.status_code == 404
    service.dry_run_task.assert_any_call(task.id)
    after = tasks.get(task.id)
    assert (
        after.status,
        after.assigned_agent,
        after.result,
        after.error,
    ) == initial_state
    assert after.status is TaskStatus.PENDING
    orchestrator.run_agent = MagicMock(
        side_effect=AssertionError("Dry-run must not execute an agent")
    )
    provider.generate.assert_not_called()


def test_unroutable_dry_run_returns_400_without_execution(task_api):
    application, service, orchestrator, tasks, _ = task_api
    task = service.create_task(
        title="Unroutable task",
        description="No routing fields",
        project_id="project-1",
    )
    original_status = tasks.get(task.id).status
    orchestrator.run_agent = MagicMock(
        side_effect=AssertionError("Dry-run must not execute an agent")
    )

    with TestClient(application) as client:
        response = client.post(
            f"/api/tasks/{task.id}/dry-run",
            headers={"Authorization": "task-reader"},
        )

    assert response.status_code == 400
    assert tasks.get(task.id).status is original_status is TaskStatus.PENDING
    orchestrator.run_agent.assert_not_called()
