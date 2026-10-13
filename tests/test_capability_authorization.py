import pytest
from unittest.mock import MagicMock

from app.application.services.capability_authorization import (
    CapabilityAuthorizationDenied,
    CapabilityAuthorizationService,
    CapabilityDefinition,
)
from app.application.services.corporation import CorporationApplicationService
from app.orchestrator import Orchestrator


def test_catalog_is_separate_from_inventory_and_defaults_to_deny():
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("project.inspect", "project", frozenset({"project:read"}), "low"),
    ])
    assert policy.definitions[0].default_enabled is False
    assert policy.evaluate(identity="owner", permissions=frozenset(),
                           capability_id="project.inspect", scope_type="project",
                           scope_id="project-1").reason == "permission_not_granted"
    decision = policy.evaluate(identity="owner", permissions=frozenset({"project:read"}),
                               capability_id="project.inspect", scope_type="project",
                               scope_id="project-1")
    assert decision.allowed is True
    assert decision.risk == "low"


def test_unknown_capability_wrong_scope_and_foreign_principal_scope_are_denied():
    policy = CapabilityAuthorizationService([
        CapabilityDefinition("local.manage", "principal", frozenset({"local:manage"}), "high"),
    ])
    permissions = frozenset({"local:manage"})
    assert policy.evaluate(identity="owner", permissions=permissions,
                           capability_id="unknown", scope_type="principal",
                           scope_id="owner").reason == "capability_not_registered"
    assert policy.evaluate(identity="owner", permissions=permissions,
                           capability_id="local.manage", scope_type="project",
                           scope_id="owner").reason == "scope_type_mismatch"
    assert policy.evaluate(identity="owner", permissions=permissions,
                           capability_id="local.manage", scope_type="principal",
                           scope_id="someone-else").reason == "scope_not_owned"
    with pytest.raises(CapabilityAuthorizationDenied):
        policy.require(identity="owner", permissions=frozenset(),
                       capability_id="local.manage", scope_type="principal",
                       scope_id="owner")


def test_legacy_route_permissions_have_explicit_compatible_definitions():
    policy = CapabilityAuthorizationService()
    by_id = {definition.capability_id: definition for definition in policy.definitions}
    for permission in ("task:read", "task:dispatch", "documentation:review", "memory:manage", "browser:act"):
        definition = by_id[permission]
        assert definition.required_permissions == frozenset({permission})
        assert definition.scope_type == "principal"
        assert definition.default_enabled is False
    assert by_id["task:read"].risk == "low"
    assert by_id["task:dispatch"].risk == "high"
    assert by_id["browser:act"].risk == "high"


def test_application_service_uses_same_authorization_policy():
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    decision = service.authorize_capability(
        identity="owner", permissions=frozenset({"task:read"}),
        capability_id="task:read", scope_type="principal", scope_id="owner")
    assert decision.allowed is True
    with pytest.raises(CapabilityAuthorizationDenied):
        service.authorize_capability(
            identity="owner", permissions=frozenset(), capability_id="task:read",
            scope_type="principal", scope_id="owner")
