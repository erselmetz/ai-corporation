from pydantic import BaseModel, ConfigDict, Field, field_validator


class CorporationIdentityResponse(BaseModel):
    id: str
    name: str


class NodeIdentityResponse(BaseModel):
    id: str
    name: str


class CorporationStatusResponse(BaseModel):
    corporation: CorporationIdentityResponse
    node: NodeIdentityResponse


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
