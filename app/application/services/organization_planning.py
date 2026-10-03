"""Bounded caller-defined organization plans; no inference or execution."""

from dataclasses import dataclass
from datetime import datetime

from app.memory.models import _identifier, _time


def _text(value: str, label: str) -> None:
    try:
        valid = isinstance(value, str) and bool(value.strip()) and len(value.encode("utf-8")) <= 1024
    except UnicodeEncodeError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be nonempty text of at most 1024 UTF-8 bytes")


def _references(references: tuple[str, ...], label: str) -> None:
    if not isinstance(references, tuple) or not 1 <= len(references) <= 10:
        raise ValueError(f"{label} must contain 1 to 10 immutable references")
    for reference in references:
        _text(reference, label)
    if len(set(references)) != len(references):
        raise ValueError(f"{label} must not contain duplicate references")


@dataclass(frozen=True, slots=True)
class OrganizationPriority:
    id: str
    statement: str
    rationale: str
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.id, "priority_id")
        _text(self.statement, "Priority statement")
        _text(self.rationale, "Priority rationale")
        _references(self.source_references, "Priority source references")


@dataclass(frozen=True, slots=True)
class OrganizationConstraint:
    id: str
    statement: str
    source_references: tuple[str, ...]
    applies_to_priority_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.id, "constraint_id")
        _text(self.statement, "Constraint statement")
        _references(self.source_references, "Constraint source references")
        if not isinstance(self.applies_to_priority_ids, tuple) or len(self.applies_to_priority_ids) > 50:
            raise ValueError("Constraint priority scope must be an immutable tuple of at most 50 IDs")
        for priority_id in self.applies_to_priority_ids:
            _identifier(priority_id, "priority_id")
        if len(set(self.applies_to_priority_ids)) != len(self.applies_to_priority_ids):
            raise ValueError("Constraint priority scope must not contain duplicate IDs")


@dataclass(frozen=True, slots=True)
class OrganizationPlan:
    corporation_id: str
    created_at: datetime
    priorities: tuple[OrganizationPriority, ...]
    constraints: tuple[OrganizationConstraint, ...]


class OrganizationPlanningService:
    """Snapshot explicit caller priorities and constraints without ranking or mutation."""

    MAX_PRIORITIES = 50
    MAX_CONSTRAINTS = 100

    def __init__(self, corporation_id: str):
        _identifier(corporation_id, "corporation_id")
        self._corporation_id = corporation_id

    def build(
        self,
        priorities: tuple[OrganizationPriority, ...],
        constraints: tuple[OrganizationConstraint, ...],
        *,
        now: datetime,
    ) -> OrganizationPlan:
        _time(now)
        if not isinstance(priorities, tuple) or not 1 <= len(priorities) <= self.MAX_PRIORITIES:
            raise ValueError("A Corporation plan requires 1 to 50 explicit priorities")
        if not all(isinstance(item, OrganizationPriority) for item in priorities):
            raise TypeError("Expected OrganizationPriority")
        if not isinstance(constraints, tuple) or len(constraints) > self.MAX_CONSTRAINTS:
            raise ValueError("Constraints must be an immutable tuple of at most 100 items")
        if not all(isinstance(item, OrganizationConstraint) for item in constraints):
            raise TypeError("Expected OrganizationConstraint")

        item_ids = tuple(item.id for item in priorities + constraints)
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("Priority and constraint IDs must be unique within the plan")
        priority_ids = {item.id for item in priorities}
        if any(not set(item.applies_to_priority_ids).issubset(priority_ids) for item in constraints):
            raise ValueError("Constraint scopes must reference priorities in this plan")

        return OrganizationPlan(self._corporation_id, now, priorities, constraints)
