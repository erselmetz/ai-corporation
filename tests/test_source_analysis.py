import base64
import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from app.integrations import (
    GitHubRepositoryAnalyzer,
    IntegrationExecutionRecord,
    IntegrationProposal,
    IntegrationSource,
    GitHubRateLimitError,
    MalformedSourceAnalysisResponseError,
    PrivateRepositoryError,
    RepositoryNotFoundError,
    SourceAnalysisAPIError,
    SourceAnalysisNetworkError,
    SourceAnalysisResult,
    SourceDiscoveryResult,
    UnsupportedAnalysisSourceError,
)
from app.integrations.analysis import (
    MAX_FILE_BYTES,
    MAX_FILES_INSPECTED,
    MAX_TREE_RESPONSE_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        if isinstance(payload, bytes):
            self.body = payload
        else:
            self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_bytes(self, chunk_size=4096):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset : offset + chunk_size]


def make_discovery(**overrides):
    values = {
        "id": "discovery-123",
        "source": IntegrationSource(
            "github_repository", "https://github.com/example/project"
        ),
        "discovered_at": datetime.now(timezone.utc),
        "owner": "example",
        "repository_name": "project",
        "repository_url": "https://github.com/example/project",
        "description": "A source-analysis project",
        "default_branch": "main",
        "is_public": True,
        "language": "Python",
        "stars": 12,
        "forks": 1,
        "open_issues": 0,
        "license_name": "MIT",
        "license_spdx_id": "MIT",
        "created_at": None,
        "updated_at": None,
        "pushed_at": None,
        "latest_release": None,
        "readme_available": True,
        "readme_size_bytes": 82,
        "readme_excerpt": (
            "# Project purpose\n\n"
            "A tool that can generate code and search repositories."
        ),
    }
    values.update(overrides)
    return SourceDiscoveryResult(**values)


def tree_entry(path, *, kind="blob", size=10, sha="abc"):
    return {"path": path, "type": kind, "size": size, "sha": sha}


def contents_payload(content, *, size=None):
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(content.encode("utf-8")) if size is None else size,
        "content": encoded,
    }


def install_responses(monkeypatch, responses):
    requested = []

    def fake_stream(method, url, **kwargs):
        requested.append((method, url, kwargs))
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.integrations.analysis.httpx.stream", fake_stream)
    return requested


def test_analyzes_repository_structure_documentation_and_metadata(monkeypatch):
    tree = {
        "truncated": False,
        "tree": [
            tree_entry("README.md"),
            tree_entry("docs/overview.md", size=49),
            tree_entry("src/app.py", size=100),
            tree_entry("tests/test_app.py", size=70),
            tree_entry("pyproject.toml", size=60),
            tree_entry("LICENSE", size=20),
            tree_entry("ignored.bin"),
        ],
    }
    requests = install_responses(
        monkeypatch,
        [
            FakeResponse(payload=tree),
            FakeResponse(payload=contents_payload("# Overview\nThis project explains APIs.")),
            FakeResponse(payload=contents_payload('[project]\ndependencies = ["fastapi"]')),
        ],
    )

    result = GitHubRepositoryAnalyzer().analyze(make_discovery())

    assert isinstance(result, SourceAnalysisResult)
    assert result.source_discovery_id == "discovery-123"
    assert result.repository_name == "project"
    assert "Python" in result.detected_languages
    assert {"docs", "src", "tests"} <= set(result.top_level_directories)
    assert "docs/overview.md" in result.documentation_files
    assert "pyproject.toml" in result.dependency_manifests
    assert "tests" in result.test_paths
    assert any(framework.statement.endswith("FastAPI.") for framework in result.detected_frameworks)
    assert result.project_purpose is not None
    assert result.project_purpose.evidence_paths == ("README (discovery excerpt)",)
    assert "A tool that can generate code" in result.project_purpose.statement
    assert result.potential_capabilities
    assert result.is_complete is True
    assert result.source_bytes_inspected > 0
    assert all(method == "GET" for method, _, _ in requests)
    assert all(url.startswith("https://api.github.com/repos/example/project/") for _, url, _ in requests)
    assert all(kwargs["follow_redirects"] is False for _, _, kwargs in requests)


def test_analysis_handles_missing_files(monkeypatch):
    install_responses(
        monkeypatch,
        [
            FakeResponse(payload={"tree": [], "truncated": False}),
        ],
    )
    result = GitHubRepositoryAnalyzer().analyze(
        make_discovery(readme_excerpt=None, description=None)
    )
    assert result.important_files == ()
    assert result.documentation_files == ()
    assert result.project_purpose is None
    assert any("No documentation evidence" in note for note in result.analysis_notes)


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(payload={"not_tree": []}),
        FakeResponse(payload=b"{not-json"),
    ],
)
def test_malformed_tree_responses_are_structured(monkeypatch, response):
    install_responses(monkeypatch, [response])
    with pytest.raises(MalformedSourceAnalysisResponseError):
        GitHubRepositoryAnalyzer().analyze(make_discovery())


def test_tree_response_limit_returns_partial_analysis(monkeypatch):
    install_responses(
        monkeypatch,
        [FakeResponse(payload=b" " * (MAX_TREE_RESPONSE_BYTES + 32))],
    )
    result = GitHubRepositoryAnalyzer().analyze(make_discovery())
    assert not result.is_complete
    assert any("tree exceeded the response limit" in note for note in result.analysis_notes)


def test_truncated_tree_is_marked_incomplete(monkeypatch):
    install_responses(
        monkeypatch,
        [
            FakeResponse(
                payload={
                    "truncated": True,
                    "tree": [tree_entry("src/app.py")],
                }
            )
        ],
    )
    result = GitHubRepositoryAnalyzer().analyze(make_discovery())
    assert not result.is_complete
    assert any("truncated" in note for note in result.analysis_notes)


def test_repository_not_found_is_structured(monkeypatch):
    install_responses(monkeypatch, [FakeResponse(status_code=404, payload={})])
    with pytest.raises(RepositoryNotFoundError):
        GitHubRepositoryAnalyzer().analyze(make_discovery())


def test_analyzer_requires_public_github_discovery_with_matching_identity():
    with pytest.raises(UnsupportedAnalysisSourceError):
        GitHubRepositoryAnalyzer().analyze(
            make_discovery(
                source=IntegrationSource("local_project", "local://project")
            )
        )
    with pytest.raises(PrivateRepositoryError):
        GitHubRepositoryAnalyzer().analyze(make_discovery(is_public=False))
    with pytest.raises(MalformedSourceAnalysisResponseError, match="identity"):
        GitHubRepositoryAnalyzer().analyze(
            make_discovery(repository_name="another-project")
        )


def test_api_failure_is_structured(monkeypatch):
    install_responses(
        monkeypatch,
        [FakeResponse(status_code=503, payload={"message": "Unavailable"})],
    )
    with pytest.raises(SourceAnalysisAPIError, match="503"):
        GitHubRepositoryAnalyzer().analyze(make_discovery())


def test_network_failure_is_structured(monkeypatch):
    install_responses(
        monkeypatch,
        [httpx.ConnectError("connection refused")],
    )
    with pytest.raises(SourceAnalysisNetworkError):
        GitHubRepositoryAnalyzer().analyze(make_discovery())


def test_rate_limit_is_structured(monkeypatch):
    install_responses(
        monkeypatch,
        [
            FakeResponse(
                status_code=403,
                payload={"message": "API rate limit exceeded"},
                headers={"x-ratelimit-remaining": "0"},
            )
        ],
    )
    with pytest.raises(GitHubRateLimitError):
        GitHubRepositoryAnalyzer().analyze(make_discovery())


def test_oversized_files_are_skipped_and_analysis_is_partial(monkeypatch):
    install_responses(
        monkeypatch,
        [
            FakeResponse(
                payload={
                    "truncated": False,
                    "tree": [
                        tree_entry("pyproject.toml", size=MAX_FILE_BYTES + 1),
                    ],
                }
            )
        ],
    )
    result = GitHubRepositoryAnalyzer().analyze(make_discovery())
    assert not result.is_complete
    assert any("oversized" in note for note in result.analysis_notes)


def test_missing_content_file_is_reported_as_partial(monkeypatch):
    install_responses(
        monkeypatch,
        [
            FakeResponse(
                payload={
                    "truncated": False,
                    "tree": [tree_entry("pyproject.toml")],
                }
            ),
            FakeResponse(status_code=404, payload={"message": "Not Found"}),
        ],
    )
    result = GitHubRepositoryAnalyzer().analyze(make_discovery())
    assert not result.is_complete
    assert any("unavailable during retrieval" in note for note in result.analysis_notes)


def test_malformed_file_content_is_structured(monkeypatch):
    install_responses(
        monkeypatch,
        [
            FakeResponse(
                payload={
                    "truncated": False,
                    "tree": [tree_entry("pyproject.toml")],
                }
            ),
            FakeResponse(
                payload={
                    "type": "file",
                    "encoding": "base64",
                    "size": 1,
                    "content": "!!!",
                }
            ),
        ],
    )
    with pytest.raises(MalformedSourceAnalysisResponseError, match="base64"):
        GitHubRepositoryAnalyzer().analyze(make_discovery())


def test_repository_file_count_limit_is_reported(monkeypatch):
    entries = [
        tree_entry(f"src/module_{index}.py", size=5, sha=str(index))
        for index in range(MAX_FILES_INSPECTED + 4)
    ]
    install_responses(
        monkeypatch,
        [FakeResponse(payload={"truncated": False, "tree": entries})],
    )
    result = GitHubRepositoryAnalyzer().analyze(
        make_discovery(readme_excerpt=None, description=None)
    )
    assert len(result.important_files) == MAX_FILES_INSPECTED
    assert not result.is_complete
    assert any(str(MAX_FILES_INSPECTED) in note for note in result.analysis_notes)


def test_total_source_byte_limit_is_respected(monkeypatch):
    entries = [
        *[
            tree_entry(f"docs/doc_{index}.md", size=48 * 1024, sha=str(index))
            for index in range(4)
        ],
        tree_entry("pyproject.toml", size=48 * 1024, sha="manifest-1"),
        tree_entry("requirements.txt", size=48 * 1024, sha="manifest-2"),
    ]
    payloads = [FakeResponse(payload={"truncated": False, "tree": entries})]
    content = "x" * MAX_FILE_BYTES
    payloads.extend(
        FakeResponse(payload=contents_payload(content)) for _ in range(6)
    )
    install_responses(monkeypatch, payloads)
    result = GitHubRepositoryAnalyzer().analyze(make_discovery(readme_excerpt=None))
    assert result.source_bytes_inspected <= MAX_TOTAL_SOURCE_BYTES
    assert not result.is_complete


def test_missing_default_branch_returns_partial_without_network(monkeypatch):
    requested = install_responses(monkeypatch, [])
    result = GitHubRepositoryAnalyzer().analyze(
        make_discovery(default_branch=None)
    )
    assert result.is_complete is False
    assert requested == []


def test_analysis_stays_separate_from_proposal_and_execution(monkeypatch):
    install_responses(
        monkeypatch,
        [FakeResponse(payload={"truncated": False, "tree": []})],
    )
    result = GitHubRepositoryAnalyzer().analyze(make_discovery())
    proposal = IntegrationProposal(
        "proposal-1",
        make_discovery().source,
        "Later evaluate this capability",
    )
    assert result.source_discovery_id == "discovery-123"
    assert not isinstance(result, (IntegrationProposal, IntegrationExecutionRecord))
    assert proposal.status.value == "discovered"


def test_analysis_never_executes_commands_or_modifies_local_files(
    monkeypatch, tmp_path
):
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    install_responses(
        monkeypatch,
        [
            FakeResponse(payload={"truncated": False, "tree": []}),
        ],
    )
    with (
        patch.object(subprocess, "run", side_effect=AssertionError("no shell")),
        patch.object(subprocess, "Popen", side_effect=AssertionError("no process")),
    ):
        GitHubRepositoryAnalyzer().analyze(make_discovery())
    assert marker.read_text(encoding="utf-8") == "unchanged"
