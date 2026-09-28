import os
import socket
import subprocess
from unittest.mock import patch

import pytest

from app.integrations import (
    IntegrationProposal,
    IntegrationSandbox,
    IntegrationSandboxRegistry,
    IntegrationSource,
    IntegrationStatus,
    SandboxCredentialMode,
    SandboxEnvironmentMode,
    SandboxExecutionNotImplementedError,
    SandboxFilesystemMode,
    SandboxIsolationPolicy,
    SandboxNetworkMode,
    SandboxProcessMode,
    SandboxResourceLimits,
    SandboxStatus,
)


def make_proposal(
    *,
    proposal_id: str = "proposal-31",
    discovery_id: str | None = "discovery-31",
    status: IntegrationStatus = IntegrationStatus.PROPOSED,
) -> IntegrationProposal:
    proposal = IntegrationProposal(
        id=proposal_id,
        source=IntegrationSource(
            "github_repository",
            "https://github.com/example/project",
            "project",
        ),
        requested_purpose="Potentially use repository tooling",
        source_discovery_id=discovery_id,
    )
    for state in (
        IntegrationStatus.ANALYZING,
        IntegrationStatus.EVALUATING,
        IntegrationStatus.PROPOSED,
    ):
        proposal.transition(state)
        if state == status:
            break
    return proposal


def test_sandbox_model_creation_and_proposal_discovery_linkage():
    sandbox = IntegrationSandbox(
        id="sandbox-31",
        proposal_id="proposal-31",
        source_discovery_id="discovery-31",
    )

    assert sandbox.id == "sandbox-31"
    assert sandbox.proposal_id == "proposal-31"
    assert sandbox.source_discovery_id == "discovery-31"
    assert sandbox.status == SandboxStatus.CONFIGURED
    assert sandbox.created_at.tzinfo is not None
    assert sandbox.isolation_enforced is False


def test_sandbox_requires_nonempty_identity_links():
    for field_name in ("id", "proposal_id", "source_discovery_id"):
        values = {
            "id": "sandbox",
            "proposal_id": "proposal",
            "source_discovery_id": "discovery",
        }
        values[field_name] = " "
        with pytest.raises(ValueError, match=field_name):
            IntegrationSandbox(**values)


def test_default_isolation_policy_is_restrictive_metadata():
    policy = SandboxIsolationPolicy()

    assert policy.filesystem_mode == SandboxFilesystemMode.READ_ONLY
    assert policy.network_mode == SandboxNetworkMode.DISABLED
    assert policy.process_mode == SandboxProcessMode.DISABLED
    assert policy.environment_mode == SandboxEnvironmentMode.MINIMAL
    assert policy.credential_mode == SandboxCredentialMode.NONE
    assert policy.resource_limits == SandboxResourceLimits(
        max_memory_mb=512,
        max_cpu_seconds=60,
        max_processes=1,
        max_disk_mb=256,
    )


def test_policy_validates_types_and_positive_resource_limits():
    with pytest.raises(TypeError, match="network_mode"):
        SandboxIsolationPolicy(network_mode="disabled")
    with pytest.raises(ValueError, match="positive integer"):
        SandboxResourceLimits(max_memory_mb=0)
    with pytest.raises(ValueError, match="positive integer"):
        SandboxResourceLimits(max_processes=True)


def test_sandbox_validates_policy_and_notes():
    with pytest.raises(TypeError, match="SandboxIsolationPolicy"):
        IntegrationSandbox("sandbox", "proposal", "discovery", isolation_policy=None)
    with pytest.raises(ValueError, match="notes"):
        IntegrationSandbox("sandbox", "proposal", "discovery", notes=(" ",))


def test_configured_to_ready_is_an_explicit_valid_transition():
    sandbox = IntegrationSandbox("sandbox", "proposal", "discovery")

    sandbox.transition(SandboxStatus.READY)

    assert sandbox.status == SandboxStatus.READY
    assert sandbox.isolation_enforced is False


def test_invalid_lifecycle_transitions_are_rejected():
    sandbox = IntegrationSandbox("sandbox", "proposal", "discovery")

    with pytest.raises(ValueError, match="Invalid sandbox transition"):
        sandbox.transition(SandboxStatus.COMPLETED)
    with pytest.raises(TypeError, match="SandboxStatus"):
        sandbox.transition("ready")


def test_running_transition_is_unavailable_without_an_executor():
    sandbox = IntegrationSandbox("sandbox", "proposal", "discovery")
    sandbox.transition(SandboxStatus.READY)

    with pytest.raises(SandboxExecutionNotImplementedError, match="not implemented"):
        sandbox.transition(SandboxStatus.RUNNING)
    assert sandbox.status == SandboxStatus.READY


def test_registry_creates_configured_sandbox_without_mutating_proposal():
    proposal = make_proposal()
    original_status = proposal.status
    registry = IntegrationSandboxRegistry()

    sandbox = registry.create("sandbox-31", proposal)

    assert sandbox.proposal_id == proposal.id
    assert sandbox.source_discovery_id == proposal.source_discovery_id
    assert sandbox.status == SandboxStatus.CONFIGURED
    assert proposal.status == original_status == IntegrationStatus.PROPOSED


def test_registry_retrieves_lists_and_transitions_explicitly():
    proposal = make_proposal()
    registry = IntegrationSandboxRegistry()
    sandbox = registry.create("sandbox-31", proposal)

    assert registry.get(sandbox.id) is sandbox
    assert registry.list() == [sandbox]

    registry.transition(sandbox.id, SandboxStatus.READY)
    assert registry.get(sandbox.id).status == SandboxStatus.READY


def test_registry_destroy_is_a_state_transition_and_retains_record():
    registry = IntegrationSandboxRegistry()
    sandbox = registry.create("sandbox-31", make_proposal())

    registry.destroy(sandbox.id)

    assert sandbox.status == SandboxStatus.DESTROYED
    assert registry.get(sandbox.id) is sandbox
    assert registry.list() == [sandbox]
    with pytest.raises(ValueError, match="Invalid sandbox transition"):
        registry.destroy(sandbox.id)


def test_unknown_sandbox_and_duplicate_ids_are_explicit_errors():
    registry = IntegrationSandboxRegistry()
    with pytest.raises(ValueError, match="Sandbox not found"):
        registry.get("missing")

    proposal = make_proposal()
    registry.create("sandbox-31", proposal)
    with pytest.raises(ValueError, match="already registered"):
        registry.create("sandbox-31", proposal)


def test_only_proposed_discovery_linked_proposals_can_create_sandboxes():
    registry = IntegrationSandboxRegistry()
    with pytest.raises(ValueError, match="PROPOSED"):
        registry.create(
            "early-sandbox",
            make_proposal(status=IntegrationStatus.EVALUATING),
        )
    with pytest.raises(ValueError, match="source discovery"):
        registry.create(
            "unlinked-sandbox",
            make_proposal(discovery_id=None),
        )


def test_custom_isolation_policy_is_retained_as_configuration_only():
    policy = SandboxIsolationPolicy(
        filesystem_mode=SandboxFilesystemMode.ISOLATED_WRITABLE,
        network_mode=SandboxNetworkMode.RESTRICTED,
        process_mode=SandboxProcessMode.ISOLATED,
        environment_mode=SandboxEnvironmentMode.CLEAN,
        credential_mode=SandboxCredentialMode.SCOPED,
        resource_limits=SandboxResourceLimits(max_memory_mb=256),
    )
    sandbox = IntegrationSandbox(
        "sandbox", "proposal", "discovery", isolation_policy=policy
    )

    assert sandbox.isolation_policy is policy
    assert sandbox.isolation_enforced is False


def test_sandbox_foundation_invokes_no_process_or_network_operations():
    proposal = make_proposal()
    registry = IntegrationSandboxRegistry()
    with (
        patch.object(subprocess, "run", side_effect=AssertionError("process invoked")),
        patch.object(subprocess, "Popen", side_effect=AssertionError("process invoked")),
        patch.object(os, "system", side_effect=AssertionError("shell invoked")),
        patch.object(os, "popen", side_effect=AssertionError("process invoked")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("network invoked")
        ),
    ):
        sandbox = registry.create("sandbox-31", proposal)
        registry.transition(sandbox.id, SandboxStatus.READY)
        registry.destroy(sandbox.id)

    assert sandbox.status == SandboxStatus.DESTROYED


def test_sandbox_creation_is_deterministic_for_explicit_identity_and_policy():
    policy = SandboxIsolationPolicy()
    registry = IntegrationSandboxRegistry()

    first = registry.create(
        "stable-sandbox", make_proposal(), isolation_policy=policy
    )
    second = IntegrationSandbox(
        "stable-sandbox",
        "proposal-31",
        "discovery-31",
        isolation_policy=policy,
        created_at=first.created_at,
    )

    assert first.id == second.id
    assert first.proposal_id == second.proposal_id
    assert first.source_discovery_id == second.source_discovery_id
    assert first.isolation_policy == second.isolation_policy
    assert first.status == second.status == SandboxStatus.CONFIGURED
