from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from app.application.services.task_planning import OutcomeCriteria, PlanningRequest
from app.database import get_connection
from app.memory import MemoryRecord, MemoryScope, MemoryType, ConversationMemoryStore
from app.orchestrator.task import Task, TaskStatus
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
CRITERIA = OutcomeCriteria("Artifact satisfies requirement", "Human reviews saved artifact", "Approved review with artifact reference")


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    for identifier, status in [("a", TaskStatus.COMPLETED), ("b", TaskStatus.PENDING), ("c", TaskStatus.FAILED)]:
        runtime.tasks.register(Task(identifier, identifier, "Work", project_id=project.id, status=status))
    return runtime, project.id


def request(identifier, dependencies=()):
    return PlanningRequest(identifier, dependencies, (CRITERIA,))


def build(runtime, project, requests, **kwargs):
    return runtime.application_service.task_planning().build(project, requests, actor_id="owner", now=NOW, **kwargs)


def test_dependency_order_status_and_unverified_outcomes_without_mutation(setup):
    runtime, project = setup
    before = tuple(replace(task) for task in runtime.tasks.all())
    plan = build(runtime, project, (request("c", ("b",)), request("b", ("a",)), request("a")))
    assert [task.task_id for task in plan.tasks] == ["a", "b", "c"]
    assert plan.tasks[1].unmet_dependencies == ()
    assert plan.tasks[2].unmet_dependencies == ("b",)
    assert plan.tasks[0].status is TaskStatus.COMPLETED
    assert all(not task.outcomes_verified for task in plan.tasks)
    assert plan.tasks[0].outcomes == (CRITERIA,)
    assert plan.context is None
    assert tuple(runtime.tasks.all()) == before
    with pytest.raises(FrozenInstanceError):
        plan.tasks[0].title = "Changed"
    runtime.tasks.update(replace(runtime.tasks.get("b"), status=TaskStatus.COMPLETED))
    assert plan.tasks[1].status is TaskStatus.PENDING
    assert build(runtime, project, (request("c", ("b",)), request("b"))).tasks[1].unmet_dependencies == ()


def test_determinism_for_unordered_requests(setup):
    runtime, project = setup
    first = (request("c"), request("a"), request("b"))
    assert build(runtime, project, first) == build(runtime, project, tuple(reversed(first)))


@pytest.mark.parametrize("requests", [(), (request("a"), request("a")), (request("missing"),),
    (request("a", ("b",)),), (request("a", ("b",)), request("b", ("a",)))])
def test_invalid_graphs_rejected_without_task_changes(setup, requests):
    runtime, project = setup
    before = tuple(replace(task) for task in runtime.tasks.all())
    with pytest.raises(ValueError):
        build(runtime, project, requests)
    assert tuple(runtime.tasks.all()) == before


def test_cross_project_and_unassociated_tasks_rejected(setup):
    runtime, project = setup
    other = runtime.application_service.create_project("Other", "")
    for identifier, project_id in [("other", other.id), ("legacy", None)]:
        runtime.tasks.register(Task(identifier, identifier, "Work", project_id=project_id))
        with pytest.raises(ValueError, match="exact Project"):
            build(runtime, project, (request(identifier),))


@pytest.mark.parametrize("construct", [
    lambda: OutcomeCriteria("", "Check", "Evidence"),
    lambda: OutcomeCriteria("x" * 1025, "Check", "Evidence"),
    lambda: PlanningRequest("a", ("a",), (CRITERIA,)),
    lambda: PlanningRequest("a", ("b", "b"), (CRITERIA,)),
    lambda: PlanningRequest("a", [], (CRITERIA,)),
    lambda: PlanningRequest("a", (), ()),
    lambda: PlanningRequest("a", (), ("fabricated",)),
])
def test_request_contracts_require_bounded_immutable_explicit_criteria(construct):
    with pytest.raises((ValueError, TypeError)):
        construct()


def test_plan_limits_and_missing_context_scope_rejected(setup):
    runtime, project = setup
    with pytest.raises(ValueError):
        build(runtime, project, tuple(request(str(i)) for i in range(51)))
    with pytest.raises(ValueError, match="Context requires"):
        build(runtime, project, (request("a"),), context_query="alpha")
    with pytest.raises(ValueError, match="match the planned Project"):
        build(runtime, project, (request("a"),), context_query="alpha",
              context_scope=MemoryScope.PROJECT, context_scope_id="other")


def test_explicit_context_authority_trace_expiry_and_no_persistence(setup):
    runtime, project = setup
    for identifier, owner in [("private", "owner"), ("other", "outsider")]:
        ConversationMemoryStore().retain(MemoryRecord(identifier, owner, MemoryScope.CONVERSATION,
            "chat", MemoryType.NOTE, "alpha context", "message", NOW, NOW + timedelta(hours=1), True), now=NOW)
    plan = build(runtime, project, (request("a"),), context_query="alpha",
                 context_scope=MemoryScope.CONVERSATION, context_scope_id="chat")
    assert [hit.source.memory_id for hit in plan.context.hits] == ["private"]
    assert plan.context.hits[0].source.original_reference == "message"
    assert plan.context.hits[0].source.expires_at == NOW + timedelta(hours=1)
    connection = get_connection()
    try:
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 3
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name='task_plans'").fetchall()
    finally:
        connection.close()
