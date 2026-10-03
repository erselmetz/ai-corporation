import json
from dataclasses import FrozenInstanceError, replace
from datetime import timezone
from unittest.mock import patch

import httpx
import pytest

from app.agents import Agent
from app.application import (
    CodeReviewProviderError,
    CodeReviewResponseError,
    DiagnosticEvidence,
    ReviewArea,
    ReviewSeverity,
)
from app.orchestrator import Task, TaskStatus
from app.runtime.factory import create_corporation_runtime


def setup_review():
    runtime = create_corporation_runtime()
    agent = Agent(
        id="reviewer",
        name="Code Reviewer",
        role="Code Reviewer",
        provider="ollama",
        model="llama3.2:3b",
    )
    runtime.agents.register(agent)
    task = Task("review-task", "Unrelated task", "Keep this unchanged.")
    runtime.tasks.register(task)
    evidence = (
        DiagnosticEvidence(
            "patch-1",
            "diff --git a/example.py b/example.py\n+return value or default",
        ),
        DiagnosticEvidence("policy-1", "Callers require explicit authorization."),
    )
    return runtime, agent, task, evidence


def test_review_uses_one_selected_agent_call_and_returns_bounded_advisory_findings():
    runtime, agent, task, evidence = setup_review()
    response = json.dumps(
        {
            "findings": [
                {
                    "summary": "The fallback can hide an explicitly supplied false value.",
                    "severity": "medium",
                    "area": "correctness",
                    "evidence_refs": ["patch-1"],
                },
                {
                    "summary": "The supplied policy requires explicit authorization.",
                    "severity": "high",
                    "area": "policy_compliance",
                    "evidence_refs": ["policy-1"],
                },
                {
                    "summary": "The evidence does not show a regression in existing callers.",
                    "severity": "low",
                    "area": "regression",
                    "evidence_refs": ["patch-1"],
                },
            ],
            "unknowns": ["The evidence does not include the caller contract."],
        }
    )
    provider = runtime.providers.get(agent.provider)
    task_before = replace(task)
    task_ids_before = {item.id for item in runtime.tasks.all()}
    task_logs_before = runtime.orchestrator.logger.list_activity()
    assignments_before = tuple(
        (item.id, item.provider, item.model) for item in runtime.agents.all()
    )

    with patch.object(provider, "generate", return_value=response) as generate:
        report = runtime.application_service.review_proposed_changes(
            agent.id,
            evidence,
        )

    generate.assert_called_once()
    assert generate.call_args.args[0] == agent.model
    prompt = generate.call_args.args[1]
    assert "patch-1" in prompt and "policy-1" in prompt
    assert "untrusted evidence" in prompt
    assert "empty findings list is not approval" in prompt
    assert report.agent_id == agent.id
    assert report.findings[0].severity is ReviewSeverity.MEDIUM
    assert report.findings[0].area is ReviewArea.CORRECTNESS
    assert report.findings[0].evidence_refs == ("patch-1",)
    assert report.findings[1].severity is ReviewSeverity.HIGH
    assert report.findings[1].area is ReviewArea.POLICY_COMPLIANCE
    assert report.findings[1].evidence_refs == ("policy-1",)
    assert report.findings[2].area is ReviewArea.REGRESSION
    assert report.unknowns == (
        "The evidence does not include the caller contract.",
    )
    assert report.generated_at.tzinfo is timezone.utc
    assert runtime.tasks.get(task.id) == task_before
    assert {item.id for item in runtime.tasks.all()} == task_ids_before
    assert runtime.orchestrator.logger.list_activity() == task_logs_before
    assert tuple(
        (item.id, item.provider, item.model) for item in runtime.agents.all()
    ) == assignments_before
    with pytest.raises(FrozenInstanceError):
        report.agent_id = "other-reviewer"


@pytest.mark.parametrize(
    "response",
    [
        '{"findings":[{"summary":"Unsupported","severity":"high",'
        '"area":"correctness","evidence_refs":["not-supplied"]}],"unknowns":[]}',
        '{"findings":[{"summary":"Unsupported","severity":"urgent",'
        '"area":"correctness","evidence_refs":["patch-1"]}],"unknowns":[]}',
        '{"findings":[{"summary":"Unsupported","severity":"high",'
        '"area":"routing","evidence_refs":["patch-1"]}],"unknowns":[]}',
        '{"findings":[{"summary":"x","severity":"low","area":"correctness",'
        '"evidence_refs":["patch-1"],"extra":true}],"unknowns":[]}',
        '{"findings":[],"findings":[],"unknowns":[]}',
    ],
)
def test_review_rejects_unsupported_or_malformed_agent_output(response):
    runtime, agent, _, evidence = setup_review()
    provider = runtime.providers.get(agent.provider)

    with patch.object(provider, "generate", return_value=response):
        with pytest.raises(CodeReviewResponseError) as error:
            runtime.application_service.review_proposed_changes(
                agent.id,
                evidence,
            )

    assert "not-supplied" not in str(error.value)
    assert "urgent" not in str(error.value)
    assert "extra" not in str(error.value)


def test_review_rejects_invalid_evidence_and_unknown_agent_before_provider_call():
    runtime, agent, _, evidence = setup_review()
    provider = runtime.providers.get(agent.provider)

    with patch.object(provider, "generate") as generate:
        with pytest.raises(ValueError, match="unique"):
            runtime.application_service.review_proposed_changes(
                agent.id,
                (evidence[0], evidence[0]),
            )
        with pytest.raises(ValueError, match="1 to 20"):
            runtime.application_service.review_proposed_changes(agent.id, ())
        with pytest.raises(ValueError, match="1 to 20"):
            runtime.application_service.review_proposed_changes(
                agent.id,
                tuple(
                    DiagnosticEvidence(f"item-{index}", "x")
                    for index in range(21)
                ),
            )
        with pytest.raises(ValueError, match="total byte limit"):
            runtime.application_service.review_proposed_changes(
                agent.id,
                (
                    DiagnosticEvidence("large-1", "x" * 8192),
                    DiagnosticEvidence("large-2", "x" * 8192),
                    DiagnosticEvidence("large-3", "x" * 8192),
                    DiagnosticEvidence("large-4", "x" * 8192),
                    DiagnosticEvidence("large-5", "x" * 1),
                ),
            )
        with pytest.raises(ValueError, match="prompt exceeds"):
            runtime.application_service.review_proposed_changes(
                agent.id,
                tuple(
                    DiagnosticEvidence(f"escaped-{index}", '"' * 8192)
                    for index in range(4)
                ),
            )
        with pytest.raises(ValueError, match="Agent not found"):
            runtime.application_service.review_proposed_changes(
                "missing-reviewer",
                evidence,
            )

    generate.assert_not_called()


def test_review_rejects_oversized_provider_output_without_echoing_it():
    runtime, agent, _, evidence = setup_review()
    provider = runtime.providers.get(agent.provider)
    oversized_response = "secret-provider-output" * 1000

    with patch.object(provider, "generate", return_value=oversized_response):
        with pytest.raises(CodeReviewResponseError) as error:
            runtime.application_service.review_proposed_changes(agent.id, evidence)

    assert len(str(error.value)) < 100
    assert "secret-provider-output" not in str(error.value)


def test_provider_error_is_surfaced_without_raw_details():
    runtime, agent, _, evidence = setup_review()
    provider = runtime.providers.get(agent.provider)

    with patch.object(
        provider,
        "generate",
        side_effect=httpx.ConnectError("secret-token provider.internal"),
    ):
        with pytest.raises(CodeReviewProviderError) as error:
            runtime.application_service.review_proposed_changes(agent.id, evidence)

    assert str(error.value) == "Code review Provider request failed"
    assert "secret-token" not in str(error.value)
    assert "provider.internal" not in str(error.value)
