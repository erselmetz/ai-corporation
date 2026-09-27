from uuid import uuid4

from app.agents import AgentRegistry, EmployeeRegistry
from app.database import TaskLogger
from app.providers import ProviderRegistry

from .task import Task, TaskStatus
from .task_registry import TaskRegistry
from .router import TaskRouter, RoutingRequest, RoutingError
from .dry_run import DryRunResult

from .project_registry import ProjectRegistry


class Orchestrator:
    def __init__(
        self,
        agents: AgentRegistry,
        providers: ProviderRegistry,
        tasks: TaskRegistry,
        projects: ProjectRegistry,
        employees: EmployeeRegistry | None = None,
    ):
        self.agents = agents
        self.providers = providers
        self.tasks = tasks
        self.logger = TaskLogger()
        self.projects = projects
        self.employees = employees
        self.router = TaskRouter(agents, employees)

    def run_agent(self, agent_id: str, prompt: str) -> str:
        agent = self.agents.get(agent_id)

        provider = agent.resolve_provider(self.providers)

        return provider.generate(agent.model, prompt)

    def run_employee(self, employee: "Employee", prompt: str) -> str:
        """
        Execute a prompt using the AI agent assigned to the employee.
        """
        if employee.agent is None:
            raise RuntimeError(f"Employee '{employee.name}' has no assigned agent")
        
        return self.run_agent(employee.agent.id, prompt)

    def execute_task(
        self,
        task: Task,
        role: str | None = None,
        capability: str | None = None,
        dry_run: bool = False,
        agent_id: str | None = None,
    ) -> Task | DryRunResult:
        try:
            routing_task = task
            if agent_id:
                routing_task = Task(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    project_id=task.project_id,
                    assigned_agent=agent_id,
                    status=task.status,
                    result=task.result,
                    error=task.error,
                    required_role=task.required_role,
                    required_capability=task.required_capability,
                )

            routing_request = RoutingRequest(task=routing_task, role=role, capability=capability)
            agent, routing_method = self.router.route_with_method(routing_request)
            
            if not dry_run and task.assigned_agent != agent.id:
                task.assigned_agent = agent.id
                self.tasks.update(task)

            if dry_run:
                selected_employee = None
                if self.employees:
                    for emp in self.employees.all():
                        if emp.agent and emp.agent.id == agent.id:
                            selected_employee = emp
                            break
                return DryRunResult(
                    task_id=task.id,
                    task_title=task.title,
                    task_description=task.description,
                    selected_agent=agent,
                    selected_employee=selected_employee,
                    provider=agent.provider,
                    model=agent.model,
                    routing_method=routing_method,
                    status="ready"
                )

        except RoutingError as e:
            if dry_run:
                # For dry-run, we can't return a DryRunResult if routing failed.
                # We should probably raise the RoutingError or return a failed DryRunResult.
                # The requirements say "No matching route" should be tested.
                # I'll let the RoutingError bubble up or handle it.
                # Let's handle it by raising it so the test can catch it.
                raise e
            
            error = str(e)
            task.status = TaskStatus.FAILED
            task.error = error
            task.result = None
            self.tasks.update(task)
            self.logger.log(task.id, "TASK_FAILED", error)
            return task

        task.status = TaskStatus.RUNNING
        task.error = None
        self.tasks.update(task)

        self.logger.log(
            task.id,
            "TASK_STARTED",
            "Task execution started.",
        )

        try:
            result = self.run_agent(
                task.assigned_agent,
                task.description,
            )

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.error = None

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.result = None

        self.tasks.update(task)

        if task.status == TaskStatus.COMPLETED:
            self.logger.log(
                task.id,
                "TASK_COMPLETED",
                "Task execution completed successfully.",
            )
        else:
            self.logger.log(
                task.id,
                "TASK_FAILED",
                task.error or "Task execution failed.",
            )

        return task
    
    def create_task(
        self,
        title: str,
        description: str,
        project_id: str,
        agent_id: str | None = None,
        role: str | None = None,
        capability: str | None = None,
    ) -> Task:
        if not self.projects.exists(project_id):
            raise ValueError(f"Project not found: {project_id}")
        if sum(value is not None for value in (agent_id, role, capability)) > 1:
            raise ValueError("Routing options are mutually exclusive.")
        for name, value in (
            ("agent_id", agent_id),
            ("role", role),
            ("capability", capability),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{name} cannot be empty.")
            
        task = Task(
            id=f"TASK-{uuid4().hex[:8].upper()}",
            title=title,
            description=description,
            project_id=project_id,
            assigned_agent=agent_id,
            required_role=role,
            required_capability=capability,
        )

        self.tasks.register(task)

        self.logger.log(
            task.id,
            "TASK_CREATED",
            f"Task created: {task.title}",
        )

        return task

    def remember_agent(self, agent_id: str, key: str, value: str) -> None:
        agent = self.agents.get(agent_id)
        agent.remember(key, value)

    def recall_agent(self, agent_id: str, key: str) -> str | None:
        agent = self.agents.get(agent_id)

        return agent.recall(key)

    def forget_agent(self, agent_id: str, key: str) -> None:
        agent = self.agents.get(agent_id)

        agent.forget(key)