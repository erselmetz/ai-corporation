from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.local import create_local_app
from app.application.services.capability_approvals import CapabilityApprovalService


ORIGIN = "http://127.0.0.1:8000"
PASSWORD = "local-automation-test-password"


def owner_client():
    app = create_local_app(password=PASSWORD, application_service=MagicMock())
    app.state.capability_approval_service = CapabilityApprovalService(app.state.capability_authorization_service)
    client = TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 51221))
    response = client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    auth = client.get("/api/local/session").json()
    return app, client, {"Origin": ORIGIN, "X-Local-CSRF": auth["csrf"]}


def test_automation_surface_is_reachable_owner_gated_and_starts_deny_by_default():
    app = create_local_app(password=PASSWORD, application_service=MagicMock())
    app.state.capability_approval_service = CapabilityApprovalService(app.state.capability_authorization_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 51222)) as client:
        assert client.get("/api/local/automation").status_code == 401
        assert client.get("/ui/automation").status_code == 404
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        result = client.get("/api/local/automation").json()
        assert result["browser"]["allowed_origins"] == []
        assert result["desktop"]["allowed_process_names"] == []
        assert result["persistence"] == "process_only"
        assert result["browser_visible"] is True


def test_allowlist_updates_need_csrf_are_exact_and_denied_targets_never_launch():
    _app, client, headers = owner_client()
    assert client.put("/api/local/automation/browser/origin", json={
        "origin": "https://example.org", "allowed": True}, headers={"Origin": ORIGIN}).status_code == 403
    added = client.put("/api/local/automation/browser/origin", json={
        "origin": "https://example.org", "allowed": True}, headers=headers)
    assert added.status_code == 200
    assert added.json()["allowed_origins"] == ["https://example.org"]

    for invalid in ("http://example.org", "https://example.org/path", "https://user@example.org"):
        response = client.put("/api/local/automation/browser/origin", json={
            "origin": invalid, "allowed": True}, headers=headers)
        assert response.status_code == 422

    denied = client.post("/api/local/automation/browser/preview", json={
        "action": "click", "url": "https://not-allowed.example/", "role": "button",
        "name": "Continue", "value": None,
    }, headers=headers)
    assert denied.status_code == 409
    assert "not explicitly allowed" in denied.json()["detail"]


def test_process_allowlist_requires_csrf_and_traces_remain_owner_scoped():
    _app, client, headers = owner_client()
    response = client.put("/api/local/automation/desktop/process", json={
        "process_name": "notepad.exe", "allowed": True}, headers=headers)
    assert response.status_code == 200
    assert response.json()["allowed_process_names"] == ["notepad.exe"]
    assert client.put("/api/local/automation/desktop/process", json={
        "process_name": "*", "allowed": True}, headers=headers).status_code == 422
    assert client.get("/api/local/automation/traces").json() == {"items": []}
