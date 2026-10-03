from datetime import datetime, timezone
from difflib import unified_diff

from fastapi.testclient import TestClient
import pytest

from app.approval import ApprovalStatus
from app.api import AuthenticatedPrincipal, create_app
from app.application import DiagnosticReport
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


class Authentication:
    def __init__(self, identity="reviewer-1", permissions=frozenset()):
        self.identity = identity
        self.permissions = permissions

    def authenticate(self, _request):
        return AuthenticatedPrincipal(self.identity, self.permissions)


def prepare_workspace(tmp_path):
    runtime = create_corporation_runtime()
    task = Task(
        "approval-task",
        "Maintenance review",
        "A task used to associate the diagnostic report.",
        status=TaskStatus.FAILED,
        failure_category=TaskFailureCategory.EXECUTION,
    )
    runtime.tasks.register(task)
    failure = runtime.application_service.detect_failures().failures[0]
    diagnostic = DiagnosticReport(
        failure=failure,
        agent_id="local_worker",
        findings=(),
        unknowns=(),
        generated_at=datetime.now(timezone.utc),
    )
    proposal = runtime.application_service.create_maintenance_proposal(
        "approval-proposal",
        diagnostic,
        title="Change one value",
        proposed_change="Update the constant.",
        scope="module.py only",
        risk="The value changes.",
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(b"value = 1\n")
    patch = "".join(
        unified_diff(
            ["value = 1\n"],
            ["value = 2\n"],
            fromfile="a/module.py",
            tofile="b/module.py",
        )
    )
    workspace = runtime.application_service.develop_patch(
        proposal.proposal_id,
        source_root,
        ("module.py",),
        patch,
    )
    return runtime, workspace, patch


def decision_payload(review, decision):
    return {
        "decision": decision,
        "patch_sha256": review["patch_sha256"],
        "source_sha256": review["source_sha256"],
    }


def test_request_exposes_exact_patch_and_fails_closed_until_approved(tmp_path):
    runtime, workspace, patch = prepare_workspace(tmp_path)
    application = runtime.application_service

    review = application.request_maintenance_approval(workspace.workspace_id)

    assert review.status is ApprovalStatus.PENDING
    assert review.workspace_id == workspace.workspace_id
    assert review.proposal_id == workspace.proposal_id
    assert review.patch_sha256 == workspace.patch_sha256
    assert review.source_sha256 == workspace.source_sha256
    assert review.changed_files == ("module.py",)
    assert review.unified_diff == patch
    assert review.decided_by is None
    assert review.decided_at is None
    pending = application.list_pending_maintenance_approvals()
    assert len(pending) == 1
    assert pending[0].request_id == review.request_id
    assert pending[0].status is ApprovalStatus.PENDING
    assert not hasattr(pending[0], "unified_diff")
    with pytest.raises(PermissionError, match="approved human review"):
        application.require_approved_maintenance_workspace(workspace.workspace_id)


def test_approval_records_authenticated_reviewer_and_is_workspace_specific(tmp_path):
    runtime, workspace, _patch = prepare_workspace(tmp_path)
    application = runtime.application_service
    review = application.request_maintenance_approval(workspace.workspace_id)

    with pytest.raises(PermissionError, match="Decision hashes"):
        application.approve_maintenance_workspace(
            review.request_id,
            approver_id="reviewer-1",
            patch_sha256="0" * 64,
            source_sha256=review.source_sha256,
        )
    assert application.get_maintenance_approval(
        review.request_id
    ).status is ApprovalStatus.PENDING

    approved = application.approve_maintenance_workspace(
        review.request_id,
        approver_id="reviewer-1",
        patch_sha256=review.patch_sha256,
        source_sha256=review.source_sha256,
    )
    assert approved.status is ApprovalStatus.APPROVED
    assert approved.decided_by == "reviewer-1"
    assert approved.decided_at is not None
    assert application.require_approved_maintenance_workspace(
        workspace.workspace_id
    ) == approved
    with pytest.raises(RuntimeError, match="Must be pending"):
        application.reject_maintenance_workspace(
            review.request_id,
            approver_id="reviewer-2",
            patch_sha256=review.patch_sha256,
            source_sha256=review.source_sha256,
        )

    source_root = tmp_path / "other-source"
    source_root.mkdir()
    (source_root / "other.py").write_bytes(b"value = 1\n")
    other_proposal = runtime.application_service.create_maintenance_proposal(
        "other-proposal",
        workspace_diagnostic(runtime, workspace),
        title="Different patch",
        proposed_change="Change another file.",
        scope="other.py only",
        risk="The value changes.",
    )
    other_workspace = application.develop_patch(
        other_proposal.proposal_id,
        source_root,
        ("other.py",),
        "".join(
            unified_diff(
                ["value = 1\n"],
                ["value = 3\n"],
                fromfile="a/other.py",
                tofile="b/other.py",
            )
        ),
    )
    with pytest.raises(PermissionError, match="approved human review"):
        application.require_approved_maintenance_workspace(
            other_workspace.workspace_id
        )


def workspace_diagnostic(runtime, workspace):
    return runtime.application_service.get_maintenance_proposal(
        workspace.proposal_id
    ).diagnostic


def test_decision_rejects_missing_actor_and_stale_workspace(tmp_path):
    runtime, workspace, _patch = prepare_workspace(tmp_path)
    application = runtime.application_service
    review = application.request_maintenance_approval(workspace.workspace_id)

    with pytest.raises(ValueError, match="Approver identity"):
        application.approve_maintenance_workspace(
            review.request_id,
            approver_id=" ",
            patch_sha256=review.patch_sha256,
            source_sha256=review.source_sha256,
        )

    application.dispose_patch_workspace(workspace.workspace_id)
    with pytest.raises(PermissionError, match="unavailable or has changed"):
        application.approve_maintenance_workspace(
            review.request_id,
            approver_id="reviewer-1",
            patch_sha256=review.patch_sha256,
            source_sha256=review.source_sha256,
        )


def test_rejection_records_reviewer_and_never_satisfies_approval_gate(tmp_path):
    runtime, workspace, _patch = prepare_workspace(tmp_path)
    application = runtime.application_service
    review = application.request_maintenance_approval(workspace.workspace_id)

    rejected = application.reject_maintenance_workspace(
        review.request_id,
        approver_id="reviewer-1",
        patch_sha256=review.patch_sha256,
        source_sha256=review.source_sha256,
    )

    assert rejected.status is ApprovalStatus.REJECTED
    assert rejected.decided_by == "reviewer-1"
    assert rejected.decided_at is not None
    with pytest.raises(PermissionError, match="approved human review"):
        application.require_approved_maintenance_workspace(workspace.workspace_id)


def test_api_requires_approval_permission_and_records_principal_identity(tmp_path):
    runtime, workspace, patch = prepare_workspace(tmp_path)
    tasks_before = tuple(
        (task.id, task.status, task.result, task.error, task.assigned_agent)
        for task in runtime.tasks.all()
    )
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model)
        for agent in runtime.agents.all()
    )
    resource_manager_before = runtime.application_service._resource_manager
    decision_request = {
        "decision": "approved",
        "patch_sha256": workspace.patch_sha256,
        "source_sha256": workspace.source_sha256,
    }

    with TestClient(create_app(runtime.application_service)) as client:
        assert client.get("/api/maintenance/approvals").status_code == 401
        assert client.post(
            "/api/maintenance/approvals",
            json={"workspace_id": workspace.workspace_id},
        ).status_code == 401
        assert client.post(
            "/api/maintenance/approvals/request-id/decision",
            json=decision_request,
        ).status_code == 401

    denied = create_app(
        runtime.application_service,
        Authentication(permissions=frozenset({"maintenance:read"})),
    )
    with TestClient(denied) as client:
        assert client.get("/api/maintenance/approvals").status_code == 403
        assert client.post(
            "/api/maintenance/approvals",
            json={"workspace_id": workspace.workspace_id},
        ).status_code == 403

    authorized = create_app(
        runtime.application_service,
        Authentication(
            identity="human-reviewer",
            permissions=frozenset({"maintenance:approve"}),
        ),
    )
    with TestClient(authorized) as client:
        created = client.post(
            "/api/maintenance/approvals",
            json={"workspace_id": workspace.workspace_id},
        )
        assert created.status_code == 201
        request_id = created.json()["request_id"]
        assert created.json()["unified_diff"] == patch
        assert created.json()["patch_sha256"] == workspace.patch_sha256
        assert created.json()["source_sha256"] == workspace.source_sha256

        listing = client.get("/api/maintenance/approvals")
        assert listing.status_code == 200
        assert listing.json()["items"][0]["request_id"] == request_id
        assert "unified_diff" not in listing.json()["items"][0]

        detail = client.get(f"/api/maintenance/approvals/{request_id}")
        assert detail.status_code == 200
        assert detail.json()["unified_diff"] == patch

        decided = client.post(
            f"/api/maintenance/approvals/{request_id}/decision",
            json=decision_payload(created.json(), "approved"),
        )
        assert decided.status_code == 200
        assert decided.json()["status"] == "approved"
        assert decided.json()["decided_by"] == "human-reviewer"
        assert decided.json()["decided_at"] is not None
        assert client.get("/api/maintenance/approvals").json()["items"] == []
        assert client.post(
            f"/api/maintenance/approvals/{request_id}/decision",
            json=decision_payload(created.json(), "rejected"),
        ).status_code == 409
        rejected_request = client.post(
            "/api/maintenance/approvals",
            json={"workspace_id": workspace.workspace_id},
        ).json()
        rejected = client.post(
            f"/api/maintenance/approvals/{rejected_request['request_id']}/decision",
            json=decision_payload(rejected_request, "rejected"),
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["decided_by"] == "human-reviewer"

    assert runtime.application_service.require_approved_maintenance_workspace(
        workspace.workspace_id
    ).decided_by == "human-reviewer"
    assert tuple(
        (task.id, task.status, task.result, task.error, task.assigned_agent)
        for task in runtime.tasks.all()
    ) == tasks_before
    assert runtime.application_service._resource_manager is resource_manager_before
    assert (tmp_path / "source" / "module.py").read_bytes() == b"value = 1\n"
    assert tuple(
        (agent.id, agent.provider, agent.model)
        for agent in runtime.agents.all()
    ) == assignments_before
