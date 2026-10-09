"""Authorized owned chat; routes depend only on application services."""
import re
from contextlib import contextmanager
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from starlette.responses import StreamingResponse

from app.application.services.github_inspection import (
    GitHubInspectionRateLimited,
    GitHubInspectionRequestError,
    GitHubInspectionUnavailable,
    GitHubRepositoryNotFound,
    GitHubRepositoryScopeDenied,
)
from app.application.services.repository_study import RepositoryStudyService
from app.application.services.chat_history import ChatHistoryError
from app.application.services.chat_knowledge import ContextRequest, KnowledgeNotFound
from app.application.services.owned_chat import ChatConflict, ChatLimit, ChatNotFound, ChatUnavailable
from app.application.services.chat_task_proposals import (
    ChatTaskProposalConflict,
    ChatTaskProposalExpired,
    ChatTaskProposalNotFound,
)
from app.memory import MemoryScope
from app.conversations import ConversationStatus
from app.integrations import (
    GitHubRateLimitError,
    ProposalGenerationError,
    SourceAnalysisError,
)
from app.providers.base import ProviderCapacityError, ProviderCapacityUnknown
from .security import require_permission

router = APIRouter(prefix="/api/chat/conversations")
_GEMINI_KEY_PATTERN = re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")
_GEMINI_KEY_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:GEMINI|GOOGLE)_API_KEY\s*=\s*\S+", re.IGNORECASE
)
SECRET_PASTE_GUIDANCE = (
    "This message looks like it contains a Gemini API key. It was not saved or sent. "
    "Use the Gemini online setup page to connect a key."
)


def contains_gemini_key(text: str) -> bool:
    return bool(
        _GEMINI_KEY_PATTERN.search(text)
        or _GEMINI_KEY_ASSIGNMENT_PATTERN.search(text)
    )


def get_application_service(request: Request):
    return request.app.state.application_service


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str = Field(min_length=1, max_length=256)


class ChatContextBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1024)
    scope: MemoryScope
    scope_id: str = Field(min_length=1, max_length=256)
    limit: int = Field(default=3, ge=1, le=3)


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8192)
    cloud_consent: bool = False
    context: ChatContextBody | None = None


class RetainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1, max_length=256)
    expires_at: datetime
    retention_opt_in: StrictBool


def get_chat_now():
    return datetime.now(timezone.utc)


class TaskProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_message_id: str = Field(min_length=1, max_length=256)
    objective: str = Field(min_length=1, max_length=1024)
    project_id: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(min_length=1, max_length=256)
    expected_outcome: str = Field(min_length=1, max_length=1024)
    verification_method: str = Field(min_length=1, max_length=1024)
    expected_evidence: str = Field(min_length=1, max_length=1024)
    context_query: str | None = Field(default=None, max_length=1024)
    context_scope: MemoryScope | None = None
    context_scope_id: str | None = Field(default=None, max_length=256)


class TaskProposalConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_digest: str = Field(min_length=64, max_length=64)
    confirmed: StrictBool


class RepositoryStudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=1, max_length=1024)
    owner: str = Field(min_length=1, max_length=100)
    repository: str = Field(min_length=1, max_length=100)

    @field_validator("objective")
    @classmethod
    def objective_must_fit_utf8_limit(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Study objective is required")
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("Study objective must be valid UTF-8 text") from error
        if len(encoded) > RepositoryStudyService.MAX_OBJECTIVE_BYTES:
            raise ValueError("Study objective exceeds the UTF-8 byte limit")
        return value


async def bounded_body(request: Request):
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > 65536:
            raise HTTPException(413, "Chat request too large")
        payload.extend(chunk)
    return bytes(payload)


def parse(model, payload):
    try:
        return model.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid chat request fields") from None


def get_repository_study_service(request: Request) -> RepositoryStudyService:
    return request.app.state.repository_study_service


@contextmanager
def chat_errors():
    try:
        yield
    except ChatTaskProposalNotFound:
        raise HTTPException(404, "Task proposal not found") from None
    except ChatTaskProposalExpired as error:
        raise HTTPException(410, str(error)) from None
    except ChatTaskProposalConflict as error:
        raise HTTPException(409, str(error)) from None
    except KnowledgeNotFound:
        raise HTTPException(404, "Retained knowledge not found") from None
    except PermissionError:
        raise HTTPException(403, "Context scope is not authorized for this conversation") from None
    except ChatNotFound:
        raise HTTPException(404, "Conversation not found") from None
    except ChatConflict as error:
        raise HTTPException(409, str(error)) from None
    except ChatLimit as error:
        raise HTTPException(429, str(error)) from None
    except ChatUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ProviderCapacityUnknown as error:
        raise HTTPException(503, str(error)) from None
    except ProviderCapacityError as error:
        raise HTTPException(429, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Chat input or conversation state is invalid") from None
    except ChatHistoryError as error:
        raise HTTPException(503, str(error)) from None
    except RuntimeError:
        raise HTTPException(502, "Chat response failed; check the configured provider and model. No automatic retry occurred.") from None


@router.get("")
def list_conversations(principal=Depends(require_permission("chat:read")),
                       service=Depends(get_application_service)):
    with chat_errors():
        return {"items": service.owned_chat().list(principal.identity)}


@router.post("")
def start_conversation(payload=Depends(bounded_body),
                       principal=Depends(require_permission("chat:start")),
                       service=Depends(get_application_service)):
    body = parse(StartRequest, payload)
    with chat_errors():
        return service.owned_chat().start(principal.identity, body.agent_id)


@router.get("/{identifier}")
def get_conversation(identifier: str, principal=Depends(require_permission("chat:read")),
                     service=Depends(get_application_service), now=Depends(get_chat_now)):
    with chat_errors():
        record = service.owned_chat().get(principal.identity, identifier)
        return {**record, "context_traces": service.chat_knowledge().traces(principal.identity, identifier, now)}


@router.post("/{identifier}/messages")
def send_message(identifier: str, payload=Depends(bounded_body),
                 principal=Depends(require_permission("chat:send")),
                 service=Depends(get_application_service), now=Depends(get_chat_now)):
    body = parse(SendRequest, payload)
    if contains_gemini_key(body.text) or (body.context and contains_gemini_key(body.context.query)):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    with chat_errors():
        current = service.owned_chat().get(principal.identity, identifier)
        if (
            service.provider_requires_explicit_cloud_consent(
                current["coordinator"].provider
            )
            and body.cloud_consent is not True
        ):
            raise HTTPException(403, "Explicit consent is required before sending this turn and recent chat context to Gemini.")
        knowledge = service.chat_knowledge()
        retrieved = trace_request = None
        if body.context is not None:
            retrieved, trace_request = knowledge.retrieve(principal.identity, identifier, ContextRequest(
                body.context.query, body.context.scope, body.context.scope_id, body.context.limit), now)
        result = service.owned_chat().send(principal.identity, identifier, body.text,
                                           knowledge.prompt_context(retrieved) if retrieved else None)
        if retrieved is not None:
            reply = result["conversation"].messages[-1]
            result = {**result, "context_trace": knowledge.record_trace(
                principal.identity, identifier, reply.id, retrieved, trace_request, now)}
        return result


@router.post("/{identifier}/messages/stream")
def stream_message(identifier: str, payload=Depends(bounded_body),
                   principal=Depends(require_permission("chat:send")),
                   service=Depends(get_application_service), now=Depends(get_chat_now)):
    body = parse(SendRequest, payload)
    if contains_gemini_key(body.text) or (body.context and contains_gemini_key(body.context.query)):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    with chat_errors():
        owned = service.owned_chat()
        current = owned.get(principal.identity, identifier)
        if not current.get("streaming_supported"):
            raise HTTPException(409, "The selected provider does not support response streaming.")
        if (
            service.provider_requires_explicit_cloud_consent(
                current["coordinator"].provider
            )
            and body.cloud_consent is not True
        ):
            raise HTTPException(
                403,
                "Explicit consent is required before sending this turn and recent chat context to Gemini.",
            )
        knowledge = service.chat_knowledge()
        retrieved = trace_request = None
        if body.context is not None:
            retrieved, trace_request = knowledge.retrieve(
                principal.identity,
                identifier,
                ContextRequest(
                    body.context.query,
                    body.context.scope,
                    body.context.scope_id,
                    body.context.limit,
                ),
                now,
            )

    def events():
        try:
            for event in owned.stream(
                principal.identity,
                identifier,
                body.text,
                knowledge.prompt_context(retrieved) if retrieved else None,
            ):
                if event["type"] == "complete" and retrieved is not None:
                    completed = event["conversation"]
                    reply = completed.messages[-1]
                    event = {
                        **event,
                        "context_trace": knowledge.record_trace(
                            principal.identity, identifier, reply.id, retrieved, trace_request, now
                        ),
                    }
                yield json.dumps(
                    jsonable_encoder(event), ensure_ascii=True, separators=(",", ":")
                ) + "\n"
        except ProviderCapacityError:
            yield json.dumps({
                "type": "error",
                "message": "Configured provider request-slot capacity is exhausted; no provider request was admitted.",
            }) + "\n"
        except Exception:
            yield json.dumps({
                "type": "error",
                "message": (
                    "The stream ended before a verified final response. The turn may have reached "
                    "the provider; inspect its pending status and do not resend it."
                ),
            }) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/{identifier}/repository-studies",
    dependencies=[Depends(require_permission("github:read"))],
)
def study_repository(
    identifier: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("chat:send")),
    service=Depends(get_application_service),
    study_service=Depends(get_repository_study_service),
):
    body = parse(RepositoryStudyRequest, payload)
    with chat_errors():
        conversation_status = service.owned_chat().get_status(
            principal.identity, identifier
        )
    if conversation_status is not ConversationStatus.OPEN:
        raise HTTPException(409, "Repository studies require an open owned conversation")
    try:
        report = study_service.study(body.objective, body.owner, body.repository)
    except GitHubInspectionRequestError:
        raise HTTPException(422, "GitHub repository identifier is invalid") from None
    except (GitHubRepositoryScopeDenied, GitHubRepositoryNotFound):
        raise HTTPException(
            404, "GitHub repository was not found or is not in scope"
        ) from None
    except (GitHubInspectionRateLimited, GitHubRateLimitError):
        raise HTTPException(429, "GitHub API rate limit exceeded") from None
    except GitHubInspectionUnavailable:
        raise HTTPException(503, "GitHub repository inspection is unavailable") from None
    except (SourceAnalysisError, ProposalGenerationError):
        raise HTTPException(503, "Repository study could not be completed") from None

    analysis = report.analysis
    discovery = report.discovery
    project_purpose = analysis.project_purpose
    response = {
        "objective": report.objective,
        "decision": report.decision.value,
        "studied_at": report.studied_at,
        "repository": {
            "owner": discovery.owner,
            "name": discovery.repository_name,
            "url": discovery.repository_url,
            "discovered_at": discovery.discovered_at,
            "description": discovery.description,
            "default_branch": discovery.default_branch,
            "license": {
                "name": discovery.license_name,
                "spdx_id": discovery.license_spdx_id,
            },
            "last_pushed_at": discovery.pushed_at,
            "revision_sha": analysis.revision_sha,
            "revision_url": (
                f"{discovery.repository_url}/tree/{analysis.revision_sha}"
                if analysis.revision_sha is not None
                else None
            ),
        },
        "analysis": {
            "complete": analysis.is_complete,
            "languages": list(analysis.detected_languages),
            "top_level_directories": list(analysis.top_level_directories),
            "dependency_manifests": list(analysis.dependency_manifests),
            "documentation_files": list(analysis.documentation_files),
            "test_paths": list(analysis.test_paths),
            "project_purpose": (
                None
                if project_purpose is None
                else {
                    "statement": project_purpose.statement,
                    "evidence_paths": list(project_purpose.evidence_paths),
                }
            ),
            "potential_capabilities": [
                {
                    "statement": observation.statement,
                    "evidence_paths": list(observation.evidence_paths),
                }
                for observation in analysis.potential_capabilities
            ],
            "notes": list(analysis.analysis_notes),
            "source_bytes_inspected": analysis.source_bytes_inspected,
        },
        "findings": jsonable_encoder(report.evaluation.findings),
        "strengths": list(report.evaluation.key_strengths),
        "concerns": list(report.evaluation.key_concerns),
        "unknowns": list(report.evaluation.unknowns),
        "integration_requirements": list(report.evaluation.integration_requirements),
        "proposal": {
            "id": report.proposal.id,
            "status": report.proposal.status.value,
            "requested_purpose": report.proposal.requested_purpose,
            "proposed_approach": report.proposal.proposed_approach,
            "risk_information": report.proposal.risk_information,
            "intended_capabilities": list(report.proposal.intended_capabilities),
            "key_strengths": list(report.proposal.key_strengths),
            "key_concerns": list(report.proposal.key_concerns),
            "unknowns": list(report.proposal.unknowns),
            "integration_requirements": list(
                report.proposal.integration_requirements
            ),
            "evidence_references": list(report.proposal.evidence_references),
        },
        "citations": jsonable_encoder(report.citations),
        "limitations": list(report.limitations),
    }
    if len(json.dumps(jsonable_encoder(response), ensure_ascii=True).encode("utf-8")) > 131072:
        raise HTTPException(502, "Repository study report exceeded its response limit")
    return response


@router.get("/{identifier}/retained")
def list_retained(identifier: str, principal=Depends(require_permission("chat:read")),
                  service=Depends(get_application_service), now=Depends(get_chat_now)):
    with chat_errors():
        return service.chat_knowledge().list_retained(principal.identity, identifier, now)


@router.post("/{identifier}/retained")
def retain_message(identifier: str, payload=Depends(bounded_body),
                   principal=Depends(require_permission("chat-knowledge:retain")),
                   service=Depends(get_application_service), now=Depends(get_chat_now)):
    body = parse(RetainRequest, payload)
    with chat_errors():
        return service.chat_knowledge().retain(
            principal.identity, identifier, body.message_id, expires_at=body.expires_at,
            retention_opt_in=body.retention_opt_in, now=now)


@router.delete("/{identifier}/retained/{memory_id}")
def withdraw_retained(identifier: str, memory_id: str,
                      principal=Depends(require_permission("chat-knowledge:withdraw")),
                      service=Depends(get_application_service)):
    with chat_errors():
        return service.chat_knowledge().withdraw(principal.identity, identifier, memory_id)


@router.post("/{identifier}/close")
def close_conversation(identifier: str, principal=Depends(require_permission("chat:close")),
                       service=Depends(get_application_service)):
    with chat_errors():
        return service.owned_chat().close(principal.identity, identifier)


@router.post("/{identifier}/task-proposals")
def create_task_proposal(
    identifier: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("chat-task:create")),
    service=Depends(get_application_service),
):
    body = parse(TaskProposalRequest, payload)
    with chat_errors():
        return service.chat_task_proposals().create(
            principal.identity,
            identifier,
            source_message_id=body.source_message_id,
            objective=body.objective,
            project_id=body.project_id,
            agent_id=body.agent_id,
            expected_outcome=body.expected_outcome,
            verification_method=body.verification_method,
            expected_evidence=body.expected_evidence,
            context_query=body.context_query,
            context_scope=body.context_scope,
            context_scope_id=body.context_scope_id,
        )


@router.post("/{identifier}/task-proposals/{proposal_id}/confirm")
def confirm_task_proposal(
    identifier: str,
    proposal_id: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("chat-task:create")),
    service=Depends(get_application_service),
):
    body = parse(TaskProposalConfirmation, payload)
    with chat_errors():
        return service.chat_task_proposals().confirm(
            principal.identity,
            identifier,
            proposal_id,
            proposal_digest=body.proposal_digest,
            confirmed=body.confirmed,
        )
