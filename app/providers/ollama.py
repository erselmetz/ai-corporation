import os
from datetime import datetime, timezone
import json
import time
from urllib.parse import urlsplit

import httpx

from .availability import AvailabilityResult, AvailabilityState
from .base import (
    AIProvider,
    ProviderModelOperationFailed,
    ProviderStreamingUnsupported,
)
from .inventory import LoadedLocalModel, LocalModelInventory, LocalModelRuntime


_DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_AVAILABILITY_TIMEOUT = 2.0
_MODEL_OPERATION_TIMEOUT = 300.0
_STREAM_TIMEOUT = 120.0
_MAX_STREAM_RESPONSE_BYTES = 262144
_MAX_STREAM_OUTPUT_BYTES = 8192


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
    ):
        self.base_url = base_url.rstrip("/")

    @property
    def supports_streaming(self) -> bool:
        return self._is_loopback_endpoint()

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

    def local_model_runtime(self) -> LocalModelRuntime:
        started = time.monotonic()

        def result(state, reason=None, models=(), supported=True):
            return LocalModelRuntime(
                state=state,
                models=models,
                supported=supported,
                source="ollama:/api/ps" if supported else "unsupported",
                checked_at=datetime.now(timezone.utc),
                probe_latency_ms=max(0.0, (time.monotonic() - started) * 1000),
                reason=reason,
            )

        if not self._is_loopback_endpoint():
            return result("unknown", "Loaded-model telemetry requires a loopback Ollama provider.",
                          supported=False)
        try:
            payload = self._bounded_request("GET", "/api/ps")
            data = json.loads(payload)
            entries = data["models"]
            if not isinstance(entries, list) or len(entries) > 100:
                return result("unknown", "Loaded-model response exceeds limits or is malformed.")
            models = []
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("Malformed model")
                name = entry["name"]
                if not isinstance(name, str) or not name.strip() or len(name.encode("utf-8")) > 256:
                    raise ValueError("Malformed model")
                size = entry.get("size")
                vram = entry.get("size_vram")
                context_length = entry.get("context_length")
                if any(value is not None and (type(value) is not int or value < 0)
                       for value in (size, vram, context_length)):
                    raise ValueError("Malformed model telemetry")
                expires_at = entry.get("expires_at")
                if expires_at is not None and not isinstance(expires_at, str):
                    raise ValueError("Malformed model telemetry")
                models.append(LoadedLocalModel(name, size, vram, expires_at, context_length))
            if len({model.name for model in models}) != len(models):
                raise ValueError("Duplicate loaded model")
            return result("available", models=tuple(models))
        except httpx.TimeoutException:
            return result("unavailable", "Loaded-model check timed out.")
        except httpx.HTTPError:
            return result("unavailable", "Ollama loaded-model check failed.")
        except (ValueError, TypeError, KeyError):
            return result("unknown", "Loaded-model response is malformed or exceeds limits.")

    def load_model(self, model: str, *, keep_alive_seconds: int = 300) -> None:
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        if type(keep_alive_seconds) is not int or not 1 <= keep_alive_seconds <= 86400:
            raise ValueError("Keep-alive must be between 1 and 86400 seconds")
        try:
            self._bounded_request("POST", "/api/generate", {
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": f"{keep_alive_seconds}s",
            }, timeout=_MODEL_OPERATION_TIMEOUT)
        except httpx.HTTPError:
            raise ProviderModelOperationFailed("Ollama could not load the requested model.") from None
        except ValueError:
            raise ProviderModelOperationFailed("Ollama returned an invalid model-operation response.") from None

    def unload_model(self, model: str) -> None:
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        try:
            self._bounded_request("POST", "/api/generate", {
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": 0,
            }, timeout=_MODEL_OPERATION_TIMEOUT)
        except httpx.HTTPError:
            raise ProviderModelOperationFailed("Ollama could not unload the requested model.") from None
        except ValueError:
            raise ProviderModelOperationFailed("Ollama returned an invalid model-operation response.") from None

    def generate_stream(self, model: str, prompt: str):
        if not self.supports_streaming:
            raise ProviderStreamingUnsupported(
                "Ollama response streaming requires a configured loopback provider"
            )
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > 32768:
            raise ValueError("Prompt exceeds byte limit")
        received_bytes = 0
        output_bytes = 0
        completed = False
        try:
            with httpx.Client(
                timeout=_STREAM_TIMEOUT, trust_env=False, follow_redirects=False
            ) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": True},
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        received_bytes += len(line.encode("utf-8")) + 1
                        if received_bytes > _MAX_STREAM_RESPONSE_BYTES:
                            raise ValueError("Provider stream exceeds byte limit")
                        if not line:
                            continue
                        item = json.loads(line)
                        if not isinstance(item, dict):
                            raise ValueError("Malformed provider stream")
                        if "error" in item:
                            raise ValueError("Provider reported stream failure")
                        chunk = item.get("response")
                        done = item.get("done")
                        if not isinstance(chunk, str) or type(done) is not bool:
                            raise ValueError("Malformed provider stream")
                        output_bytes += len(chunk.encode("utf-8"))
                        if output_bytes > _MAX_STREAM_OUTPUT_BYTES:
                            raise ValueError("Provider output exceeds byte limit")
                        if chunk:
                            yield chunk
                        if done:
                            completed = True
                            break
            if not completed:
                raise ValueError("Provider stream ended without a final marker")
        except httpx.HTTPError:
            raise RuntimeError("Ollama response stream failed.") from None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise RuntimeError("Ollama returned an invalid or oversized response stream.") from None

    def _is_loopback_endpoint(self):
        try:
            endpoint = urlsplit(self.base_url)
            port = endpoint.port
        except ValueError:
            return False
        return (
            endpoint.scheme == "http"
            and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            and endpoint.username is None
            and endpoint.password is None
            and not endpoint.path
            and not endpoint.query
            and not endpoint.fragment
            and (port is None or 1 <= port <= 65535)
        )

    def _bounded_request(self, method, path, body=None, *, timeout=5.0):
        if not self._is_loopback_endpoint():
            raise ValueError("Ollama runtime operations require a loopback provider")
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            with client.stream(method, f"{self.base_url}{path}", json=body) as response:
                response.raise_for_status()
                payload = bytearray()
                deadline = time.monotonic() + timeout
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("Local provider request timed out.")
                    if len(payload) + len(chunk) > 262144:
                        raise ValueError("Local provider response exceeds the byte limit")
                    payload.extend(chunk)
        return bytes(payload)

    def generate(self, model: str, prompt: str) -> str:
        with httpx.Client(
            timeout=120.0, trust_env=False, follow_redirects=False
        ) as client:
            response = client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                },
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
