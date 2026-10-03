from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from difflib import unified_diff as make_unified_diff
from io import BytesIO
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import pytest

from app.application import (
    DiagnosticEvidence,
    PatchWorkspace,
    RunStatus,
    TestingWorkflowService,
)
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


def create_proposal(runtime):
    task = Task(
        "testing-task",
        "Failure",
        "Task for test workflow",
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
        "testing-proposal",
        diagnostic,
        title="Change the feature",
        proposed_change="Update the feature value.",
        scope="The feature module only.",
        risk="Tests run without OS-level isolation.",
    )


def diff_for(path, original, updated):
    return "".join(
        make_unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def create_workspace(runtime, tmp_path, feature_value):
    proposal = create_proposal(runtime)
    source_root = tmp_path / "trusted-source"
    (source_root / "tests").mkdir(parents=True)
    feature = source_root / "feature.py"
    feature.write_bytes(b"value = 1\n")
    test_file = source_root / "tests" / "test_feature.py"
    test_file.write_bytes(
        b"from feature import value\n\n"
        b"def test_feature_value():\n"
        b"    assert value == 2\n"
    )
    patch_text = diff_for(
        "feature.py",
        "value = 1\n",
        f"value = {feature_value}\n",
    )
    workspace = runtime.application_service.develop_patch(
        proposal.proposal_id,
        source_root,
        ("feature.py", "tests/test_feature.py"),
        patch_text,
    )
    return proposal, feature, test_file, workspace


def test_runs_only_selected_tests_against_a_separate_copy(tmp_path):
    runtime = create_corporation_runtime()
    proposal, feature, test_file, workspace = create_workspace(runtime, tmp_path, 2)
    original_task = runtime.tasks.get(proposal.diagnostic.failure.task_id)
    task_state = (original_task.status, original_task.result, original_task.error)
    agent = runtime.agents.get("local_worker")
    assignment = (agent.provider, agent.model)
    provider = runtime.providers.get(agent.provider)
    generate = Mock(side_effect=AssertionError("Testing invoked Provider"))

    with patch.object(provider, "generate", generate):
        report = runtime.application_service.run_selected_tests(
            workspace.workspace_id,
            ("tests/test_feature.py",),
        )

    generate.assert_not_called()
    assert report.proposal_id == proposal.proposal_id
    assert report.workspace_id == workspace.workspace_id
    assert report.selected_tests == ("tests/test_feature.py",)
    assert report.status is RunStatus.PASSED
    assert report.return_code == 0
    assert "1 passed" in report.output
    assert not report.output_truncated
    assert report.finished_at >= report.started_at
    assert feature.read_bytes() == b"value = 1\n"
    assert (workspace.path / "feature.py").read_bytes() == b"value = 2\n"
    assert (workspace.path / "tests" / "test_feature.py").read_bytes() == test_file.read_bytes()
    assert runtime.tasks.get(proposal.diagnostic.failure.task_id) == original_task
    assert task_state == (original_task.status, original_task.result, original_task.error)
    assert assignment == (agent.provider, agent.model)
    assert runtime.application_service._resource_manager is None
    with pytest.raises(FrozenInstanceError):
        report.status = RunStatus.FAILED
    runtime.application_service.dispose_patch_workspace(workspace.workspace_id)


def test_reports_actual_test_failure_and_rejects_tests_outside_workspace(tmp_path):
    runtime = create_corporation_runtime()
    proposal, _, _, workspace = create_workspace(runtime, tmp_path, 3)

    with pytest.raises(ValueError, match="selected Python files"):
        runtime.application_service.run_selected_tests(
            workspace.workspace_id,
            ("../other_test.py",),
        )
    report = runtime.application_service.run_selected_tests(
        workspace.workspace_id,
        ("tests/test_feature.py",),
    )
    assert report.proposal_id == proposal.proposal_id
    assert report.status is RunStatus.FAILED
    assert report.return_code != 0
    assert "1 failed" in report.output
    runtime.application_service.dispose_patch_workspace(workspace.workspace_id)


def test_no_collected_tests_are_reported_separately(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    test_file = workspace.path / "tests" / "test_sample.py"
    test_file.write_text("sample = True\n", encoding="utf-8")

    report = TestingWorkflowService().run(workspace, ("tests/test_sample.py",))

    assert report.status is RunStatus.NO_TESTS
    assert report.return_code == 5
    assert "no tests ran" in report.output.lower()


def make_workspace(path: Path) -> PatchWorkspace:
    (path / "tests").mkdir(parents=True, exist_ok=True)
    (path / "tests" / "test_sample.py").write_text("def test_sample(): pass\n", encoding="utf-8")
    return PatchWorkspace(
        workspace_id="workspace-id",
        proposal_id="proposal-id",
        files=("tests/test_sample.py",),
        changed_files=("tests/test_sample.py",),
        patch_sha256="patch-hash",
        source_sha256="source-hash",
        created_at=datetime.now(timezone.utc),
        path=path,
    )


class FakeProcess:
    def __init__(self, output: bytes, return_code: int = 0, timeout: bool = False):
        self.stdout = BytesIO(output)
        self.returncode = None if timeout else return_code
        self._timeout = timeout
        self._waited = False

    def wait(self, timeout=None):
        if self._timeout and not self._waited:
            self._waited = True
            raise subprocess.TimeoutExpired("pytest", timeout)
        return self.returncode

    def kill(self):
        self.returncode = -9

    def poll(self):
        return self.returncode


def test_timeout_and_output_limits_are_reported_with_a_bounded_environment(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    service = TestingWorkflowService()
    service.MAX_OUTPUT_BYTES = 96
    process = FakeProcess(b"diagnostic output " * 100, timeout=True)
    launch_args = None
    launch_kwargs = None

    def fake_popen(*args, **kwargs):
        nonlocal launch_args, launch_kwargs
        launch_args = args
        launch_kwargs = kwargs
        return process

    with patch.dict("os.environ", {"TESTING_WORKFLOW_SECRET": "not-forwarded"}):
        with patch("app.application.services.testing_workflow.subprocess.Popen", fake_popen):
            report = service.run(workspace, ("tests/test_sample.py",))

    assert report.status is RunStatus.TIMED_OUT
    assert report.return_code == -9
    assert report.output_truncated
    assert len(report.output.encode("utf-8")) <= service.MAX_OUTPUT_BYTES
    assert "[pytest output truncated]" in report.output
    assert launch_args is not None
    assert launch_args[0][1:5] == ["-m", "pytest", "-q", "--no-header"]
    assert launch_kwargs is not None
    assert launch_kwargs["shell"] is False
    assert launch_kwargs["stdin"] is subprocess.DEVNULL
    assert "TESTING_WORKFLOW_SECRET" not in launch_kwargs["env"]
    assert Path(launch_kwargs["env"]["TMP"]) == launch_kwargs["cwd"]
    assert launch_kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert not launch_kwargs["cwd"].exists()


def test_test_runner_start_failure_is_reported_without_exposing_exception_text(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    with patch(
        "app.application.services.testing_workflow.subprocess.Popen",
        side_effect=OSError("sensitive test-runner detail"),
    ):
        report = TestingWorkflowService().run(
            workspace,
            ("tests/test_sample.py",),
        )

    assert report.status is RunStatus.ERROR
    assert report.return_code is None
    assert report.output == "Could not start the selected test runner."
    assert "sensitive" not in report.output
