from __future__ import annotations

import importlib
from io import BytesIO
import re
from pathlib import PurePosixPath, PureWindowsPath
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol

from .sandbox import (
    IntegrationSandbox,
    IntegrationSandboxRegistry,
    SandboxCredentialMode,
    SandboxEnvironmentMode,
    SandboxFilesystemMode,
    SandboxNetworkMode,
    SandboxProcessMode,
    SandboxResourceLimits,
    SandboxStatus,
)
from .sandbox_executor import (
    SandboxBackend,
    SandboxBackendSession,
    SandboxExecutionError,
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxExecutionStatus,
    SandboxExecutor,
)

_IMAGE_DIGEST_PATTERN = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
_NANO_CPUS_PER_CORE = 1_000_000_000


class DockerSandboxError(SandboxExecutionError):
    """Base class for Docker backend errors."""


class DockerSandboxBlockedError(DockerSandboxError):
    """Raised when Docker execution cannot satisfy a required safety control."""


class DockerSandboxBackendError(DockerSandboxError):
    """Raised when a Docker operation fails after execution setup begins."""


@dataclass(frozen=True)
class SandboxImagePolicy:
    allowed_images: tuple[str, ...] = ()
    default_image: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_images, tuple):
            raise TypeError("allowed_images must be a tuple")
        for image in self.allowed_images:
            if not isinstance(image, str) or not _IMAGE_DIGEST_PATTERN.fullmatch(image):
                raise ValueError("Allowed images must use an immutable sha256 digest")
        if len(set(self.allowed_images)) != len(self.allowed_images):
            raise ValueError("allowed_images cannot contain duplicates")
        if self.default_image is not None:
            if not isinstance(self.default_image, str) or not self.default_image.strip():
                raise ValueError("default_image cannot be empty")
            if self.default_image not in self.allowed_images:
                raise ValueError("default_image must be present in allowed_images")

    def resolve(self, requested_image: str | None = None) -> str:
        image = requested_image or self.default_image
        if image is None:
            raise DockerSandboxBlockedError(
                "No approved Docker sandbox image is configured."
            )
        if image not in self.allowed_images:
            raise DockerSandboxBlockedError(
                "Docker image is not in the approved image allowlist."
            )
        return image


class _DockerContainer(Protocol):
    def start(self) -> None: ...

    def wait(self, *, timeout: int) -> Mapping[str, int]: ...

    def logs(self, *, stdout: bool, stderr: bool) -> bytes: ...

    def put_archive(self, path: str, data: bytes) -> bool: ...

    def exec_run(
        self,
        cmd: list[str],
        *,
        stdout: bool,
        stderr: bool,
        demux: bool,
        environment: dict[str, str],
        workdir: str,
    ) -> tuple[int | None, bytes | str | None]: ...

    def kill(self) -> None: ...

    def remove(self, *, force: bool, v: bool) -> None: ...


class _DockerImages(Protocol):
    def get(self, image: str) -> object: ...


class _DockerContainers(Protocol):
    def create(self, **kwargs: object) -> _DockerContainer: ...


class _DockerClient(Protocol):
    images: _DockerImages
    containers: _DockerContainers

    def info(self) -> Mapping[str, object]: ...


@dataclass
class _DockerSession:
    container: _DockerContainer
    started_at: datetime | None = None
    started_monotonic: float | None = None
    exit_code: int | None = None
    timed_out: bool = False
    timeout_cleanup_error: str | None = None


class DockerSandboxBackend(SandboxBackend):
    """Disposable Docker backend with a fail-closed, no-host-mount policy."""

    def __init__(
        self,
        image_policy: SandboxImagePolicy,
        *,
        client: _DockerClient | None = None,
        client_timeout_seconds: int = 10,
    ) -> None:
        if not isinstance(image_policy, SandboxImagePolicy):
            raise TypeError("image_policy must be a SandboxImagePolicy")
        if (
            isinstance(client_timeout_seconds, bool)
            or not isinstance(client_timeout_seconds, int)
            or not 1 <= client_timeout_seconds <= 300
        ):
            raise ValueError("client_timeout_seconds must be from 1 to 300")
        self.image_policy = image_policy
        self._client = client
        self._client_timeout_seconds = client_timeout_seconds
        self._sdk_checked = client is not None
        self._sdk_error: str | None = None
        self._availability_error: str | None = None

    @property
    def backend_id(self) -> str:
        return "docker"

    @property
    def available(self) -> bool:
        try:
            client = self._get_client()
            info = client.info()
            if info.get("OSType") != "linux":
                self._availability_error = (
                    "Docker sandbox execution requires a Linux container daemon."
                )
                return False
            self._availability_error = None
            return True
        except DockerSandboxBlockedError as exc:
            self._availability_error = str(exc)
            return False
        except Exception as exc:
            self._availability_error = (
                f"Docker daemon is unavailable: {type(exc).__name__}: {exc}"
            )
            return False

    @property
    def enforces_isolation(self) -> bool:
        return self.available

    @property
    def unavailable_reason(self) -> str | None:
        if self.available:
            return None
        return self._availability_error or "Docker sandbox backend is unavailable."

    def prepare(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxBackendSession:
        self._validate_types(sandbox, request)
        image = self.image_policy.resolve()
        self._validate_policy(sandbox, request)
        client = self._get_client()
        info = client.info()
        if info.get("OSType") != "linux":
            raise DockerSandboxBlockedError(
                "Docker sandbox execution requires a Linux container daemon."
            )
        try:
            client.images.get(image)
        except Exception as exc:
            raise DockerSandboxBlockedError(
                "Approved Docker image could not be verified locally; automatic "
                f"pulls are disabled ({type(exc).__name__}: {exc})."
            ) from exc

        resources = request.requested_resources
        try:
            container = _create_isolated_container(
                client,
                image,
                [f"/{request.entrypoint}"],
                list(request.arguments),
                resources,
            )
        except Exception as exc:
            raise DockerSandboxBlockedError(
                "Docker could not create a container with all requested isolation and resource controls."
            ) from exc

        state = _DockerSession(container=container)
        return SandboxBackendSession(
            sandbox_id=sandbox.id,
            backend_id=self.backend_id,
            handle=state,
        )

    def execute_workspace_command(
        self,
        archive: bytes,
        command: tuple[str, ...],
        *,
        timeout_seconds: int,
        requested_resources: SandboxResourceLimits,
        max_output_bytes: int,
    ) -> tuple[int, bytes]:
        """Run an argv in an ephemeral no-network, no-host-mount workspace."""
        if not isinstance(archive, bytes) or len(archive) > 16 * 1024 * 1024 + 65536:
            raise ValueError("Workspace archive is invalid or exceeds the byte limit")
        _validate_workspace_archive(archive)
        if (
            not isinstance(command, tuple)
            or not command
            or len(command) > 32
            or any(
                not isinstance(argument, str)
                or not argument
                or "\x00" in argument
                or len(argument.encode("utf-8")) > 8192
                for argument in command
            )
        ):
            raise ValueError("Workspace command must be a bounded argv tuple")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or timeout_seconds <= 0
            or not isinstance(requested_resources, SandboxResourceLimits)
            or timeout_seconds > requested_resources.max_cpu_seconds
        ):
            raise ValueError("Workspace execution limits are invalid")
        if (
            isinstance(max_output_bytes, bool)
            or not isinstance(max_output_bytes, int)
            or not 1 <= max_output_bytes <= 1024 * 1024
        ):
            raise ValueError("Workspace output limit is invalid")
        if not self.available:
            raise DockerSandboxBlockedError(
                "Docker maintenance sandbox is unavailable."
            )

        image = self.image_policy.resolve()
        client = self._get_client()
        try:
            client.images.get(image)
        except Exception:
            raise DockerSandboxBlockedError(
                "Approved Docker image is not available locally; automatic pulls are disabled."
            ) from None

        try:
            container = _create_isolated_container(
                client,
                image,
                ["/bin/sleep"],
                ["infinity"],
                requested_resources,
                workspace_tmpfs=True,
            )
        except Exception:
            raise DockerSandboxBlockedError(
                "Docker could not create a container with all required isolation controls."
            ) from None

        primary_error: BaseException | None = None
        result: tuple[int, bytes] | None = None
        try:
            try:
                container.start()
            except Exception:
                raise DockerSandboxBackendError(
                    "Docker maintenance container could not start."
                ) from None
            try:
                staged = container.put_archive("/workspace", archive)
            except Exception:
                raise DockerSandboxBackendError(
                    "Docker could not stage the bounded maintenance workspace."
                ) from None
            if staged is not True:
                raise DockerSandboxBackendError(
                    "Docker did not accept the maintenance workspace."
                )
            try:
                exit_code, output = container.exec_run(
                    list(command),
                    stdout=True,
                    stderr=True,
                    demux=False,
                    environment={
                        "HOME": "/tmp",
                        "TMPDIR": "/tmp",
                        "PYTHONDONTWRITEBYTECODE": "1",
                        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                        "PYTHONUTF8": "1",
                        "PYTHONIOENCODING": "utf-8",
                    },
                    workdir="/workspace",
                )
            except Exception:
                raise DockerSandboxBackendError(
                    "Docker maintenance command failed."
                ) from None
            if (
                isinstance(exit_code, bool)
                or not isinstance(exit_code, int)
                or not isinstance(output, (bytes, str))
            ):
                raise DockerSandboxBackendError(
                    "Docker returned an invalid maintenance command result."
                )
            output_bytes = (
                output.encode("utf-8", errors="replace")
                if isinstance(output, str)
                else output
            )
            result = (exit_code, output_bytes[: max_output_bytes + 256])
        except BaseException as exc:
            primary_error = exc
        cleanup_error = None
        try:
            container.remove(force=True, v=True)
        except Exception:
            cleanup_error = DockerSandboxBackendError(
                "Docker maintenance container cleanup failed."
            )
        if primary_error is not None:
            raise primary_error.with_traceback(primary_error.__traceback__)
        if cleanup_error is not None:
            raise cleanup_error
        if result is None:
            raise DockerSandboxBackendError(
                "Docker did not return a maintenance command result."
            )
        return result

    def execute(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> None:
        state = self._session_state(session, request)
        state.started_at = datetime.now(timezone.utc)
        state.started_monotonic = time.monotonic()
        try:
            state.container.start()
        except Exception as exc:
            raise DockerSandboxBackendError(
                f"Docker container start failed: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            wait_result = state.container.wait(timeout=request.timeout_seconds)
            state.exit_code = wait_result.get("StatusCode")
            if isinstance(state.exit_code, bool) or not isinstance(state.exit_code, int):
                raise DockerSandboxBackendError(
                    "Docker returned no valid container exit code."
                )
        except Exception as exc:
            if not self._is_timeout(exc):
                raise DockerSandboxBackendError(
                    f"Docker container execution failed: {type(exc).__name__}: {exc}"
                ) from exc
            state.timed_out = True
            try:
                state.container.kill()
                state.container.wait(timeout=5)
            except Exception as cleanup_exc:
                state.timeout_cleanup_error = (
                    f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                )

    def collect_result(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        state = self._session_state(session, request)
        try:
            stdout = self._decode_output(
                state.container.logs(stdout=True, stderr=False)
            )
            stderr = self._decode_output(
                state.container.logs(stdout=False, stderr=True)
            )
        except Exception as exc:
            raise DockerSandboxBackendError(
                f"Could not collect Docker container output: {type(exc).__name__}: {exc}"
            ) from exc

        completed_at = datetime.now(timezone.utc)
        duration = (
            max(0.0, time.monotonic() - state.started_monotonic)
            if state.started_monotonic is not None
            else None
        )
        if state.timed_out:
            status = SandboxExecutionStatus.TIMED_OUT
            notes = ("Container exceeded its bounded execution timeout.",)
            if state.timeout_cleanup_error is not None:
                notes += (
                    "Container termination reported an error: "
                    + state.timeout_cleanup_error,
                )
        elif state.exit_code == 0:
            status = SandboxExecutionStatus.COMPLETED
            notes = ()
        else:
            status = SandboxExecutionStatus.FAILED
            notes = ("Container exited with a non-zero status.",)
        return SandboxExecutionResult(
            sandbox_id=session.sandbox_id,
            status=status,
            isolation_backend=self.backend_id,
            exit_code=state.exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            started_at=state.started_at,
            completed_at=completed_at,
            notes=notes,
        )

    def cleanup(self, session: SandboxBackendSession) -> None:
        if (
            not isinstance(session, SandboxBackendSession)
            or session.backend_id != self.backend_id
            or not isinstance(session.handle, _DockerSession)
        ):
            raise TypeError("session must be a Docker session created by this backend")
        try:
            session.handle.container.remove(force=True, v=True)
        except Exception as exc:
            raise DockerSandboxBackendError(
                f"Docker container cleanup failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _get_client(self) -> _DockerClient:
        if self._client is not None:
            return self._client
        if not self._sdk_checked:
            self._sdk_checked = True
            try:
                sdk = importlib.import_module("docker")
                self._client = sdk.from_env(timeout=self._client_timeout_seconds)
            except ImportError as exc:
                self._sdk_error = (
                    "Docker Python SDK is not installed; install the optional "
                    "'docker' package explicitly to enable this backend."
                )
                raise DockerSandboxBlockedError(self._sdk_error) from exc
            except Exception as exc:
                raise DockerSandboxBlockedError(
                    f"Could not initialize Docker SDK client: {type(exc).__name__}: {exc}"
                ) from exc
        if self._client is None:
            raise DockerSandboxBlockedError(
                self._sdk_error or "Docker SDK client is unavailable."
            )
        return self._client

    @staticmethod
    def _validate_types(
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> None:
        if not isinstance(sandbox, IntegrationSandbox):
            raise TypeError("sandbox must be an IntegrationSandbox")
        if not isinstance(request, SandboxExecutionRequest):
            raise TypeError("request must be a SandboxExecutionRequest")
        if sandbox.id != request.sandbox_id:
            raise DockerSandboxBlockedError(
                "Request sandbox_id does not match the supplied sandbox."
            )
        if sandbox.proposal_id != request.proposal_id:
            raise DockerSandboxBlockedError(
                "Request proposal_id does not match the supplied sandbox."
            )
        if sandbox.status != SandboxStatus.READY:
            raise DockerSandboxBlockedError("Sandbox must be READY before execution.")

    @staticmethod
    def _validate_policy(
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> None:
        policy = sandbox.isolation_policy
        if policy.network_mode != SandboxNetworkMode.DISABLED:
            raise DockerSandboxBlockedError(
                "Docker backend supports only disabled networking."
            )
        if policy.filesystem_mode != SandboxFilesystemMode.READ_ONLY:
            raise DockerSandboxBlockedError(
                "Docker backend supports only a read-only container filesystem."
            )
        if policy.process_mode != SandboxProcessMode.ISOLATED:
            raise DockerSandboxBlockedError(
                "Docker backend requires isolated process mode."
            )
        if policy.credential_mode != SandboxCredentialMode.NONE:
            raise DockerSandboxBlockedError(
                "Docker backend does not support credential injection."
            )
        if (
            policy.environment_mode != SandboxEnvironmentMode.MINIMAL
            or request.environment_mode != SandboxEnvironmentMode.MINIMAL
        ):
            raise DockerSandboxBlockedError(
                "Docker backend supports only the minimal environment policy."
            )
        limits = policy.resource_limits
        resources = request.requested_resources
        if (
            resources.max_memory_mb > limits.max_memory_mb
            or resources.max_cpu_seconds > limits.max_cpu_seconds
            or resources.max_processes > limits.max_processes
            or resources.max_disk_mb > limits.max_disk_mb
        ):
            raise DockerSandboxBlockedError(
                "Requested resource limits exceed the sandbox policy."
            )
        if (
            request.timeout_seconds > limits.max_cpu_seconds
            or request.timeout_seconds > resources.max_cpu_seconds
        ):
            raise DockerSandboxBlockedError(
                "Execution timeout exceeds the sandbox/requested CPU-time policy."
            )

    @staticmethod
    def _session_state(
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> _DockerSession:
        if (
            not isinstance(session, SandboxBackendSession)
            or session.backend_id != "docker"
            or session.sandbox_id != request.sandbox_id
            or not isinstance(session.handle, _DockerSession)
        ):
            raise TypeError("session does not belong to this Docker execution request")
        return session.handle

    @staticmethod
    def _decode_output(output: bytes | str) -> str:
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        if isinstance(output, str):
            return output
        raise TypeError("Docker output must be bytes or text")

    @staticmethod
    def _is_timeout(error: Exception) -> bool:
        error_type = type(error)
        return isinstance(error, TimeoutError) or (
            error_type.__name__ in {"ReadTimeout", "Timeout"}
            and error_type.__module__.startswith("requests.")
        )


def _create_isolated_container(
    client: _DockerClient,
    image: str,
    entrypoint: list[str],
    command: list[str],
    resources: SandboxResourceLimits,
    *,
    workspace_tmpfs: bool = False,
) -> _DockerContainer:
    tmpfs = {
        "/tmp": f"rw,nosuid,nodev,noexec,size={resources.max_disk_mb}m"
    }
    if workspace_tmpfs:
        tmpfs["/workspace"] = (
            f"rw,nosuid,nodev,noexec,size={resources.max_disk_mb}m,mode=1777"
        )
    return client.containers.create(
        image=image,
        entrypoint=entrypoint,
        command=command,
        detach=True,
        network_disabled=True,
        network_mode="none",
        read_only=True,
        privileged=False,
        user="65534:65534",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        mem_limit=f"{resources.max_memory_mb}m",
        nano_cpus=_NANO_CPUS_PER_CORE,
        pids_limit=resources.max_processes,
        storage_opt={"size": f"{resources.max_disk_mb}M"},
        tmpfs=tmpfs,
        environment={},
        auto_remove=False,
    )


def _validate_workspace_archive(archive: bytes) -> None:
    try:
        with tarfile.open(fileobj=BytesIO(archive), mode="r:") as tar:
            members = tar.getmembers()
    except (EOFError, tarfile.TarError, OSError):
        raise ValueError("Workspace archive is invalid") from None
    if not 1 <= len(members) <= 5200:
        raise ValueError("Workspace archive member count is invalid")

    names: set[str] = set()
    file_paths: set[str] = set()
    file_count = 0
    total_bytes = 0
    for member in members:
        name = member.name
        if not isinstance(name, str):
            raise ValueError("Workspace archive path is invalid")
        path = PurePosixPath(name)
        windows_path = PureWindowsPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or path.as_posix() != name
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or name in names
            or member.mode & 0o7000
            or set(member.pax_headers) - {"path"}
        ):
            raise ValueError("Workspace archive paths or file modes are unsafe")
        names.add(name)
        if member.isdir():
            if (
                member.size != 0
                or member.uid != 65534
                or member.gid != 65534
                or member.mode != 0o777
            ):
                raise ValueError("Workspace archive directory is invalid")
            continue
        if not member.isfile():
            raise ValueError("Workspace archive may contain only regular files")
        if member.uid != 65534 or member.gid != 65534 or member.mode != 0o666:
            raise ValueError("Workspace archive file metadata is invalid")
        file_count += 1
        if member.size < 0 or member.size > 1024 * 1024:
            raise ValueError("Workspace archive file exceeds the byte limit")
        total_bytes += member.size
        file_paths.add(name)
        if file_count > 20 or total_bytes > 16 * 1024 * 1024:
            raise ValueError("Workspace archive exceeds file or byte limits")
    if file_count == 0:
        raise ValueError("Workspace archive contains no files")
    if any(
        parent.as_posix() in file_paths
        for path in file_paths
        for parent in PurePosixPath(path).parents
        if parent.as_posix() != "."
    ):
        raise ValueError("Workspace archive path conflicts with a regular file")


class DockerSandboxExecutor(SandboxExecutor):
    """Runs sandbox requests only through an explicitly configured Docker backend."""

    def __init__(
        self,
        backend: DockerSandboxBackend,
        registry: IntegrationSandboxRegistry,
    ) -> None:
        if not isinstance(backend, DockerSandboxBackend):
            raise TypeError("backend must be a DockerSandboxBackend")
        if not isinstance(registry, IntegrationSandboxRegistry):
            raise TypeError("registry must be an IntegrationSandboxRegistry")
        self._backend = backend
        self._registry = registry

    def execute(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        if not isinstance(sandbox, IntegrationSandbox):
            raise TypeError("sandbox must be an IntegrationSandbox")
        if not isinstance(request, SandboxExecutionRequest):
            raise TypeError("request must be a SandboxExecutionRequest")
        if self._registry.get(sandbox.id) is not sandbox:
            raise ValueError("Sandbox must be the instance registered in the registry")

        session: SandboxBackendSession | None = None
        result: SandboxExecutionResult | None = None
        execution_started = False
        try:
            session = self._backend.prepare(sandbox, request)
            self._registry._transition_for_executor(sandbox.id, SandboxStatus.RUNNING)
            execution_started = True
            self._backend.execute(session, request)
            result = self._backend.collect_result(session, request)
            if result.sandbox_id != sandbox.id or result.isolation_backend != "docker":
                raise DockerSandboxBackendError(
                    "Docker backend returned a result with inconsistent identity."
                )
        except DockerSandboxBlockedError as exc:
            result = self._failure_result(
                sandbox.id,
                SandboxExecutionStatus.BLOCKED,
                "none",
                str(exc),
            )
        except DockerSandboxError as exc:
            result = self._failure_result(
                sandbox.id,
                SandboxExecutionStatus.FAILED if execution_started else SandboxExecutionStatus.BLOCKED,
                "docker" if session is not None else "none",
                str(exc),
            )
        except Exception as exc:
            result = self._failure_result(
                sandbox.id,
                SandboxExecutionStatus.FAILED if execution_started else SandboxExecutionStatus.BLOCKED,
                "docker" if session is not None else "none",
                f"Docker backend error: {type(exc).__name__}: {exc}",
            )

        cleanup_error: str | None = None
        if session is not None:
            try:
                self._backend.cleanup(session)
            except DockerSandboxError as exc:
                cleanup_error = str(exc)
            except Exception as exc:
                cleanup_error = f"Container cleanup failed: {type(exc).__name__}: {exc}"

        if cleanup_error is not None:
            base_result = result or self._failure_result(
                sandbox.id,
                SandboxExecutionStatus.FAILED,
                "docker" if session is not None else "none",
                cleanup_error,
            )
            result = SandboxExecutionResult(
                sandbox_id=base_result.sandbox_id,
                status=SandboxExecutionStatus.FAILED,
                isolation_backend=base_result.isolation_backend,
                exit_code=base_result.exit_code,
                stdout=base_result.stdout,
                stderr=base_result.stderr,
                duration_seconds=base_result.duration_seconds,
                started_at=base_result.started_at,
                completed_at=base_result.completed_at,
                notes=base_result.notes + (cleanup_error,),
            )

        if execution_started:
            target = (
                SandboxStatus.COMPLETED
                if result is not None
                and result.status == SandboxExecutionStatus.COMPLETED
                and cleanup_error is None
                else SandboxStatus.FAILED
            )
            self._registry._transition_for_executor(sandbox.id, target)
        return result or self._failure_result(
            sandbox.id,
            SandboxExecutionStatus.BLOCKED,
            "none",
            "Docker backend did not return an execution result.",
        )

    @staticmethod
    def _failure_result(
        sandbox_id: str,
        status: SandboxExecutionStatus,
        backend_id: str,
        note: str,
    ) -> SandboxExecutionResult:
        return SandboxExecutionResult(
            sandbox_id=sandbox_id,
            status=status,
            isolation_backend=backend_id,
            notes=(note,),
        )
