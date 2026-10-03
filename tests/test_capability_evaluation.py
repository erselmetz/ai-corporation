from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from app.capability_discovery import CapabilityCandidate
from app.capability_evaluation import (
    MAX_EVALUATION_EVIDENCE,
    MAX_EVALUATION_TOTAL_BYTES,
    CallerReportedAssessment,
    CapabilityEvaluationCoverage,
    CapabilityEvaluationDimension,
    CapabilityEvaluationEvidence,
    CapabilityEvaluationReport,
    CapabilityEvaluationService,
    EvidenceCoverageStatus,
)
from app.runtime.factory import create_corporation_runtime


def candidate() -> CapabilityCandidate:
    return CapabilityCandidate(
        candidate_id="capability-1",
        name="Read-only status integration",
        description="Read service status without changing remote state.",
        source_reference="caller-note:status-integration",
    )


def evidence(
    evidence_id: str,
    dimension: CapabilityEvaluationDimension,
    assessment: CallerReportedAssessment = CallerReportedAssessment.SUPPORTS,
    statement: str = "Caller supplied observation.",
) -> CapabilityEvaluationEvidence:
    return CapabilityEvaluationEvidence(
        evidence_id=evidence_id,
        dimension=dimension,
        reported_assessment=assessment,
        statement=statement,
        source_reference=f"caller-evidence:{evidence_id}",
    )


def test_evaluation_preserves_caller_evidence_and_reports_dimension_coverage() -> None:
    supplied = (
        evidence("fit-1", CapabilityEvaluationDimension.CAPABILITY_FIT),
        evidence(
            "risk-1",
            CapabilityEvaluationDimension.RISK,
            CallerReportedAssessment.CONCERN,
            "Caller noted a possible outbound network dependency.",
        ),
    )

    report = CapabilityEvaluationService().evaluate(candidate(), supplied)

    assert report.candidate_id == "capability-1"
    assert report.evidence is supplied
    assert report.evaluated_at.tzinfo == timezone.utc
    assert tuple(item.dimension for item in report.coverage) == tuple(
        CapabilityEvaluationDimension
    )
    assert tuple(item.status for item in report.coverage) == (
        EvidenceCoverageStatus.DOCUMENTED,
        EvidenceCoverageStatus.DOCUMENTED,
        EvidenceCoverageStatus.UNKNOWN,
    )
    assert tuple(item.evidence_count for item in report.coverage) == (1, 1, 0)
    assert report.evidence[1].reported_assessment is CallerReportedAssessment.CONCERN
    assert any("not independently verified" in item for item in report.limitations)
    assert any("does not approve" in item for item in report.limitations)
    with pytest.raises(FrozenInstanceError):
        report.evidence = ()
    with pytest.raises(FrozenInstanceError):
        report.coverage[0].status = EvidenceCoverageStatus.UNKNOWN


def test_empty_evidence_keeps_all_evaluation_dimensions_unknown() -> None:
    report = CapabilityEvaluationService().evaluate(candidate(), ())

    assert report.evidence == ()
    assert all(
        item.status is EvidenceCoverageStatus.UNKNOWN
        and item.evidence_count == 0
        for item in report.coverage
    )


def test_application_service_review_does_not_mutate_runtime_or_call_provider() -> None:
    runtime = create_corporation_runtime()
    agent_state = tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    )
    task_state = tuple(task.id for task in runtime.tasks.all())
    provider = runtime.providers.get("ollama")

    with patch.object(
        provider,
        "generate",
        Mock(side_effect=AssertionError("Evaluation invoked a Provider")),
    ) as generate:
        report = runtime.application_service.evaluate_capability(
            candidate(),
            (evidence("fit-1", CapabilityEvaluationDimension.CAPABILITY_FIT),),
        )

    generate.assert_not_called()
    assert report.candidate_id == candidate().candidate_id
    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == agent_state
    assert tuple(task.id for task in runtime.tasks.all()) == task_state
    assert runtime.providers.get("ollama") is provider


@pytest.mark.parametrize(
    ("candidate_value", "items", "error", "message"),
    [
        (None, (), TypeError, "CapabilityCandidate"),
        (candidate(), [], TypeError, "immutable tuple"),
        (candidate(), (object(),), TypeError, "Expected CapabilityEvaluationEvidence"),
        (
            candidate(),
            (
                evidence("duplicate", CapabilityEvaluationDimension.RISK),
                evidence("duplicate", CapabilityEvaluationDimension.CAPABILITY_FIT),
            ),
            ValueError,
            "unique",
        ),
        (
            candidate(),
            tuple(
                evidence(f"evidence-{index}", CapabilityEvaluationDimension.RISK)
                for index in range(MAX_EVALUATION_EVIDENCE + 1)
            ),
            ValueError,
            "count exceeds",
        ),
    ],
)
def test_evaluation_rejects_invalid_candidate_or_evidence(
    candidate_value: object,
    items: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        CapabilityEvaluationService().evaluate(
            candidate_value,  # type: ignore[arg-type]
            items,  # type: ignore[arg-type]
        )


def test_evaluation_enforces_total_evidence_byte_limit() -> None:
    items = tuple(
        evidence(
            f"large-{index}",
            CapabilityEvaluationDimension.RISK,
            statement="x" * 2_048,
        )
        for index in range(MAX_EVALUATION_TOTAL_BYTES // 2_048)
    )
    with pytest.raises(ValueError, match="total byte limit"):
        CapabilityEvaluationService().evaluate(candidate(), items)


def test_report_rejects_naive_time_and_coverage_not_matching_evidence() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CapabilityEvaluationReport(
            candidate_id="capability-1",
            evaluated_at=datetime(2026, 10, 4),
            evidence=(),
            coverage=(),
        )

    with pytest.raises(ValueError, match="each evaluation dimension"):
        CapabilityEvaluationReport(
            candidate_id="capability-1",
            evaluated_at=datetime.now(timezone.utc),
            evidence=(),
            coverage=(),
        )

    with pytest.raises(ValueError, match="coverage counts"):
        CapabilityEvaluationReport(
            candidate_id="capability-1",
            evaluated_at=datetime.now(timezone.utc),
            evidence=(evidence("fit-1", CapabilityEvaluationDimension.CAPABILITY_FIT),),
            coverage=tuple(
                CapabilityEvaluationCoverage(
                    dimension=dimension,
                    status=EvidenceCoverageStatus.UNKNOWN,
                    evidence_count=0,
                )
                for dimension in CapabilityEvaluationDimension
            ),
        )
