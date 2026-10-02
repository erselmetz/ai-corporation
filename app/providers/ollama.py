import os
from datetime import datetime, timezone

import httpx

from .availability import AvailabilityResult, AvailabilityState
from .base import AIProvider


_DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_AVAILABILITY_TIMEOUT = 2.0


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

    def check_availability(self) -> AvailabilityResult:
        try:
            response = httpx.get(
                f"{self.base_url}/api/tags",
                timeout=_AVAILABILITY_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            return self._availability_result(
                AvailabilityState.UNAVAILABLE,
                "Provider availability check timed out.",
            )
        except httpx.HTTPStatusError:
            return self._availability_result(
                AvailabilityState.UNAVAILABLE,
                "Provider service returned an unsuccessful response.",
            )
        except httpx.RequestError:
            return self._availability_result(
                AvailabilityState.UNAVAILABLE,
                "Provider service could not be reached.",
            )

        return self._availability_result(AvailabilityState.AVAILABLE)

    @staticmethod
    def _availability_result(
        state: AvailabilityState,
        reason: str | None = None,
    ) -> AvailabilityResult:
        return AvailabilityResult(state, datetime.now(timezone.utc), reason)
