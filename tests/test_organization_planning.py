from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.application.services.organization_planning import (
    OrganizationConstraint,
    OrganizationPriority,
)
from app.database import get_connection
from app.orchestrator.task import Task, TaskStatus
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def priority(identifier, statement, reference):
    return OrganizationPriority(identifier, statement, "Caller-supplied rationale", (reference,))


def test_plan_preserves_explicit_order_constraints_and_trace_without_runtime_mutation():
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    runtime.tasks.register(Task("existing", "Existing Task", "Work", project_id=project.id,
                                status=TaskStatus.PENDING))
    priorities = (
        priority("p1", "Protect reliability", "board-note-1"),
        priority("p2", "Improve onboarding", "board-note-2"),
    )
    constraints = (
        OrganizationConstraint("c1", "No unapproved production changes", ("policy-7",), ("p1",)),
        OrganizationConstraint("c2", "Respect the approved budget", ("budget-2026",)),
    )
    tasks_before = tuple(runtime.tasks.all())
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    providers_before = tuple(runtime.providers.all())

    plan = runtime.application_service.corporation_planning().build(
        priorities, constraints, now=NOW
    )

    assert plan.corporation_id == runtime.corporation.id
    assert plan.created_at == NOW
    assert plan.priorities == priorities
    assert plan.constraints == constraints
    assert plan.priorities[0].id == "p1"
    assert plan.constraints[0].applies_to_priority_ids == ("p1",)
    assert plan.constraints[1].applies_to_priority_ids == ()
    assert tuple(runtime.tasks.all()) == tasks_before
    assert tuple((agent.id, agent.provider, agent.model) for agent in runtime.agents.all()) == assignments_before
    assert tuple(runtime.providers.all()) == providers_before
    with pytest.raises(FrozenInstanceError):
        plan.priorities = ()

    connection = get_connection()
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='organization_plans'"
        ).fetchone() is None
    finally:
        connection.close()


def test_plan_rejects_unconfigured_corporation_identity():
    from app.application.services.corporation import CorporationApplicationService

    runtime = create_corporation_runtime()
    application = CorporationApplicationService(runtime.orchestrator)
    with pytest.raises(RuntimeError, match="Corporation identity is not configured"):
        application.corporation_planning()


@pytest.mark.parametrize(
    "priorities, constraints, error",
    [
        ([], (), ValueError),
        ((), (), ValueError),
        (tuple(priority(str(index), "Goal", f"ref-{index}") for index in range(51)), (), ValueError),
        ((priority("same", "Goal", "ref"),), (OrganizationConstraint("same", "Limit", ("policy",)),), ValueError),
        ((priority("p1", "Goal", "ref"),), (OrganizationConstraint("c1", "Limit", ("policy",), ("missing",)),), ValueError),
        ((priority("p1", "Goal", "ref"),), [], ValueError),
        ((priority("p1", "Goal", "ref"),), ("not a constraint",), TypeError),
    ],
)
def test_invalid_plan_inputs_are_rejected(priorities, constraints, error):
    service = create_corporation_runtime().application_service.corporation_planning()
    with pytest.raises(error):
        service.build(priorities, constraints, now=NOW)


@pytest.mark.parametrize(
    "construct",
    [
        lambda: OrganizationPriority("p", "", "reason", ("ref",)),
        lambda: OrganizationPriority("p", "goal", "reason", []),
        lambda: OrganizationPriority("p", "goal", "reason", ("ref", "ref")),
        lambda: OrganizationConstraint("c", "limit", ("ref",), ["p"]),
        lambda: OrganizationConstraint("c", "limit", ("ref",), ("p", "p")),
    ],
)
def test_priority_and_constraint_inputs_are_bounded_immutable_records(construct):
    with pytest.raises(ValueError):
        construct()


def test_plan_requires_timezone_aware_timestamp():
    service = create_corporation_runtime().application_service.corporation_planning()
    with pytest.raises(ValueError):
        service.build((priority("p", "Goal", "ref"),), (), now=datetime(2026, 10, 4))
