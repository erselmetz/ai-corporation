"""Bounded process-local, owner-created session grants for low-risk capabilities."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import threading
from uuid import uuid4

from .capability_authorization import CapabilityAuthorizationService


class CapabilityGrantConflict(Exception):
    pass


class CapabilityGrantNotFound(Exception):
    pass


@dataclass(frozen=True)
class CapabilityGrant:
    grant_id: str
    grantor: str
    capability_id: str
    scope_type: str
    scope_id: str
    session_id: str
    granted_at: str
    expires_at: str
    revoked_at: str | None

class CapabilityGrantService:
    MAX_GRANTS = 1000
    MAX_GRANTS_PER_SESSION = 100
    MAX_TTL_SECONDS = 3600

    def __init__(self, policy: CapabilityAuthorizationService, *, clock=None):
        self._policy = policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._grants: dict[str, CapabilityGrant] = {}
        self._enabled: dict[str, bool] = {}
        self._lock = threading.RLock()

    def set_audit_service(self, audit_service) -> None:
        self._audit = audit_service

    def _record(self, actor_id: str, capability_id: str, action_state: str,
                result_state: str, reference: str | None = None) -> None:
        if getattr(self, "_audit", None) is not None:
            self._audit.record(actor_id=actor_id, capability_id=capability_id,
                               permission_decision="allow", action_state=action_state,
                               result_state=result_state, safe_reference=reference)

    def enabled_snapshot(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple({"capability_id": definition.capability_id,
                          "enabled": self._enabled.get(definition.capability_id,
                                                        definition.default_enabled),
                          "default_enabled": definition.default_enabled,
                          "persistence": "process_only"}
                         for definition in self._policy.definitions
                         if "session" in definition.grant_modes and definition.risk == "low")

    def set_enabled(self, capability_id: str, *, enabled: bool, actor_id: str = "system") -> dict:
        definition = self._policy.definition(capability_id)
        if definition is None:
            raise CapabilityGrantNotFound("Capability is not registered")
        if ("session" not in definition.grant_modes or definition.risk != "low"
                or definition.scope_type != "principal"):
            raise CapabilityGrantConflict("Capability is not approved for owner enablement")
        if type(enabled) is not bool:
            raise ValueError("Capability enabled state must be boolean")
        self._record(actor_id, capability_id, "enabled" if enabled else "disabled", "success", actor_id)
        with self._lock:
            self._enabled[capability_id] = enabled
            if not enabled:
                now = self._clock().astimezone(timezone.utc).isoformat()
                for grant_id, grant in tuple(self._grants.items()):
                    if (grant.capability_id == capability_id and grant.revoked_at is None
                            and datetime.fromisoformat(grant.expires_at) > datetime.fromisoformat(now)):
                        self._grants[grant_id] = replace(grant, revoked_at=now)
            return {"capability_id": capability_id, "enabled": enabled,
                    "default_enabled": definition.default_enabled,
                    "persistence": "process_only"}

    def eligible(self, *, identity: str, permissions: frozenset[str]) -> tuple[dict, ...]:
        eligible = []
        for definition in self._policy.definitions:
            if ("session" not in definition.grant_modes or definition.risk != "low"
                    or definition.scope_type != "principal"
                    or not self._enabled.get(definition.capability_id, definition.default_enabled)
                    or definition.required_permissions.issubset(permissions)):
                continue
            eligible.append({"capability_id": definition.capability_id,
                             "scope_type": definition.scope_type,
                             "scope_id": identity, "risk": definition.risk})
        return tuple(eligible)

    def issue(self, *, grantor: str, permissions: frozenset[str], session_id: str,
              capability_id: str, scope_type: str, scope_id: str,
              ttl_seconds: int) -> CapabilityGrant:
        definition = self._policy.definition(capability_id)
        if definition is None:
            raise CapabilityGrantNotFound("Capability is not registered")
        if ("session" not in definition.grant_modes or definition.risk != "low"
                or definition.scope_type != "principal"):
            raise CapabilityGrantConflict("Capability is not approved for session grants")
        if not grantor or not session_id or scope_type != "principal" or scope_id != grantor:
            raise CapabilityGrantConflict("Grants are limited to the grantor's principal scope")
        if definition.required_permissions.issubset(permissions):
            raise CapabilityGrantConflict("The principal already has this legacy permission")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= self.MAX_TTL_SECONDS:
            raise ValueError("Session grant expiry must be between 1 and 3600 seconds")
        now = self._clock().astimezone(timezone.utc)
        with self._lock:
            if not self._enabled.get(capability_id, definition.default_enabled):
                raise CapabilityGrantConflict("Capability must be explicitly enabled first")
            active_for_session = [grant for grant in self._grants.values()
                                  if grant.session_id == session_id and grant.revoked_at is None
                                  and datetime.fromisoformat(grant.expires_at) > now]
            if len(self._grants) >= self.MAX_GRANTS or len(active_for_session) >= self.MAX_GRANTS_PER_SESSION:
                raise CapabilityGrantConflict("Session grant capacity is full")
            if any(grant.capability_id == capability_id and grant.scope_id == scope_id
                   and grant.session_id == session_id and grant.revoked_at is None
                   and datetime.fromisoformat(grant.expires_at) > now
                   for grant in self._grants.values()):
                raise CapabilityGrantConflict("An active grant already exists for this scope")
            grant = CapabilityGrant(uuid4().hex, grantor, capability_id, scope_type,
                                    scope_id, session_id, now.isoformat(),
                                    (now + timedelta(seconds=ttl_seconds)).isoformat(), None)
            self._record(grantor, capability_id, "granted", "success", grant.grant_id)
            self._grants[grant.grant_id] = grant
            return grant

    def list_for_session(self, *, grantor: str, session_id: str) -> tuple[CapabilityGrant, ...]:
        with self._lock:
            grants = [grant for grant in self._grants.values()
                      if grant.grantor == grantor and grant.session_id == session_id]
            return tuple(sorted(grants, key=lambda grant: grant.granted_at, reverse=True))

    def snapshot(self, grant: CapabilityGrant) -> dict:
        now = self._clock().astimezone(timezone.utc)
        status = ("revoked" if grant.revoked_at is not None else
                  "expired" if datetime.fromisoformat(grant.expires_at) <= now else "active")
        return {"grant_id": grant.grant_id, "grantor": grant.grantor,
                "capability_id": grant.capability_id, "scope_type": grant.scope_type,
                "scope_id": grant.scope_id, "session_id": grant.session_id,
                "granted_at": grant.granted_at, "expires_at": grant.expires_at,
                "revoked_at": grant.revoked_at, "status": status,
                "persistence": "session_only"}

    def active_keys(self, *, grantor: str, session_id: str) -> frozenset[tuple[str, str, str]]:
        now = self._clock().astimezone(timezone.utc)
        with self._lock:
            return frozenset((grant.capability_id, grant.scope_type, grant.scope_id)
                             for grant in self._grants.values()
                             if grant.grantor == grantor and grant.session_id == session_id
                             and self._enabled.get(grant.capability_id, False)
                             and grant.revoked_at is None
                             and datetime.fromisoformat(grant.expires_at) > now)

    def revoke(self, grant_id: str, *, grantor: str, session_id: str) -> CapabilityGrant:
        with self._lock:
            grant = self._grants.get(grant_id)
            if grant is None or grant.grantor != grantor or grant.session_id != session_id:
                raise CapabilityGrantNotFound("Session grant unavailable")
            if grant.revoked_at is not None:
                return grant
            if datetime.fromisoformat(grant.expires_at) <= self._clock().astimezone(timezone.utc):
                raise CapabilityGrantConflict("Expired session grants cannot be revoked")
            revoked = replace(grant, revoked_at=self._clock().astimezone(timezone.utc).isoformat())
            self._record(grantor, grant.capability_id, "revoked", "success", grant.grant_id)
            self._grants[grant_id] = revoked
            return revoked

    def revoke_session(self, session_id: str) -> None:
        timestamp = self._clock().astimezone(timezone.utc)
        now = timestamp.isoformat()
        with self._lock:
            for grant_id, grant in tuple(self._grants.items()):
                if (grant.session_id == session_id and grant.revoked_at is None
                        and datetime.fromisoformat(grant.expires_at) > timestamp):
                    self._grants[grant_id] = replace(grant, revoked_at=now)
