"""Review-only model candidate selection from explicit caller-supplied facts."""

from dataclasses import dataclass
from decimal import Decimal

from app.providers import AvailabilityState

from .assessment import ModelCandidate, ModelResourceAssessment
from .manager import identifier


@dataclass(frozen=True, slots=True)
class RoutingCandidate:
    candidate: ModelCandidate
    capabilities: tuple[str, ...]
    policy_tags: tuple[str, ...]
    availability: AvailabilityState
    estimated_cost: Decimal | None = None

    def __post_init__(self):
        if not isinstance(self.candidate, ModelCandidate):
            raise TypeError("candidate must be a ModelCandidate")
        _validate_labels(self.capabilities, "capabilities")
        _validate_labels(self.policy_tags, "policy_tags")
        if not isinstance(self.availability, AvailabilityState):
            raise TypeError("availability must be an AvailabilityState")
        if self.estimated_cost is not None:
            _validate_cost(self.estimated_cost, "estimated_cost")


@dataclass(frozen=True, slots=True)
class ModelRoutingConstraints:
    required_capabilities: tuple[str, ...] = ()
    allowed_provider_ids: tuple[str, ...] | None = None
    required_policy_tags: tuple[str, ...] = ()
    max_cost: Decimal | None = None
    allow_unknown_availability: bool = False

    def __post_init__(self):
        _validate_labels(self.required_capabilities, "required_capabilities")
        _validate_labels(self.required_policy_tags, "required_policy_tags")
        if self.allowed_provider_ids is not None:
            if not isinstance(self.allowed_provider_ids, tuple):
                raise TypeError("allowed_provider_ids must be an immutable tuple")
            if any(not isinstance(value, str) for value in self.allowed_provider_ids):
                raise TypeError("allowed_provider_ids must contain strings")
            for provider_id in self.allowed_provider_ids:
                identifier(provider_id)
            if len(set(self.allowed_provider_ids)) != len(self.allowed_provider_ids):
                raise ValueError("allowed_provider_ids must not contain duplicates")
        if self.max_cost is not None:
            _validate_cost(self.max_cost, "max_cost")
        if not isinstance(self.allow_unknown_availability, bool):
            raise TypeError("allow_unknown_availability must be a bool")


@dataclass(frozen=True, slots=True)
class ModelRoutingCandidateAssessment:
    candidate: RoutingCandidate
    eligible: bool
    reasons: tuple[str, ...]
    admission: ModelResourceAssessment

    def __post_init__(self):
        if not isinstance(self.candidate, RoutingCandidate):
            raise TypeError("candidate must be a RoutingCandidate")
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be a bool")
        _validate_labels(self.reasons, "reasons")
        if self.eligible != (not self.reasons):
            raise ValueError("eligible must match whether reasons are empty")
        if not isinstance(self.admission, ModelResourceAssessment):
            raise TypeError("admission must be a ModelResourceAssessment")


@dataclass(frozen=True, slots=True)
class ModelRoutingSelection:
    selected: ModelCandidate | None
    candidates: tuple[ModelRoutingCandidateAssessment, ...]
    limitations: tuple[str, ...] = (
        "Caller-supplied candidate metadata, availability and cost estimates are not independently verified.",
        "Candidate order is the tie-break; this result does not modify assignments or execute Tasks.",
        "Task 71 configured admission capacity is reported separately and does not determine selection.",
        "Hardware feasibility remains unknown; Task 70 remains authoritative for atomic admission.",
    )

    def __post_init__(self):
        if self.selected is not None and not isinstance(self.selected, ModelCandidate):
            raise TypeError("selected must be a ModelCandidate or None")
        if not isinstance(self.candidates, tuple) or not all(
            isinstance(candidate, ModelRoutingCandidateAssessment)
            for candidate in self.candidates
        ):
            raise TypeError("candidates must be an immutable tuple of assessments")
        _validate_labels(self.limitations, "limitations")
        if self.selected is not None and not any(
            item.candidate.candidate == self.selected and item.eligible
            for item in self.candidates
        ):
            raise ValueError("selected candidate must be eligible")


def select_model_candidate(
    candidates: tuple[RoutingCandidate, ...],
    constraints: ModelRoutingConstraints,
    *,
    admission_assessments: tuple[ModelResourceAssessment, ...],
) -> ModelRoutingSelection:
    if not isinstance(candidates, tuple) or not 1 <= len(candidates) <= 100:
        raise ValueError("Supply an immutable tuple of 1 to 100 routing candidates")
    if not all(isinstance(candidate, RoutingCandidate) for candidate in candidates):
        raise TypeError("Expected RoutingCandidate")
    if not isinstance(constraints, ModelRoutingConstraints):
        raise TypeError("Expected ModelRoutingConstraints")
    if not isinstance(admission_assessments, tuple) or len(admission_assessments) != len(candidates):
        raise ValueError("Supply one admission assessment for each routing candidate")
    if not all(isinstance(item, ModelResourceAssessment) for item in admission_assessments):
        raise TypeError("Expected ModelResourceAssessment")
    if tuple(item.candidate for item in admission_assessments) != tuple(
        candidate.candidate for candidate in candidates
    ):
        raise ValueError("Admission assessments must match candidates in caller order")
    identities = tuple(candidate.candidate for candidate in candidates)
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate model candidates")

    assessments = []
    selected = None
    for candidate, admission in zip(candidates, admission_assessments):
        reasons = []
        if not admission.provider_registered:
            reasons.append("provider_missing")
        if not set(constraints.required_capabilities).issubset(candidate.capabilities):
            reasons.append("required_capability_missing")
        if (
            constraints.allowed_provider_ids is not None
            and candidate.candidate.provider_id not in constraints.allowed_provider_ids
        ):
            reasons.append("provider_not_allowed")
        if not set(constraints.required_policy_tags).issubset(candidate.policy_tags):
            reasons.append("required_policy_tag_missing")
        if candidate.availability is AvailabilityState.UNAVAILABLE:
            reasons.append("provider_unavailable")
        elif (
            candidate.availability is AvailabilityState.UNKNOWN
            and not constraints.allow_unknown_availability
        ):
            reasons.append("provider_availability_unknown")
        if constraints.max_cost is not None:
            if candidate.estimated_cost is None:
                reasons.append("cost_unknown")
            elif candidate.estimated_cost > constraints.max_cost:
                reasons.append("cost_limit_exceeded")
        eligible = not reasons
        if eligible and selected is None:
            selected = candidate.candidate
        assessments.append(
            ModelRoutingCandidateAssessment(candidate, eligible, tuple(reasons), admission)
        )
    return ModelRoutingSelection(selected, tuple(assessments))


def _validate_labels(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field} must be an immutable tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")


def _validate_cost(value: Decimal, field: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field} must be a Decimal")
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field} must be finite and non-negative")
