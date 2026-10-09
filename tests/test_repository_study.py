import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api import AuthenticatedPrincipal, create_app
from app.application.services.github_inspection import (
    GitHubRepositoryInspectionService,
    GitHubRepositoryScope,
    GitHubRepositoryScopeDenied,
)
from app.application.services.owned_chat import ChatNotFound
from app.application.services.repository_study import (
    RepositoryStudyDecision,
    RepositoryStudyService,
)
from app.conversations import ConversationStatus
from app.integrations import (
    AnalysisObservation,
    GitHubIntegrationProposalGenerator,
    GitHubRepositoryEvaluator,
    IntegrationSource,
    ProjectFile,
    SourceAnalysisResult,
    SourceDiscovery,
    SourceDiscoveryResult,
)


class FakeDiscovery(SourceDiscovery):
    def __init__(self, result):
        self.result = result
        self.sources = []

    def discover(self, source):
        self.sources.append(source)
        return self.result


def discovery_result():
    return SourceDiscoveryResult(
        id="discovery-121",
        source=IntegrationSource(
            "github_repository", "https://github.com/example/project"
        ),
        discovered_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
        owner="example",
        repository_name="project",
        repository_url="https://github.com/example/project",
        description="A small repository search service.",
        default_branch="main",
        is_public=True,
        language="Python",
        stars=12,
        forks=2,
        open_issues=1,
        license_name="MIT License",
        license_spdx_id="MIT",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2026-10-01T00:00:00Z",
        pushed_at="2026-10-08T00:00:00Z",
        latest_release=None,
        readme_available=True,
        readme_size_bytes=80,
        readme_excerpt="A source discovery library for Python.",
    )


def analysis_result(*, complete=True, revision_sha="a" * 40):
    return SourceAnalysisResult(
        id="analysis-121",
        source_discovery_id="discovery-121",
        repository_url="https://github.com/example/project",
        repository_name="project",
        analyzed_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
        detected_languages=("Python",),
        top_level_directories=("src", "tests"),
        important_files=(
            ProjectFile("README.md", "documentation", 80),
            ProjectFile("pyproject.toml", "dependency_manifest", 90),
            ProjectFile("src/search.py", "source", 120),
        ),
        dependency_manifests=("pyproject.toml",),
        documentation_files=("README.md",),
        test_paths=("tests",),
        detected_frameworks=(
            AnalysisObservation(
                "Inspected repository text mentions FastAPI.",
                ("pyproject.toml",),
            ),
        ),
        project_purpose=AnalysisObservation(
            "Available source information describes a source discovery library.",
            ("README.md",),
        ),
        potential_capabilities=(
            AnalysisObservation(
                "Documentation mentions repository search.",
                ("README.md",),
            ),
        ),
        analysis_notes=() if complete else ("Some files were not inspected.",),
        is_complete=complete,
        source_bytes_inspected=290,
        revision_sha=revision_sha,
    )


class FakeAnalyzer:
    def __init__(self, result):
        self.result = result
        self.discoveries = []

    def analyze_pinned(self, discovery):
        self.discoveries.append(discovery)
        return self.result


def make_study_service(*, complete=True, revision_sha="a" * 40, scopes=None):
    discovery = FakeDiscovery(discovery_result())
    inspection = GitHubRepositoryInspectionService(
        frozenset(
            {GitHubRepositoryScope("example", "project")}
            if scopes is None
            else scopes
        ),
        discovery,
    )
    analyzer = FakeAnalyzer(
        analysis_result(complete=complete, revision_sha=revision_sha)
    )
    service = RepositoryStudyService(
        inspection,
        analyzer=analyzer,
        evaluator=GitHubRepositoryEvaluator(),
        proposal_generator=GitHubIntegrationProposalGenerator(),
    )
    return service, discovery, analyzer


def test_repository_study_reuses_evaluation_and_links_evidence_to_pinned_commit():
    service, discovery, analyzer = make_study_service()

    report = service.study(
        "Assess whether search can be adapted", "EXAMPLE", "PROJECT"
    )

    assert report.decision is RepositoryStudyDecision.PROPOSAL_FOR_HUMAN_REVIEW
    assert report.objective == "Assess whether search can be adapted"
    assert report.analysis.revision_sha == "a" * 40
    assert report.proposal.status.value == "proposed"
    assert analyzer.discoveries == [discovery.result]
    assert discovery.sources[0].location == "https://github.com/example/project"
    assert any(
        citation.url
        == "https://github.com/example/project/blob/"
        + "a" * 40
        + "/README.md"
        for citation in report.citations
    )
    assert any("untrusted" in limitation for limitation in report.limitations)


def test_incomplete_repository_analysis_requests_more_information():
    service, _, _ = make_study_service(complete=False)

    report = service.study("Assess an integration", "example", "project")

    assert report.decision is RepositoryStudyDecision.REQUEST_MORE_INFORMATION
    assert not report.analysis.is_complete


def test_repository_allowlist_is_checked_before_discovery_or_analysis():
    service, discovery, analyzer = make_study_service(scopes=frozenset())

    with pytest.raises(GitHubRepositoryScopeDenied):
        service.study("Assess an integration", "example", "project")

    assert discovery.sources == []
    assert analyzer.discoveries == []


@pytest.mark.parametrize("objective", ["", "x" * 1025, "\ud800"])
def test_study_rejects_blank_oversized_or_invalid_unicode_objective(objective):
    service, _, _ = make_study_service()

    with pytest.raises(ValueError):
        service.study(objective, "example", "project")


class StudyAuthenticationBackend:
    def authenticate(self, request: Request):
        permissions = {
            "both": frozenset({"chat:send", "github:read"}),
            "chat-only": frozenset({"chat:send"}),
            "github-only": frozenset({"github:read"}),
        }.get(request.headers.get("Authorization", ""))
        return (
            None
            if permissions is None
            else AuthenticatedPrincipal("study-owner", permissions)
        )


class FakeOwnedChat:
    def __init__(self, *, open_conversation=True):
        self.open_conversation = open_conversation
        self.calls = []

    def get(self, owner, identifier):
        raise AssertionError("Repository study must not read conversation messages")

    def get_status(self, owner, identifier):
        self.calls.append((owner, identifier))
        if identifier != "owned-conversation" or owner != "study-owner":
            raise ChatNotFound("Conversation not found")
        return (
            ConversationStatus.OPEN
            if self.open_conversation
            else ConversationStatus.CLOSED
        )


class FakeApplicationService:
    def __init__(self, owned_chat):
        self.chat = owned_chat

    def owned_chat(self):
        return self.chat


def create_study_api(study_service, *, open_conversation=True):
    owned_chat = FakeOwnedChat(open_conversation=open_conversation)
    application = create_app(
        application_service=FakeApplicationService(owned_chat),
        authentication_backend=StudyAuthenticationBackend(),
        repository_study_service=study_service,
    )
    return application, owned_chat


def test_chat_repository_study_requires_both_permissions_and_owned_open_chat():
    study_service, _, _ = make_study_service()
    application, owned_chat = create_study_api(study_service)
    payload = {
        "objective": "Assess repository search",
        "owner": "example",
        "repository": "project",
    }

    with TestClient(application) as client:
        unauthenticated = client.post(
            "/api/chat/conversations/owned-conversation/repository-studies",
            json=payload,
        )
        chat_only = client.post(
            "/api/chat/conversations/owned-conversation/repository-studies",
            headers={"Authorization": "chat-only"},
            json=payload,
        )
        github_only = client.post(
            "/api/chat/conversations/owned-conversation/repository-studies",
            headers={"Authorization": "github-only"},
            json=payload,
        )
        allowed = client.post(
            "/api/chat/conversations/owned-conversation/repository-studies",
            headers={"Authorization": "both"},
            json=payload,
        )

    assert unauthenticated.status_code == 401
    assert chat_only.status_code == 403
    assert github_only.status_code == 403
    assert allowed.status_code == 200
    result = allowed.json()
    assert result["decision"] == "proposal_for_human_review"
    assert result["repository"]["revision_sha"] == "a" * 40
    assert result["repository"]["revision_url"].endswith("/tree/" + "a" * 40)
    assert result["proposal"]["status"] == "proposed"
    assert any(item["url"].endswith("/blob/" + "a" * 40 + "/README.md")
               for item in result["citations"])
    assert owned_chat.calls == [("study-owner", "owned-conversation")]


@pytest.mark.parametrize("objective", ["   ", "é" * 513, "\ud800"])
def test_chat_repository_study_rejects_invalid_or_oversized_utf8_objective(objective):
    study_service, discovery, analyzer = make_study_service()
    application, _ = create_study_api(study_service)

    with TestClient(application) as client:
        response = client.post(
            "/api/chat/conversations/owned-conversation/repository-studies",
            headers={"Authorization": "both", "Content-Type": "application/json"},
            content=json.dumps(
                {
                    "objective": objective,
                    "owner": "example",
                    "repository": "project",
                },
                ensure_ascii=True,
            ),
        )

    assert response.status_code == 422
    assert discovery.sources == []
    assert analyzer.discoveries == []


def test_repository_study_rejects_closed_or_unowned_conversation():
    study_service, discovery, analyzer = make_study_service()
    closed_app, _ = create_study_api(study_service, open_conversation=False)
    unowned_app, _ = create_study_api(study_service)
    payload = {
        "objective": "Assess repository search",
        "owner": "example",
        "repository": "project",
    }

    with TestClient(closed_app) as client:
        closed = client.post(
            "/api/chat/conversations/owned-conversation/repository-studies",
            headers={"Authorization": "both"},
            json=payload,
        )
    with TestClient(unowned_app) as client:
        unowned = client.post(
            "/api/chat/conversations/not-owned/repository-studies",
            headers={"Authorization": "both"},
            json=payload,
        )

    assert closed.status_code == 409
    assert unowned.status_code == 404
    assert discovery.sources == []
    assert analyzer.discoveries == []
