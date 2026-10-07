from abc import ABC, abstractmethod

from .availability import AvailabilityResult
from .inventory import LocalModelInventory, LocalModelRuntime


class ProviderCapacityError(RuntimeError):
    """A request was denied by configured provider/model concurrency limits."""


class ProviderCapacityUnknown(ProviderCapacityError):
    """A request was denied because no applicable capacity limit is known."""


class ProviderModelOperationUnsupported(RuntimeError):
    """The provider does not implement explicit model lifecycle operations."""


class ProviderModelOperationFailed(RuntimeError):
    """A supported provider model lifecycle operation failed."""


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

    def local_model_runtime(self) -> LocalModelRuntime:
        """Report loaded models only when the provider has authoritative telemetry."""
        return LocalModelRuntime()

    def load_model(self, model: str, *, keep_alive_seconds: int = 300) -> None:
        raise ProviderModelOperationUnsupported("Model loading is unsupported by this provider")

    def unload_model(self, model: str) -> None:
        raise ProviderModelOperationUnsupported("Model unloading is unsupported by this provider")
