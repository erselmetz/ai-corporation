"""Owner-reviewed private documentation drafts; published files remain read-only."""
from typing import Annotated
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from app.application.services.documentation_review import (
    DocumentationReviewConflict,
    DocumentationReviewNotFound,
    DocumentationReviewService,
)
from .security import AuthenticatedPrincipal, require_permission

router = APIRouter(prefix="/api/documentation/review")
DocumentId = Annotated[str, Path(min_length=1, max_length=64)]


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: StrictStr = Field(min_length=1, max_length=200)
    content: StrictStr = Field(min_length=1, max_length=DocumentationReviewService.MAX_CONTENT)
    provenance: StrictStr = Field(min_length=1, max_length=1024)


class DraftUpdate(DraftInput):
    expected_version: StrictInt = Field(ge=1, le=DocumentationReviewService.MAX_VERSIONS)


class DraftApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: StrictInt = Field(ge=1, le=DocumentationReviewService.MAX_VERSIONS)
    digest: StrictStr = Field(min_length=64, max_length=64)


class DraftRecovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version: StrictInt = Field(ge=1, le=DocumentationReviewService.MAX_VERSIONS)
    expected_version: StrictInt = Field(ge=1, le=DocumentationReviewService.MAX_VERSIONS)


def service(request: Request) -> DocumentationReviewService:
    return request.app.state.documentation_review_service


def invoke(operation):
    try:
        return operation()
    except DocumentationReviewNotFound:
        raise HTTPException(404, "Documentation draft unavailable") from None
    except DocumentationReviewConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except (OSError, RuntimeError, sqlite3.Error):
        raise HTTPException(503, "Documentation review service unavailable") from None


@router.post("", status_code=201)
def create_draft(body: DraftInput,
                 principal: AuthenticatedPrincipal = Depends(require_permission("documentation:review")),
                 drafts: DocumentationReviewService = Depends(service)):
    return invoke(lambda: drafts.create(title=body.title, content=body.content,
                                       provenance=body.provenance, actor=principal.identity))


@router.get("/{document_id}")
def get_draft(document_id: DocumentId,
              principal: AuthenticatedPrincipal = Depends(require_permission("documentation:review")),
              drafts: DocumentationReviewService = Depends(service)):
    return invoke(lambda: drafts.get(document_id, actor=principal.identity))


@router.get("/{document_id}/versions")
def list_versions(document_id: DocumentId,
                  principal: AuthenticatedPrincipal = Depends(require_permission("documentation:review")),
                  drafts: DocumentationReviewService = Depends(service)):
    return {"items": invoke(lambda: drafts.history(document_id, actor=principal.identity))}


@router.put("/{document_id}")
def update_draft(document_id: DocumentId, body: DraftUpdate,
                 principal: AuthenticatedPrincipal = Depends(require_permission("documentation:review")),
                 drafts: DocumentationReviewService = Depends(service)):
    return invoke(lambda: drafts.update(document_id, expected_version=body.expected_version,
                                       title=body.title, content=body.content,
                                       provenance=body.provenance, actor=principal.identity))


@router.post("/{document_id}/approve")
def approve_draft(document_id: DocumentId, body: DraftApproval,
                  principal: AuthenticatedPrincipal = Depends(require_permission("documentation:review")),
                  drafts: DocumentationReviewService = Depends(service)):
    return invoke(lambda: drafts.approve(document_id, version=body.version,
                                        digest=body.digest, actor=principal.identity))


@router.post("/{document_id}/recover")
def recover_draft(document_id: DocumentId, body: DraftRecovery,
                  principal: AuthenticatedPrincipal = Depends(require_permission("documentation:review")),
                  drafts: DocumentationReviewService = Depends(service)):
    return invoke(lambda: drafts.recover(document_id, source_version=body.source_version,
                                        expected_version=body.expected_version,
                                        actor=principal.identity))
