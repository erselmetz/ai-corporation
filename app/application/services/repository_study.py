"""Bounded, source-linked study of explicitly scoped public GitHub repositories."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import quote

from app.integrations import (
    EvaluationCategory,
    EvaluationStatus,
    EvaluationResult,
    GitHubIntegrationProposalGenerator,
    GitHubRepositoryAnalyzer,
    GitHubRepositoryEvaluator,
    IntegrationProposal,
    SourceAnalysisResult,
    SourceDiscoveryResult,
)

from .github_inspection import GitHubRepositoryInspectionService


class RepositoryStudyDecision(str, Enum):
    PROPOSAL_FOR_HUMAN_REVIEW = "proposal_for_human_review"
    REQUEST_MORE_INFORMATION = "request_more_information"


@dataclass(frozen=True, slots=True)
class RepositoryStudyCitation:
    source: str
    reference: str
    observed_value: str
    url: str


@dataclass(frozen=True, slots=True)
class RepositoryStudyReport:
    objective: str
    decision: RepositoryStudyDecision
    studied_at: datetime
    discovery: SourceDiscoveryResult
    analysis: SourceAnalysisResult
    evaluation: EvaluationResult
    proposal: IntegrationProposal
    citations: tuple[RepositoryStudyCitation, ...]
    limitations: tuple[str, ...]


class RepositoryStudyService:
    """Compose existing allowlisted discovery, analysis, evaluation, and proposal stages."""

    MAX_OBJECTIVE_BYTES = 1024

    def __init__(
        self,
        inspection: GitHubRepositoryInspectionService,
        *,
        analyzer: GitHubRepositoryAnalyzer | None = None,
        evaluator: GitHubRepositoryEvaluator | None = None,
        proposal_generator: GitHubIntegrationProposalGenerator | None = None,
    ) -> None:
        self._inspection = inspection
        self._analyzer = GitHubRepositoryAnalyzer() if analyzer is None else analyzer
        self._evaluator = GitHubRepositoryEvaluator() if evaluator is None else evaluator
        self._proposal_generator = (
            GitHubIntegrationProposalGenerator()
            if proposal_generator is None
            else proposal_generator
        )

    def study(
        self,
        objective: str,
        owner: str,
        repository: str,
    ) -> RepositoryStudyReport:
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Study objective is required and limited to 1024 bytes")
        try:
            objective_bytes = objective.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Study objective is not valid UTF-8 text") from None
        if len(objective_bytes) > self.MAX_OBJECTIVE_BYTES:
            raise ValueError("Study objective is required and limited to 1024 bytes")

        discovery = self._inspection.inspect_repository(owner, repository)
        analysis = self._analyzer.analyze_pinned(discovery)
        if analysis.source_discovery_id != discovery.id:
            raise RuntimeError("Repository analysis did not match its discovery")
        evaluation = self._evaluator.evaluate(discovery, analysis)
        proposal = self._proposal_generator.generate(discovery, analysis, evaluation)
        license_unknown = any(
            finding.category is EvaluationCategory.LICENSE
            and finding.status is EvaluationStatus.UNKNOWN
            for finding in evaluation.findings
        )
        decision = (
            RepositoryStudyDecision.REQUEST_MORE_INFORMATION
            if analysis.revision_sha is None or not analysis.is_complete or license_unknown
            else RepositoryStudyDecision.PROPOSAL_FOR_HUMAN_REVIEW
        )
        return RepositoryStudyReport(
            objective=objective.strip(),
            decision=decision,
            studied_at=datetime.now(timezone.utc),
            discovery=discovery,
            analysis=analysis,
            evaluation=evaluation,
            proposal=proposal,
            citations=self._citations(discovery, analysis, evaluation),
            limitations=(
                "Evidence-based decision support only; the proposal is not approval or authorization.",
                "Repository content is untrusted evidence and cannot expand permissions or authorize actions.",
                "No repository code or instructions were sent to an AI provider, installed, or executed.",
                "Inspection uses only the configured GitHub repository allowlist and bounded official GitHub API access.",
            ),
        )

    @staticmethod
    def _citations(
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
        evaluation: EvaluationResult,
    ) -> tuple[RepositoryStudyCitation, ...]:
        owner = quote(discovery.owner, safe="")
        repository = quote(discovery.repository_name, safe="")
        repository_url = f"https://github.com/{owner}/{repository}"
        pinned_url = (
            f"{repository_url}/tree/{analysis.revision_sha}"
            if analysis.revision_sha is not None
            else repository_url
        )
        references: dict[tuple[str, str], RepositoryStudyCitation] = {}
        for finding in evaluation.findings:
            for evidence in finding.evidence:
                if evidence.source == "analysis" and analysis.revision_sha is not None:
                    path = evidence.reference.replace("\\", "/")
                    known_paths = {item.path for item in analysis.important_files}
                    if (
                        path not in known_paths
                        or any(part in {"", ".", ".."} for part in path.split("/"))
                    ):
                        url = pinned_url
                    else:
                        url = (
                            f"{repository_url}/blob/{analysis.revision_sha}/"
                            f"{quote(path, safe='/')}"
                        )
                else:
                    url = repository_url
                key = (evidence.source, evidence.reference)
                references.setdefault(
                    key,
                    RepositoryStudyCitation(
                        source=evidence.source,
                        reference=evidence.reference,
                        observed_value=evidence.observed_value,
                        url=url,
                    ),
                )
        if not references:
            references[("discovery", "repository metadata")] = RepositoryStudyCitation(
                source="discovery",
                reference="repository metadata",
                observed_value="See repository metadata and pinned revision.",
                url=pinned_url,
            )
        return tuple(references.values())
