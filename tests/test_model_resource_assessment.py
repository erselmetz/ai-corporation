from dataclasses import FrozenInstanceError, replace

import pytest

from app.providers import AIProvider
from app.resources import ResourceLimits, ProviderLimit, ModelLimit, ResourceCapacityError
from app.resources.assessment import ModelCandidate, assess_model_resources
from app.resources.manager import ResourceSnapshot, Capacity
from app.orchestrator.task import Task, TaskStatus
from app.runtime.factory import create_corporation_runtime

MODEL = "llama3.2:3b"
CANDIDATE = ModelCandidate("ollama", MODEL)

class Provider(AIProvider):
    def __init__(self):
        self.calls = 0
    def generate(self, model, prompt):
        self.calls += 1
        return "Deterministic reply"

def setup(global_slots=3, provider_slots=2, model_slots=2):
    runtime = create_corporation_runtime()
    provider = Provider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    runtime.providers.register("q", provider)
    resource = runtime.application_service.resource_manager(ResourceLimits(global_slots,
        (ProviderLimit("ollama", provider_slots), ProviderLimit("q", 2)),
        (ModelLimit("ollama", MODEL, model_slots), ModelLimit("ollama", "other", 2), ModelLimit("q", MODEL, 2))))
    return runtime, provider, resource

def assess(runtime, candidates=(CANDIDATE,)):
    return runtime.application_service.assess_model_resources(candidates)

def test_eligible_immutable_non_reserving_snapshot_and_no_assignments_or_calls():
    runtime, provider, resource = setup()
    runtime.tasks.register(Task("task", "Work", "Description", assigned_agent="local_worker"))
    tasks = tuple(replace(task) for task in runtime.tasks.all())
    agents = tuple((agent.id, agent.provider, agent.model) for agent in runtime.agents.all())
    before = resource.snapshot()
    result = assess(runtime)[0]
    assert result.configured_admission_eligible and result.reasons == ()
    assert result.global_configured and result.provider_configured and result.model_configured
    assert result.global_capacity.remaining == 3
    assert result.provider_capacity.remaining == 2
    assert result.model_capacity.remaining == 2
    assert result.hardware_feasibility == result.provider_health == "unknown"
    assert result.allocation_id_semantics == "fresh_unique_id"
    assert result.allocation_id_history_capacity.remaining == resource.MAX_ALLOCATION_IDS
    assert result.limitations
    with pytest.raises(FrozenInstanceError):
        result.configured_admission_eligible = False
    assert resource.snapshot() == before
    assert tuple(runtime.tasks.all()) == tasks
    assert tuple((agent.id, agent.provider, agent.model) for agent in runtime.agents.all()) == agents
    assert provider.calls == 0

@pytest.mark.parametrize("kind", ["global", "provider", "model"])
def test_each_exhausted_budget_is_reported(kind):
    runtime, provider, resource = setup(global_slots=1 if kind == "global" else 3,
        provider_slots=1 if kind == "provider" else 2, model_slots=1 if kind == "model" else 2)
    resource.allocate("active", provider_id="q" if kind == "global" else "ollama",
                      model_id="other" if kind == "provider" else MODEL)
    result = assess(runtime)[0]
    assert result.reasons == (kind + "_exhausted",)
    assert not result.configured_admission_eligible
    assert provider.calls == 0

def test_removed_provider_reported_missing_without_health_claim():
    runtime, provider, _ = setup()
    runtime.providers.remove("ollama")
    result = assess(runtime)[0]
    assert not result.provider_registered
    assert result.reasons == ("provider_missing",)
    assert not result.configured_admission_eligible
    assert result.provider_health == "unknown"
    assert provider.calls == 0

def test_unconfigured_global_provider_model_and_history_are_not_invented():
    runtime = create_corporation_runtime()
    result = assess(runtime)[0]
    assert result.provider_registered
    assert not result.global_configured and not result.provider_configured and not result.model_configured
    assert result.global_capacity is result.provider_capacity is result.model_capacity is None
    assert result.allocation_id_history_capacity is None
    assert result.reasons == ("global_unconfigured", "provider_unconfigured", "model_unconfigured", "allocation_history_unknown")
    with pytest.raises(RuntimeError):
        runtime.application_service.resource_manager()

def test_individually_unconfigured_candidates_and_stable_input_order():
    runtime, _, _ = setup()
    candidates = (ModelCandidate("q", "unknown"), ModelCandidate("unknown-provider", "m"), CANDIDATE)
    results = assess(runtime, candidates)
    assert tuple(result.candidate for result in results) == candidates
    assert results[0].reasons == ("model_unconfigured",)
    assert results[1].reasons == ("provider_missing", "provider_unconfigured", "model_unconfigured")
    assert results[2].configured_admission_eligible

def test_history_exhaustion_prevents_eligibility_with_all_slots_free():
    runtime, provider, resource = setup()
    old = assess(runtime)[0]
    for index in range(resource.MAX_ALLOCATION_IDS):
        resource.allocate(str(index), provider_id="ollama", model_id=MODEL)
        resource.release(str(index))
    result = assess(runtime)[0]
    assert result.global_capacity.remaining == 3
    assert result.provider_capacity.remaining == result.model_capacity.remaining == 2
    assert result.reasons == ("allocation_history_exhausted",)
    assert not result.configured_admission_eligible
    assert result.allocation_id_history_capacity.remaining == 0
    assert old.configured_admission_eligible
    with pytest.raises(ResourceCapacityError, match="history limit"):
        resource.allocate("fresh", provider_id="ollama", model_id=MODEL)
    assert provider.calls == 0

def test_stale_assessment_is_not_reservation_and_controlled_execution_rechecks():
    runtime, provider, resource = setup(global_slots=1)
    runtime.tasks.register(Task("task", "Work", "Description", assigned_agent="local_worker"))
    old = assess(runtime)[0]
    resource.allocate("outside", provider_id="ollama", model_id=MODEL)
    assert old.configured_admission_eligible
    assert not assess(runtime)[0].configured_admission_eligible
    with pytest.raises(ResourceCapacityError):
        runtime.application_service.execute_controlled_task("task")
    assert runtime.tasks.get("task").status is TaskStatus.PENDING
    assert provider.calls == 0
    resource.release("outside")
    assert assess(runtime)[0].configured_admission_eligible
    assert runtime.application_service.execute_controlled_task("task").status == "completed"
    assert provider.calls == 1

@pytest.mark.parametrize("candidates", [(), [CANDIDATE], (CANDIDATE, CANDIDATE), ("invalid",),
    tuple(ModelCandidate("ollama", str(index)) for index in range(101))])
def test_candidate_requests_are_bounded_typed_and_explicit(candidates):
    runtime = create_corporation_runtime()
    with pytest.raises((ValueError, TypeError)):
        assess(runtime, candidates)

def test_old_snapshot_unknown_history_fails_closed():
    old = ResourceSnapshot(Capacity(1, 0), (("ollama", Capacity(1, 0)),),
        (("ollama", MODEL, Capacity(1, 0)),), (), ("ollama",))
    result = assess_model_resources((CANDIDATE,), snapshot=old, registered_providers=("ollama",))[0]
    assert result.reasons == ("allocation_history_unknown",)
    assert not result.configured_admission_eligible

def test_registered_provider_with_no_configured_limits_is_explicitly_unconfigured():
    runtime, provider, _ = setup()
    runtime.providers.register("unconfigured", provider)
    result = assess(runtime, (ModelCandidate("unconfigured", "model"),))[0]
    assert result.provider_registered
    assert result.global_configured
    assert not result.provider_configured and not result.model_configured
    assert result.reasons == ("provider_unconfigured", "model_unconfigured")
    assert not result.configured_admission_eligible
    assert provider.calls == 0
