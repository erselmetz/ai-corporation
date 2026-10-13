from datetime import datetime, timezone
from typing import Annotated, Literal
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from app.memory import MemoryScope, MemoryExpiredError
from app.memory.models import MemoryDataError
from app.memory.management import MemoryConflictError
from app.knowledge import SemanticMemoryService
from app.knowledge.service import SemanticCapabilityUnavailable
from app.application.services.knowledge_proposals import (
    KnowledgeProposalConflict,
    KnowledgeProposalNotFound,
)
from .security import AuthenticatedPrincipal, require_permission

router = APIRouter(prefix="/api/memory")
Identifier = Annotated[str, Query(min_length=1, max_length=256)]


class MemoryProvenanceSummary(BaseModel):
    source_scope: MemoryScope
    source_scope_id: str
    source_reference: str
    source_created_at: datetime


class MemorySummary(BaseModel):
    id: str
    scope: MemoryScope
    scope_id: str
    type: str
    created_at: datetime
    expires_at: datetime
    expired: bool
    can_manage: bool
    provenance: MemoryProvenanceSummary | None = None


class MemoryList(BaseModel):
    items: list[MemorySummary]


class MemoryDetail(MemorySummary):
    content: str
    source_id: str
    revision: str
    source_scope: MemoryScope
    source_scope_id: str
    source_reference: str


class MemoryEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=8192)
    expires_at: datetime
    retention_opt_in: StrictBool
    revision: str = Field(min_length=64, max_length=64)


class SemanticIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: MemoryScope
    scope_id: StrictStr = Field(min_length=1, max_length=256)
    memory_id: StrictStr = Field(min_length=1, max_length=256)


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: StrictStr = Field(min_length=1, max_length=1024)
    scope: MemoryScope
    scope_id: StrictStr = Field(min_length=1, max_length=256)
    limit: StrictInt = Field(default=5, ge=1, le=10)


class SemanticLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: MemoryScope
    scope_id: StrictStr = Field(min_length=1, max_length=256)
    memory_ids: list[StrictStr] = Field(min_length=1, max_length=10)


class KnowledgeProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: MemoryScope
    scope_id: StrictStr = Field(min_length=1, max_length=256)
    memory_id: StrictStr = Field(min_length=1, max_length=256)
    agent_id: StrictStr = Field(min_length=1, max_length=256)


class KnowledgeProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_digest: StrictStr = Field(min_length=64, max_length=64)
    decision: Literal["accept", "reject", "more_information"]


def get_memory_now():
    return datetime.now(timezone.utc)


def service(request: Request):
    return request.app.state.application_service.memory_management()


def semantic_service(request: Request):
    configured = getattr(request.app.state, "semantic_memory_service", None)
    if configured is not None:
        return configured
    application = request.app.state.application_service
    factory = getattr(application, "semantic_memory", None)
    if factory is None:
        return SemanticMemoryService(application.memory_management())
    return factory()


def invoke(operation):
    try:
        return operation()
    except MemoryDataError:
        raise HTTPException(503, "Stored memory is invalid") from None
    except MemoryExpiredError:
        raise HTTPException(410, "Memory has expired") from None
    except MemoryConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except PermissionError:
        raise HTTPException(403, "Memory owner authorization required") from None
    except KeyError:
        raise HTTPException(404, "Memory unavailable") from None
    except ValueError:
        raise HTTPException(422, "Memory validation or provenance check failed") from None
    except (RuntimeError, sqlite3.Error, TypeError):
        raise HTTPException(503, "Memory service unavailable") from None


@router.get("", response_model=MemoryList)
def list_memory(scope: MemoryScope, scope_id: Identifier, limit: int = Query(50, ge=1, le=100),
                principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                manager=Depends(service), now=Depends(get_memory_now)):
    return {"items": invoke(lambda: manager.list(actor_id=principal.identity, scope=scope,
                                                 scope_id=scope_id, limit=limit, now=now))}


@router.get("/record", response_model=MemoryDetail)
def get_memory(scope: MemoryScope, scope_id: Identifier, memory_id: Identifier,
               principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
               manager=Depends(service), now=Depends(get_memory_now)):
    return invoke(lambda: manager.inspect(memory_id, actor_id=principal.identity, scope=scope, scope_id=scope_id, now=now))


@router.put("/record", response_model=MemoryDetail)
def edit_memory(body: MemoryEdit, scope: MemoryScope, scope_id: Identifier, memory_id: Identifier,
                principal: AuthenticatedPrincipal = Depends(require_permission("memory:manage")),
                manager=Depends(service), now=Depends(get_memory_now)):
    return invoke(lambda: manager.update(memory_id, actor_id=principal.identity, scope=scope,
                                        scope_id=scope_id, revision=body.revision, content=body.content,
                                        expires_at=body.expires_at, retention_opt_in=body.retention_opt_in, now=now))


@router.delete("/record", status_code=204)
def delete_memory(scope: MemoryScope, scope_id: Identifier, memory_id: Identifier,
                  principal: AuthenticatedPrincipal = Depends(require_permission("memory:manage")),
                  manager=Depends(service)):
    invoke(lambda: manager.remove(memory_id, actor_id=principal.identity, scope=scope, scope_id=scope_id))
    return Response(status_code=204)


@router.get("/semantic/status")
def semantic_status(principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                    index=Depends(semantic_service)):
    del principal
    return index.status()


@router.post("/semantic/index")
def index_memory(body: SemanticIndexRequest,
                 principal: AuthenticatedPrincipal = Depends(require_permission("memory:index")),
                 index=Depends(semantic_service), now=Depends(get_memory_now)):
    try:
        chunks = index.index(body.memory_id, actor_id=principal.identity, scope=body.scope,
                             scope_id=body.scope_id, now=now)
    except SemanticCapabilityUnavailable:
        raise HTTPException(503, "Semantic indexing is unavailable") from None
    except MemoryExpiredError:
        raise HTTPException(410, "Memory has expired") from None
    except PermissionError:
        raise HTTPException(403, "Only the memory owner may index this record") from None
    except KeyError:
        raise HTTPException(404, "Memory unavailable") from None
    except MemoryDataError:
        raise HTTPException(503, "Stored memory is invalid") from None
    except ValueError:
        raise HTTPException(422, "Memory indexing request is invalid") from None
    except (RuntimeError, sqlite3.Error, TypeError):
        raise HTTPException(503, "Local semantic indexing failed") from None
    except Exception:
        raise HTTPException(503, "Local semantic indexing failed") from None
    return {"indexed": True, "memory_id": body.memory_id, "scope": body.scope.value,
            "scope_id": body.scope_id, "chunk_count": len(chunks),
            "model": index.status().get("model")}


@router.post("/semantic/search")
def search_memory(body: SemanticSearchRequest,
                  principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                  index=Depends(semantic_service), now=Depends(get_memory_now)):
    try:
        result = index.search(body.query, actor_id=principal.identity, scope=body.scope,
                              scope_id=body.scope_id, now=now, limit=body.limit)
    except SemanticCapabilityUnavailable:
        raise HTTPException(503, "Semantic search is unavailable") from None
    except MemoryDataError:
        raise HTTPException(503, "Stored memory is invalid") from None
    except ValueError:
        raise HTTPException(422, "Semantic search request is invalid") from None
    except (RuntimeError, sqlite3.Error, TypeError):
        raise HTTPException(503, "Local semantic search failed") from None
    except Exception:
        raise HTTPException(503, "Local semantic search failed") from None
    return {"items": [{"memory_id": hit.memory_id, "scope": hit.scope.value,
                       "scope_id": hit.scope_id, "source_reference": hit.source_reference,
                       "revision": hit.revision, "excerpt": hit.excerpt,
                       "chunk_position": hit.chunk_position, "relevance": hit.relevance,
                       "expires_at": hit.expires_at}
                      for hit in result.hits],
            "capability": result.capability,
            "candidate_limit_reached": result.candidate_limit_reached,
            "note": "Similarity orders candidates; it does not prove correctness."}


def _semantic_lifecycle(operation, body, principal, index, now):
    try:
        result = operation(body.memory_ids, actor_id=principal.identity,
                           scope=body.scope, scope_id=body.scope_id, now=now)
    except SemanticCapabilityUnavailable:
        raise HTTPException(503, "Semantic lifecycle capability is unavailable") from None
    except ValueError:
        raise HTTPException(422, "Semantic lifecycle request is invalid") from None
    except (RuntimeError, sqlite3.Error, TypeError):
        raise HTTPException(503, "Semantic lifecycle operation failed") from None
    except Exception:
        raise HTTPException(503, "Semantic lifecycle operation failed") from None
    return {
        "operation": result.operation,
        "sources": [source.__dict__ for source in result.sources],
        "completed": result.completed,
        "failed": result.failed,
        "stale_chunks": result.stale_chunks,
        "chunk_counts_truncated": result.counts_truncated,
        "storage": result.storage,
        "execution": "synchronous-bounded",
        "progress_note": "Each selected source result records the completed/total count; no background job is persisted.",
    }


@router.post("/semantic/rebuild")
def rebuild_semantic_memory(body: SemanticLifecycleRequest,
                            principal: AuthenticatedPrincipal = Depends(require_permission("memory:index")),
                            index=Depends(semantic_service), now=Depends(get_memory_now)):
    return _semantic_lifecycle(index.rebuild, body, principal, index, now)


@router.post("/semantic/inspect")
def inspect_semantic_memory(body: SemanticLifecycleRequest,
                            principal: AuthenticatedPrincipal = Depends(require_permission("memory:index")),
                            index=Depends(semantic_service), now=Depends(get_memory_now)):
    return _semantic_lifecycle(index.inspect_lifecycle, body, principal, index, now)


@router.post("/semantic/cleanup")
def cleanup_semantic_memory(body: SemanticLifecycleRequest,
                            principal: AuthenticatedPrincipal = Depends(require_permission("memory:index")),
                            index=Depends(semantic_service), now=Depends(get_memory_now)):
    return _semantic_lifecycle(index.cleanup_stale, body, principal, index, now)


@router.post("/proposals")
def prepare_knowledge_proposal(body: KnowledgeProposalRequest,
                               request: Request,
                               principal: AuthenticatedPrincipal = Depends(require_permission("memory:manage"))):
    try:
        return request.app.state.application_service.knowledge_proposals().prepare(
            principal.identity, body.scope, body.scope_id, body.memory_id, body.agent_id)
    except MemoryExpiredError:
        raise HTTPException(410, "Selected memory source has expired") from None
    except PermissionError:
        raise HTTPException(403, "Only the retained memory owner may prepare a proposal") from None
    except KeyError:
        raise HTTPException(404, "Selected retained memory source is unavailable") from None
    except ValueError as exc:
        message = str(exc)
        if "loopback Ollama" in message:
            raise HTTPException(409, "The selected Agent must use the configured loopback Ollama provider") from None
        raise HTTPException(422, "Knowledge proposal request or generated result is invalid") from None
    except Exception:
        raise HTTPException(503, "Local knowledge proposal generation failed") from None


@router.post("/proposals/{proposal_id}/decision")
def decide_knowledge_proposal(proposal_id: str, body: KnowledgeProposalDecision,
                              request: Request,
                              principal: AuthenticatedPrincipal = Depends(require_permission("memory:manage"))):
    service = request.app.state.application_service.knowledge_proposals()
    try:
        return service.decide(principal.identity, proposal_id,
                              proposal_digest=body.proposal_digest, decision=body.decision)
    except KnowledgeProposalNotFound:
        raise HTTPException(404, "Knowledge proposal not found or expired") from None
    except KnowledgeProposalConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError:
        raise HTTPException(422, "Knowledge proposal decision is invalid") from None
    except (PermissionError, KeyError):
        raise HTTPException(403, "Selected memory source is no longer available to its owner") from None
    except Exception:
        raise HTTPException(503, "Knowledge proposal decision failed") from None
