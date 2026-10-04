from abc import ABC, abstractmethod

from .availability import AvailabilityResult
from .inventory import LocalModelInventory


class ProviderCapacityError(RuntimeError):
    """A request was denied by configured provider/model concurrency limits."""


class ProviderCapacityUnknown(ProviderCapacityError):
    """A request was denied because no applicable capacity limit is known."""


class AIProvider(ABC):
    requires_explicit_cloud_consent = False

    @abstractmethod
    def generate(self, model: str, prompt: str) -> str:
        """Generate a response from the AI provider."""
        raise NotImplementedError

    def check_availability(self) -> AvailabilityResult:
        """Return UNKNOWN unless this provider implements a truthful health check."""
        return AvailabilityResult()

    def local_model_inventory(self) -> LocalModelInventory:
        """Explicit observation; unsupported providers truthfully return UNKNOWN."""
        return LocalModelInventory()
