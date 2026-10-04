from fastapi import Request
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.local import create_local_app
from app.positions import POSITION_TEMPLATES
from app.runtime.factory import create_corporation_runtime

PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"


class PositionAuthentication:
    def authenticate(self, request: Request):
        identities = {
            "position-reader": frozenset({"position:read"}),
            "position-manager": frozenset({"position:manage"}),
            "position-owner": frozenset({
                "position:read", "position:manage", "employee:read",
            }),
            "employee-manager": frozenset({"employee:manage"}),
        }
        permissions = identities.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal("test-owner", permissions)


def create_position(client, *, title="Architect", employee_id=None, parent=None):
    return client.post(
        "/api/positions",
        headers={"Authorization": "position-owner"},
        json={
            "title": title,
            "responsibilities": ["Review scoped work"],
            "reports_to_position_id": parent,
            "employee_id": employee_id,
        },
    )


def test_positions_use_distinct_read_and_manage_permissions_and_default_deny():
    runtime = create_corporation_runtime()
    app = create_app(
        application_service=runtime.application_service,
        authentication_backend=PositionAuthentication(),
    )
    with TestClient(app) as client:
        assert client.get("/api/positions").status_code == 401
        assert client.get("/api/positions/templates",
                         headers={"Authorization": "employee-manager"}).status_code == 403
        assert client.get("/api/positions/templates",
                         headers={"Authorization": "position-reader"}).json() == {
                             "items": list(POSITION_TEMPLATES),
                         }
        denied = client.post(
            "/api/positions",
            headers={"Authorization": "position-reader"},
            json={"title": "Developer", "responsibilities": ["Build software"]},
        )
        assert denied.status_code == 403
        assert client.get("/api/positions",
                         headers={"Authorization": "position-manager"}).status_code == 403
        assert client.get("/api/positions").status_code == 401


def test_position_revisions_preserve_employee_and_reporting_provenance():
    runtime = create_corporation_runtime()
    original_agent = runtime.employees.get("local_employee").agent
    app = create_app(
        application_service=runtime.application_service,
        authentication_backend=PositionAuthentication(),
    )
    with TestClient(app) as client:
        root = create_position(client, employee_id="local_employee").json()
        child = create_position(client, title="Developer", parent=root["id"]).json()
        assert root["employee_id"] == "local_employee"
        assert root["active"] is True
        assert root["revision"] == 1
        assert "agent_id" not in root and "permissions" not in root
        assert child["reports_to_position_id"] == root["id"]
        blocked_employee_removal = client.delete(
            "/api/employees/local_employee",
            headers={"Authorization": "employee-manager"},
        )
        assert blocked_employee_removal.status_code == 409
        assert runtime.employees.exists("local_employee")

        update = client.put(
            f"/api/positions/{child['id']}",
            headers={"Authorization": "position-owner"},
            json={
                "expected_revision": 1,
                "title": "Researcher",
                "responsibilities": ["Inspect evidence", "Record unknowns"],
                "reports_to_position_id": None,
                "employee_id": None,
            },
        )
        assert update.status_code == 200
        revised = update.json()
        assert revised["revision"] == 2
        assert revised["history"][0]["revision"] == 1
        assert revised["history"][0]["reports_to_position_id"] == root["id"]
        assert revised["responsibilities"] == ["Inspect evidence", "Record unknowns"]
        assert client.put(
            f"/api/positions/{child['id']}",
            headers={"Authorization": "position-owner"},
            json={
                "expected_revision": 1,
                "title": "Researcher",
                "responsibilities": ["Updated"],
            },
        ).status_code == 409
        unassign = client.put(
            f"/api/positions/{root['id']}",
            headers={"Authorization": "position-owner"},
            json={
                "expected_revision": 1,
                "title": "Architect",
                "responsibilities": ["Review scoped work"],
                "reports_to_position_id": None,
                "employee_id": None,
            },
        )
        assert unassign.status_code == 200
        assert unassign.json()["history"][0]["employee_id"] == "local_employee"
        assert client.delete(
            f"/api/positions/{root['id']}",
            headers={"Authorization": "position-owner"},
        ).status_code == 409
        assert runtime.employees.get("local_employee").agent is original_agent
        assert runtime.application_service.get_employee("local_employee").role == "Local AI Worker"


def test_position_reference_validation_removal_and_deactivation_conflicts():
    runtime = create_corporation_runtime()
    app = create_app(
        application_service=runtime.application_service,
        authentication_backend=PositionAuthentication(),
    )
    with TestClient(app) as client:
        invalid_parent = client.post(
            "/api/positions",
            headers={"Authorization": "position-owner"},
            json={
                "title": "Security",
                "responsibilities": ["Review access"],
                "reports_to_position_id": "missing",
            },
        )
        assert invalid_parent.status_code == 422
        invalid_employee = create_position(client, employee_id="missing-employee")
        assert invalid_employee.status_code == 422

        root = create_position(client).json()
        child = create_position(client, title="Developer", parent=root["id"]).json()
        cycle = client.put(
            f"/api/positions/{root['id']}",
            headers={"Authorization": "position-owner"},
            json={
                "expected_revision": 1,
                "title": "Architect",
                "responsibilities": ["Review scoped work"],
                "reports_to_position_id": child["id"],
            },
        )
        assert cycle.status_code == 422
        assert client.post(
            f"/api/positions/{root['id']}/deactivate",
            headers={"Authorization": "position-owner"},
            json={"expected_revision": 1},
        ).status_code == 409
        assert client.delete(
            f"/api/positions/{root['id']}",
            headers={"Authorization": "position-owner"},
        ).status_code == 409

        unlinked = client.put(
            f"/api/positions/{child['id']}",
            headers={"Authorization": "position-owner"},
            json={
                "expected_revision": 1,
                "title": "Developer",
                "responsibilities": ["Build software"],
            },
        )
        assert unlinked.status_code == 200
        inactive = client.post(
            f"/api/positions/{root['id']}/deactivate",
            headers={"Authorization": "position-owner"},
            json={"expected_revision": 1},
        )
        assert inactive.status_code == 200 and inactive.json()["active"] is False
        assert inactive.json()["history"][0]["active"] is True
        assert client.delete(
            f"/api/positions/{root['id']}",
            headers={"Authorization": "position-owner"},
        ).status_code == 409
        disposable = create_position(client, title="UI/UX").json()
        assert client.delete(
            f"/api/positions/{disposable['id']}",
            headers={"Authorization": "position-owner"},
        ).status_code == 204
        assert client.get(
            f"/api/positions/{disposable['id']}",
            headers={"Authorization": "position-owner"},
        ).status_code == 404


def test_local_owner_has_explicit_position_permissions_and_csrf_protection():
    runtime = create_corporation_runtime()
    app = create_local_app(
        password=PASSWORD,
        application_service=runtime.application_service,
    )
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.post(
            "/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN}
        ).status_code == 200
        session = client.get("/api/local/session").json()
        assert {"position:read", "position:manage"} <= set(session["permissions"])
        assert "employee:manage" not in session["permissions"]
        body = {"title": "Architect", "responsibilities": ["Review scoped work"]}
        denied = client.post(
            "/api/positions", json=body, headers={"Origin": ORIGIN}
        )
        assert denied.status_code == 403
        allowed = client.post(
            "/api/positions",
            json=body,
            headers={"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]},
        )
        assert allowed.status_code == 201
        assert client.get("/api/positions").status_code == 200
        assert client.get("/ui/positions").status_code == 200
        assert 'src="/ui/static/positions.mjs"' in client.get("/ui/positions").text

    from app.api.app import create_app as create_default_app

    with TestClient(create_default_app(application_service=runtime.application_service)) as client:
        assert client.get("/api/positions").status_code == 401
        assert client.get("/ui/positions").status_code == 200
