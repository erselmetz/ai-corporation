from contextlib import contextmanager
from threading import RLock

from .agent import Agent


class AgentAssignmentBusy(RuntimeError):
    """An Agent is executing or another assignment change is in progress."""


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._execution_lock = RLock()
        self._active_runs: dict[str, int] = {}
        self._configuring: set[str] = set()

    @contextmanager
    def execution(self, agent_id: str):
        with self._execution_lock:
            if agent_id in self._configuring:
                raise AgentAssignmentBusy("Agent connection is changing")
            self._active_runs[agent_id] = self._active_runs.get(agent_id, 0) + 1
        try:
            yield
        finally:
            with self._execution_lock:
                active = self._active_runs[agent_id] - 1
                if active:
                    self._active_runs[agent_id] = active
                else:
                    del self._active_runs[agent_id]

    @contextmanager
    def assignment_change(self, agent_id: str):
        with self._execution_lock:
            if self._active_runs.get(agent_id, 0) or agent_id in self._configuring:
                raise AgentAssignmentBusy("Agent has active work; wait before changing its connection")
            self._configuring.add(agent_id)
        try:
            yield
        finally:
            with self._execution_lock:
                self._configuring.remove(agent_id)

    def register(self, agent: Agent) -> None:
        if not isinstance(agent, Agent):
            raise TypeError("Only Agent instances can be registered")

        if agent.id in self._agents:
            raise ValueError(f"Agent already registered: {agent.id}")

        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> Agent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise ValueError(f"Agent not found: {agent_id}")

    def all(self) -> list[Agent]:
        return list(self._agents.values())

    def exists(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def find_by_role(self, role: str) -> list[Agent]:
        return [agent for agent in self._agents.values() if agent.role == role]

    def find_by_capability(self, capability: str) -> list[Agent]:
        return [agent for agent in self._agents.values() if capability in agent.capabilities]