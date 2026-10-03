from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch

import pytest

from app.application import DiagnosticEvidence
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


def create_diagnostic(runtime):
    task = Task(
        "proposal-diagnostic-task",
        "Failure",
        "Failed Task",
        status=TaskStatus.FAILED,
        failure_category=TaskFailureCategory.EXECUTION,
    )
    runtime.tasks.register(task)
    failure = runtime.application_service.detect_failures().failures[0]
    agent = runtime.agents.get("local_worker")
    with patch.object(
        runtime.providers.get(agent.provider),
        "generate",
        return_value='{"findings":[{"summary":"Supplied evidence indicates a timeout.",'
        '"evidence_refs":["trace-1"]}],"unknowns":[]}',
    ):
        return runtime.application_service.diagnose_failure(
            agent.id,
            failure,
            (DiagnosticEvidence("trace-1", "Caller-sanitized timeout observation."),),
        )


def test_caller_authored_proposal_is_immutable_local_and_review_only():
    runtime = create_corporation_runtime()
    diagnostic = create_diagnostic(runtime)
    before_task = runtime.tasks.get(diagnostic.failure.task_id)
    task_ids = {task.id for task in runtime.tasks.all()}
    provider = runtime.providers.get("ollama")
    generate = Mock(side_effect=AssertionError("Proposal creation invoked Provider"))
    with patch.object(provider, "generate", generate):
        proposal = runtime.application_service.create_maintenance_proposal(
            "proposal-1",
            diagnostic,
            title="Clarify timeout handling",
            proposed_change="Propose a bounded timeout response.",
            scope="Only the request adapter; do not modify task lifecycle.",
            risk="Could change retry behavior; retries remain explicitly out of scope.",
        )

    generate.assert_not_called()
    assert runtime.application_service.get_maintenance_proposal("proposal-1") is proposal
    assert runtime.application_service.list_maintenance_proposals() == (proposal,)
    assert proposal.diagnostic is diagnostic
    assert proposal.scope.startswith("Only the request adapter")
    assert proposal.risk.startswith("Could change retry behavior")
    assert runtime.tasks.get(diagnostic.failure.task_id) == before_task
    assert {task.id for task in runtime.tasks.all()} == task_ids
    assert runtime.orchestrator.logger.get_task_logs(diagnostic.failure.task_id) == []
    with pytest.raises(FrozenInstanceError):
        proposal.risk = "changed"


def test_proposals_require_diagnostic_and_bounded_nonempty_scope_and_risk():
    runtime = create_corporation_runtime()
    diagnostic = create_diagnostic(runtime)
    create = runtime.application_service.create_maintenance_proposal
    base = {
        "title": "Proposal",
        "proposed_change": "Change",
        "scope": "Bounded scope",
        "risk": "Explicit risk",
    }

    with pytest.raises(TypeError, match="DiagnosticReport"):
        create("bad-diagnostic", object(), **base)
    with pytest.raises(ValueError, match="scope cannot be empty"):
        create("empty-scope", diagnostic, **{**base, "scope": " "})
    with pytest.raises(ValueError, match="risk exceeds byte limit"):
        create("large-risk", diagnostic, **{**base, "risk": "x" * 2049})
    with pytest.raises(ValueError, match="proposed_change exceeds byte limit"):
        create(
            "large-change",
            diagnostic,
            **{**base, "proposed_change": "x" * 8193},
        )
    assert runtime.application_service.list_maintenance_proposals() == ()


def test_proposal_identity_is_unique_and_missing_proposal_is_distinct():
    runtime = create_corporation_runtime()
    diagnostic = create_diagnostic(runtime)
    create = runtime.application_service.create_maintenance_proposal
    fields = {
        "title": "Proposal",
        "proposed_change": "Change",
        "scope": "Bounded scope",
        "risk": "Explicit risk",
    }
    create("same-id", diagnostic, **fields)

    with pytest.raises(ValueError, match="already exists"):
        create("same-id", diagnostic, **fields)
    with pytest.raises(ValueError, match="not found"):
        runtime.application_service.get_maintenance_proposal("missing")
