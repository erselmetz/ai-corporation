"""Caller-authored, review-only Employee headcount and role-change proposals."""

from dataclasses import dataclass
from datetime import datetime

from app.agents import EmployeeRegistry
from app.memory.models import _identifier, _time
from .organization_planning import OrganizationPlan


MAX_EMPLOYEES_SCANNED = 1000


def _text(value: str, label: str, maximum_bytes: int = 1024) -> None:
    try:
        valid = (
            isinstance(value, str)
            and bool(value.strip())
            and len(value.encode("utf-8")) <= maximum_bytes
        )
    except UnicodeEncodeError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be nonempty text of at most {maximum_bytes} UTF-8 bytes")


def _references(references: tuple[str, ...], label: str) -> None:
    if not isinstance(references, tuple) or not 1 <= len(references) <= 10:
        raise ValueError(f"{label} must contain 1 to 10 immutable references")
    for reference in references:
        _text(reference, label)
    if len(set(references)) != len(references):
        raise ValueError(f"{label} must not contain duplicates")


def _responsibilities(values: tuple[str, ...], label: str) -> None:
    if not isinstance(values, tuple) or len(values) > 50:
        raise ValueError(f"{label} must be an immutable tuple of at most 50 responsibilities")
    for value in values:
        _text(value, label)
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must not contain duplicates")


@dataclass(frozen=True, slots=True)
class WorkforceCapacityTarget:
    priority_id: str
    role: str
    target_headcount: int
    rationale: str
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.priority_id, "priority_id")
        _text(self.role, "role", 256)
        if type(self.target_headcount) is not int or not 0 <= self.target_headcount <= MAX_EMPLOYEES_SCANNED:
            raise ValueError("target_headcount must be an integer from 0 to 1000")
        _text(self.rationale, "rationale")
        _references(self.source_references, "source_references")


@dataclass(frozen=True, slots=True)
class EmployeeRoleChange:
    priority_id: str
    employee_id: str
    expected_role: str
    expected_responsibilities: tuple[str, ...]
    proposed_role: str
    proposed_responsibilities: tuple[str, ...]
    rationale: str
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.priority_id, "priority_id")
        _identifier(self.employee_id, "employee_id")
        _text(self.expected_role, "expected_role", 256)
        _responsibilities(self.expected_responsibilities, "expected_responsibilities")
        _text(self.proposed_role, "proposed_role", 256)
        _responsibilities(self.proposed_responsibilities, "proposed_responsibilities")
        if (
            self.expected_role == self.proposed_role
            and self.expected_responsibilities == self.proposed_responsibilities
        ):
            raise ValueError("Employee role proposal must request a change")
        _text(self.rationale, "rationale")
        _references(self.source_references, "source_references")


@dataclass(frozen=True, slots=True)
class RoleCapacityAssessment:
    priority_id: str
    role: str
    current_headcount: int
    target_headcount: int
    rationale: str
    source_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EmployeeRoleAssessment:
    priority_id: str
    employee_id: str
    employee_name: str
    current_role: str
    current_responsibilities: tuple[str, ...]
    proposed_role: str
    proposed_responsibilities: tuple[str, ...]
    rationale: str
    source_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkforceAdjustmentProposal:
    corporation_id: str
    proposal_id: str
    created_at: datetime
    plan: OrganizationPlan
    capacity_targets: tuple[RoleCapacityAssessment, ...]
    role_changes: tuple[EmployeeRoleAssessment, ...]
    limitations: tuple[str, ...] = (
        "Adjustment targets, rationales, and source references are caller-authored and not independently verified.",
        "Capacity means Employee headcount by exact role, not Task 71 compute/resource capacity.",
        "Proposed role changes are not applied, approved, or reconciled to target headcounts.",
        "Employee records are read sequentially without an atomic cross-record snapshot.",
        "No Employee, Agent, model, Task, or resource assignment is changed.",
    )


class WorkforceReviewService:
    """Validate caller-authored workforce changes against current Employee records."""

    MAX_CAPACITY_TARGETS = 50
    MAX_ROLE_CHANGES = 100

    def __init__(self, corporation_id: str, employees: EmployeeRegistry) -> None:
        _identifier(corporation_id, "corporation_id")
        if not isinstance(employees, EmployeeRegistry):
            raise TypeError("employees must be an EmployeeRegistry")
        self._corporation_id = corporation_id
        self._employees = employees

    def propose(
        self,
        proposal_id: str,
        plan: OrganizationPlan,
        capacity_targets: tuple[WorkforceCapacityTarget, ...],
        role_changes: tuple[EmployeeRoleChange, ...],
        *,
        created_at: datetime,
    ) -> WorkforceAdjustmentProposal:
        _identifier(proposal_id, "proposal_id")
        if not isinstance(plan, OrganizationPlan):
            raise TypeError("Expected OrganizationPlan")
        if plan.corporation_id != self._corporation_id:
            raise ValueError("Plan belongs to a different Corporation")
        _time(created_at)
        _time(plan.created_at)
        if created_at < plan.created_at:
            raise ValueError("Proposal time precedes its organization plan")
        if not isinstance(capacity_targets, tuple) or len(capacity_targets) > self.MAX_CAPACITY_TARGETS:
            raise ValueError("Capacity targets must be an immutable tuple of at most 50 items")
        if not all(isinstance(item, WorkforceCapacityTarget) for item in capacity_targets):
            raise TypeError("Expected WorkforceCapacityTarget")
        if not isinstance(role_changes, tuple) or len(role_changes) > self.MAX_ROLE_CHANGES:
            raise ValueError("Role changes must be an immutable tuple of at most 100 items")
        if not all(isinstance(item, EmployeeRoleChange) for item in role_changes):
            raise TypeError("Expected EmployeeRoleChange")
        if not capacity_targets and not role_changes:
            raise ValueError("A workforce proposal requires at least one explicit adjustment")

        priority_ids = {item.id for item in plan.priorities}
        if any(
            item.priority_id not in priority_ids
            for item in (*capacity_targets, *role_changes)
        ):
            raise ValueError("Workforce adjustments must reference a priority in the plan")
        roles = tuple(item.role for item in capacity_targets)
        if len(set(roles)) != len(roles):
            raise ValueError("Capacity targets must contain one target per exact role")
        employee_ids = tuple(item.employee_id for item in role_changes)
        if len(set(employee_ids)) != len(employee_ids):
            raise ValueError("An Employee may have only one proposed role change")

        employees = self._employees.all_bounded(MAX_EMPLOYEES_SCANNED + 1)
        if len(employees) > MAX_EMPLOYEES_SCANNED:
            raise ValueError("Employee registry exceeds the bounded workforce review limit")
        for employee in employees:
            _text(employee.role, "employee role", 256)
        current_counts: dict[str, int] = {}
        for target in capacity_targets:
            current_counts[target.role] = sum(employee.role == target.role for employee in employees)
        capacities = tuple(
            RoleCapacityAssessment(
                item.priority_id,
                item.role,
                current_counts[item.role],
                item.target_headcount,
                item.rationale,
                item.source_references,
            )
            for item in capacity_targets
        )

        assessments = []
        for change in role_changes:
            employee = self._employees.get(change.employee_id)
            _text(employee.name, "employee name")
            _text(employee.role, "employee role", 256)
            current_responsibilities = tuple(employee.responsibilities)
            _responsibilities(current_responsibilities, "current_responsibilities")
            if (
                employee.role != change.expected_role
                or current_responsibilities != change.expected_responsibilities
            ):
                raise ValueError("Employee changed since the proposed current-state snapshot")
            assessments.append(
                EmployeeRoleAssessment(
                    change.priority_id,
                    employee.id,
                    employee.name,
                    employee.role,
                    current_responsibilities,
                    change.proposed_role,
                    change.proposed_responsibilities,
                    change.rationale,
                    change.source_references,
                )
            )

        return WorkforceAdjustmentProposal(
            self._corporation_id,
            proposal_id,
            created_at,
            plan,
            capacities,
            tuple(assessments),
        )
