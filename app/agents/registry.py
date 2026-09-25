from .agent import Agent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}

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