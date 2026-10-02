"""Non-reserving admission assessments, never physical compute feasibility."""
from dataclasses import dataclass

from .manager import Capacity, ResourceSnapshot, identifier


@dataclass(frozen=True)
class ModelCandidate:
    provider_id: str
    model_id: str

    def __post_init__(self):
        identifier(self.provider_id)
        identifier(self.model_id)


@dataclass(frozen=True)
class ModelResourceAssessment:
    candidate: ModelCandidate
    provider_registered: bool
    global_capacity: Capacity | None
    provider_capacity: Capacity | None
    model_capacity: Capacity | None
    allocation_id_history_capacity: Capacity | None
    configured_admission_eligible: bool
    reasons: tuple[str, ...]
    hardware_feasibility: str = "unknown"
    provider_health: str = "unknown"
    allocation_id_semantics: str = "fresh_unique_id"
    limitations: tuple[str, ...] = (
        "Non-reserving local snapshot; capacity and registration may change immediately.",
        "Refresh before decisions; Task 70 atomically rechecks and reserves actual admission.",
        "Eligibility does not prove hardware feasibility, provider health, model loading, or successful execution.",
        "No preference ranking, model assignment, or Task routing is implied.",
    )

    @property
    def global_configured(self):
        return self.global_capacity is not None

    @property
    def provider_configured(self):
        return self.provider_capacity is not None

    @property
    def model_configured(self):
        return self.model_capacity is not None


def assess_model_resources(candidates, *, snapshot: ResourceSnapshot | None, registered_providers):
    if not isinstance(candidates, tuple) or not 1 <= len(candidates) <= 100:
        raise ValueError("Supply an immutable tuple of 1 to 100 model candidates")
    if not all(isinstance(candidate, ModelCandidate) for candidate in candidates):
        raise TypeError("Expected ModelCandidate")
    if len(set(candidates)) != len(candidates):
        raise ValueError("Duplicate model candidates")
    if snapshot is not None and not isinstance(snapshot, ResourceSnapshot):
        raise TypeError("Expected ResourceSnapshot")
    registered = frozenset(registered_providers)
    providers = dict(snapshot.providers) if snapshot is not None else {}
    models = {(provider, model): capacity for provider, model, capacity in snapshot.models} if snapshot is not None else {}
    global_capacity = snapshot.global_capacity if snapshot is not None else None
    history = snapshot.allocation_id_history_capacity if snapshot is not None else None
    assessments = []
    for candidate in candidates:
        exists = candidate.provider_id in registered
        provider = providers.get(candidate.provider_id)
        model = models.get((candidate.provider_id, candidate.model_id))
        reasons = []
        if not exists:
            reasons.append("provider_missing")
        for name, capacity in (("global", global_capacity), ("provider", provider), ("model", model)):
            if capacity is None:
                reasons.append(name + "_unconfigured")
            elif capacity.remaining <= 0:
                reasons.append(name + "_exhausted")
        if history is None:
            reasons.append("allocation_history_unknown")
        elif history.remaining <= 0:
            reasons.append("allocation_history_exhausted")
        assessments.append(ModelResourceAssessment(candidate, exists, global_capacity, provider, model,
                                                    history, not reasons, tuple(reasons)))
    return tuple(assessments)
