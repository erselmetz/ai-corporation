from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal
from app.application.services.structure_map import build_structure_map
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
ALL = frozenset({"position:read", "employee:read", "agent:read"})


def _service():
    service = create_corporation_runtime().application_service
    service.create_employee("analyst", "Analyst", "Analyst", ["analyse"])
    root = service.create_position("Architect", ["lead"], None, "local_employee")
    child = service.create_position("Researcher", ["analyse"], root.id, "analyst")
    vacant = service.create_position("Developer", ["tbd"], root.id, None)
    return service, root, child, vacant


def test_structure_reports_only_recorded_links_and_distinguishes_missing_identities():
    service, root, child, vacant = _service()
    report = build_structure_map(service, ALL)
    nodes = {n["id"]: n for n in report["positions"]}
    assert report["roots"] == [root.id]
    assert nodes[child.id]["reports_to_position_id"] == root.id
    assert nodes[root.id]["agent"]["state"] == "assigned"
    assert nodes[root.id]["agent"]["model_id"] == "llama3.2:3b"
    assert nodes[child.id]["employee"]["state"] == "assigned"
    assert nodes[child.id]["agent"] == {"state": "unassigned"}
    assert nodes[vacant.id]["employee"] == {"state": "unassigned"}
    assert nodes[vacant.id]["agent"] == {"state": "not_applicable"}
    assert set(report["sections"].values()) == {"available"}


def test_forbidden_sections_are_labelled():
    service, root, child, _ = _service()
    report = build_structure_map(service, frozenset({"position:read"}))
    assert report["sections"] == {
        "positions": "available", "employees": "forbidden", "agents": "forbidden"}
    nodes = {n["id"]: n for n in report["positions"]}
    assert nodes[root.id]["employee"] == {"state": "forbidden", "id": "local_employee"}
    assert nodes[root.id]["agent"] == {"state": "forbidden"}


def test_missing_parent_employee_agent_and_provider_are_labelled():
    from types import SimpleNamespace as NS

    class Stub:
        def list_positions(self):
            return (
                NS(id="p1", title="Architect", responsibilities=("a",), active=True,
                   revision=1, reports_to_position_id="gone", employee_id="ghost"),
                NS(id="p2", title="Developer", responsibilities=("b",), active=True,
                   revision=1, reports_to_position_id=None, employee_id="e2"),
            )

        def list_employees(self):
            return (NS(id="e2", name="E", role="R", agent_id="a2"),)

        def list_agents(self):
            return (NS(id="a2", name="A", provider="offline", model="m"),)

        def provider_exists(self, provider_id):
            return False

    report = build_structure_map(Stub(), ALL)
    nodes = {n["id"]: n for n in report["positions"]}
    assert nodes["p1"]["reporting_state"] == "missing"
    assert "p1" in report["roots"]
    assert nodes["p1"]["employee"]["state"] == "missing"
    assert nodes["p2"]["agent"]["state"] == "assigned"
    assert nodes["p2"]["agent"]["provider_state"] == "unavailable"


def test_permission_error_without_position_read():
    import pytest

    service, *_ = _service()
    with pytest.raises(PermissionError):
        build_structure_map(service, frozenset({"employee:read"}))

def test_api_requires_position_read_and_local_session():
    service, root, _, _ = _service()
    app = create_local_app(password=PASSWORD, application_service=service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/structure-map").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        body = client.get("/api/structure-map").json()
        assert [n["id"] for n in body["positions"]][0] == root.id
        assert "api_key" not in str(body).lower()
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"employee:read"}))
        assert client.get("/api/structure-map").status_code == 403
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"position:read"}))
        partial = client.get("/api/structure-map").json()
        assert partial["sections"]["agents"] == "forbidden"
        assert client.post("/api/structure-map").status_code in {405, 415, 403}
