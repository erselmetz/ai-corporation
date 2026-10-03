from dataclasses import replace
from datetime import datetime, timezone
from difflib import unified_diff
import json
import shutil
import subprocess
from unittest.mock import patch

import pytest

from app.agents import Agent
from app.application import (
    CapabilityArtifactCheckStatus,
    CapabilityArtifactConsistency,
    CapabilityIntegrationStage,
    CapabilityIntegrationStatus,
    DiagnosticEvidence,
    DiagnosticReport,
    DetectedFailure,
    MaintenanceSandboxReport,
    MaintenanceSandboxStatus,
    MaintenanceWorkflowStage,
    MaintenanceWorkflowStatus,
    OrganizationPriority,
    OrganizationWorkflowSource,
    ResponsibilitySelection,
    RunStatus,
    TestRunReport as HostTestRunReport,
    WorkflowReference,
)
from app.approval import ApprovalStatus
from app.capability_discovery import CapabilityCandidate
from app.capability_evaluation import CapabilityEvaluationService
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


def _git(repository, *arguments):
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Git command failed: {arguments!r}: "
            f"{result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def _start_patch_workflow(tmp_path):
    runtime = create_corporation_runtime()
    task = Task(
        "workflow-task",
        "Maintenance review",
        "A failed Task for the maintenance workflow.",
        status=TaskStatus.FAILED,
        failure_category=TaskFailureCategory.EXECUTION,
    )
    runtime.tasks.register(task)
    failure = runtime.application_service.detect_failures().failures[0]
    workflow = runtime.application_service.start_maintenance_workflow(failure)
    diagnostic = DiagnosticReport(
        failure=failure,
        agent_id="workflow-reviewer",
        findings=(),
        unknowns=(),
        generated_at=datetime.now(timezone.utc),
    )
    runtime.application_service.record_maintenance_diagnostic(
        workflow.workflow_id,
        diagnostic,
    )
    proposal = runtime.application_service.create_maintenance_proposal(
        "workflow-proposal",
        diagnostic,
        title="Update module value",
        proposed_change="Change the module constant.",
        scope="module.py only",
        risk="The value changes.",
    )
    runtime.application_service.record_maintenance_proposal(
        workflow.workflow_id,
        proposal.proposal_id,
    )

    repository = tmp_path / "maintenance source"
    repository.mkdir()
    if shutil.which("git") is None:
        pytest.skip("Git executable is unavailable")
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "Workflow Test")
    _git(repository, "config", "user.email", "workflow@example.invalid")
    _git(repository, "config", "commit.gpgsign", "false")
    (repository / "module.py").write_bytes(b"value = 1\n")
    _git(repository, "add", "module.py")
    _git(repository, "commit", "-m", "initial")
    patch_text = "".join(
        unified_diff(
            ["value = 1\n"],
            ["value = 2\n"],
            fromfile="a/module.py",
            tofile="b/module.py",
        )
    )
    workspace = runtime.application_service.develop_patch(
        proposal.proposal_id,
        repository,
        ("module.py",),
        patch_text,
    )
    runtime.application_service.record_maintenance_patch(
        workflow.workflow_id,
        workspace.workspace_id,
    )
    return runtime, task, failure, workflow, diagnostic, proposal, workspace


def _passed_host_report(workspace):
    now = datetime.now(timezone.utc)
    return HostTestRunReport(
        run_id="workflow-host-run",
        proposal_id=workspace.proposal_id,
        workspace_id=workspace.workspace_id,
        selected_tests=("tests/test_module.py",),
        status=RunStatus.PASSED,
        return_code=0,
        output="",
        output_truncated=False,
        started_at=now,
        finished_at=now,
    )


def _review(runtime, workspace, evidence=None):
    agent = next(
        (item for item in runtime.agents.all() if item.id == "workflow-reviewer"),
        None,
    )
    if agent is None:
        agent = Agent(
            id="workflow-reviewer",
            name="Workflow Reviewer",
            role="Code Reviewer",
            provider="ollama",
            model="llama3.2:3b",
        )
        runtime.agents.register(agent)
    if evidence is None:
        evidence = (
            DiagnosticEvidence("approved-patch", workspace.unified_diff),
            DiagnosticEvidence("review-scope", "Review only this exact patch."),
        )
    with patch.object(
        runtime.providers.get(agent.provider),
        "generate",
        return_value=json.dumps(
            {
                "findings": [
                    {
                        "summary": "Review finding remains advisory.",
                        "severity": "high",
                        "area": "correctness",
                        "evidence_refs": [evidence[0].reference_id],
                    }
                ],
                "unknowns": [],
            }
        ),
    ) as generate:
        report = runtime.application_service.review_proposed_changes(
            agent.id,
            evidence,
        )
    generate.assert_called_once()
    return report, evidence


def test_workflow_records_explicit_stages_without_running_tasks_or_tests(tmp_path):
    (
        runtime,
        task,
        _failure,
        workflow,
        _diagnostic,
        _proposal,
        workspace,
    ) = _start_patch_workflow(tmp_path)
    runtime.agents.register(
        Agent(
            id="workflow-reviewer",
            name="Workflow Reviewer",
            role="Code Reviewer",
            provider="ollama",
            model="llama3.2:3b",
        )
    )
    tasks_before = tuple(replace(item) for item in runtime.tasks.all())
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    report = _passed_host_report(workspace)

    tested = runtime.application_service.record_maintenance_test_result(
        workflow.workflow_id,
        report,
    )
    review, evidence = _review(runtime, workspace)
    ready = runtime.application_service.record_maintenance_review(
        workflow.workflow_id,
        review,
        evidence,
    )

    assert tested.stage is MaintenanceWorkflowStage.TESTED
    assert ready.status is MaintenanceWorkflowStatus.READY_FOR_APPROVAL
    assert ready.review_finding_count == 1
    assert ready.review_evidence_sha256 == review.evidence_sha256
    assert runtime.application_service.list_pending_maintenance_approvals() == ()
    assert runtime.application_service.list_maintenance_checkpoints() == ()
    assert tuple(runtime.tasks.all()) == tasks_before
    assert runtime.tasks.get(task.id).status is TaskStatus.FAILED
    assert tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    ) == assignments_before
    events = runtime.orchestrator.logger.get_task_logs(task.id)
    workflow_events = [
        event for event in events if event["event"].startswith("MAINTENANCE_WORKFLOW_")
    ]
    assert [event["event"] for event in workflow_events] == [
        "MAINTENANCE_WORKFLOW_FAILURE_RECORDED",
        "MAINTENANCE_WORKFLOW_DIAGNOSED",
        "MAINTENANCE_WORKFLOW_PROPOSED",
        "MAINTENANCE_WORKFLOW_PATCHED",
        "MAINTENANCE_WORKFLOW_TESTED",
        "MAINTENANCE_WORKFLOW_REVIEWED",
    ]
    assert workspace.unified_diff not in str(workflow_events)
    assert runtime.application_service.get_maintenance_workflow(
        workflow.workflow_id
    ) == ready


def test_failed_test_is_terminal_and_cannot_be_reviewed(tmp_path):
    runtime, _task, _failure, workflow, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    now = datetime.now(timezone.utc)
    failed = HostTestRunReport(
        run_id="workflow-failed-run",
        proposal_id=workspace.proposal_id,
        workspace_id=workspace.workspace_id,
        selected_tests=("tests/test_module.py",),
        status=RunStatus.FAILED,
        return_code=1,
        output="failure details are not copied to the audit log",
        output_truncated=False,
        started_at=now,
        finished_at=now,
    )

    result = runtime.application_service.record_maintenance_test_result(
        workflow.workflow_id,
        failed,
    )

    assert result.status is MaintenanceWorkflowStatus.FAILED
    assert result.stage is MaintenanceWorkflowStage.TEST_FAILED
    with pytest.raises(ValueError, match="out of order or terminal"):
        runtime.application_service.record_maintenance_test_result(
            workflow.workflow_id,
            _passed_host_report(workspace),
        )
    review, evidence = _review(runtime, workspace)
    with pytest.raises(ValueError, match="out of order or terminal"):
        runtime.application_service.record_maintenance_review(
            workflow.workflow_id,
            review,
            evidence,
        )
    logs = runtime.orchestrator.logger.get_task_logs(result.task_id)
    message = "\n".join(str(item["message"]) for item in logs)
    assert "failure details" not in message


def test_review_requires_the_task81_evidence_digest_and_exact_patch(tmp_path):
    runtime, _task, _failure, workflow, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    runtime.application_service.record_maintenance_test_result(
        workflow.workflow_id,
        _passed_host_report(workspace),
    )
    review, evidence = _review(runtime, workspace)

    with pytest.raises(ValueError, match="does not match the supplied evidence"):
        runtime.application_service.record_maintenance_review(
            workflow.workflow_id,
            replace(review, evidence_sha256="0" * 64),
            evidence,
        )
    incorrect_patch = (DiagnosticEvidence("other-patch", "not the workspace diff"),)
    wrong_patch_review, _ = _review(runtime, workspace, incorrect_patch)
    with pytest.raises(ValueError, match="exact patch"):
        runtime.application_service.record_maintenance_review(
            workflow.workflow_id,
            wrong_patch_review,
            incorrect_patch,
        )
    assert runtime.application_service.get_maintenance_workflow(
        workflow.workflow_id
    ).stage is MaintenanceWorkflowStage.TESTED


def test_task82_pass_report_is_a_valid_explicit_test_stage(tmp_path):
    runtime, _task, _failure, workflow, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    now = datetime.now(timezone.utc)
    report = MaintenanceSandboxReport(
        run_id="workflow-sandbox-run",
        proposal_id=workspace.proposal_id,
        workspace_id=workspace.workspace_id,
        selected_tests=("tests/test_module.py",),
        status=MaintenanceSandboxStatus.PASSED,
        backend_id="docker",
        return_code=0,
        output="",
        output_truncated=False,
        started_at=now,
        finished_at=now,
        notes=(),
    )

    result = runtime.application_service.record_maintenance_test_result(
        workflow.workflow_id,
        report,
    )

    assert result.status is MaintenanceWorkflowStatus.ACTIVE
    assert result.stage is MaintenanceWorkflowStage.TESTED


def test_approval_and_checkpoint_remain_separate_task83_and_task84_actions(
    tmp_path,
):
    if shutil.which("git") is None:
        pytest.skip("Git executable is unavailable")
    runtime, _task, _failure, workflow, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    runtime.application_service.record_maintenance_test_result(
        workflow.workflow_id,
        _passed_host_report(workspace),
    )
    review, evidence = _review(runtime, workspace)
    runtime.application_service.record_maintenance_review(
        workflow.workflow_id,
        review,
        evidence,
    )

    pending = runtime.application_service.request_maintenance_approval(
        workspace.workspace_id
    )
    waiting = runtime.application_service.record_maintenance_approval(
        workflow.workflow_id,
        pending.request_id,
    )
    assert waiting.status is MaintenanceWorkflowStatus.AWAITING_APPROVAL
    approved = runtime.application_service.approve_maintenance_workspace(
        pending.request_id,
        approver_id="human-reviewer",
        patch_sha256=pending.patch_sha256,
        source_sha256=pending.source_sha256,
    )
    ready = runtime.application_service.record_maintenance_approval(
        workflow.workflow_id,
        approved.request_id,
    )
    assert ready.status is MaintenanceWorkflowStatus.APPROVED
    checkpoint = runtime.application_service.create_maintenance_checkpoint(
        workspace.workspace_id,
        created_by="checkpoint-operator",
    )
    complete = runtime.application_service.record_maintenance_checkpoint(
        workflow.workflow_id,
        checkpoint.checkpoint_id,
    )

    assert complete.status is MaintenanceWorkflowStatus.CHECKPOINTED
    assert len(complete.events) == 9
    assert complete.checkpoint_commit_sha == checkpoint.commit_sha
    assert complete.decision_by == "human-reviewer"
    assert complete.checkpoint_created_by == "checkpoint-operator"
    assert [event.stage for event in complete.events][-4:] == [
        MaintenanceWorkflowStage.REVIEWED,
        MaintenanceWorkflowStage.APPROVAL_PENDING,
        MaintenanceWorkflowStage.APPROVED,
        MaintenanceWorkflowStage.CHECKPOINTED,
    ]


def test_workflow_rejects_missing_or_nonfailed_task_and_out_of_order_stages():
    runtime = create_corporation_runtime()
    missing = DetectedFailure("missing-task", TaskFailureCategory.EXECUTION)
    with pytest.raises(ValueError):
        runtime.application_service.start_maintenance_workflow(missing)

    task = Task("pending-task", "Pending", "Not a failure.")
    runtime.tasks.register(task)
    failure = DetectedFailure(task.id, TaskFailureCategory.UNKNOWN)
    with pytest.raises(ValueError, match="no longer current"):
        runtime.application_service.start_maintenance_workflow(failure)

    task.status = TaskStatus.FAILED
    task.failure_category = TaskFailureCategory.UNKNOWN
    workflow = runtime.application_service.start_maintenance_workflow(failure)
    with pytest.raises(ValueError, match="out of order or terminal"):
        runtime.application_service.record_maintenance_proposal(
            workflow.workflow_id,
            "missing-proposal",
        )


def test_workflow_registry_has_a_fixed_capacity():
    runtime = create_corporation_runtime()
    task = Task(
        "capacity-task",
        "Failed Task",
        "Used to verify the workflow capacity.",
        status=TaskStatus.FAILED,
        failure_category=TaskFailureCategory.EXECUTION,
    )
    runtime.tasks.register(task)
    failure = runtime.application_service.detect_failures().failures[0]

    for _ in range(100):
        runtime.application_service.start_maintenance_workflow(failure)

    assert len(runtime.application_service.list_maintenance_workflows()) == 100
    with pytest.raises(ValueError, match="workflow limit"):
        runtime.application_service.start_maintenance_workflow(failure)


def test_capability_workflow_links_existing_change_control_without_activation(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("Git executable is unavailable")
    runtime, task, _failure, _maintenance, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    candidate = CapabilityCandidate(
        candidate_id="status-capability",
        name="Read-only status integration",
        description="Read service status without changing remote state.",
        source_reference="caller:status-source",
    )
    evaluation = CapabilityEvaluationService().evaluate(candidate, ())
    before_tasks = tuple((item.id, item.status) for item in runtime.tasks.all())

    started = runtime.application_service.start_capability_integration_workflow(
        candidate,
        evaluation,
        workspace.workspace_id,
    )
    assert started.status is CapabilityIntegrationStatus.ACTIVE
    assert started.events[0].stage is CapabilityIntegrationStage.CANDIDATE_LINKED
    assert any("not semantically verified" in item for item in started.limitations)

    tested = runtime.application_service.record_capability_integration_test_result(
        started.workflow_id,
        _passed_host_report(workspace),
    )
    review, evidence = _review(runtime, workspace)
    before_assignments = tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    )
    with patch.object(
        runtime.providers.get("ollama"),
        "generate",
        side_effect=AssertionError("Workflow record invoked a Provider"),
    ) as generate:
        reviewed = runtime.application_service.record_capability_integration_review(
            started.workflow_id,
            review,
            evidence,
        )
    generate.assert_not_called()

    pending = runtime.application_service.request_maintenance_approval(
        workspace.workspace_id
    )
    waiting = runtime.application_service.record_capability_integration_approval(
        started.workflow_id,
        pending.request_id,
    )
    approved_patch = runtime.application_service.approve_maintenance_workspace(
        pending.request_id,
        approver_id="human-reviewer",
        patch_sha256=pending.patch_sha256,
        source_sha256=pending.source_sha256,
    )
    approved = runtime.application_service.record_capability_integration_approval(
        started.workflow_id,
        approved_patch.request_id,
    )
    checkpoint = runtime.application_service.create_maintenance_checkpoint(
        workspace.workspace_id,
        created_by="checkpoint-operator",
    )
    checkpointed = (
        runtime.application_service.record_capability_integration_checkpoint(
            started.workflow_id,
            checkpoint.checkpoint_id,
        )
    )

    assert tested.stage is CapabilityIntegrationStage.TESTED
    assert reviewed.status is CapabilityIntegrationStatus.READY_FOR_APPROVAL
    assert waiting.status is CapabilityIntegrationStatus.AWAITING_APPROVAL
    assert approved.status is CapabilityIntegrationStatus.PATCH_APPROVED
    assert checkpointed.status is CapabilityIntegrationStatus.CHECKPOINTED
    assert checkpointed.checkpoint_commit_sha == checkpoint.commit_sha
    assert checkpointed.decision_by == "human-reviewer"
    assert checkpointed.checkpoint_created_by == "checkpoint-operator"
    assert [event.stage for event in checkpointed.events] == [
        CapabilityIntegrationStage.CANDIDATE_LINKED,
        CapabilityIntegrationStage.TESTED,
        CapabilityIntegrationStage.REVIEWED,
        CapabilityIntegrationStage.APPROVAL_PENDING,
        CapabilityIntegrationStage.PATCH_APPROVED,
        CapabilityIntegrationStage.CHECKPOINTED,
    ]
    assert workspace.unified_diff not in str(checkpointed.events)
    assert tuple((item.id, item.status) for item in runtime.tasks.all()) == before_tasks
    assert runtime.tasks.get(task.id).status is TaskStatus.FAILED
    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == before_assignments
    before_task_states = tuple((item.id, item.status) for item in runtime.tasks.all())
    with patch.object(
        runtime.providers.get("ollama"),
        "generate",
        side_effect=AssertionError("Pipeline review invoked a Provider"),
    ) as generate:
        report = runtime.application_service.review_capability_integration_pipeline()
    generate.assert_not_called()
    assessment = next(
        item for item in report.workflows if item.workflow.workflow_id == started.workflow_id
    )
    check_statuses = {
        check.artifact_kind: check.status for check in assessment.checks
    }
    assert assessment.workflow.status is CapabilityIntegrationStatus.CHECKPOINTED
    assert assessment.artifact_consistency is CapabilityArtifactConsistency.UNVERIFIABLE
    assert check_statuses["candidate_evaluation"] is CapabilityArtifactCheckStatus.CONSISTENT
    assert check_statuses["workspace"] is CapabilityArtifactCheckStatus.CONSISTENT
    assert check_statuses["test_result"] is CapabilityArtifactCheckStatus.UNVERIFIABLE
    assert check_statuses["review_evidence"] is CapabilityArtifactCheckStatus.UNVERIFIABLE
    assert check_statuses["approval"] is CapabilityArtifactCheckStatus.CONSISTENT
    assert check_statuses["checkpoint"] is CapabilityArtifactCheckStatus.CONSISTENT
    assert tuple((item.id, item.status) for item in runtime.tasks.all()) == before_task_states
    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == before_assignments


def test_capability_pipeline_review_detects_workspace_drift_without_mutation(
    tmp_path,
    monkeypatch,
):
    runtime, _task, _failure, _maintenance, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    candidate = CapabilityCandidate(
        candidate_id="pipeline-review-candidate",
        name="Read-only status integration",
        description="Read service status without changing remote state.",
        source_reference="caller:pipeline-review-source",
    )
    evaluation = CapabilityEvaluationService().evaluate(candidate, ())
    started = runtime.application_service.start_capability_integration_workflow(
        candidate,
        evaluation,
        workspace.workspace_id,
    )
    original_get = runtime.application_service._patch_development.get
    monkeypatch.setattr(
        runtime.application_service._patch_development,
        "get",
        lambda workspace_id: replace(
            original_get(workspace_id),
            patch_sha256="0" * 64,
        ),
    )

    report = runtime.application_service.review_capability_integration_pipeline()
    assessment = report.workflows[0]

    assert assessment.workflow.workflow_id == started.workflow_id
    assert assessment.artifact_consistency is CapabilityArtifactConsistency.INCONSISTENT
    assert next(
        check for check in assessment.checks if check.artifact_kind == "workspace"
    ).status is CapabilityArtifactCheckStatus.INCONSISTENT
    assert runtime.application_service.get_capability_integration_workflow(
        started.workflow_id
    ) == started


def test_capability_pipeline_review_is_empty_without_recorded_workflows():
    runtime = create_corporation_runtime()

    report = runtime.application_service.review_capability_integration_pipeline()

    assert report.workflows == ()


def test_capability_workflow_stops_on_test_failure_and_rejects_mismatched_artifacts(
    tmp_path,
):
    runtime, _task, _failure, _maintenance, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    candidate = CapabilityCandidate(
        candidate_id="status-capability",
        name="Read-only status integration",
        description="Read service status without changing remote state.",
        source_reference="caller:status-source",
    )
    evaluation = CapabilityEvaluationService().evaluate(candidate, ())
    started = runtime.application_service.start_capability_integration_workflow(
        candidate,
        evaluation,
        workspace.workspace_id,
    )
    passed = _passed_host_report(workspace)
    with pytest.raises(ValueError, match="does not match"):
        runtime.application_service.record_capability_integration_test_result(
            started.workflow_id,
            replace(passed, workspace_id="another-workspace"),
        )
    assert runtime.application_service.get_capability_integration_workflow(
        started.workflow_id
    ) == started

    failed = runtime.application_service.record_capability_integration_test_result(
        started.workflow_id,
        replace(passed, run_id="failed-capability-test", status=RunStatus.FAILED),
    )
    assert failed.status is CapabilityIntegrationStatus.TEST_FAILED
    with pytest.raises(ValueError, match="out of order or terminal"):
        runtime.application_service.record_capability_integration_test_result(
            started.workflow_id,
            passed,
        )
    assessment = runtime.application_service.review_capability_integration_pipeline().workflows[0]
    assert assessment.workflow.status is CapabilityIntegrationStatus.TEST_FAILED
    assert assessment.artifact_consistency is CapabilityArtifactConsistency.UNVERIFIABLE
    assert next(
        check for check in assessment.checks if check.artifact_kind == "test_result"
    ).status is CapabilityArtifactCheckStatus.UNVERIFIABLE


def test_task97_coordinates_registered_responsibility_and_approved_workflow_sources(
    tmp_path,
):
    runtime, task, _failure, maintenance, _diagnostic, _proposal, workspace = (
        _start_patch_workflow(tmp_path)
    )
    candidate = CapabilityCandidate(
        candidate_id="coordination-candidate",
        name="Read-only status integration",
        description="Read service status without changing remote state.",
        source_reference="caller:coordination-source",
    )
    evaluation = CapabilityEvaluationService().evaluate(candidate, ())
    capability = runtime.application_service.start_capability_integration_workflow(
        candidate,
        evaluation,
        workspace.workspace_id,
    )

    passed = _passed_host_report(workspace)
    runtime.application_service.record_maintenance_test_result(
        maintenance.workflow_id, passed
    )
    runtime.application_service.record_capability_integration_test_result(
        capability.workflow_id, passed
    )
    review, evidence = _review(runtime, workspace)
    runtime.application_service.record_maintenance_review(
        maintenance.workflow_id, review, evidence
    )
    runtime.application_service.record_capability_integration_review(
        capability.workflow_id, review, evidence
    )
    request = runtime.application_service.request_maintenance_approval(
        workspace.workspace_id
    )
    runtime.application_service.record_maintenance_approval(
        maintenance.workflow_id, request.request_id
    )
    runtime.application_service.record_capability_integration_approval(
        capability.workflow_id, request.request_id
    )
    approved = runtime.application_service.approve_maintenance_workspace(
        request.request_id,
        approver_id="human-reviewer",
        patch_sha256=request.patch_sha256,
        source_sha256=request.source_sha256,
    )
    maintenance = runtime.application_service.record_maintenance_approval(
        maintenance.workflow_id, approved.request_id
    )
    capability = runtime.application_service.record_capability_integration_approval(
        capability.workflow_id, approved.request_id
    )

    plan = runtime.application_service.corporation_planning().build(
        (
            OrganizationPriority(
                "priority",
                "Protect reliability",
                "Caller-supplied rationale",
                ("board-note-1",),
            ),
        ),
        (),
        now=datetime.now(timezone.utc),
    )
    selection = ResponsibilitySelection(
        "priority",
        "local_employee",
        "General task execution",
        (
            WorkflowReference(
                OrganizationWorkflowSource.MAINTENANCE,
                maintenance.workflow_id,
            ),
            WorkflowReference(
                OrganizationWorkflowSource.CAPABILITY_INTEGRATION,
                capability.workflow_id,
            ),
        ),
    )
    tasks_before = tuple(
        (item.id, item.status, item.assigned_agent) for item in runtime.tasks.all()
    )
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    )
    queue = runtime.application_service.execution_queue()
    queue_before = queue.list()
    maintenance_before = runtime.application_service.get_maintenance_workflow(
        maintenance.workflow_id
    )
    capability_before = runtime.application_service.get_capability_integration_workflow(
        capability.workflow_id
    )

    with (
        patch.object(
            runtime.providers.get("ollama"),
            "generate",
            side_effect=AssertionError("Coordination invoked a Provider"),
        ) as generate,
        patch.object(
            runtime.orchestrator,
            "execute_task",
            side_effect=AssertionError("Coordination executed a Task"),
        ) as execute_task,
        patch.object(
            runtime.orchestrator,
            "create_task",
            side_effect=AssertionError("Coordination created a Task"),
        ) as create_task,
        patch.object(
            runtime.orchestrator,
            "execution_queue",
            wraps=runtime.orchestrator.execution_queue,
        ) as queue_factory,
    ):
        report = runtime.application_service.organization_coordination().build(
            plan,
            (selection,),
            observed_at=datetime.now(timezone.utc),
        )

    generate.assert_not_called()
    execute_task.assert_not_called()
    create_task.assert_not_called()
    queue_factory.assert_not_called()
    assert report.plan == plan
    assert report.responsibilities[0].employee_id == "local_employee"
    assert report.responsibilities[0].employee_role == "Local AI Worker"
    assert report.responsibilities[0].responsibility == "General task execution"
    maintenance_result, capability_result = report.responsibilities[0].workflows
    assert maintenance_result.source is OrganizationWorkflowSource.MAINTENANCE
    assert maintenance_result.status is MaintenanceWorkflowStatus.APPROVED
    assert maintenance_result.approval_status is ApprovalStatus.APPROVED
    assert maintenance_result.patch_sha256 == workspace.patch_sha256
    assert capability_result.source is OrganizationWorkflowSource.CAPABILITY_INTEGRATION
    assert capability_result.status is CapabilityIntegrationStatus.PATCH_APPROVED
    assert capability_result.approval_status is ApprovalStatus.APPROVED
    assert capability_result.patch_sha256 == workspace.patch_sha256
    assert any("not capability adoption" in item for item in report.limitations)
    assert runtime.application_service.get_maintenance_workflow(
        maintenance.workflow_id
    ) == maintenance_before
    assert runtime.application_service.get_capability_integration_workflow(
        capability.workflow_id
    ) == capability_before
    assert tuple(
        (item.id, item.status, item.assigned_agent) for item in runtime.tasks.all()
    ) == tasks_before
    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == assignments_before
    assert queue.list() == queue_before
    with pytest.raises(RuntimeError, match="Resource limits are not configured"):
        runtime.application_service.resource_manager()
    assert runtime.tasks.get(task.id).status is TaskStatus.FAILED
