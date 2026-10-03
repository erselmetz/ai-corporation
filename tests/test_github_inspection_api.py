from datetime import datetime, timezone
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api import AuthenticatedPrincipal, create_app
from app.application import (
    CorporationApplicationService,
    GitHubInspectionRateLimited,
    GitHubInspectionRequestError,
    GitHubInspectionUnavailable,
    GitHubRepositoryInspectionService,
    GitHubRepositoryNotFound,
    GitHubRepositoryScope,
    GitHubRepositoryScopeDenied,
)
from app.integrations import (
    GITHUB_REPOSITORY_SOURCE_TYPE,
    GitHubRateLimitError,
    IntegrationSource,
    LatestRelease,
    PrivateRepositoryError,
    RepositoryNotFoundError,
    SourceDiscovery,
    SourceDiscoveryAPIError,
    SourceDiscoveryError,
    SourceDiscoveryResult,
)
from app.orchestrator import Orchestrator


class GitHubTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "github-reader": frozenset({"github:read"}),
            "task-reader": frozenset({"task:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(
            identity="github-test-user",
            permissions=permissions,
        )


class FakeSourceDiscovery(SourceDiscovery):
    def __init__(self, outcome: SourceDiscoveryResult | SourceDiscoveryError) -> None:
        self.outcome = outcome
        self.sources: list[IntegrationSource] = []

    def discover(self, source: IntegrationSource) -> SourceDiscoveryResult:
        self.sources.append(source)
        if isinstance(self.outcome, SourceDiscoveryError):
            raise self.outcome
        return self.outcome


def discovery_result() -> SourceDiscoveryResult:
    return SourceDiscoveryResult(
        id="discovery-1",
        source=IntegrationSource(
            GITHUB_REPOSITORY_SOURCE_TYPE,
            "https://github.com/example/project",
        ),
        discovered_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
        owner="example",
        repository_name="project",
        repository_url="https://github.com/example/project",
        description="Example repository",
        default_branch="main",
        is_public=True,
        language="Python",
        stars=12,
        forks=3,
        open_issues=2,
        license_name="MIT License",
        license_spdx_id="MIT",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2026-10-01T00:00:00Z",
        pushed_at="2026-10-02T00:00:00Z",
        latest_release=LatestRelease(
            tag_name="v1.0",
            name="Version 1.0",
            published_at="2026-10-01T00:00:00Z",
            html_url="https://github.com/example/project/releases/tag/v1.0",
        ),
        readme_available=True,
        readme_size_bytes=45,
        readme_excerpt="UNTRUSTED README CONTENT",
    )


def create_github_api(
    discovery: SourceDiscovery,
    scopes: frozenset[GitHubRepositoryScope] | None = None,
):
    service = GitHubRepositoryInspectionService(
        frozenset() if scopes is None else scopes,
        discovery,
    )
    application = create_app(
        application_service=CorporationApplicationService(
            MagicMock(spec=Orchestrator)
        ),
        authentication_backend=GitHubTestAuthenticationBackend(),
        github_repository_inspection_service=service,
    )
    return application, service


def test_repository_scope_normalizes_identifiers_and_is_immutable() -> None:
    scope = GitHubRepositoryScope("Example", "Project")

    assert scope == GitHubRepositoryScope("example", "project")
    assert scope.url == "https://github.com/example/project"
    with pytest.raises(AttributeError):
        scope.owner = "other"


def test_github_read_permission_and_repository_scope_gate_inspection() -> None:
    discovery = FakeSourceDiscovery(discovery_result())
    application, _ = create_github_api(
        discovery,
        frozenset({GitHubRepositoryScope("example", "project")}),
    )

    with TestClient(application) as client:
        unauthenticated = client.get("/api/github/repositories/example/project")
        forbidden = client.get(
            "/api/github/repositories/example/project",
            headers={"Authorization": "task-reader"},
        )
        response = client.get(
            "/api/github/repositories/EXAMPLE/PROJECT",
            headers={"Authorization": "github-reader"},
        )
        post_response = client.post(
            "/api/github/repositories/example/project",
            headers={"Authorization": "github-reader"},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json() == {
        "owner": "example",
        "repository_name": "project",
        "repository_url": "https://github.com/example/project",
        "discovered_at": "2026-10-03T00:00:00Z",
        "description": "Example repository",
        "default_branch": "main",
        "language": "Python",
        "stars": 12,
        "forks": 3,
        "open_issues": 2,
        "license_name": "MIT License",
        "license_spdx_id": "MIT",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
        "pushed_at": "2026-10-02T00:00:00Z",
        "latest_release": {
            "tag_name": "v1.0",
            "name": "Version 1.0",
            "published_at": "2026-10-01T00:00:00Z",
            "html_url": "https://github.com/example/project/releases/tag/v1.0",
        },
        "readme_available": True,
        "readme_size_bytes": 45,
    }
    assert "UNTRUSTED README CONTENT" not in response.text
    assert post_response.status_code == 405
    assert len(discovery.sources) == 1
    assert discovery.sources[0].location == "https://github.com/example/project"
    assert set(application.openapi()["paths"]["/api/github/repositories/{owner}/{repository}"]) == {
        "get"
    }


def test_out_of_scope_repository_is_hidden_and_never_fetched() -> None:
    discovery = FakeSourceDiscovery(discovery_result())
    application, _ = create_github_api(
        discovery,
        frozenset({GitHubRepositoryScope("example", "approved")}),
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/github/repositories/example/project",
            headers={"Authorization": "github-reader"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "GitHub repository was not found or is not in scope"
    }
    assert discovery.sources == []


def test_invalid_or_unconfigured_repository_scope_fails_closed() -> None:
    discovery = FakeSourceDiscovery(discovery_result())
    application, _ = create_github_api(discovery)

    with TestClient(application) as client:
        invalid = client.get(
            "/api/github/repositories/example/bad%20name",
            headers={"Authorization": "github-reader"},
        )
        unconfigured = client.get(
            "/api/github/repositories/example/project",
            headers={"Authorization": "github-reader"},
        )

    assert invalid.status_code == 422
    assert unconfigured.status_code == 404
    assert discovery.sources == []


@pytest.mark.parametrize(
    ("discovery_error", "expected_status", "detail"),
    [
        (
            RepositoryNotFoundError("not found"),
            404,
            "GitHub repository was not found or is not in scope",
        ),
        (
            PrivateRepositoryError("private"),
            404,
            "GitHub repository was not found or is not in scope",
        ),
        (
            GitHubRateLimitError("rate limited"),
            429,
            "GitHub API rate limit exceeded",
        ),
        (
            SourceDiscoveryAPIError(500, "token=secret"),
            503,
            "GitHub repository inspection is unavailable",
        ),
    ],
)
def test_github_errors_are_mapped_without_raw_details(
    discovery_error: SourceDiscoveryError,
    expected_status: int,
    detail: str,
) -> None:
    discovery = FakeSourceDiscovery(discovery_error)
    application, _ = create_github_api(
        discovery,
        frozenset({GitHubRepositoryScope("example", "project")}),
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/github/repositories/example/project",
            headers={"Authorization": "github-reader"},
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}
    assert "secret" not in response.text


def test_service_translates_request_and_scope_errors_before_discovery() -> None:
    discovery = FakeSourceDiscovery(discovery_result())
    service = GitHubRepositoryInspectionService(
        frozenset({GitHubRepositoryScope("example", "project")}),
        discovery,
    )

    with pytest.raises(GitHubInspectionRequestError):
        service.inspect_repository("invalid/owner", "project")
    with pytest.raises(GitHubRepositoryScopeDenied):
        service.inspect_repository("example", "other")

    assert discovery.sources == []


def test_service_rejects_a_discovery_result_from_another_repository() -> None:
    result = replace(discovery_result(), owner="other-owner")
    discovery = FakeSourceDiscovery(result)
    service = GitHubRepositoryInspectionService(
        frozenset({GitHubRepositoryScope("example", "project")}),
        discovery,
    )

    with pytest.raises(GitHubInspectionUnavailable):
        service.inspect_repository("example", "project")
