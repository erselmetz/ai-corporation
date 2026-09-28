import os
import subprocess
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.integrations import (
    AnalysisObservation,
    EvaluationCategory,
    EvaluationStatus,
    GitHubRepositoryEvaluator,
    IntegrationExecutionRecord,
    IntegrationProposal,
    IntegrationSource,
    SecurityObservationStatus,
    SourceAnalysisResult,
    SourceDiscoveryResult,
    SourceEvaluator,
)
from app.integrations.analysis import ProjectFile


def make_discovery(**overrides):
    values = {
        "id": "discovery-29",
        "source": IntegrationSource(
            "github_repository", "https://github.com/example/project"
        ),
        "discovered_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "owner": "example",
        "repository_name": "project",
        "repository_url": "https://github.com/example/project",
        "description": "A helper service that exposes a network API.",
        "default_branch": "main",
        "is_public": True,
        "language": "Python",
        "stars": 23,
        "forks": 4,
        "open_issues": 3,
        "license_name": "MIT License",
        "license_spdx_id": "MIT",
        "created_at": "2022-01-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
        "pushed_at": "2026-08-15T00:00:00Z",
        "latest_release": None,
        "readme_available": True,
        "readme_size_bytes": 100,
        "readme_excerpt": "# Project\nA helper service.",
    }
    values.update(overrides)
    return SourceDiscoveryResult(**values)


def make_analysis(**overrides):
    values = {
        "id": "analysis-29",
        "source_discovery_id": "discovery-29",
        "repository_url": "https://github.com/example/project",
        "repository_name": "project",
        "analyzed_at": datetime(2026, 9, 2, tzinfo=timezone.utc),
        "detected_languages": ("Python",),
        "top_level_directories": ("src", "tests"),
        "important_files": (
            ProjectFile("README.md", "documentation", 500),
            ProjectFile("pyproject.toml", "dependency_manifest", 120),
            ProjectFile("src/server.py", "source", 200),
            ProjectFile("openapi.yaml", "configuration", 100),
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
            "Available source information describes the project as: A code generation and repository search service.",
            ("README.md",),
        ),
        "potential_capabilities": (
            AnalysisObservation(
                "Documentation mentions potential code generation capability.",
                ("README.md",),
            ),
            AnalysisObservation(
                "Documentation mentions potential repository search capability.",
                ("README.md",),
            ),
            AnalysisObservation(
                "Documentation mentions potential network access and API client capability.",
                ("README.md",),
            ),
        ),
        "analysis_notes": (),
        "is_complete": True,
        "source_bytes_inspected": 820,
    }
    values.update(overrides)
    return SourceAnalysisResult(**values)


def findings_for(result, category):
    return tuple(finding for finding in result.findings if finding.category == category)


def test_evaluator_is_an_interface_and_github_is_its_concrete_adapter():
    evaluator = GitHubRepositoryEvaluator()
    assert isinstance(evaluator, SourceEvaluator)


def test_github_evaluation_has_linked_evidence_and_structured_decision_support():
    discovery = make_discovery()
    analysis = make_analysis()

    result = GitHubRepositoryEvaluator().evaluate(discovery, analysis)

    assert result.source_discovery_id == discovery.id
    assert result.findings
    assert result.key_strengths
    assert result.key_concerns
    assert result.unknowns
    assert result.integration_requirements
    assert result.evaluated_at.tzinfo is not None
    assert all(
        finding.source_discovery_id == discovery.id
        for finding in result.findings
    )
    assert all(
        evidence.source_discovery_id == discovery.id
        for finding in result.findings
        for evidence in finding.evidence
    )


def test_capability_fit_uses_task_28_evidence_and_does_not_assume_by_name():
    result = GitHubRepositoryEvaluator().evaluate(make_discovery(), make_analysis())
    capability_findings = findings_for(result, EvaluationCategory.CAPABILITY_FIT)
    code_generation = next(
        item for item in capability_findings if "coding assistance" in item.summary
    )
    terminal = next(
        item
        for item in capability_findings
        if "terminal or computer control" in item.summary
    )

    assert code_generation.status == EvaluationStatus.SUPPORTED
    assert code_generation.evidence[0].reference == "README.md"
    assert terminal.status == EvaluationStatus.UNKNOWN


def test_architecture_and_dependencies_report_only_available_facts():
    result = GitHubRepositoryEvaluator().evaluate(make_discovery(), make_analysis())
    architecture = findings_for(
        result, EvaluationCategory.ARCHITECTURE_COMPATIBILITY
    )
    dependencies = findings_for(result, EvaluationCategory.DEPENDENCIES)

    assert any(
        item.status == EvaluationStatus.SUPPORTED
        and "Python source" in item.summary
        for item in architecture
    )
    assert any(
        item.status == EvaluationStatus.SUPPORTED
        and "interface descriptor" in item.summary
        for item in architecture
    )
    assert any(
        item.status == EvaluationStatus.UNKNOWN
        and "Service/process model" in item.summary
        for item in architecture
    )
    manifest_finding = next(
        item
        for item in dependencies
        if item.status == EvaluationStatus.SUPPORTED
    )
    assert manifest_finding.evidence[0].reference == "file:pyproject.toml"
    assert any(item.status == EvaluationStatus.UNKNOWN for item in dependencies)
    assert any(
        "not verified dependency declarations" in item.summary
        for item in dependencies
    )


def test_license_findings_distinguish_reported_identifier_and_missing_license():
    evaluator = GitHubRepositoryEvaluator()
    known = evaluator.evaluate(make_discovery(), make_analysis())
    license_finding = findings_for(known, EvaluationCategory.LICENSE)[0]
    assert license_finding.status == EvaluationStatus.SUPPORTED
    assert {item.reference for item in license_finding.evidence} == {
        "license_name",
        "license_spdx_id",
    }
    assert "not legal advice" in license_finding.summary

    unknown = evaluator.evaluate(
        make_discovery(license_name=None, license_spdx_id=None),
        make_analysis(),
    )
    assert findings_for(unknown, EvaluationCategory.LICENSE)[0].status == (
        EvaluationStatus.UNKNOWN
    )


def test_license_name_without_identifier_remains_uncertain():
    result = GitHubRepositoryEvaluator().evaluate(
        make_discovery(license_spdx_id=None),
        make_analysis(),
    )
    finding = findings_for(result, EvaluationCategory.LICENSE)[0]
    assert finding.status == EvaluationStatus.UNKNOWN
    assert "no SPDX identifier" in finding.summary


def test_security_signals_are_evidence_scoped_and_absence_is_not_assurance():
    result = GitHubRepositoryEvaluator().evaluate(make_discovery(), make_analysis())
    security = findings_for(result, EvaluationCategory.SECURITY)
    network = next(
        item for item in security if "network access" in item.summary.casefold()
    )
    shell = next(
        item
        for item in security
        if "shell or system access" in item.summary.casefold()
    )

    assert network.security_status == SecurityObservationStatus.OBSERVED
    assert network.status == EvaluationStatus.CONCERN
    assert network.evidence
    assert shell.security_status == SecurityObservationStatus.NOT_OBSERVED
    assert shell.status == EvaluationStatus.UNKNOWN
    assert "not evidence of absence" in shell.summary


def test_maintenance_and_complexity_do_not_invent_activity_or_estimates():
    discovery = make_discovery(
        latest_release=None,
        pushed_at=None,
    )
    analysis = make_analysis()
    result = GitHubRepositoryEvaluator().evaluate(discovery, analysis)
    maintenance = findings_for(result, EvaluationCategory.MAINTENANCE)
    complexity = findings_for(result, EvaluationCategory.INTEGRATION_COMPLEXITY)

    assert sum(item.status == EvaluationStatus.UNKNOWN for item in maintenance) == 2
    assert any(
        item.status == EvaluationStatus.SUPPORTED
        and "Documentation file paths" in item.summary
        for item in maintenance
    )
    assert any("bounded inventory" in item.summary for item in complexity)
    assert any("cannot be estimated" in item.summary for item in complexity)


def test_incomplete_analysis_marks_result_partial_and_adds_requirement():
    result = GitHubRepositoryEvaluator().evaluate(
        make_discovery(),
        make_analysis(is_complete=False, analysis_notes=("tree truncated",)),
    )
    assert result.complete is False
    assert any("Complete or repeat bounded analysis" in item for item in result.integration_requirements)
    assert any(
        item.security_status == SecurityObservationStatus.UNKNOWN
        for item in findings_for(result, EvaluationCategory.SECURITY)
    )


def test_missing_evidence_produces_unknowns_instead_of_inference():
    result = GitHubRepositoryEvaluator().evaluate(
        make_discovery(
            license_name=None,
            license_spdx_id=None,
            latest_release=None,
            pushed_at=None,
        ),
        make_analysis(
            detected_languages=(),
            important_files=(),
            dependency_manifests=(),
            documentation_files=(),
            detected_frameworks=(),
            potential_capabilities=(),
            project_purpose=None,
        ),
    )
    assert any(item.status == EvaluationStatus.UNKNOWN for item in result.findings)
    assert not result.key_strengths


def test_incomplete_input_and_mismatched_discovery_are_rejected():
    evaluator = GitHubRepositoryEvaluator()
    with pytest.raises(TypeError, match="SourceDiscoveryResult"):
        evaluator.evaluate(object(), make_analysis())
    with pytest.raises(TypeError, match="SourceAnalysisResult"):
        evaluator.evaluate(make_discovery(), object())
    with pytest.raises(ValueError, match="does not reference"):
        evaluator.evaluate(
            make_discovery(),
            make_analysis(source_discovery_id="different"),
        )
    with pytest.raises(ValueError, match="identity"):
        evaluator.evaluate(
            make_discovery(),
            make_analysis(repository_name="other"),
        )
    with pytest.raises(TypeError, match="potential_capabilities"):
        evaluator.evaluate(
            make_discovery(),
            make_analysis(potential_capabilities=("untyped observation",)),
        )


def test_evaluation_does_not_create_or_transition_proposals():
    proposal = IntegrationProposal(
        "proposal-29",
        make_discovery().source,
        "Evaluate as possible external capability",
    )
    original_status = proposal.status
    evaluator = GitHubRepositoryEvaluator()

    first = evaluator.evaluate(make_discovery(), make_analysis())
    second = evaluator.evaluate(make_discovery(), make_analysis())

    assert proposal.status == original_status
    assert proposal.status.value == "discovered"
    assert not isinstance(first, (IntegrationProposal, IntegrationExecutionRecord))
    assert first.findings == second.findings
    assert first.id == second.id
    assert first.evaluated_at != second.evaluated_at


def test_evaluation_never_runs_commands_or_changes_local_files(tmp_path):
    marker = tmp_path / "evaluation-marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    evaluator = GitHubRepositoryEvaluator()
    with (
        patch.object(subprocess, "run", side_effect=AssertionError("no shell")),
        patch.object(subprocess, "Popen", side_effect=AssertionError("no process")),
        patch.object(os, "system", side_effect=AssertionError("no shell")),
        patch.object(os, "popen", side_effect=AssertionError("no process")),
        patch(
            "app.integrations.discovery.httpx.get",
            side_effect=AssertionError("evaluation performs no network requests"),
        ),
        patch(
            "app.integrations.analysis.httpx.stream",
            side_effect=AssertionError("evaluation performs no network requests"),
        ),
    ):
        evaluator.evaluate(make_discovery(), make_analysis())
    assert marker.read_text(encoding="utf-8") == "unchanged"
