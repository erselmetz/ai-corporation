from __future__ import annotations

import base64
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .models import IntegrationSource


GITHUB_REPOSITORY_SOURCE_TYPE = "github_repository"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_TIMEOUT_SECONDS = 10.0
MAX_README_BYTES = 64 * 1024
MAX_README_EXCERPT_CHARACTERS = 2000
_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SourceDiscoveryError(Exception):
    """Base class for expected external source discovery failures."""


class UnsupportedSourceTypeError(SourceDiscoveryError):
    pass


class InvalidSourceLocationError(SourceDiscoveryError):
    pass


class RepositoryNotFoundError(SourceDiscoveryError):
    pass


class PrivateRepositoryError(SourceDiscoveryError):
    pass


class GitHubRateLimitError(SourceDiscoveryError):
    pass


class SourceDiscoveryNetworkError(SourceDiscoveryError):
    pass


class SourceDiscoveryAPIError(SourceDiscoveryError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"GitHub API error ({status_code}): {message}")


class MalformedDiscoveryResponseError(SourceDiscoveryError):
    pass


@dataclass(frozen=True)
class LatestRelease:
    tag_name: str
    name: str | None = None
    published_at: str | None = None
    html_url: str | None = None


@dataclass(frozen=True)
class SourceDiscoveryResult:
    id: str
    source: IntegrationSource
    discovered_at: datetime
    owner: str
    repository_name: str
    repository_url: str
    description: str | None
    default_branch: str | None
    is_public: bool
    language: str | None
    stars: int | None
    forks: int | None
    open_issues: int | None
    license_name: str | None
    license_spdx_id: str | None
    created_at: str | None
    updated_at: str | None
    pushed_at: str | None
    latest_release: LatestRelease | None
    readme_available: bool
    readme_size_bytes: int | None
    readme_excerpt: str | None


class SourceDiscovery(ABC):
    """Adapter boundary for metadata discovery from a typed external source."""

    @abstractmethod
    def discover(self, source: IntegrationSource) -> SourceDiscoveryResult:
        raise NotImplementedError


def validate_github_repository_url(location: str) -> tuple[str, str, str]:
    """Validate a public GitHub repository URL and return owner, repo, canonical URL."""
    if not isinstance(location, str) or not location.strip():
        raise InvalidSourceLocationError("GitHub repository URL cannot be empty")

    try:
        parsed = urlsplit(location.strip())
        port = parsed.port
    except ValueError as exc:
        raise InvalidSourceLocationError("Invalid GitHub repository URL") from exc

    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidSourceLocationError(
            "Only HTTPS URLs on github.com are supported"
        )

    path = parsed.path
    if "%" in path:
        raise InvalidSourceLocationError("Encoded GitHub repository paths are unsupported")
    if not path.startswith("/"):
        raise InvalidSourceLocationError(
            "GitHub URL must identify exactly an owner and repository"
        )
    path = path[1:]
    if path.endswith("/"):
        path = path[:-1]
    segments = path.split("/")
    if len(segments) != 2:
        raise InvalidSourceLocationError(
            "GitHub URL must identify exactly an owner and repository"
        )

    owner, repository = segments
    if repository.endswith(".git"):
        repository = repository[:-4]
    if (
        not _COMPONENT_PATTERN.fullmatch(owner)
        or not _COMPONENT_PATTERN.fullmatch(repository)
        or owner in {".", ".."}
        or repository in {".", ".."}
    ):
        raise InvalidSourceLocationError("Malformed GitHub owner or repository name")

    canonical_url = f"https://github.com/{owner}/{repository}"
    return owner, repository, canonical_url


class GitHubRepositoryDiscovery(SourceDiscovery):
    """Discover public GitHub repository metadata without cloning or executing code."""

    def discover(self, source: IntegrationSource) -> SourceDiscoveryResult:
        if source.source_type != GITHUB_REPOSITORY_SOURCE_TYPE:
            raise UnsupportedSourceTypeError(
                f"Unsupported source type: {source.source_type}"
            )

        owner, repository, canonical_url = validate_github_repository_url(
            source.location
        )
        repository_path = f"/repos/{owner}/{repository}"
        repository_data = self._require_mapping(
            self._request_json(repository_path),
            "repository",
        )

        repository_owner = repository_data.get("owner")
        if not isinstance(repository_owner, dict):
            raise MalformedDiscoveryResponseError(
                "GitHub repository response has no valid owner"
            )
        actual_owner = repository_owner.get("login")
        actual_name = repository_data.get("name")
        if not self._nonempty_string(actual_owner) or not self._nonempty_string(
            actual_name
        ):
            raise MalformedDiscoveryResponseError(
                "GitHub repository response is missing its owner or name"
            )

        visibility = repository_data.get("visibility")
        is_private = repository_data.get("private")
        if visibility is not None:
            if not isinstance(visibility, str):
                raise MalformedDiscoveryResponseError(
                    "GitHub repository visibility is malformed"
                )
            is_public = visibility.lower() == "public"
        elif isinstance(is_private, bool):
            is_public = not is_private
        else:
            raise MalformedDiscoveryResponseError(
                "GitHub repository response is missing visibility"
            )
        if not is_public:
            raise PrivateRepositoryError(
                "Only public GitHub repositories can be discovered"
            )

        license_data = repository_data.get("license")
        if license_data is not None and not isinstance(license_data, dict):
            raise MalformedDiscoveryResponseError(
                "GitHub repository license metadata is malformed"
            )

        release_data = self._request_json(
            f"{repository_path}/releases/latest",
            allow_not_found=True,
        )
        latest_release = self._parse_release(release_data)

        readme_data = self._request_json(
            f"{repository_path}/readme",
            allow_not_found=True,
        )
        readme_available, readme_size, readme_excerpt = self._parse_readme(
            readme_data
        )

        canonical_source = IntegrationSource(
            source_type=source.source_type,
            location=canonical_url,
            project_name=actual_name,
        )
        return SourceDiscoveryResult(
            id=str(uuid4()),
            source=canonical_source,
            discovered_at=datetime.now(timezone.utc),
            owner=actual_owner,
            repository_name=actual_name,
            repository_url=canonical_url,
            description=self._optional_string(repository_data, "description"),
            default_branch=self._optional_string(repository_data, "default_branch"),
            is_public=True,
            language=self._optional_string(repository_data, "language"),
            stars=self._optional_nonnegative_int(
                repository_data, "stargazers_count"
            ),
            forks=self._optional_nonnegative_int(repository_data, "forks_count"),
            open_issues=self._optional_nonnegative_int(
                repository_data, "open_issues_count"
            ),
            license_name=self._optional_string(license_data or {}, "name"),
            license_spdx_id=self._optional_string(license_data or {}, "spdx_id"),
            created_at=self._optional_string(repository_data, "created_at"),
            updated_at=self._optional_string(repository_data, "updated_at"),
            pushed_at=self._optional_string(repository_data, "pushed_at"),
            latest_release=latest_release,
            readme_available=readme_available,
            readme_size_bytes=readme_size,
            readme_excerpt=readme_excerpt,
        )

    def _request_json(
        self, path: str, *, allow_not_found: bool = False
    ) -> dict[str, Any] | None:
        url = f"{GITHUB_API_BASE_URL}{path}"
        try:
            response = httpx.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "ERSELMETZ-AI-CORPORATION",
                },
                timeout=GITHUB_API_TIMEOUT_SECONDS,
                follow_redirects=False,
            )
        except httpx.RequestError as exc:
            raise SourceDiscoveryNetworkError(
                "Could not connect to the GitHub API"
            ) from exc

        if response.status_code == 404 and allow_not_found:
            return None
        if response.status_code == 404:
            raise RepositoryNotFoundError("Public GitHub repository was not found")
        if self._is_rate_limited(response):
            raise GitHubRateLimitError("GitHub API rate limit exceeded")
        if not 200 <= response.status_code < 300:
            raise SourceDiscoveryAPIError(
                response.status_code,
                self._api_error_message(response),
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise MalformedDiscoveryResponseError(
                "GitHub API returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise MalformedDiscoveryResponseError(
                "GitHub API response must be a JSON object"
            )
        return payload

    @staticmethod
    def _is_rate_limited(response: httpx.Response) -> bool:
        if response.status_code == 429:
            return True
        if response.status_code != 403:
            return False
        if response.headers.get("x-ratelimit-remaining") == "0":
            return True
        try:
            payload = response.json()
        except ValueError:
            return False
        return (
            isinstance(payload, dict)
            and isinstance(payload.get("message"), str)
            and "rate limit" in payload["message"].lower()
        )

    @staticmethod
    def _api_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Request failed"
        if isinstance(payload, dict):
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message[:300]
        return "Request failed"

    @staticmethod
    def _require_mapping(
        payload: dict[str, Any] | None, context: str
    ) -> dict[str, Any]:
        if payload is None:
            raise MalformedDiscoveryResponseError(
                f"GitHub returned no {context} metadata"
            )
        return payload

    @staticmethod
    def _nonempty_string(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @classmethod
    def _optional_string(
        cls, payload: dict[str, Any], key: str
    ) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        if not cls._nonempty_string(value):
            raise MalformedDiscoveryResponseError(
                f"GitHub metadata field '{key}' is malformed"
            )
        return value

    @staticmethod
    def _optional_nonnegative_int(
        payload: dict[str, Any], key: str
    ) -> int | None:
        value = payload.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MalformedDiscoveryResponseError(
                f"GitHub metadata field '{key}' is malformed"
            )
        return value

    @classmethod
    def _parse_release(
        cls, payload: dict[str, Any] | None
    ) -> LatestRelease | None:
        if payload is None:
            return None
        tag_name = cls._optional_string(payload, "tag_name")
        if tag_name is None:
            raise MalformedDiscoveryResponseError(
                "GitHub release response is missing its tag"
            )
        return LatestRelease(
            tag_name=tag_name,
            name=cls._optional_string(payload, "name"),
            published_at=cls._optional_string(payload, "published_at"),
            html_url=cls._optional_string(payload, "html_url"),
        )

    @classmethod
    def _parse_readme(
        cls, payload: dict[str, Any] | None
    ) -> tuple[bool, int | None, str | None]:
        if payload is None:
            return False, None, None

        size = cls._optional_nonnegative_int(payload, "size")
        encoded_content = payload.get("content")
        encoding = payload.get("encoding")
        if encoded_content is None:
            return True, size, None
        if not isinstance(encoded_content, str) or encoding != "base64":
            raise MalformedDiscoveryResponseError(
                "GitHub README response content is malformed"
            )
        if size is not None and size > MAX_README_BYTES:
            return True, size, None

        compact_content = "".join(encoded_content.split())
        max_encoded_length = (MAX_README_BYTES * 4 + 2) // 3
        if len(compact_content) > max_encoded_length:
            return True, size, None
        try:
            readme_bytes = base64.b64decode(compact_content, validate=True)
            readme_text = readme_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise MalformedDiscoveryResponseError(
                "GitHub README content could not be safely decoded"
            ) from exc
        return (
            True,
            size if size is not None else len(readme_bytes),
            readme_text[:MAX_README_EXCERPT_CHARACTERS],
        )
