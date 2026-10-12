"""Owner-scoped, bounded patch experiments in disposable workspaces."""

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pathlib import PurePosixPath
from threading import RLock
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from starlette.responses import Response

from app.application import DiagnosticEvidence
from app.application.services.code_review import (
    CodeReviewProviderError,
    CodeReviewReport,
    CodeReviewResponseError,
    CodeReviewService,
)
from app.application.services.maintenance_sandbox import (
    MaintenanceSandboxReport,
    MaintenanceSandboxService,
    MaintenanceSandboxStatus,
)
from app.approval import ApprovalStatus
from app.application.services.patch_development import (
    PatchDevelopmentService,
    PatchWorkspace,
    _validate_relative_path,
    _source_digest,
    _source_file,
)
from app.integrations import SandboxImagePolicy
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/maintenance/experiments")
require_experiment = require_permission("maintenance:experiment")
require_activation = require_permission("maintenance:activate")
ExperimentIdentifier = Annotated[str, ApiPath(min_length=1, max_length=64)]


class ExperimentSourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)
    content: str = Field(max_length=PatchDevelopmentService.MAX_FILE_BYTES)

    @field_validator("content")
    @classmethod
    def content_must_fit_utf8_limit(cls, value: str) -> str:
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise ValueError("Source file must be valid UTF-8 text") from error
        if size > PatchDevelopmentService.MAX_FILE_BYTES:
            raise ValueError("Source file exceeds the byte limit")
        return value


class ExperimentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str = Field(min_length=1, max_length=128)
    files: tuple[ExperimentSourceFile, ...] = Field(
        min_length=1, max_length=PatchDevelopmentService.MAX_FILES
    )
    unified_diff: str = Field(max_length=PatchDevelopmentService.MAX_PATCH_BYTES)

    @field_validator("files")
    @classmethod
    def files_must_be_unique_and_bounded(cls, files):
        paths = tuple(file.path for file in files)
        if len(set(paths)) != len(paths):
            raise ValueError("Experiment source paths must be unique")
        if sum(len(file.content.encode("utf-8")) for file in files) > (
            PatchDevelopmentService.MAX_TOTAL_SOURCE_BYTES
        ):
            raise ValueError("Experiment source exceeds the total byte limit")
        return files


class ExperimentTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_tests: tuple[str, ...] = Field(
        min_length=1, max_length=20
    )
    timeout_seconds: int = Field(default=60, ge=1, le=60)


class ExperimentReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_agent_id: str = Field(min_length=1, max_length=256)
    cloud_consent: StrictBool = False


class ExperimentActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_request_id: str = Field(min_length=1, max_length=128)


@dataclass(slots=True)
class _ExperimentRecord:
    owner: str
    workspace: PatchWorkspace
    source_directory: tempfile.TemporaryDirectory
    created_at: datetime
    test_report: MaintenanceSandboxReport | None = None
    review_report: CodeReviewReport | None = None
    activation_result: dict | None = None
    active: bool = False


class MaintenanceExperimentService:
    """Bind workspace ownership and preserve its source snapshot until disposal."""

    MAX_EXPERIMENTS = PatchDevelopmentService.MAX_WORKSPACES
    MAX_REQUEST_BYTES = 24 * 1024 * 1024
    MAX_REVIEW_PATCH_BYTES = CodeReviewService.MAX_EVIDENCE_BYTES - 8 * 1024
    APPROVAL_MAX_AGE = timedelta(hours=24)
    RECOVERY_LIMITS = (
        "The uploaded source and patch are isolated from the active installation.",
        "Experiments, test results, and review records are process-local and are lost on restart.",
        "Disposal permanently removes the experiment workspace; no automatic backup or rollback is created.",
        "This task does not approve, integrate, commit, or apply the proposed patch.",
    )
    EXECUTION_POLICY = {
        "allowed_actions": (
            "Apply the supplied unified diff to the explicitly uploaded files.",
            "Run only explicitly selected Python test files in the approved Docker sandbox.",
            "Request one independent review of the exact patch and bounded test evidence.",
        ),
        "arbitrary_commands": False,
        "network_access": False,
        "host_mounts": False,
        "automatic_image_pull": False,
        "maximum_test_timeout_seconds": MaintenanceSandboxService.MAX_TIMEOUT_SECONDS,
        "maximum_test_output_bytes": MaintenanceSandboxService.MAX_OUTPUT_BYTES,
        "resource_limits": {
            "memory_mb": MaintenanceSandboxService.RESOURCES.max_memory_mb,
            "cpu_seconds": MaintenanceSandboxService.RESOURCES.max_cpu_seconds,
            "processes": MaintenanceSandboxService.RESOURCES.max_processes,
            "disk_mb": MaintenanceSandboxService.RESOURCES.max_disk_mb,
        },
    }

    def __init__(
        self,
        application_service,
        image_policy: SandboxImagePolicy,
        *,
        activation_root: Path,
    ):
        if not isinstance(image_policy, SandboxImagePolicy):
            raise TypeError("image_policy must be a SandboxImagePolicy")
        self._application = application_service
        self._image_policy = image_policy
        try:
            self._activation_root = Path(activation_root).resolve(strict=True)
        except (OSError, RuntimeError, TypeError, ValueError):
            raise ValueError("Maintenance activation checkout is unavailable") from None
        if not self._activation_root.is_dir():
            raise ValueError("Maintenance activation checkout is unavailable")
        self._records: dict[str, _ExperimentRecord] = {}
        self._lock = RLock()
        self._activation_lock = RLock()

    def create(
        self,
        owner: str,
        request: ExperimentCreateRequest,
    ) -> dict:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Experiment owner is required")
        if not isinstance(request, ExperimentCreateRequest):
            raise TypeError("Expected ExperimentCreateRequest")

        source_paths = tuple(_validate_relative_path(item.path) for item in request.files)
        folded_paths = tuple(path.casefold() for path in source_paths)
        if len(set(folded_paths)) != len(folded_paths):
            raise ValueError("Experiment source paths must be unique on supported filesystems")
        path_parts = tuple(
            tuple(part.casefold() for part in PurePosixPath(path).parts)
            for path in source_paths
        )
        if any(
            left[: len(right)] == right or right[: len(left)] == left
            for index, left in enumerate(path_parts)
            for right in path_parts[index + 1 :]
        ):
            raise ValueError("Experiment source files cannot contain file/directory path conflicts")
        source_contents = {item.path: item.content for item in request.files}
        source_directory = tempfile.TemporaryDirectory(prefix="ai-corp-experiment-source-")
        try:
            root = Path(source_directory.name)
            for relative_path, content in zip(source_paths, source_contents.values()):
                destination = root.joinpath(*Path(relative_path).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content.encode("utf-8"))
            workspace = self._application.develop_patch(
                request.proposal_id,
                root,
                source_paths,
                request.unified_diff,
            )
            with self._lock:
                if len(self._records) >= self.MAX_EXPERIMENTS:
                    self._application.dispose_patch_workspace(workspace.workspace_id)
                    raise ValueError("Maintenance experiment limit reached")
                record = _ExperimentRecord(
                    owner=owner,
                    workspace=workspace,
                    source_directory=source_directory,
                    created_at=datetime.now(timezone.utc),
                )
                self._records[workspace.workspace_id] = record
                return self._snapshot(record)
        except BaseException:
            source_directory.cleanup()
            raise

    def get(self, owner: str, workspace_id: str) -> dict:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            return self._snapshot(record)

    def run_tests(
        self,
        owner: str,
        workspace_id: str,
        selected_tests: tuple[str, ...],
        timeout_seconds: int,
    ) -> dict:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            if record.active:
                raise RuntimeError("Experiment already has an active operation")
            if record.test_report is not None:
                raise RuntimeError("Experiment tests have already been recorded")
            if record.review_report is not None:
                raise RuntimeError("Experiment review has already been recorded")
            if (
                not isinstance(selected_tests, tuple)
                or not 1 <= len(selected_tests) <= 20
                or len(set(selected_tests)) != len(selected_tests)
                or any(path not in record.workspace.files for path in selected_tests)
            ):
                raise ValueError("Tests must be selected from the exact experiment files")
            record.active = True

        try:
            report = self._application.run_sandboxed_tests(
                workspace_id,
                selected_tests,
                self._image_policy,
                timeout_seconds=timeout_seconds,
            )
        except BaseException:
            with self._lock:
                record.active = False
            raise
        with self._lock:
            record.active = False
            record.test_report = report
            return self._snapshot(record)

    def review(
        self,
        owner: str,
        workspace_id: str,
        reviewer_agent_id: str,
        *,
        cloud_consent: bool,
    ) -> dict:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            if record.active:
                raise RuntimeError("Experiment already has an active operation")
            if record.review_report is not None:
                raise RuntimeError("Experiment review has already been recorded")
            if (
                record.test_report is None
                or record.test_report.status is not MaintenanceSandboxStatus.PASSED
            ):
                raise PermissionError(
                    "Independent review requires tests to pass in the isolated backend"
                )
            if len(record.workspace.unified_diff.encode("utf-8")) > (
                self.MAX_REVIEW_PATCH_BYTES
            ):
                raise ValueError(
                    "Patch exceeds the bounded independent-review evidence limit"
                )
            proposal = self._application.get_maintenance_proposal(
                record.workspace.proposal_id
            )
            if reviewer_agent_id == proposal.diagnostic.agent_id:
                raise PermissionError(
                    "The diagnosing Agent cannot independently review this patch"
                )
            reviewer = self._application.get_agent(reviewer_agent_id)
            if (
                self._application.provider_requires_explicit_cloud_consent(
                    reviewer.provider
                )
                and cloud_consent is not True
            ):
                raise PermissionError(
                    "Explicit per-review cloud consent is required for this reviewer"
                )
            record.active = True
            evidence = (
                DiagnosticEvidence(
                    "exact-patch",
                    record.workspace.unified_diff,
                ),
                DiagnosticEvidence(
                    "experiment-scope",
                    json.dumps(
                        {
                            "proposal_id": record.workspace.proposal_id,
                            "allowed_files": record.workspace.files,
                            "changed_files": record.workspace.changed_files,
                            "patch_sha256": record.workspace.patch_sha256,
                            "source_sha256": record.workspace.source_sha256,
                            "test_status": record.test_report.status.value,
                            "test_run_id": record.test_report.run_id,
                            "test_output_excerpt": record.test_report.output[:2048],
                        },
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                ),
            )

        try:
            report = self._application.review_code(reviewer_agent_id, evidence)
        except BaseException:
            with self._lock:
                record.active = False
            raise
        with self._lock:
            record.active = False
            record.review_report = report
            return self._snapshot(record)

    def activate(
        self,
        owner: str,
        workspace_id: str,
        approval_request_id: str,
    ) -> dict:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            if record.active:
                raise RuntimeError("Experiment already has an active operation")
            if record.activation_result is not None:
                raise RuntimeError("Experiment activation has already been recorded")
            workspace = record.workspace
            if (
                record.test_report is None
                or record.test_report.status is not MaintenanceSandboxStatus.PASSED
                or record.test_report.workspace_id != workspace.workspace_id
                or record.test_report.proposal_id != workspace.proposal_id
            ):
                raise PermissionError("Activation requires passing tests for this exact patch")
            if record.review_report is None or not record.review_report.evidence_sha256:
                raise PermissionError("Activation requires independent review of this exact patch")
            if any(
                finding.severity.value in {"critical", "high"}
                for finding in record.review_report.findings
            ):
                raise PermissionError("Activation is blocked by critical or high review findings")
            record.active = True

        self._activation_lock.acquire()
        try:
            approval = self._application.get_maintenance_approval(approval_request_id)
            if (
                approval.workspace_id != workspace.workspace_id
                or approval.proposal_id != workspace.proposal_id
                or approval.patch_sha256 != workspace.patch_sha256
                or approval.source_sha256 != workspace.source_sha256
                or approval.status is not ApprovalStatus.APPROVED
                or approval.decided_by is None
                or approval.decided_at is None
            ):
                raise PermissionError("Approval does not match this exact tested patch")
            approved_at = approval.decided_at
            reviewed_at = record.review_report.generated_at
            tested_at = record.test_report.finished_at
            now = datetime.now(timezone.utc)
            if (
                approved_at.tzinfo is None
                or approved_at < max(reviewed_at, tested_at)
                or approved_at > now
                or now - approved_at > self.APPROVAL_MAX_AGE
            ):
                raise PermissionError(
                    "Approval is stale; re-review the current test evidence and approve again"
                )

            self._verify_target_source(workspace)
            checkpoint = self._application.create_maintenance_checkpoint(
                workspace.workspace_id,
                created_by=owner,
                source_root=self._activation_root,
                approval_request_id=approval.request_id,
            )
            if (
                checkpoint.approval_request_id != approval.request_id
                or checkpoint.patch_sha256 != workspace.patch_sha256
                or checkpoint.source_sha256 != workspace.source_sha256
            ):
                raise PermissionError("Checkpoint does not match the approved artifact")
            with self._lock:
                record.activation_result = {
                    "status": "checkpointed_pending_activation",
                    "workspace_id": workspace.workspace_id,
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "commit_sha": checkpoint.commit_sha,
                    "parent_sha": checkpoint.parent_sha,
                    "patch_sha256": workspace.patch_sha256,
                    "source_sha256": workspace.source_sha256,
                }
            self._verify_target_source(workspace)
            self._application.activate_maintenance_checkpoint(
                checkpoint.checkpoint_id,
                source_root=self._activation_root,
            )
            result = {
                "status": "activated",
                "activation_mode": "local_git_fast_forward",
                "workspace_id": workspace.workspace_id,
                "proposal_id": workspace.proposal_id,
                "source_sha256": workspace.source_sha256,
                "patch_sha256": workspace.patch_sha256,
                "approval_request_id": approval.request_id,
                "approved_by": approval.decided_by,
                "approved_at": approval.decided_at,
                "checkpoint_id": checkpoint.checkpoint_id,
                "commit_sha": checkpoint.commit_sha,
                "parent_sha": checkpoint.parent_sha,
                "changed_files": workspace.changed_files,
                "impact_report": _impact_report(workspace.changed_files),
                "test_run_id": record.test_report.run_id,
                "test_status": record.test_report.status.value,
                "reviewer_agent_id": record.review_report.agent_id,
                "review_findings": tuple(
                    {
                        "severity": finding.severity.value,
                        "summary": finding.summary,
                    }
                    for finding in record.review_report.findings
                ),
                "review_unknowns": record.review_report.unknowns,
                "runtime_restart": "not_performed",
                "runtime_health": "not_verified",
                "website_deployment": "not_performed",
                "recovery": {
                    "available_only_when_activation_is_clean_HEAD": True,
                    "action": f"POST /api/maintenance/experiments/{workspace.workspace_id}/recover",
                    "external_actions_reversed": False,
                },
            }
            with self._lock:
                record.activation_result = result
                record.active = False
                return result
        except BaseException:
            with self._lock:
                if record.activation_result is not None:
                    record.activation_result = {
                        **record.activation_result,
                        "status": "activation_uncertain",
                        "failure": (
                            "Activation did not return verified. Inspect the local Git checkout "
                            "and checkpoint before attempting recovery."
                        ),
                    }
                record.active = False
            raise
        finally:
            self._activation_lock.release()

    def recover(self, owner: str, workspace_id: str) -> dict:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            if record.active:
                raise RuntimeError("Experiment already has an active operation")
            if record.activation_result is None:
                raise ValueError("Experiment has no recorded activation to recover")
            if record.activation_result.get("recovered"):
                raise RuntimeError("Experiment activation has already been recovered")
            record.active = True
            checkpoint_id = record.activation_result["checkpoint_id"]
        self._activation_lock.acquire()
        try:
            checkpoint = self._application.recover_maintenance_activation(
                checkpoint_id,
                source_root=self._activation_root,
            )
            with self._lock:
                record.activation_result = {
                    **record.activation_result,
                    "recovered": True,
                    "recovery_commit_parent": checkpoint.commit_sha,
                    "recovery_scope": "reverted only the exact local Git activation",
                    "runtime_restart": "not_performed",
                    "website_deployment": "not_performed",
                }
                record.active = False
                return record.activation_result
        except BaseException:
            with self._lock:
                record.active = False
            raise
        finally:
            self._activation_lock.release()

    def _verify_target_source(self, workspace: PatchWorkspace) -> None:
        try:
            contents = {}
            for relative_path in workspace.files:
                path = _source_file(self._activation_root, relative_path)
                with path.open("rb") as stream:
                    content = stream.read(PatchDevelopmentService.MAX_FILE_BYTES + 1)
                if len(content) > PatchDevelopmentService.MAX_FILE_BYTES:
                    raise ValueError("Source file exceeds the limit")
                contents[relative_path] = content
            if _source_digest(contents) != workspace.source_sha256:
                raise ValueError("Source snapshot differs")
        except (OSError, ValueError):
            raise PermissionError(
                "Activation source no longer matches the uploaded snapshot"
            ) from None

    def dispose(self, owner: str, workspace_id: str) -> None:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            if record.active:
                raise RuntimeError("Cannot dispose an active experiment")
            if record.activation_result is not None:
                raise RuntimeError("Activated experiment provenance must be retained until restart")
            del self._records[workspace_id]
        try:
            self._application.dispose_patch_workspace(workspace_id)
        finally:
            record.source_directory.cleanup()

    def close(self) -> None:
        with self._lock:
            records = tuple(self._records.values())
            self._records.clear()
        for record in records:
            try:
                self._application.dispose_patch_workspace(
                    record.workspace.workspace_id
                )
            finally:
                record.source_directory.cleanup()

    def _owned_record(self, owner: str, workspace_id: str) -> _ExperimentRecord:
        if not isinstance(workspace_id, str) or not workspace_id:
            raise LookupError("Maintenance experiment not found")
        record = self._records.get(workspace_id)
        if record is None or record.owner != owner:
            raise LookupError("Maintenance experiment not found")
        return record

    def _snapshot(self, record: _ExperimentRecord) -> dict:
        workspace = record.workspace
        return {
            "workspace_id": workspace.workspace_id,
            "proposal_id": workspace.proposal_id,
            "created_at": record.created_at,
            "allowed_files": workspace.files,
            "changed_files": workspace.changed_files,
            "source_sha256": workspace.source_sha256,
            "patch_sha256": workspace.patch_sha256,
            "unified_diff": workspace.unified_diff,
            "test_report": record.test_report,
            "review_report": record.review_report,
            "activation_result": record.activation_result,
            "execution_policy": self.EXECUTION_POLICY,
            "recovery_limits": self.RECOVERY_LIMITS,
        }


async def bounded_experiment_body(request: Request) -> bytes:
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MaintenanceExperimentService.MAX_REQUEST_BYTES:
            raise HTTPException(413, "Maintenance experiment request exceeds its byte limit")
        payload.extend(chunk)
    return bytes(payload)


def _service(request: Request) -> MaintenanceExperimentService:
    return request.app.state.maintenance_experiment_service


def _impact_report(changed_files: tuple[str, ...]) -> dict:
    dependency_names = {
        "pyproject.toml", "poetry.lock", "uv.lock", "package.json",
        "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    }
    dependencies = tuple(
        path for path in changed_files
        if Path(path).name in dependency_names or Path(path).name.startswith("requirements")
    )
    configuration = tuple(
        path for path in changed_files
        if Path(path).suffix.lower() in {".toml", ".ini", ".yaml", ".yml", ".json"}
        or Path(path).name.startswith(".env")
    )
    data = tuple(
        path for path in changed_files
        if "migration" in path.lower()
        or Path(path).suffix.lower() in {".db", ".sqlite", ".sqlite3"}
        or path.lower().startswith(("data/", "database/"))
    )
    classified = set(dependencies) | set(configuration) | set(data)
    return {
        "changed_files": changed_files,
        "source_or_other_files": tuple(
            path for path in changed_files if path not in classified
        ),
        "dependency_manifests": dependencies,
        "configuration_files": configuration,
        "data_or_migration_files": data,
        "dependency_installation": "not_performed",
        "data_migration": "not_performed",
    }


def _parse(model, payload: bytes):
    try:
        return model.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Maintenance experiment request is invalid") from None


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, LookupError):
        raise HTTPException(404, "Maintenance experiment not found") from None
    if isinstance(error, PermissionError):
        raise HTTPException(403, str(error)) from None
    if isinstance(error, RuntimeError):
        raise HTTPException(409, str(error)) from None
    if isinstance(error, ValueError):
        raise HTTPException(422, str(error)) from None
    if isinstance(error, (CodeReviewProviderError, CodeReviewResponseError)):
        raise HTTPException(502, "Independent code review could not be verified") from None
    raise error


@router.post("", status_code=201, dependencies=[Depends(require_experiment)])
def create_experiment(
    payload=Depends(bounded_experiment_body),
    principal: AuthenticatedPrincipal = Depends(require_experiment),
    service: MaintenanceExperimentService = Depends(_service),
):
    body = _parse(ExperimentCreateRequest, payload)
    try:
        return service.create(principal.identity, body)
    except (LookupError, PermissionError, RuntimeError, ValueError) as error:
        _raise_service_error(error)


@router.get("/{workspace_id}", dependencies=[Depends(require_experiment)])
def get_experiment(
    workspace_id: ExperimentIdentifier,
    principal: AuthenticatedPrincipal = Depends(require_experiment),
    service: MaintenanceExperimentService = Depends(_service),
):
    try:
        return service.get(principal.identity, workspace_id)
    except (LookupError, PermissionError, RuntimeError, ValueError) as error:
        _raise_service_error(error)


@router.post(
    "/{workspace_id}/tests",
    dependencies=[Depends(require_experiment)],
)
def run_experiment_tests(
    workspace_id: ExperimentIdentifier,
    body: ExperimentTestRequest,
    principal: AuthenticatedPrincipal = Depends(require_experiment),
    service: MaintenanceExperimentService = Depends(_service),
):
    try:
        return service.run_tests(
            principal.identity,
            workspace_id,
            body.selected_tests,
            body.timeout_seconds,
        )
    except (LookupError, PermissionError, RuntimeError, ValueError) as error:
        _raise_service_error(error)


@router.post(
    "/{workspace_id}/review",
    dependencies=[Depends(require_experiment)],
)
def review_experiment(
    workspace_id: ExperimentIdentifier,
    body: ExperimentReviewRequest,
    principal: AuthenticatedPrincipal = Depends(require_experiment),
    service: MaintenanceExperimentService = Depends(_service),
):
    try:
        return service.review(
            principal.identity,
            workspace_id,
            body.reviewer_agent_id,
            cloud_consent=body.cloud_consent,
        )
    except (
        CodeReviewProviderError,
        CodeReviewResponseError,
        LookupError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        _raise_service_error(error)


@router.post(
    "/{workspace_id}/activate",
    status_code=201,
    dependencies=[Depends(require_activation)],
)
def activate_experiment(
    workspace_id: ExperimentIdentifier,
    body: ExperimentActivationRequest,
    principal: AuthenticatedPrincipal = Depends(require_activation),
    service: MaintenanceExperimentService = Depends(_service),
):
    try:
        return service.activate(
            principal.identity,
            workspace_id,
            body.approval_request_id,
        )
    except (LookupError, PermissionError, RuntimeError, ValueError) as error:
        _raise_service_error(error)


@router.post(
    "/{workspace_id}/recover",
    dependencies=[Depends(require_activation)],
)
def recover_experiment_activation(
    workspace_id: ExperimentIdentifier,
    principal: AuthenticatedPrincipal = Depends(require_activation),
    service: MaintenanceExperimentService = Depends(_service),
):
    try:
        return service.recover(principal.identity, workspace_id)
    except (LookupError, PermissionError, RuntimeError, ValueError) as error:
        _raise_service_error(error)


@router.delete(
    "/{workspace_id}",
    status_code=204,
    dependencies=[Depends(require_experiment)],
)
def dispose_experiment(
    workspace_id: ExperimentIdentifier,
    principal: AuthenticatedPrincipal = Depends(require_experiment),
    service: MaintenanceExperimentService = Depends(_service),
) -> Response:
    try:
        service.dispose(principal.identity, workspace_id)
    except (LookupError, PermissionError, RuntimeError, ValueError) as error:
        _raise_service_error(error)
    return Response(status_code=204)
