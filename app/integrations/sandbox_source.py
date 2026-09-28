from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from uuid import uuid4

from .models import IntegrationProposal
from .sandbox import IntegrationSandbox, IntegrationSandboxRegistry
from .source_staging import (
    GitHubSourceStager,
    SourceStagingResult,
    SourceStagingStatus,
    UnsafeSourceArchiveError,
    calculate_staged_source_digest,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_STAGING_ID_PATTERN = re.compile(r"^staging-[0-9a-f]{32}$")


class SandboxSourceBindingError(ValueError):
    """Raised when staged source cannot be safely bound to a sandbox."""


class SandboxSourceBindingStatus(str, Enum):
    BOUND = "bound"


@dataclass(frozen=True)
class SandboxSourceBinding:
    binding_id: str
    sandbox_id: str
    proposal_id: str
    source_discovery_id: str
    staging_id: str
    workspace_reference: str
    status: SandboxSourceBindingStatus
    sha256: str
    archive_sha256: str
    file_count: int
    total_bytes: int
    notes: tuple[str, ...]


class SandboxSourceBindingRegistry:
    """In-memory registry for validated, non-executable sandbox source references."""

    def __init__(
        self,
        sandbox_registry: IntegrationSandboxRegistry,
        *,
        source_stager: GitHubSourceStager,
    ) -> None:
        if not isinstance(sandbox_registry, IntegrationSandboxRegistry):
            raise TypeError("sandbox_registry must be an IntegrationSandboxRegistry")
        if not isinstance(source_stager, GitHubSourceStager):
            raise TypeError("source_stager must be a GitHubSourceStager")
        self._sandbox_registry = sandbox_registry
        self._workspace_root = source_stager.workspace_root.resolve(strict=True)
        self._project_root = source_stager.project_root.resolve(strict=True)
        self._ensure_directory(self._workspace_root, "Controlled staging root")
        if (
            self._is_inside(self._workspace_root, self._project_root)
            or self._is_inside(self._project_root, self._workspace_root)
        ):
            raise SandboxSourceBindingError(
                "Controlled staging root must be separate from the project repository."
            )
        self._bindings: dict[str, SandboxSourceBinding] = {}

    def bind(
        self,
        proposal: IntegrationProposal,
        sandbox: IntegrationSandbox,
        staging: SourceStagingResult,
    ) -> SandboxSourceBinding:
        if not isinstance(proposal, IntegrationProposal):
            raise SandboxSourceBindingError(
                "A valid IntegrationProposal is required."
            )
        if not isinstance(sandbox, IntegrationSandbox):
            raise SandboxSourceBindingError("A valid IntegrationSandbox is required.")
        if not isinstance(staging, SourceStagingResult):
            raise SandboxSourceBindingError(
                "A successfully completed SourceStagingResult is required."
            )
        try:
            registered_sandbox = self._sandbox_registry.get(sandbox.id)
        except ValueError as exc:
            raise SandboxSourceBindingError(
                "Sandbox must be registered before source can be bound."
            ) from exc
        if registered_sandbox is not sandbox:
            raise SandboxSourceBindingError(
                "Sandbox must be the registered sandbox instance."
            )
        self._validate_linkage(proposal, sandbox, staging)
        workspace = self._validate_workspace(staging)
        try:
            digest, file_count, total_bytes = calculate_staged_source_digest(workspace)
        except (OSError, UnsafeSourceArchiveError, ValueError) as exc:
            raise SandboxSourceBindingError(
                f"Staged workspace integrity validation failed: {exc}"
            ) from exc
        if (
            digest != staging.sha256
            or file_count != staging.file_count
            or total_bytes != staging.total_bytes
        ):
            raise SandboxSourceBindingError(
                "Staged workspace no longer matches its staging integrity metadata."
            )

        binding = SandboxSourceBinding(
            binding_id=f"source-binding-{uuid4().hex}",
            sandbox_id=sandbox.id,
            proposal_id=proposal.id,
            source_discovery_id=staging.source_discovery_id,
            staging_id=staging.staging_id,
            workspace_reference=str(workspace),
            status=SandboxSourceBindingStatus.BOUND,
            sha256=staging.sha256,
            archive_sha256=staging.archive_sha256,
            file_count=file_count,
            total_bytes=total_bytes,
            notes=(
                "Binding validates source identity only; it does not establish trust or approval.",
                "The workspace reference is data-only and is not executable by this binding.",
            ),
        )
        self._bindings[binding.binding_id] = binding
        return binding

    def get(self, binding_id: str) -> SandboxSourceBinding:
        try:
            return self._bindings[binding_id]
        except KeyError:
            raise ValueError(f"Sandbox source binding not found: {binding_id}") from None

    def list(self) -> list[SandboxSourceBinding]:
        return list(self._bindings.values())

    def _validate_linkage(
        self,
        proposal: IntegrationProposal,
        sandbox: IntegrationSandbox,
        staging: SourceStagingResult,
    ) -> None:
        if (
            proposal.id != sandbox.proposal_id
            or proposal.source_discovery_id != sandbox.source_discovery_id
            or staging.source_discovery_id != sandbox.source_discovery_id
            or staging.source_discovery_id != proposal.source_discovery_id
        ):
            raise SandboxSourceBindingError(
                "Proposal, sandbox, and staging discovery linkage do not match."
            )
        if staging.sandbox_id is not None and staging.sandbox_id != sandbox.id:
            raise SandboxSourceBindingError(
                "Staging result belongs to a different sandbox."
            )
        if (
            not _STAGING_ID_PATTERN.fullmatch(staging.staging_id)
            or staging.status is not SourceStagingStatus.STAGED
            or staging.complete is not True
        ):
            raise SandboxSourceBindingError(
                "Only successfully completed staging results can be bound."
            )
        if (
            not isinstance(staging.sha256, str)
            or not _SHA256_PATTERN.fullmatch(staging.sha256)
            or not isinstance(staging.archive_sha256, str)
            or not _SHA256_PATTERN.fullmatch(staging.archive_sha256)
        ):
            raise SandboxSourceBindingError(
                "Staging result is missing valid SHA-256 integrity metadata."
            )

    def _validate_workspace(self, staging: SourceStagingResult) -> Path:
        reference = staging.workspace_reference
        if not isinstance(reference, str) or not reference.strip():
            raise SandboxSourceBindingError(
                "Staging result has no workspace reference."
            )
        candidate = Path(reference)
        if not candidate.is_absolute() or ".." in candidate.parts:
            raise SandboxSourceBindingError(
                "Workspace reference must be an absolute, normalized path."
            )
        try:
            if stat.S_ISLNK(candidate.lstat().st_mode):
                raise SandboxSourceBindingError(
                    "Workspace reference cannot be a symbolic link."
                )
            if candidate.parent.resolve(strict=True) != self._workspace_root:
                raise SandboxSourceBindingError(
                    "Staged workspace is outside the controlled staging root."
                )
            workspace = candidate.resolve(strict=True)
        except SandboxSourceBindingError:
            raise
        except OSError as exc:
            raise SandboxSourceBindingError(
                "Staged workspace does not exist."
            ) from exc
        if workspace.parent != self._workspace_root:
            raise SandboxSourceBindingError(
                "Staged workspace is outside the controlled staging root."
            )
        expected_prefix = f"erselmetz-source-{staging.staging_id}-"
        if not workspace.name.startswith(expected_prefix):
            raise SandboxSourceBindingError(
                "Workspace identity does not match the staging result."
            )
        self._ensure_directory(workspace, "Staged workspace")
        if (
            self._is_inside(workspace, self._project_root)
            or self._is_inside(self._project_root, workspace)
        ):
            raise SandboxSourceBindingError(
                "Staged workspace must not overlap the project repository."
            )
        return workspace

    @staticmethod
    def _ensure_directory(path: Path, description: str) -> None:
        try:
            if stat.S_ISLNK(path.lstat().st_mode) or not path.is_dir():
                raise SandboxSourceBindingError(
                    f"{description} must be a real directory, not a symbolic link."
                )
        except OSError as exc:
            raise SandboxSourceBindingError(
                f"{description} does not exist or cannot be inspected."
            ) from exc

    @staticmethod
    def _is_inside(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
