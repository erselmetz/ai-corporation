"""Deterministic, evidence-bounded review records for capability candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.capability_discovery import CapabilityCandidate

MAX_EVALUATION_EVIDENCE = 30
MAX_EVALUATION_EVIDENCE_ID_BYTES = 128
MAX_EVALUATION_STATEMENT_BYTES = 2_048
MAX_EVALUATION_REFERENCE_BYTES = 2_048
MAX_EVALUATION_TOTAL_BYTES = 32_768
MAX_EVALUATION_LIMITATIONS = 8
MAX_EVALUATION_LIMITATION_BYTES = 512


class CapabilityEvaluationDimension(str, Enum):
    CAPABILITY_FIT = "capability_fit"
    RISK = "risk"
    OPERATIONAL_REQUIREMENTS = "operational_requirements"


class CallerReportedAssessment(str, Enum):
    SUPPORTS = "supports"
    CONCERN = "concern"
    UNKNOWN = "unknown"


class EvidenceCoverageStatus(str, Enum):
    DOCUMENTED = "documented"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityEvaluationEvidence:
    evidence_id: str
    dimension: CapabilityEvaluationDimension
    reported_assessment: CallerReportedAssessment
    statement: str
    source_reference: str

    def __post_init__(self) -> None:
        _validate_text(
            self.evidence_id,
            "evidence_id",
            MAX_EVALUATION_EVIDENCE_ID_BYTES,
        )
        if not isinstance(self.dimension, CapabilityEvaluationDimension):
            raise TypeError("dimension must be a CapabilityEvaluationDimension")
        if not isinstance(self.reported_assessment, CallerReportedAssessment):
            raise TypeError("reported_assessment must be a CallerReportedAssessment")
        _validate_text(
            self.statement,
            "statement",
            MAX_EVALUATION_STATEMENT_BYTES,
        )
        _validate_text(
            self.source_reference,
            "source_reference",
            MAX_EVALUATION_REFERENCE_BYTES,
        )


@dataclass(frozen=True, slots=True)
class CapabilityEvaluationCoverage:
    dimension: CapabilityEvaluationDimension
    status: EvidenceCoverageStatus
    evidence_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, CapabilityEvaluationDimension):
            raise TypeError("dimension must be a CapabilityEvaluationDimension")
        if not isinstance(self.status, EvidenceCoverageStatus):
            raise TypeError("status must be an EvidenceCoverageStatus")
        if (
            not isinstance(self.evidence_count, int)
            or isinstance(self.evidence_count, bool)
            or not 0 <= self.evidence_count <= MAX_EVALUATION_EVIDENCE
        ):
            raise ValueError("evidence_count is invalid")
        expected = (
            EvidenceCoverageStatus.DOCUMENTED
            if self.evidence_count
            else EvidenceCoverageStatus.UNKNOWN
        )
        if self.status is not expected:
            raise ValueError("coverage status must match the supplied evidence count")


@dataclass(frozen=True, slots=True)
class CapabilityEvaluationReport:
    candidate_id: str
    evaluated_at: datetime
    evidence: tuple[CapabilityEvaluationEvidence, ...]
    coverage: tuple[CapabilityEvaluationCoverage, ...]
    limitations: tuple[str, ...] = (
        "Evidence, assessments, and source references are caller-supplied and are not independently verified.",
        "Documented coverage means information was supplied; it does not establish truth, safety, fit, or readiness.",
        "This report is decision support only and does not approve, register, grant, or activate a capability.",
    )

    def __post_init__(self) -> None:
        _validate_text(
            self.candidate_id,
            "candidate_id",
            MAX_EVALUATION_EVIDENCE_ID_BYTES,
        )
        if (
            not isinstance(self.evaluated_at, datetime)
            or self.evaluated_at.tzinfo is None
            or self.evaluated_at.utcoffset() is None
        ):
            raise ValueError("evaluated_at must be timezone-aware")
        if not isinstance(self.evidence, tuple) or not all(
            isinstance(item, CapabilityEvaluationEvidence) for item in self.evidence
        ):
            raise TypeError("evidence must be an immutable tuple of evaluation evidence")
        if len(self.evidence) > MAX_EVALUATION_EVIDENCE:
            raise ValueError("evaluation evidence count exceeds its limit")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence IDs must be unique")
        if not isinstance(self.coverage, tuple) or not all(
            isinstance(item, CapabilityEvaluationCoverage) for item in self.coverage
        ):
            raise TypeError("coverage must be an immutable tuple of coverage results")
        if tuple(item.dimension for item in self.coverage) != tuple(
            CapabilityEvaluationDimension
        ):
            raise ValueError("coverage must contain each evaluation dimension in order")
        if tuple(item.evidence_count for item in self.coverage) != tuple(
            sum(evidence.dimension is item.dimension for evidence in self.evidence)
            for item in self.coverage
        ):
            raise ValueError("coverage counts must match supplied evidence")
        if _total_evidence_bytes(self.evidence) > MAX_EVALUATION_TOTAL_BYTES:
            raise ValueError("evaluation evidence exceeds its total byte limit")
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations must be an immutable tuple of text")
        if len(self.limitations) > MAX_EVALUATION_LIMITATIONS:
            raise ValueError("limitation count exceeds its limit")
        for limitation in self.limitations:
            _validate_text(
                limitation,
                "limitation",
                MAX_EVALUATION_LIMITATION_BYTES,
            )


class CapabilityEvaluationService:
    """Group caller evidence by fixed dimensions without inferring its truth."""

    def evaluate(
        self,
        candidate: CapabilityCandidate,
        evidence: tuple[CapabilityEvaluationEvidence, ...],
    ) -> CapabilityEvaluationReport:
        if not isinstance(candidate, CapabilityCandidate):
            raise TypeError("candidate must be a CapabilityCandidate")
        if not isinstance(evidence, tuple):
            raise TypeError("evidence must be an immutable tuple")
        if len(evidence) > MAX_EVALUATION_EVIDENCE:
            raise ValueError("evaluation evidence count exceeds its limit")
        if not all(
            isinstance(item, CapabilityEvaluationEvidence) for item in evidence
        ):
            raise TypeError("Expected CapabilityEvaluationEvidence")
        if len({item.evidence_id for item in evidence}) != len(evidence):
            raise ValueError("evidence IDs must be unique")
        if _total_evidence_bytes(evidence) > MAX_EVALUATION_TOTAL_BYTES:
            raise ValueError("evaluation evidence exceeds its total byte limit")

        coverage = tuple(
            CapabilityEvaluationCoverage(
                dimension=dimension,
                status=(
                    EvidenceCoverageStatus.DOCUMENTED
                    if any(item.dimension is dimension for item in evidence)
                    else EvidenceCoverageStatus.UNKNOWN
                ),
                evidence_count=sum(
                    item.dimension is dimension for item in evidence
                ),
            )
            for dimension in CapabilityEvaluationDimension
        )
        return CapabilityEvaluationReport(
            candidate_id=candidate.candidate_id,
            evaluated_at=datetime.now(timezone.utc),
            evidence=evidence,
            coverage=coverage,
        )


def _total_evidence_bytes(
    evidence: tuple[CapabilityEvaluationEvidence, ...],
) -> int:
    return sum(
        len(item.evidence_id.encode("utf-8"))
        + len(item.statement.encode("utf-8"))
        + len(item.source_reference.encode("utf-8"))
        for item in evidence
    )


def _validate_text(value: str, field_name: str, maximum_bytes: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    try:
        encoded_size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must contain valid Unicode text") from exc
    if encoded_size > maximum_bytes:
        raise ValueError(f"{field_name} exceeds its byte limit")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} contains control characters")
