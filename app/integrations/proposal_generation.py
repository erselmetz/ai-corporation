from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

from .analysis import SourceAnalysisResult
from .discovery import GITHUB_REPOSITORY_SOURCE_TYPE, SourceDiscoveryResult
from .evaluation import (
    EvaluationCategory,
    EvaluationFinding,
    EvaluationResult,
    EvaluationStatus,
)
from .models import IntegrationProposal, IntegrationSource, IntegrationStatus


class ProposalGenerationError(Exception):
    """Base class for source-backed proposal generation failures."""


class UnsupportedProposalSourceError(ProposalGenerationError):
    pass


class ProposalGenerator(ABC):
    """Builds a planned IntegrationProposal from completed source-stage results."""

    @abstractmethod
    def generate(
        self,
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
        evaluation: EvaluationResult,
    ) -> IntegrationProposal:
        raise NotImplementedError


class GitHubIntegrationProposalGenerator(ProposalGenerator):
    """Generate a traceable, unapproved proposal without performing integration."""

    def generate(
        self,
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
        evaluation: EvaluationResult,
    ) -> IntegrationProposal:
        self._validate_inputs(discovery, analysis, evaluation)

        purpose = self._requested_purpose(discovery, analysis)
        capabilities = self._intended_capabilities(evaluation)
        evaluation_findings = tuple(
            self._format_finding(finding) for finding in evaluation.findings
        )
        dependencies = self._findings_for(evaluation, EvaluationCategory.DEPENDENCIES)
        license_information = self._findings_for(
            evaluation, EvaluationCategory.LICENSE
        )
        security = self._findings_for(evaluation, EvaluationCategory.SECURITY)
        implementation_considerations = self._implementation_considerations(
            evaluation
        )
        evidence_references = tuple(
            dict.fromkeys(
                f"{item.source}:{item.reference}"
                for finding in evaluation.findings
                for item in finding.evidence
            )
        )
        approach = self._proposed_approach(evaluation)
        risk_information = self._risk_information(evaluation, security)

        identity = hashlib.sha256(
            f"{discovery.id}:{analysis.id}:{evaluation.id}".encode("utf-8")
        ).hexdigest()[:16]
        proposal = IntegrationProposal(
            id=f"proposal-{identity}",
            source=IntegrationSource(
                source_type=discovery.source.source_type,
                location=discovery.repository_url,
                project_name=discovery.repository_name,
            ),
            requested_purpose=purpose,
            project_name=discovery.repository_name,
            evaluation_information=self._evaluation_information(
                evaluation, evaluation_findings
            ),
            proposed_approach=approach,
            risk_information=risk_information,
            source_discovery_id=discovery.id,
            source_analysis_id=analysis.id,
            source_evaluation_id=evaluation.id,
            intended_capabilities=capabilities,
            evaluation_findings=evaluation_findings,
            key_strengths=evaluation.key_strengths,
            key_concerns=evaluation.key_concerns,
            unknowns=evaluation.unknowns,
            dependency_information=dependencies,
            license_information=license_information,
            security_considerations=security,
            integration_requirements=(
                evaluation.integration_requirements
                or ("unknown: no integration requirements were recorded",)
            ),
            implementation_considerations=implementation_considerations,
            evidence_references=evidence_references,
        )

        proposal.transition(IntegrationStatus.ANALYZING)
        proposal.transition(IntegrationStatus.EVALUATING)
        proposal.transition(IntegrationStatus.PROPOSED)
        return proposal

    @staticmethod
    def _validate_inputs(
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
        evaluation: EvaluationResult,
    ) -> None:
        if not isinstance(discovery, SourceDiscoveryResult):
            raise TypeError("discovery must be a SourceDiscoveryResult")
        if not isinstance(analysis, SourceAnalysisResult):
            raise TypeError("analysis must be a SourceAnalysisResult")
        if not isinstance(evaluation, EvaluationResult):
            raise TypeError("evaluation must be an EvaluationResult")
        if discovery.source.source_type != GITHUB_REPOSITORY_SOURCE_TYPE:
            raise UnsupportedProposalSourceError(
                f"Unsupported proposal source type: {discovery.source.source_type}"
            )
        if not discovery.is_public:
            raise ProposalGenerationError(
                "Proposal generation requires a public repository discovery"
            )
        if analysis.source_discovery_id != discovery.id:
            raise ProposalGenerationError(
                "Analysis result does not reference the supplied discovery result"
            )
        if evaluation.source_discovery_id != discovery.id:
            raise ProposalGenerationError(
                "Evaluation result does not reference the supplied discovery result"
            )
        if evaluation.source_analysis_id != analysis.id:
            raise ProposalGenerationError(
                "Evaluation result does not reference the supplied analysis result"
            )
        if (
            analysis.repository_name.casefold()
            != discovery.repository_name.casefold()
            or analysis.repository_url.rstrip("/").casefold()
            != discovery.repository_url.rstrip("/").casefold()
        ):
            raise ProposalGenerationError(
                "Analysis repository identity does not match discovery"
            )
        if any(
            finding.source_discovery_id != discovery.id
            for finding in evaluation.findings
        ):
            raise ProposalGenerationError(
                "Evaluation findings must reference the supplied discovery result"
            )

    @staticmethod
    def _requested_purpose(
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
    ) -> str:
        if analysis.project_purpose is not None:
            return (
                "Possible integration purpose based on untrusted source information: "
                f"{analysis.project_purpose.statement}"
            )
        if discovery.description:
            return (
                "Possible integration purpose based on repository metadata "
                f"(untrusted text): {discovery.description}"
            )
        return "unknown: source purpose was not established by discovery or analysis"

    @staticmethod
    def _intended_capabilities(evaluation: EvaluationResult) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                finding.summary
                for finding in evaluation.findings
                if finding.category == EvaluationCategory.CAPABILITY_FIT
                and finding.status == EvaluationStatus.SUPPORTED
            )
        ) or ("unknown: no potential capability was supported by available evidence",)

    @staticmethod
    def _format_finding(finding: EvaluationFinding) -> str:
        evidence = tuple(
            f"{item.source}:{item.reference} ({item.observed_value})"
            for item in finding.evidence
        )
        rendered = (
            f"{finding.category.value} [{finding.status.value}]: {finding.summary}"
        )
        if evidence:
            rendered += f" Evidence: {'; '.join(evidence)}"
        return rendered

    @classmethod
    def _findings_for(
        cls, evaluation: EvaluationResult, category: EvaluationCategory
    ) -> tuple[str, ...]:
        matches = tuple(
            cls._format_finding(finding)
            for finding in evaluation.findings
            if finding.category == category
        )
        return matches or (f"unknown: no {category.value} evidence was recorded",)

    @classmethod
    def _proposed_approach(cls, evaluation: EvaluationResult) -> str:
        interfaces = tuple(
            cls._format_finding(finding)
            for finding in evaluation.findings
            if finding.category == EvaluationCategory.ARCHITECTURE_COMPATIBILITY
            and finding.status == EvaluationStatus.SUPPORTED
        )
        if interfaces:
            approach = (
                "For a future, separately reviewed effort, validate the evidenced "
                "interface(s) and design a narrow isolated adapter. Evidence: "
                + " ".join(interfaces)
            )
        else:
            approach = (
                "For a future, separately reviewed effort, first establish and "
                "validate a narrow adapter boundary; current evaluation evidence "
                "does not establish an interface."
            )
        return (
            f"{approach} This proposal authorizes no execution, source modification, "
            "capability activation, or integration."
        )

    @staticmethod
    def _risk_information(
        evaluation: EvaluationResult, security: tuple[str, ...]
    ) -> str:
        sections = [
            "Evidence-backed concerns: "
            + (
                "; ".join(evaluation.key_concerns)
                if evaluation.key_concerns
                else "unknown: no concerns were reported"
            ),
            "Unknowns: "
            + ("; ".join(evaluation.unknowns) if evaluation.unknowns else "none recorded"),
            "Security observations: " + "; ".join(security),
        ]
        if not evaluation.complete:
            sections.append("Evaluation is incomplete because its source analysis was incomplete.")
        return "\n".join(sections)

    @staticmethod
    def _implementation_considerations(
        evaluation: EvaluationResult,
    ) -> tuple[str, ...]:
        considerations = list(evaluation.integration_requirements)
        if not evaluation.complete:
            considerations.append(
                "unknown: evaluation is incomplete; resolve missing evidence before review"
            )
        return tuple(dict.fromkeys(considerations)) or (
            "unknown: no implementation considerations were recorded",
        )

    @staticmethod
    def _evaluation_information(
        evaluation: EvaluationResult, findings: tuple[str, ...]
    ) -> str:
        completeness = "complete" if evaluation.complete else "incomplete"
        return (
            f"Evaluation {evaluation.id} ({completeness}); "
            f"source discovery {evaluation.source_discovery_id}.\n"
            + "\n".join(findings)
        )
