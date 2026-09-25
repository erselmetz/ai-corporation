from .registry import ProviderRegistry
from .base import AIProvider
from .ollama import OllamaProvider

class ProviderManagement:
    """
    Service layer for managing AI Providers within the Corporation.
    Handles the business logic of creating, retrieving, listing, and removing providers.
    """
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    def create_provider(self, provider_id: str, name: str) -> AIProvider:
        """
        Registers a new AI Provider. 
        For the purpose of this management layer, we instantiate a default 
        implementation (OllamaProvider) if no specific type is provided.
        In a more complex system, this would map provider_id or a type to a specific class.
        """
        if not provider_id:
            raise ValueError("Provider ID cannot be empty")
        if not name:
            raise ValueError("Provider name cannot be empty")

        # Based on current architecture, we use OllamaProvider as the default 
        # since it's the only one implemented.
        provider = OllamaProvider()
        
        # The registry.register method already handles duplicate ID validation.
        self.registry.register(provider_id, provider)
        return provider

    def get_provider(self, provider_id: str) -> AIProvider:
        """
        Retrieves a provider by ID.
        """
        return self.registry.get(provider_id)

    def list_providers(self) -> dict[str, AIProvider]:
        """
        Returns all registered providers.
        """
        return self.registry.all()

    def remove_provider(self, provider_id: str) -> None:
        """
        Removes a provider from the registry.
        Associated Agents remain registered but will fail resolution.
        """
        self.registry.remove(provider_id)

