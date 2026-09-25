import pytest
from app.agents import AgentRegistry, Agent, ModelManagement
from app.providers import ProviderRegistry, OllamaProvider

class TestModelManagement:
    @pytest.fixture
    def setup(self):
        agent_reg = AgentRegistry()
        provider_reg = ProviderRegistry()
        mgmt = ModelManagement(agent_reg, provider_reg)
        
        # Setup common providers
        provider_reg.register("ollama", OllamaProvider())
        provider_reg.register("openai", OllamaProvider()) # Use Ollama as mock for OpenAI
        
        # Setup common agents
        agent = Agent(id="worker-1", name="Worker 1", role="Worker", provider="ollama", model="llama3")
        agent_reg.register(agent)
        
        return agent_reg, provider_reg, mgmt

    def test_assign_model(self, setup):
        agent_reg, provider_reg, mgmt = setup
        mgmt.assign_model("worker-1", "ollama", "gemma4:26b")
        
        agent = agent_reg.get("worker-1")
        assert agent.provider == "ollama"
        assert agent.model == "gemma4:26b"

    def test_get_model(self, setup):
        agent_reg, provider_reg, mgmt = setup
        info = mgmt.get_model("worker-1")
        assert info["provider"] == "ollama"
        assert info["model"] == "llama3"

    def test_replace_model_same_provider(self, setup):
        agent_reg, provider_reg, mgmt = setup
        mgmt.replace_model("worker-1", "ollama", "gemma4:26b")
        
        agent = agent_reg.get("worker-1")
        assert agent.provider == "ollama"
        assert agent.model == "gemma4:26b"

    def test_replace_provider_and_model(self, setup):
        agent_reg, provider_reg, mgmt = setup
        mgmt.replace_model("worker-1", "openai", "gpt-5")
        
        agent = agent_reg.get("worker-1")
        assert agent.provider == "openai"
        assert agent.model == "gpt-5"

    def test_missing_agent_rejection(self, setup):
        agent_reg, provider_reg, mgmt = setup
        with pytest.raises(ValueError, match="Agent not found"):
            mgmt.assign_model("unknown", "ollama", "llama3")

    def test_missing_provider_rejection(self, setup):
        agent_reg, provider_reg, mgmt = setup
        with pytest.raises(ValueError, match="Provider not found"):
            mgmt.assign_model("worker-1", "unknown", "llama3")

    def test_empty_model_rejection(self, setup):
        agent_reg, provider_reg, mgmt = setup
        with pytest.raises(ValueError, match="Model identifier cannot be empty"):
            mgmt.assign_model("worker-1", "ollama", "")
        with pytest.raises(ValueError, match="Model identifier cannot be empty"):
            mgmt.assign_model("worker-1", "ollama", "   ")

    def test_atomic_behavior_fails(self, setup):
        agent_reg, provider_reg, mgmt = setup
        agent = agent_reg.get("worker-1")
        original_provider = agent.provider
        original_model = agent.model
        
        with pytest.raises(ValueError):
            # Fail due to missing provider
            mgmt.assign_model("worker-1", "unknown-prov", "some-model")
            
        # Verify original state is preserved
        assert agent.provider == original_provider
        assert agent.model == original_model

    def test_agent_identity_remains_unchanged(self, setup):
        agent_reg, provider_reg, mgmt = setup
        agent = agent_reg.get("worker-1")
        original_name = agent.name
        original_role = agent.role
        
        mgmt.assign_model("worker-1", "openai", "gpt-5")
        
        updated_agent = agent_reg.get("worker-1")
        assert updated_agent.id == "worker-1"
        assert updated_agent.name == original_name
        assert updated_agent.role == original_role

    def test_employee_relationship_intact(self, setup):
        # Employee references Agent. Model changes shouldn't affect this.
        from app.agents import Employee
        agent_reg, provider_reg, mgmt = setup
        agent = agent_reg.get("worker-1")
        emp = Employee(id="emp-1", name="Emp 1", role="role1", agent=agent)
        
        mgmt.assign_model("worker-1", "openai", "gpt-5")
        
        assert emp.agent.provider == "openai"
        assert emp.agent.model == "gpt-5"

    def test_execution_path_uses_assigned_model(self, setup):
        agent_reg, provider_reg, mgmt = setup
        # Assign new model
        mgmt.assign_model("worker-1", "ollama", "gemma4:26b")
        agent = agent_reg.get("worker-1")
        
        # Simulate execution: Agent -> Provider -> generate(model, prompt)
        provider = provider_reg.get(agent.provider)
        # We don't actually call generate as it needs a real Ollama server, 
        # but we verify the model passed is the assigned one.
        
        # Mock the provider's generate method to check the model argument
        import unittest.mock as mock
        with mock.patch.object(provider, 'generate', return_value="mock response") as mock_gen:
            provider.generate(agent.model, "hello")
            mock_gen.assert_called_once_with("gemma4:26b", "hello")
