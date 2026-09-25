from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate(self, model: str, prompt: str) -> str:
        """Generate a response from the AI provider."""
        raise NotImplementedError