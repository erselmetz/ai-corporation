"""Central deny-by-default authorization for declared application capabilities."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Literal


CapabilityRisk = Literal["low", "moderate", "high"]
CapabilityGrantMode = Literal["session"]


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    scope_type: str
    required_permissions: frozenset[str]
    risk: CapabilityRisk
    default_enabled: bool = False
    grant_modes: frozenset[CapabilityGrantMode] = frozenset()


@dataclass(frozen=True)
class CapabilityAuthorizationDecision:
    capability_id: str
    scope_type: str
    scope_id: str
    risk: CapabilityRisk | None
    allowed: bool
    reason: str


class CapabilityAuthorizationDenied(PermissionError):
    pass


# Compatibility catalog: existing permission strings keep their identity and
# grant meaning. Adding a new route permission requires an explicit catalog entry.
_LEGACY_PERMISSION_NAMES = (
    "activity:read", "agent:read", "assignment-policy:manage", "assignment-policy:read",
    "chat-history:manage", "chat-knowledge:retain", "chat-knowledge:withdraw",
    "capability-approval:manage", "capability-audit:read", "capability-grant:manage", "chat-task:create", "chat:close", "chat:read", "chat:send", "chat:start",
    "corporation:read", "documentation:read", "documentation:review",
    "employee-chat:close", "employee-chat:read", "employee-chat:send", "employee-chat:start",
    "employee:manage", "employee:read", "github:read", "inventory:read",
    "local-model:select", "maintenance:activate", "maintenance:approve",
    "maintenance:checkpoint", "maintenance:experiment", "memory:index", "memory:manage",
    "memory:read", "model-runtime:manage", "model:manage", "model:read",
    "online-provider:connect", "online-provider:disconnect", "position:manage",
    "position:read", "project:create", "project:read", "provider-connection:manage",
    "provider-connection:read", "provider:manage", "provider:read", "software:manage",
    "software:read", "task:create", "task:dispatch", "task:read", "updates:read",
    "workflow:manage", "workflow:read",
)
_HIGH_RISK = frozenset({
    "maintenance:activate", "maintenance:approve", "maintenance:checkpoint",
    "maintenance:experiment", "task:dispatch", "software:manage", "provider-connection:manage",
    "online-provider:connect", "online-provider:disconnect", "chat-history:manage",
    "memory:manage", "memory:index", "documentation:review", "task:create", "capability-grant:manage",
    "capability-approval:manage",
    "capability-audit:read",
})
_MODERATE_RISK = frozenset({
    "assignment-policy:manage", "chat:send", "chat:start", "chat:close",
    "chat-task:create", "chat-knowledge:retain", "chat-knowledge:withdraw",
    "employee-chat:send", "employee-chat:start", "employee-chat:close", "employee:manage",
    "local-model:select", "model-runtime:manage", "model:manage", "position:manage",
    "project:create", "provider:manage", "workflow:manage",
})


def _legacy_definitions() -> tuple[CapabilityDefinition, ...]:
    definitions = []
    for permission in _LEGACY_PERMISSION_NAMES:
        risk: CapabilityRisk = (
            "high" if permission in _HIGH_RISK else
            "moderate" if permission in _MODERATE_RISK else "low"
        )
        definitions.append(CapabilityDefinition(
            capability_id=permission,
            scope_type="principal",
            required_permissions=frozenset({permission}),
            risk=risk,
            default_enabled=False,
            grant_modes=frozenset({"session"}) if risk == "low" else frozenset(),
        ))
    return tuple(definitions)


class CapabilityAuthorizationService:
    """Evaluate explicit principal grants against an immutable capability catalog."""

    def __init__(self, definitions: Iterable[CapabilityDefinition] | None = None):
        catalog = _legacy_definitions() if definitions is None else tuple(definitions)
        if any(not isinstance(item, CapabilityDefinition) for item in catalog):
            raise TypeError("Capability catalog entries must be CapabilityDefinition values")
        if len({item.capability_id for item in catalog}) != len(catalog):
            raise ValueError("Capability identifiers must be unique")
        for item in catalog:
            if (not item.capability_id.strip() or not item.scope_type.strip()
                    or not item.required_permissions
                    or any(not permission.strip() for permission in item.required_permissions)
                    or item.risk not in {"low", "moderate", "high"}
                    or not item.grant_modes.issubset({"session"})
                    or (item.grant_modes and item.risk != "low")
                    or not isinstance(item.default_enabled, bool)):
                raise ValueError("Capability definitions must be complete and valid")
        self._catalog = MappingProxyType({item.capability_id: item for item in catalog})

    @property
    def definitions(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._catalog.values())

    def definition(self, capability_id: str) -> CapabilityDefinition | None:
        return self._catalog.get(capability_id)

    def evaluate(self, *, identity: str, permissions: frozenset[str],
                 capability_id: str, scope_type: str, scope_id: str,
                 session_grants: frozenset[tuple[str, str, str]] = frozenset()) -> CapabilityAuthorizationDecision:
        definition = self._catalog.get(capability_id)
        reason = "capability_not_registered"
        allowed = False
        risk = None
        if definition is not None:
            risk = definition.risk
            reason = "scope_type_mismatch"
            if scope_type == definition.scope_type:
                reason = "scope_not_owned"
                principal_scope_owned = scope_type != "principal" or (identity and scope_id == identity)
                if principal_scope_owned and scope_id:
                    reason = "permission_not_granted"
                    grant_key = (capability_id, scope_type, scope_id)
                    legacy_grant = definition.required_permissions.issubset(permissions)
                    session_grant = "session" in definition.grant_modes and grant_key in session_grants
                    if legacy_grant or session_grant:
                        reason = "explicit_permission_granted"
                        allowed = True
        return CapabilityAuthorizationDecision(
            capability_id, scope_type, scope_id, risk, allowed, reason)

    def require(self, *, identity: str, permissions: frozenset[str],
                capability_id: str, scope_type: str, scope_id: str,
                session_grants: frozenset[tuple[str, str, str]] = frozenset()) -> CapabilityAuthorizationDecision:
        decision = self.evaluate(identity=identity, permissions=permissions,
                                 capability_id=capability_id, scope_type=scope_type,
                                 scope_id=scope_id, session_grants=session_grants)
        if not decision.allowed:
            raise CapabilityAuthorizationDenied(decision.reason)
        return decision


DEFAULT_CAPABILITY_AUTHORIZATION = CapabilityAuthorizationService()
