import json
from dataclasses import replace
from unittest.mock import patch

import httpx
import pytest

from app.agents import Agent
from app.application import (
    DiagnosticEvidence,
    DiagnosticProviderError,
    DiagnosticResponseError,
)
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime


def setup_diagnostic():
    runtime = create_corporation_runtime()
    diagnostic_agent = Agent(
        id="diagnostic",
        name="Diagnostic Agent",
        role="Diagnostic Agent",
        provider="ollama",
        model="llama3.2:3b",
    )
    runtime.agents.register(diagnostic_agent)
    task = Task(
        "diagnostic-task",
        "Failed operation",
        "Private exception content must not be retrieved",
        status=TaskStatus.FAILED,
        error="secret=not-for-diagnostics",
        failure_category=TaskFailureCategory.EXECUTION,
    )
    runtime.tasks.register(task)
    failure = next(
        entry
        for entry in runtime.application_service.detect_failures().failures
        if entry.task_id == task.id
    )
    evidence = (
        DiagnosticEvidence("config-1", "The explicitly supplied setting is disabled."),
        DiagnosticEvidence("log-2", "The caller-supplied operation returned status 503."),
    )
    return runtime, task, diagnostic_agent, failure, evidence


def test_diagnostic_agent_uses_one_explicit_call_and_cites_only_supplied_evidence():
    runtime, task, agent, failure, evidence = setup_diagnostic()
    response = json.dumps(
        {
            "findings": [
                {
                    "summary": "The supplied configuration reports the feature disabled.",
                    "evidence_refs": ["config-1"],
                }
            ],
            "unknowns": ["The supplied evidence does not establish a root cause."],
        }
    )
    provider = runtime.providers.get(agent.provider)
    task_before = replace(task)
    task_logs_before = runtime.orchestrator.logger.get_task_logs(task.id)
    task_ids_before = {item.id for item in runtime.tasks.all()}
    assignments_before = tuple(
        (item.id, item.provider, item.model) for item in runtime.agents.all()
    )
    with patch.object(provider, "generate", return_value=response) as generate:
        report = runtime.application_service.diagnose_failure(
            agent.id,
            failure,
            evidence,
        )

    generate.assert_called_once()
    assert generate.call_args.args[0] == agent.model
    prompt = generate.call_args.args[1]
    assert "config-1" in prompt and "log-2" in prompt
    assert "secret=not-for-diagnostics" not in prompt
    assert report.failure == failure
    assert report.agent_id == agent.id
    assert report.findings[0].evidence_refs == ("config-1",)
    assert report.unknowns == (
        "The supplied evidence does not establish a root cause.",
    )
    assert runtime.tasks.get(task.id) == task_before
    assert {item.id for item in runtime.tasks.all()} == task_ids_before
    assert runtime.orchestrator.logger.get_task_logs(task.id) == task_logs_before
    assert tuple(
        (item.id, item.provider, item.model) for item in runtime.agents.all()
    ) == assignments_before


def test_diagnostic_response_rejects_citations_outside_supplied_evidence():
    runtime, _, agent, failure, evidence = setup_diagnostic()
    invalid_response = json.dumps(
        {
            "findings": [
                {"summary": "Unsupported", "evidence_refs": ["not-supplied"]}
            ],
            "unknowns": [],
        }
    )
    provider = runtime.providers.get(agent.provider)

    with patch.object(provider, "generate", return_value=invalid_response):
        with pytest.raises(DiagnosticResponseError) as error:
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                evidence,
            )

    assert "not-supplied" not in str(error.value)


def test_stale_failure_and_invalid_evidence_are_rejected_before_provider_call():
    runtime, task, agent, failure, evidence = setup_diagnostic()
    provider = runtime.providers.get(agent.provider)
    with patch.object(provider, "generate") as generate:
        runtime.tasks.update(replace(task, status=TaskStatus.COMPLETED))
        with pytest.raises(ValueError, match="no longer current"):
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                evidence,
            )
        with pytest.raises(ValueError, match="unique"):
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                (evidence[0], evidence[0]),
            )

    generate.assert_not_called()


def test_provider_http_error_is_surfaced_without_raw_connection_details():
    runtime, _, agent, failure, evidence = setup_diagnostic()
    provider = runtime.providers.get(agent.provider)
    with patch.object(
        provider,
        "generate",
        side_effect=httpx.ConnectError("https://user:secret@provider.invalid"),
    ):
        with pytest.raises(DiagnosticProviderError) as error:
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                evidence,
            )

    assert str(error.value) == "Diagnostic Provider request failed"
    assert "secret" not in str(error.value)


def test_duplicate_json_keys_are_rejected_without_echoing_provider_output():
    runtime, _, agent, failure, evidence = setup_diagnostic()
    response = (
        '{"findings":[{"summary":"x","evidence_refs":["config-1"],'
        '"evidence_refs":["not-supplied"]}],"unknowns":[]}'
    )
    provider = runtime.providers.get(agent.provider)
    with patch.object(provider, "generate", return_value=response):
        with pytest.raises(DiagnosticResponseError) as error:
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                evidence,
            )

    assert "not-supplied" not in str(error.value)


def test_diagnostic_evidence_and_model_output_byte_bounds_are_enforced():
    runtime, _, agent, failure, evidence = setup_diagnostic()
    provider = runtime.providers.get(agent.provider)
    with patch.object(provider, "generate") as generate:
        with pytest.raises(ValueError, match="1 to 20"):
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                evidence * 11,
            )
        with pytest.raises(ValueError, match="total byte limit"):
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                tuple(
                    DiagnosticEvidence(f"item-{index}", "x" * 8192)
                    for index in range(5)
                ),
            )

    generate.assert_not_called()
    with patch.object(provider, "generate", return_value="x" * 8193):
        with pytest.raises(DiagnosticResponseError):
            runtime.application_service.diagnose_failure(
                agent.id,
                failure,
                evidence,
            )
