"""Mounted exclusively by the explicitly configured local-owner application."""
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .chat import bounded_body, get_application_service
from .security import require_permission
from app.application.services.owned_chat import ChatConflict, ChatUnavailable

router = APIRouter(prefix="/api/local/models")


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=256)


@contextmanager
def model_errors():
    try:
        yield
    except ChatConflict as error:
        raise HTTPException(409, str(error)) from None
    except ChatUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ValueError:
        raise HTTPException(404, "Coordinator or provider not found; refresh the coordinator list") from None
    except Exception:
        raise HTTPException(502, "Local model operation failed; check provider configuration") from None


@router.get("/{agent_id}")
def inventory(agent_id: str, _principal=Depends(require_permission("model:read")),
              service=Depends(get_application_service)):
    with model_errors():
        agent = service.get_agent(agent_id)
        observed = service.local_model_inventory(agent.provider)
        return {"agent_id": agent.id, "provider_id": agent.provider,
                "configured_model": agent.model, "inventory": observed,
                "configured_installed": agent.model in observed.models if observed.state == "available" else None,
                "execution_readiness": "unknown"}


@router.put("/{agent_id}")
def select(agent_id: str, payload=Depends(bounded_body),
           _principal=Depends(require_permission("local-model:select")),
           service=Depends(get_application_service)):
    try:
        body = SelectionRequest.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid local model selection fields") from None
    with model_errors():
        return service.select_local_model(agent_id, body.provider_id, body.model_id)
