from dataclasses import FrozenInstanceError
from difflib import unified_diff
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.application import DiagnosticEvidence
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


def create_proposal(runtime):
    task = Task(
        "patch-task",
        "Failure",
        "Task for patch proposal",
        status=TaskStatus.FAILED,
        failure_category=TaskFailureCategory.EXECUTION,
    )
    runtime.tasks.register(task)
    failure = runtime.application_service.detect_failures().failures[0]
    agent = runtime.agents.get("local_worker")
    with patch.object(
        runtime.providers.get(agent.provider),
        "generate",
        return_value='{"findings":[{"summary":"The evidence records an existing issue.",'
        '"evidence_refs":["ref-1"]}],"unknowns":[]}',
    ):
        diagnostic = runtime.application_service.diagnose_failure(
            agent.id,
            failure,
            (DiagnosticEvidence("ref-1", "Caller-supplied sanitized evidence."),),
        )
    return runtime.application_service.create_maintenance_proposal(
        "patch-proposal",
        diagnostic,
        title="Clarify behavior",
        proposed_change="Change the targeted source text only.",
        scope="Only the explicitly selected file.",
        risk="Behavior changes are not tested or reviewed here.",
    )


def diff_for(path, original, updated):
    return "".join(
        unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def test_patch_is_applied_only_to_a_disposable_copy_and_never_executes(tmp_path):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "trusted-source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(b"value = 1\n")
    untouched_file = source_root / "untouched.py"
    untouched_file.write_bytes(b"stable = True\n")
    original_task = runtime.tasks.get(proposal.diagnostic.failure.task_id)
    task_state = (
        original_task.status,
        original_task.result,
        original_task.error,
        original_task.assigned_agent,
    )
    task_ids = {task.id for task in runtime.tasks.all()}
    agent = runtime.agents.get("local_worker")
    assignment = (agent.provider, agent.model)
    provider = runtime.providers.get("ollama")
    generate = Mock(side_effect=AssertionError("Patch development invoked Provider"))
    patch_text = diff_for("module.py", "value = 1\n", "value = 2\n")

    with patch.object(provider, "generate", generate):
        workspace = runtime.application_service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py", "untouched.py"),
            patch_text,
        )

    generate.assert_not_called()
    assert workspace.proposal_id == proposal.proposal_id
    assert workspace.files == ("module.py", "untouched.py")
    assert workspace.changed_files == ("module.py",)
    assert (workspace.path / "module.py").read_bytes() == b"value = 2\n"
    assert (workspace.path / "untouched.py").read_bytes() == b"stable = True\n"
    assert sorted(path.name for path in workspace.path.iterdir()) == [
        "module.py",
        "untouched.py",
    ]
    assert source_file.read_bytes() == b"value = 1\n"
    assert untouched_file.read_bytes() == b"stable = True\n"
    assert runtime.tasks.get(proposal.diagnostic.failure.task_id) == original_task
    assert task_state == (
        original_task.status,
        original_task.result,
        original_task.error,
        original_task.assigned_agent,
    )
    assert assignment == (agent.provider, agent.model)
    assert runtime.application_service._resource_manager is None
    assert {task.id for task in runtime.tasks.all()} == task_ids
    assert runtime.orchestrator.logger.get_task_logs(proposal.diagnostic.failure.task_id) == []
    with pytest.raises(FrozenInstanceError):
        workspace.proposal_id = "changed"

    assert runtime.application_service.get_patch_workspace(workspace.workspace_id) is workspace
    runtime.application_service.dispose_patch_workspace(workspace.workspace_id)
    assert not workspace.path.exists()
    with pytest.raises(ValueError, match="not found"):
        runtime.application_service.get_patch_workspace(workspace.workspace_id)


@pytest.mark.parametrize(
    "invalid_path",
    ("../outside.py", "/absolute.py", r"..\outside.py", "C:/outside.py", "."),
)
def test_untrusted_file_paths_are_rejected_without_writing_outside(tmp_path, invalid_path):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(b"value = 1\n")
    patch_text = diff_for("module.py", "value = 1\n", "value = 2\n")

    with pytest.raises(ValueError):
        runtime.application_service.develop_patch(
            proposal.proposal_id,
            source_root,
            (invalid_path,),
            patch_text,
        )
    assert source_file.read_bytes() == b"value = 1\n"


def test_patch_cannot_modify_unselected_file_or_escape_via_symlink(tmp_path, monkeypatch):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(b"value = 1\n")
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"secret = True\n")
    link = source_root / "linked.py"
    with pytest.raises(ValueError, match="selected"):
        runtime.application_service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py",),
            diff_for("outside.py", "secret = True\n", "secret = False\n"),
        )
    actual_lstat = Path.lstat

    def lstat_with_link(path):
        if path == link:
            return SimpleNamespace(st_mode=stat.S_IFLNK)
        return actual_lstat(path)

    monkeypatch.setattr(Path, "lstat", lstat_with_link)
    with pytest.raises(ValueError, match="symlinks"):
        runtime.application_service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("linked.py",),
            diff_for("linked.py", "secret = True\n", "secret = False\n"),
        )
    assert outside.read_bytes() == b"secret = True\n"


def test_untrusted_hunks_and_empty_patch_fail_closed_without_creating_workspace(tmp_path):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(b"value = 1\n")
    service = runtime.application_service

    with pytest.raises(ValueError, match="does not match"):
        service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py",),
            diff_for("module.py", "wrong = 0\n", "wrong = 1\n"),
        )
    with pytest.raises(ValueError, match="empty"):
        service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py",),
            "",
        )
    assert source_file.read_bytes() == b"value = 1\n"


@pytest.mark.parametrize(
    ("original", "updated"),
    (
        ("first\n", "first\nsecond\n"),
        ("first\nsecond\n", "first\n"),
        ("", "new file contents\n"),
    ),
)
def test_patch_honors_unified_diff_insertions_and_deletions(tmp_path, original, updated):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(original.encode("utf-8"))

    workspace = runtime.application_service.develop_patch(
        proposal.proposal_id,
        source_root,
        ("module.py",),
        diff_for("module.py", original, updated),
    )
    assert (workspace.path / "module.py").read_bytes() == updated.encode("utf-8")
    runtime.application_service.dispose_patch_workspace(workspace.workspace_id)


def test_patch_preserves_files_without_a_trailing_newline(tmp_path):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "module.py").write_bytes(b"value = 1")
    patch_text = (
        "--- a/module.py\n"
        "+++ b/module.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "\\ No newline at end of file\n"
        "+value = 2\n"
        "\\ No newline at end of file\n"
    )

    workspace = runtime.application_service.develop_patch(
        proposal.proposal_id,
        source_root,
        ("module.py",),
        patch_text,
    )
    assert (workspace.path / "module.py").read_bytes() == b"value = 2"
    runtime.application_service.dispose_patch_workspace(workspace.workspace_id)


@pytest.mark.parametrize(
    "bad_patch",
    (
        "--- a/module.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-value = 1\n",
        "--- a/module.py\n+++ b/module.py\n@@ -1 +1,2 @@\n-value = 1\n",
        "--- a/module.py\n+++ b/module.py\n@@ -1 +2 @@\n-value = 1\n+value = 2\n",
        "--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-value = 1",
    ),
)
def test_malformed_or_structural_diffs_are_rejected(tmp_path, bad_patch):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "module.py").write_bytes(b"value = 1\n")

    with pytest.raises(ValueError):
        runtime.application_service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py",),
            bad_patch,
        )


def test_file_and_live_workspace_limits_are_enforced_and_disposable(tmp_path):
    runtime = create_corporation_runtime()
    proposal = create_proposal(runtime)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "module.py"
    source_file.write_bytes(b"value = 1\n")
    service = runtime.application_service
    service._patch_development.MAX_WORKSPACES = 1
    patch_text = diff_for("module.py", "value = 1\n", "value = 2\n")

    first = service.develop_patch(
        proposal.proposal_id,
        source_root,
        ("module.py",),
        patch_text,
    )
    with pytest.raises(ValueError, match="workspace limit"):
        service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py",),
            patch_text,
        )
    service.dispose_patch_workspace(first.workspace_id)

    source_file.write_bytes(b"x" * (service._patch_development.MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="byte limit"):
        service.develop_patch(
            proposal.proposal_id,
            source_root,
            ("module.py",),
            patch_text,
        )
