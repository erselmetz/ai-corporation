from dataclasses import dataclass, field
from .agent import Agent

@dataclass
class Employee:
    """
    Represents an AI Employee within the Corporation.
    An Employee has an organizational identity and is associated with a technical Agent.
    """
    id: str
    name: str
    role: str
    responsibilities: list[str] = field(default_factory=list)
    agent: Agent | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Employee id cannot be empty")
        if not self.name:
            raise ValueError("Employee name cannot be empty")
        if not self.role:
            raise ValueError("Employee role cannot be empty")
        if not all(isinstance(r, str) and r.strip() for r in self.responsibilities):
            raise ValueError("All responsibilities must be non-empty strings")

    def assign_agent(self, agent: Agent) -> None:
        """Assigns a technical AI agent to this employee."""
        self.agent = agent

    def describe(self) -> str:
        """Returns a description of the employee and their associated agent."""
        agent_desc = self.agent.describe() if self.agent else "No agent assigned"
        return (
            f"Employee: {self.name} | Role: {self.role} | "
            f"Responsibilities: {', '.join(self.responsibilities)} | "
            f"Agent: {agent_desc}"
        )
