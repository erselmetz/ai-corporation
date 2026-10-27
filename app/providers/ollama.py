import base64
import os
from datetime import datetime, timezone
import json
import time
from urllib.parse import urlsplit

import httpx

from app.chat_prompt import validate_chat_messages
from app.agent_runtime import (check_runtime_step, current_invocation,
                               runtime_output_token_budget, runtime_timeout_seconds)
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
    @property
    def is_local(self) -> bool:
        return self._is_loopback_endpoint()

    @property
    def supports_image_input(self) -> bool:
        return self._is_loopback_endpoint()

    def supports_model_image_input(self, model: str) -> bool | None:
        """Use Ollama's reported model capabilities; never infer from the model name."""
        return self._supports_model_capability(model, "vision")

    def supports_model_chat(self, model: str) -> bool | None:
        return self._supports_model_capability(model, "completion")

    def _supports_model_capability(self, model: str, capability: str) -> bool | None:
        if isinstance(model,str) and model.casefold().endswith((":cloud","-cloud")):
            return False
        if (not self._is_loopback_endpoint() or not isinstance(model, str)
                or not model.strip() or len(model.encode("utf-8")) > 256):
            return None
        try:
            payload = self._bounded_request("POST", "/api/show", {"model": model})
            data = json.loads(payload)
            if isinstance(data,dict) and (data.get("remote_host") or data.get("remote_model")):
                return False
            capabilities = data.get("capabilities") if isinstance(data, dict) else None
            if not isinstance(capabilities, list) or len(capabilities) > 32:
                return None
            if any(not isinstance(item, str) or len(item) > 64 for item in capabilities):
                return None
            return capability in capabilities
        except httpx.HTTPError:
            return None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

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
        request_body = {"model": model, "prompt": prompt, "stream": True}
        self._prepare_answer_request(model,request_body)
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
                    json=request_body,
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

    def _prepare_answer_request(self,model,body):
        """Preserve the answer-only contract within the existing runtime budget.

        Native thinking is not currently an exposed chat control. On models that
        permit it, disable unrequested reasoning so it cannot consume the entire
        final-answer budget. Thinking UI/stream control remains Task 226.
        """
        if not isinstance(model,str): raise ValueError("Invalid model identifier")
        if model.casefold().endswith((":cloud","-cloud")):
            raise ValueError("Ollama cloud models require a separately reviewed cloud-consent path")
        from app.resources.context import native_scope
        strict=native_scope.get() is not None
        if not self._is_loopback_endpoint():
            if strict:raise ValueError('Native local chat requires a verified loopback model')
            return
        try:
            metadata=json.loads(self._bounded_request("POST","/api/show",{"model":model}))
        except (httpx.HTTPError,ValueError,TypeError):
            if strict:raise ValueError('Local model metadata could not be verified; no message was sent') from None
            return
        if not isinstance(metadata,dict):
            if strict:raise ValueError('Local model metadata is invalid; no message was sent')
            return
        if metadata.get("remote_host") or metadata.get("remote_model"):
            raise ValueError("A remote Ollama model cannot use the local-only chat path")
        thinking=metadata.get("thinking")
        values=thinking.get("values",[]) if isinstance(thinking,dict) else []
        permits_off=thinking is None or (isinstance(values,list) and any(value is False for value in values))
        capabilities=metadata.get("capabilities",[])
        if strict and (not isinstance(capabilities,list) or 'completion' not in capabilities):
            raise ValueError('The selected local model does not report chat capability')
        if strict:
            options=body.setdefault('options',{})
            options.setdefault('num_ctx',8192)
            options.setdefault('temperature',0)
        if isinstance(capabilities,list) and "thinking" in capabilities and permits_off:
            body["think"]=False
        return metadata

    def generate_native_step(self,model,messages,tools,*,num_ctx=8192,thinking=False):
        """One bounded native Ollama tool-call step; results confer no authority."""
        if type(num_ctx) is not int or not 2048<=num_ctx<=16384 or type(thinking) is not bool:
            raise ValueError('Unsupported native context or thinking option')
        if (not isinstance(messages,list) or not 2<=len(messages)<=34
                or len(json.dumps(messages,ensure_ascii=False).encode())>32768
                or any(not isinstance(m,dict) or m.get('role') not in {'system','user','assistant','tool'} for m in messages)):
            raise ValueError('Native chat messages exceed the supported bounds')
        if not isinstance(tools,list) or not 1<=len(tools)<=16:raise ValueError('Native tool catalog is invalid')
        body={'model':model,'messages':messages,'tools':tools,'stream':False,
              'options':{'num_ctx':num_ctx,'num_predict':min(512,runtime_output_token_budget(512))}}
        metadata=self._prepare_answer_request(model,body)
        if not isinstance(metadata,dict) or 'tools' not in metadata.get('capabilities',[]):
            raise ValueError('This installed local model does not report tool capability')
        if thinking:
            if 'thinking' in metadata.get('capabilities',[]):
                levels=metadata.get('thinking')
                values=levels.get('values',[]) if isinstance(levels,dict) else []
                default=levels.get('default') if isinstance(levels,dict) else None
                if isinstance(default,str) and (not values or default in values):body['think']=default
                elif isinstance(values,list) and values and all(isinstance(value,str) for value in values):body['think']=values[0]
                else:body['think']=True
        payload=self._bounded_request('POST','/api/chat',body,timeout=min(90,runtime_timeout_seconds(90)))
        check_runtime_step();data=json.loads(payload)
        if not isinstance(data,dict) or data.get('done') is not True or data.get('error'):
            raise ValueError('The local model did not finish its tool step')
        message=data.get('message')
        if not isinstance(message,dict) or message.get('role')!='assistant':raise ValueError('The model returned an invalid assistant step')
        content=message.get('content','');reasoning=message.get('thinking','');calls=message.get('tool_calls',[])
        if (not isinstance(content,str) or len(content.encode())>8192 or not isinstance(reasoning,str)
                or len(reasoning.encode())>8192 or not isinstance(calls,list) or len(calls)>1):
            raise ValueError('The model exceeded the single-tool or output bound')
        # Only a leading, balanced block actually returned by the model is
        # tagged thinking. Never infer reasoning from answer prose or tool data.
        if content.startswith('<think>'):
            closing=content.find('</think>',7)
            if closing<0:raise ValueError('The model returned an unfinished thinking block')
            tagged=content[7:closing].strip();content=content[closing+8:].lstrip()
            if not reasoning:reasoning=tagged
        if calls:
            call=calls[0];function=call.get('function') if isinstance(call,dict) else None
            if (not isinstance(function,dict) or not isinstance(function.get('name'),str)
                    or not isinstance(function.get('arguments'),dict)
                    or len(json.dumps(function).encode())>12288):raise ValueError('The model returned an invalid tool call')
            if function['name'] not in {tool['function']['name'] for tool in tools}:
                raise ValueError('The model requested an unavailable tool')
            return {'message':{'role':'assistant','content':content,'tool_calls':[{'function':function}]},
                    'thinking':reasoning if thinking else ''}
        if not content.strip():raise ValueError('The model returned no answer or tool request')
        return {'message':{'role':'assistant','content':content},'thinking':reasoning if thinking else ''}

    def generate(self, model: str, prompt: str) -> str:
        request_body = {"model": model, "prompt": prompt, "stream": False}
        self._prepare_answer_request(model,request_body)
        with httpx.Client(
            timeout=120.0, trust_env=False, follow_redirects=False
        ) as client:
            response = client.post(
                f"{self.base_url}/api/generate",
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

        return data["response"]

    def generate_chat(self, model: str, messages) -> str:
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        normalized = validate_chat_messages(messages)
        request_body = {"model": model, "messages": normalized, "stream": False}
        self._prepare_answer_request(model,request_body)
        if current_invocation() is not None:
            request_body.setdefault('options',{})['num_predict']=runtime_output_token_budget()
        response_body = bytearray()
        with httpx.Client(timeout=runtime_timeout_seconds(), trust_env=False,
                          follow_redirects=False) as client:
            with client.stream("POST", f"{self.base_url}/api/chat", json=request_body) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    check_runtime_step()
                    if len(response_body) + len(chunk) > 262144:
                        raise ValueError("Ollama chat response exceeds the byte limit")
                    response_body.extend(chunk)
        check_runtime_step()
        data = json.loads(response_body)
        message = data.get("message") if isinstance(data, dict) else None
        output = message.get("content") if isinstance(message, dict) else None
        if not isinstance(output, str) or not output.strip() or len(output.encode("utf-8")) > 8192:
            raise ValueError("Ollama returned an invalid chat response")
        return output

    def generate_chat_stream(self, model: str, messages):
        if not self.supports_streaming:
            raise ProviderStreamingUnsupported(
                "Ollama response streaming requires a configured loopback provider"
            )
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        normalized = validate_chat_messages(messages)
        received_bytes = 0
        output_bytes = 0
        completed = False
        try:
            request_body = {"model": model, "messages": normalized, "stream": True}
            self._prepare_answer_request(model,request_body)
            if current_invocation() is not None:
                request_body.setdefault('options',{})['num_predict']=runtime_output_token_budget()
            with httpx.Client(timeout=min(_STREAM_TIMEOUT, runtime_timeout_seconds(_STREAM_TIMEOUT)), trust_env=False,
                              follow_redirects=False) as client:
                with client.stream("POST", f"{self.base_url}/api/chat", json=request_body) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        check_runtime_step()
                        received_bytes += len(line.encode("utf-8")) + 1
                        if received_bytes > _MAX_STREAM_RESPONSE_BYTES:
                            raise ValueError("Provider stream exceeds byte limit")
                        if not line:
                            continue
                        item = json.loads(line)
                        message = item.get("message") if isinstance(item, dict) else None
                        chunk = message.get("content") if isinstance(message, dict) else None
                        done = item.get("done") if isinstance(item, dict) else None
                        if "error" in item or not isinstance(chunk, str) or type(done) is not bool:
                            raise ValueError("Malformed provider chat stream")
                        output_bytes += len(chunk.encode("utf-8"))
                        if output_bytes > _MAX_STREAM_OUTPUT_BYTES:
                            raise ValueError("Provider output exceeds byte limit")
                        if chunk:
                            yield chunk
                        if done:
                            completed = True
                            break
            if not completed:
                raise ValueError("Provider chat stream ended without a final marker")
        except httpx.HTTPError:
            raise RuntimeError("Ollama chat stream failed.") from None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise RuntimeError("Ollama returned an invalid or oversized chat stream.") from None

    def generate_chat_with_images(self, model: str, messages, images, *, ocr_evidence=()) -> str:
        from app.application.services.chat_images import ChatImageStore
        if not self._is_loopback_endpoint():
            raise RuntimeError("Image input requires a configured loopback Ollama provider")
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        normalized = validate_chat_messages(messages)
        if not isinstance(images, tuple) or not 1 <= len(images) <= ChatImageStore.MAX_PER_CONVERSATION:
            raise ValueError("Select one to four images")
        if self.supports_model_image_input(model) is not True:
            raise RuntimeError("Ollama did not report vision support for the selected model; no image was sent")
        total = 0
        encoded = []
        for image in images:
            data = getattr(image, "_data", None)
            media_type = getattr(image, "media_type", None)
            if not isinstance(data, bytes) or media_type not in {"image/png", "image/jpeg"}:
                raise ValueError("Image attachment is invalid")
            total += len(data)
            if len(data) > ChatImageStore.MAX_IMAGE_BYTES or total > 8 * 1024 * 1024:
                raise ValueError("Selected images exceed the byte limit")
            encoded.append(base64.b64encode(data).decode("ascii"))
        normalized[-1]["images"] = encoded
        try:
            with httpx.Client(timeout=120.0, trust_env=False, follow_redirects=False) as client:
                response = client.post(f"{self.base_url}/api/chat", json={
                    "model": model, "messages": normalized, "stream": False,
                })
                response.raise_for_status()
                data = response.json()
            message = data.get("message") if isinstance(data, dict) else None
            output = message.get("content") if isinstance(message, dict) else None
            if not isinstance(output, str) or not output.strip() or len(output.encode("utf-8")) > 8192:
                raise ValueError("Ollama returned an invalid chat response")
            return output
        except httpx.HTTPError:
            raise RuntimeError("Ollama image chat failed; check the configured local model.") from None

    def generate_with_images(self, model: str, prompt: str, images, *, ocr_evidence=()) -> str:
        """Send only caller-selected bounded images to the configured Ollama endpoint."""
        from app.application.services.chat_images import ChatImageStore

        if not self._is_loopback_endpoint():
            raise RuntimeError("Image input requires a configured loopback Ollama provider")
        if not isinstance(model, str) or not model.strip() or len(model.encode("utf-8")) > 256:
            raise ValueError("Invalid model identifier")
        if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > 32768:
            raise ValueError("Prompt exceeds byte limit")
        if not isinstance(images, tuple) or not 1 <= len(images) <= ChatImageStore.MAX_PER_CONVERSATION:
            raise ValueError("Select one to four images")
        total = 0
        encoded = []
        for image in images:
            data = getattr(image, "_data", None)
            media_type = getattr(image, "media_type", None)
            if not isinstance(data, bytes) or media_type not in {"image/png", "image/jpeg"}:
                raise ValueError("Image attachment is invalid")
            total += len(data)
            if len(data) > ChatImageStore.MAX_IMAGE_BYTES or total > 8 * 1024 * 1024:
                raise ValueError("Selected images exceed the byte limit")
            encoded.append(base64.b64encode(data).decode("ascii"))
        if self.supports_model_image_input(model) is not True:
            raise RuntimeError("Ollama did not report vision support for the selected model; no image was sent")
        try:
            with httpx.Client(timeout=120.0, trust_env=False, follow_redirects=False) as client:
                request_body = {"model": model, "prompt": prompt,
                                "stream": False, "images": encoded}
                with client.stream("POST", f"{self.base_url}/api/generate",
                                   json=request_body) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    deadline = time.monotonic() + 120.0
                    for chunk in response.iter_bytes():
                        if time.monotonic() > deadline:
                            raise httpx.ReadTimeout("Local provider request timed out")
                        if len(payload) + len(chunk) > 262144:
                            raise ValueError("Provider response exceeds byte limit")
                        payload.extend(chunk)
            result = json.loads(payload)
            output = result.get("response")
            if not isinstance(output, str) or not output.strip() or len(output.encode("utf-8")) > 8192:
                raise ValueError("Provider output is invalid or exceeds limits")
            return output
        except httpx.HTTPError:
            raise RuntimeError("Ollama image request failed; check the configured local model.") from None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise RuntimeError("Ollama returned an invalid or oversized image response.") from None

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
