from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import app.application.services.corporation as corporation_service_module
import app.database.connection as database_connection
from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.database import initialize_database
from app.orchestrator import (
    Orchestrator,
    Project,
    ProjectRegistry,
    TaskRegistry,
)
from app.agents import AgentRegistry, EmployeeRegistry
from app.providers import ProviderRegistry


class ProjectTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "project-reader": frozenset({"project:read"}),
            "project-creator": frozenset({"project:create"}),
            "other-reader": frozenset({"task:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(identity="test-user", permissions=permissions)


@pytest.fixture
def project_api(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database_connection,
        "DATABASE_PATH",
        tmp_path / "ai_corporation.db",
    )
    initialize_database()

    projects = ProjectRegistry()
    projects.register(
        Project(
            id="project-1",
            name="Existing Project",
            description="Persisted project",
        )
    )
    orchestrator = Orchestrator(
        agents=AgentRegistry(),
        providers=ProviderRegistry(),
        tasks=TaskRegistry(),
        projects=projects,
        employees=EmployeeRegistry(),
    )
    orchestrator.create_task = MagicMock(
        side_effect=AssertionError("Project API must not create tasks")
    )
    orchestrator.execute_task = MagicMock(
        side_effect=AssertionError("Project API must not execute tasks")
    )
    service = CorporationApplicationService(orchestrator)
    for method in ("list_projects", "get_project", "create_project"):
        setattr(
            service,
            method,
            MagicMock(wraps=getattr(service, method)),
        )
    application = create_app(service, ProjectTestAuthenticationBackend())
    return application, service, orchestrator, projects


def test_project_list_requires_auth_and_project_read_permission(project_api):
    application, service, _, _ = project_api

    with TestClient(application) as client:
        unauthenticated = client.get("/api/projects")
        forbidden = client.get(
            "/api/projects",
            headers={"Authorization": "other-reader"},
        )
        response = client.get(
            "/api/projects",
            headers={"Authorization": "project-reader"},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "project-1",
                "name": "Existing Project",
                "description": "Persisted project",
                "status": "active",
            }
        ]
    }
    assert set(response.json()["items"][0]) == {
        "id",
        "name",
        "description",
        "status",
    }
    service.list_projects.assert_called_once_with()
    assert "registry" not in response.json()["items"][0]


def test_project_detail_returns_summary_and_missing_project_is_404(project_api):
    application, service, _, _ = project_api

    with TestClient(application) as client:
        response = client.get(
            "/api/projects/project-1",
            headers={"Authorization": "project-reader"},
        )
        missing = client.get(
            "/api/projects/missing",
            headers={"Authorization": "project-reader"},
        )
        forbidden = client.get(
            "/api/projects/project-1",
            headers={"Authorization": "other-reader"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": "project-1",
        "name": "Existing Project",
        "description": "Persisted project",
        "status": "active",
    }
    assert missing.status_code == 404
    assert forbidden.status_code == 403
    assert service.get_project.call_args_list == [
        call("project-1"),
        call("missing"),
    ]


def test_project_creation_uses_service_generated_id_and_existing_persistence(
    project_api,
):
    application, service, orchestrator, projects = project_api

    with TestClient(application) as client:
        forbidden = client.post(
            "/api/projects",
            headers={"Authorization": "project-reader"},
            json={"name": "New Project"},
        )
        created = client.post(
            "/api/projects",
            headers={"Authorization": "project-creator"},
            json={
                "name": "New Project",
                "description": "Created through the API",
            },
        )

    assert forbidden.status_code == 403
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert project_id.startswith("PROJECT-")
    assert created.json() == {
        "id": project_id,
        "name": "New Project",
        "description": "Created through the API",
        "status": "active",
    }
    service.create_project.assert_called_once_with(
        name="New Project",
        description="Created through the API",
    )
    assert projects.get(project_id).id == project_id
    assert ProjectRegistry().get(project_id).name == "New Project"
    orchestrator.create_task.assert_not_called()
    orchestrator.execute_task.assert_not_called()
    assert orchestrator.tasks.all() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " "},
        {"name": "Valid name", "id": "client-controlled"},
        {"name": "Valid name", "status": "completed"},
    ],
)
def test_project_creation_rejects_invalid_or_internal_fields(project_api, payload):
    application, service, _, _ = project_api

    with TestClient(application) as client:
        response = client.post(
            "/api/projects",
            headers={"Authorization": "project-creator"},
            json=payload,
        )

    assert response.status_code == 422
    service.create_project.assert_not_called()


def test_project_create_maps_registry_conflict_to_409(project_api, monkeypatch):
    application, service, _, projects = project_api
    conflict_id = "PROJECT-DEADBEEF"
    projects.register(
        Project(
            id=conflict_id,
            name="Conflicting Project",
        )
    )
    monkeypatch.setattr(
        corporation_service_module,
        "uuid4",
        lambda: SimpleNamespace(hex="DEADBEEF"),
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/projects",
            headers={"Authorization": "project-creator"},
            json={"name": "New Project"},
        )

    assert response.status_code == 409
    assert service.create_project.call_count == 1
