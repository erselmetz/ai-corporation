from abc import ABC, abstractmethod

from .availability import AvailabilityResult


class AIProvider(ABC):
    @abstractmethod
    def generate(self, model: str, prompt: str) -> str:
        """Generate a response from the AI provider."""
        raise NotImplementedError

    def check_availability(self) -> AvailabilityResult:
        """Return UNKNOWN unless this provider implements a truthful health check."""
        return AvailabilityResult()