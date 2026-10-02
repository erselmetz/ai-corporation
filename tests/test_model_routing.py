from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.orchestrator.task import Task, TaskStatus
from app.providers import AvailabilityState
from app.resources import (
    ModelCandidate,
    ModelRoutingConstraints,
    ResourceLimits,
    ProviderLimit,
    ModelLimit,
    RoutingCandidate,
)
from app.runtime.factory import create_corporation_runtime


def candidate(provider, model, *, capabilities=("summarize",), tags=("approved",),
              availability=AvailabilityState.AVAILABLE, cost=Decimal("1")):
    return RoutingCandidate(
        ModelCandidate(provider, model),
        capabilities,
        tags,
        availability,
        cost,
    )


def setup_runtime():
    runtime = create_corporation_runtime()
    runtime.providers.register("second", runtime.providers.get("ollama"))
    runtime.application_service.resource_manager(
        ResourceLimits(
            1,
            (ProviderLimit("ollama", 1), ProviderLimit("second", 1)),
            (
                ModelLimit("ollama", "model-a", 1),
                ModelLimit("second", "model-b", 1),
            ),
        )
    )
    runtime.tasks.register(
        Task("routing-task", "Work", "Description", assigned_agent="local_worker")
    )
    return runtime


def test_selects_first_feasible_candidate_in_caller_order_and_reports_capacity_separately():
    runtime = setup_runtime()
    first = candidate("ollama", "model-a", cost=Decimal("3"))
    second = candidate("second", "model-b", cost=Decimal("2"))
    constraints = ModelRoutingConstraints(
        required_capabilities=("summarize",),
        allowed_provider_ids=("ollama", "second"),
        required_policy_tags=("approved",),
        max_cost=Decimal("4"),
    )
    tasks_before = tuple(runtime.tasks.all())
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    resource_manager = runtime.application_service.resource_manager()
    resource_manager.allocate("occupied", provider_id="ollama", model_id="model-a")
    resource_before = resource_manager.snapshot()

    result = runtime.application_service.select_model_candidate((first, second), constraints)

    assert result.selected == first.candidate
    assert tuple(item.candidate for item in result.candidates) == (first, second)
    assert all(item.eligible for item in result.candidates)
    assert all(not item.admission.configured_admission_eligible for item in result.candidates)
    assert all("global_exhausted" in item.admission.reasons for item in result.candidates)
    assert resource_manager.snapshot() == resource_before
    assert tuple(runtime.tasks.all()) == tasks_before
    assert runtime.tasks.get("routing-task").status is TaskStatus.PENDING
    assert tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    ) == assignments_before
    assert result.limitations
    with pytest.raises(FrozenInstanceError):
        result.selected = second.candidate


def test_capability_policy_and_unavailable_constraints_exclude_candidates():
    runtime = setup_runtime()
    wrong_capability = candidate(
        "ollama", "model-a", capabilities=("translate",)
    )
    wrong_policy = candidate(
        "second", "model-b", tags=("unapproved",)
    )
    unavailable = candidate(
        "ollama", "other", availability=AvailabilityState.UNAVAILABLE
    )

    result = runtime.application_service.select_model_candidate(
        (wrong_capability, wrong_policy, unavailable),
        ModelRoutingConstraints(
            required_capabilities=("summarize",),
            allowed_provider_ids=("second",),
            required_policy_tags=("approved",),
        ),
    )

    assert result.selected is None
    assert result.candidates[0].reasons == (
        "required_capability_missing",
        "provider_not_allowed",
    )
    assert result.candidates[1].reasons == ("required_policy_tag_missing",)
    assert result.candidates[2].reasons == (
        "provider_not_allowed",
        "provider_unavailable",
    )


def test_unknown_availability_requires_explicit_opt_in():
    runtime = setup_runtime()
    unknown = candidate("ollama", "model-a", availability=AvailabilityState.UNKNOWN)

    excluded = runtime.application_service.select_model_candidate(
        (unknown,), ModelRoutingConstraints()
    )
    allowed = runtime.application_service.select_model_candidate(
        (unknown,), ModelRoutingConstraints(allow_unknown_availability=True)
    )

    assert excluded.selected is None
    assert excluded.candidates[0].reasons == ("provider_availability_unknown",)
    assert allowed.selected == unknown.candidate


def test_missing_registered_provider_is_never_selected():
    runtime = setup_runtime()
    missing = candidate("missing", "model-c", availability=AvailabilityState.AVAILABLE)

    result = runtime.application_service.select_model_candidate(
        (missing,), ModelRoutingConstraints()
    )

    assert result.selected is None
    assert result.candidates[0].reasons == ("provider_missing",)


def test_cost_limit_excludes_unknown_and_over_budget_candidates_but_not_unpriced_without_limit():
    runtime = setup_runtime()
    unpriced = candidate("ollama", "model-a", cost=None)
    expensive = candidate("second", "model-b", cost=Decimal("5"))

    no_limit = runtime.application_service.select_model_candidate(
        (unpriced,), ModelRoutingConstraints()
    )
    limited = runtime.application_service.select_model_candidate(
        (unpriced, expensive),
        ModelRoutingConstraints(max_cost=Decimal("4")),
    )

    assert no_limit.selected == unpriced.candidate
    assert limited.selected is None
    assert limited.candidates[0].reasons == ("cost_unknown",)
    assert limited.candidates[1].reasons == ("cost_limit_exceeded",)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"capabilities": ["mutable"]},
        {"availability": "available"},
        {"cost": 1.0},
        {"cost": Decimal("-1")},
    ],
)
def test_routing_candidate_rejects_invalid_inputs(kwargs):
    with pytest.raises((TypeError, ValueError)):
        candidate("ollama", "model-a", **kwargs)


def test_constraints_and_candidate_batches_are_bounded_and_immutable():
    with pytest.raises(TypeError, match="immutable tuple"):
        ModelRoutingConstraints(allowed_provider_ids=["ollama"])
    with pytest.raises(ValueError, match="immutable tuple"):
        create_corporation_runtime().application_service.select_model_candidate(
            [candidate("ollama", "model-a")],
            ModelRoutingConstraints(),
        )
    with pytest.raises(ValueError, match="Duplicate model candidates"):
        create_corporation_runtime().application_service.select_model_candidate(
            (
                candidate("ollama", "model-a"),
                candidate("ollama", "model-a", cost=Decimal("2")),
            ),
            ModelRoutingConstraints(),
        )
