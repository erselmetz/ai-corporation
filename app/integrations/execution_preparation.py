from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .models import IntegrationProposal
from .registry import IntegrationRegistry
from .sandbox import (
    IntegrationSandbox,
    IntegrationSandboxRegistry,
    SandboxCredentialMode,
    SandboxEnvironmentMode,
    SandboxIsolationPolicy,
    SandboxStatus,
)
from .sandbox_source import (
    SandboxSourceBinding,
    SandboxSourceBindingRegistry,
    SandboxSourceBindingStatus,
)
from .source_staging import (
    GitHubSourceStager,
    SourceStagingResult,
    SourceStagingStatus,
    UnsafeSourceArchiveError,
    calculate_staged_source_digest,
)

_STAGING_ID_PATTERN = re.compile(r"^staging-[0-9a-f]{32}$")
_BINDING_ID_PATTERN = re.compile(r"^source-binding-[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ExecutionPreparationStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    INVALID = "invalid"


@dataclass(frozen=True)
class ExecutionPreparationRequest:
    """Only existing IDs and staging metadata; intentionally no command/env fields."""

    proposal_id: str
    sandbox_id: str
    staging_result: SourceStagingResult | None
    binding_id: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("proposal_id", self.proposal_id),
            ("sandbox_id", self.sandbox_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if self.binding_id is not None and (
            not isinstance(self.binding_id, str) or not self.binding_id.strip()
        ):
            raise ValueError("binding_id cannot be empty")


@dataclass(frozen=True)
class ExecutionPreparation:
    preparation_id: str
    proposal_id: str
    sandbox_id: str
    source_discovery_id: str | None
    staging_id: str | None
    source_binding_id: str | None
    workspace_reference: str | None
    source_sha256: str | None
    archive_sha256: str | None
    file_count: int | None
    total_bytes: int | None
    isolation_policy: SandboxIsolationPolicy | None
    prepared_at: datetime
    status: ExecutionPreparationStatus
    validation_notes: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.preparation_id, str) or not self.preparation_id.strip():
            raise ValueError("preparation_id cannot be empty")
        if not isinstance(self.status, ExecutionPreparationStatus):
            raise TypeError("status must be an ExecutionPreparationStatus")
        if self.prepared_at.tzinfo is None:
            raise ValueError("prepared_at must be timezone-aware")
        for name, values in (
            ("validation_notes", self.validation_notes),
            ("limitations", self.limitations),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"{name} must be a tuple of non-empty strings")
        if self.status is ExecutionPreparationStatus.READY and any(
            value is None
            for value in (
                self.source_discovery_id,
                self.staging_id,
                self.source_binding_id,
                self.workspace_reference,
                self.source_sha256,
                self.archive_sha256,
                self.file_count,
                self.total_bytes,
                self.isolation_policy,
            )
        ):
            raise ValueError("Ready preparation requires complete source metadata")


class ExecutionPreparationRegistry:
    """In-memory validation records; preparing never invokes an execution backend."""

    def __init__(
        self,
        *,
        proposals: IntegrationRegistry,
        sandboxes: IntegrationSandboxRegistry,
        bindings: SandboxSourceBindingRegistry,
        source_stager: GitHubSourceStager,
        project_root: str | Path | None = None,
    ) -> None:
        if not isinstance(proposals, IntegrationRegistry):
            raise TypeError("proposals must be an IntegrationRegistry")
        if not isinstance(sandboxes, IntegrationSandboxRegistry):
            raise TypeError("sandboxes must be an IntegrationSandboxRegistry")
        if not isinstance(bindings, SandboxSourceBindingRegistry):
            raise TypeError("bindings must be a SandboxSourceBindingRegistry")
        if not isinstance(source_stager, GitHubSourceStager):
            raise TypeError("source_stager must be a GitHubSourceStager")
        self._proposals = proposals
        self._sandboxes = sandboxes
        self._bindings = bindings
        self._workspace_root = source_stager.workspace_root.resolve(strict=True)
        self._project_root = (
            Path(project_root).resolve(strict=True)
            if project_root is not None
            else source_stager.project_root.resolve(strict=True)
        )
        self._preparations: dict[str, ExecutionPreparation] = {}

    def prepare(
        self,
        request: ExecutionPreparationRequest,
    ) -> ExecutionPreparation:
        if not isinstance(request, ExecutionPreparationRequest):
            raise TypeError("request must be an ExecutionPreparationRequest")

        proposal: IntegrationProposal | None = None
        sandbox: IntegrationSandbox | None = None
        staging = request.staging_result
        binding: SandboxSourceBinding | None = None
        notes: list[str] = []
        status = ExecutionPreparationStatus.READY

        try:
            proposal = self._proposals.get(request.proposal_id)
        except ValueError:
            status = ExecutionPreparationStatus.INVALID
            notes.append("Integration proposal is not registered.")

        try:
            sandbox = self._sandboxes.get(request.sandbox_id)
        except ValueError:
            status = ExecutionPreparationStatus.INVALID
            notes.append("Sandbox is not registered.")

        if staging is None:
            status = ExecutionPreparationStatus.INVALID
            notes.append("Source staging result is missing.")
        elif not isinstance(staging, SourceStagingResult):
            status = ExecutionPreparationStatus.INVALID
            notes.append("Source staging result has an invalid type.")
            staging = None
        elif staging.status is not SourceStagingStatus.STAGED or not staging.complete:
            status = ExecutionPreparationStatus.BLOCKED
            notes.append("Source staging did not complete successfully.")

        if request.binding_id is None:
            status = ExecutionPreparationStatus.INVALID
            notes.append("Source binding is missing.")
        else:
            try:
                binding = self._bindings.get(request.binding_id)
            except ValueError:
                status = ExecutionPreparationStatus.INVALID
                notes.append("Source binding is not registered.")

        if proposal is not None and sandbox is not None:
            if (
                proposal.source_discovery_id is None
                or proposal.id != sandbox.proposal_id
                or proposal.source_discovery_id != sandbox.source_discovery_id
            ):
                status = ExecutionPreparationStatus.INVALID
                notes.append("Proposal and sandbox linkage does not match.")
            if sandbox.status not in {SandboxStatus.CONFIGURED, SandboxStatus.READY}:
                status = ExecutionPreparationStatus.BLOCKED
                notes.append(
                    "Sandbox lifecycle state is not eligible for future execution preparation."
                )
            if (
                sandbox.isolation_policy is None
                or sandbox.isolation_policy.credential_mode
                is not SandboxCredentialMode.NONE
                or sandbox.isolation_policy.environment_mode
                not in {SandboxEnvironmentMode.MINIMAL, SandboxEnvironmentMode.CLEAN}
            ):
                status = ExecutionPreparationStatus.BLOCKED
                notes.append(
                    "Sandbox policy is missing or allows credentials/environment inheritance."
                )

        if proposal is not None and sandbox is not None and staging is not None:
            if staging.source_discovery_id != proposal.source_discovery_id:
                status = ExecutionPreparationStatus.INVALID
                notes.append("Staging source discovery does not match the proposal.")
            if staging.source_discovery_id != sandbox.source_discovery_id:
                status = ExecutionPreparationStatus.INVALID
                notes.append("Staging source discovery does not match the sandbox.")

        if binding is not None and staging is not None:
            if (
                binding.status is not SandboxSourceBindingStatus.BOUND
                or binding.staging_id != staging.staging_id
                or binding.source_discovery_id != staging.source_discovery_id
                or binding.sha256 != staging.sha256
                or binding.archive_sha256 != staging.archive_sha256
                or binding.file_count != staging.file_count
                or binding.total_bytes != staging.total_bytes
            ):
                status = ExecutionPreparationStatus.INVALID
                notes.append("Source binding does not match the staging result.")
            if (
                proposal is not None
                and binding.proposal_id != proposal.id
                or sandbox is not None
                and binding.sandbox_id != sandbox.id
            ):
                status = ExecutionPreparationStatus.INVALID
                notes.append("Source binding does not match proposal/sandbox IDs.")

        workspace: Path | None = None
        if (
            status is ExecutionPreparationStatus.READY
            and proposal is not None
            and sandbox is not None
            and staging is not None
            and binding is not None
        ):
            try:
                workspace = self._validate_workspace(staging, binding)
                digest, file_count, total_bytes = calculate_staged_source_digest(
                    workspace
                )
                if (
                    digest != staging.sha256
                    or digest != binding.sha256
                    or file_count != staging.file_count
                    or file_count != binding.file_count
                    or total_bytes != staging.total_bytes
                    or total_bytes != binding.total_bytes
                ):
                    status = ExecutionPreparationStatus.BLOCKED
                    notes.append(
                        "Staged source identity, file count, or byte size changed."
                    )
                else:
                    notes.extend(
                        (
                            "Proposal, sandbox, discovery, staging, and binding linkage validated.",
                            "Staged workspace boundary and current SHA-256/count/size validated.",
                            "Sandbox isolation policy metadata validated; isolation is not performed during preparation.",
                            "No command, host environment, or credential reference is accepted by this request.",
                        )
                    )
            except (OSError, UnsafeSourceArchiveError, ValueError) as exc:
                status = ExecutionPreparationStatus.BLOCKED
                notes.append(f"Staged workspace validation failed: {exc}")

        preparation = self._build_record(
            request=request,
            staging=staging,
            binding=binding,
            workspace=workspace if status is ExecutionPreparationStatus.READY else None,
            status=status,
            notes=tuple(notes),
            isolation_policy=(
                sandbox.isolation_policy if sandbox is not None else None
            ),
        )
        existing = self._preparations.get(preparation.preparation_id)
        if existing is not None:
            return existing
        self._preparations[preparation.preparation_id] = preparation
        return preparation

    def get(self, preparation_id: str) -> ExecutionPreparation:
        try:
            return self._preparations[preparation_id]
        except KeyError:
            raise ValueError(
                f"Execution preparation not found: {preparation_id}"
            ) from None

    def list(self) -> list[ExecutionPreparation]:
        return list(self._preparations.values())

    def verify_workspace(self, preparation_id: str) -> bool:
        """Revalidate a ready preparation immediately before any future use."""
        preparation = self.get(preparation_id)
        if preparation.status is not ExecutionPreparationStatus.READY:
            return False
        assert preparation.workspace_reference is not None
        try:
            workspace = self._validate_workspace_reference(
                preparation.workspace_reference, preparation.staging_id
            )
            digest, file_count, total_bytes = calculate_staged_source_digest(workspace)
        except (OSError, UnsafeSourceArchiveError, ValueError):
            return False
        return (
            digest == preparation.source_sha256
            and file_count == preparation.file_count
            and total_bytes == preparation.total_bytes
        )

    def _validate_workspace(
        self,
        staging: SourceStagingResult,
        binding: SandboxSourceBinding,
    ) -> Path:
        if (
            not isinstance(staging.staging_id, str)
            or not _STAGING_ID_PATTERN.fullmatch(staging.staging_id)
            or not isinstance(binding.binding_id, str)
            or not _BINDING_ID_PATTERN.fullmatch(binding.binding_id)
            or not isinstance(staging.sha256, str)
            or not _SHA256_PATTERN.fullmatch(staging.sha256)
            or not isinstance(staging.archive_sha256, str)
            or not _SHA256_PATTERN.fullmatch(staging.archive_sha256)
        ):
            raise ValueError("Staging/binding identity metadata is invalid.")
        if (
            staging.workspace_reference != binding.workspace_reference
            or staging.sha256 != binding.sha256
            or staging.archive_sha256 != binding.archive_sha256
            or staging.file_count != binding.file_count
            or staging.total_bytes != binding.total_bytes
        ):
            raise ValueError("Binding and staging integrity metadata do not match.")
        return self._validate_workspace_reference(
            binding.workspace_reference, staging.staging_id
        )

    def _validate_workspace_reference(
        self,
        reference: str,
        staging_id: str | None,
    ) -> Path:
        candidate = Path(reference)
        if (
            not candidate.is_absolute()
            or ".." in candidate.parts
            or not isinstance(staging_id, str)
            or not _STAGING_ID_PATTERN.fullmatch(staging_id)
        ):
            raise ValueError("Workspace reference is not a controlled absolute path.")
        try:
            if stat.S_ISLNK(candidate.lstat().st_mode):
                raise ValueError("Workspace reference cannot be a symbolic link.")
            if candidate.parent.resolve(strict=True) != self._workspace_root:
                raise ValueError("Workspace is outside the configured staging root.")
            workspace = candidate.resolve(strict=True)
            if stat.S_ISLNK(workspace.lstat().st_mode) or not workspace.is_dir():
                raise ValueError("Workspace must be a real directory.")
        except OSError as exc:
            raise ValueError("Staged workspace does not exist.") from exc
        if workspace.parent != self._workspace_root:
            raise ValueError("Workspace escaped the configured staging root.")
        if not workspace.name.startswith(f"erselmetz-source-{staging_id}-"):
            raise ValueError("Workspace name does not match the staging ID.")
        if self._is_inside(workspace, self._project_root) or self._is_inside(
            self._project_root, workspace
        ):
            raise ValueError("Workspace must not overlap the project repository.")
        return workspace

    def _build_record(
        self,
        *,
        request: ExecutionPreparationRequest,
        staging: SourceStagingResult | None,
        binding: SandboxSourceBinding | None,
        workspace: Path | None,
        status: ExecutionPreparationStatus,
        notes: tuple[str, ...],
        isolation_policy: SandboxIsolationPolicy | None,
    ) -> ExecutionPreparation:
        source_discovery_id = (
            staging.source_discovery_id if staging is not None else None
        )
        staging_id = staging.staging_id if staging is not None else None
        sha256 = staging.sha256 if staging is not None else None
        archive_sha256 = staging.archive_sha256 if staging is not None else None
        file_count = staging.file_count if staging is not None else None
        total_bytes = staging.total_bytes if staging is not None else None
        identity = {
            "proposal_id": request.proposal_id,
            "sandbox_id": request.sandbox_id,
            "source_discovery_id": source_discovery_id,
            "staging_id": staging_id,
            "binding_id": binding.binding_id if binding is not None else None,
            "workspace": str(workspace) if workspace is not None else None,
            "sha256": sha256,
            "archive_sha256": archive_sha256,
            "isolation_policy": self._policy_identity(isolation_policy),
            "status": status.value,
            "notes": notes,
        }
        preparation_id = "preparation-" + hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode("utf-8")
        ).hexdigest()[:32]
        return ExecutionPreparation(
            preparation_id=preparation_id,
            proposal_id=request.proposal_id,
            sandbox_id=request.sandbox_id,
            source_discovery_id=source_discovery_id,
            staging_id=staging_id,
            source_binding_id=binding.binding_id if binding is not None else None,
            workspace_reference=str(workspace) if workspace is not None else None,
            source_sha256=sha256,
            archive_sha256=archive_sha256,
            file_count=file_count,
            total_bytes=total_bytes,
            isolation_policy=isolation_policy,
            prepared_at=datetime.now(timezone.utc),
            status=status,
            validation_notes=notes,
            limitations=(
                "SHA-256 verifies source identity only, not safety, trust, or approval.",
                "This record validates readiness; it does not execute source or enforce sandbox isolation.",
                "A future executor must revalidate the workspace using verify_workspace before use.",
            ),
        )

    @staticmethod
    def _is_inside(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    @staticmethod
    def _policy_identity(
        policy: SandboxIsolationPolicy | None,
    ) -> dict[str, object] | None:
        if policy is None:
            return None
        return {
            "filesystem_mode": policy.filesystem_mode.value,
            "network_mode": policy.network_mode.value,
            "process_mode": policy.process_mode.value,
            "environment_mode": policy.environment_mode.value,
            "credential_mode": policy.credential_mode.value,
            "resources": {
                "max_memory_mb": policy.resource_limits.max_memory_mb,
                "max_cpu_seconds": policy.resource_limits.max_cpu_seconds,
                "max_processes": policy.resource_limits.max_processes,
                "max_disk_mb": policy.resource_limits.max_disk_mb,
            },
        }
