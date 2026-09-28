import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.integrations import (
    DockerSandboxBackend,
    DockerSandboxBlockedError,
    DockerSandboxExecutor,
    IntegrationProposal,
    IntegrationSandboxRegistry,
    IntegrationSource,
    IntegrationStatus,
    SandboxCredentialMode,
    SandboxEnvironmentMode,
    SandboxFilesystemMode,
    SandboxImagePolicy,
    SandboxIsolationPolicy,
    SandboxNetworkMode,
    SandboxProcessMode,
    SandboxResourceLimits,
    SandboxStatus,
    SandboxExecutionRequest,
    SandboxExecutionStatus,
)


IMAGE = "registry.example/sandbox@sha256:" + "a" * 64


class FakeContainer:
    def __init__(self, *, exit_code=0, wait_error=None):
        self.exit_code = exit_code
        self.wait_error = wait_error
        self.started = False
        self.killed = False
        self.removed = False
        self.wait_calls = []

    def start(self):
        self.started = True

    def wait(self, *, timeout):
        self.wait_calls.append(timeout)
        if self.wait_error is not None:
            error = self.wait_error
            self.wait_error = None
            raise error
        return {"StatusCode": self.exit_code}

    def logs(self, *, stdout, stderr):
        if stdout:
            return b"hello\n"
        if stderr:
            return b"error\n"
        return b""

    def kill(self):
        self.killed = True

    def remove(self, *, force, v):
        self.removed = True
        self.remove_force = force
        self.remove_volumes = v


class FakeDockerClient:
    def __init__(self, *, container=None, os_type="linux", image_present=True):
        self.container = container or FakeContainer()
        self.os_type = os_type
        self.image_present = image_present
        self.image_get_calls = []
        self.pull_calls = []
        self.create_kwargs = None
        self.create_error = None
        self.images = SimpleNamespace(get=self.get_image, pull=self.pull_image)
        self.containers = SimpleNamespace(create=self.create_container)

    def info(self):
        return {"OSType": self.os_type}

    def get_image(self, image):
        self.image_get_calls.append(image)
        if not self.image_present:
            raise LookupError("image not found")
        return object()

    def pull_image(self, image):
        self.pull_calls.append(image)
        raise AssertionError("Image pulls are not allowed")

    def create_container(self, **kwargs):
        self.create_kwargs = kwargs
        if self.create_error is not None:
            raise self.create_error
        return self.container


def proposal():
    item = IntegrationProposal(
        id="proposal-33",
        source=IntegrationSource(
            "github_repository",
            "https://github.com/example/project",
        ),
        requested_purpose="Sandbox experiment",
        source_discovery_id="discovery-33",
    )
    for status in (
        IntegrationStatus.ANALYZING,
        IntegrationStatus.EVALUATING,
        IntegrationStatus.PROPOSED,
    ):
        item.transition(status)
    return item


def sandbox_registry(policy=None):
    registry = IntegrationSandboxRegistry()
    sandbox = registry.create(
        "sandbox-33",
        proposal(),
        isolation_policy=policy
        or SandboxIsolationPolicy(process_mode=SandboxProcessMode.ISOLATED),
    )
    registry.transition(sandbox.id, SandboxStatus.READY)
    return registry, sandbox


def execution_request(**overrides):
    values = {
        "sandbox_id": "sandbox-33",
        "proposal_id": "proposal-33",
        "entrypoint": "app/run.py",
        "arguments": ("--flag", "value with spaces"),
        "timeout_seconds": 30,
    }
    values.update(overrides)
    return SandboxExecutionRequest(**values)


def configured_backend(client=None, *, image_policy=None):
    return DockerSandboxBackend(
        image_policy
        or SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE),
        client=client,
    )


def test_docker_backend_initialization_and_identity():
    backend = configured_backend(FakeDockerClient())

    assert backend.backend_id == "docker"
    assert backend.available
    assert backend.enforces_isolation
    assert backend.unavailable_reason is None


def test_missing_docker_sdk_is_reported_without_installing_it(monkeypatch):
    backend = configured_backend()
    sandbox = sandbox_registry(
        SandboxIsolationPolicy(process_mode=SandboxProcessMode.ISOLATED)
    )[1]
    real_import = importlib.import_module

    def missing_sdk(name, package=None):
        if name == "docker":
            raise ImportError("not installed")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", missing_sdk)

    assert backend.available is False
    assert "Docker Python SDK is not installed" in backend.unavailable_reason
    with pytest.raises(DockerSandboxBlockedError, match="SDK is not installed"):
        backend.prepare(sandbox, execution_request())


def test_image_policy_requires_immutable_allowlisted_default():
    assert SandboxImagePolicy(
        allowed_images=(IMAGE,), default_image=IMAGE
    ).resolve() == IMAGE
    with pytest.raises(ValueError, match="sha256 digest"):
        SandboxImagePolicy(allowed_images=("python:latest",))
    with pytest.raises(ValueError, match="allowed_images"):
        SandboxImagePolicy(allowed_images=(IMAGE,), default_image="other")
    with pytest.raises(DockerSandboxBlockedError, match="No approved"):
        SandboxImagePolicy().resolve()
    with pytest.raises(DockerSandboxBlockedError, match="allowlist"):
        SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE).resolve(
            "registry.example/untrusted:latest"
        )


def test_backend_requires_default_approved_image_and_never_pulls():
    client = FakeDockerClient()
    backend = configured_backend(
        client,
        image_policy=SandboxImagePolicy(allowed_images=(IMAGE,)),
    )
    with pytest.raises(DockerSandboxBlockedError, match="No approved"):
        backend.prepare(sandbox_registry()[1], execution_request())
    assert client.pull_calls == []
    assert client.create_kwargs is None


def test_docker_creation_applies_conservative_isolation_configuration():
    client = FakeDockerClient()
    backend = configured_backend(client)
    session = backend.prepare(sandbox_registry()[1], execution_request())
    options = client.create_kwargs

    assert session.backend_id == "docker"
    assert options["image"] == IMAGE
    assert options["network_disabled"] is True
    assert options["network_mode"] == "none"
    assert options["read_only"] is True
    assert options["privileged"] is False
    assert options["user"] == "65534:65534"
    assert options["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in options["security_opt"]
    assert options["environment"] == {}
    assert "volumes" not in options
    assert "mounts" not in options
    assert client.pull_calls == []


def test_network_credentials_filesystem_and_process_policy_fail_closed():
    policies = (
        SandboxIsolationPolicy(network_mode=SandboxNetworkMode.RESTRICTED),
        SandboxIsolationPolicy(credential_mode=SandboxCredentialMode.SCOPED),
        SandboxIsolationPolicy(
            filesystem_mode=SandboxFilesystemMode.ISOLATED_WRITABLE
        ),
        SandboxIsolationPolicy(process_mode=SandboxProcessMode.DISABLED),
        SandboxIsolationPolicy(environment_mode=SandboxEnvironmentMode.CLEAN),
    )
    for policy in policies:
        client = FakeDockerClient()
        backend = configured_backend(client)
        sandbox = sandbox_registry(policy)[1]
        with pytest.raises(DockerSandboxBlockedError):
            backend.prepare(sandbox, execution_request())
        assert client.create_kwargs is None


def test_default_process_policy_blocks_until_isolated_process_mode_is_explicit():
    client = FakeDockerClient()
    backend = configured_backend(client)
    sandbox = sandbox_registry(SandboxIsolationPolicy())[1]

    with pytest.raises(DockerSandboxBlockedError, match="isolated process mode"):
        backend.prepare(sandbox, execution_request())
    assert client.create_kwargs is None


def test_host_mount_and_docker_socket_are_never_added():
    client = FakeDockerClient()
    configured_backend(client).prepare(sandbox_registry()[1], execution_request())
    options = client.create_kwargs

    assert "volumes" not in options
    assert "mounts" not in options
    assert "/var/run/docker.sock" not in repr(options)
    assert "C:\\" not in repr(options)
    assert "D:\\" not in repr(options)


def test_privileged_mode_is_always_disabled_and_non_root_user_is_used():
    client = FakeDockerClient()
    configured_backend(client).prepare(sandbox_registry()[1], execution_request())
    assert client.create_kwargs["privileged"] is False
    assert client.create_kwargs["user"] != "0"


def test_resource_controls_are_passed_explicitly_to_docker():
    client = FakeDockerClient()
    request = execution_request(
        requested_resources=SandboxResourceLimits(
            max_memory_mb=256,
            max_cpu_seconds=30,
            max_processes=1,
            max_disk_mb=128,
        )
    )
    policy = SandboxIsolationPolicy(
        process_mode=SandboxProcessMode.ISOLATED,
        resource_limits=SandboxResourceLimits(
            max_memory_mb=512,
            max_cpu_seconds=60,
            max_processes=1,
            max_disk_mb=256,
        ),
    )
    configured_backend(client).prepare(sandbox_registry(policy)[1], request)
    options = client.create_kwargs

    assert options["mem_limit"] == "256m"
    assert options["nano_cpus"] == 1_000_000_000
    assert options["pids_limit"] == 1
    assert options["storage_opt"] == {"size": "128M"}
    assert "size=128m" in options["tmpfs"]["/tmp"]


def test_entrypoint_arguments_are_passed_as_a_vector_not_shell_text():
    client = FakeDockerClient()
    request = execution_request(arguments=("arg one", "; touch /tmp/pwned"))
    configured_backend(client).prepare(sandbox_registry()[1], request)

    assert client.create_kwargs["entrypoint"] == ["/app/run.py"]
    assert client.create_kwargs["command"] == ["arg one", "; touch /tmp/pwned"]


def test_missing_local_image_blocks_without_pulling_or_creating():
    client = FakeDockerClient(image_present=False)
    with pytest.raises(DockerSandboxBlockedError, match="automatic pulls are disabled"):
        configured_backend(client).prepare(
            sandbox_registry()[1], execution_request()
        )
    assert client.image_get_calls == [IMAGE]
    assert client.pull_calls == []
    assert client.create_kwargs is None


def test_non_linux_docker_daemon_is_unavailable():
    backend = configured_backend(FakeDockerClient(os_type="windows"))

    assert backend.available is False
    assert "Linux" in backend.unavailable_reason
    with pytest.raises(DockerSandboxBlockedError, match="Linux"):
        backend.prepare(sandbox_registry()[1], execution_request())


def test_successful_execution_collects_result_cleans_container_and_updates_lifecycle():
    container = FakeContainer(exit_code=0)
    client = FakeDockerClient(container=container)
    registry, sandbox = sandbox_registry()
    executor = DockerSandboxExecutor(configured_backend(client), registry)

    result = executor.execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.COMPLETED
    assert result.isolation_backend == "docker"
    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.duration_seconds is not None
    assert result.started_at is not None
    assert result.completed_at is not None
    assert container.started
    assert container.removed
    assert container.remove_force
    assert container.remove_volumes
    assert sandbox.status == SandboxStatus.COMPLETED


def test_nonzero_container_exit_maps_to_failed_and_cleans_up():
    container = FakeContainer(exit_code=3)
    registry, sandbox = sandbox_registry()
    result = DockerSandboxExecutor(
        configured_backend(FakeDockerClient(container=container)),
        registry,
    ).execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.FAILED
    assert result.exit_code == 3
    assert result.isolation_backend == "docker"
    assert result.stderr == "error\n"
    assert sandbox.status == SandboxStatus.FAILED
    assert container.removed


def test_timeout_kills_collects_output_and_cleans_up():
    container = FakeContainer(wait_error=TimeoutError("wait timed out"))
    registry, sandbox = sandbox_registry()
    result = DockerSandboxExecutor(
        configured_backend(FakeDockerClient(container=container)),
        registry,
    ).execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.TIMED_OUT
    assert result.isolation_backend == "docker"
    assert result.exit_code is None
    assert result.stdout == "hello\n"
    assert container.killed
    assert container.removed
    assert sandbox.status == SandboxStatus.FAILED


def test_cleanup_runs_after_container_start_exception():
    class StartFailureContainer(FakeContainer):
        def start(self):
            raise RuntimeError("start failed")

    container = StartFailureContainer()
    registry, sandbox = sandbox_registry()
    result = DockerSandboxExecutor(
        configured_backend(FakeDockerClient(container=container)),
        registry,
    ).execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.FAILED
    assert result.isolation_backend == "docker"
    assert container.removed
    assert sandbox.status == SandboxStatus.FAILED


def test_cleanup_failure_is_reported_and_sandbox_fails():
    class CleanupFailureContainer(FakeContainer):
        def remove(self, *, force, v):
            raise RuntimeError("remove failed")

    container = CleanupFailureContainer()
    registry, sandbox = sandbox_registry()
    result = DockerSandboxExecutor(
        configured_backend(FakeDockerClient(container=container)),
        registry,
    ).execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.FAILED
    assert any("cleanup failed" in note for note in result.notes)
    assert sandbox.status == SandboxStatus.FAILED


def test_container_creation_failure_does_not_mark_sandbox_running():
    client = FakeDockerClient()
    client.create_error = RuntimeError("resource control unsupported")
    registry, sandbox = sandbox_registry()
    result = DockerSandboxExecutor(
        configured_backend(client), registry
    ).execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.BLOCKED
    assert result.isolation_backend == "none"
    assert sandbox.status == SandboxStatus.READY


def test_no_arbitrary_image_pull_and_no_subprocess_fallback():
    client = FakeDockerClient(image_present=False)
    backend = configured_backend(client)
    registry, sandbox = sandbox_registry()
    executor = DockerSandboxExecutor(backend, registry)

    with (
        patch("subprocess.run", side_effect=AssertionError("host process")),
        patch("subprocess.Popen", side_effect=AssertionError("host process")),
    ):
        result = executor.execute(sandbox, execution_request())

    assert result.status == SandboxExecutionStatus.BLOCKED
    assert client.pull_calls == []
    assert client.create_kwargs is None
    assert sandbox.status == SandboxStatus.READY


def test_blocked_preflight_result_is_deterministic():
    registry, sandbox = sandbox_registry()
    backend = configured_backend(
        FakeDockerClient(image_present=False),
        image_policy=SandboxImagePolicy(
            allowed_images=(IMAGE,), default_image=IMAGE
        ),
    )
    executor = DockerSandboxExecutor(backend, registry)

    first = executor.execute(sandbox, execution_request())
    second = executor.execute(sandbox, execution_request())

    assert first == second
    assert first.status == SandboxExecutionStatus.BLOCKED
    assert first.isolation_backend == "none"


def test_missing_sdk_does_not_install_or_mutate_dependencies():
    backend = configured_backend()
    registry, sandbox = sandbox_registry()

    with patch("subprocess.run", side_effect=AssertionError("install attempted")):
        result = DockerSandboxExecutor(backend, registry).execute(
            sandbox, execution_request()
        )

    assert result.status == SandboxExecutionStatus.BLOCKED
    assert "SDK is not installed" in result.notes[0]
    assert sandbox.status == SandboxStatus.READY
