from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
import pytest

from app.api.security import require_permission
from app.application.services.capability_audit import CapabilityAuditService
from app.application.services.capability_authorization import DEFAULT_CAPABILITY_AUTHORIZATION
from app.application.services.capability_authorization import CapabilityAuthorizationService, CapabilityDefinition
from app.application.services.capability_grants import CapabilityGrantService
from app.local import create_local_app


def test_audit_redacts_unsafe_actor_and_reference_and_bounds_history(tmp_path):
    now = [datetime(2035, 1, 1, tzinfo=timezone.utc)]
    audit = CapabilityAuditService(tmp_path / "audit.sqlite", clock=lambda: now[0])
    audit.MAX_EVENTS = 2
    audit.record(actor_id="sk_live_abcdefgh", capability_id="chat:send",
                 permission_decision="allow", action_state="authorization",
                 result_state="allowed", safe_reference="token=secret")
    events = audit.list_events()
    assert len(events) == 1
    assert events[0]["actor_ref"].startswith("actor:")
    assert events[0]["safe_reference"] is None
    assert "secret" not in repr(events)
    assert "sk_live_abcdefgh" not in repr(events)

    for n in range(3):
        audit.record(actor_id="owner", capability_id="chat:send",
                     permission_decision="allow", action_state="executed",
                     result_state="success", safe_reference=f"action:{n}")
    assert len(audit.list_events(limit=20)) == 2
    now[0] += timedelta(days=31)
    assert audit.list_events() == ()


def test_audit_rejects_arbitrary_payload_and_unbounded_inspection(tmp_path):
    audit = CapabilityAuditService(tmp_path / "audit.sqlite")
    with pytest.raises(TypeError):
        audit.record(actor_id="owner", capability_id="chat:send",
                     permission_decision="allow", action_state="executed",
                     result_state="success", prompt="private prompt")
    with pytest.raises(ValueError):
        audit.list_events(limit=201)


def test_audit_inspection_requires_explicit_local_owner_permission(tmp_path):
    audit = CapabilityAuditService(tmp_path / "audit.sqlite")
    audit.record(actor_id="local-owner", capability_id="chat:send",
                 permission_decision="allow", action_state="executed",
                 result_state="success")
    app = create_local_app(password="test-only-owner-passphrase",
                           capability_audit_service=audit)
    protected = APIRouter()

    @protected.get("/api/audit-test-denied",
                   dependencies=[Depends(require_permission("test:denied"))])
    def denied_route():
        return {"ok": True}

    app.include_router(protected)
    with TestClient(app, base_url="http://127.0.0.1:8000",
                    client=("127.0.0.1", 50131)) as client:
        assert client.get("/api/capabilities/audit").status_code == 401
        assert client.post("/api/local/login", json={"password": "test-only-owner-passphrase"},
                           headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200
        response = client.get("/api/capabilities/audit")
        assert response.status_code == 200
        assert any(item["capability_id"] == "capability-audit:read"
                   for item in response.json()["items"])
        assert client.get("/api/audit-test-denied").status_code == 403
        denied = client.get("/api/capabilities/audit").json()["items"]
        assert any(item["capability_id"] == "test:denied"
                   and item["permission_decision"] == "deny"
                   and item["result_state"] == "denied" for item in denied)


def test_audit_read_is_not_session_grantable():
    definition = DEFAULT_CAPABILITY_AUTHORIZATION.definition("capability-audit:read")
    assert definition is not None
    assert definition.risk == "high"
    assert not definition.grant_modes


def test_grant_lifecycle_records_actor_and_safe_capability_metadata(tmp_path):
    audit = CapabilityAuditService(tmp_path / "audit.sqlite")
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("optional.inspect", "principal", frozenset({"optional:inspect"}),
                             "low", grant_modes=frozenset({"session"})),
    ])
    grants = CapabilityGrantService(policy)
    grants.set_audit_service(audit)
    grants.set_enabled("optional.inspect", enabled=True, actor_id="owner")
    grant = grants.issue(grantor="owner", permissions=frozenset(), session_id="session",
                         capability_id="optional.inspect", scope_type="principal",
                         scope_id="owner", ttl_seconds=60)
    events = audit.list_events(limit=10)
    assert [item["action_state"] for item in reversed(events)] == ["enabled", "granted"]
    assert all(item["actor_ref"].startswith("actor:") for item in events)
    assert len({item["actor_ref"] for item in events}) == 1
    assert all(item["capability_id"] == "optional.inspect" for item in events)
    assert grants.revoke(grant.grant_id, grantor="owner", session_id="session").revoked_at
