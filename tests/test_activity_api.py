from unittest.mock import MagicMock, call

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import app.database.connection as database_connection
from app.agents import AgentRegistry, EmployeeRegistry
from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.database import TaskLogger, initialize_database
from app.orchestrator import Orchestrator, Project, ProjectRegistry, TaskRegistry
from app.providers import ProviderRegistry


class ActivityTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "activity-reader": frozenset({"activity:read"}),
            "task-reader": frozenset({"task:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(identity="test-user", permissions=permissions)


@pytest.fixture
def activity_api(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database_connection,
        "DATABASE_PATH",
        tmp_path / "ai_corporation.db",
    )
    initialize_database()
    projects = ProjectRegistry()
    projects.register(Project(id="project-1", name="Test Project"))
    tasks = TaskRegistry()
    orchestrator = Orchestrator(
        agents=AgentRegistry(),
        providers=ProviderRegistry(),
        tasks=tasks,
        projects=projects,
        employees=EmployeeRegistry(),
    )
    orchestrator.create_task = MagicMock(
        wraps=orchestrator.create_task,
    )
    orchestrator.execute_task = MagicMock(
        side_effect=AssertionError("Activity API must not execute tasks")
    )
    service = CorporationApplicationService(orchestrator)
    service.list_activity = MagicMock(wraps=service.list_activity)
    application = create_app(service, ActivityTestAuthenticationBackend())
    return application, service, orchestrator


def test_activity_list_requires_auth_and_exposes_only_safe_schema(activity_api):
    application, service, orchestrator = activity_api
    task = orchestrator.create_task(
        title="Create an activity",
        description="Generate existing core activity",
        project_id="project-1",
        agent_id=None,
    )
    orchestrator.logger.log(task.id, "TASK_FAILED", "Sensitive internal detail")

    with TestClient(application) as client:
        unauthenticated = client.get("/api/activity")
        forbidden = client.get(
            "/api/activity",
            headers={"Authorization": "task-reader"},
        )
        response = client.get(
            "/api/activity",
            headers={"Authorization": "activity-reader"},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert [item["event"] for item in response.json()["items"]] == [
        "TASK_FAILED",
        "TASK_CREATED",
    ]
    assert response.json()["items"][0]["id"] > 0
    assert response.json()["items"][0]["task_id"] == task.id
    assert response.json()["items"][0]["event"] == "TASK_FAILED"
    assert response.json()["items"][0]["created_at"]
    assert set(response.json()["items"][0]) == {
        "id",
        "task_id",
        "event",
        "created_at",
    }
    assert "Sensitive internal detail" not in response.text
    assert "message" not in response.json()["items"][0]
    service.list_activity.assert_called_once_with(limit=100, task_id=None)


def test_activity_filters_by_task_and_obeys_bounded_limit(activity_api):
    application, service, orchestrator = activity_api
    first = orchestrator.create_task(
        title="First task",
        description="First task activity",
        project_id="project-1",
    )
    second = orchestrator.create_task(
        title="Second task",
        description="Second task activity",
        project_id="project-1",
    )

    with TestClient(application) as client:
        bounded = client.get(
            "/api/activity?limit=1",
            headers={"Authorization": "activity-reader"},
        )
        filtered = client.get(
            f"/api/activity?task_id={first.id}",
            headers={"Authorization": "activity-reader"},
        )
        too_small = client.get(
            "/api/activity?limit=0",
            headers={"Authorization": "activity-reader"},
        )
        too_large = client.get(
            "/api/activity?limit=101",
            headers={"Authorization": "activity-reader"},
        )

    assert bounded.status_code == 200
    assert len(bounded.json()["items"]) == 1
    assert bounded.json()["items"][0]["task_id"] == second.id
    assert filtered.status_code == 200
    assert [item["task_id"] for item in filtered.json()["items"]] == [first.id]
    assert too_small.status_code == 422
    assert too_large.status_code == 422
    assert service.list_activity.call_args_list == [
        call(limit=1, task_id=None),
        call(limit=100, task_id=first.id),
    ]


def test_activity_reads_are_read_only_and_no_mutation_routes_exist(activity_api):
    application, _, orchestrator = activity_api
    task = orchestrator.create_task(
        title="Read-only activity",
        description="Verify no mutation",
        project_id="project-1",
    )
    before = orchestrator.logger.get_task_logs(task.id)

    with TestClient(application) as client:
        get_response = client.get(
            "/api/activity",
            headers={"Authorization": "activity-reader"},
        )
        post_response = client.post("/api/activity")
        put_response = client.put("/api/activity")
        delete_response = client.delete("/api/activity")

    after = orchestrator.logger.get_task_logs(task.id)
    assert get_response.status_code == 200
    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405
    assert after == before
    orchestrator.execute_task.assert_not_called()
    paths = application.openapi()["paths"]
    assert set(paths["/api/activity"]) == {"get"}
    assert "/api/activity/{log_id}" not in paths


def test_application_service_reads_existing_task_logger_without_registry_access(
    activity_api,
):
    _, service, orchestrator = activity_api
    task = orchestrator.create_task(
        title="Service boundary",
        description="Test application service",
        project_id="project-1",
    )

    summaries = service.list_activity(task_id=task.id)

    assert len(summaries) == 1
    assert summaries[0].event == "TASK_CREATED"
    assert not hasattr(summaries[0], "message")
    assert not hasattr(summaries[0], "registry")
    assert isinstance(orchestrator.logger, TaskLogger)
