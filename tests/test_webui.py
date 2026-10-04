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


def test_provider_model_management_page_uses_protected_apis_and_safe_assets():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/providers")
        script = client.get("/ui/static/providers.mjs")
        stylesheet = client.get("/ui/static/style.css")
        dashboard = client.get("/ui")
        employees = client.get("/ui/employees")
        protected = [
            client.get("/api/providers"),
            client.get("/api/providers/local"),
            client.post("/api/providers", json={"id": "local", "name": "Local"}),
            client.delete("/api/providers/local"),
            client.get("/api/models"),
            client.get("/api/models/agent-1"),
            client.put(
                "/api/models/agent-1",
                json={"provider_id": "local", "model_id": "model"},
            ),
        ]

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "ERSELMETZ AI CORPORATION" in page.text
    assert "Provider &amp; Model Management" in page.text
    assert 'href="/ui"' in page.text
    assert 'href="/ui/employees"' in page.text
    assert 'src="/ui/static/providers.mjs"' in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert stylesheet.status_code == 200
    assert "management-grid" in stylesheet.text
    assert all(
        endpoint in script.text
        for endpoint in (
            "/api/providers",
            "/api/models",
            "method: \"DELETE\"",
            "method: \"PUT\"",
        )
    )
    assert "Bearer " not in script.text
    assert "api_key" not in script.text.lower()
    assert "password" not in script.text.lower()
    assert "Employee management" in dashboard.text
    assert 'href="/ui/providers"' in dashboard.text
    assert 'href="/ui/providers"' in employees.text
    assert [response.status_code for response in protected] == [401] * 7

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_task_management_page_uses_existing_protected_task_contract():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/tasks")
        script = client.get("/ui/static/tasks.mjs")
        stylesheet = client.get("/ui/static/style.css")
        dashboard = client.get("/ui")
        employees = client.get("/ui/employees")
        providers = client.get("/ui/providers")
        protected = [
            client.get("/api/tasks"),
            client.get("/api/tasks/TASK-1"),
            client.post(
                "/api/tasks",
                json={"title": "Task", "description": "Description"},
            ),
            client.post("/api/tasks/TASK-1/dry-run"),
        ]
        unsupported_delete = client.delete("/api/tasks/TASK-1")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "ERSELMETZ AI CORPORATION" in page.text
    assert "Task Management" in page.text
    assert 'href="/ui"' in page.text
    assert 'src="/ui/static/tasks.mjs"' in page.text
    assert 'href="/ui/static/style.css"' in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert stylesheet.status_code == 200
    assert "task-layout" in stylesheet.text
    assert all(endpoint in script.text for endpoint in ("/api/tasks", "/dry-run"))
    assert "DELETE" not in script.text
    assert "Bearer " not in script.text
    assert "api_key" not in script.text.lower()
    assert "password" not in script.text.lower()
    assert 'href="/ui/tasks"' in dashboard.text
    assert 'href="/ui/tasks"' in employees.text
    assert 'href="/ui/tasks"' in providers.text
    assert [response.status_code for response in protected] == [401] * 4
    assert unsupported_delete.status_code == 405

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_project_management_page_uses_existing_protected_project_contract():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/projects")
        script = client.get("/ui/static/projects.mjs")
        stylesheet = client.get("/ui/static/style.css")
        dashboard = client.get("/ui")
        tasks = client.get("/ui/tasks")
        protected = [
            client.get("/api/projects"),
            client.get("/api/projects/project-1"),
            client.post(
                "/api/projects",
                json={"name": "Project", "description": "Description"},
            ),
        ]
        unsupported_delete = client.delete("/api/projects/project-1")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "Project Management" in page.text
    assert 'href="/ui/static/style.css"' in page.text
    assert 'src="/ui/static/projects.mjs"' in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert stylesheet.status_code == 200
    assert "project-layout" in stylesheet.text
    assert all(endpoint in script.text for endpoint in ("/api/projects", "method: \"POST\""))
    assert "method: \"DELETE\"" not in script.text
    assert "Bearer " not in script.text
    assert "api_key" not in script.text.lower()
    assert "password" not in script.text.lower()
    assert 'href="/ui/projects"' in dashboard.text
    assert 'href="/ui/projects"' in tasks.text
    assert [response.status_code for response in protected] == [401] * 3
    assert unsupported_delete.status_code == 405

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_activity_page_uses_existing_protected_read_only_api():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/activity")
        script = client.get("/ui/static/activity.mjs")
        stylesheet = client.get("/ui/static/style.css")
        dashboard = client.get("/ui")
        projects = client.get("/ui/projects")
        protected = client.get("/api/activity")
        invalid_limit = client.get("/api/activity?limit=101")
        unsupported_detail = client.get("/api/activity/1")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "Activity &amp; Logs" in page.text
    assert 'href="/ui/static/style.css"' in page.text
    assert 'src="/ui/static/activity.mjs"' in page.text
    assert 'name="limit"' in page.text
    assert 'name="task_id"' in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert stylesheet.status_code == 200
    assert "activity-list" in stylesheet.text
    assert "/api/activity?" in script.text
    assert "task_id" in script.text
    assert "Bearer " not in script.text
    assert "api_key" not in script.text.lower()
    assert "password" not in script.text.lower()
    assert 'href="/ui/activity"' in dashboard.text
    assert 'href="/ui/activity"' in projects.text
    assert protected.status_code == 401
    assert invalid_limit.status_code == 401
    assert unsupported_detail.status_code == 404

    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_documentation_portal_uses_only_its_protected_markdown_api():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/documentation")
        script = client.get("/ui/static/documentation.mjs")
        stylesheet = client.get("/ui/static/style.css")
        dashboard = client.get("/ui")
        activity = client.get("/ui/activity")
        api_list = client.get("/api/documentation")
        api_detail = client.get("/api/documentation/corporation-overview")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "Documentation &amp; Knowledge Portal" in page.text
    assert "separate from the" in page.text
    assert 'href="/ui/static/style.css"' in page.text
    assert 'src="/ui/static/documentation.mjs"' in page.text
    assert "documentation:read" in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert stylesheet.status_code == 200
    assert "documentation-layout" in stylesheet.text
    assert "/api/documentation" in script.text
    assert "credentials: \"same-origin\"" in script.text
    assert "innerHTML" not in script.text
    assert "node:fs" not in script.text
    assert "sqlite" not in script.text.lower()
    assert "DATABASE_PATH" not in script.text
    assert 'href="/ui/documentation"' in dashboard.text
    assert 'href="/ui/documentation"' in activity.text
    assert api_list.status_code == 401
    assert api_detail.status_code == 401
    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_updates_page_uses_only_the_protected_curated_updates_api():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        page = client.get("/ui/updates")
        script = client.get("/ui/static/updates.mjs")
        stylesheet = client.get("/ui/static/style.css")
        dashboard = client.get("/ui")
        documentation = client.get("/ui/documentation")
        api_list = client.get("/api/updates")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "Updates / Changelog" in page.text
    assert "manually maintained" in page.text
    assert "separate from" in page.text
    assert "updates:read" in page.text
    assert 'src="/ui/static/updates.mjs"' in page.text
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert stylesheet.status_code == 200
    assert "updates-list" in stylesheet.text
    assert "/api/updates" in script.text
    assert "credentials: \"same-origin\"" in script.text
    assert "innerHTML" not in script.text
    assert "node:fs" not in script.text
    assert "sqlite" not in script.text.lower()
    assert "DATABASE_PATH" not in script.text
    assert 'href="/ui/updates"' in dashboard.text
    assert 'href="/ui/updates"' in documentation.text
    assert api_list.status_code == 401
    orchestrator.execute_task.assert_not_called()
    orchestrator.run_agent.assert_not_called()
    orchestrator.create_task.assert_not_called()
    assert orchestrator.method_calls == []


def test_activity_progress_shell_and_asset_preserve_fail_closed_task_reads():
    orchestrator = MagicMock(spec=Orchestrator)
    app = create_app(CorporationApplicationService(orchestrator))
    with TestClient(app) as client:
        shell = client.get("/ui/activity")
        asset = client.get("/ui/static/task-progress.mjs")
        protected = client.get("/api/tasks/task")
    assert shell.status_code == 200
    assert 'id="task-progress"' in shell.text
    assert "task:read independently of activity:read" in shell.text
    assert asset.status_code == 200
    assert protected.status_code == 401
    orchestrator.run_agent.assert_not_called()
    orchestrator.execute_task.assert_not_called()


def test_employee_chat_page_and_assignment_preview_modules_are_served():
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    with TestClient(create_app(service)) as client:
        page = client.get("/ui/employee-chat")
        chat_module = client.get("/ui/static/employee-chat.mjs")
        preview_module = client.get("/ui/static/assignment-preview.mjs")

    assert page.status_code == 200
    assert 'src="/ui/static/employee-chat.mjs"' in page.text
    assert "/api/employee-chat/conversations" not in page.text
    assert chat_module.status_code == preview_module.status_code == 200
    assert chat_module.headers["content-type"].startswith("text/javascript")
    assert preview_module.headers["content-type"].startswith("text/javascript")
