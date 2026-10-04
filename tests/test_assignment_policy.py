from datetime import datetime, timezone
from decimal import Decimal

from app.application.services.assignment_policy import (
    AssignmentModelCandidate,
    AssignmentPolicy,
    AssignmentPolicyService,
    CapabilityEvidence,
)
from app.providers import AIProvider
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from app.runtime.factory import create_corporation_runtime


class Provider(AIProvider):
    def generate(self, model, prompt):
        raise AssertionError("Assignment recommendations must not call providers")


def setup():
    runtime = create_corporation_runtime()
    provider_ids = ("ollama", "local-two", "online-one", "online-two", "online-three")
    for provider_id in provider_ids[1:]:
        runtime.providers.register(provider_id, Provider())
    models = tuple((provider_id, f"model-{index}") for index, provider_id in enumerate(provider_ids))
    runtime.application_service.resource_manager(ResourceLimits(
        5,
        tuple(ProviderLimit(provider_id, 1) for provider_id in provider_ids),
        tuple(ModelLimit(provider_id, model_id, 1) for provider_id, model_id in models),
    ))
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    service = AssignmentPolicyService(runtime.application_service, clock=lambda: now)
    capabilities = tuple(runtime.application_service.get_agent("local_worker").capabilities)
    evidence = tuple(
        CapabilityEvidence(
            capability=capability,
            kind="tested",
            supports=True,
            reference=f"test-report-{capability}",
            observed_at=now,
        )
        for capability in capabilities
    )
    candidates = tuple(
        AssignmentModelCandidate(
            provider_id=provider_id,
            model_id=model_id,
            inventory_kind="local" if index < 2 else "online",
            inventory_models=(model_id,),
            inventory_reference=f"inventory-{provider_id}",
            inventory_observed_at=now,
            estimated_cost=Decimal("0.5"),
            evidence=evidence,
        )
        for index, (provider_id, model_id) in enumerate(models)
    )
    policy = AssignmentPolicy(
        enabled=True,
        allowed_provider_ids=provider_ids,
        online_enabled=True,
        budget_limit=Decimal("1"),
        budget_unit="owner-defined units per request",
        candidates=candidates,
    )
    return runtime, service, now, capabilities, candidates, policy


def test_two_local_and_three_online_inventory_preview_is_fresh_and_non_mutating():
    runtime, service, _, _, candidates, policy = setup()
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    service.configure("local-owner", policy)

    report = service.preview("local-owner")

    assert report["enabled"] is True
    assert report["budget_unit"] == "owner-defined units per request"
    assert len(report["assignments"]) == 1
    assignment = report["assignments"][0]
    assert assignment["recommendation"] == {
        "provider_id": candidates[0].provider_id,
        "model_id": candidates[0].model_id,
    }
    assert [item["inventory_kind"] for item in assignment["candidates"]] == [
        "local", "local", "online", "online", "online",
    ]
    assert all(item["eligible"] for item in assignment["candidates"])
    assert assignment["manual_assignment_preserved"] is True
    assert tuple((agent.id, agent.provider, agent.model) for agent in runtime.agents.all()) == assignments_before


def test_default_disable_owner_isolation_and_manual_assignment_are_preserved():
    runtime, service, _, _, _, policy = setup()
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    assert service.preview("local-owner")["enabled"] is False
    service.configure("local-owner", policy)
    assert service.preview("another-owner")["enabled"] is False
    disabled = service.disable("local-owner")
    assert disabled.enabled is False
    assert disabled.candidates == ()
    assert service.preview("local-owner")["assignments"] == []
    assert tuple((agent.id, agent.provider, agent.model) for agent in runtime.agents.all()) == assignments_before


def test_declared_stale_over_budget_unapproved_and_unconfigured_capacity_stay_ineligible():
    runtime, service, now, capabilities, candidates, policy = setup()
    candidate = candidates[0]
    declared = tuple(
        CapabilityEvidence(
            capability=capability,
            kind="declared",
            supports=True,
            reference="owner-declaration",
            observed_at=now,
        )
        for capability in capabilities
    )
    service.configure("owner", AssignmentPolicy(
        enabled=True,
        allowed_provider_ids=(),
        online_enabled=False,
        budget_limit=Decimal("0.1"),
        budget_unit="owner units",
        candidates=(AssignmentModelCandidate(
            provider_id=candidate.provider_id,
            model_id=candidate.model_id,
            inventory_kind="local",
            inventory_models=candidate.inventory_models,
            inventory_reference=candidate.inventory_reference,
            inventory_observed_at=now,
            estimated_cost=Decimal("0.5"),
            evidence=declared,
        ),),
    ))

    assessment = service.preview("owner")["assignments"][0]["candidates"][0]

    assert assessment["eligible"] is False
    assert "provider_not_allowed" in assessment["reasons"]
    assert "budget_exceeded" in assessment["reasons"]
    assert all(f"capability_not_tested:{item}" in assessment["reasons"] for item in capabilities)
    assert all("declared but not validated" in item for item in assessment["unknowns"] if "declared" in item)
    assert service.preview("owner")["assignments"][0]["recommendation"] is None


def test_stale_inventory_and_evidence_are_reported_without_silent_fallback():
    runtime, service, now, _, candidates, policy = setup()
    stale = candidates[0]
    stale_candidate = AssignmentModelCandidate(
        provider_id=stale.provider_id,
        model_id=stale.model_id,
        inventory_kind=stale.inventory_kind,
        inventory_models=stale.inventory_models,
        inventory_reference=stale.inventory_reference,
        inventory_observed_at=now.replace(year=2025),
        estimated_cost=stale.estimated_cost,
        evidence=tuple(
            CapabilityEvidence(item.capability, "tested", True, item.reference,
                               now.replace(year=2025))
            for item in stale.evidence
        ),
    )
    service.configure("owner", AssignmentPolicy(
        enabled=True,
        allowed_provider_ids=policy.allowed_provider_ids,
        online_enabled=True,
        budget_limit=policy.budget_limit,
        budget_unit=policy.budget_unit,
        candidates=(stale_candidate,),
    ))

    result = service.preview("owner")["assignments"][0]["candidates"][0]

    assert result["eligible"] is False
    assert result["reasons"].count("inventory_stale_or_future") == 1
    assert all("capability_not_tested:" + item in result["reasons"] for item in runtime.agents.get("local_worker").capabilities)
    assert "inventory freshness is not established" in result["unknowns"]


def test_online_candidates_require_explicit_policy_opt_in_and_unknown_roles_stay_unassigned():
    runtime, service, _, _, candidates, policy = setup()
    online = candidates[2]
    service.configure("owner", AssignmentPolicy(
        enabled=True,
        allowed_provider_ids=policy.allowed_provider_ids,
        online_enabled=False,
        budget_limit=policy.budget_limit,
        budget_unit=policy.budget_unit,
        candidates=(online,),
    ))
    online_result = service.preview("owner")["assignments"][0]
    assert online_result["recommendation"] is None
    assert "online_policy_disabled" in online_result["candidates"][0]["reasons"]
    assert any("provider health" in item for item in online_result["candidates"][0]["unknowns"])

    runtime.agents.get("local_worker").capabilities.clear()
    service.configure("owner", policy)
    unsupported = service.preview("owner")["assignments"][0]
    assert unsupported["recommendation"] is None
    assert all(
        "role_requirements_unknown" in item["reasons"]
        for item in unsupported["candidates"]
    )
