from dataclasses import dataclass
from uuid import uuid4

from app.agents import Agent, Employee, EmployeeManagement, ModelManagement
from app.corporation import Corporation
from app.node import Node
from app.orchestrator import Orchestrator, Project, Task
from app.orchestrator.dry_run import DryRunResult
from app.providers import ProviderManagement


@dataclass(frozen=True)
class CorporationStatusSummary:
    corporation_id: str
    corporation_name: str
    node_id: str
    node_name: str


@dataclass(frozen=True)
class AgentSummary:
    id: str
    name: str
    role: str
    provider: str
    model: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class EmployeeSummary:
    id: str
    name: str
    role: str
    responsibilities: tuple[str, ...]
    agent_id: str | None


@dataclass(frozen=True)
class ProjectSummary:
    id: str
    name: str
    description: str
    status: str


@dataclass(frozen=True)
class ActivitySummary:
    id: int
    task_id: str
    event: str
    created_at: str


@dataclass(frozen=True)
class ProviderSummary:
    id: str
    type_name: str


@dataclass(frozen=True)
class ModelSummary:
    provider: str
    model: str


@dataclass(frozen=True)
class ModelAssignmentSummary:
    agent_id: str
    provider_id: str
    model_id: str


@dataclass(frozen=True)
class TaskSummary:
    id: str
    title: str
    description: str
    project_id: str | None
    status: str
    result: str | None
    error: str | None
    assigned_agent: str | None
    required_role: str | None
    required_capability: str | None


@dataclass(frozen=True)
class DryRunSummary:
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


class CorporationApplicationService:
    """Interface-neutral use cases coordinating existing Corporation services."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        corporation: Corporation | None = None,
        node: Node | None = None,
    ):
        self._orchestrator = orchestrator
        self._corporation_chat = None
        self._resource_manager = None
        self._controlled_execution = None
        self._corporation = corporation
        self._node = node

    def assess_model_resources(self, candidates):
        from app.resources.assessment import assess_model_resources
        snapshot = self._resource_manager.snapshot() if self._resource_manager is not None else None
        return assess_model_resources(candidates, snapshot=snapshot,
                                      registered_providers=self._orchestrator.providers.all())

    def execute_controlled_task(self, task_id):
        self.resource_manager()  # Reject missing configuration before touching Tasks.
        return self._task_summary(self._controlled_execution.execute(task_id))

    def execution_queue(self):
        if self._corporation is None:
            raise RuntimeError("Corporation identity is not configured")
        return self._orchestrator.execution_queue(self._corporation.id)

    def resource_manager(self, limits=None):
        from app.resources import ResourceManager
        if self._resource_manager is None:
            if limits is None:
                raise RuntimeError("Resource limits are not configured")
            self._resource_manager = ResourceManager(limits, self._orchestrator.providers)
            from .controlled_execution import ControlledExecution
            self._controlled_execution = ControlledExecution(self._orchestrator, self._resource_manager)
        elif limits is not None:
            raise ValueError("Resource manager is already configured")
        return self._resource_manager

    def task_planning(self):
        from .task_planning import TaskPlanningService
        return TaskPlanningService(self._orchestrator, self.context_retrieval())

    def context_retrieval(self):
        from .context_retrieval import ContextRetrievalService
        return ContextRetrievalService(self.memory_management())

    def memory_management(self):
        from .memory_management import MemoryManagementService
        return MemoryManagementService(self._orchestrator, self._corporation.id if self._corporation else None)

    def corporation_knowledge(self):
        if self._corporation is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        from .corporation_knowledge import CorporationKnowledgeService
        return CorporationKnowledgeService(self._corporation.id, self._orchestrator)

    def project_knowledge(self):
        from .project_knowledge import ProjectKnowledgeService
        return ProjectKnowledgeService(self._orchestrator)

    def corporation_chat(self):
        """Local-only facade; no HTTP exposure or new permission grant."""
        if self._corporation is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        if self._corporation_chat is None:
            from .corporation_chat import CorporationChatService
            self._corporation_chat = CorporationChatService(self._corporation.id, self._orchestrator)
        return self._corporation_chat

    def get_corporation_status(self) -> CorporationStatusSummary:
        if self._corporation is None or self._node is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        return CorporationStatusSummary(
            corporation_id=self._corporation.id,
            corporation_name=self._corporation.name,
            node_id=self._node.id,
            node_name=self._node.name,
        )

    def list_agents(self) -> list[AgentSummary]:
        return [
            self._agent_summary(agent)
            for agent in self._orchestrator.agents.all()
        ]

    def get_agent(self, agent_id: str) -> AgentSummary:
        return self._agent_summary(self._orchestrator.agents.get(agent_id))

    def list_employees(self) -> list[EmployeeSummary]:
        return [
            self._employee_summary(employee)
            for employee in self._employee_management().list_employees()
        ]

    def get_employee(self, employee_id: str) -> EmployeeSummary:
        employee = self._employee_management().get_employee(employee_id)
        return self._employee_summary(employee)

    def create_employee(
        self,
        employee_id: str,
        name: str,
        role: str,
        responsibilities: list[str],
    ) -> EmployeeSummary:
        employee = self._employee_management().create_employee(
            employee_id, name, role, responsibilities
        )
        return self._employee_summary(employee)

    def remove_employee(self, employee_id: str) -> None:
        self._employee_management().remove_employee(employee_id)

    def list_projects(self) -> list[ProjectSummary]:
        return [
            self._project_summary(project)
            for project in self._orchestrator.projects.all()
        ]

    def get_project(self, project_id: str) -> ProjectSummary:
        return self._project_summary(self._orchestrator.projects.get(project_id))

    def create_project(
        self,
        name: str,
        description: str = "",
    ) -> ProjectSummary:
        project = Project(
            id=f"PROJECT-{uuid4().hex[:8].upper()}",
            name=name,
            description=description,
        )
        self._orchestrator.projects.register(project)
        return self._project_summary(project)

    def list_activity(
        self,
        limit: int = 100,
        task_id: str | None = None,
    ) -> list[ActivitySummary]:
        return [
            ActivitySummary(
                id=record["id"],
                task_id=record["task_id"],
                event=record["event"],
                created_at=record["created_at"],
            )
            for record in self._orchestrator.logger.list_activity(
                limit=limit,
                task_id=task_id,
            )
        ]

    def list_providers(self) -> list[ProviderSummary]:
        return [
            ProviderSummary(id=provider_id, type_name=provider.__class__.__name__)
            for provider_id, provider in self._provider_management()
            .list_providers()
            .items()
        ]

    def get_provider(self, provider_id: str) -> ProviderSummary:
        provider = self._provider_management().get_provider(provider_id)
        return ProviderSummary(
            id=provider_id,
            type_name=provider.__class__.__name__,
        )

    def create_provider(self, provider_id: str, name: str) -> ProviderSummary:
        provider = self._provider_management().create_provider(provider_id, name)
        return ProviderSummary(
            id=provider_id,
            type_name=provider.__class__.__name__,
        )

    def remove_provider(self, provider_id: str) -> None:
        self._provider_management().remove_provider(provider_id)

    def list_models(self) -> list[ModelAssignmentSummary]:
        return [
            ModelAssignmentSummary(
                agent_id=agent.id,
                provider_id=agent.provider,
                model_id=agent.model,
            )
            for agent in self._orchestrator.agents.all()
        ]

    def get_model_assignment(self, agent_id: str) -> ModelAssignmentSummary:
        agent = self._orchestrator.agents.get(agent_id)
        return ModelAssignmentSummary(
            agent_id=agent.id,
            provider_id=agent.provider,
            model_id=agent.model,
        )

    def get_model(self, agent_id: str) -> ModelSummary:
        assignment = self._model_management().get_model(agent_id)
        return ModelSummary(
            provider=assignment["provider"],
            model=assignment["model"],
        )

    def replace_model(
        self,
        agent_id: str,
        provider_id: str,
        model: str,
    ) -> ModelAssignmentSummary:
        agent = self._model_management().replace_model(
            agent_id,
            provider_id,
            model,
        )
        return ModelAssignmentSummary(
            agent_id=agent.id,
            provider_id=agent.provider,
            model_id=agent.model,
        )

    def assign_model(
        self,
        agent_id: str,
        provider_id: str,
        model: str,
    ) -> AgentSummary:
        agent = self._model_management().assign_model(agent_id, provider_id, model)
        return AgentSummary(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            provider=agent.provider,
            model=agent.model,
            capabilities=tuple(agent.capabilities),
        )

    def list_tasks(self) -> list[TaskSummary]:
        return [
            self._task_summary(task)
            for task in self._orchestrator.tasks.all()
        ]

    def get_task(self, task_id: str) -> TaskSummary:
        return self._task_summary(self._orchestrator.tasks.get(task_id))

    def create_task(
        self,
        title: str,
        description: str,
        project_id: str | None = None,
        agent_id: str | None = None,
        role: str | None = None,
        capability: str | None = None,
    ) -> TaskSummary:
        resolved_project_id = (
            self._default_project_id() if project_id is None else project_id
        )
        routing = {
            key: value
            for key, value in (
                ("agent_id", agent_id),
                ("role", role),
                ("capability", capability),
            )
            if value is not None
        }
        task = self._orchestrator.create_task(
            title=title,
            description=description,
            project_id=resolved_project_id,
            **routing,
        )
        return self._task_summary(task)

    def execute_task(
        self,
        task_id: str,
        role: str | None = None,
        capability: str | None = None,
        agent_id: str | None = None,
    ) -> TaskSummary:
        task = self._orchestrator.tasks.get(task_id)
        routing = {
            key: value
            for key, value in (
                ("role", role),
                ("capability", capability),
                ("agent_id", agent_id),
            )
            if value is not None
        }
        result = self._orchestrator.execute_task(
            task,
            **routing,
        )
        if not isinstance(result, Task):
            raise RuntimeError("Task execution returned an unexpected result")
        return self._task_summary(result)

    def dry_run_task(
        self,
        task_id: str,
        role: str | None = None,
        capability: str | None = None,
        agent_id: str | None = None,
    ) -> DryRunSummary:
        task = self._orchestrator.tasks.get(task_id)
        routing = {
            key: value
            for key, value in (
                ("role", role),
                ("capability", capability),
                ("agent_id", agent_id),
            )
            if value is not None
        }
        result = self._orchestrator.execute_task(
            task,
            dry_run=True,
            **routing,
        )
        if not isinstance(result, DryRunResult):
            raise RuntimeError("Dry-run returned an unexpected result")

        employee = result.selected_employee
        agent = result.selected_agent
        return DryRunSummary(
            task_id=result.task_id,
            task_title=result.task_title,
            task_description=result.task_description,
            selected_agent_id=agent.id,
            selected_agent_name=agent.name,
            selected_agent_role=agent.role,
            selected_employee_id=employee.id if employee else None,
            selected_employee_name=employee.name if employee else None,
            provider=result.provider,
            model=result.model,
            routing_method=result.routing_method,
            status=result.status,
        )

    def _employee_management(self) -> EmployeeManagement:
        if self._orchestrator.employees is None:
            raise RuntimeError("Employee management is not configured")
        return EmployeeManagement(self._orchestrator.employees)

    def _provider_management(self) -> ProviderManagement:
        return ProviderManagement(self._orchestrator.providers)

    def _model_management(self) -> ModelManagement:
        return ModelManagement(
            self._orchestrator.agents,
            self._orchestrator.providers,
        )

    def _default_project_id(self) -> str:
        projects = self._orchestrator.projects.all()
        if projects:
            return projects[0].id

        project = Project(
            id="default_proj",
            name="General",
            description="Default Project",
            status="active",
        )
        self._orchestrator.projects.register(project)
        return project.id

    @staticmethod
    def _employee_summary(employee: Employee) -> EmployeeSummary:
        return EmployeeSummary(
            id=employee.id,
            name=employee.name,
            role=employee.role,
            responsibilities=tuple(employee.responsibilities),
            agent_id=employee.agent.id if employee.agent else None,
        )

    @staticmethod
    def _agent_summary(agent: Agent) -> AgentSummary:
        return AgentSummary(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            provider=agent.provider,
            model=agent.model,
            capabilities=tuple(agent.capabilities),
        )

    @staticmethod
    def _task_summary(task: Task) -> TaskSummary:
        return TaskSummary(
            id=task.id,
            title=task.title,
            description=task.description,
            project_id=task.project_id,
            status=task.status.value,
            result=task.result,
            error=task.error,
            assigned_agent=task.assigned_agent,
            required_role=task.required_role,
            required_capability=task.required_capability,
        )

    @staticmethod
    def _project_summary(project: Project) -> ProjectSummary:
        return ProjectSummary(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
        )
