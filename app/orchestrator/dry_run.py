from dataclasses import dataclass
from app.agents import Agent, Employee

@dataclass
class DryRunResult:
    """
    Structured result of a dry-run execution.
    Contains the orchestration path without actually executing the AI model.
    """
    task_id: str
    task_title: str
    task_description: str
    selected_agent: Agent
    selected_employee: Employee | None = None
    provider: str | None = None
    model: str | None = None
    routing_method: str | None = None
    status: str = "ready"

    def __str__(self) -> str:
        return (
            f"DRY RUN RESULT\n"
            f"Task: [{self.task_id}] {self.task_title}\n"
            f"Description: {self.task_description}\n"
            f"Employee: {self.selected_employee.name if self.selected_employee else 'N/A'}\n"
            f"Agent: {self.selected_agent.name} ({self.selected_agent.role})\n"
            f"Provider: {self.provider}\n"
            f"Model: {self.model}\n"
            f"Route: {self.routing_method}\n"
            f"Status: {self.status}"
        )
