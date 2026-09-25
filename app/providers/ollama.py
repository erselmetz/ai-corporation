import os
import httpx

from .base import AIProvider


_DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
    ):
        self.base_url = base_url.rstrip("/")

    def generate(self, model: str, prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120.0,
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]
