"""Bounded installed-model observations; never hardware or execution evidence."""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class LocalModelInventory:
    state: str = "unknown"
    models: tuple[str, ...] = ()
    supported: bool = False
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "unsupported"
    reason: str | None = "Installed-model inventory is unsupported."

    def __post_init__(self):
        if self.state not in {"available", "unavailable", "unknown"}:
            raise ValueError("Invalid inventory state")
        if (not isinstance(self.models, tuple) or len(self.models) > 100
                or any(not isinstance(model, str) or not model.strip()
                       or len(model.encode("utf-8")) > 256
                       or any(ord(char) < 32 or ord(char) == 127 for char in model)
                       for model in self.models)
                or len(set(self.models)) != len(self.models)):
            raise ValueError("Invalid installed model identifiers")
        if self.state != "available" and self.models:
            raise ValueError("Only successful inventory can report installed models")
