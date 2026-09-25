from dataclasses import dataclass, field
from app.providers import AIProvider
from app.memory import MemoryStore

@dataclass
class Agent:
    id: str
    name: str
    role: str
    provider: str
    model: str
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Agent id cannot be empty")
        if not self.name:
            raise ValueError("Agent name cannot be empty")
        if not self.role:
            raise ValueError("Agent role cannot be empty")
        if not self.provider:
            raise ValueError("Agent provider cannot be empty")
        if not self.model:
            raise ValueError("Agent model cannot be empty")
        
        if not all(isinstance(c, str) and c.strip() for c in self.capabilities):
            raise ValueError("All capabilities must be non-empty strings")
        if not all(isinstance(p, str) and p.strip() for p in self.permissions):
            raise ValueError("All permissions must be non-empty strings")

    def describe(self) -> str:
        return (
            f"{self.name} ({self.role}) | "
            f"Provider: {self.provider} | "
            f"Model: {self.model}"
        )

    def resolve_provider(self, providers) -> AIProvider:
        provider = providers.get(self.provider)
        if provider is None:
            raise RuntimeError(f"Provider '{self.provider}' could not be resolved for agent {self.id}")
        return provider

    def remember(self, key: str, value: str) -> None:
        memory = MemoryStore()

        memory.remember(
            self.id,
            key,
            value,
        )

    def recall(self, key: str) -> str | None:
        memory = MemoryStore()

        return memory.recall(
            self.id,
            key,
        )

    def forget(self, key: str) -> None:
        memory = MemoryStore()

        memory.forget(
            self.id,
            key,
        )

    def memories(self) -> list[dict]:
        memory = MemoryStore()

        return memory.all(self.id)