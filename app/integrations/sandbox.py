from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .models import IntegrationProposal, IntegrationStatus


class SandboxStatus(str, Enum):
    CONFIGURED = "configured"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


class SandboxFilesystemMode(str, Enum):
    READ_ONLY = "read_only"
    ISOLATED_WRITABLE = "isolated_writable"


class SandboxNetworkMode(str, Enum):
    DISABLED = "disabled"
    RESTRICTED = "restricted"


class SandboxProcessMode(str, Enum):
    DISABLED = "disabled"
    ISOLATED = "isolated"


class SandboxEnvironmentMode(str, Enum):
    MINIMAL = "minimal"
    CLEAN = "clean"


class SandboxCredentialMode(str, Enum):
    NONE = "none"
    SCOPED = "scoped"


class SandboxExecutionNotImplementedError(RuntimeError):
    """Raised when a lifecycle transition requires the future executor."""


@dataclass(frozen=True)
class SandboxResourceLimits:
    max_memory_mb: int = 512
    max_cpu_seconds: int = 60
    max_processes: int = 1
    max_disk_mb: int = 256

    def __post_init__(self) -> None:
        for name, value in (
            ("max_memory_mb", self.max_memory_mb),
            ("max_cpu_seconds", self.max_cpu_seconds),
            ("max_processes", self.max_processes),
            ("max_disk_mb", self.max_disk_mb),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class SandboxIsolationPolicy:
    filesystem_mode: SandboxFilesystemMode = SandboxFilesystemMode.READ_ONLY
    network_mode: SandboxNetworkMode = SandboxNetworkMode.DISABLED
    process_mode: SandboxProcessMode = SandboxProcessMode.DISABLED
    environment_mode: SandboxEnvironmentMode = SandboxEnvironmentMode.MINIMAL
    credential_mode: SandboxCredentialMode = SandboxCredentialMode.NONE
    resource_limits: SandboxResourceLimits = field(
        default_factory=SandboxResourceLimits
    )

    def __post_init__(self) -> None:
        enum_fields = (
            ("filesystem_mode", self.filesystem_mode, SandboxFilesystemMode),
            ("network_mode", self.network_mode, SandboxNetworkMode),
            ("process_mode", self.process_mode, SandboxProcessMode),
            ("environment_mode", self.environment_mode, SandboxEnvironmentMode),
            ("credential_mode", self.credential_mode, SandboxCredentialMode),
        )
        for name, value, expected_type in enum_fields:
            if not isinstance(value, expected_type):
                raise TypeError(f"{name} must be a {expected_type.__name__}")
        if not isinstance(self.resource_limits, SandboxResourceLimits):
            raise TypeError("resource_limits must be a SandboxResourceLimits")


_SANDBOX_TRANSITIONS: dict[SandboxStatus, set[SandboxStatus]] = {
    SandboxStatus.CONFIGURED: {SandboxStatus.READY, SandboxStatus.DESTROYED},
    SandboxStatus.READY: {SandboxStatus.RUNNING, SandboxStatus.DESTROYED},
    SandboxStatus.RUNNING: {
        SandboxStatus.COMPLETED,
        SandboxStatus.FAILED,
        SandboxStatus.DESTROYED,
    },
    SandboxStatus.COMPLETED: {SandboxStatus.DESTROYED},
    SandboxStatus.FAILED: {SandboxStatus.DESTROYED},
    SandboxStatus.DESTROYED: set(),
}


@dataclass
class IntegrationSandbox:
    id: str
    proposal_id: str
    source_discovery_id: str
    isolation_policy: SandboxIsolationPolicy = field(
        default_factory=SandboxIsolationPolicy
    )
    notes: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _status: SandboxStatus = field(
        default=SandboxStatus.CONFIGURED,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("proposal_id", self.proposal_id),
            ("source_discovery_id", self.source_discovery_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Sandbox {name} cannot be empty")
        if not isinstance(self.isolation_policy, SandboxIsolationPolicy):
            raise TypeError("isolation_policy must be a SandboxIsolationPolicy")
        if not isinstance(self.notes, tuple) or any(
            not isinstance(note, str) or not note.strip() for note in self.notes
        ):
            raise ValueError("Sandbox notes must be a tuple of non-empty strings")

    @property
    def status(self) -> SandboxStatus:
        return self._status

    @property
    def isolation_enforced(self) -> bool:
        return False

    def transition(self, target: SandboxStatus) -> None:
        if not isinstance(target, SandboxStatus):
            raise TypeError("Target must be a SandboxStatus")
        if target == SandboxStatus.RUNNING:
            raise SandboxExecutionNotImplementedError(
                "Sandbox execution is not implemented"
            )
        if target not in _SANDBOX_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid sandbox transition: {self.status.value} -> {target.value}"
            )
        self._status = target

    def _transition_for_executor(self, target: SandboxStatus) -> None:
        if not isinstance(target, SandboxStatus):
            raise TypeError("Target must be a SandboxStatus")
        if target not in _SANDBOX_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid sandbox transition: {self.status.value} -> {target.value}"
            )
        if target not in {SandboxStatus.RUNNING, SandboxStatus.COMPLETED, SandboxStatus.FAILED}:
            raise ValueError("Executor transitions are limited to execution states")
        self._status = target


class IntegrationSandboxRegistry:
    """In-memory metadata registry; it does not create or enforce isolation."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, IntegrationSandbox] = {}

    def create(
        self,
        sandbox_id: str,
        proposal: IntegrationProposal,
        *,
        isolation_policy: SandboxIsolationPolicy | None = None,
        notes: tuple[str, ...] = (),
    ) -> IntegrationSandbox:
        if not isinstance(proposal, IntegrationProposal):
            raise TypeError("proposal must be an IntegrationProposal")
        if proposal.status != IntegrationStatus.PROPOSED:
            raise ValueError("Sandbox creation requires a PROPOSED proposal")
        if proposal.source_discovery_id is None:
            raise ValueError("Proposal must reference a source discovery result")
        if sandbox_id in self._sandboxes:
            raise ValueError(f"Sandbox already registered: {sandbox_id}")
        sandbox = IntegrationSandbox(
            id=sandbox_id,
            proposal_id=proposal.id,
            source_discovery_id=proposal.source_discovery_id,
            isolation_policy=isolation_policy or SandboxIsolationPolicy(),
            notes=notes,
        )
        self._sandboxes[sandbox.id] = sandbox
        return sandbox

    def get(self, sandbox_id: str) -> IntegrationSandbox:
        try:
            return self._sandboxes[sandbox_id]
        except KeyError:
            raise ValueError(f"Sandbox not found: {sandbox_id}") from None

    def list(self) -> list[IntegrationSandbox]:
        return list(self._sandboxes.values())

    def transition(self, sandbox_id: str, target: SandboxStatus) -> None:
        self.get(sandbox_id).transition(target)

    def _transition_for_executor(
        self, sandbox_id: str, target: SandboxStatus
    ) -> IntegrationSandbox:
        sandbox = self.get(sandbox_id)
        sandbox._transition_for_executor(target)
        return sandbox

    def destroy(self, sandbox_id: str) -> None:
        self.transition(sandbox_id, SandboxStatus.DESTROYED)
