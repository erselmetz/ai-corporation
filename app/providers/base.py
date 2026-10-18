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


class ProviderStreamingUnsupported(RuntimeError):
    """The provider does not implement validated response streaming."""


class ProviderVisionUnsupported(RuntimeError):
    """The configured provider does not accept explicit image input."""


class AIProvider(ABC):
    is_local = False
    requires_explicit_cloud_consent = False
    supports_streaming = False
    supports_image_input = False

    @abstractmethod
    def generate(self, model: str, prompt: str) -> str:
        """Generate a response from the AI provider."""
        raise NotImplementedError

    def generate_stream(self, model: str, prompt: str):
        raise ProviderStreamingUnsupported("Response streaming is unsupported by this provider")

    def generate_with_images(self, model: str, prompt: str, images, *, ocr_evidence=()) -> str:
        raise ProviderVisionUnsupported("Image input is unsupported by this provider")

    def supports_model_image_input(self, model: str) -> bool | None:
        """Report explicit model capability; None means the capability is unknown."""
        return True if self.supports_image_input is True else False

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
