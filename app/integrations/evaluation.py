from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .analysis import AnalysisObservation, ProjectFile, SourceAnalysisResult
from .discovery import (
    GITHUB_REPOSITORY_SOURCE_TYPE,
    SourceDiscoveryResult,
)
from .models import IntegrationSource


class EvaluationCategory(str, Enum):
    CAPABILITY_FIT = "capability_fit"
    ARCHITECTURE_COMPATIBILITY = "architecture_compatibility"
    DEPENDENCIES = "dependencies"
    LICENSE = "license"
    SECURITY = "security"
    MAINTENANCE = "maintenance"
    INTEGRATION_COMPLEXITY = "integration_complexity"


class EvaluationStatus(str, Enum):
    SUPPORTED = "supported"
    CONCERN = "concern"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class SecurityObservationStatus(str, Enum):
    OBSERVED = "observed"
    NOT_OBSERVED = "not_observed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvaluationEvidence:
    source_discovery_id: str
    source: str
    reference: str
    observed_value: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_discovery_id, str) or not self.source_discovery_id.strip():
            raise ValueError("Evaluation evidence requires a discovery id")
        if self.source not in {"discovery", "analysis"}:
            raise ValueError("Evaluation evidence source must be discovery or analysis")
        if not isinstance(self.reference, str) or not self.reference.strip():
            raise ValueError("Evaluation evidence reference cannot be empty")
        if not isinstance(self.observed_value, str) or not self.observed_value.strip():
            raise ValueError("Evaluation evidence value cannot be empty")


@dataclass(frozen=True)
class EvaluationFinding:
    source_discovery_id: str
    category: EvaluationCategory
    status: EvaluationStatus
    summary: str
    evidence: tuple[EvaluationEvidence, ...] = ()
    security_status: SecurityObservationStatus | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_discovery_id, str) or not self.source_discovery_id.strip():
            raise ValueError("Evaluation finding requires a discovery id")
        if not isinstance(self.category, EvaluationCategory):
            raise TypeError("Evaluation finding category must be an EvaluationCategory")
        if not isinstance(self.status, EvaluationStatus):
            raise TypeError("Evaluation finding status must be an EvaluationStatus")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("Evaluation finding summary cannot be empty")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, EvaluationEvidence) for item in self.evidence
        ):
            raise TypeError("Evaluation finding evidence must contain EvaluationEvidence values")
        if self.category == EvaluationCategory.SECURITY and self.security_status is None:
            raise ValueError("Security findings require an observation status")
        if self.category != EvaluationCategory.SECURITY and self.security_status is not None:
            raise ValueError("Only security findings may set security status")
        if any(item.source_discovery_id != self.source_discovery_id for item in self.evidence):
            raise ValueError("Evaluation evidence must reference the finding's discovery")


@dataclass(frozen=True)
class EvaluationResult:
    id: str
    source_discovery_id: str
    evaluated_at: datetime
    findings: tuple[EvaluationFinding, ...]
    key_strengths: tuple[str, ...]
    key_concerns: tuple[str, ...]
    unknowns: tuple[str, ...]
    integration_requirements: tuple[str, ...]
    complete: bool
    notes: tuple[str, ...]
    source_analysis_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or not self.id.strip()
            or not isinstance(self.source_discovery_id, str)
            or not self.source_discovery_id.strip()
        ):
            raise ValueError("Evaluation result id and discovery id are required")
        if not isinstance(self.findings, tuple) or any(
            not isinstance(item, EvaluationFinding) for item in self.findings
        ):
            raise TypeError("Evaluation result findings must contain EvaluationFinding values")
        if any(item.source_discovery_id != self.source_discovery_id for item in self.findings):
            raise ValueError("Evaluation findings must reference the result's discovery")
        if self.source_analysis_id is not None and (
            not isinstance(self.source_analysis_id, str)
            or not self.source_analysis_id.strip()
        ):
            raise ValueError("Evaluation source analysis id cannot be empty")


class SourceEvaluator(ABC):
    """Evidence-backed decision-support boundary for already analyzed sources."""

    @abstractmethod
    def evaluate(
        self,
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
    ) -> EvaluationResult:
        raise NotImplementedError


class GitHubRepositoryEvaluator(SourceEvaluator):
    """Evaluate available GitHub discovery/analysis evidence without fetching code."""

    _SECURITY_SIGNALS = (
        ("shell or system access", re.compile(r"\b(shell|subprocess|system command|terminal access)\b", re.I)),
        ("file modification", re.compile(r"\b(write|modify|delete|edit)\s+(?:local\s+)?files?\b", re.I)),
        ("browser or computer control", re.compile(r"\b(browser automation|computer control|mouse and keyboard)\b", re.I)),
        ("network access", re.compile(r"\b(network access|outbound connection|http client|api client)\b", re.I)),
        ("credential handling", re.compile(r"\b(credentials?|secrets?|api keys?|tokens?)\b", re.I)),
        ("external service dependency", re.compile(r"\b(external service|hosted api|cloud service)\b", re.I)),
        ("arbitrary code execution", re.compile(r"\b(execute arbitrary code|run arbitrary code|dynamic code execution)\b", re.I)),
        ("privileged operations", re.compile(r"\b(administrator|root access|privileged operation)\b", re.I)),
    )

    def evaluate(
        self,
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
    ) -> EvaluationResult:
        self._validate_input(discovery, analysis)
        source_id = discovery.id
        findings: list[EvaluationFinding] = []

        findings.extend(self._capability_findings(source_id, analysis))
        findings.extend(self._architecture_findings(source_id, analysis))
        findings.extend(self._dependency_findings(source_id, analysis))
        findings.append(self._license_finding(discovery))
        findings.extend(self._security_findings(source_id, discovery, analysis))
        findings.extend(self._maintenance_findings(source_id, discovery, analysis))
        findings.extend(self._complexity_findings(source_id, analysis))

        strengths = tuple(
            finding.summary
            for finding in findings
            if finding.status == EvaluationStatus.SUPPORTED
        )
        concerns = tuple(
            finding.summary
            for finding in findings
            if finding.status == EvaluationStatus.CONCERN
        )
        unknowns = tuple(
            finding.summary
            for finding in findings
            if finding.status == EvaluationStatus.UNKNOWN
        )
        requirements = self._integration_requirements(discovery, analysis)
        notes = (
            "Decision support only: findings describe available evidence and do not recommend, approve, or perform integration.",
            "External repository content is untrusted; evaluation reads only the supplied discovery and analysis results.",
        )
        stable_key = hashlib.sha256(
            f"{source_id}:{analysis.id}".encode("utf-8")
        ).hexdigest()[:16]
        return EvaluationResult(
            id=f"evaluation-{stable_key}",
            source_discovery_id=source_id,
            evaluated_at=datetime.now(timezone.utc),
            findings=tuple(findings),
            key_strengths=strengths,
            key_concerns=concerns,
            unknowns=unknowns,
            integration_requirements=requirements,
            complete=analysis.is_complete,
            notes=notes,
            source_analysis_id=analysis.id,
        )

    @staticmethod
    def _validate_input(
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
    ) -> None:
        if not isinstance(discovery, SourceDiscoveryResult):
            raise TypeError("discovery must be a SourceDiscoveryResult")
        if not isinstance(analysis, SourceAnalysisResult):
            raise TypeError("analysis must be a SourceAnalysisResult")
        if not isinstance(discovery.source, IntegrationSource):
            raise TypeError("discovery.source must be an IntegrationSource")
        if not isinstance(discovery.id, str) or not discovery.id.strip():
            raise ValueError("Discovery id cannot be empty")
        if not isinstance(analysis.id, str) or not analysis.id.strip():
            raise ValueError("Analysis id cannot be empty")
        if analysis.source_discovery_id != discovery.id:
            raise ValueError("Analysis result does not reference this discovery result")
        if (
            not isinstance(discovery.repository_name, str)
            or not isinstance(discovery.repository_url, str)
            or not isinstance(discovery.owner, str)
        ):
            raise TypeError("Discovery repository identity fields must be strings")
        if (
            not isinstance(analysis.repository_name, str)
            or not isinstance(analysis.repository_url, str)
        ):
            raise TypeError("Analysis repository identity fields must be strings")
        if discovery.source.source_type != GITHUB_REPOSITORY_SOURCE_TYPE:
            raise ValueError("GitHub evaluator requires a GitHub repository discovery")
        if not isinstance(discovery.is_public, bool):
            raise TypeError("Discovery public status must be a boolean")
        if not discovery.is_public:
            raise ValueError("GitHub evaluator requires a public repository")
        if (
            analysis.repository_name.casefold()
            != discovery.repository_name.casefold()
            or analysis.repository_url.rstrip("/").casefold()
            != discovery.repository_url.rstrip("/").casefold()
        ):
            raise ValueError("Analysis repository identity does not match discovery")
        if not isinstance(analysis.is_complete, bool):
            raise TypeError("Analysis completeness must be a boolean")
        if any(
            value is not None and not isinstance(value, str)
            for value in (discovery.license_name, discovery.license_spdx_id, discovery.pushed_at)
        ):
            raise TypeError("Discovery license and activity metadata must be strings or None")
        if (
            isinstance(analysis.source_bytes_inspected, bool)
            or not isinstance(analysis.source_bytes_inspected, int)
            or analysis.source_bytes_inspected < 0
        ):
            raise ValueError("Analysis source byte count cannot be negative")
        if not isinstance(analysis.detected_languages, tuple) or any(
            not isinstance(language, str) for language in analysis.detected_languages
        ):
            raise TypeError("Analysis detected_languages must be a tuple of strings")
        if not isinstance(analysis.important_files, tuple) or any(
            not isinstance(item, ProjectFile) for item in analysis.important_files
        ):
            raise TypeError("Analysis important_files must contain ProjectFile values")
        if not isinstance(analysis.dependency_manifests, tuple) or any(
            not isinstance(path, str) for path in analysis.dependency_manifests
        ):
            raise TypeError("Analysis dependency_manifests must be a tuple of strings")
        if not isinstance(analysis.detected_frameworks, tuple) or any(
            not isinstance(item, AnalysisObservation)
            for item in analysis.detected_frameworks
        ):
            raise TypeError("Analysis frameworks must contain AnalysisObservation values")
        if not isinstance(analysis.potential_capabilities, tuple) or any(
            not isinstance(item, AnalysisObservation)
            for item in analysis.potential_capabilities
        ):
            raise TypeError(
                "Analysis potential_capabilities must contain AnalysisObservation values"
            )
        if analysis.project_purpose is not None and not isinstance(
            analysis.project_purpose, AnalysisObservation
        ):
            raise TypeError("Analysis project_purpose must be an AnalysisObservation")

    def _capability_findings(
        self, source_id: str, analysis: SourceAnalysisResult
    ) -> list[EvaluationFinding]:
        capability_groups = {
            "coding assistance": ("code generation", "coding assistant", "coding assistance"),
            "repository intelligence": ("repository search", "repository intelligence", "repository indexing"),
            "terminal or computer control": ("terminal", "computer control", "shell access"),
            "browser automation": ("browser automation", "browser control"),
            "MCP integration": ("mcp", "model context protocol"),
            "Git/GitHub workflows": ("git workflow", "github workflow", "pull request automation"),
            "agent orchestration": ("agent orchestration", "multi-agent orchestration"),
            "task execution": ("task execution", "task runner"),
            "developer tooling": ("developer tooling", "development tool"),
        }
        result: list[EvaluationFinding] = []
        observations = analysis.potential_capabilities
        for capability, signals in capability_groups.items():
            matching = tuple(
                observation
                for observation in observations
                if any(signal in observation.statement.casefold() for signal in signals)
            )
            evidence = tuple(
                self._analysis_evidence(source_id, observation)
                for observation in matching
            )
            if matching:
                result.append(
                    EvaluationFinding(
                        source_id,
                        EvaluationCategory.CAPABILITY_FIT,
                        EvaluationStatus.SUPPORTED,
                        f"Analysis records a potential {capability} capability; this is an indication, not verification.",
                        evidence,
                    )
                )
            else:
                result.append(
                    EvaluationFinding(
                        source_id,
                        EvaluationCategory.CAPABILITY_FIT,
                        EvaluationStatus.UNKNOWN,
                        f"Available analysis does not establish whether the project provides {capability}.",
                    )
                )
        return result

    @staticmethod
    def _architecture_findings(
        source_id: str, analysis: SourceAnalysisResult
    ) -> list[EvaluationFinding]:
        findings: list[EvaluationFinding] = []
        python_files = tuple(
            item.path
            for item in analysis.important_files
            if item.path.casefold().endswith(".py")
        )
        python_evidence = tuple(
            EvaluationEvidence(
                source_id,
                "analysis",
                f"file:{path}",
                "Python source file path listed in analysis",
            )
            for path in python_files[:5]
        )
        if "Python" in analysis.detected_languages and python_evidence:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.ARCHITECTURE_COMPATIBILITY,
                    EvaluationStatus.SUPPORTED,
                    "Python source is present, which may ease implementation of a Python adapter; runtime compatibility is unverified.",
                    python_evidence,
                )
            )
        else:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.ARCHITECTURE_COMPATIBILITY,
                    EvaluationStatus.UNKNOWN,
                    "Available evidence does not establish compatibility with the Corporation's Python integration boundaries.",
                )
            )

        interface_evidence = tuple(
            EvaluationEvidence(
                source_id,
                "analysis",
                f"file:{item.path}",
                f"Analyzed file path categorized as {item.category}",
            )
            for item in analysis.important_files
            if item.path.casefold().endswith(
                (".mcp.json", "openapi.yaml", "openapi.yml", "openapi.json")
            )
        )
        if interface_evidence:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.ARCHITECTURE_COMPATIBILITY,
                    EvaluationStatus.SUPPORTED,
                    "An API/interface descriptor path is present; interface behavior has not been verified.",
                    interface_evidence,
                )
            )
        else:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.ARCHITECTURE_COMPATIBILITY,
                    EvaluationStatus.UNKNOWN,
                    "No inspected API, OpenAPI, or MCP interface descriptor establishes an integration boundary.",
                )
            )
        findings.append(
            EvaluationFinding(
                source_id,
                EvaluationCategory.ARCHITECTURE_COMPATIBILITY,
                EvaluationStatus.UNKNOWN,
                "Service/process model and overlap with Corporation-owned responsibilities have not been established.",
            )
        )
        return findings

    def _dependency_findings(
        self, source_id: str, analysis: SourceAnalysisResult
    ) -> list[EvaluationFinding]:
        if not analysis.dependency_manifests:
            findings = [
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.DEPENDENCIES,
                    EvaluationStatus.UNKNOWN,
                    "No dependency manifest was identified in the analyzed file inventory.",
                ),
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.DEPENDENCIES,
                    EvaluationStatus.UNKNOWN,
                    "Runtime, transitive, and external-service requirements are unknown.",
                ),
            ]
            return findings
        evidence = tuple(
            EvaluationEvidence(
                source_id,
                "analysis",
                f"file:{path}",
                "Dependency manifest path identified; dependencies were not resolved or installed.",
            )
            for path in analysis.dependency_manifests
        )
        findings = [
            EvaluationFinding(
                source_id,
                EvaluationCategory.DEPENDENCIES,
                EvaluationStatus.SUPPORTED,
                "Dependency manifest(s) are present; package requirements and versions are not verified.",
                evidence,
            ),
            EvaluationFinding(
                source_id,
                EvaluationCategory.DEPENDENCIES,
                EvaluationStatus.UNKNOWN,
                "Transitive dependencies, runtime requirements, and external services remain unknown.",
                evidence,
            ),
        ]
        if analysis.detected_frameworks:
            framework_evidence = tuple(
                self._analysis_evidence(source_id, observation)
                for observation in analysis.detected_frameworks
            )
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.DEPENDENCIES,
                    EvaluationStatus.SUPPORTED,
                    "Analyzed text contains framework/library mentions; these are not verified dependency declarations.",
                    framework_evidence,
                )
            )
        return findings

    @staticmethod
    def _license_finding(discovery: SourceDiscoveryResult) -> EvaluationFinding:
        license_values = tuple(
            value
            for value in (discovery.license_name, discovery.license_spdx_id)
            if value
        )
        if not license_values:
            return EvaluationFinding(
                discovery.id,
                EvaluationCategory.LICENSE,
                EvaluationStatus.UNKNOWN,
                "No license information was available in repository discovery; licensing requires review.",
            )
        evidence = tuple(
            EvaluationEvidence(
                discovery.id,
                "discovery",
                field_name,
                value,
            )
            for field_name, value in (
                ("license_name", discovery.license_name),
                ("license_spdx_id", discovery.license_spdx_id),
            )
            if value
        )
        status = (
            EvaluationStatus.SUPPORTED
            if discovery.license_spdx_id
            else EvaluationStatus.UNKNOWN
        )
        summary = (
            f"Repository metadata reports license {', '.join(license_values)}; this is not legal advice or a compatibility determination."
            if discovery.license_spdx_id
            else f"Repository metadata reports license name {discovery.license_name}, but no SPDX identifier or license text was reviewed."
        )
        return EvaluationFinding(
            discovery.id,
            EvaluationCategory.LICENSE,
            status,
            summary,
            evidence,
        )

    def _security_findings(
        self,
        source_id: str,
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
    ) -> list[EvaluationFinding]:
        inspected: list[tuple[str, str, str]] = []
        result: list[EvaluationFinding] = []
        for observation in self._documentary_observations(analysis):
            inspected.append(
                (
                    "analysis",
                    ", ".join(observation.evidence_paths) or "analysis observation",
                    observation.statement,
                )
            )
        if discovery.description:
            inspected.append(("discovery", "description", discovery.description))
        for key, pattern in self._SECURITY_SIGNALS:
            matches = tuple(
                EvaluationEvidence(source_id, source, reference, text[:240])
                for source, reference, text in inspected
                if pattern.search(text)
            )
            status = (
                SecurityObservationStatus.OBSERVED
                if matches
                else (
                    SecurityObservationStatus.NOT_OBSERVED
                    if analysis.is_complete
                    else SecurityObservationStatus.UNKNOWN
                )
            )
            evaluation_status = (
                EvaluationStatus.CONCERN
                if matches
                else EvaluationStatus.UNKNOWN
            )
            summary = (
                f"Inspected source descriptions mention {key}; the actual behavior has not been verified."
                if matches
                else f"{key.capitalize()} was not established from the bounded information inspected; this is not evidence of absence."
            )
            result.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.SECURITY,
                    evaluation_status,
                    summary,
                    matches,
                    status,
                )
            )
        return result

    @staticmethod
    def _maintenance_findings(
        source_id: str,
        discovery: SourceDiscoveryResult,
        analysis: SourceAnalysisResult,
    ) -> list[EvaluationFinding]:
        findings: list[EvaluationFinding] = []
        if discovery.latest_release is not None:
            release = discovery.latest_release
            value = f"tag={release.tag_name}, published_at={release.published_at or 'unavailable'}"
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.MAINTENANCE,
                    EvaluationStatus.SUPPORTED,
                    "A latest release is reported by repository discovery; this alone does not establish maintenance health.",
                    (
                        EvaluationEvidence(
                            source_id,
                            "discovery",
                            "latest_release",
                            value,
                        ),
                    ),
                )
            )
        else:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.MAINTENANCE,
                    EvaluationStatus.UNKNOWN,
                    "No latest release information was returned; release activity cannot be inferred.",
                )
            )
        if discovery.pushed_at:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.MAINTENANCE,
                    EvaluationStatus.SUPPORTED,
                    "Repository discovery reports a last-push timestamp; no activity rating is inferred.",
                    (
                        EvaluationEvidence(
                            source_id, "discovery", "pushed_at", discovery.pushed_at
                        ),
                    ),
                )
            )
        else:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.MAINTENANCE,
                    EvaluationStatus.UNKNOWN,
                    "No last-push timestamp is available.",
                )
            )
        documentation_paths = analysis.documentation_files
        if documentation_paths:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.MAINTENANCE,
                    EvaluationStatus.SUPPORTED,
                    "Documentation file paths are present in the bounded inventory; documentation quality/completeness is not assessed.",
                    tuple(
                        EvaluationEvidence(
                            source_id,
                            "analysis",
                            f"file:{path}",
                            "Documentation path identified in analysis",
                        )
                        for path in documentation_paths[:5]
                    ),
                )
            )
        else:
            findings.append(
                EvaluationFinding(
                    source_id,
                    EvaluationCategory.MAINTENANCE,
                    EvaluationStatus.UNKNOWN,
                    "No documentation file path was identified in the bounded inventory.",
                )
            )
        return findings

    @staticmethod
    def _complexity_findings(
        source_id: str, analysis: SourceAnalysisResult
    ) -> list[EvaluationFinding]:
        if analysis.important_files:
            inventory_evidence = tuple(
                EvaluationEvidence(
                    source_id,
                    "analysis",
                    f"file:{item.path}",
                    f"Analyzed inventory category: {item.category}",
                )
                for item in analysis.important_files[:5]
            )
            structure_finding = EvaluationFinding(
                source_id,
                EvaluationCategory.INTEGRATION_COMPLEXITY,
                EvaluationStatus.SUPPORTED,
                f"Analysis identified {len(analysis.important_files)} relevant file entries; this is a bounded inventory, not a full project-size estimate.",
                inventory_evidence,
            )
        else:
            structure_finding = EvaluationFinding(
                source_id,
                EvaluationCategory.INTEGRATION_COMPLEXITY,
                EvaluationStatus.UNKNOWN,
                "No relevant file inventory is available to describe structural integration effort.",
            )
        return [
            structure_finding,
            EvaluationFinding(
                source_id,
                EvaluationCategory.INTEGRATION_COMPLEXITY,
                EvaluationStatus.UNKNOWN,
                "Adapter effort, runtime requirements, and external service dependencies cannot be estimated from the available evidence.",
            ),
        ]

    @staticmethod
    def _integration_requirements(
        discovery: SourceDiscoveryResult, analysis: SourceAnalysisResult
    ) -> tuple[str, ...]:
        requirements = [
            "Verify the project's actual runtime and supported Python versions.",
            "Inspect documented/API interfaces and confirm an isolated adapter boundary.",
            "Review dependency versions, transitive dependencies, and external service requirements without installing them.",
            "Review security-sensitive behavior and credentials handling using a controlled process.",
            "Obtain a separate human decision and approval before any future integration work.",
        ]
        if not discovery.license_spdx_id:
            requirements.append("Clarify the applicable license through appropriate review.")
        if not analysis.is_complete:
            requirements.append("Complete or repeat bounded analysis before relying on these findings.")
        return tuple(requirements)

    @staticmethod
    def _analysis_evidence(
        source_id: str, observation: AnalysisObservation
    ) -> EvaluationEvidence:
        return EvaluationEvidence(
            source_id,
            "analysis",
            ", ".join(observation.evidence_paths) or "analysis observation",
            observation.statement,
        )

    @staticmethod
    def _documentary_observations(
        analysis: SourceAnalysisResult,
    ) -> tuple[AnalysisObservation, ...]:
        observations = list(analysis.detected_frameworks)
        observations.extend(analysis.potential_capabilities)
        if analysis.project_purpose is not None:
            observations.append(analysis.project_purpose)
        return tuple(observations)
