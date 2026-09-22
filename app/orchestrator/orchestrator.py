from uuid import uuid4

from app.agents import AgentRegistry
from app.database import TaskLogger
from app.providers import ProviderRegistry

from .task import Task, TaskStatus
from .task_registry import TaskRegistry


class Orchestrator:
    def __init__(
        self,
        agents: AgentRegistry,
        providers: ProviderRegistry,
        tasks: TaskRegistry,
    ):
        self.agents = agents
        self.providers = providers
        self.tasks = tasks
        self.logger = TaskLogger()

    def run_agent(self, agent_id: str, prompt: str) -> str:
        agent = self.agents.get(agent_id)

        provider = agent.resolve_provider(self.providers)

        return provider.generate(prompt)

    def execute_task(self, task: Task) -> Task:
        if not task.assigned_agent:
            task.status = TaskStatus.FAILED
            task.error = "Task has no assigned agent."
            self.tasks.update(task)
            return task

        task.status = TaskStatus.RUNNING
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

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)

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
    
    def create_task(self, title: str, description: str, agent_id: str | None = None) -> Task:
        task = Task(
            id=f"TASK-{uuid4().hex[:8].upper()}",
            title=title,
            description=description,
            assigned_agent=agent_id,
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