from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from app.integrations import (
    DockerSandboxBackend,
    GitHubSourceStager,
    IntegrationProposal,
    IntegrationSandbox,
    IntegrationSandboxRegistry,
    IntegrationSource,
    IntegrationStatus,
    SandboxSourceBindingError,
    SandboxSourceBindingRegistry,
    SandboxSourceBindingStatus,
    SourceStagingResult,
    SourceStagingStatus,
    calculate_staged_source_digest,
)

STAGING_ID = "staging-0123456789abcdef0123456789abcdef"


def make_proposal(proposal_id="proposal-35", discovery_id="discovery-35"):
    proposal = IntegrationProposal(
        id=proposal_id,
        source=IntegrationSource(
            "github_repository", "https://github.com/example/project"
        ),
        requested_purpose="Inspect source in a future sandbox experiment",
        source_discovery_id=discovery_id,
    )
    proposal.transition(IntegrationStatus.ANALYZING)
    proposal.transition(IntegrationStatus.EVALUATING)
    proposal.transition(IntegrationStatus.PROPOSED)
    return proposal


def setup_binding(tmp_path, *, content=b"untrusted source"):
    project = tmp_path / "project"
    project.mkdir()
    workspace_root = tmp_path / "controlled-staging"
    workspace_root.mkdir()
    proposal = make_proposal()
    sandbox_registry = IntegrationSandboxRegistry()
    sandbox = sandbox_registry.create("sandbox-35", proposal)
    workspace = workspace_root / f"erselmetz-source-{STAGING_ID}-abc123"
    workspace.mkdir()
    (workspace / "README.md").write_bytes(content)
    digest, file_count, total_bytes = calculate_staged_source_digest(workspace)
    staging = SourceStagingResult(
        staging_id=STAGING_ID,
        source_discovery_id="discovery-35",
        workspace_reference=str(workspace),
        status=SourceStagingStatus.STAGED,
        sha256=digest,
        archive_sha256="a" * 64,
        file_count=file_count,
        total_bytes=total_bytes,
        complete=True,
        staged_at=datetime.now(timezone.utc),
        sandbox_id=sandbox.id,
    )
    registry = SandboxSourceBindingRegistry(
        sandbox_registry,
        source_stager=GitHubSourceStager(
            workspace_parent=workspace_root,
            project_root=project,
        ),
    )
    return registry, proposal, sandbox, staging, workspace, project, sandbox_registry


def test_successful_binding_preserves_linkage_and_integrity_metadata(tmp_path):
    registry, proposal, sandbox, staging, workspace, _, _ = setup_binding(tmp_path)

    binding = registry.bind(proposal, sandbox, staging)

    assert binding.status is SandboxSourceBindingStatus.BOUND
    assert binding.sandbox_id == sandbox.id
    assert binding.proposal_id == proposal.id
    assert binding.source_discovery_id == staging.source_discovery_id
    assert binding.staging_id == staging.staging_id
    assert binding.workspace_reference == str(workspace.resolve())
    assert binding.sha256 == staging.sha256
    assert binding.archive_sha256 == staging.archive_sha256
    assert binding.file_count == staging.file_count
    assert binding.total_bytes == staging.total_bytes
    assert registry.get(binding.binding_id) is binding


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_discovery_id", "different-discovery"),
        ("sandbox_id", "different-sandbox"),
    ],
)
def test_staging_linkage_mismatch_is_rejected(tmp_path, field, value):
    registry, proposal, sandbox, staging, *_ = setup_binding(tmp_path)

    with pytest.raises(SandboxSourceBindingError):
        registry.bind(proposal, sandbox, replace(staging, **{field: value}))


def test_proposal_and_sandbox_linkage_mismatch_is_rejected(tmp_path):
    registry, _proposal, sandbox, staging, *_ = setup_binding(tmp_path)
    other_proposal = make_proposal("another-proposal")

    with pytest.raises(SandboxSourceBindingError, match="linkage"):
        registry.bind(other_proposal, sandbox, staging)


def test_unregistered_sandbox_is_rejected(tmp_path):
    registry, proposal, _sandbox, staging, *_ = setup_binding(tmp_path)
    unregistered = IntegrationSandbox(
        id="unregistered-sandbox",
        proposal_id=proposal.id,
        source_discovery_id="discovery-35",
    )

    with pytest.raises(SandboxSourceBindingError, match="registered"):
        registry.bind(proposal, unregistered, staging)


@pytest.mark.parametrize(
    ("status", "complete"),
    [
        (SourceStagingStatus.BLOCKED, False),
        (SourceStagingStatus.INCOMPLETE, False),
    ],
)
def test_blocked_or_incomplete_staging_is_rejected(tmp_path, status, complete):
    registry, proposal, sandbox, staging, *_ = setup_binding(tmp_path)

    with pytest.raises(SandboxSourceBindingError, match="successfully completed"):
        registry.bind(
            proposal,
            sandbox,
            replace(staging, status=status, complete=complete),
        )


def test_missing_staging_result_is_rejected(tmp_path):
    registry, proposal, sandbox, *_ = setup_binding(tmp_path)

    with pytest.raises(SandboxSourceBindingError, match="SourceStagingResult"):
        registry.bind(proposal, sandbox, None)


@pytest.mark.parametrize("reference", ["", "not-an-absolute-path"])
def test_invalid_or_missing_workspace_is_rejected(tmp_path, reference):
    registry, proposal, sandbox, staging, *_ = setup_binding(tmp_path)

    with pytest.raises(SandboxSourceBindingError):
        registry.bind(proposal, sandbox, replace(staging, workspace_reference=reference))


def test_nonexistent_workspace_is_rejected(tmp_path):
    registry, proposal, sandbox, staging, *_ = setup_binding(tmp_path)
    missing = tmp_path / "controlled-staging" / (
        f"erselmetz-source-{STAGING_ID}-missing"
    )

    with pytest.raises(SandboxSourceBindingError, match="does not exist"):
        registry.bind(proposal, sandbox, replace(staging, workspace_reference=str(missing)))


def test_workspace_outside_controlled_staging_area_is_rejected(tmp_path):
    registry, proposal, sandbox, staging, *_ = setup_binding(tmp_path)
    outside = tmp_path / f"erselmetz-source-{STAGING_ID}-outside"
    outside.mkdir()

    with pytest.raises(SandboxSourceBindingError, match="outside"):
        registry.bind(proposal, sandbox, replace(staging, workspace_reference=str(outside)))


def test_project_directory_cannot_be_used_as_staging_root_or_workspace(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    proposal = make_proposal()
    sandbox_registry = IntegrationSandboxRegistry()
    sandbox = sandbox_registry.create("sandbox-35", proposal)

    with pytest.raises(SandboxSourceBindingError, match="separate"):
        SandboxSourceBindingRegistry(
            sandbox_registry,
            source_stager=GitHubSourceStager(
                workspace_parent=project,
                project_root=project,
            ),
        )


def test_workspace_modification_fails_integrity_check(tmp_path):
    registry, proposal, sandbox, staging, workspace, *_ = setup_binding(tmp_path)
    (workspace / "README.md").write_bytes(b"modified after staging")

    with pytest.raises(SandboxSourceBindingError, match="no longer matches"):
        registry.bind(proposal, sandbox, staging)


def test_workspace_symlink_is_rejected(tmp_path):
    registry, proposal, sandbox, staging, workspace, *_ = setup_binding(tmp_path)
    link = workspace / "escape"
    target = tmp_path / "outside-file"
    target.write_text("external", encoding="utf-8")
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable in this environment.")

    with pytest.raises(SandboxSourceBindingError, match="symbolic link"):
        registry.bind(proposal, sandbox, staging)


def test_binding_does_not_change_proposal_or_sandbox_lifecycle(tmp_path):
    registry, proposal, sandbox, staging, *_ = setup_binding(tmp_path)
    proposal_status = proposal.status
    sandbox_status = sandbox.status

    registry.bind(proposal, sandbox, staging)

    assert proposal.status is proposal_status is IntegrationStatus.PROPOSED
    assert sandbox.status is sandbox_status


def test_binding_does_not_execute_source_or_invoke_docker(tmp_path, monkeypatch):
    registry, proposal, sandbox, staging, workspace, *_ = setup_binding(tmp_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Execution must not occur while binding source.")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(DockerSandboxBackend, "execute", forbidden)
    registry.bind(proposal, sandbox, staging)

    assert (workspace / "README.md").read_bytes() == b"untrusted source"
