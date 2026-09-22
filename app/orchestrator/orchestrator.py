from app.agents import AgentRegistry
from app.providers import ProviderRegistry

from .task import Task, TaskStatus
from .task_registry import TaskRegistry

from uuid import uuid4


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

        return task
    
    def create_task(self, title: str, description: str, agent_id: str | None = None) -> Task:
        task = Task(
            id=f"TASK-{uuid4().hex[:8].upper()}",
            title=title,
            description=description,
            assigned_agent=agent_id,
        )

        self.tasks.register(task)

        return task