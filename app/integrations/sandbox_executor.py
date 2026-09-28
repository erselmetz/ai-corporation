from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath

from .sandbox import (
    IntegrationSandbox,
    SandboxEnvironmentMode,
    SandboxResourceLimits,
    SandboxStatus,
)


class SandboxExecutionStatus(str, Enum):
    NOT_EXECUTED = "not_executed"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class SandboxExecutionError(Exception):
    """Base class for sandbox execution boundary errors."""


class SandboxExecutionNotAvailableError(SandboxExecutionError):
    """Raised when execution is requested but no isolated backend can run it."""


@dataclass(frozen=True)
class SandboxExecutionRequest:
    sandbox_id: str
    proposal_id: str
    entrypoint: str
    arguments: tuple[str, ...] = ()
    timeout_seconds: int = 60
    environment_mode: SandboxEnvironmentMode = SandboxEnvironmentMode.MINIMAL
    requested_resources: SandboxResourceLimits = field(
        default_factory=SandboxResourceLimits
    )

    def __post_init__(self) -> None:
        for name, value in (
            ("sandbox_id", self.sandbox_id),
            ("proposal_id", self.proposal_id),
            ("entrypoint", self.entrypoint),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if "\x00" in self.entrypoint or "\\" in self.entrypoint:
            raise ValueError("entrypoint must be a relative POSIX workspace path")
        path = PurePosixPath(self.entrypoint)
        windows_path = PureWindowsPath(self.entrypoint)
        if (
            path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or any(part in {"", ".", ".."} for part in self.entrypoint.split("/"))
        ):
            raise ValueError("entrypoint must be a normalized relative workspace path")
        if not isinstance(self.arguments, tuple) or any(
            not isinstance(argument, str) or "\x00" in argument
            for argument in self.arguments
        ):
            raise ValueError("arguments must be a tuple of strings without NUL")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, int)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive integer")
        if not isinstance(self.environment_mode, SandboxEnvironmentMode):
            raise TypeError("environment_mode must be a SandboxEnvironmentMode")
        if not isinstance(self.requested_resources, SandboxResourceLimits):
            raise TypeError(
                "requested_resources must be a SandboxResourceLimits"
            )


@dataclass(frozen=True)
class SandboxExecutionResult:
    sandbox_id: str
    status: SandboxExecutionStatus
    isolation_backend: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.sandbox_id, str) or not self.sandbox_id.strip():
            raise ValueError("sandbox_id cannot be empty")
        if not isinstance(self.status, SandboxExecutionStatus):
            raise TypeError("status must be a SandboxExecutionStatus")
        if not isinstance(self.isolation_backend, str) or not self.isolation_backend.strip():
            raise ValueError("isolation_backend cannot be empty")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise TypeError("exit_code must be an integer or None")
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise TypeError("stdout and stderr must be strings")
        if self.duration_seconds is not None and (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or self.duration_seconds < 0
        ):
            raise ValueError("duration_seconds must be non-negative or None")
        if not isinstance(self.notes, tuple) or any(
            not isinstance(note, str) or not note.strip() for note in self.notes
        ):
            raise ValueError("notes must be a tuple of non-empty strings")
        if self.status in {
            SandboxExecutionStatus.NOT_EXECUTED,
            SandboxExecutionStatus.BLOCKED,
        } and any(
            value is not None
            for value in (
                self.exit_code,
                self.duration_seconds,
                self.started_at,
                self.completed_at,
            )
        ):
            raise ValueError("Unexecuted results cannot report execution measurements")


@dataclass(frozen=True)
class SandboxBackendSession:
    sandbox_id: str
    backend_id: str
    handle: object = field(repr=False, compare=False)


class SandboxBackend(ABC):
    """Future boundary for a backend that genuinely enforces sandbox isolation."""

    @property
    @abstractmethod
    def backend_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def enforces_isolation(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def prepare(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxBackendSession:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def collect_result(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self, session: SandboxBackendSession) -> None:
        raise NotImplementedError


class UnavailableSandboxBackend(SandboxBackend):
    """Explicit no-execution backend; it never invokes host facilities."""

    @property
    def backend_id(self) -> str:
        return "none"

    @property
    def available(self) -> bool:
        return False

    @property
    def enforces_isolation(self) -> bool:
        return False

    def prepare(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxBackendSession:
        del sandbox, request
        raise SandboxExecutionNotAvailableError(
            "Actual sandbox execution backend is not configured."
        )

    def execute(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> None:
        del session, request
        raise SandboxExecutionNotAvailableError(
            "Actual sandbox execution backend is not configured."
        )

    def collect_result(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        del session, request
        raise SandboxExecutionNotAvailableError(
            "Actual sandbox execution backend is not configured."
        )

    def cleanup(self, session: SandboxBackendSession) -> None:
        del session
        raise SandboxExecutionNotAvailableError(
            "Actual sandbox execution backend is not configured."
        )


class SandboxExecutor(ABC):
    """Execution boundary; the Task 32 implementation always blocks execution."""

    @abstractmethod
    def execute(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        raise NotImplementedError


class UnavailableSandboxExecutor(SandboxExecutor):
    """Validate requests and block until a reviewed executor implementation exists."""

    def __init__(self, backend: SandboxBackend | None = None) -> None:
        if backend is not None and not isinstance(backend, SandboxBackend):
            raise TypeError("backend must be a SandboxBackend")
        self._backend = backend or UnavailableSandboxBackend()

    def execute(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        if not isinstance(sandbox, IntegrationSandbox):
            raise TypeError("sandbox must be an IntegrationSandbox")
        if not isinstance(request, SandboxExecutionRequest):
            raise TypeError("request must be a SandboxExecutionRequest")
        if request.sandbox_id != sandbox.id:
            raise ValueError("Request sandbox_id does not match the supplied sandbox")
        if request.proposal_id != sandbox.proposal_id:
            raise ValueError("Request proposal_id does not match the supplied sandbox")
        if sandbox.status != SandboxStatus.READY:
            raise ValueError("Sandbox must be READY before execution is requested")
        if request.timeout_seconds > sandbox.isolation_policy.resource_limits.max_cpu_seconds:
            raise ValueError("timeout_seconds exceeds the sandbox CPU-time policy")
        if request.timeout_seconds > request.requested_resources.max_cpu_seconds:
            raise ValueError("timeout_seconds exceeds requested CPU-time resources")
        if request.environment_mode != sandbox.isolation_policy.environment_mode:
            raise ValueError("environment_mode does not match the sandbox policy")
        if not self._within_limits(
            request.requested_resources,
            sandbox.isolation_policy.resource_limits,
        ):
            raise ValueError("requested_resources exceed the sandbox policy")

        reason = (
            "Actual sandbox execution backend is not configured."
            if not self._backend.available or not self._backend.enforces_isolation
            else "Sandbox execution is not implemented by this executor."
        )
        return SandboxExecutionResult(
            sandbox_id=sandbox.id,
            status=SandboxExecutionStatus.BLOCKED,
            isolation_backend="none",
            notes=(reason,),
        )

    @staticmethod
    def _within_limits(
        requested: SandboxResourceLimits,
        maximum: SandboxResourceLimits,
    ) -> bool:
        return (
            requested.max_memory_mb <= maximum.max_memory_mb
            and requested.max_cpu_seconds <= maximum.max_cpu_seconds
            and requested.max_processes <= maximum.max_processes
            and requested.max_disk_mb <= maximum.max_disk_mb
        )
