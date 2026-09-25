import pytest
from app.providers import ProviderRegistry, ProviderManagement, AIProvider, OllamaProvider
from app.agents import Agent, AgentRegistry

class TestProviderManagement:
    @pytest.fixture
    def setup(self):
        registry = ProviderRegistry()
        mgmt = ProviderManagement(registry)
        agent_reg = AgentRegistry()
        return registry, mgmt, agent_reg

    def test_create_provider(self, setup):
        registry, mgmt, _ = setup
        provider = mgmt.create_provider("ollama", "Ollama Local")
        assert isinstance(provider, AIProvider)
        assert registry.exists("ollama")

    def test_get_provider(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_provider("openai", "OpenAI")
        provider = mgmt.get_provider("openai")
        assert provider is not None

    def test_list_providers(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_provider("p1", "Prov 1")
        mgmt.create_provider("p2", "Prov 2")
        providers = mgmt.list_providers()
        assert len(providers) == 2

    def test_remove_provider(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_provider("p1", "Prov 1")
        mgmt.remove_provider("p1")
        assert not registry.exists("p1")

    def test_duplicate_provider_rejection(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_provider("p1", "Prov 1")
        with pytest.raises(ValueError, match="Provider already registered"):
            mgmt.create_provider("p1", "Prov 1 Duplicate")

    def test_missing_provider_handling(self, setup):
        registry, mgmt, _ = setup
        with pytest.raises(ValueError, match="Provider not found"):
            mgmt.get_provider("none")
        with pytest.raises(ValueError, match="Provider not found"):
            mgmt.remove_provider("none")

    def test_invalid_field_validation(self, setup):
        registry, mgmt, _ = setup
        with pytest.raises(ValueError, match="Provider ID cannot be empty"):
            mgmt.create_provider("", "Name")
        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            mgmt.create_provider("id", "")

    def test_removal_does_not_delete_agent(self, setup):
        registry, mgmt, agent_reg = setup
        # Create provider
        mgmt.create_provider("ollama", "Ollama")
        # Create agent referencing this provider
        agent = Agent(id="a1", name="Agent 1", role="role1", provider="ollama", model="llama3")
        agent_reg.register(agent)
        
        # Remove provider
        mgmt.remove_provider("ollama")
        
        # Agent should still exist
        assert agent_reg.exists("a1")
        # But provider resolution should now fail
        with pytest.raises(ValueError, match="Provider not found"):
            registry.get("ollama")
