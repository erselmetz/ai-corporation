"""Single-use owner approvals bound to one exact protected action."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import threading
from typing import Callable
from uuid import uuid4

from .capability_authorization import CapabilityAuthorizationService


class CapabilityApprovalError(Exception):
    pass


class CapabilityApprovalNotFound(CapabilityApprovalError):
    pass


POLICY_VERSION = "capability-risk-v1"
APPROVAL_MANAGEMENT_PERMISSION = "capability-approval:manage"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CapabilityActionApproval:
    approval_id: str
    actor_id: str
    capability_id: str
    action_id: str
    action_summary: str
    target_ref: str
    scope_type: str
    scope_id: str
    payload_digest: str
    target_digest: str
    policy_version: str
    risk: str
    irreversible: bool
    requested_at: str
    expires_at: str
    approval_digest: str
    status: str = "pending"
    approved_by: str | None = None
    approved_at: str | None = None
    denied_by: str | None = None
    denied_at: str | None = None
    consumed_at: str | None = None
    workspace_id: str = ""
    workspace_agent_id: str = ""
    workspace_project_id: str = ""
    workspace_model_id: str = ""


class CapabilityApprovalService:
    """In-memory review records; protected operations execute only through the guarded callback."""

    MAX_APPROVALS = 500
    MAX_TTL_SECONDS = 300

    def __init__(self, policy: CapabilityAuthorizationService, *, clock=None):
        self._policy = policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: dict[str, CapabilityActionApproval] = {}
        self._lock = threading.RLock()
        self._audit = None

    def set_audit_service(self, audit_service) -> None:
        self._audit = audit_service

    def _record(self, actor_id: str, capability_id: str, action_state: str,
                result_state: str, reference: str | None = None) -> None:
        if self._audit is not None:
            self._audit.record(actor_id=actor_id, capability_id=capability_id,
                               permission_decision="allow", action_state=action_state,
                               result_state=result_state, safe_reference=reference)

    def request(self, *, actor_id: str, permissions: frozenset[str],
                session_grants: frozenset[tuple[str, str, str]] = frozenset(),
                capability_id: str, action_id: str, action_summary: str, target_ref: str,
                scope_type: str, scope_id: str, payload_digest: str,
                target_digest: str, irreversible: bool = False,
                ttl_seconds: int = MAX_TTL_SECONDS) -> CapabilityActionApproval:
        definition = self._policy.definition(capability_id)
        if definition is None:
            raise CapabilityApprovalNotFound("Capability is not registered")
        if definition.risk == "low":
            raise ValueError("Low-risk actions do not require an approval record")
        if definition.risk not in {"moderate", "high"}:
            raise ValueError("Capability risk is not classified")
        self._policy.require(identity=actor_id, permissions=permissions,
                             capability_id=capability_id, scope_type=scope_type,
                             scope_id=scope_id, session_grants=session_grants)
        if type(irreversible) is not bool:
            raise ValueError("Irreversible state must be boolean")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= self.MAX_TTL_SECONDS:
            raise ValueError("Approval expiry must be between 1 and 300 seconds")
        for name, value, limit in (("actor", actor_id, 128), ("action", action_id, 128),
                                   ("action summary", action_summary, 512),
                                   ("target", target_ref, 256), ("scope type", scope_type, 64),
                                   ("scope", scope_id, 256)):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Approval {name} is invalid")
        for name, value in (("payload", payload_digest), ("target", target_digest)):
            if not isinstance(value, str) or not _DIGEST.fullmatch(value):
                raise ValueError(f"Approval {name} digest is invalid")
        now = self._now()
        expiry = now + timedelta(seconds=ttl_seconds)
        risk = "high" if irreversible else definition.risk
        bound = {"actor_id": actor_id, "capability_id": capability_id,
                 "action_id": action_id, "action_summary": action_summary,
                 "target_ref": target_ref,
                 "scope_type": scope_type, "scope_id": scope_id,
                 "payload_digest": payload_digest, "target_digest": target_digest,
                 "policy_version": POLICY_VERSION, "risk": risk,
                 "irreversible": irreversible, "expires_at": expiry.isoformat()}
        from .chat_workspaces import current_workspace
        workspace = current_workspace.get()
        provenance = ({"workspace_id": workspace.id, "workspace_agent_id": workspace.agent_id,
                       "workspace_project_id": workspace.project_id, "workspace_model_id": workspace.model_id}
                      if workspace is not None else {})
        if workspace is not None and workspace.owner != actor_id:
            raise PermissionError("Workspace owner does not match this action")
        bound.update(provenance)
        digest = _fingerprint(bound)
        approval = CapabilityActionApproval(
            uuid4().hex, actor_id, capability_id, action_id, action_summary, target_ref,
            scope_type, scope_id, payload_digest, target_digest, POLICY_VERSION,
            risk, irreversible, now.isoformat(), expiry.isoformat(), digest, **provenance)
        with self._lock:
            if len(self._records) >= self.MAX_APPROVALS:
                raise CapabilityApprovalError("Approval record capacity is full")
            self._record(actor_id, capability_id, "approval_requested", "pending", approval.approval_id)
            self._records[approval.approval_id] = approval
        return approval

    def snapshot(self, approval: CapabilityActionApproval) -> dict:
        status = approval.status
        if status in {"pending", "approved"} and datetime.fromisoformat(approval.expires_at) <= self._now():
            status = "expired"
        return {"approval_id": approval.approval_id, "actor_id": approval.actor_id,
                "capability_id": approval.capability_id, "action_id": approval.action_id,
                "action_summary": approval.action_summary,
                "target_ref": approval.target_ref, "scope_type": approval.scope_type,
                "scope_id": approval.scope_id, "payload_digest": approval.payload_digest,
                "target_digest": approval.target_digest, "policy_version": approval.policy_version,
                "risk": approval.risk, "irreversible": approval.irreversible,
                "requested_at": approval.requested_at, "expires_at": approval.expires_at,
                "approval_digest": approval.approval_digest, "status": status,
                "approved_by": approval.approved_by, "approved_at": approval.approved_at,
                "denied_by": approval.denied_by, "denied_at": approval.denied_at,
                "consumed_at": approval.consumed_at,
                "workspace_id": approval.workspace_id, "workspace_agent_id": approval.workspace_agent_id,
                "workspace_project_id": approval.workspace_project_id, "workspace_model_id": approval.workspace_model_id}

    @staticmethod
    def _workspace_matches(record):
        from .chat_workspaces import current_workspace
        workspace = current_workspace.get()
        return record.workspace_id == (workspace.id if workspace is not None else "")

    def get(self, approval_id: str) -> CapabilityActionApproval:
        with self._lock:
            record = self._records.get(approval_id)
            if record is None or not self._workspace_matches(record):
                raise CapabilityApprovalNotFound("Approval request is unavailable")
            return record

    def list_for_actor(self, actor_id: str) -> tuple[CapabilityActionApproval, ...]:
        now = self._now()
        with self._lock:
            return tuple(sorted(
                (record for record in self._records.values()
                 if record.actor_id == actor_id and self._workspace_matches(record)
                 and record.status in {"pending", "approved"}
                 and datetime.fromisoformat(record.expires_at) > now),
                key=lambda record: record.requested_at, reverse=True))

    def approve(self, approval_id: str, *, approver_id: str,
                permissions: frozenset[str], confirmed_digest: str) -> CapabilityActionApproval:
        self._policy.require(identity=approver_id, permissions=permissions,
                             capability_id=APPROVAL_MANAGEMENT_PERMISSION,
                             scope_type="principal", scope_id=approver_id)
        with self._lock:
            record = self._get_locked(approval_id)
            if record.status != "pending" or datetime.fromisoformat(record.expires_at) <= self._now():
                raise CapabilityApprovalError("Approval request is no longer pending")
            if approver_id != record.actor_id or confirmed_digest != record.approval_digest:
                raise CapabilityApprovalError("Owner confirmation does not match this exact action")
            approved = replace(record, status="approved", approved_by=approver_id,
                               approved_at=self._now().isoformat())
            self._record(approver_id, record.capability_id, "approval_confirmed", "success",
                         record.approval_id)
            self._records[approval_id] = approved
            return approved

    def deny(self, approval_id: str, *, approver_id: str,
             permissions: frozenset[str], confirmed_digest: str) -> CapabilityActionApproval:
        """Record an owner's denial; it cannot execute or alter the protected action."""
        self._policy.require(identity=approver_id, permissions=permissions,
                             capability_id=APPROVAL_MANAGEMENT_PERMISSION,
                             scope_type="principal", scope_id=approver_id)
        with self._lock:
            record = self._get_locked(approval_id)
            if record.status != "pending" or datetime.fromisoformat(record.expires_at) <= self._now():
                raise CapabilityApprovalError("Approval request is no longer pending")
            if approver_id != record.actor_id or confirmed_digest != record.approval_digest:
                raise CapabilityApprovalError("Owner confirmation does not match this exact action")
            denied = replace(record, status="denied", denied_by=approver_id,
                             denied_at=self._now().isoformat())
            self._record(approver_id, record.capability_id, "approval_denied", "denied",
                         record.approval_id)
            self._records[approval_id] = denied
            return denied

    def execute(self, approval_id: str, *, actor_id: str, permissions: frozenset[str],
                session_grants: frozenset[tuple[str, str, str]] = frozenset(),
                capability_id: str, action_id: str, action_summary: str, target_ref: str,
                scope_type: str, scope_id: str, payload_digest: str,
                current_policy_version: str,
                read_current_target_digest: Callable[[], str],
                operation: Callable[[], object]):
        record = self.get(approval_id)
        if record.status != "approved" or datetime.fromisoformat(record.expires_at) <= self._now():
            raise CapabilityApprovalError("Approval is not current and approved")
        bound = (record.actor_id, record.capability_id, record.action_id, record.action_summary,
                 record.target_ref, record.scope_type, record.scope_id,
                 record.payload_digest, record.policy_version)
        provided = (actor_id, capability_id, action_id, action_summary, target_ref, scope_type,
                    scope_id, payload_digest, current_policy_version)
        if bound != provided or current_policy_version != POLICY_VERSION:
            raise CapabilityApprovalError("Approved action, target, scope, or policy changed")
        self._policy.require(identity=actor_id, permissions=permissions,
                             capability_id=capability_id, scope_type=scope_type,
                             scope_id=scope_id, session_grants=session_grants)
        if read_current_target_digest() != record.target_digest:
            with self._lock:
                current = self._get_locked(approval_id)
                if current.status == "approved":
                    self._record(actor_id, capability_id, "stale", "stale", approval_id)
                    self._records[approval_id] = replace(current, status="stale")
            raise CapabilityApprovalError("Approved target state has changed")
        with self._lock:
            current = self._get_locked(approval_id)
            if current.status != "approved" or datetime.fromisoformat(current.expires_at) <= self._now():
                raise CapabilityApprovalError("Approval is no longer usable")
            consumed = replace(current, status="consumed", consumed_at=self._now().isoformat())
            self._record(actor_id, capability_id, "execution_started", "pending", approval_id)
            self._records[approval_id] = consumed
        try:
            result = operation()
        except Exception:
            self._record(actor_id, capability_id, "executed", "failure", approval_id)
            raise
        self._record(actor_id, capability_id, "executed", "success", approval_id)
        return result

    def _get_locked(self, approval_id: str) -> CapabilityActionApproval:
        record = self._records.get(approval_id)
        if record is None or not self._workspace_matches(record):
            raise CapabilityApprovalNotFound("Approval request is unavailable")
        return record

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Approval clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)


def _fingerprint(bound: dict) -> str:
    encoded = json.dumps(bound, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
