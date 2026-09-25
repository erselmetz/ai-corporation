from .base import AIProvider


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, AIProvider] = {}

    def register(self, provider_id: str, provider: AIProvider) -> None:
        if provider_id in self._providers:
            raise ValueError(f"Provider already registered: {provider_id}")

        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> AIProvider:
        try:
            return self._providers[provider_id]
        except KeyError:
            raise ValueError(f"Provider not found: {provider_id}")

    def all(self) -> dict[str, AIProvider]:
        return self._providers.copy()

    def exists(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def remove(self, provider_id: str) -> None:
        """Removes a provider from the registry."""
        if not self.exists(provider_id):
            raise ValueError(f"Provider not found: {provider_id}")
        del self._providers[provider_id]