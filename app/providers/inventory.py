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


@dataclass(frozen=True)
class LoadedLocalModel:
    name: str
    size_bytes: int | None
    vram_bytes: int | None
    expires_at: str | None = None
    context_length: int | None = None


@dataclass(frozen=True)
class LocalModelRuntime:
    state: str = "unknown"
    models: tuple[LoadedLocalModel, ...] = ()
    supported: bool = False
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "unsupported"
    probe_latency_ms: float | None = None
    reason: str | None = "Loaded-model telemetry is unsupported."
    hardware_feasibility: str = "unknown"

    def __post_init__(self):
        if self.state not in {"available", "unavailable", "unknown"}:
            raise ValueError("Invalid model runtime state")
        if not isinstance(self.models, tuple) or len(self.models) > 100:
            raise ValueError("Invalid loaded-model list")
        if self.state != "available" and self.models:
            raise ValueError("Only successful runtime checks can report loaded models")
        if self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None:
            raise ValueError("Runtime check time must be timezone-aware")
        if self.probe_latency_ms is not None and (
            type(self.probe_latency_ms) not in {int, float}
            or self.probe_latency_ms < 0
        ):
            raise ValueError("Invalid runtime probe latency")
