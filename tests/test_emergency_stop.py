from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.application.services.capability_authorization import (
    CapabilityAuthorizationService,
    CapabilityDefinition,
    DEFAULT_CAPABILITY_AUTHORIZATION,
)
from app.application.services.emergency_stop import EmergencyStopService
from app.local import create_local_app


PASSWORD = "emergency-stop-test-password"
ORIGIN = "http://127.0.0.1:8000"


def test_emergency_stop_blocks_new_actions_but_keeps_stop_status_revoke_and_resume():
    policy = CapabilityAuthorizationService((*DEFAULT_CAPABILITY_AUTHORIZATION.definitions,
        CapabilityDefinition("optional.inspect", "principal", frozenset({"optional:inspect"}),
                             "low", grant_modes=frozenset({"session"}))))
    stop_service = EmergencyStopService(clock=lambda: datetime(2035, 1, 1, tzinfo=timezone.utc))
    app = create_local_app(password=PASSWORD, application_service=MagicMock(),
                           capability_authorization_service=policy,
                           emergency_stop_service=stop_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50145)) as client:
        assert client.get("/api/local/emergency-stop").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        session = client.get("/api/local/session").json()
        headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}

        assert client.put("/api/capabilities/grants/policy/optional.inspect", headers=headers,
                          json={"enabled": True}).status_code == 200
        grant_response = client.post("/api/capabilities/grants", headers=headers, json={
            "capability_id": "optional.inspect", "scope_type": "principal",
            "scope_id": "local-owner", "ttl_seconds": 120,
        })
        assert grant_response.status_code == 201
        grant_id = grant_response.json()["grant_id"]

        stopped = client.post("/api/local/emergency-stop/stop", headers=headers, json={})
        assert stopped.status_code == 200
        assert stopped.json()["stopped"] is True
        assert stopped.json()["persistence"] == "process_only"
        assert client.post("/api/local/voice/cloud-budget", headers=headers,
                           json={"ceiling_cents": 10}).status_code == 423
        status = client.get("/api/local/emergency-stop")
        assert status.status_code == 200
        assert status.json()["stopped"] is True
        assert "capability-emergency:manage" in status.json()["active_capabilities"]
        assert status.json()["capture"]["screen"] == "page-reported"
        assert any(item["grant_id"] == grant_id and item["expires_at"]
                   for item in status.json()["session_grants"])

        revoked = client.post(f"/api/capabilities/grants/{grant_id}/revoke",
                              headers=headers, json={})
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert client.post("/api/local/emergency-stop/resume", headers=headers,
                           json={"confirmed": False}).status_code == 409
        resumed = client.post("/api/local/emergency-stop/resume", headers=headers,
                              json={"confirmed": True})
        assert resumed.status_code == 200
        assert resumed.json()["stopped"] is False
        assert client.post("/api/local/voice/cloud-budget", headers=headers,
                           json={"ceiling_cents": 10}).status_code == 200


def test_emergency_stop_is_process_local_and_idempotent():
    now = datetime(2035, 1, 1, tzinfo=timezone.utc)
    service = EmergencyStopService(clock=lambda: now)
    assert service.snapshot()["stopped"] is False
    first = service.stop()
    assert service.stop() == first
    assert service.snapshot()["stopped_at"] == now.isoformat()
    assert EmergencyStopService().snapshot()["stopped"] is False
    assert service.resume()["stopped"] is False
