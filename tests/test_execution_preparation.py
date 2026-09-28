from dataclasses import replace
from datetime import datetime, timezone
import subprocess
from unittest.mock import patch

import pytest

from app.integrations import (
    DockerSandboxBackend,
    ExecutionPreparationRegistry,
    ExecutionPreparationRequest,
    ExecutionPreparationStatus,
    GitHubSourceStager,
    IntegrationProposal,
    IntegrationRegistry,
    IntegrationSandboxRegistry,
    IntegrationSource,
    IntegrationStatus,
    SandboxCredentialMode,
    SandboxIsolationPolicy,
    SandboxSourceBindingRegistry,
    SandboxExecutor,
    SandboxStatus,
    SourceStagingResult,
    SourceStagingStatus,
    calculate_staged_source_digest,
)

STAGING_ID = "staging-11111111111111111111111111111111"


def setup_preparation(tmp_path, *, policy=None):
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace_root = tmp_path / "controlled-workspaces"
    workspace_root.mkdir()
    workspace = workspace_root / f"erselmetz-source-{STAGING_ID}-fixture"
    workspace.mkdir()
    (workspace / "README.txt").write_text("untrusted source data", encoding="utf-8")

    stager = GitHubSourceStager(
        workspace_parent=workspace_root,
        project_root=project_root,
    )
    proposal = IntegrationProposal(
        id="proposal-36",
        source=IntegrationSource(
            "github_repository", "https://github.com/example/repository"
        ),
        requested_purpose="Prepare an isolated future experiment",
        source_discovery_id="discovery-36",
    )
    for status in (
        IntegrationStatus.ANALYZING,
        IntegrationStatus.EVALUATING,
        IntegrationStatus.PROPOSED,
    ):
        proposal.transition(status)

    proposals = IntegrationRegistry()
    proposals.register(proposal)
    sandboxes = IntegrationSandboxRegistry()
    sandbox = sandboxes.create(
        "sandbox-36",
        proposal,
        isolation_policy=policy,
    )
    bindings = SandboxSourceBindingRegistry(
        sandboxes,
        source_stager=stager,
    )
    digest, file_count, total_bytes = calculate_staged_source_digest(workspace)
    staging = SourceStagingResult(
        staging_id=STAGING_ID,
        source_discovery_id="discovery-36",
        workspace_reference=str(workspace),
        status=SourceStagingStatus.STAGED,
        sha256=digest,
        archive_sha256="b" * 64,
        file_count=file_count,
        total_bytes=total_bytes,
        complete=True,
        staged_at=datetime.now(timezone.utc),
        sandbox_id=sandbox.id,
    )
    binding = bindings.bind(proposal, sandbox, staging)
    preparations = ExecutionPreparationRegistry(
        proposals=proposals,
        sandboxes=sandboxes,
        bindings=bindings,
        source_stager=stager,
    )
    request = ExecutionPreparationRequest(
        proposal_id=proposal.id,
        sandbox_id=sandbox.id,
        staging_result=staging,
        binding_id=binding.binding_id,
    )
    return (
        preparations,
        request,
        proposal,
        sandbox,
        staging,
        binding,
        workspace,
        project_root,
        proposals,
        sandboxes,
        bindings,
        stager,
    )


def test_successful_execution_preparation_is_complete_and_immutable(tmp_path):
    preparations, request, proposal, sandbox, staging, binding, workspace, *_ = (
        setup_preparation(tmp_path)
    )

    record = preparations.prepare(request)

    assert record.status is ExecutionPreparationStatus.READY
    assert record.proposal_id == proposal.id
    assert record.sandbox_id == sandbox.id
    assert record.source_discovery_id == staging.source_discovery_id
    assert record.staging_id == staging.staging_id
    assert record.source_binding_id == binding.binding_id
    assert record.workspace_reference == str(workspace.resolve())
    assert record.source_sha256 == staging.sha256
    assert record.archive_sha256 == staging.archive_sha256
    assert record.file_count == staging.file_count
    assert record.total_bytes == staging.total_bytes
    assert record.isolation_policy == sandbox.isolation_policy
    assert record.prepared_at.tzinfo is not None
    assert preparations.get(record.preparation_id) is record
    with pytest.raises(AttributeError):
        record.sandbox_id = "changed"


def test_repeated_preparation_is_deterministic_for_unchanged_source(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)

    first = preparations.prepare(request)
    second = preparations.prepare(request)

    assert second is first
    assert second.preparation_id == first.preparation_id
    assert second.source_sha256 == first.source_sha256
    assert preparations.verify_workspace(first.preparation_id)


def test_missing_proposal_returns_invalid_preparation(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)
    missing = replace(request, proposal_id="missing-proposal")

    result = preparations.prepare(missing)

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("proposal is not registered" in note for note in result.validation_notes)


def test_missing_sandbox_returns_invalid_preparation(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)

    result = preparations.prepare(replace(request, sandbox_id="missing-sandbox"))

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("Sandbox is not registered" in note for note in result.validation_notes)


def test_sandbox_must_not_be_destroyed_or_running(tmp_path):
    preparations, request, _proposal, sandbox, *_ = setup_preparation(tmp_path)
    sandbox._status = SandboxStatus.DESTROYED

    result = preparations.prepare(request)

    assert result.status is ExecutionPreparationStatus.BLOCKED
    assert any("lifecycle state" in note for note in result.validation_notes)


def test_sandbox_must_belong_to_proposal(tmp_path):
    preparations, request, _proposal, sandbox, *_ = setup_preparation(tmp_path)
    sandbox.proposal_id = "another-proposal"

    result = preparations.prepare(request)

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("linkage" in note for note in result.validation_notes)


def test_staging_discovery_linkage_is_validated(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)
    changed = replace(
        request.staging_result,
        source_discovery_id="other-discovery",
    )

    result = preparations.prepare(replace(request, staging_result=changed))

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("discovery" in note for note in result.validation_notes)


def test_staging_binding_linkage_is_validated(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)

    result = preparations.prepare(replace(request, binding_id="missing-binding"))

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("binding is not registered" in note for note in result.validation_notes)


def test_invalid_registered_binding_is_rejected(tmp_path):
    setup = setup_preparation(tmp_path)
    preparations, request, binding, bindings = (
        setup[0],
        setup[1],
        setup[5],
        setup[10],
    )
    bindings._bindings[binding.binding_id] = replace(
        binding,
        source_discovery_id="different-discovery",
    )

    result = preparations.prepare(request)

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("binding does not match" in note for note in result.validation_notes)


@pytest.mark.parametrize(
    ("status", "complete"),
    [
        (SourceStagingStatus.BLOCKED, False),
        (SourceStagingStatus.INCOMPLETE, False),
    ],
)
def test_failed_or_incomplete_staging_is_blocked(tmp_path, status, complete):
    preparations, request, *_ = setup_preparation(tmp_path)
    invalid_staging = replace(
        request.staging_result,
        status=status,
        complete=complete,
    )

    result = preparations.prepare(
        replace(request, staging_result=invalid_staging)
    )

    assert result.status is ExecutionPreparationStatus.BLOCKED


def test_missing_staging_returns_invalid_preparation(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)

    result = preparations.prepare(replace(request, staging_result=None))

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("staging result is missing" in note for note in result.validation_notes)


def test_missing_workspace_is_blocked(tmp_path):
    setup = setup_preparation(tmp_path)
    preparations, request, workspace = setup[0], setup[1], setup[6]
    import shutil

    shutil.rmtree(workspace)

    result = preparations.prepare(request)

    assert result.status is ExecutionPreparationStatus.BLOCKED
    assert any("does not exist" in note for note in result.validation_notes)


def test_workspace_outside_staging_root_is_blocked(tmp_path):
    (
        preparations,
        request,
        proposal,
        sandbox,
        staging,
        binding,
        workspace,
        project_root,
        proposals,
        sandboxes,
        bindings,
        _stager,
    ) = setup_preparation(tmp_path)
    other_stager = GitHubSourceStager(
        workspace_parent=tmp_path / "other-root",
        project_root=project_root,
    )
    (tmp_path / "other-root").mkdir()
    outside_preparer = ExecutionPreparationRegistry(
        proposals=proposals,
        sandboxes=sandboxes,
        bindings=bindings,
        source_stager=other_stager,
    )

    result = outside_preparer.prepare(request)

    assert result.status is ExecutionPreparationStatus.BLOCKED
    assert any("outside" in note for note in result.validation_notes)


def test_project_directory_workspace_is_rejected(tmp_path):
    (
        preparations,
        request,
        proposal,
        sandbox,
        staging,
        binding,
        workspace,
        project_root,
        proposals,
        sandboxes,
        bindings,
        stager,
    ) = setup_preparation(tmp_path)
    project_preparer = ExecutionPreparationRegistry(
        proposals=proposals,
        sandboxes=sandboxes,
        bindings=bindings,
        source_stager=stager,
        project_root=workspace,
    )

    result = project_preparer.prepare(request)

    assert result.status is ExecutionPreparationStatus.BLOCKED
    assert any("project repository" in note for note in result.validation_notes)


def test_source_integrity_mismatch_after_preparation_is_detectable(tmp_path):
    setup = setup_preparation(tmp_path)
    preparations, request, workspace = setup[0], setup[1], setup[6]
    record = preparations.prepare(request)
    (workspace / "README.txt").write_text("changed bytes", encoding="utf-8")

    assert not preparations.verify_workspace(record.preparation_id)
    changed = preparations.prepare(request)
    assert changed.status is ExecutionPreparationStatus.BLOCKED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("file_count", 99),
        ("total_bytes", 9999),
    ],
)
def test_file_count_and_byte_size_mismatch_block_preparation(tmp_path, field, value):
    preparations, request, *_ = setup_preparation(tmp_path)
    modified_staging = replace(request.staging_result, **{field: value})

    result = preparations.prepare(
        replace(request, staging_result=modified_staging)
    )

    assert result.status is ExecutionPreparationStatus.INVALID
    assert any("binding does not match" in note for note in result.validation_notes)


def test_credential_policy_is_rejected(tmp_path):
    scoped = SandboxIsolationPolicy(
        credential_mode=SandboxCredentialMode.SCOPED,
    )
    preparations, request, *_ = setup_preparation(tmp_path, policy=scoped)

    result = preparations.prepare(request)

    assert result.status is ExecutionPreparationStatus.BLOCKED
    assert any("credentials/environment" in note for note in result.validation_notes)


@pytest.mark.parametrize(
    "prohibited_field",
    ["command", "host_environment", "credential_references"],
)
def test_request_cannot_accept_commands_or_host_environment(prohibited_field):
    with pytest.raises(TypeError):
        ExecutionPreparationRequest(
            proposal_id="proposal",
            sandbox_id="sandbox",
            staging_result=None,
            binding_id=None,
            **{prohibited_field: "must-not-be-accepted"},
        )


def test_preparation_does_not_execute_source_or_invoke_docker(tmp_path):
    preparations, request, *_ = setup_preparation(tmp_path)

    with (
        patch.object(
            subprocess,
            "Popen",
            side_effect=AssertionError("host subprocess invoked"),
        ),
        patch.object(
            DockerSandboxBackend,
            "execute",
            side_effect=AssertionError("Docker invoked"),
        ),
        patch.object(
            SandboxExecutor,
            "execute",
            side_effect=AssertionError("Sandbox executor invoked"),
        ),
    ):
        result = preparations.prepare(request)

    assert result.status is ExecutionPreparationStatus.READY


def test_preparation_does_not_change_proposal_or_sandbox_lifecycle(tmp_path):
    preparations, request, proposal, sandbox, *_ = setup_preparation(tmp_path)
    proposal_status = proposal.status
    sandbox_status = sandbox.status

    preparations.prepare(request)

    assert proposal.status is proposal_status is IntegrationStatus.PROPOSED
    assert sandbox.status is sandbox_status is SandboxStatus.CONFIGURED
