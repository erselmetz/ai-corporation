from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response from the AI provider."""
        raise NotImplementedError