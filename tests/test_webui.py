from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api import create_app
from app.application import CorporationApplicationService
from app.orchestrator import Orchestrator


def test_dashboard_shell_and_assets_are_served_without_runtime_execution():
    orchestrator = MagicMock(spec=Orchestrator)
    service = CorporationApplicationService(orchestrator)
    application = create_app(service)

    with TestClient(application) as client:
        shell = client.get("/ui")
        stylesheet = client.get("/ui/static/style.css")
        dashboard_script = client.get("/ui/static/dashboard.mjs")
        missing_asset = client.get("/ui/static/missing.css")
        protected_responses = [
            client.get(path)
            for path in (
                "/api/status",
                "/api/employees",
                "/api/agents",
                "/api/providers",
                "/api/models",
                "/api/tasks",
                "/api/projects",
                "/api/activity",
            )
        ]

    assert shell.status_code == 200
    assert shell.headers["content-type"].startswith("text/html")
    assert "ERSELMETZ AI CORPORATION" in shell.text
    assert "Corporation Web UI" in shell.text
    assert "Corporation dashboard" in shell.text
    assert "aria-label=\"Corporation navigation\"" in shell.text
    for section in (
        "Corporation overview",
        "Workforce overview",
        "Providers &amp; model assignments",
        "Tasks overview",
        "Projects overview",
        "Recent activity",
    ):
        assert section in shell.text

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert ".dashboard-grid" in stylesheet.text
    assert dashboard_script.status_code == 200
    assert dashboard_script.headers["content-type"].startswith("text/javascript")
    for endpoint in (
        "/api/status",
        "/api/employees",
        "/api/agents",
        "/api/providers",
        "/api/models",
        "/api/tasks",
        "/api/projects",
        "/api/activity?limit=8",
    ):
        assert endpoint in dashboard_script.text
    assert "Bearer " not in dashboard_script.text
    assert "api_key" not in dashboard_script.text.lower()
    assert "password" not in dashboard_script.text.lower()
    assert missing_asset.status_code == 404
    assert [response.status_code for response in protected_responses] == [401] * 8

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_employee_management_page_and_script_keep_employee_api_protected():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/employees")
        script = client.get("/ui/static/employees.mjs")
        dashboard = client.get("/ui")
        list_response = client.get("/api/employees")
        create_response = client.post(
            "/api/employees",
            json={
                "id": "employee-1",
                "name": "Example",
                "role": "Operator",
            },
        )
        delete_response = client.delete("/api/employees/employee-1")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "ERSELMETZ AI CORPORATION" in page.text
    assert "Employee Management" in page.text
    assert 'href="/ui"' in page.text
    assert 'src="/ui/static/employees.mjs"' in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert "/api/employees" in script.text
    assert "employee:read" not in script.text
    assert "employee:manage" not in script.text
    assert "Bearer " not in script.text
    assert "password" not in script.text.lower()
    assert "Employee management" in dashboard.text
    assert list_response.status_code == 401
    assert create_response.status_code == 401
    assert delete_response.status_code == 401

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []
