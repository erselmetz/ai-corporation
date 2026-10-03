from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.agents import Employee
from app.application import (
    EmployeeRoleChange,
    OrganizationPriority,
    WorkforceCapacityTarget,
)
from app.database import get_connection
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
PRIORITY = OrganizationPriority(
    "priority",
    "Maintain service reliability",
    "Caller-authored rationale",
    ("board-note-1",),
)


def _plan(runtime):
    return runtime.application_service.corporation_planning().build(
        (PRIORITY,), (), now=NOW
    )


def test_workforce_proposal_reports_headcount_and_role_change_without_mutation():
    runtime = create_corporation_runtime()
    employee = runtime.employees.get("local_employee")
    targets = (
        WorkforceCapacityTarget(
            "priority",
            "Local AI Worker",
            1,
            "Maintain one worker in the current role.",
            ("staffing-plan-1",),
        ),
        WorkforceCapacityTarget(
            "priority",
            "Research Lead",
            1,
            "Propose a lead position.",
            ("staffing-plan-2",),
        ),
    )
    change = EmployeeRoleChange(
        "priority",
        employee.id,
        employee.role,
        tuple(employee.responsibilities),
        "Research Lead",
        ("Research", "Planning"),
        "Caller-proposed role update.",
        ("role-review-1",),
    )
    before_employee = (
        employee.id,
        employee.name,
        employee.role,
        tuple(employee.responsibilities),
        employee.agent.id,
    )
    before_assignments = tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    )
    before_tasks = tuple(
        (task.id, task.status, task.assigned_agent) for task in runtime.tasks.all()
    )
    before_providers = tuple(runtime.providers.all())

    proposal = runtime.application_service.workforce_review().propose(
        "proposal-1",
        _plan(runtime),
        targets,
        (change,),
        created_at=NOW,
    )

    assert proposal.corporation_id == runtime.corporation.id
    assert proposal.proposal_id == "proposal-1"
    assert proposal.capacity_targets[0].current_headcount == 1
    assert proposal.capacity_targets[0].target_headcount == 1
    assert proposal.capacity_targets[1].current_headcount == 0
    assert proposal.capacity_targets[1].target_headcount == 1
    assert proposal.role_changes[0].current_role == "Local AI Worker"
    assert proposal.role_changes[0].proposed_role == "Research Lead"
    assert proposal.role_changes[0].current_responsibilities == ("General task execution",)
    assert proposal.role_changes[0].proposed_responsibilities == ("Research", "Planning")
    assert any("not applied, approved" in item for item in proposal.limitations)
    with pytest.raises(FrozenInstanceError):
        proposal.capacity_targets = ()

    assert (
        employee.id,
        employee.name,
        employee.role,
        tuple(employee.responsibilities),
        employee.agent.id,
    ) == before_employee
    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == before_assignments
    assert tuple(
        (task.id, task.status, task.assigned_agent) for task in runtime.tasks.all()
    ) == before_tasks
    assert tuple(runtime.providers.all()) == before_providers
    assert runtime.application_service._resource_manager is None
    connection = get_connection()
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='workforce_adjustments'"
        ).fetchone() is None
    finally:
        connection.close()


def test_role_change_requires_current_state_to_match_exact_employee_snapshot():
    runtime = create_corporation_runtime()
    employee = runtime.employees.get("local_employee")
    runtime.employees.get(employee.id).role = "Updated Role"
    change = EmployeeRoleChange(
        "priority",
        employee.id,
        "Local AI Worker",
        ("General task execution",),
        "Research Lead",
        ("Research",),
        "Caller-proposed role update.",
        ("role-review-1",),
    )

    with pytest.raises(ValueError, match="changed since"):
        runtime.application_service.workforce_review().propose(
            "proposal-stale",
            _plan(runtime),
            (),
            (change,),
            created_at=NOW,
        )


def test_workforce_proposal_rejects_unknown_priority_and_empty_adjustment():
    runtime = create_corporation_runtime()
    plan = _plan(runtime)
    with pytest.raises(ValueError, match="at least one explicit adjustment"):
        runtime.application_service.workforce_review().propose(
            "proposal-empty", plan, (), (), created_at=NOW
        )

    target = WorkforceCapacityTarget(
        "missing-priority", "Research Lead", 1, "Caller target", ("source-1",)
    )
    with pytest.raises(ValueError, match="reference a priority"):
        runtime.application_service.workforce_review().propose(
            "proposal-invalid-priority", plan, (target,), (), created_at=NOW
        )


@pytest.mark.parametrize(
    "construct",
    [
        lambda: WorkforceCapacityTarget("p", "role", True, "why", ("ref",)),
        lambda: WorkforceCapacityTarget("p", "role", 1001, "why", ("ref",)),
        lambda: WorkforceCapacityTarget("p", "role", 1, "why", []),
        lambda: EmployeeRoleChange(
            "p", "e", "role", [], "next", (), "why", ("ref",)
        ),
        lambda: EmployeeRoleChange(
            "p", "e", "role", (), "role", (), "why", ("ref",)
        ),
    ],
)
def test_workforce_inputs_are_bounded_immutable_and_non_noop(construct):
    with pytest.raises(ValueError):
        construct()


def test_workforce_service_requires_configured_corporation_and_employee_registry():
    from app.application.services.corporation import CorporationApplicationService

    runtime = create_corporation_runtime()
    with pytest.raises(RuntimeError, match="Corporation identity is not configured"):
        CorporationApplicationService(runtime.orchestrator).workforce_review()

    runtime.orchestrator.employees = None
    application = CorporationApplicationService(
        runtime.orchestrator, corporation=runtime.corporation
    )
    with pytest.raises(RuntimeError, match="Employee registry is not configured"):
        application.workforce_review()


def test_workforce_proposal_requires_timezone_aware_timestamp():
    runtime = create_corporation_runtime()
    with pytest.raises(ValueError):
        runtime.application_service.workforce_review().propose(
            "proposal-time",
            _plan(runtime),
            (WorkforceCapacityTarget("priority", "Role", 1, "why", ("ref",)),),
            (),
            created_at=datetime(2026, 10, 4),
        )


def test_workforce_review_rejects_a_roster_larger_than_its_scan_limit(monkeypatch):
    from app.application.services import workforce_review

    runtime = create_corporation_runtime()
    runtime.employees.register(
        Employee("second-employee", "Second Employee", "Researcher", ["Research"])
    )
    monkeypatch.setattr(workforce_review, "MAX_EMPLOYEES_SCANNED", 1)
    target = WorkforceCapacityTarget(
        "priority", "Researcher", 1, "Caller target", ("source-1",)
    )

    with pytest.raises(ValueError, match="bounded workforce review limit"):
        runtime.application_service.workforce_review().propose(
            "proposal-bounded-roster",
            _plan(runtime),
            (target,),
            (),
            created_at=NOW,
        )
