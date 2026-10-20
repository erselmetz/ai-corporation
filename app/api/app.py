from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from app.application import (
    ActivitySummary,
    CorporationApplicationService,
    DocumentationApplicationService,
    DocumentationDocument,
    DocumentationNotFound,
    DocumentationSource,
    DocumentationSourceUnavailable,
    GitHubRepositoryInspectionService,
    ProjectSummary,
    RepositoryStudyService,
    TaskSummary,
    UpdatesApplicationService,
    UpdatesSource,
    UpdatesSourceUnavailable,
)
from app.documentation import MarkdownDocumentationSource
from app.updates import CuratedUpdatesManifest
from app.updates.trusted_release import TrustedReleaseError, TrustedReleaseService
from app.application.services.owned_chat import ChatConflict
from app.application.services.corporation import BuiltinAgentProtected
from app.integrations import SandboxImagePolicy
from app.runtime import create_corporation_runtime
from app.build_stamp import BUILD_STAMP
from app.chat_prompt import debug_chat_adapter_contract_self_check
from app.webui import web_ui_router
from app.positions import (
    POSITION_TEMPLATES,
    CorporationPosition,
    PositionConflictError,
    PositionNotFoundError,
    PositionValidationError,
)
from .models import (
    ActivityListResponse,
    ActivityResponse,
    AgentListResponse,
    AgentResponse,
    CorporationIdentityResponse,
    CorporationStatusResponse,
    DocumentationListResponse,
    DocumentationResponse,
    DocumentationSummaryResponse,
    EmployeeCreateRequest,
    EmployeeListResponse,
    EmployeeResponse,
    ModelAssignmentListResponse,
    ModelAssignmentRequest,
    ModelAssignmentResponse,
    NodeIdentityResponse,
    ProviderCreateRequest,
    ProviderListResponse,
    ProviderResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    PositionCreateRequest,
    PositionDeactivateRequest,
    PositionListResponse,
    PositionResponse,
    PositionRevisionResponse,
    PositionTemplatesResponse,
    PositionUpdateRequest,
    TaskCreateRequest,
    TaskDryRunResponse,
    TaskListResponse,
    TaskResponse,
    UpdatesListResponse,
    UpdateResponse,
    ReleasePrepareRequest,
)
from app.orchestrator.router import RoutingError
from .security import (
    AuthenticationBackend,
    RejectingAuthenticationBackend,
    require_permission,
)

api_router = APIRouter()
corporation_router = APIRouter(prefix="/api")


class WebUIStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if path.endswith(".mjs") and response.status_code == status.HTTP_200_OK:
            response.headers["content-type"] = "text/javascript; charset=utf-8"
        return response


@api_router.get("/")
def root() -> dict[str, str]:
    return {"application": "ERSELMETZ AI API"}


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", **BUILD_STAMP}


def get_application_service(request: Request) -> CorporationApplicationService:
    """FastAPI dependency for interface routes using application use cases."""
    return request.app.state.application_service


def get_documentation_service(
    request: Request,
) -> DocumentationApplicationService:
    return request.app.state.documentation_service


def get_updates_service(request: Request) -> UpdatesApplicationService:
    return request.app.state.updates_service


@corporation_router.get(
    "/status",
    response_model=CorporationStatusResponse,
    dependencies=[Depends(require_permission("corporation:read"))],
)
def corporation_status(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> CorporationStatusResponse:
    summary = application_service.get_corporation_status()
    return CorporationStatusResponse(
        corporation=CorporationIdentityResponse(
            id=summary.corporation_id,
            name=summary.corporation_name,
        ),
        node=NodeIdentityResponse(
            id=summary.node_id,
            name=summary.node_name,
        ),
    )


@corporation_router.get(
    "/documentation",
    response_model=DocumentationListResponse,
    dependencies=[Depends(require_permission("documentation:read"))],
)
def list_documentation(
    documentation_service: DocumentationApplicationService = Depends(
        get_documentation_service
    ),
) -> DocumentationListResponse:
    try:
        summaries = documentation_service.list_documents()
    except DocumentationSourceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Documentation source unavailable",
        ) from exc
    return DocumentationListResponse(
        items=[
            DocumentationSummaryResponse(id=summary.id, title=summary.title)
            for summary in summaries
        ]
    )


@corporation_router.get(
    "/documentation/{document_id}",
    response_model=DocumentationResponse,
    dependencies=[Depends(require_permission("documentation:read"))],
)
def get_documentation(
    document_id: str,
    documentation_service: DocumentationApplicationService = Depends(
        get_documentation_service
    ),
) -> DocumentationResponse:
    try:
        document: DocumentationDocument = documentation_service.get_document(
            document_id
        )
    except DocumentationNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documentation document not found",
        ) from exc
    except DocumentationSourceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Documentation source unavailable",
        ) from exc
    return DocumentationResponse(
        id=document.id,
        title=document.title,
        content=document.content,
    )


@corporation_router.get(
    "/updates",
    response_model=UpdatesListResponse,
    dependencies=[Depends(require_permission("updates:read"))],
)
def list_updates(
    updates_service: UpdatesApplicationService = Depends(get_updates_service),
) -> UpdatesListResponse:
    try:
        updates = updates_service.list_updates()
    except UpdatesSourceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Updates source unavailable",
        ) from exc
    return UpdatesListResponse(
        items=[
            UpdateResponse(
                date=update.date,
                type=update.type,
                title=update.title,
                summary=update.summary,
            )
            for update in updates
        ]
    )


@corporation_router.get(
    "/updates/release",
    dependencies=[Depends(require_permission("updates:read"))],
)
def check_trusted_release(request: Request) -> dict[str, object]:
    try:
        return request.app.state.trusted_release_service.check().response()
    except TrustedReleaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@corporation_router.post(
    "/updates/release/prepare",
    dependencies=[Depends(require_permission("updates:manage"))],
)
def prepare_trusted_release(
    payload: ReleasePrepareRequest,
    request: Request,
) -> dict[str, object]:
    csrf = getattr(request.app.state.authentication_backend, "require_csrf", None)
    if callable(csrf):
        csrf(request)
    try:
        return request.app.state.trusted_release_service.prepare(payload.version)
    except TrustedReleaseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@corporation_router.get(
    "/employees",
    response_model=EmployeeListResponse,
    dependencies=[Depends(require_permission("employee:read"))],
)
def list_employees(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> EmployeeListResponse:
    return EmployeeListResponse(
        items=[
            EmployeeResponse(
                id=summary.id,
                name=summary.name,
                role=summary.role,
                responsibilities=list(summary.responsibilities),
                agent_id=summary.agent_id,
            )
            for summary in application_service.list_employees()
        ]
    )


@corporation_router.get(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("employee:read"))],
)
def get_employee(
    employee_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> EmployeeResponse:
    try:
        summary = application_service.get_employee(employee_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    return EmployeeResponse(
        id=summary.id,
        name=summary.name,
        role=summary.role,
        responsibilities=list(summary.responsibilities),
        agent_id=summary.agent_id,
    )


@corporation_router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("employee:manage"))],
)
def create_employee(
    employee: EmployeeCreateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> EmployeeResponse:
    try:
        summary = application_service.create_employee(
            employee_id=employee.id,
            name=employee.name,
            role=employee.role,
            responsibilities=employee.responsibilities,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee already exists",
        ) from exc
    return EmployeeResponse(
        id=summary.id,
        name=summary.name,
        role=summary.role,
        responsibilities=list(summary.responsibilities),
        agent_id=summary.agent_id,
    )


@corporation_router.delete(
    "/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("employee:manage"))],
)
def remove_employee(
    employee_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> Response:
    try:
        application_service.remove_employee(employee_id)
    except PositionConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee is referenced by an organizational position",
        ) from None
    except BuiltinAgentProtected as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _position_response(position: CorporationPosition) -> PositionResponse:
    return PositionResponse(
        id=position.id,
        title=position.title,
        responsibilities=list(position.responsibilities),
        reports_to_position_id=position.reports_to_position_id,
        employee_id=position.employee_id,
        active=position.active,
        revision=position.revision,
        history=[
            PositionRevisionResponse(
                revision=item.revision,
                title=item.title,
                responsibilities=list(item.responsibilities),
                reports_to_position_id=item.reports_to_position_id,
                employee_id=item.employee_id,
                active=item.active,
                recorded_at=item.recorded_at,
            )
            for item in position.history
        ],
    )


@corporation_router.get(
    "/positions/templates",
    response_model=PositionTemplatesResponse,
    dependencies=[Depends(require_permission("position:read"))],
)
def list_position_templates() -> PositionTemplatesResponse:
    return PositionTemplatesResponse(items=list(POSITION_TEMPLATES))


@corporation_router.get(
    "/positions",
    response_model=PositionListResponse,
    dependencies=[Depends(require_permission("position:read"))],
)
def list_positions(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> PositionListResponse:
    return PositionListResponse(
        items=[
            _position_response(item)
            for item in application_service.list_positions()
        ]
    )


@corporation_router.get(
    "/positions/{position_id}",
    response_model=PositionResponse,
    dependencies=[Depends(require_permission("position:read"))],
)
def get_position(
    position_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> PositionResponse:
    try:
        return _position_response(application_service.get_position(position_id))
    except PositionNotFoundError:
        raise HTTPException(status_code=404, detail="Position not found") from None


@corporation_router.post(
    "/positions",
    response_model=PositionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("position:manage"))],
)
def create_position(
    body: PositionCreateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> PositionResponse:
    try:
        position = application_service.create_position(
            body.title,
            body.responsibilities,
            body.reports_to_position_id,
            body.employee_id,
        )
    except PositionValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except PositionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return _position_response(position)


@corporation_router.put(
    "/positions/{position_id}",
    response_model=PositionResponse,
    dependencies=[Depends(require_permission("position:manage"))],
)
def update_position(
    position_id: str,
    body: PositionUpdateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> PositionResponse:
    try:
        position = application_service.update_position(
            position_id,
            body.expected_revision,
            body.title,
            body.responsibilities,
            body.reports_to_position_id,
            body.employee_id,
        )
    except PositionNotFoundError:
        raise HTTPException(status_code=404, detail="Position not found") from None
    except PositionValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except PositionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return _position_response(position)


@corporation_router.post(
    "/positions/{position_id}/deactivate",
    response_model=PositionResponse,
    dependencies=[Depends(require_permission("position:manage"))],
)
def deactivate_position(
    position_id: str,
    body: PositionDeactivateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> PositionResponse:
    try:
        position = application_service.deactivate_position(
            position_id, body.expected_revision
        )
    except PositionNotFoundError:
        raise HTTPException(status_code=404, detail="Position not found") from None
    except PositionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return _position_response(position)


@corporation_router.delete(
    "/positions/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("position:manage"))],
)
def remove_position(
    position_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> Response:
    try:
        application_service.remove_position(position_id)
    except PositionNotFoundError:
        raise HTTPException(status_code=404, detail="Position not found") from None
    except PositionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@corporation_router.get(
    "/agents",
    response_model=AgentListResponse,
    dependencies=[Depends(require_permission("agent:read"))],
)
def list_agents(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> AgentListResponse:
    return AgentListResponse(
        items=[
            AgentResponse(
                id=summary.id,
                name=summary.name,
                role=summary.role,
                provider=summary.provider,
                model=summary.model,
                capabilities=list(summary.capabilities),
            )
            for summary in application_service.list_agents()
        ]
    )


@corporation_router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    dependencies=[Depends(require_permission("agent:read"))],
)
def get_agent(
    agent_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> AgentResponse:
    try:
        summary = application_service.get_agent(agent_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        ) from exc
    return AgentResponse(
        id=summary.id,
        name=summary.name,
        role=summary.role,
        provider=summary.provider,
        model=summary.model,
        capabilities=list(summary.capabilities),
    )


@corporation_router.get(
    "/providers",
    response_model=ProviderListResponse,
    dependencies=[Depends(require_permission("provider:read"))],
)
def list_providers(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ProviderListResponse:
    return ProviderListResponse(
        items=[
            ProviderResponse(id=summary.id, type=summary.type_name)
            for summary in application_service.list_providers()
        ]
    )


@corporation_router.get(
    "/providers/{provider_id}",
    response_model=ProviderResponse,
    dependencies=[Depends(require_permission("provider:read"))],
)
def get_provider(
    provider_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ProviderResponse:
    try:
        summary = application_service.get_provider(provider_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        ) from exc
    return ProviderResponse(id=summary.id, type=summary.type_name)


@corporation_router.post(
    "/providers",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("provider:manage"))],
)
def create_provider(
    provider: ProviderCreateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ProviderResponse:
    try:
        summary = application_service.create_provider(provider.id, provider.name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider already exists",
        ) from exc
    return ProviderResponse(id=summary.id, type=summary.type_name)


@corporation_router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("provider:manage"))],
)
def remove_provider(
    provider_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> Response:
    try:
        application_service.remove_provider(provider_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@corporation_router.get(
    "/models",
    response_model=ModelAssignmentListResponse,
    dependencies=[Depends(require_permission("model:read"))],
)
def list_models(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ModelAssignmentListResponse:
    return ModelAssignmentListResponse(
        items=[
            ModelAssignmentResponse(
                agent_id=assignment.agent_id,
                provider_id=assignment.provider_id,
                model_id=assignment.model_id,
            )
            for assignment in application_service.list_models()
        ]
    )


@corporation_router.get(
    "/models/{agent_id}",
    response_model=ModelAssignmentResponse,
    dependencies=[Depends(require_permission("model:read"))],
)
def get_model_assignment(
    agent_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ModelAssignmentResponse:
    try:
        assignment = application_service.get_model_assignment(agent_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent model assignment not found",
        ) from exc
    return ModelAssignmentResponse(
        agent_id=assignment.agent_id,
        provider_id=assignment.provider_id,
        model_id=assignment.model_id,
    )


@corporation_router.put(
    "/models/{agent_id}",
    response_model=ModelAssignmentResponse,
    dependencies=[Depends(require_permission("model:manage"))],
)
def replace_model_assignment(
    agent_id: str,
    assignment: ModelAssignmentRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ModelAssignmentResponse:
    try:
        result = application_service.replace_model(
            agent_id,
            assignment.provider_id,
            assignment.model_id,
        )
    except ChatConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent or provider not found",
        ) from exc
    return ModelAssignmentResponse(
        agent_id=result.agent_id,
        provider_id=result.provider_id,
        model_id=result.model_id,
    )


def _project_response(summary: ProjectSummary) -> ProjectResponse:
    return ProjectResponse(
        id=summary.id,
        name=summary.name,
        description=summary.description,
        status=summary.status,
    )


@corporation_router.get(
    "/projects",
    response_model=ProjectListResponse,
    dependencies=[Depends(require_permission("project:read"))],
)
def list_projects(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ProjectListResponse:
    return ProjectListResponse(
        items=[
            _project_response(summary)
            for summary in application_service.list_projects()
        ]
    )


@corporation_router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_permission("project:read"))],
)
def get_project(
    project_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ProjectResponse:
    try:
        summary = application_service.get_project(project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from exc
    return _project_response(summary)


@corporation_router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("project:create"))],
)
def create_project(
    project: ProjectCreateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ProjectResponse:
    try:
        summary = application_service.create_project(
            name=project.name,
            description=project.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project conflicts with an existing project",
        ) from exc
    return _project_response(summary)


def _activity_response(summary: ActivitySummary) -> ActivityResponse:
    return ActivityResponse(
        id=summary.id,
        task_id=summary.task_id,
        event=summary.event,
        created_at=summary.created_at,
    )


@corporation_router.get(
    "/activity",
    response_model=ActivityListResponse,
    dependencies=[Depends(require_permission("activity:read"))],
)
def list_activity(
    task_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=100),
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> ActivityListResponse:
    return ActivityListResponse(
        items=[
            _activity_response(summary)
            for summary in application_service.list_activity(
                limit=limit,
                task_id=task_id,
            )
        ]
    )


def _task_response(summary: TaskSummary) -> TaskResponse:
    return TaskResponse(
        id=summary.id,
        title=summary.title,
        description=summary.description,
        project_id=summary.project_id,
        status=summary.status,
        assigned_agent=summary.assigned_agent,
        required_role=summary.required_role,
        required_capability=summary.required_capability,
    )


@corporation_router.get(
    "/tasks",
    response_model=TaskListResponse,
    dependencies=[Depends(require_permission("task:read"))],
)
def list_tasks(
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> TaskListResponse:
    return TaskListResponse(
        items=[
            _task_response(summary)
            for summary in application_service.list_tasks()
        ]
    )


@corporation_router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_permission("task:read"))],
)
def get_task(
    task_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> TaskResponse:
    try:
        summary = application_service.get_task(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc
    return _task_response(summary)


@corporation_router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("task:create"))],
)
def create_task(
    task: TaskCreateRequest,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> TaskResponse:
    try:
        summary = application_service.create_task(
            title=task.title,
            description=task.description,
            project_id=task.project_id,
            agent_id=task.agent_id,
            role=task.role,
            capability=task.capability,
        )
    except ValueError as exc:
        if str(exc).startswith("Project not found:"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _task_response(summary)


@corporation_router.post(
    "/tasks/{task_id}/dry-run",
    response_model=TaskDryRunResponse,
    dependencies=[Depends(require_permission("task:read"))],
)
def dry_run_task(
    task_id: str,
    application_service: CorporationApplicationService = Depends(
        get_application_service
    ),
) -> TaskDryRunResponse:
    try:
        summary = application_service.dry_run_task(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc
    except RoutingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task cannot be routed with its current assignment",
        ) from exc
    return TaskDryRunResponse(
        task_id=summary.task_id,
        task_title=summary.task_title,
        task_description=summary.task_description,
        selected_agent_id=summary.selected_agent_id,
        selected_agent_name=summary.selected_agent_name,
        selected_agent_role=summary.selected_agent_role,
        selected_employee_id=summary.selected_employee_id,
        selected_employee_name=summary.selected_employee_name,
        provider=summary.provider,
        model=summary.model,
        routing_method=summary.routing_method,
        status=summary.status,
    )


def create_app(
    application_service: CorporationApplicationService | None = None,
    authentication_backend: AuthenticationBackend | None = None,
    documentation_source: DocumentationSource | None = None,
    updates_source: UpdatesSource | None = None,
    trusted_release_service: TrustedReleaseService | None = None,
    github_repository_inspection_service: GitHubRepositoryInspectionService | None = None,
    repository_study_service: RepositoryStudyService | None = None,
    maintenance_sandbox_image_policy: SandboxImagePolicy | None = None,
    maintenance_activation_root: Path | None = None,
    semantic_memory_service=None,
    documentation_review_service=None,
    capability_authorization_service=None,
    capability_grant_service=None,
    capability_audit_service=None,
    with_builtin_agent_team: bool = False,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        debug_chat_adapter_contract_self_check()
        if application_service is None:
            runtime = (create_corporation_runtime(with_builtin_agent_team=True)
                       if with_builtin_agent_team else create_corporation_runtime())
            application.state.application_service = runtime.application_service
        else:
            application.state.application_service = application_service
        restore_local_setup = getattr(application.state, "restore_local_first_run", None)
        if callable(restore_local_setup):
            restore_local_setup(application.state.application_service)
        if application.state.capability_approval_service is None:
            approval_factory = getattr(application.state.application_service, "capability_approvals", None)
            application.state.capability_approval_service = (
                approval_factory() if callable(approval_factory) else None)
        if hasattr(application.state.capability_approval_service, "set_audit_service"):
            application.state.capability_approval_service.set_audit_service(
                application.state.capability_audit_service)
        source = documentation_source
        if source is None:
            source = MarkdownDocumentationSource(
                Path(__file__).resolve().parents[2] / "corporation_docs"
            )
        application.state.documentation_service = DocumentationApplicationService(
            source
        )
        if documentation_review_service is None:
            from app.application.services.documentation_review import DocumentationReviewService
            application.state.documentation_review_service = DocumentationReviewService()
        else:
            application.state.documentation_review_service = documentation_review_service
        source_updates = updates_source
        if source_updates is None:
            source_updates = CuratedUpdatesManifest(
                Path(__file__).resolve().parents[2] / "corporation_updates.json"
            )
        application.state.updates_service = UpdatesApplicationService(source_updates)
        application.state.trusted_release_service = (
            trusted_release_service
            if trusted_release_service is not None
            else TrustedReleaseService(Path.cwd())
        )
        inspection_service = (
            GitHubRepositoryInspectionService()
            if github_repository_inspection_service is None
            else github_repository_inspection_service
        )
        application.state.github_repository_inspection_service = inspection_service
        application.state.repository_study_service = (
            RepositoryStudyService(inspection_service)
            if repository_study_service is None
            else repository_study_service
        )
        image_policy = (
            SandboxImagePolicy()
            if maintenance_sandbox_image_policy is None
            else maintenance_sandbox_image_policy
        )
        from .maintenance_experiments import MaintenanceExperimentService

        experiment_service = MaintenanceExperimentService(
            application.state.application_service,
            image_policy,
            activation_root=(
                Path(__file__).resolve().parents[2]
                if maintenance_activation_root is None
                else maintenance_activation_root
            ),
        )
        application.state.maintenance_experiment_service = experiment_service
        try:
            yield
        finally:
            experiment_service.close()

    application = FastAPI(
        title="ERSELMETZ AI API",
        version=BUILD_STAMP["version"],
        lifespan=lifespan,
    )
    application.state.authentication_backend = (
        RejectingAuthenticationBackend()
        if authentication_backend is None
        else authentication_backend
    )
    if capability_audit_service is None:
        from app.application.services.capability_audit import CapabilityAuditService
        application.state.capability_audit_service = CapabilityAuditService()
    else:
        application.state.capability_audit_service = capability_audit_service
    if capability_authorization_service is None:
        from app.application.services.capability_authorization import DEFAULT_CAPABILITY_AUTHORIZATION
        application.state.capability_authorization_service = DEFAULT_CAPABILITY_AUTHORIZATION
    else:
        application.state.capability_authorization_service = capability_authorization_service
    if capability_grant_service is None:
        from app.application.services.capability_grants import CapabilityGrantService
        application.state.capability_grant_service = CapabilityGrantService(
            application.state.capability_authorization_service)
    else:
        application.state.capability_grant_service = capability_grant_service
    if hasattr(application.state.capability_grant_service, "set_audit_service"):
        application.state.capability_grant_service.set_audit_service(application.state.capability_audit_service)
    approval_factory = getattr(application_service, "capability_approvals", None)
    application.state.capability_approval_service = (
        approval_factory() if callable(approval_factory) else None)
    application.state.semantic_memory_service = semantic_memory_service
    if semantic_memory_service is not None and hasattr(application_service, "configure_semantic_memory"):
        application_service.configure_semantic_memory(semantic_memory_service)
    application.mount(
        "/ui/static",
        WebUIStaticFiles(
            directory=str(Path(__file__).parent.parent / "webui" / "static")
        ),
        name="web-ui-static",
    )
    application.include_router(api_router)
    application.include_router(corporation_router)
    from .memory import router as memory_router
    application.include_router(memory_router)
    from .capability_grants import router as capability_grants_router
    application.include_router(capability_grants_router)
    from .capability_approvals import router as capability_approvals_router
    application.include_router(capability_approvals_router)
    from .system_monitoring import router as system_monitoring_router
    application.include_router(system_monitoring_router)
    from .capability_audit import router as capability_audit_router
    application.include_router(capability_audit_router)
    from .documentation_review import router as documentation_review_router
    application.include_router(documentation_review_router)
    from .maintenance_approvals import router as maintenance_approvals_router
    application.include_router(maintenance_approvals_router)
    from .maintenance_checkpoints import router as maintenance_checkpoints_router
    application.include_router(maintenance_checkpoints_router)
    from .maintenance_experiments import router as maintenance_experiments_router
    application.include_router(maintenance_experiments_router)
    from .github import router as github_router
    application.include_router(github_router)
    from .chat_history import router as chat_history_router
    application.include_router(chat_history_router)
    from .chat import router as chat_router
    application.include_router(chat_router)
    from .employee_chat import router as employee_chat_router
    application.include_router(employee_chat_router)
    from .task_dispatch import router as task_dispatch_router
    application.include_router(task_dispatch_router)
    from .structure_map import router as structure_map_router
    application.include_router(structure_map_router)
    application.include_router(web_ui_router)
    return application


app = create_app()
