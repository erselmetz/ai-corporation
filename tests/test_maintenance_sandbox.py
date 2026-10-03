from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.application import MaintenanceSandboxService, MaintenanceSandboxStatus
from app.application.services.maintenance_sandbox import _BOUNDED_TEST_RUNNER
from app.application.services.patch_development import PatchWorkspace
from app.integrations import (
    DockerSandboxBackend,
    SandboxImagePolicy,
    SandboxResourceLimits,
)
from app.runtime.factory import create_corporation_runtime


IMAGE = "registry.example/maintenance@sha256:" + "a" * 64


def test_bounded_runner_script_has_valid_python_syntax():
    compile(_BOUNDED_TEST_RUNNER, "<maintenance-sandbox-runner>", "exec")


def test_bounded_runner_terminates_tests_at_its_timeout(monkeypatch):
    class TimedOutProcess:
        def __init__(self):
            self.stdout = BytesIO(b"partial output\n")
            self.killed = False

        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("selected tests", timeout)
            return -9

        def kill(self):
            self.killed = True

    process = TimedOutProcess()
    output = BytesIO()
    captured_stdout = SimpleNamespace(buffer=output, write=lambda _text: None)
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(sys, "argv", ["runner", "3", "1024", "./tests/test_x.py"])
    monkeypatch.setattr(sys, "stdout", captured_stdout)

    with pytest.raises(SystemExit) as result:
        exec(
            compile(_BOUNDED_TEST_RUNNER, "<maintenance-sandbox-runner>", "exec"),
            {},
        )

    assert result.value.code == 124
    assert process.killed
    assert b"partial output\n" in output.getvalue()
    assert b"[maintenance tests timed out]" in output.getvalue()


class FakeContainer:
    def __init__(self, *, exit_code=0, output=b"tests passed\n", stage_ok=True):
        self.exit_code = exit_code
        self.output = output
        self.stage_ok = stage_ok
        self.started = False
        self.removed = False
        self.archive = None
        self.command = None
        self.environment = None
        self.workdir = None

    def start(self):
        self.started = True

    def put_archive(self, path, data):
        assert path == "/workspace"
        self.archive = data
        return self.stage_ok

    def exec_run(
        self,
        cmd,
        *,
        stdout,
        stderr,
        demux,
        environment,
        workdir,
    ):
        self.command = cmd
        self.environment = environment
        self.workdir = workdir
        assert stdout and stderr and not demux
        return self.exit_code, self.output

    def remove(self, *, force, v):
        assert force and v
        self.removed = True


class FakeDockerClient:
    def __init__(self, *, container=None, os_type="linux", image_present=True):
        self.container = container or FakeContainer()
        self.os_type = os_type
        self.image_present = image_present
        self.images = SimpleNamespace(get=self.get_image)
        self.containers = SimpleNamespace(create=self.create)
        self.create_kwargs = None
        self.image_calls = []

    def info(self):
        return {"OSType": self.os_type}

    def get_image(self, image):
        self.image_calls.append(image)
        if not self.image_present:
            raise LookupError("secret local image details")
        return object()

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return self.container


def workspace(tmp_path: Path) -> PatchWorkspace:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "src" / "module.py").write_bytes(b"VALUE = 1\n")
    (tmp_path / "tests" / "test_module.py").write_bytes(
        b"from src.module import VALUE\nassert VALUE == 1\n"
    )
    return PatchWorkspace(
        workspace_id="workspace-82",
        proposal_id="proposal-82",
        files=("src/module.py", "tests/test_module.py"),
        changed_files=("src/module.py",),
        patch_sha256="a" * 64,
        source_sha256="b" * 64,
        created_at=datetime.now(timezone.utc),
        path=tmp_path,
    )


def service(client):
    backend = DockerSandboxBackend(
        SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE),
        client=client,
    )
    return MaintenanceSandboxService(backend)


def archive_files(data):
    with tarfile.open(fileobj=BytesIO(data), mode="r:*") as archive:
        return {
            member.name: archive.extractfile(member).read()
            for member in archive.getmembers()
            if member.isfile()
        }


def test_sandbox_stages_only_workspace_files_and_runs_in_fail_closed_container(
    tmp_path,
):
    item = workspace(tmp_path / "workspace")
    container = FakeContainer()
    client = FakeDockerClient(container=container)

    report = service(client).run(
        item,
        ("tests/test_module.py",),
    )

    options = client.create_kwargs
    assert report.status is MaintenanceSandboxStatus.PASSED
    assert report.backend_id == "docker"
    assert report.return_code == 0
    assert report.output == "tests passed\n"
    assert report.workspace_id == item.workspace_id
    assert report.proposal_id == item.proposal_id
    assert container.started and container.removed
    staged = archive_files(container.archive)
    assert staged == {
        "src/module.py": b"VALUE = 1\n",
        "tests/test_module.py": b"from src.module import VALUE\nassert VALUE == 1\n",
    }
    assert container.command[0:2] == ["python3", "-c"]
    assert "./tests/test_module.py" in container.command
    assert container.workdir == "/workspace"
    assert container.environment == {
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    assert options["network_disabled"] is True
    assert options["network_mode"] == "none"
    assert options["read_only"] is True
    assert options["privileged"] is False
    assert options["environment"] == {}
    assert options["user"] == "65534:65534"
    assert options["cap_drop"] == ["ALL"]
    assert options["mem_limit"] == "512m"
    assert options["pids_limit"] == 16
    assert options["storage_opt"] == {"size": "256M"}
    assert "volumes" not in options and "mounts" not in options
    assert "noexec" in options["tmpfs"]["/workspace"]
    assert options["image"] == IMAGE
    assert client.image_calls == [IMAGE]
    assert (tmp_path / "workspace" / "src" / "module.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 1\n"


@pytest.mark.parametrize(
    ("exit_code", "expected_status"),
    [
        (1, MaintenanceSandboxStatus.FAILED),
        (5, MaintenanceSandboxStatus.NO_TESTS),
        (124, MaintenanceSandboxStatus.TIMED_OUT),
        (125, MaintenanceSandboxStatus.OUTPUT_LIMIT),
        (2, MaintenanceSandboxStatus.ERROR),
    ],
)
def test_sandbox_reports_actual_container_result(exit_code, expected_status, tmp_path):
    container = FakeContainer(exit_code=exit_code)

    report = service(FakeDockerClient(container=container)).run(
        workspace(tmp_path / "workspace"),
        ("tests/test_module.py",),
    )

    assert report.status is expected_status
    assert report.return_code == exit_code
    assert container.removed
    assert report.output_truncated is (
        expected_status is MaintenanceSandboxStatus.OUTPUT_LIMIT
    )


def test_missing_docker_is_blocked_without_host_execution_or_secret_details(tmp_path):
    container = FakeContainer()
    client = FakeDockerClient(container=container, os_type="windows")

    report = service(client).run(
        workspace(tmp_path / "workspace"),
        ("tests/test_module.py",),
    )

    assert report.status is MaintenanceSandboxStatus.BLOCKED
    assert report.backend_id == "none"
    assert report.return_code is None
    assert report.output == "Docker isolation is unavailable or not approved."
    assert report.notes
    assert client.create_kwargs is None
    assert not container.started


def test_missing_approved_local_image_blocks_without_pull_or_execution(tmp_path):
    client = FakeDockerClient(image_present=False)

    report = service(client).run(
        workspace(tmp_path / "workspace"),
        ("tests/test_module.py",),
    )

    assert report.status is MaintenanceSandboxStatus.BLOCKED
    assert report.return_code is None
    assert "secret local image details" not in report.output
    assert client.create_kwargs is None


def test_sandbox_bounds_container_output(tmp_path):
    container = FakeContainer(output=b"x" * 100_000)

    report = service(FakeDockerClient(container=container)).run(
        workspace(tmp_path / "workspace"),
        ("tests/test_module.py",),
    )

    assert report.output_truncated
    assert len(report.output.encode("utf-8")) <= MaintenanceSandboxService.MAX_OUTPUT_BYTES


def test_invalid_workspace_selection_is_rejected_before_container_creation(tmp_path):
    item = workspace(tmp_path / "workspace")
    client = FakeDockerClient()
    sandbox = service(client)

    with pytest.raises(ValueError, match="patch workspace"):
        sandbox.run(item, ("../outside.py",))
    with pytest.raises(ValueError, match="timeout_seconds"):
        sandbox.run(item, ("tests/test_module.py",), timeout_seconds=61)
    with pytest.raises(ValueError, match="canonical"):
        sandbox.run(
            replace(item, files=("../outside.py",)),
            ("../outside.py",),
        )

    assert client.create_kwargs is None


@pytest.mark.parametrize(
    "members",
    [
        (("../escape.py", tarfile.REGTYPE, b"bad"),),
        (("link.py", tarfile.SYMTYPE, b"../../host"),),
        (
            ("same.py", tarfile.REGTYPE, b"first"),
            ("same.py", tarfile.REGTYPE, b"second"),
        ),
    ],
)
def test_docker_boundary_rejects_unsafe_workspace_archives(members):
    archive_data = BytesIO()
    with tarfile.open(fileobj=archive_data, mode="w") as archive:
        for name, entry_type, data in members:
            member = tarfile.TarInfo(name)
            member.type = entry_type
            member.size = len(data) if entry_type == tarfile.REGTYPE else 0
            if entry_type == tarfile.REGTYPE:
                archive.addfile(member, BytesIO(data))
            else:
                member.linkname = data.decode()
                archive.addfile(member)
    client = FakeDockerClient()
    backend = DockerSandboxBackend(
        SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE),
        client=client,
    )

    with pytest.raises(ValueError):
        backend.execute_workspace_command(
            archive_data.getvalue(),
            ("python3", "-c", "pass"),
            timeout_seconds=1,
            requested_resources=SandboxResourceLimits(
                max_memory_mb=512,
                max_cpu_seconds=60,
                max_processes=16,
                max_disk_mb=256,
            ),
            max_output_bytes=1024,
        )

    assert client.create_kwargs is None


def test_staging_and_cleanup_failures_are_reported_without_raw_details(tmp_path):
    rejected = FakeContainer(stage_ok=False)
    report = service(FakeDockerClient(container=rejected)).run(
        workspace(tmp_path / "first"),
        ("tests/test_module.py",),
    )
    assert report.status is MaintenanceSandboxStatus.ERROR
    assert report.return_code is None
    assert "Docker did not accept" not in report.output
    assert rejected.removed

    class CleanupFailureContainer(FakeContainer):
        def remove(self, *, force, v):
            raise RuntimeError("secret host path")

    failed_cleanup = CleanupFailureContainer()
    report = service(FakeDockerClient(container=failed_cleanup)).run(
        workspace(tmp_path / "second"),
        ("tests/test_module.py",),
    )
    assert report.status is MaintenanceSandboxStatus.ERROR
    assert report.return_code is None
    assert "secret host path" not in report.output


def test_application_service_looks_up_registered_workspace_and_uses_docker(
    tmp_path,
):
    item = workspace(tmp_path / "workspace")
    client = FakeDockerClient()
    backend = DockerSandboxBackend(
        SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE),
        client=client,
    )
    runtime = create_corporation_runtime()
    app_service = runtime.application_service
    tasks_before = tuple(runtime.tasks.all())
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    with (
        patch.object(app_service._patch_development, "get", return_value=item) as get,
        patch.object(
            app_service._testing_workflow,
            "run",
            side_effect=AssertionError("Task 80 host runner must not be used"),
        ) as host_runner,
        patch(
            "app.application.services.corporation.DockerSandboxBackend",
            return_value=backend,
        ) as backend_factory,
        patch(
            "subprocess.Popen",
            side_effect=AssertionError("Sandbox tests must not run on the host"),
        ) as host_process,
    ):
        report = app_service.run_sandboxed_tests(
            item.workspace_id,
            ("tests/test_module.py",),
            SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE),
        )

    get.assert_called_once_with(item.workspace_id)
    host_runner.assert_not_called()
    host_process.assert_not_called()
    backend_factory.assert_called_once()
    assert backend_factory.call_args.kwargs["client_timeout_seconds"] == 70
    assert report.status is MaintenanceSandboxStatus.PASSED
    assert tuple(runtime.tasks.all()) == tasks_before
    assert tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    ) == assignments_before
