import os
from datetime import datetime, timezone
import json
import time
from urllib.parse import urlsplit

import httpx

from .availability import AvailabilityResult, AvailabilityState
from .base import AIProvider
from .inventory import LocalModelInventory


_DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_AVAILABILITY_TIMEOUT = 2.0


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
    ):
        self.base_url = base_url.rstrip("/")

    def local_model_inventory(self) -> LocalModelInventory:
        try:
            endpoint = urlsplit(self.base_url)
        except ValueError:
            return LocalModelInventory(reason="Inventory requires a configured loopback HTTP provider.")
        if (endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
                or endpoint.username or endpoint.password or endpoint.path
                or endpoint.query or endpoint.fragment):
            return LocalModelInventory(reason="Inventory requires a configured loopback HTTP provider.")
        def result(state, reason=None, models=()):
            return LocalModelInventory(state, models, True, source="ollama:/api/tags", reason=reason)
        try:
            deadline = time.monotonic() + 3.0
            # Streaming caps decoded response bytes; redirects and proxy discovery are disabled.
            with httpx.Client(timeout=2.0, trust_env=False, follow_redirects=False) as client:
                with client.stream("GET", f"{self.base_url}/api/tags") as response:
                    response.raise_for_status()
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() > deadline:
                            return result("unavailable", "Local provider inventory check timed out.")
                        if len(payload) + len(chunk) > 262144:
                            return result("unknown", "Inventory response exceeds the byte limit.")
                        payload.extend(chunk)
            data = json.loads(payload)
            entries = data["models"]
            if not isinstance(entries, list) or len(entries) > 100:
                return result("unknown", "Inventory response exceeds limits or is malformed.")
            identifiers = tuple(entry["name"] for entry in entries)
            return result("available", models=identifiers)
        except httpx.TimeoutException:
            return result("unavailable", "Local provider inventory check timed out.")
        except httpx.HTTPError:
            return result("unavailable", "Local provider is unavailable; check that Ollama is running.")
        except (ValueError, TypeError, KeyError):
            return result("unknown", "Local provider inventory response is malformed.")

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
