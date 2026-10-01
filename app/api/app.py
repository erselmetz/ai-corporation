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
    ProjectSummary,
    TaskSummary,
)
from app.documentation import MarkdownDocumentationSource
from app.runtime import create_corporation_runtime
from app.webui import web_ui_router
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
    TaskCreateRequest,
    TaskDryRunResponse,
    TaskListResponse,
    TaskResponse,
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
    return {"application": "ERSELMETZ AI CORPORATION API"}


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_application_service(request: Request) -> CorporationApplicationService:
    """FastAPI dependency for interface routes using application use cases."""
    return request.app.state.application_service


def get_documentation_service(
    request: Request,
) -> DocumentationApplicationService:
    return request.app.state.documentation_service


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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
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
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        if application_service is None:
            runtime = create_corporation_runtime()
            application.state.application_service = runtime.application_service
        else:
            application.state.application_service = application_service
        source = documentation_source
        if source is None:
            source = MarkdownDocumentationSource(
                Path(__file__).resolve().parents[2] / "corporation_docs"
            )
        application.state.documentation_service = DocumentationApplicationService(
            source
        )
        yield

    application = FastAPI(
        title="ERSELMETZ AI CORPORATION API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.authentication_backend = (
        RejectingAuthenticationBackend()
        if authentication_backend is None
        else authentication_backend
    )
    application.mount(
        "/ui/static",
        WebUIStaticFiles(
            directory=str(Path(__file__).parent.parent / "webui" / "static")
        ),
        name="web-ui-static",
    )
    application.include_router(api_router)
    application.include_router(corporation_router)
    application.include_router(web_ui_router)
    return application


app = create_app()
