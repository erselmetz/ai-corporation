from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class CorporationIdentityResponse(BaseModel):
    id: str
    name: str


class NodeIdentityResponse(BaseModel):
    id: str
    name: str


class CorporationStatusResponse(BaseModel):
    corporation: CorporationIdentityResponse
    node: NodeIdentityResponse


class DocumentationSummaryResponse(BaseModel):
    id: str
    title: str


class DocumentationListResponse(BaseModel):
    items: list[DocumentationSummaryResponse]


class DocumentationResponse(DocumentationSummaryResponse):
    content: str


class UpdateResponse(BaseModel):
    date: date
    type: Literal["development", "release"]
    title: str
    summary: str


class UpdatesListResponse(BaseModel):
    items: list[UpdateResponse]


class GitHubLatestReleaseResponse(BaseModel):
    tag_name: str
    name: str | None
    published_at: str | None
    html_url: str | None


class GitHubRepositoryInspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str
    repository_name: str
    repository_url: str
    discovered_at: datetime
    description: str | None
    default_branch: str | None
    language: str | None
    stars: int | None
    forks: int | None
    open_issues: int | None
    license_name: str | None
    license_spdx_id: str | None
    created_at: str | None
    updated_at: str | None
    pushed_at: str | None
    latest_release: GitHubLatestReleaseResponse | None
    readme_available: bool
    readme_size_bytes: int | None


class EmployeeResponse(BaseModel):
    id: str
    name: str
    role: str
    responsibilities: list[str]
    agent_id: str | None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]


class EmployeeCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    responsibilities: list[str] = Field(default_factory=list)

    @field_validator("id", "name", "role")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("responsibilities")
    @classmethod
    def require_non_blank_responsibilities(
        cls,
        responsibilities: list[str],
    ) -> list[str]:
        if any(not item.strip() for item in responsibilities):
            raise ValueError("Responsibilities cannot be blank")
        return responsibilities


class PositionRevisionResponse(BaseModel):
    revision: int
    title: str
    responsibilities: list[str]
    reports_to_position_id: str | None
    employee_id: str | None
    active: bool
    recorded_at: datetime


class PositionResponse(BaseModel):
    id: str
    title: str
    responsibilities: list[str]
    reports_to_position_id: str | None
    employee_id: str | None
    active: bool
    revision: int
    history: list[PositionRevisionResponse]


class PositionListResponse(BaseModel):
    items: list[PositionResponse]


class PositionFieldsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=64)
    responsibilities: list[str] = Field(min_length=1, max_length=20)
    reports_to_position_id: str | None = Field(default=None, max_length=256)
    employee_id: str | None = Field(default=None, max_length=256)

    @field_validator("title", mode="before")
    @classmethod
    def require_non_blank_title(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()

    @field_validator("reports_to_position_id", "employee_id", mode="before")
    @classmethod
    def normalize_optional_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("References cannot be blank")
        return value.strip()

    @field_validator("responsibilities")
    @classmethod
    def validate_responsibilities(cls, values: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError("Responsibilities cannot be blank")
        return [item.strip() for item in values]


class PositionCreateRequest(PositionFieldsRequest):
    pass


class PositionUpdateRequest(PositionFieldsRequest):
    expected_revision: int = Field(ge=1)


class PositionDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class PositionTemplatesResponse(BaseModel):
    items: list[str]


class EmployeeChatMessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    status: Literal["pending", "completed", "failed"]


class EmployeeChatConversationResponse(BaseModel):
    id: str
    employee_id: str
    agent_id: str
    status: Literal["open", "closed"]
    messages: list[EmployeeChatMessageResponse]


class EmployeeChatIdentityResponse(BaseModel):
    id: str
    name: str
    role: str


class EmployeeChatAgentResponse(BaseModel):
    id: str
    name: str
    role: str
    provider_id: str
    model_id: str


class EmployeeChatResponse(BaseModel):
    conversation: EmployeeChatConversationResponse
    employee: EmployeeChatIdentityResponse
    agent: EmployeeChatAgentResponse


class EmployeeChatListItemResponse(BaseModel):
    conversation_id: str
    employee: EmployeeChatIdentityResponse
    agent: EmployeeChatAgentResponse
    status: Literal["open", "closed"]


class EmployeeChatListResponse(BaseModel):
    items: list[EmployeeChatListItemResponse]


class AgentResponse(BaseModel):
    id: str
    name: str
    role: str
    provider: str
    model: str
    capabilities: list[str]


class AgentListResponse(BaseModel):
    items: list[AgentResponse]


class ProviderResponse(BaseModel):
    id: str
    type: str


class ProviderListResponse(BaseModel):
    items: list[ProviderResponse]


class ProviderCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    @field_validator("id", "name")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value


class ModelAssignmentResponse(BaseModel):
    agent_id: str
    provider_id: str
    model_id: str


class ModelAssignmentListResponse(BaseModel):
    items: list[ModelAssignmentResponse]


class ModelAssignmentRequest(BaseModel):
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)

    @field_validator("provider_id", "model_id")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""

    @field_validator("name")
    @classmethod
    def require_non_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name cannot be blank")
        return value


class ActivityResponse(BaseModel):
    id: int
    task_id: str
    event: str
    created_at: str


class ActivityListResponse(BaseModel):
    items: list[ActivityResponse]


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    project_id: str | None
    status: str
    assigned_agent: str | None
    required_role: str | None
    required_capability: str | None


class TaskListResponse(BaseModel):
    items: list[TaskResponse]


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    project_id: str | None = None
    agent_id: str | None = None
    role: str | None = None
    capability: str | None = None

    @field_validator("title", "description")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("project_id", "agent_id", "role", "capability")
    @classmethod
    def require_non_blank_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value cannot be blank")
        return value


class TaskDryRunResponse(BaseModel):
    task_id: str
    task_title: str
    task_description: str
    selected_agent_id: str
    selected_agent_name: str
    selected_agent_role: str
    selected_employee_id: str | None
    selected_employee_name: str | None
    provider: str | None
    model: str | None
    routing_method: str | None
    status: str


class TaskDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: StrictBool


class TaskDispatchResolutionRequest(TaskDispatchRequest):
    resolution: str = Field(min_length=1, max_length=1024)

    @field_validator("resolution")
    @classmethod
    def require_non_blank_resolution(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Resolution cannot be blank")
        return value


class TaskDispatchTaskStateResponse(BaseModel):
    title: str
    status: str
    result_recorded: bool
    error_recorded: bool


class TaskDispatchQueueEntryResponse(BaseModel):
    sequence: int
    id: str
    task_id: str
    state: Literal["queued", "claimed", "completed", "failed", "abandoned"]
    worker_id: str | None
    claim_id: str | None
    resolution: str | None
    created_at: str
    updated_at: str
    task: TaskDispatchTaskStateResponse


class TaskDispatchQueueResponse(BaseModel):
    items: list[TaskDispatchQueueEntryResponse]
    history_limit_reached: bool
