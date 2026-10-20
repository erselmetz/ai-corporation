from contextlib import contextmanager
from threading import RLock
from datetime import datetime, timezone

from .agent import Agent


class AgentAssignmentBusy(RuntimeError):
    """An Agent is executing or another assignment change is in progress."""


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._execution_lock = RLock()
        self._active_runs: dict[str, int] = {}
        self._configuring: set[str] = set()
        self._last_active: dict[str, str] = {}
        self._last_failed: set[str] = set()

    @contextmanager
    def execution(self, agent_id: str):
        with self._execution_lock:
            if agent_id in self._configuring:
                raise AgentAssignmentBusy("Agent connection is changing")
            agent = self._agents.get(agent_id)
            if agent is not None and agent.paused:
                raise AgentAssignmentBusy("Agent is paused by the owner")
            self._active_runs[agent_id] = self._active_runs.get(agent_id, 0) + 1
        try:
            yield
        except Exception:
            with self._execution_lock:
                self._last_failed.add(agent_id)
                self._last_active[agent_id] = datetime.now(timezone.utc).isoformat()
            raise
        else:
            with self._execution_lock:
                self._last_failed.discard(agent_id)
                self._last_active[agent_id] = datetime.now(timezone.utc).isoformat()
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

    def is_executing(self, agent_id: str) -> bool:
        with self._execution_lock:
            return self._active_runs.get(agent_id, 0) > 0

    def last_active(self, agent_id: str) -> str | None:
        with self._execution_lock:
            return self._last_active.get(agent_id)

    def last_failed(self, agent_id: str) -> bool:
        with self._execution_lock:
            return agent_id in self._last_failed
