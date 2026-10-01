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
