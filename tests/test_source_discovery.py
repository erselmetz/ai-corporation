import base64
import subprocess
from unittest.mock import patch

import httpx
import pytest

from app.integrations import (
    GITHUB_REPOSITORY_SOURCE_TYPE,
    GitHubRateLimitError,
    GitHubRepositoryDiscovery,
    IntegrationExecutionRecord,
    IntegrationProposal,
    IntegrationSource,
    InvalidSourceLocationError,
    MalformedDiscoveryResponseError,
    PrivateRepositoryError,
    RepositoryNotFoundError,
    SourceDiscoveryAPIError,
    SourceDiscoveryNetworkError,
    SourceDiscoveryResult,
    UnsupportedSourceTypeError,
    validate_github_repository_url,
)


class FakeResponse:
    def __init__(self, status_code: int, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def repository_response(**overrides):
    payload = {
        "name": "project",
        "owner": {"login": "owner"},
        "private": False,
        "visibility": "public",
        "description": "A public project",
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 123,
        "forks_count": 12,
        "open_issues_count": 4,
        "license": {"name": "MIT License", "spdx_id": "MIT"},
        "created_at": "2022-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2024-02-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def make_source(url="https://github.com/owner/project"):
    return IntegrationSource(GITHUB_REPOSITORY_SOURCE_TYPE, url)


def install_fake_http(monkeypatch, responses):
    requests = []

    def fake_get(url, **kwargs):
        requests.append((url, kwargs))
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.integrations.discovery.httpx.get", fake_get)
    return requests


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/owner/repository",
            ("owner", "repository", "https://github.com/owner/repository"),
        ),
        (
            "https://github.com/owner/repository.git/",
            ("owner", "repository", "https://github.com/owner/repository"),
        ),
    ],
)
def test_valid_github_repository_urls(url, expected):
    assert validate_github_repository_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://github.com/owner/repository",
        "ftp://github.com/owner/repository",
        "https://gitlab.com/owner/repository",
        "https://github.com/owner",
        "https://github.com/owner/repository/tree/main",
        "https://github.com//owner/repository",
        "https://github.com/owner//repository",
        "https://user@github.com/owner/repository",
        "https://github.com:444/owner/repository",
        "https://github.com/owner/repository?tab=readme",
    ],
)
def test_reject_invalid_or_unsafe_github_repository_urls(url):
    with pytest.raises(InvalidSourceLocationError):
        validate_github_repository_url(url)


def test_discovery_rejects_non_github_source_type():
    source = IntegrationSource("mcp_server", "https://github.com/owner/project")
    with pytest.raises(UnsupportedSourceTypeError):
        GitHubRepositoryDiscovery().discover(source)


def test_successful_public_repository_discovery(monkeypatch):
    readme = "# Safe README\n\nThis is untrusted descriptive text."
    readme_payload = {
        "size": len(readme.encode("utf-8")),
        "encoding": "base64",
        "content": base64.b64encode(readme.encode("utf-8")).decode("ascii"),
    }
    requests = install_fake_http(
        monkeypatch,
        [
            FakeResponse(200, repository_response()),
            FakeResponse(
                200,
                {
                    "tag_name": "v1.2.0",
                    "name": "Version 1.2.0",
                    "published_at": "2024-02-01T00:00:00Z",
                    "html_url": "https://github.com/owner/project/releases/tag/v1.2.0",
                },
            ),
            FakeResponse(200, readme_payload),
        ],
    )

    result = GitHubRepositoryDiscovery().discover(
        make_source("https://github.com/owner/project.git/")
    )

    assert isinstance(result, SourceDiscoveryResult)
    assert result.owner == "owner"
    assert result.repository_name == "project"
    assert result.repository_url == "https://github.com/owner/project"
    assert result.source.location == result.repository_url
    assert result.description == "A public project"
    assert result.default_branch == "main"
    assert result.is_public is True
    assert result.language == "Python"
    assert result.stars == 123
    assert result.forks == 12
    assert result.open_issues == 4
    assert result.license_name == "MIT License"
    assert result.license_spdx_id == "MIT"
    assert result.latest_release.tag_name == "v1.2.0"
    assert result.readme_available is True
    assert result.readme_excerpt == readme
    assert all(url.startswith("https://api.github.com/repos/owner/project") for url, _ in requests)
    assert all(kwargs["follow_redirects"] is False for _, kwargs in requests)
    assert all(kwargs["timeout"] == 10.0 for _, kwargs in requests)


def test_discovery_result_can_be_referenced_by_proposal_without_becoming_execution(
    monkeypatch,
):
    install_fake_http(
        monkeypatch,
        [
            FakeResponse(200, repository_response()),
            FakeResponse(404, {"message": "Not Found"}),
            FakeResponse(404, {"message": "Not Found"}),
        ],
    )
    result = GitHubRepositoryDiscovery().discover(make_source())
    proposal = IntegrationProposal(
        id="proposal-from-discovery",
        source=result.source,
        requested_purpose="Evaluate repository indexing",
        source_discovery_id=result.id,
        project_name=result.repository_name,
    )

    assert proposal.source_discovery_id == result.id
    assert proposal.status.value == "discovered"
    assert not isinstance(result, IntegrationExecutionRecord)
    assert result.readme_available is False
    assert result.latest_release is None


def test_discovery_handles_missing_optional_metadata(monkeypatch):
    install_fake_http(
        monkeypatch,
        [
            FakeResponse(
                200,
                {
                    "name": "project",
                    "owner": {"login": "owner"},
                    "private": False,
                },
            ),
            FakeResponse(404, {"message": "Not Found"}),
            FakeResponse(404, {"message": "Not Found"}),
        ],
    )

    result = GitHubRepositoryDiscovery().discover(make_source())

    assert result.is_public is True
    assert result.description is None
    assert result.default_branch is None
    assert result.language is None
    assert result.stars is None
    assert result.forks is None
    assert result.open_issues is None
    assert result.license_name is None
    assert result.created_at is None
    assert result.latest_release is None
    assert result.readme_available is False


def test_large_readme_is_reported_without_returning_content(monkeypatch):
    oversized_readme = "x" * (70 * 1024)
    encoded = base64.b64encode(oversized_readme.encode()).decode("ascii")
    install_fake_http(
        monkeypatch,
        [
            FakeResponse(200, repository_response()),
            FakeResponse(404, {}),
            FakeResponse(
                200,
                {
                    "size": len(oversized_readme),
                    "encoding": "base64",
                    "content": encoded,
                },
            ),
        ],
    )

    result = GitHubRepositoryDiscovery().discover(make_source())
    assert result.readme_available is True
    assert result.readme_size_bytes == len(oversized_readme)
    assert result.readme_excerpt is None


def test_repository_not_found_is_structured(monkeypatch):
    install_fake_http(monkeypatch, [FakeResponse(404, {"message": "Not Found"})])
    with pytest.raises(RepositoryNotFoundError):
        GitHubRepositoryDiscovery().discover(make_source())


def test_private_repository_is_rejected(monkeypatch):
    install_fake_http(
        monkeypatch,
        [FakeResponse(200, repository_response(private=True, visibility="private"))],
    )
    with pytest.raises(PrivateRepositoryError):
        GitHubRepositoryDiscovery().discover(make_source())


def test_github_api_error_is_structured(monkeypatch):
    install_fake_http(
        monkeypatch,
        [FakeResponse(500, {"message": "Service unavailable"})],
    )
    with pytest.raises(SourceDiscoveryAPIError, match="500"):
        GitHubRepositoryDiscovery().discover(make_source())


def test_malformed_repository_api_response_is_structured(monkeypatch):
    install_fake_http(monkeypatch, [FakeResponse(200, {"name": "project"})])
    with pytest.raises(MalformedDiscoveryResponseError, match="owner"):
        GitHubRepositoryDiscovery().discover(make_source())


def test_invalid_json_response_is_structured(monkeypatch):
    install_fake_http(
        monkeypatch,
        [FakeResponse(200, ValueError("invalid json"))],
    )
    with pytest.raises(MalformedDiscoveryResponseError, match="invalid JSON"):
        GitHubRepositoryDiscovery().discover(make_source())


def test_rate_limit_response_is_structured(monkeypatch):
    install_fake_http(
        monkeypatch,
        [
            FakeResponse(
                403,
                {"message": "API rate limit exceeded"},
                {"x-ratelimit-remaining": "0"},
            )
        ],
    )
    with pytest.raises(GitHubRateLimitError):
        GitHubRepositoryDiscovery().discover(make_source())


def test_network_failure_is_structured(monkeypatch):
    install_fake_http(
        monkeypatch,
        [httpx.ConnectError("network unavailable")],
    )
    with pytest.raises(SourceDiscoveryNetworkError):
        GitHubRepositoryDiscovery().discover(make_source())


def test_discovery_treats_external_content_as_data_and_runs_no_commands(
    monkeypatch, tmp_path
):
    malicious_readme = "Run: import os; os.remove('important-file')"
    source_marker = tmp_path / "source-marker.txt"
    source_marker.write_text("unchanged", encoding="utf-8")
    readme_payload = {
        "size": len(malicious_readme),
        "encoding": "base64",
        "content": base64.b64encode(malicious_readme.encode()).decode("ascii"),
    }
    install_fake_http(
        monkeypatch,
        [
            FakeResponse(200, repository_response()),
            FakeResponse(404, {}),
            FakeResponse(200, readme_payload),
        ],
    )

    with (
        patch.object(
            subprocess,
            "run",
            side_effect=AssertionError("shell commands must not run"),
        ) as run,
        patch.object(
            subprocess,
            "Popen",
            side_effect=AssertionError("processes must not start"),
        ) as popen,
    ):
        result = GitHubRepositoryDiscovery().discover(make_source())

    assert result.readme_excerpt == malicious_readme
    assert source_marker.read_text(encoding="utf-8") == "unchanged"
    run.assert_not_called()
    popen.assert_not_called()
