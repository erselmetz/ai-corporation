"""Run explicitly selected tests against a disposable patch-workspace copy."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from uuid import uuid4

from .patch_development import (
    PatchWorkspace,
    _source_file,
    _validate_relative_path,
)


class RunStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NO_TESTS = "no_tests"
    TIMED_OUT = "timed_out"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TestRunReport:
    run_id: str
    proposal_id: str
    workspace_id: str
    selected_tests: tuple[str, ...]
    status: RunStatus
    return_code: int | None
    output: str
    output_truncated: bool
    started_at: datetime
    finished_at: datetime


class TestingWorkflowService:
    MAX_SELECTED_TESTS = 20
    MAX_FILE_BYTES = 1024 * 1024
    MAX_TOTAL_SOURCE_BYTES = 16 * 1024 * 1024
    MAX_OUTPUT_BYTES = 64 * 1024
    TIMEOUT_SECONDS = 120
    OUTPUT_TRUNCATION_NOTICE = b"\n[pytest output truncated]\n"

    def run(
        self,
        workspace: PatchWorkspace,
        selected_tests: tuple[str, ...],
    ) -> TestRunReport:
        if not isinstance(workspace, PatchWorkspace):
            raise TypeError("Expected PatchWorkspace")
        if (
            not isinstance(workspace.files, tuple)
            or not 1 <= len(workspace.files) <= self.MAX_SELECTED_TESTS
            or not all(isinstance(path, str) for path in workspace.files)
            or len(set(workspace.files)) != len(workspace.files)
        ):
            raise ValueError("Patch workspace file selection is invalid")
        if (
            not isinstance(selected_tests, tuple)
            or not 1 <= len(selected_tests) <= self.MAX_SELECTED_TESTS
        ):
            raise ValueError("Select an immutable tuple of 1 to 20 test files")
        if not all(isinstance(test_file, str) for test_file in selected_tests):
            raise TypeError("Selected test paths must be text")
        if len(set(selected_tests)) != len(selected_tests):
            raise ValueError("Selected test files must be unique")
        if any(
            not isinstance(test_file, str)
            or test_file not in workspace.files
            or PurePosixPath(test_file).suffix.lower() != ".py"
            for test_file in selected_tests
        ):
            raise ValueError("Tests must be selected Python files in the patch workspace")

        started_at = datetime.now(timezone.utc)
        with TemporaryDirectory(prefix="ai-corp-tests-") as temporary_directory:
            test_root = Path(temporary_directory)
            source_root = _resolved_workspace_root(workspace)
            _copy_workspace_files(workspace, source_root, test_root, self)
            env = _test_environment(test_root)
            command = [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-header",
                *[f"./{test_file}" for test_file in selected_tests],
            ]
            try:
                process = subprocess.Popen(
                    command,
                    cwd=test_root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
            except OSError:
                return _report(
                    workspace,
                    selected_tests,
                    RunStatus.ERROR,
                    None,
                    "Could not start the selected test runner.",
                    False,
                    started_at,
                )
            stdout = process.stdout
            if stdout is None:
                process.kill()
                process.wait()
                raise RuntimeError("Test runner output pipe was not created")

            captured = bytearray()
            capture_lock = Lock()
            output_truncated = Event()
            output_read_errors: list[OSError] = []

            def collect_output() -> None:
                try:
                    while True:
                        chunk = stdout.read(8192)
                        if not chunk:
                            break
                        with capture_lock:
                            available = self.MAX_OUTPUT_BYTES - len(captured)
                            if available > 0:
                                captured.extend(chunk[:available])
                            if len(chunk) > available:
                                output_truncated.set()
                except OSError as exc:
                    output_read_errors.append(exc)
                    output_truncated.set()

            reader = Thread(target=collect_output, daemon=True)
            reader.start()
            timed_out = False
            try:
                try:
                    return_code = process.wait(timeout=self.TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.kill()
                    return_code = process.wait()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                reader.join(timeout=1)
                if reader.is_alive():
                    output_truncated.set()
                    try:
                        stdout.close()
                    except OSError as exc:
                        output_read_errors.append(exc)
                    reader.join(timeout=1)

            with capture_lock:
                output_bytes = bytes(captured)
            if output_truncated.is_set():
                output_bytes = output_bytes[
                    : self.MAX_OUTPUT_BYTES - len(self.OUTPUT_TRUNCATION_NOTICE)
                ]
                output_bytes += self.OUTPUT_TRUNCATION_NOTICE
            output = output_bytes.decode("utf-8", errors="replace")
            if timed_out:
                status = RunStatus.TIMED_OUT
            elif output_read_errors or reader.is_alive():
                status = RunStatus.ERROR
            elif return_code == 0:
                status = RunStatus.PASSED
            elif return_code == 1:
                status = RunStatus.FAILED
            elif return_code == 5:
                status = RunStatus.NO_TESTS
            else:
                status = RunStatus.ERROR
            return _report(
                workspace,
                selected_tests,
                status,
                return_code,
                output,
                output_truncated.is_set(),
                started_at,
            )


def _resolved_workspace_root(workspace: PatchWorkspace) -> Path:
    try:
        root = workspace.path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Patch workspace is unavailable") from exc
    if not root.is_dir():
        raise ValueError("Patch workspace is unavailable")
    return root


def _copy_workspace_files(
    workspace: PatchWorkspace,
    source_root: Path,
    destination_root: Path,
    service: TestingWorkflowService,
) -> None:
    total_bytes = 0
    for relative_path in workspace.files:
        path = PurePosixPath(_validate_relative_path(relative_path))
        source_file = _source_file(source_root, relative_path)
        try:
            with source_file.open("rb") as stream:
                content = stream.read(service.MAX_FILE_BYTES + 1)
        except OSError as exc:
            raise ValueError("Patch workspace file is unavailable") from exc
        if len(content) > service.MAX_FILE_BYTES:
            raise ValueError("Patch workspace file exceeds the byte limit")
        total_bytes += len(content)
        if total_bytes > service.MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("Patch workspace files exceed the total byte limit")
        destination = destination_root.joinpath(*path.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def _test_environment(test_root: Path) -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL"}
    }
    for name in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE"):
        environment[name] = str(test_root)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def _report(
    workspace: PatchWorkspace,
    selected_tests: tuple[str, ...],
    status: RunStatus,
    return_code: int | None,
    output: str,
    output_truncated: bool,
    started_at: datetime,
) -> TestRunReport:
    return TestRunReport(
        run_id=uuid4().hex,
        proposal_id=workspace.proposal_id,
        workspace_id=workspace.workspace_id,
        selected_tests=selected_tests,
        status=status,
        return_code=return_code,
        output=output,
        output_truncated=output_truncated,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    )
