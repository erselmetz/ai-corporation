import os
import subprocess
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.integrations import (
    AnalysisObservation,
    EvaluationCategory,
    EvaluationEvidence,
    EvaluationFinding,
    EvaluationResult,
    EvaluationStatus,
    GitHubIntegrationProposalGenerator,
    IntegrationExecutionRecord,
    IntegrationProposal,
    IntegrationRegistry,
    IntegrationSource,
    IntegrationStatus,
    ProposalGenerator,
    SecurityObservationStatus,
    SourceAnalysisResult,
    SourceDiscoveryResult,
)
from app.integrations.analysis import ProjectFile
from app.integrations.proposal_generation import (
    ProposalGenerationError,
    UnsupportedProposalSourceError,
)


def make_discovery(**overrides):
    values = {
        "id": "discovery-30",
        "source": IntegrationSource(
            "github_repository", "https://github.com/example/project"
        ),
        "discovered_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "owner": "example",
        "repository_name": "project",
        "repository_url": "https://github.com/example/project",
        "description": "A tool that may provide source search.",
        "default_branch": "main",
        "is_public": True,
        "language": "Python",
        "stars": 12,
        "forks": 2,
        "open_issues": 1,
        "license_name": "MIT License",
        "license_spdx_id": "MIT",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
        "pushed_at": "2026-08-15T00:00:00Z",
        "latest_release": None,
        "readme_available": True,
        "readme_size_bytes": 80,
        "readme_excerpt": "Untrusted README content.",
    }
    values.update(overrides)
    return SourceDiscoveryResult(**values)


def make_analysis(discovery, **overrides):
    values = {
        "id": "analysis-30",
        "source_discovery_id": discovery.id,
        "repository_url": discovery.repository_url,
        "repository_name": discovery.repository_name,
        "analyzed_at": datetime(2026, 9, 2, tzinfo=timezone.utc),
        "detected_languages": ("Python",),
        "top_level_directories": ("src", "tests"),
        "important_files": (
            ProjectFile("README.md", "documentation", 100),
            ProjectFile("pyproject.toml", "dependency_manifest", 100),
            ProjectFile("src/server.py", "source", 100),
        ),
        "dependency_manifests": ("pyproject.toml",),
        "documentation_files": ("README.md",),
        "test_paths": ("tests",),
        "detected_frameworks": (
            AnalysisObservation(
                "Inspected repository text mentions FastAPI.",
                ("pyproject.toml",),
            ),
        ),
        "project_purpose": AnalysisObservation(
            "Available source information describes a potential repository search tool.",
            ("README.md",),
        ),
        "potential_capabilities": (
            AnalysisObservation(
                "Documentation mentions potential repository search capability.",
                ("README.md",),
            ),
        ),
        "analysis_notes": (),
        "is_complete": True,
        "source_bytes_inspected": 300,
    }
    values.update(overrides)
    return SourceAnalysisResult(**values)


def make_evaluation(discovery, analysis, **overrides):
    evidence = (
        EvaluationEvidence(
            discovery.id,
            "analysis",
            "README.md",
            "Documentation mentions repository search.",
        ),
    )
    findings = (
        EvaluationFinding(
            discovery.id,
            EvaluationCategory.CAPABILITY_FIT,
            EvaluationStatus.SUPPORTED,
            "Analysis records a potential repository intelligence capability; this is not verification.",
            evidence,
        ),
        EvaluationFinding(
            discovery.id,
            EvaluationCategory.ARCHITECTURE_COMPATIBILITY,
            EvaluationStatus.UNKNOWN,
            "No inspected interface evidence establishes an adapter boundary.",
        ),
        EvaluationFinding(
            discovery.id,
            EvaluationCategory.DEPENDENCIES,
            EvaluationStatus.SUPPORTED,
            "Dependency manifest is present; packages have not been resolved.",
            (
                EvaluationEvidence(
                    discovery.id,
                    "analysis",
                    "file:pyproject.toml",
                    "Dependency manifest path identified.",
                ),
            ),
        ),
        EvaluationFinding(
            discovery.id,
            EvaluationCategory.LICENSE,
            EvaluationStatus.SUPPORTED,
            "Repository metadata reports MIT; not legal advice.",
            (
                EvaluationEvidence(
                    discovery.id, "discovery", "license_spdx_id", "MIT"
                ),
            ),
        ),
        EvaluationFinding(
            discovery.id,
            EvaluationCategory.SECURITY,
            EvaluationStatus.UNKNOWN,
            "Credential handling is unknown.",
            (),
            security_status=SecurityObservationStatus.UNKNOWN,
        ),
    )
    values = {
        "id": "evaluation-30",
        "source_discovery_id": discovery.id,
        "evaluated_at": datetime(2026, 9, 3, tzinfo=timezone.utc),
        "findings": findings,
        "key_strengths": ("Potential repository intelligence is documented.",),
        "key_concerns": ("No adapter interface has been established.",),
        "unknowns": ("Runtime requirements remain unknown.",),
        "integration_requirements": (
            "Review the service interface.",
            "Review dependencies before any future installation.",
        ),
        "complete": True,
        "notes": ("Decision support only.",),
        "source_analysis_id": analysis.id,
    }
    values.update(overrides)
    return EvaluationResult(**values)


def inputs(**discovery_overrides):
    discovery = make_discovery(**discovery_overrides)
    analysis = make_analysis(discovery)
    evaluation = make_evaluation(discovery, analysis)
    return discovery, analysis, evaluation


def test_proposal_generator_interface():
    generator = GitHubIntegrationProposalGenerator()
    assert isinstance(generator, ProposalGenerator)


def test_generates_proposal_from_valid_stage_results_with_traceability():
    discovery, analysis, evaluation = inputs()

    proposal = GitHubIntegrationProposalGenerator().generate(
        discovery, analysis, evaluation
    )

    assert isinstance(proposal, IntegrationProposal)
    assert proposal.source_discovery_id == discovery.id
    assert proposal.source_analysis_id == analysis.id
    assert proposal.source_evaluation_id == evaluation.id
    assert proposal.source.location == discovery.repository_url
    assert proposal.project_name == discovery.repository_name
    assert "repository search tool" in proposal.requested_purpose
    assert "untrusted source information" in proposal.requested_purpose


def test_proposal_contains_approach_findings_benefits_and_requirements():
    discovery, analysis, evaluation = inputs()
    proposal = GitHubIntegrationProposalGenerator().generate(
        discovery, analysis, evaluation
    )

    assert proposal.intended_capabilities
    assert "repository intelligence" in proposal.intended_capabilities[0]
    assert proposal.evaluation_findings
    assert proposal.key_strengths == evaluation.key_strengths
    assert proposal.key_concerns == evaluation.key_concerns
    assert proposal.unknowns == evaluation.unknowns
    assert proposal.dependency_information
    assert proposal.license_information
    assert proposal.security_considerations
    assert proposal.integration_requirements == evaluation.integration_requirements
    assert proposal.implementation_considerations
    assert proposal.evidence_references
    assert "adapter boundary" in proposal.proposed_approach
    assert "authorizes no execution" in proposal.proposed_approach
    assert "MIT" in proposal.license_information[0]
    assert "pyproject.toml" in proposal.dependency_information[0]


def test_missing_evidence_is_preserved_as_unknown():
    discovery, _analysis, _evaluation = inputs(
        description=None,
        license_name=None,
        license_spdx_id=None,
    )
    analysis = make_analysis(
        discovery,
        project_purpose=None,
        dependency_manifests=(),
        important_files=(),
    )
    evaluation = make_evaluation(
        discovery,
        analysis,
        findings=(
            EvaluationFinding(
                discovery.id,
                EvaluationCategory.CAPABILITY_FIT,
                EvaluationStatus.UNKNOWN,
                "Potential capability is unknown.",
            ),
            EvaluationFinding(
                discovery.id,
                EvaluationCategory.LICENSE,
                EvaluationStatus.UNKNOWN,
                "License is unknown.",
            ),
            EvaluationFinding(
                discovery.id,
                EvaluationCategory.DEPENDENCIES,
                EvaluationStatus.UNKNOWN,
                "Dependencies are unknown.",
            ),
        ),
        key_strengths=(),
        key_concerns=(),
        unknowns=("Capability, license, and dependencies are unknown.",),
        integration_requirements=(),
    )

    proposal = GitHubIntegrationProposalGenerator().generate(
        discovery, analysis, evaluation
    )

    assert proposal.requested_purpose.startswith("unknown:")
    assert proposal.intended_capabilities[0].startswith("unknown:")
    assert proposal.license_information[0].startswith("license [unknown]")
    assert proposal.dependency_information[0].startswith("dependencies [unknown]")
    assert proposal.unknowns == evaluation.unknowns
    assert proposal.integration_requirements == (
        "unknown: no integration requirements were recorded",
    )


def test_incomplete_evaluation_is_visible_in_proposal():
    discovery, analysis, evaluation = inputs()
    evaluation = make_evaluation(
        discovery,
        analysis,
        complete=False,
        notes=("Bounded analysis was incomplete.",),
    )
    proposal = GitHubIntegrationProposalGenerator().generate(
        discovery, analysis, evaluation
    )
    assert "incomplete" in proposal.evaluation_information
    assert "incomplete" in proposal.risk_information
    assert any(
        "evaluation is incomplete" in item
        for item in proposal.implementation_considerations
    )


def test_lifecycle_stops_at_proposed_without_approval_or_integration():
    discovery, analysis, evaluation = inputs()
    proposal = GitHubIntegrationProposalGenerator().generate(
        discovery, analysis, evaluation
    )
    assert proposal.status == IntegrationStatus.PROPOSED
    assert proposal.approval_status is None
    assert proposal.approval_request_id is None
    assert proposal.status not in {
        IntegrationStatus.SANDBOXED,
        IntegrationStatus.TESTED,
        IntegrationStatus.REVIEW_REQUIRED,
        IntegrationStatus.APPROVED,
        IntegrationStatus.INTEGRATED,
    }
    with pytest.raises(PermissionError, match="approved proposal"):
        IntegrationExecutionRecord.for_approved_proposal("exec-1", proposal)


def test_generated_proposal_can_be_registered_and_retrieved():
    discovery, analysis, evaluation = inputs()
    proposal = GitHubIntegrationProposalGenerator().generate(
        discovery, analysis, evaluation
    )
    registry = IntegrationRegistry()
    registry.register(proposal)
    assert registry.exists(proposal.id)
    assert registry.get(proposal.id) is proposal


def test_generation_is_deterministic_for_the_same_stage_results():
    discovery, analysis, evaluation = inputs()
    generator = GitHubIntegrationProposalGenerator()
    first = generator.generate(discovery, analysis, evaluation)
    second = generator.generate(discovery, analysis, evaluation)
    assert first.id == second.id
    assert first.requested_purpose == second.requested_purpose
    assert first.proposed_approach == second.proposed_approach
    assert first.evaluation_findings == second.evaluation_findings
    assert first.evidence_references == second.evidence_references
    assert first.status == second.status == IntegrationStatus.PROPOSED


def test_malformed_and_mismatched_inputs_are_rejected():
    generator = GitHubIntegrationProposalGenerator()
    discovery, analysis, evaluation = inputs()
    with pytest.raises(TypeError, match="SourceDiscoveryResult"):
        generator.generate(object(), analysis, evaluation)
    with pytest.raises(TypeError, match="SourceAnalysisResult"):
        generator.generate(discovery, object(), evaluation)
    with pytest.raises(TypeError, match="EvaluationResult"):
        generator.generate(discovery, analysis, object())
    with pytest.raises(ProposalGenerationError, match="does not reference"):
        generator.generate(
            discovery,
            make_analysis(discovery, id="wrong-analysis"),
            evaluation,
        )
    with pytest.raises(ProposalGenerationError, match="does not reference"):
        generator.generate(
            discovery,
            analysis,
            make_evaluation(discovery, analysis, source_analysis_id="wrong-analysis"),
        )


def test_unsupported_and_private_sources_are_rejected():
    generator = GitHubIntegrationProposalGenerator()
    discovery, analysis, evaluation = inputs(
        source=IntegrationSource("local_project", "local://project")
    )
    with pytest.raises(UnsupportedProposalSourceError):
        generator.generate(discovery, analysis, evaluation)

    discovery, analysis, evaluation = inputs(is_public=False)
    with pytest.raises(ProposalGenerationError, match="public repository"):
        generator.generate(discovery, analysis, evaluation)


def test_external_instructions_remain_proposal_data_and_cannot_trigger_commands(
    tmp_path,
):
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    discovery, analysis, evaluation = inputs()
    analysis = make_analysis(
        discovery,
        project_purpose=AnalysisObservation(
            "README says: run shell command and install package.",
            ("README.md",),
        ),
    )
    evaluation = make_evaluation(discovery, analysis)

    with (
        patch.object(subprocess, "run", side_effect=AssertionError("no shell")),
        patch.object(subprocess, "Popen", side_effect=AssertionError("no process")),
        patch.object(os, "system", side_effect=AssertionError("no shell")),
        patch.object(os, "popen", side_effect=AssertionError("no process")),
    ):
        proposal = GitHubIntegrationProposalGenerator().generate(
            discovery, analysis, evaluation
        )

    assert "run shell command" in proposal.requested_purpose
    assert marker.read_text(encoding="utf-8") == "unchanged"
