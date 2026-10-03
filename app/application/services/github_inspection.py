"""Repository-scoped, read-only GitHub inspection use case."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations import (
    GITHUB_REPOSITORY_SOURCE_TYPE,
    GitHubRateLimitError,
    GitHubRepositoryDiscovery,
    IntegrationSource,
    InvalidSourceLocationError,
    PrivateRepositoryError,
    RepositoryNotFoundError,
    SourceDiscovery,
    SourceDiscoveryError,
    SourceDiscoveryResult,
    validate_github_repository_url,
)

_MAX_REPOSITORY_SCOPES = 64
_MAX_IDENTIFIER_CHARACTERS = 100


class GitHubInspectionRequestError(Exception):
    """A GitHub repository identifier is invalid."""


class GitHubRepositoryScopeDenied(Exception):
    """The repository is not present in the explicit inspection allowlist."""


class GitHubRepositoryNotFound(Exception):
    """The repository is missing or private."""


class GitHubInspectionRateLimited(Exception):
    """GitHub rejected the request because of its rate limit."""


class GitHubInspectionUnavailable(Exception):
    """A repository inspection could not be completed."""


@dataclass(frozen=True, slots=True)
class GitHubRepositoryScope:
    owner: str
    repository: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.owner, str)
            or not isinstance(self.repository, str)
            or len(self.owner) > _MAX_IDENTIFIER_CHARACTERS
            or len(self.repository) > _MAX_IDENTIFIER_CHARACTERS
        ):
            raise ValueError("GitHub repository scope is invalid")
        try:
            owner, repository, _ = validate_github_repository_url(
                f"https://github.com/{self.owner}/{self.repository}"
            )
        except InvalidSourceLocationError:
            raise ValueError("GitHub repository scope is invalid") from None
        object.__setattr__(self, "owner", owner.casefold())
        object.__setattr__(self, "repository", repository.casefold())

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repository}"


class GitHubRepositoryInspectionService:
    """Inspect explicitly allowlisted public repositories without remote mutation."""

    def __init__(
        self,
        allowed_repositories: frozenset[GitHubRepositoryScope] = frozenset(),
        discovery: SourceDiscovery | None = None,
    ) -> None:
        if (
            not isinstance(allowed_repositories, frozenset)
            or len(allowed_repositories) > _MAX_REPOSITORY_SCOPES
            or any(not isinstance(scope, GitHubRepositoryScope) for scope in allowed_repositories)
        ):
            raise ValueError("GitHub repository scopes must be a bounded frozen allowlist")
        if discovery is not None and not isinstance(discovery, SourceDiscovery):
            raise TypeError("discovery must implement SourceDiscovery")
        self._allowed_repositories = allowed_repositories
        self._discovery = GitHubRepositoryDiscovery() if discovery is None else discovery

    def inspect_repository(self, owner: str, repository: str) -> SourceDiscoveryResult:
        try:
            scope = GitHubRepositoryScope(owner, repository)
        except ValueError:
            raise GitHubInspectionRequestError("GitHub repository identifier is invalid") from None
        if scope not in self._allowed_repositories:
            raise GitHubRepositoryScopeDenied("GitHub repository is outside the allowed scope")

        source = IntegrationSource(
            source_type=GITHUB_REPOSITORY_SOURCE_TYPE,
            location=scope.url,
        )
        try:
            result = self._discovery.discover(source)
        except (RepositoryNotFoundError, PrivateRepositoryError):
            raise GitHubRepositoryNotFound("GitHub repository was not found") from None
        except GitHubRateLimitError:
            raise GitHubInspectionRateLimited("GitHub API rate limit exceeded") from None
        except SourceDiscoveryError:
            raise GitHubInspectionUnavailable("GitHub repository inspection failed") from None
        if (
            not result.is_public
            or result.owner.casefold() != scope.owner
            or result.repository_name.casefold() != scope.repository
        ):
            raise GitHubInspectionUnavailable("GitHub repository identity did not match its scope")
        return result
