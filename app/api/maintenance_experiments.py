"""Owner-scoped, bounded patch experiments in disposable workspaces."""

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
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
from app.application.services.patch_development import (
    PatchDevelopmentService,
    PatchWorkspace,
    _validate_relative_path,
)
from app.integrations import SandboxImagePolicy
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/maintenance/experiments")
require_experiment = require_permission("maintenance:experiment")
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


@dataclass(slots=True)
class _ExperimentRecord:
    owner: str
    workspace: PatchWorkspace
    source_directory: tempfile.TemporaryDirectory
    created_at: datetime
    test_report: MaintenanceSandboxReport | None = None
    review_report: CodeReviewReport | None = None
    active: bool = False


class MaintenanceExperimentService:
    """Bind workspace ownership and preserve its source snapshot until disposal."""

    MAX_EXPERIMENTS = PatchDevelopmentService.MAX_WORKSPACES
    MAX_REQUEST_BYTES = 24 * 1024 * 1024
    MAX_REVIEW_PATCH_BYTES = CodeReviewService.MAX_EVIDENCE_BYTES - 8 * 1024
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
    ):
        if not isinstance(image_policy, SandboxImagePolicy):
            raise TypeError("image_policy must be a SandboxImagePolicy")
        self._application = application_service
        self._image_policy = image_policy
        self._records: dict[str, _ExperimentRecord] = {}
        self._lock = RLock()

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

    def dispose(self, owner: str, workspace_id: str) -> None:
        with self._lock:
            record = self._owned_record(owner, workspace_id)
            if record.active:
                raise RuntimeError("Cannot dispose an active experiment")
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
