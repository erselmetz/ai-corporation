"""Run explicitly selected maintenance tests in an isolated Docker container."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import io
from pathlib import Path, PurePosixPath
import tarfile
from uuid import uuid4

from app.integrations import (
    DockerSandboxBackend,
    DockerSandboxBackendError,
    DockerSandboxBlockedError,
    SandboxResourceLimits,
)
from .patch_development import (
    PatchWorkspace,
    _source_file,
    _validate_relative_path,
)


_BOUNDED_TEST_RUNNER = """\
import os
import subprocess
import sys
from threading import Event, Lock, Thread

timeout_seconds = int(sys.argv[1])
output_limit = int(sys.argv[2])
selected_tests = sys.argv[3:]
command = [
    sys.executable,
    "-m",
    "pytest",
    "-q",
    "--no-header",
    "-p",
    "no:cacheprovider",
    *selected_tests,
]
environment = {
    "PATH": os.environ.get("PATH", ""),
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}
try:
    process = subprocess.Popen(
        command,
        cwd="/workspace",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
except OSError:
    sys.stdout.write("Could not start the selected tests.")
    sys.exit(126)

captured = bytearray()
lock = Lock()
output_limited = Event()
read_errors = []

def terminate():
    try:
        process.kill()
    except ProcessLookupError:
        pass

def collect():
    try:
        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                break
            with lock:
                available = output_limit - len(captured)
                if available > 0:
                    captured.extend(chunk[:available])
                if len(chunk) > available:
                    output_limited.set()
                    terminate()
    except OSError:
        read_errors.append(True)
        terminate()

reader = Thread(target=collect, daemon=True)
reader.start()
timed_out = False
try:
    return_code = process.wait(timeout=timeout_seconds)
except subprocess.TimeoutExpired:
    timed_out = True
    terminate()
    return_code = process.wait()
reader.join(timeout=1)
if reader.is_alive():
    terminate()
    process.stdout.close()
    reader.join(timeout=1)
with lock:
    output = bytes(captured)
if timed_out:
    marker = b"\\n[maintenance tests timed out]\\n"
    output = output[:output_limit - len(marker)] + marker
    return_code = 124
elif output_limited.is_set():
    marker = b"\\n[maintenance test output truncated]\\n"
    output = output[:output_limit - len(marker)] + marker
    return_code = 125
elif read_errors or reader.is_alive():
    output = b"Could not collect bounded test output."
    return_code = 126
sys.stdout.buffer.write(output)
sys.exit(return_code)
"""


class MaintenanceSandboxStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NO_TESTS = "no_tests"
    TIMED_OUT = "timed_out"
    OUTPUT_LIMIT = "output_limit"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MaintenanceSandboxReport:
    run_id: str
    proposal_id: str
    workspace_id: str
    selected_tests: tuple[str, ...]
    status: MaintenanceSandboxStatus
    backend_id: str
    return_code: int | None
    output: str
    output_truncated: bool
    started_at: datetime
    finished_at: datetime
    notes: tuple[str, ...]


class MaintenanceSandboxService:
    MAX_SELECTED_TESTS = 20
    MAX_FILES = 20
    MAX_FILE_BYTES = 1024 * 1024
    MAX_TOTAL_SOURCE_BYTES = 16 * 1024 * 1024
    MAX_OUTPUT_BYTES = 64 * 1024
    MAX_TIMEOUT_SECONDS = 60
    RESOURCES = SandboxResourceLimits(
        max_memory_mb=512,
        max_cpu_seconds=MAX_TIMEOUT_SECONDS,
        max_processes=16,
        max_disk_mb=256,
    )

    def __init__(self, backend: DockerSandboxBackend):
        if not isinstance(backend, DockerSandboxBackend):
            raise TypeError("backend must be a DockerSandboxBackend")
        self._backend = backend

    def run(
        self,
        workspace: PatchWorkspace,
        selected_tests: tuple[str, ...],
        *,
        timeout_seconds: int = MAX_TIMEOUT_SECONDS,
    ) -> MaintenanceSandboxReport:
        if not isinstance(workspace, PatchWorkspace):
            raise TypeError("Expected PatchWorkspace")
        if (
            not isinstance(workspace.files, tuple)
            or not 1 <= len(workspace.files) <= self.MAX_FILES
            or not all(isinstance(path, str) for path in workspace.files)
            or len(set(workspace.files)) != len(workspace.files)
        ):
            raise ValueError("Patch workspace file selection is invalid")
        if (
            not isinstance(selected_tests, tuple)
            or not 1 <= len(selected_tests) <= self.MAX_SELECTED_TESTS
        ):
            raise ValueError("Select an immutable tuple of 1 to 20 test files")
        if not all(isinstance(path, str) for path in selected_tests):
            raise TypeError("Selected test paths must be text")
        if len(set(selected_tests)) != len(selected_tests):
            raise ValueError("Selected test files must be unique")
        if any(
            path not in workspace.files
            or PurePosixPath(path).suffix.lower() != ".py"
            for path in selected_tests
        ):
            raise ValueError("Tests must be selected Python files in the patch workspace")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= self.MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds must be from 1 to 60")

        archive = _workspace_archive(workspace, self)
        started_at = datetime.now(timezone.utc)
        try:
            return_code, output_bytes = self._backend.execute_workspace_command(
                archive,
                (
                    "python3",
                    "-c",
                    _BOUNDED_TEST_RUNNER,
                    str(timeout_seconds),
                    str(self.MAX_OUTPUT_BYTES),
                    *tuple(f"./{path}" for path in selected_tests),
                ),
                timeout_seconds=timeout_seconds,
                requested_resources=self.RESOURCES,
                max_output_bytes=self.MAX_OUTPUT_BYTES,
            )
        except DockerSandboxBlockedError:
            return _report(
                workspace,
                selected_tests,
                MaintenanceSandboxStatus.BLOCKED,
                "none",
                None,
                "Docker isolation is unavailable or not approved.",
                False,
                started_at,
            )
        except DockerSandboxBackendError:
            return _report(
                workspace,
                selected_tests,
                MaintenanceSandboxStatus.ERROR,
                "docker",
                None,
                "Docker maintenance execution failed or cleanup was incomplete.",
                False,
                started_at,
            )

        bounded_output = output_bytes[: self.MAX_OUTPUT_BYTES]
        output = bounded_output.decode("utf-8", errors="replace")
        if return_code == 0:
            status = MaintenanceSandboxStatus.PASSED
        elif return_code == 1:
            status = MaintenanceSandboxStatus.FAILED
        elif return_code == 5:
            status = MaintenanceSandboxStatus.NO_TESTS
        elif return_code == 124:
            status = MaintenanceSandboxStatus.TIMED_OUT
        elif return_code == 125:
            status = MaintenanceSandboxStatus.OUTPUT_LIMIT
        else:
            status = MaintenanceSandboxStatus.ERROR
        return _report(
            workspace,
            selected_tests,
            status,
            "docker",
            return_code,
            output,
            status is MaintenanceSandboxStatus.OUTPUT_LIMIT
            or len(output_bytes) > self.MAX_OUTPUT_BYTES,
            started_at,
        )


def _workspace_archive(
    workspace: PatchWorkspace,
    service: MaintenanceSandboxService,
) -> bytes:
    try:
        root = workspace.path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Patch workspace is unavailable") from exc
    if not root.is_dir():
        raise ValueError("Patch workspace is unavailable")

    contents: dict[str, bytes] = {}
    total_bytes = 0
    for relative_path in workspace.files:
        relative_path = _validate_relative_path(relative_path)
        source = _source_file(root, relative_path)
        try:
            with source.open("rb") as stream:
                content = stream.read(service.MAX_FILE_BYTES + 1)
        except OSError as exc:
            raise ValueError("Patch workspace file is unavailable") from exc
        if len(content) > service.MAX_FILE_BYTES:
            raise ValueError("Patch workspace file exceeds the byte limit")
        total_bytes += len(content)
        if total_bytes > service.MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("Patch workspace files exceed the total byte limit")
        contents[relative_path] = content

    directories = {
        parent
        for path in contents
        for parent in PurePosixPath(path).parents
        if parent.as_posix() != "."
    }
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for directory in sorted(
            directories,
            key=lambda item: (len(item.parts), item.as_posix()),
        ):
            entry = tarfile.TarInfo(directory.as_posix())
            entry.type = tarfile.DIRTYPE
            entry.mode = 0o777
            entry.uid = 65534
            entry.gid = 65534
            tar.addfile(entry)
        for path, content in contents.items():
            entry = tarfile.TarInfo(path)
            entry.size = len(content)
            entry.mode = 0o666
            entry.uid = 65534
            entry.gid = 65534
            tar.addfile(entry, io.BytesIO(content))
    return archive.getvalue()


def _report(
    workspace: PatchWorkspace,
    selected_tests: tuple[str, ...],
    status: MaintenanceSandboxStatus,
    backend_id: str,
    return_code: int | None,
    output: str,
    output_truncated: bool,
    started_at: datetime,
) -> MaintenanceSandboxReport:
    if status is MaintenanceSandboxStatus.BLOCKED:
        notes = ("No test code was run because Docker isolation was unavailable.",)
    elif status is MaintenanceSandboxStatus.ERROR:
        notes = ("Docker execution failed; no success is claimed.",)
    else:
        notes = ()
    return MaintenanceSandboxReport(
        run_id=uuid4().hex,
        proposal_id=workspace.proposal_id,
        workspace_id=workspace.workspace_id,
        selected_tests=selected_tests,
        status=status,
        backend_id=backend_id,
        return_code=return_code,
        output=output,
        output_truncated=output_truncated,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        notes=notes,
    )
