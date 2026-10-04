"""Owner-managed, review-only model assignment recommendations."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import RLock

from app.resources import ModelCandidate

MAX_POLICY_CANDIDATES = 100
MAX_EVIDENCE_PER_CANDIDATE = 30
MAX_EVIDENCE_AGE = timedelta(days=30)
MAX_INVENTORY_AGE = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    capability: str
    kind: str
    supports: bool
    reference: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _text(self.capability, "capability", 128)
        if self.kind not in {"declared", "tested"}:
            raise ValueError("evidence kind must be declared or tested")
        if not isinstance(self.supports, bool):
            raise TypeError("supports must be a bool")
        _text(self.reference, "evidence reference", 512)
        _aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class AssignmentModelCandidate:
    provider_id: str
    model_id: str
    inventory_kind: str
    inventory_models: tuple[str, ...]
    inventory_reference: str
    inventory_observed_at: datetime
    estimated_cost: Decimal | None
    evidence: tuple[CapabilityEvidence, ...]

    def __post_init__(self) -> None:
        ModelCandidate(self.provider_id, self.model_id)
        if self.inventory_kind not in {"local", "online"}:
            raise ValueError("inventory_kind must be local or online")
        if (
            not isinstance(self.inventory_models, tuple)
            or not 1 <= len(self.inventory_models) <= 100
            or any(not isinstance(item, str) or not item.strip() for item in self.inventory_models)
            or len(set(self.inventory_models)) != len(self.inventory_models)
            or self.model_id not in self.inventory_models
        ):
            raise ValueError("inventory_models must include the unique candidate model")
        for item in self.inventory_models:
            _text(item, "inventory model", 256)
        _text(self.inventory_reference, "inventory reference", 512)
        _aware(self.inventory_observed_at, "inventory_observed_at")
        if self.estimated_cost is not None and (
            not isinstance(self.estimated_cost, Decimal)
            or not self.estimated_cost.is_finite()
            or self.estimated_cost < 0
        ):
            raise ValueError("estimated_cost must be a finite non-negative Decimal")
        if (
            not isinstance(self.evidence, tuple)
            or len(self.evidence) > MAX_EVIDENCE_PER_CANDIDATE
            or not all(isinstance(item, CapabilityEvidence) for item in self.evidence)
        ):
            raise TypeError("evidence must be a bounded immutable tuple")


@dataclass(frozen=True, slots=True)
class AssignmentPolicy:
    enabled: bool = False
    allowed_provider_ids: tuple[str, ...] = ()
    online_enabled: bool = False
    budget_limit: Decimal | None = None
    budget_unit: str | None = None
    candidates: tuple[AssignmentModelCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.online_enabled, bool):
            raise TypeError("enabled and online_enabled must be bools")
        if (
            not isinstance(self.allowed_provider_ids, tuple)
            or len(self.allowed_provider_ids) > MAX_POLICY_CANDIDATES
            or any(not isinstance(item, str) or not item.strip() for item in self.allowed_provider_ids)
            or len(set(self.allowed_provider_ids)) != len(self.allowed_provider_ids)
        ):
            raise ValueError("allowed_provider_ids must be a unique immutable tuple")
        for item in self.allowed_provider_ids:
            _text(item, "allowed provider ID", 256)
        if self.budget_limit is not None and (
            not isinstance(self.budget_limit, Decimal)
            or not self.budget_limit.is_finite()
            or self.budget_limit < 0
        ):
            raise ValueError("budget_limit must be a finite non-negative Decimal")
        if self.budget_unit is not None:
            _text(self.budget_unit, "budget_unit", 64)
        if not isinstance(self.candidates, tuple) or len(self.candidates) > MAX_POLICY_CANDIDATES:
            raise ValueError("candidates must be a bounded immutable tuple")
        if not all(isinstance(item, AssignmentModelCandidate) for item in self.candidates):
            raise TypeError("candidates must contain AssignmentModelCandidate values")
        keys = tuple((item.provider_id, item.model_id) for item in self.candidates)
        if len(set(keys)) != len(keys):
            raise ValueError("candidate provider/model pairs must be unique")
        if self.enabled and (not self.candidates or self.budget_limit is None or self.budget_unit is None):
            raise ValueError("enabled policy requires candidates and an explicit budget and unit")


class AssignmentPolicyService:
    """Keep a bounded per-owner policy in memory; previews never mutate assignments."""

    MAX_OWNERS = 8

    def __init__(self, application_service, *, clock=lambda: datetime.now(timezone.utc)):
        self._application = application_service
        self._clock = clock
        self._policies: dict[str, AssignmentPolicy] = {}
        self._lock = RLock()

    def get(self, owner_id: str) -> AssignmentPolicy:
        _text(owner_id, "owner_id", 256)
        with self._lock:
            return self._policies.get(owner_id, AssignmentPolicy())

    def configure(self, owner_id: str, policy: AssignmentPolicy) -> AssignmentPolicy:
        _text(owner_id, "owner_id", 256)
        if not isinstance(policy, AssignmentPolicy):
            raise TypeError("policy must be an AssignmentPolicy")
        with self._lock:
            if owner_id not in self._policies and len(self._policies) >= self.MAX_OWNERS:
                raise ValueError("assignment policy owner limit reached")
            self._policies[owner_id] = policy
        return policy

    def disable(self, owner_id: str) -> AssignmentPolicy:
        _text(owner_id, "owner_id", 256)
        with self._lock:
            self._policies.pop(owner_id, None)
            return AssignmentPolicy()

    def preview(self, owner_id: str) -> dict:
        policy = self.get(owner_id)
        if not policy.enabled:
            return {"enabled": False, "assignments": [], "limitations": _LIMITATIONS}
        candidates = tuple(
            ModelCandidate(item.provider_id, item.model_id)
            for item in policy.candidates
        )
        resources = self._application.assess_model_resources(candidates)
        agents = self._application.list_agents()
        now = self._clock()
        _aware(now, "clock")
        assignments = []
        for agent in agents:
            assessments = []
            for candidate, resource in zip(policy.candidates, resources):
                reasons, unknowns, references = self._assess(
                    candidate, resource, agent.capabilities, policy, now
                )
                assessments.append({
                    "provider_id": candidate.provider_id,
                    "model_id": candidate.model_id,
                    "eligible": not reasons,
                    "reasons": reasons,
                    "unknowns": unknowns,
                    "evidence_references": references,
                    "estimated_cost": (
                        str(candidate.estimated_cost)
                        if candidate.estimated_cost is not None else None
                    ),
                    "inventory_kind": candidate.inventory_kind,
                })
            selected = next((item for item in assessments if item["eligible"]), None)
            assignments.append({
                "agent_id": agent.id,
                "role": agent.role,
                "required_capabilities": list(agent.capabilities),
                "current_assignment": {
                    "provider_id": agent.provider,
                    "model_id": agent.model,
                },
                "recommendation": (
                    {"provider_id": selected["provider_id"], "model_id": selected["model_id"]}
                    if selected else None
                ),
                "candidates": assessments,
                "manual_assignment_preserved": True,
            })
        return {
            "enabled": True,
            "budget_limit": str(policy.budget_limit),
            "budget_unit": policy.budget_unit,
            "assignments": assignments,
            "limitations": _LIMITATIONS,
        }

    @staticmethod
    def _assess(candidate, resource, requirements, policy, now):
        reasons: list[str] = []
        unknowns: list[str] = [
            "provider health, model compatibility, hardware feasibility, and execution readiness are unknown"
        ]
        references: list[str] = [candidate.inventory_reference]
        if not requirements:
            reasons.append("role_requirements_unknown")
            unknowns.append("Agent declares no required capabilities")
        if candidate.provider_id not in policy.allowed_provider_ids:
            reasons.append("provider_not_allowed")
        if not resource.provider_registered:
            reasons.append("provider_missing")
        if candidate.inventory_kind == "online" and not policy.online_enabled:
            reasons.append("online_policy_disabled")
        age = now - candidate.inventory_observed_at
        if age < timedelta(0) or age > MAX_INVENTORY_AGE:
            reasons.append("inventory_stale_or_future")
            unknowns.append("inventory freshness is not established")
        if candidate.model_id not in candidate.inventory_models:
            reasons.append("model_not_in_inventory")
        if not resource.configured_admission_eligible:
            reasons.append("capacity_not_eligible")
            unknowns.extend(f"capacity:{reason}" for reason in resource.reasons)
        if policy.budget_limit is None or policy.budget_unit is None:
            reasons.append("budget_unknown")
            unknowns.append("an explicit policy budget and unit are required")
        elif candidate.estimated_cost is None:
            reasons.append("cost_unknown")
            unknowns.append("candidate cost estimate is not supplied")
        elif candidate.estimated_cost > policy.budget_limit:
            reasons.append("budget_exceeded")

        for capability in requirements:
            matching = [item for item in candidate.evidence if item.capability == capability]
            fresh = [
                item for item in matching
                if timedelta(0) <= now - item.observed_at <= MAX_EVIDENCE_AGE
            ]
            references.extend(item.reference for item in fresh)
            tested = [item for item in fresh if item.kind == "tested"]
            if any(not item.supports for item in tested):
                reasons.append(f"capability_test_failed:{capability}")
            elif any(item.supports for item in tested):
                continue
            else:
                reasons.append(f"capability_not_tested:{capability}")
                if any(item.supports for item in fresh):
                    unknowns.append(f"{capability} is declared but not validated by a test")
                elif matching:
                    unknowns.append(f"{capability} evidence is stale")
                else:
                    unknowns.append(f"{capability} has no evidence")
        return list(dict.fromkeys(reasons)), list(dict.fromkeys(unknowns)), list(dict.fromkeys(references))


_LIMITATIONS = (
    "Capability evidence, model inventories, and cost estimates are owner-supplied and not independently verified.",
    "Only fresh positive tested capability evidence qualifies; declarations are shown as unknown.",
    "Capacity is a non-reserving Task 71 admission snapshot, not hardware feasibility or execution readiness.",
    "Provider health, model compatibility, and execution performance are not assessed.",
    "Online recommendations do not connect a provider, grant cloud consent, or send data.",
    "Recommendations never change assignments; disabling the policy leaves manual assignments untouched.",
    "Policy state is in-memory and is lost on restart.",
)


def _aware(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def _text(value: str, field: str, limit: int) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > limit
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field} must be bounded non-empty text")
