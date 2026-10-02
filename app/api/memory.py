from datetime import datetime, timezone
from typing import Annotated
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.memory import MemoryScope, MemoryExpiredError
from app.memory.models import MemoryDataError
from app.memory.management import MemoryConflictError
from .security import AuthenticatedPrincipal, require_permission

router = APIRouter(prefix="/api/memory")
Identifier = Annotated[str, Query(min_length=1, max_length=256)]


class MemorySummary(BaseModel):
    id: str
    scope: MemoryScope
    scope_id: str
    type: str
    expires_at: datetime
    expired: bool
    can_manage: bool


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


def get_memory_now():
    return datetime.now(timezone.utc)


def service(request: Request):
    return request.app.state.application_service.memory_management()


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
