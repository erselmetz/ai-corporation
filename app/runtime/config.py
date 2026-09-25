from dataclasses import dataclass
from .models import RuntimeContext

@dataclass
class RuntimeConfig:
    """
    Configuration source for the current runtime identity.
    
    This object defines WHAT identity the application should use.
    It is the source for creating a RuntimeContext.
    """
    corporation_id: str
    node_id: str

    def __post_init__(self) -> None:
        if not self.corporation_id or not self.corporation_id.strip():
            raise ValueError("Configuration: corporation_id cannot be empty")
        if not self.node_id or not self.node_id.strip():
            raise ValueError("Configuration: node_id cannot be empty")

    def to_context(self) -> RuntimeContext:
        """Returns a RuntimeContext based on this configuration."""
        return RuntimeContext(
            corporation_id=self.corporation_id,
            node_id=self.node_id,
        )
