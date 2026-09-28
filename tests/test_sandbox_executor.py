import os
import socket
import subprocess
from unittest.mock import patch

import pytest

from app.integrations import (
    IntegrationProposal,
    IntegrationSandbox,
    IntegrationSource,
    IntegrationStatus,
    SandboxBackend,
    SandboxBackendSession,
    SandboxEnvironmentMode,
    SandboxExecutionNotAvailableError,
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxExecutionStatus,
    SandboxExecutor,
    SandboxStatus,
    UnavailableSandboxExecutor,
    UnavailableSandboxBackend,
)


def make_sandbox() -> IntegrationSandbox:
    sandbox = IntegrationSandbox(
        id="sandbox-32",
        proposal_id="proposal-32",
        source_discovery_id="discovery-32",
    )
    sandbox.transition(SandboxStatus.READY)
    return sandbox


def make_request(**overrides) -> SandboxExecutionRequest:
    values = {
        "sandbox_id": "sandbox-32",
        "proposal_id": "proposal-32",
        "entrypoint": "src/main.py",
        "arguments": ("--help",),
    }
    values.update(overrides)
    return SandboxExecutionRequest(**values)


class ClaimedIsolatedBackend(SandboxBackend):
    @property
    def backend_id(self) -> str:
        return "claimed-isolated"

    @property
    def available(self) -> bool:
        return True

    @property
    def enforces_isolation(self) -> bool:
        return True

    def prepare(
        self,
        sandbox: IntegrationSandbox,
        request: SandboxExecutionRequest,
    ) -> SandboxBackendSession:
        del sandbox, request
        raise AssertionError("Task 32 must not invoke backend preparation")

    def execute(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> None:
        del session, request
        raise AssertionError("Task 32 must not invoke a backend")

    def collect_result(
        self,
        session: SandboxBackendSession,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        del session, request
        raise AssertionError("Task 32 must not collect a fabricated result")

    def cleanup(self, session: SandboxBackendSession) -> None:
        del session
        raise AssertionError("Task 32 must not invoke backend cleanup")


def test_executor_interface_and_concrete_implementation():
    executor = UnavailableSandboxExecutor()

    assert isinstance(executor, SandboxExecutor)


def test_execution_request_validates_fields_and_relative_entrypoint():
    request = make_request()

    assert request.entrypoint == "src/main.py"
    assert request.arguments == ("--help",)
    assert request.timeout_seconds == 60

    for entrypoint in (
        "",
        "../outside.py",
        "src/../../outside.py",
        "/tmp/script.py",
        "C:\\Users\\person\\script.py",
        "C:script.py",
        "src\\script.py",
        "src//script.py",
        "src/./script.py",
    ):
        with pytest.raises(ValueError, match="entrypoint"):
            make_request(entrypoint=entrypoint)

    with pytest.raises(ValueError, match="timeout_seconds"):
        make_request(timeout_seconds=0)
    with pytest.raises(ValueError, match="arguments"):
        make_request(arguments=("valid", "\x00bad"))


def test_execution_result_model_supports_blocked_without_fake_execution_data():
    result = SandboxExecutionResult(
        sandbox_id="sandbox-32",
        status=SandboxExecutionStatus.BLOCKED,
        isolation_backend="none",
        notes=("Actual sandbox execution backend is not configured.",),
    )

    assert result.exit_code is None
    assert result.duration_seconds is None
    assert result.started_at is None
    assert result.completed_at is None
    assert result.stdout == ""
    assert result.stderr == ""
    with pytest.raises(ValueError, match="cannot report execution measurements"):
        SandboxExecutionResult(
            sandbox_id="sandbox-32",
            status=SandboxExecutionStatus.BLOCKED,
            isolation_backend="none",
            exit_code=0,
        )


def test_unavailable_backend_identifies_itself_and_refuses_all_backend_steps():
    backend = UnavailableSandboxBackend()
    assert backend.backend_id == "none"
    assert backend.available is False
    assert backend.enforces_isolation is False

    session = SandboxBackendSession("sandbox-32", "none", object())
    with pytest.raises(SandboxExecutionNotAvailableError, match="not configured"):
        backend.prepare(make_sandbox(), make_request())
    with pytest.raises(SandboxExecutionNotAvailableError, match="not configured"):
        backend.execute(session, make_request())
    with pytest.raises(SandboxExecutionNotAvailableError, match="not configured"):
        backend.collect_result(session, make_request())
    with pytest.raises(SandboxExecutionNotAvailableError, match="not configured"):
        backend.cleanup(session)


def test_default_executor_returns_blocked_when_isolated_backend_is_unavailable():
    sandbox = make_sandbox()

    result = UnavailableSandboxExecutor().execute(sandbox, make_request())

    assert result.status == SandboxExecutionStatus.BLOCKED
    assert result.isolation_backend == "none"
    assert result.notes == ("Actual sandbox execution backend is not configured.",)
    assert sandbox.status == SandboxStatus.READY


def test_executor_does_not_trust_backend_claim_or_invoke_it_in_task_32():
    sandbox = make_sandbox()
    backend = ClaimedIsolatedBackend()

    result = UnavailableSandboxExecutor(backend).execute(sandbox, make_request())

    assert result.status == SandboxExecutionStatus.BLOCKED
    assert result.isolation_backend == "none"
    assert "not implemented" in result.notes[0]
    assert sandbox.status == SandboxStatus.READY


def test_blocked_request_does_not_fabricate_success_or_exit_code():
    result = UnavailableSandboxExecutor().execute(make_sandbox(), make_request())

    assert result.status not in {
        SandboxExecutionStatus.COMPLETED,
        SandboxExecutionStatus.FAILED,
        SandboxExecutionStatus.TIMED_OUT,
    }
    assert result.exit_code is None
    assert result.duration_seconds is None


def test_executor_validates_sandbox_request_linkage_and_state():
    executor = UnavailableSandboxExecutor()
    sandbox = make_sandbox()

    with pytest.raises(ValueError, match="sandbox_id"):
        executor.execute(sandbox, make_request(sandbox_id="other"))
    with pytest.raises(ValueError, match="proposal_id"):
        executor.execute(sandbox, make_request(proposal_id="other"))

    configured = IntegrationSandbox("configured", "proposal-32", "discovery-32")
    with pytest.raises(ValueError, match="READY"):
        executor.execute(
            configured,
            make_request(sandbox_id="configured"),
        )
    with pytest.raises(TypeError, match="IntegrationSandbox"):
        executor.execute(object(), make_request())
    with pytest.raises(TypeError, match="SandboxExecutionRequest"):
        executor.execute(sandbox, object())


def test_requested_resources_timeout_and_environment_cannot_exceed_policy():
    executor = UnavailableSandboxExecutor()
    sandbox = make_sandbox()

    with pytest.raises(ValueError, match="timeout_seconds exceeds"):
        executor.execute(
            sandbox,
            make_request(timeout_seconds=61),
        )
    with pytest.raises(ValueError, match="exceeds requested CPU-time"):
        executor.execute(
            sandbox,
            make_request(
                requested_resources=type(sandbox.isolation_policy.resource_limits)(
                    max_cpu_seconds=30
                )
            ),
        )
    with pytest.raises(ValueError, match="requested_resources exceed"):
        executor.execute(
            sandbox,
            make_request(
                requested_resources=type(sandbox.isolation_policy.resource_limits)(
                    max_memory_mb=513
                )
            ),
        )

    with pytest.raises(ValueError, match="environment_mode"):
        executor.execute(
            sandbox,
            make_request(environment_mode=SandboxEnvironmentMode.CLEAN),
        )


def test_request_does_not_accept_host_paths_or_environment_credentials():
    request = make_request()
    assert not hasattr(request, "environment")
    assert not hasattr(request, "credentials")
    assert not hasattr(request, "host_workspace")
    assert request.entrypoint == "src/main.py"


def test_sandbox_and_proposal_states_remain_unchanged_after_blocked_attempt():
    sandbox = make_sandbox()
    proposal = IntegrationProposal(
        id="proposal-32",
        source=IntegrationSource("github_repository", "https://github.com/example/repo"),
        requested_purpose="Test proposal",
        source_discovery_id="discovery-32",
    )
    for status in (
        IntegrationStatus.ANALYZING,
        IntegrationStatus.EVALUATING,
        IntegrationStatus.PROPOSED,
    ):
        proposal.transition(status)

    result = UnavailableSandboxExecutor().execute(sandbox, make_request())

    assert result.status == SandboxExecutionStatus.BLOCKED
    assert sandbox.status == SandboxStatus.READY
    assert proposal.status == IntegrationStatus.PROPOSED


def test_executor_uses_no_shell_subprocess_install_clone_or_network_operations():
    sandbox = make_sandbox()
    executor = UnavailableSandboxExecutor()
    with (
        patch.object(subprocess, "run", side_effect=AssertionError("subprocess used")),
        patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess used")),
        patch.object(os, "system", side_effect=AssertionError("shell used")),
        patch.object(os, "popen", side_effect=AssertionError("process used")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("network used")
        ),
    ):
        result = executor.execute(sandbox, make_request())

    assert result.status == SandboxExecutionStatus.BLOCKED


def test_blocked_result_is_deterministic_for_same_request_and_sandbox():
    sandbox = make_sandbox()
    executor = UnavailableSandboxExecutor()
    request = make_request()

    first = executor.execute(sandbox, request)
    second = executor.execute(sandbox, request)

    assert first == second
    assert first.status == SandboxExecutionStatus.BLOCKED
    assert first.isolation_backend == "none"
