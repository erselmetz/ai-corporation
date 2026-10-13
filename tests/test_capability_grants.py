from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from app.api import require_permission
from app.application.services.capability_authorization import (
    CapabilityAuthorizationService,
    CapabilityDefinition,
    DEFAULT_CAPABILITY_AUTHORIZATION,
)
from app.application.services.capability_grants import CapabilityGrantConflict, CapabilityGrantService
from app.local import create_local_app

PASSWORD = "test-only-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"


def policy_with_optional_capability():
    return CapabilityAuthorizationService((*DEFAULT_CAPABILITY_AUTHORIZATION.definitions,
        CapabilityDefinition("optional.inspect", "principal", frozenset({"optional:inspect"}),
                             "low", grant_modes=frozenset({"session"}))))


def test_owner_explicit_session_grant_is_scoped_expires_and_can_be_revoked():
    policy = policy_with_optional_capability()
    app = create_local_app(password=PASSWORD, capability_authorization_service=policy,
                           application_service=MagicMock())
    protected = APIRouter()

    @protected.get("/api/optional-inspection", dependencies=[Depends(require_permission("optional.inspect"))])
    def inspect_optional():
        return {"ok": True}

    app.include_router(protected)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/optional-inspection").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        session = client.get("/api/local/session").json()
        headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}
        assert client.get("/api/capabilities/grants/policy").json()["items"][-1]["enabled"] is False
        eligible = client.get("/api/capabilities/grants/eligible").json()["items"]
        assert eligible == []
        enabled = client.put("/api/capabilities/grants/policy/optional.inspect",
                             headers=headers, json={"enabled": True})
        assert enabled.status_code == 200
        eligible = client.get("/api/capabilities/grants/eligible").json()["items"]
        assert eligible == [{"capability_id": "optional.inspect", "scope_type": "principal",
                             "scope_id": "local-owner", "risk": "low"}]
        assert client.get("/api/optional-inspection").status_code == 403
        created = client.post("/api/capabilities/grants", headers=headers, json={
            "capability_id": "optional.inspect", "scope_type": "principal",
            "scope_id": "local-owner", "ttl_seconds": 120,
        })
        assert created.status_code == 201
        grant = created.json()
        assert grant["grantor"] == "local-owner"
        assert grant["session_id"]
        assert grant["persistence"] == "session_only"
        assert grant["status"] == "active"
        assert client.get("/api/optional-inspection").status_code == 200
        assert client.post("/api/capabilities/grants", headers=headers, json={
            "capability_id": "optional.inspect", "scope_type": "principal",
            "scope_id": "local-owner", "ttl_seconds": 120,
        }).status_code == 409
        revoked = client.post(f"/api/capabilities/grants/{grant['grant_id']}/revoke",
                              headers=headers, json={})
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert client.get("/api/optional-inspection").status_code == 403
        assert client.get("/api/capabilities/grants").json()["items"][0]["revoked_at"]
        assert client.put("/api/capabilities/grants/policy/optional.inspect",
                          headers=headers, json={"enabled": True}).status_code == 200
        second = client.post("/api/capabilities/grants", headers=headers, json={
            "capability_id": "optional.inspect", "scope_type": "principal",
            "scope_id": "local-owner", "ttl_seconds": 120,
        }).json()
        disabled = client.put("/api/capabilities/grants/policy/optional.inspect",
                              headers=headers, json={"enabled": False})
        assert disabled.status_code == 200
        assert client.get("/api/optional-inspection").status_code == 403
        assert client.get("/api/capabilities/grants").json()["items"][0]["status"] == "revoked"
        assert client.put("/api/capabilities/grants/policy/optional.inspect",
                          headers=headers, json={"enabled": True}).status_code == 200
        third = client.post("/api/capabilities/grants", headers=headers, json={
            "capability_id": "optional.inspect", "scope_type": "principal",
            "scope_id": "local-owner", "ttl_seconds": 120,
        }).json()
        assert client.post("/api/local/logout", headers=headers, json={}).status_code == 200
        assert client.get("/api/optional-inspection").status_code == 401
        third_grant = app.state.capability_grant_service.list_for_session(
            grantor="local-owner", session_id=third["session_id"])
        assert third["status"] == "active"
        assert app.state.capability_grant_service.snapshot(third_grant[0])["status"] == "revoked"


def test_session_grant_rejects_high_risk_wrong_scope_and_invalid_expiry():
    now = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("safe.read", "principal", frozenset({"safe:read"}),
                             "low", grant_modes=frozenset({"session"})),
        CapabilityDefinition("unsafe.write", "principal", frozenset({"unsafe:write"}), "high"),
    ])
    service = CapabilityGrantService(policy, clock=lambda: now[0])
    args = {"grantor": "owner", "permissions": frozenset(), "session_id": "session",
            "scope_type": "principal", "scope_id": "owner"}
    assert service.enabled_snapshot()[0]["enabled"] is False
    service.set_enabled("safe.read", enabled=True)
    with pytest.raises(CapabilityGrantConflict, match="not approved"):
        service.issue(**args, capability_id="unsafe.write", ttl_seconds=60)
    with pytest.raises(CapabilityGrantConflict, match="grantor's principal"):
        service.issue(**{**args, "scope_id": "other"}, capability_id="safe.read", ttl_seconds=60)
    with pytest.raises(ValueError, match="expiry"):
        service.issue(**args, capability_id="safe.read", ttl_seconds=3601)
    grant = service.issue(**args, capability_id="safe.read", ttl_seconds=60)
    assert len(service.active_keys(grantor="owner", session_id="session")) == 1
    now[0] += timedelta(seconds=61)
    assert service.active_keys(grantor="owner", session_id="session") == frozenset()
    assert service.snapshot(grant)["status"] == "expired"
    service.revoke_session("session")
    assert service.snapshot(service.list_for_session(grantor="owner", session_id="session")[0])["status"] == "expired"
