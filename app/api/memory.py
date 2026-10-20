from datetime import datetime, timezone
from typing import Annotated, Literal
import json
import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
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
    source_reference: str | None = None
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


class OwnerKnowledgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: StrictStr = Field(min_length=1, max_length=8192)
    source_name: StrictStr = Field(default="Owner note", min_length=1, max_length=128)
    expires_at: datetime
    retention_opt_in: StrictBool


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


class FaissPackInstall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool
    manifest_digest: StrictStr = Field(min_length=64, max_length=64)


class BrainEmbeddingPull(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool
    manifest_digest: StrictStr = Field(min_length=71, max_length=71)
    manifest_bytes: StrictInt = Field(gt=0, le=10 * 1024 * 1024 * 1024)


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


def faiss_pack(request: Request):
    configured = getattr(request.app.state, "faiss_pack_installer", None)
    if configured is not None:
        return configured
    from app.knowledge.faiss_pack import OptionalFaissPack, application_data_root
    return OptionalFaissPack(application_data_root())


@router.get("/brain/faiss/preview")
def preview_brain_faiss_pack(_principal: AuthenticatedPrincipal = Depends(require_permission("capability-pack:manage")),
                             installer=Depends(faiss_pack)):
    return installer.preview()


@router.post("/brain/faiss/install")
def install_brain_faiss_pack(body: FaissPackInstall,
                             request: Request,
                             _principal: AuthenticatedPrincipal = Depends(require_permission("capability-pack:manage")),
                             installer=Depends(faiss_pack)):
    preview = installer.preview()
    if body.confirmed is not True or body.manifest_digest != preview.get("manifest_digest"):
        raise HTTPException(409, "Review the current pinned wheel size and digest, then explicitly confirm installation")
    try:
        result = installer.install(confirmed=body.confirmed, manifest_digest=body.manifest_digest)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    application = getattr(request.app.state, "application_service", None)
    reset = getattr(application, "reset_semantic_memory", None)
    if result.get("state") == "installed" and callable(reset):
        reset()
    return result


@router.post("/brain/faiss/self-test")
def test_brain_faiss_pack(_principal: AuthenticatedPrincipal = Depends(require_permission("capability-pack:manage")),
                         installer=Depends(faiss_pack)):
    from tempfile import TemporaryDirectory
    from pathlib import Path
    from app.knowledge.faiss_pack import activate_faiss_pack
    if installer.preview().get("state") != "installed":
        return {"state": "not-installed", "detail": "Install the optional FAISS pack after reviewing its pinned wheels."}
    try:
        activate_faiss_pack(installer.site_packages)
        from app.knowledge.vector_store import FaissVectorStore
        with TemporaryDirectory(prefix="ersel-brain-test-") as temporary:
            store = FaissVectorStore(temporary)
            store.upsert(["self-test-a", "self-test-b"], [[1.0, 0.0], [0.0, 1.0]], [
                {"scope": "self-test", "scope_id": "temporary", "source_key": "a"},
                {"scope": "self-test", "scope_id": "temporary", "source_key": "b"},
            ])
            result = store.search([1.0, 0.0], {"$and": [{"scope_id": "temporary"}]}, 1)
            if len(result) != 1 or result[0][0] != "self-test-a":
                raise RuntimeError("FAISS result mismatch")
            store.delete_source("a")
            if store.stats()["vector_count"] != 1:
                raise RuntimeError("FAISS deletion mismatch")
        return {"state": "working", "detail": "Local index, filtered search, persistence metadata, and delete passed."}
    except Exception:
        return {"state": "failed", "detail": "FAISS self-test failed; Brain continues using lexical retrieval."}


def brain_embedding_service(request: Request):
    configured = getattr(request.app.state, "brain_embedding_model_service", None)
    if configured is not None:
        return configured
    from app.application.services.first_run_setup import OllamaFirstRunService
    service = OllamaFirstRunService(
        model_id="nomic-embed-text:latest",
        registry_manifest="https://registry.ollama.ai/v2/library/nomic-embed-text/manifests/latest",
    )
    request.app.state.brain_embedding_model_service = service
    return service


@router.get("/brain/embedding/status")
def brain_embedding_status(_principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                           model_service=Depends(brain_embedding_service)):
    try:
        return model_service.status()
    except Exception:
        return {"state": "unknown", "service_running": None,
                "model_id": "nomic-embed-text:latest", "model_installed": None,
                "source": "Local Ollama status check", "reason": "Ollama status could not be checked."}


@router.get("/brain/embedding/preview")
def brain_embedding_preview(_principal: AuthenticatedPrincipal = Depends(require_permission("embedding-model:manage")),
                            model_service=Depends(brain_embedding_service)):
    try:
        preview = model_service.preview_model()
        status = model_service.status()
        return {**preview, "service_running": status.get("service_running"),
                "model_installed": status.get("model_installed")}
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/brain/embedding/pull")
def brain_embedding_pull(body: BrainEmbeddingPull,
                         request: Request,
                         _principal: AuthenticatedPrincipal = Depends(require_permission("embedding-model:manage")),
                         model_service=Depends(brain_embedding_service)):
    if body.confirmed is not True:
        raise HTTPException(409, "Explicit embedding-model download confirmation is required")
    try:
        preview = model_service.preview_model()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    if (preview.get("manifest_digest") != body.manifest_digest
            or preview.get("manifest_bytes") != body.manifest_bytes):
        raise HTTPException(409, "The Ollama model manifest changed; review its size again before downloading")

    def stream():
        completed = False
        for line in model_service.pull(expected_digest=body.manifest_digest,
                                       expected_bytes=body.manifest_bytes):
            try:
                event = json.loads(line)
            except ValueError:
                yield json.dumps({"event": "error", "message": "Ollama returned invalid download progress."}) + "\n"
                return
            if event.get("event") == "complete":
                completed = True
            yield json.dumps(event, separators=(",", ":")) + "\n"
        if completed:
            application = getattr(request.app.state, "application_service", None)
            reset = getattr(application, "reset_semantic_memory", None)
            if callable(reset):
                reset()

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/brain/embedding/self-test")
def brain_embedding_self_test(_principal: AuthenticatedPrincipal = Depends(require_permission("embedding-model:manage"))):
    try:
        from app.knowledge.providers import OllamaEmbeddingProvider
        vector = OllamaEmbeddingProvider("nomic-embed-text:latest").embed_one(
            "ERSELMETZ AI Brain local embedding self-test")
        if not vector or len(vector) > 16_384:
            raise ValueError("invalid embedding")
        return {"state": "working", "dimensions": len(vector),
                "detail": "Ollama returned a bounded local embedding vector."}
    except Exception:
        return {"state": "failed", "detail": "Local embedding self-test failed; lexical retrieval remains available."}


@router.get("/owner")
def list_owner_knowledge(principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                         manager=Depends(service), index=Depends(semantic_service),
                         now=Depends(get_memory_now)):
    items = invoke(lambda: manager.list(actor_id=principal.identity, scope=MemoryScope.OWNER,
                                        scope_id=principal.identity, limit=100, now=now))
    return {"scope": MemoryScope.OWNER.value, "scope_id": principal.identity,
            "items": items, "semantic": index.status()}


@router.get("/brain/graph")
def owner_brain_graph(principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                      manager=Depends(service), now=Depends(get_memory_now)):
    from app.knowledge.brain_graph import build_owner_brain_graph
    return invoke(lambda: build_owner_brain_graph(manager, principal.identity, now))


@router.get("/brain/node")
def owner_brain_node(node_id: Annotated[str, Query(min_length=1, max_length=300)],
                     principal: AuthenticatedPrincipal = Depends(require_permission("memory:read")),
                     manager=Depends(service), now=Depends(get_memory_now)):
    from app.knowledge.brain_graph import inspect_owner_brain_node
    try:
        return inspect_owner_brain_node(manager, principal.identity, node_id, now)
    except MemoryExpiredError:
        raise HTTPException(410, "Brain source has expired") from None
    except PermissionError:
        raise HTTPException(403, "Brain source is not available to this owner") from None
    except KeyError:
        raise HTTPException(404, "Brain node is unavailable") from None
    except ValueError:
        raise HTTPException(422, "Brain node request is invalid") from None


@router.post("/owner")
def create_owner_knowledge(body: OwnerKnowledgeCreate,
                           principal: AuthenticatedPrincipal = Depends(require_permission("memory:manage")),
                           manager=Depends(service), now=Depends(get_memory_now)):
    from app.knowledge.intake import source_name
    from app.knowledge.chunking import chunk_text
    try:
        chunks = chunk_text(body.content)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from None
    record = invoke(lambda: manager.create_owner_note(
        principal.identity, body.content, source_name=source_name(body.source_name),
        expires_at=body.expires_at, retention_opt_in=body.retention_opt_in, now=now))
    return {**record, "chunk_count": len(chunks)}


@router.post("/owner/upload")
async def upload_owner_knowledge(request: Request, file: UploadFile = File(...),
                                 expires_at: datetime = Query(...),
                                 retention_opt_in: bool = Query(...),
                                 principal: AuthenticatedPrincipal = Depends(require_permission("memory:manage")),
                                 manager=Depends(service), now=Depends(get_memory_now)):
    from app.knowledge.intake import MAX_UPLOAD_BYTES, extract_upload
    from app.knowledge.chunking import chunk_text
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > MAX_UPLOAD_BYTES + 16_384):
        raise HTTPException(413, "Knowledge upload exceeds the 1 MiB file limit")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        content, name = extract_upload(file.filename, data)
        chunks = chunk_text(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    record = invoke(lambda: manager.create_owner_note(
        principal.identity, content, source_name=name, expires_at=expires_at,
        retention_opt_in=retention_opt_in, now=now))
    return {**record, "chunk_count": len(chunks)}


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
            "indexed_at": chunks[0].indexed_at.isoformat() if chunks else None,
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
