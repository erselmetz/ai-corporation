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

    def describe(self) -> str:
        return (
            f"{self.name} ({self.role}) | "
            f"Provider: {self.provider} | "
            f"Model: {self.model}"
        )

    def resolve_provider(self, providers) -> AIProvider:
        return providers.get(self.provider)

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