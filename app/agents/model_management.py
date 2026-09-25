from app.agents import AgentRegistry, Agent
from app.providers import ProviderRegistry

class ModelManagement:
    """
    Service layer for managing model assignments for AI Agents.
    Allows updating the provider and model used by an Agent.
    """
    def __init__(self, agent_registry: AgentRegistry, provider_registry: ProviderRegistry):
        self.agent_registry = agent_registry
        self.provider_registry = provider_registry

    def assign_model(self, agent_id: str, provider_id: str, model: str) -> Agent:
        """
        Assigns a provider and model to an Agent.
        Validates existence of Agent and Provider before applying changes.
        """
        if not model or not model.strip():
            raise ValueError("Model identifier cannot be empty")

        # Atomic validation
        agent = self.agent_registry.get(agent_id)
        if not self.provider_registry.exists(provider_id):
            raise ValueError(f"Provider not found: {provider_id}")

        # Update the Agent object
        agent.provider = provider_id
        agent.model = model
        
        return agent

    def get_model(self, agent_id: str) -> dict:
        """
        Retrieves the current provider and model assignment for an Agent.
        """
        agent = self.agent_registry.get(agent_id)
        return {
            "provider": agent.provider,
            "model": agent.model
        }

    def replace_model(self, agent_id: str, provider_id: str, model: str) -> Agent:
        """
        Replaces the existing model/provider assignment for an Agent.
        Logic is identical to assign_model as it updates the existing Agent.
        """
        return self.assign_model(agent_id, provider_id, model)
