from dataclasses import dataclass
from app.agents import Agent, AgentRegistry, EmployeeRegistry
from app.orchestrator.task import Task

class RoutingError(Exception):
    """Raised when no suitable agent can be found for a task."""
    pass

@dataclass
class RoutingRequest:
    task: Task
    role: str | None = None
    capability: str | None = None

class TaskRouter:
    """
    Deterministic task router for ERSELMETZ AI CORPORATION.
    Decides WHO should handle the task based on priority rules.
    """
    def __init__(self, agent_registry: AgentRegistry, employee_registry: EmployeeRegistry | None = None):
        self.agent_registry = agent_registry
        self.employee_registry = employee_registry

    def route(self, request: RoutingRequest) -> Agent:
        agent, _ = self.route_with_method(request)
        return agent

    def route_with_method(self, request: RoutingRequest) -> tuple[Agent, str]:
        """
        Route a task to a suitable Agent based on priority:
        1. Explicit assigned_agent
        2. Employee Role
        3. Agent Capability
        """
        task = request.task
        if request.role is not None or request.capability is not None:
            role = request.role
            capability = request.capability
        else:
            role = task.required_role
            capability = task.required_capability

        # 1. Explicit Agent (Highest Priority)
        if task.assigned_agent:
            if self.agent_registry.exists(task.assigned_agent):
                return self.agent_registry.get(task.assigned_agent), "explicit_agent"
            else:
                # If explicitly assigned but not found, we treat it as a routing error
                # because we should not override an explicit assignment with a guess.
                raise RoutingError(f"Explicitly assigned agent '{task.assigned_agent}' not found.")

        # 2. Employee Role
        if role and self.employee_registry:
            employees = self.employee_registry.find_by_role(role)
            if employees:
                # Return the first employee's agent
                employee = employees[0]
                if employee.agent:
                    return employee.agent, "employee_role"
                else:
                    raise RoutingError(f"Employee found for role '{role}', but no agent is assigned to them.")

        # 3. Capability-based routing
        if capability:
            agents = self.agent_registry.find_by_capability(capability)
            if agents:
                # Return the first agent with the capability
                return agents[0], "capability"

        # 4. No matching agent
        raise RoutingError(
            f"No suitable agent found for task '{task.id}'. "
            f"Requested role: {role}, Requested capability: {capability}"
        )
