from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock, patch

import pytest

from app.agents import Agent
from app.orchestrator.collaboration import (
    CollaborationEventType,
    CollaborationFailureReason,
    CollaborationParticipant,
    CollaborationStatus,
)
from app.orchestrator.task import Task, TaskStatus
from app.runtime.factory import create_corporation_runtime


def setup_collaboration():
    runtime = create_corporation_runtime()
    second = Agent(
        id="reviewer",
        name="Reviewer",
        role="Reviewer",
        provider="ollama",
        model="llama3.2:3b",
    )
    runtime.agents.register(second)
    task = Task(
        "collaboration-task",
        "Review report",
        "Review the supplied report",
        assigned_agent="local_worker",
    )
    runtime.tasks.register(task)
    participants = (
        CollaborationParticipant("local_worker", "Local AI Worker"),
        CollaborationParticipant("reviewer", "Reviewer"),
    )
    return runtime, task, participants


def test_handoff_uses_explicit_registered_roles_and_shared_context_without_task_execution():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()
    initial_task = replace(task)
    assignments = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    provider = runtime.providers.get("ollama")
    generate = Mock(side_effect=AssertionError("Collaboration invoked a Provider"))
    with patch.object(provider, "generate", generate):
        started = service.start(
            "collaboration-1", task.id, participants, "Caller-supplied report context"
        )
        handed_off = service.handoff(
            "collaboration-1",
            "local_worker",
            "reviewer",
            "Caller-supplied review handoff",
        )
        completed = service.complete(
            "collaboration-1",
            "reviewer",
            "Caller-supplied review result",
        )
    generate.assert_not_called()
    assert service is runtime.application_service.task_collaboration()

    assert started.active_agent_id == "local_worker"
    assert started.participants == participants
    assert handed_off.active_agent_id == "reviewer"
    assert completed.status is CollaborationStatus.COMPLETED
    assert completed.active_agent_id is None
    assert tuple(event.type for event in completed.events) == (
        CollaborationEventType.INITIAL_CONTEXT,
        CollaborationEventType.HANDOFF,
        CollaborationEventType.COMPLETED,
    )
    assert completed.events[1].agent_id == "local_worker"
    assert completed.events[1].role == "Local AI Worker"
    assert completed.events[1].recipient_agent_id == "reviewer"
    assert completed.events[2].agent_id == "reviewer"
    assert service.get("collaboration-1") == completed
    assert runtime.tasks.get(task.id) == initial_task
    assert runtime.tasks.get(task.id).status is TaskStatus.PENDING
    assert tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    ) == assignments

    logs = runtime.orchestrator.logger.get_task_logs(task.id)
    events = [entry["event"] for entry in logs]
    assert events[-3:] == [
        "COLLABORATION_STARTED",
        "COLLABORATION_HANDOFF",
        "COLLABORATION_COMPLETED",
    ]
    messages = [entry["message"] for entry in logs if entry["event"].startswith("COLLABORATION_")]
    assert "Caller-supplied report context" not in "".join(messages)
    assert "Caller-supplied review handoff" not in "".join(messages)
    assert "Caller-supplied review result" not in "".join(messages)
    with pytest.raises(FrozenInstanceError):
        completed.status = CollaborationStatus.ACTIVE


def test_inactive_agent_cannot_impersonate_current_participant_or_skip_handoff():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()
    service.start("collaboration-2", task.id, participants, "initial")

    with pytest.raises(ValueError, match="not the active participant"):
        service.handoff("collaboration-2", "reviewer", "reviewer", "impersonated")
    with pytest.raises(ValueError, match="next listed participant"):
        service.handoff("collaboration-2", "local_worker", "local_worker", "skipped")
    with pytest.raises(ValueError, match="Only the final"):
        service.complete("collaboration-2", "local_worker", "early completion")

    assert service.get("collaboration-2").active_agent_id == "local_worker"
    assert len(service.get("collaboration-2").events) == 1


def test_participant_failure_is_terminal_and_does_not_change_task_lifecycle():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()
    service.start("collaboration-3", task.id, participants, "initial")
    failed = service.fail(
        "collaboration-3",
        "local_worker",
        CollaborationFailureReason.BLOCKED,
    )

    assert failed.status is CollaborationStatus.FAILED
    assert failed.failure_reason is CollaborationFailureReason.BLOCKED
    assert failed.events[-1].type is CollaborationEventType.FAILED
    assert failed.events[-1].agent_id == "local_worker"
    assert runtime.tasks.get(task.id).status is TaskStatus.PENDING
    with pytest.raises(ValueError, match="not active"):
        service.handoff("collaboration-3", "local_worker", "reviewer", "retry")


def test_start_requires_pending_task_distinct_registered_agents_and_exact_roles():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()

    with pytest.raises(ValueError, match="role does not match"):
        service.start(
            "bad-role",
            task.id,
            (
                CollaborationParticipant("local_worker", "Reviewer"),
                participants[1],
            ),
            "initial",
        )
    with pytest.raises(ValueError, match="only once"):
        service.start(
            "duplicate",
            task.id,
            (
                participants[0],
                CollaborationParticipant("local_worker", "Local AI Worker"),
            ),
            "initial",
        )
    runtime.tasks.update(replace(task, status=TaskStatus.RUNNING))
    with pytest.raises(ValueError, match="pending Task"):
        service.start("running-task", task.id, participants, "initial")


def test_handoff_is_bounded_and_collaboration_fails_if_task_leaves_pending_state():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()
    service.start("collaboration-4", task.id, participants, "initial")
    runtime.tasks.update(replace(task, status=TaskStatus.COMPLETED))

    with pytest.raises(ValueError, match="pending Task"):
        service.handoff("collaboration-4", "local_worker", "reviewer", "output")
    failed = service.fail(
        "collaboration-4",
        "local_worker",
        CollaborationFailureReason.BLOCKED,
    )
    assert failed.status is CollaborationStatus.FAILED
    assert runtime.tasks.get(task.id).status is TaskStatus.COMPLETED


def test_size_and_participant_bounds_are_enforced():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()

    with pytest.raises(ValueError, match="2 to 10"):
        service.start("one-agent", task.id, participants[:1], "context")
    with pytest.raises(ValueError, match="2 to 10"):
        service.start("too-many", task.id, participants * 6, "context")
    with pytest.raises(ValueError, match="byte limit"):
        service.start(
            "large-context",
            task.id,
            participants,
            "x" * (service.MAX_ENTRY_BYTES + 1),
        )
    service.start(
        "bounded",
        task.id,
        participants,
        "x" * service.MAX_ENTRY_BYTES,
    )
    with pytest.raises(ValueError, match="byte limit"):
        service.handoff(
            "bounded",
            "local_worker",
            "reviewer",
            "y" * (service.MAX_ENTRY_BYTES + 1),
        )


def test_total_shared_context_has_an_independent_workflow_limit():
    runtime, task, participants = setup_collaboration()
    additions = tuple(
        Agent(
            id=f"specialist-{index}",
            name=f"Specialist {index}",
            role=f"Specialist {index}",
            provider="ollama",
            model="llama3.2:3b",
        )
        for index in range(3)
    )
    for agent in additions:
        runtime.agents.register(agent)
    participants = participants + tuple(
        CollaborationParticipant(agent.id, agent.role) for agent in additions
    )
    service = runtime.application_service.task_collaboration()
    context_part = "x" * service.MAX_ENTRY_BYTES
    service.start("total-limit", task.id, participants, context_part)
    for index in range(3):
        service.handoff(
            "total-limit",
            participants[index].agent_id,
            participants[index + 1].agent_id,
            context_part,
        )

    with pytest.raises(ValueError, match="context exceeds byte limit"):
        service.handoff(
            "total-limit",
            participants[3].agent_id,
            participants[4].agent_id,
            context_part,
        )
    assert service.get("total-limit").active_agent_id == participants[3].agent_id


def test_audit_failure_does_not_create_or_advance_collaboration():
    runtime, task, participants = setup_collaboration()
    service = runtime.application_service.task_collaboration()

    with patch.object(runtime.orchestrator.logger, "log", side_effect=RuntimeError("audit failure")):
        with pytest.raises(RuntimeError, match="audit failure"):
            service.start("audit-fail", task.id, participants, "initial")

    with pytest.raises(ValueError, match="not found"):
        service.get("audit-fail")
    service.start("audit-ok", task.id, participants, "initial")
    previous = service.get("audit-ok")
    with patch.object(runtime.orchestrator.logger, "log", side_effect=RuntimeError("audit failure")):
        with pytest.raises(RuntimeError, match="audit failure"):
            service.handoff("audit-ok", "local_worker", "reviewer", "handoff")
    assert service.get("audit-ok") == previous
