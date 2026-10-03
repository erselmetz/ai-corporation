"""Authenticated, repository-scoped, read-only GitHub inspection route."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.application.services import (
    GitHubInspectionRateLimited,
    GitHubInspectionRequestError,
    GitHubInspectionUnavailable,
    GitHubRepositoryInspectionService,
    GitHubRepositoryNotFound,
    GitHubRepositoryScopeDenied,
)
from app.integrations import SourceDiscoveryResult
from .models import GitHubLatestReleaseResponse, GitHubRepositoryInspectionResponse
from .security import require_permission

router = APIRouter(prefix="/api/github/repositories")
RepositoryIdentifier = Annotated[str, Path(min_length=1, max_length=100)]
require_github_read = require_permission("github:read")


def _inspection_response(
    inspection: SourceDiscoveryResult,
) -> GitHubRepositoryInspectionResponse:
    release = inspection.latest_release
    return GitHubRepositoryInspectionResponse(
        owner=inspection.owner,
        repository_name=inspection.repository_name,
        repository_url=inspection.repository_url,
        discovered_at=inspection.discovered_at,
        description=inspection.description,
        default_branch=inspection.default_branch,
        language=inspection.language,
        stars=inspection.stars,
        forks=inspection.forks,
        open_issues=inspection.open_issues,
        license_name=inspection.license_name,
        license_spdx_id=inspection.license_spdx_id,
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
        pushed_at=inspection.pushed_at,
        latest_release=(
            None
            if release is None
            else GitHubLatestReleaseResponse(
                tag_name=release.tag_name,
                name=release.name,
                published_at=release.published_at,
                html_url=release.html_url,
            )
        ),
        readme_available=inspection.readme_available,
        readme_size_bytes=inspection.readme_size_bytes,
    )


def get_github_repository_inspection_service(
    request: Request,
) -> GitHubRepositoryInspectionService:
    return request.app.state.github_repository_inspection_service


@router.get(
    "/{owner}/{repository}",
    response_model=GitHubRepositoryInspectionResponse,
    dependencies=[Depends(require_github_read)],
)
def inspect_github_repository(
    owner: RepositoryIdentifier,
    repository: RepositoryIdentifier,
    service: GitHubRepositoryInspectionService = Depends(
        get_github_repository_inspection_service
    ),
) -> GitHubRepositoryInspectionResponse:
    try:
        result = service.inspect_repository(owner, repository)
    except GitHubInspectionRequestError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GitHub repository identifier is invalid",
        ) from None
    except (GitHubRepositoryScopeDenied, GitHubRepositoryNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub repository was not found or is not in scope",
        ) from None
    except GitHubInspectionRateLimited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="GitHub API rate limit exceeded",
        ) from None
    except GitHubInspectionUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub repository inspection is unavailable",
        ) from None
    return _inspection_response(result)
