from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api import create_app
from app.application import CorporationApplicationService
from app.orchestrator import Orchestrator


def test_web_ui_shell_and_static_css_are_served_without_runtime_execution():
    orchestrator = MagicMock(spec=Orchestrator)
    service = CorporationApplicationService(orchestrator)
    application = create_app(service)

    with TestClient(application) as client:
        shell = client.get("/ui")
        stylesheet = client.get("/ui/static/style.css")
        missing_asset = client.get("/ui/static/missing.css")
        protected_status = client.get("/api/status")

    assert shell.status_code == 200
    assert shell.headers["content-type"].startswith("text/html")
    assert "ERSELMETZ AI CORPORATION" in shell.text
    assert "Web UI" in shell.text
    assert "aria-label=\"Future Corporation sections\"" in shell.text
    assert "Web UI foundation is operational" in shell.text
    assert "Dashboard — planned" in shell.text

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert ".site-header" in stylesheet.text
    assert missing_asset.status_code == 404
    assert protected_status.status_code == 401

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []
