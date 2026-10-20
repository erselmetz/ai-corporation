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
    system_prompt: str = ""
    brain_scopes: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    builtin_key: str | None = None
    paused: bool = False
    model_route_preference: str = "manual"

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
        if (not isinstance(self.system_prompt, str) or len(self.system_prompt) > 2000
                or not isinstance(self.brain_scopes, list)
                or not isinstance(self.allowed_tools, list)
                or any(not isinstance(item, str) or not item.strip() or len(item) > 128
                       for item in (*self.brain_scopes, *self.allowed_tools))):
            raise ValueError("Agent role profile is invalid")
        if self.builtin_key is not None and (not isinstance(self.builtin_key, str) or not self.builtin_key.strip()):
            raise ValueError("Built-in Agent key is invalid")
        if type(self.paused) is not bool:
            raise ValueError("Agent pause state must be boolean")
        if self.model_route_preference not in {"manual", "default", "installed-coder"}:
            raise ValueError("Agent model route preference is invalid")

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
