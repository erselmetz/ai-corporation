from dataclasses import dataclass, field


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