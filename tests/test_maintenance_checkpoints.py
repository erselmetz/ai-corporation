from datetime import datetime, timezone
from difflib import unified_diff
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from app.api import AuthenticatedPrincipal, create_app
from app.application import DiagnosticReport
from app.application.services.git_checkpoints import (
    GitCheckpointBlockedError,
    GitCheckpointNotFoundError,
)
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


class Authentication:
    def __init__(self, identity="checkpoint-reviewer", permissions=frozenset()):
        self.identity = identity
        self.permissions = permissions

    def authenticate(self, _request):
        return AuthenticatedPrincipal(self.identity, self.permissions)


def git(repository, *arguments):
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


def prepare_approved_workspace(
    tmp_path,
    *,
    approve=True,
    initialize_git=True,
):
    if shutil.which("git") is None:
        pytest.skip("Git executable is unavailable")

    repository = tmp_path / "maintenance source repo"
    repository.mkdir()
    if initialize_git:
        git(repository, "init", "-q")
        git(repository, "config", "user.name", "Checkpoint Test")
        git(repository, "config", "user.email", "checkpoint@example.invalid")
        git(repository, "config", "commit.gpgsign", "false")
    (repository / "module.py").write_bytes(b"value = 1\n")
    (repository / "unrelated.py").write_bytes(b"other = 1\n")
    if initialize_git:
        git(repository, "add", "module.py", "unrelated.py")
        git(repository, "commit", "-m", "initial")

    runtime = create_corporation_runtime()
    task = Task(
        "checkpoint-task",
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
        "checkpoint-proposal",
        diagnostic,
        title="Change one value",
        proposed_change="Update the constant.",
        scope="module.py only",
        risk="The value changes.",
    )
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
        repository,
        ("module.py",),
        patch,
    )
    review = runtime.application_service.request_maintenance_approval(
        workspace.workspace_id
    )
    if approve:
        runtime.application_service.approve_maintenance_workspace(
            review.request_id,
            approver_id="checkpoint-reviewer",
            patch_sha256=review.patch_sha256,
            source_sha256=review.source_sha256,
        )
    return runtime, repository, workspace


def test_approved_patch_creates_separate_local_branch_without_touching_checkout(
    tmp_path,
):
    runtime, repository, workspace = prepare_approved_workspace(tmp_path)
    application = runtime.application_service
    head_before = git(repository, "rev-parse", "HEAD").decode().strip()
    branch_before = git(repository, "branch", "--show-current").decode().strip()
    tasks_before = tuple(
        (task.id, task.status, task.result, task.error, task.assigned_agent)
        for task in runtime.tasks.all()
    )
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model)
        for agent in runtime.agents.all()
    )

    checkpoint = application.create_maintenance_checkpoint(
        workspace.workspace_id,
        created_by="checkpoint-operator",
    )

    reference = f"refs/heads/{checkpoint.branch_name}"
    assert checkpoint.workspace_id == workspace.workspace_id
    assert checkpoint.parent_sha == head_before
    assert git(repository, "rev-parse", reference).decode().strip() == (
        checkpoint.commit_sha
    )
    assert git(repository, "rev-parse", f"{reference}^").decode().strip() == (
        head_before
    )
    assert git(repository, "show", f"{reference}:module.py") == b"value = 2\n"
    assert git(repository, "rev-parse", "HEAD").decode().strip() == head_before
    assert git(repository, "branch", "--show-current").decode().strip() == (
        branch_before
    )
    assert git(repository, "status", "--porcelain") == b""
    assert git(repository, "remote").strip() == b""
    assert checkpoint.unified_diff == workspace.unified_diff
    assert checkpoint.created_by == "checkpoint-operator"
    commit_message = git(
        repository,
        "show",
        "-s",
        "--format=%B",
        checkpoint.commit_sha,
    ).decode()
    assert "Checkpoint-Created-By: checkpoint-operator" in commit_message
    assert application.get_maintenance_checkpoint(
        checkpoint.checkpoint_id
    ) == checkpoint
    assert application.list_maintenance_checkpoints() == (checkpoint,)
    assert tuple(
        (task.id, task.status, task.result, task.error, task.assigned_agent)
        for task in runtime.tasks.all()
    ) == tasks_before
    assert tuple(
        (agent.id, agent.provider, agent.model)
        for agent in runtime.agents.all()
    ) == assignments_before


def test_checkpoint_requires_approval_and_a_registered_workspace(tmp_path):
    runtime, repository, workspace = prepare_approved_workspace(
        tmp_path, approve=False
    )
    application = runtime.application_service
    with pytest.raises(PermissionError, match="approved human review"):
        application.create_maintenance_checkpoint(
            workspace.workspace_id,
            created_by="checkpoint-operator",
        )

    with pytest.raises(GitCheckpointNotFoundError):
        application.create_maintenance_checkpoint(
            "missing-workspace",
            created_by="checkpoint-operator",
        )
    assert application.list_maintenance_checkpoints() == ()
    assert git(repository, "for-each-ref", "refs/heads/maintenance-checkpoints") == b""


def test_checkpoint_blocks_non_git_source_without_modifying_source(tmp_path):
    runtime, repository, workspace = prepare_approved_workspace(
        tmp_path,
        initialize_git=False,
    )
    original = (repository / "module.py").read_bytes()

    with pytest.raises(
        GitCheckpointBlockedError,
        match="not an available Git repository",
    ):
        runtime.application_service.create_maintenance_checkpoint(
            workspace.workspace_id,
            created_by="checkpoint-operator",
        )

    assert (repository / "module.py").read_bytes() == original
    assert runtime.application_service.list_maintenance_checkpoints() == ()


def test_checkpoint_rejects_source_changed_after_human_approval(tmp_path):
    runtime, repository, workspace = prepare_approved_workspace(tmp_path)
    (repository / "module.py").write_bytes(b"value = 3\n")
    git(repository, "add", "module.py")
    git(repository, "commit", "-m", "update reviewed source")
    head_before = git(repository, "rev-parse", "HEAD")

    with pytest.raises(
        GitCheckpointBlockedError,
        match="patch no longer matches its source",
    ):
        runtime.application_service.create_maintenance_checkpoint(
            workspace.workspace_id,
            created_by="checkpoint-operator",
        )

    assert git(repository, "rev-parse", "HEAD") == head_before
    assert git(repository, "status", "--porcelain") == b""
    assert git(repository, "for-each-ref", "refs/heads/maintenance-checkpoints") == b""


@pytest.mark.parametrize("dirty_state", ["worktree", "index", "untracked"])
def test_checkpoint_blocks_dirty_repository_without_changing_git_state(
    tmp_path,
    dirty_state,
):
    runtime, repository, workspace = prepare_approved_workspace(tmp_path)
    unrelated = repository / "unrelated.py"
    if dirty_state == "worktree":
        unrelated.write_bytes(b"other = 2\n")
    elif dirty_state == "index":
        unrelated.write_bytes(b"other = 2\n")
        git(repository, "add", "unrelated.py")
    else:
        (repository / "untracked.txt").write_bytes(b"untracked\n")

    before = git(repository, "status", "--porcelain")
    head_before = git(repository, "rev-parse", "HEAD")
    with pytest.raises(GitCheckpointBlockedError, match="clean worktree and index"):
        runtime.application_service.create_maintenance_checkpoint(
            workspace.workspace_id,
            created_by="checkpoint-operator",
        )

    assert git(repository, "status", "--porcelain") == before
    assert git(repository, "rev-parse", "HEAD") == head_before
    assert git(repository, "for-each-ref", "refs/heads/maintenance-checkpoints") == b""


def test_checkpoint_creation_is_idempotent_for_the_same_approved_workspace(
    tmp_path,
):
    runtime, _repository, workspace = prepare_approved_workspace(tmp_path)
    application = runtime.application_service

    first = application.create_maintenance_checkpoint(
        workspace.workspace_id,
        created_by="checkpoint-operator",
    )
    retry = application.create_maintenance_checkpoint(
        workspace.workspace_id,
        created_by="checkpoint-operator",
    )

    assert retry == first
    assert application.list_maintenance_checkpoints() == (first,)


def test_existing_checkpoint_branch_is_never_overwritten(tmp_path):
    runtime, repository, workspace = prepare_approved_workspace(tmp_path)
    branch = f"maintenance-checkpoints/{workspace.workspace_id}"
    git(repository, "branch", branch, "HEAD")
    existing_commit = git(repository, "rev-parse", f"refs/heads/{branch}")
    head_before = git(repository, "rev-parse", "HEAD")

    with pytest.raises(
        GitCheckpointBlockedError,
        match="checkpoint branch could not be created",
    ):
        runtime.application_service.create_maintenance_checkpoint(
            workspace.workspace_id,
            created_by="checkpoint-operator",
        )

    assert git(repository, "rev-parse", f"refs/heads/{branch}") == existing_commit
    assert git(repository, "rev-parse", "HEAD") == head_before
    assert git(repository, "status", "--porcelain") == b""


def test_checkpoint_does_not_bypass_configured_commit_signing(tmp_path):
    runtime, repository, workspace = prepare_approved_workspace(tmp_path)
    git(repository, "config", "commit.gpgsign", "true")

    with pytest.raises(
        GitCheckpointBlockedError,
        match="signed commits are not supported",
    ):
        runtime.application_service.create_maintenance_checkpoint(
            workspace.workspace_id,
            created_by="checkpoint-operator",
        )

    assert git(repository, "status", "--porcelain") == b""
    assert git(repository, "for-each-ref", "refs/heads/maintenance-checkpoints") == b""


def test_checkpoint_api_requires_separate_checkpoint_permission(tmp_path):
    runtime, repository, workspace = prepare_approved_workspace(tmp_path)
    approval_only = create_app(
        runtime.application_service,
        Authentication(permissions=frozenset({"maintenance:approve"})),
    )
    with TestClient(approval_only) as client:
        assert client.post(
            "/api/maintenance/checkpoints",
            json={"workspace_id": workspace.workspace_id},
        ).status_code == 403

    authorized = create_app(
        runtime.application_service,
        Authentication(
            identity="checkpoint-operator",
            permissions=frozenset(
                {"maintenance:approve", "maintenance:checkpoint"}
            ),
        ),
    )
    with TestClient(authorized) as client:
        created = client.post(
            "/api/maintenance/checkpoints",
            json={"workspace_id": workspace.workspace_id},
        )
        assert created.status_code == 201
        result = created.json()
        assert result["approval_request_id"]
        assert result["created_by"] == "checkpoint-operator"
        assert result["branch_name"].startswith("maintenance-checkpoints/")
        assert result["unified_diff"] == workspace.unified_diff
        assert client.get("/api/maintenance/checkpoints").json()["items"][0][
            "checkpoint_id"
        ] == result["checkpoint_id"]
        assert client.get(
            f"/api/maintenance/checkpoints/{result['checkpoint_id']}"
        ).json()["commit_sha"] == result["commit_sha"]
    assert git(repository, "status", "--porcelain") == b""
