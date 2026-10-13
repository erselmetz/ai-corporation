from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.application.services.capability_approvals import (
    APPROVAL_MANAGEMENT_PERMISSION,
    POLICY_VERSION,
    CapabilityApprovalError,
    CapabilityApprovalService,
)
from app.application.services.capability_authorization import (
    CapabilityAuthorizationService,
    CapabilityDefinition,
)
from app.local import create_local_app


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _service(clock):
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("action:moderate", "principal", frozenset({"action:moderate"}), "moderate"),
        CapabilityDefinition("action:high", "principal", frozenset({"action:high"}), "high"),
        CapabilityDefinition(APPROVAL_MANAGEMENT_PERMISSION, "principal",
                             frozenset({APPROVAL_MANAGEMENT_PERMISSION}), "high"),
        CapabilityDefinition("action:low", "principal", frozenset({"action:low"}), "low"),
    ])
    return CapabilityApprovalService(policy, clock=clock)


def _request(service, *, capability="action:high", irreversible=True):
    permissions = frozenset({capability, APPROVAL_MANAGEMENT_PERMISSION})
    approval = service.request(
        actor_id="owner", permissions=permissions,
        capability_id=capability, action_id="software.remove",
        action_summary="Remove the selected editor package and its installed version",
        target_ref="package:editor", scope_type="principal", scope_id="owner",
        payload_digest=_digest("remove exact editor version"),
        target_digest=_digest("installed-version:1.2.3"), irreversible=irreversible)
    return approval, permissions


def test_high_impact_approval_binds_exact_action_and_is_single_use():
    now = [datetime(2035, 1, 1, tzinfo=timezone.utc)]
    service = _service(lambda: now[0])
    approval, permissions = _request(service)
    snapshot = service.snapshot(approval)
    assert snapshot["status"] == "pending"
    assert snapshot["risk"] == "high"
    assert snapshot["irreversible"] is True
    assert snapshot["policy_version"] == POLICY_VERSION
    assert snapshot["expires_at"]
    assert snapshot["approval_digest"]

    with pytest.raises(CapabilityApprovalError, match="exact action"):
        service.approve(approval.approval_id, approver_id="owner", permissions=permissions,
                        confirmed_digest=_digest("different action"))
    approved = service.approve(approval.approval_id, approver_id="owner", permissions=permissions,
                               confirmed_digest=approval.approval_digest)
    assert service.snapshot(approved)["approved_by"] == "owner"
    calls = []
    with pytest.raises(CapabilityApprovalError, match="policy changed"):
        service.execute(
            approval.approval_id, actor_id="owner", permissions=permissions,
            capability_id="action:high", action_id="software.remove",
            action_summary="Remove the selected editor package and its installed version",
            target_ref="package:editor", scope_type="principal", scope_id="owner",
            payload_digest=_digest("remove exact editor version"),
            current_policy_version="capability-risk-v2",
            read_current_target_digest=lambda: _digest("installed-version:1.2.3"),
            operation=lambda: calls.append("wrong-policy"))
    assert calls == []
    result = service.execute(
        approval.approval_id, actor_id="owner", permissions=permissions,
        capability_id="action:high", action_id="software.remove",
        action_summary="Remove the selected editor package and its installed version",
        target_ref="package:editor", scope_type="principal", scope_id="owner",
        payload_digest=_digest("remove exact editor version"),
        current_policy_version=POLICY_VERSION,
        read_current_target_digest=lambda: _digest("installed-version:1.2.3"),
        operation=lambda: calls.append("ran") or "done")
    assert result == "done"
    assert calls == ["ran"]
    assert service.snapshot(service.get(approval.approval_id))["status"] == "consumed"
    with pytest.raises(CapabilityApprovalError, match="not current and approved"):
        service.execute(
            approval.approval_id, actor_id="owner", permissions=permissions,
            capability_id="action:high", action_id="software.remove",
            action_summary="Remove the selected editor package and its installed version",
            target_ref="package:editor", scope_type="principal", scope_id="owner",
            payload_digest=_digest("remove exact editor version"),
            current_policy_version=POLICY_VERSION,
            read_current_target_digest=lambda: _digest("installed-version:1.2.3"),
            operation=lambda: calls.append("replayed"))
    assert calls == ["ran"]


def test_expiry_target_change_policy_change_and_revoked_authority_fail_closed():
    now = [datetime(2035, 1, 1, tzinfo=timezone.utc)]
    service = _service(lambda: now[0])
    approval, permissions = _request(service, capability="action:moderate", irreversible=False)
    assert service.snapshot(approval)["risk"] == "moderate"
    service.approve(approval.approval_id, approver_id="owner", permissions=permissions,
                    confirmed_digest=approval.approval_digest)
    calls = []
    with pytest.raises(CapabilityApprovalError, match="target state has changed"):
        service.execute(
            approval.approval_id, actor_id="owner", permissions=permissions,
            capability_id="action:moderate", action_id="software.remove",
            action_summary="Remove the selected editor package and its installed version",
            target_ref="package:editor", scope_type="principal", scope_id="owner",
            payload_digest=_digest("remove exact editor version"),
            current_policy_version=POLICY_VERSION,
            read_current_target_digest=lambda: _digest("installed-version:1.2.4"),
            operation=lambda: calls.append("changed"))
    assert calls == []
    assert service.snapshot(service.get(approval.approval_id))["status"] == "stale"

    expired, permissions = _request(service)
    service.approve(expired.approval_id, approver_id="owner", permissions=permissions,
                    confirmed_digest=expired.approval_digest)
    now[0] += timedelta(seconds=301)
    assert service.snapshot(expired)["status"] == "expired"
    with pytest.raises(CapabilityApprovalError, match="not current and approved"):
        service.execute(
            expired.approval_id, actor_id="owner", permissions=permissions,
            capability_id="action:high", action_id="software.remove",
            action_summary="Remove the selected editor package and its installed version",
            target_ref="package:editor", scope_type="principal", scope_id="owner",
            payload_digest=_digest("remove exact editor version"),
            current_policy_version=POLICY_VERSION,
            read_current_target_digest=lambda: _digest("installed-version:1.2.3"),
            operation=lambda: calls.append("expired"))
    assert calls == []

    revoked, permissions = _request(service, capability="action:moderate", irreversible=False)
    service.approve(revoked.approval_id, approver_id="owner", permissions=permissions,
                    confirmed_digest=revoked.approval_digest)
    with pytest.raises(PermissionError):
        service.execute(
            revoked.approval_id, actor_id="owner", permissions=frozenset({APPROVAL_MANAGEMENT_PERMISSION}),
            capability_id="action:moderate", action_id="software.remove",
            action_summary="Remove the selected editor package and its installed version",
            target_ref="package:editor", scope_type="principal", scope_id="owner",
            payload_digest=_digest("remove exact editor version"),
            current_policy_version=POLICY_VERSION,
            read_current_target_digest=lambda: _digest("installed-version:1.2.3"),
            operation=lambda: calls.append("revoked"))
    assert calls == []


def test_low_risk_actions_do_not_create_approval_and_high_risk_never_auto_approves():
    service = _service(lambda: datetime(2035, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="Low-risk"):
        _request(service, capability="action:low", irreversible=False)
    high, _ = _request(service)
    assert service.snapshot(high)["status"] == "pending"


def test_local_owner_can_review_and_confirm_exact_digest_with_csrf():
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("action:high", "principal", frozenset({"action:high"}), "high"),
        CapabilityDefinition(APPROVAL_MANAGEMENT_PERMISSION, "principal",
                             frozenset({APPROVAL_MANAGEMENT_PERMISSION}), "high"),
    ])
    approvals = CapabilityApprovalService(policy)
    permissions = frozenset({"action:high", APPROVAL_MANAGEMENT_PERMISSION})
    record = approvals.request(
        actor_id="local-owner", permissions=permissions,
        capability_id="action:high", action_id="software.remove",
        action_summary="Remove the selected editor package and installed version",
        target_ref="package:editor", scope_type="principal", scope_id="local-owner",
        payload_digest=_digest("remove exact editor version"),
        target_digest=_digest("installed-version:1.2.3"), irreversible=True)
    app = create_local_app(password="test-only-owner-passphrase",
                           capability_authorization_service=policy,
                           application_service=MagicMock())
    app.state.capability_approval_service = approvals
    with TestClient(app, base_url="http://127.0.0.1:8000",
                    client=("127.0.0.1", 50101)) as client:
        assert client.get("/api/capabilities/approvals").status_code in {401, 403}
        assert client.post("/api/local/login", json={"password": "test-only-owner-passphrase"},
                           headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200
        session = client.get("/api/local/session").json()
        headers = {"Origin": "http://127.0.0.1:8000", "X-Local-CSRF": session["csrf"]}
        listing = client.get("/api/capabilities/approvals")
        assert listing.status_code == 200
        item = listing.json()["items"][0]
        assert item["action_summary"] == "Remove the selected editor package and installed version"
        assert item["irreversible"] is True
        assert item["status"] == "pending"
        assert client.post(f"/api/capabilities/approvals/{record.approval_id}/approve",
                           json={"confirmed_digest": record.approval_digest},
                           headers={"Origin": headers["Origin"]}).status_code == 403
        approved = client.post(f"/api/capabilities/approvals/{record.approval_id}/approve",
                               json={"confirmed_digest": record.approval_digest}, headers=headers)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["approved_by"] == "local-owner"
