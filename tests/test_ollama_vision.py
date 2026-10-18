import base64
import json

import pytest

from app.application.services.chat_images import ChatImageStore
from app.providers.ollama import OllamaProvider

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00IHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0bIDATx\x9cc`\x00\x02\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND\xaeB`\x82"


class Response:
    def __init__(self, payload, status=200): self.payload = payload; self.status = status
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def raise_for_status(self):
        if self.status >= 400:
            import httpx
            raise httpx.HTTPStatusError("failed", request=None, response=None)
    def iter_bytes(self): yield self.payload


class Client:
    def __init__(self, **kwargs): self.options = kwargs
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def stream(self, method, url, *, json):
        self.request = (method, url, json)
        clients.append(self)
        if url.endswith("/api/show"):
            return Response(show_response)
        return Response(b'{"response":"vision result"}')


clients = []
show_response = b'{"capabilities":["completion","vision"]}'


def test_ollama_vision_request_is_bounded_and_uses_explicit_selected_images(monkeypatch):
    import app.providers.ollama as module
    global show_response
    clients.clear()
    show_response = b'{"capabilities":["completion","vision"]}'
    monkeypatch.setattr(module.httpx, "Client", Client)
    store = ChatImageStore()
    image = store.attach("owner", "chat", PNG, "image/png")
    provider = OllamaProvider("http://localhost:11434")
    assert provider.supports_image_input is True
    assert provider.generate_with_images("vision-model", "describe", (image,)) == "vision result"
    method, url, payload = clients[-1].request
    assert method == "POST" and url.endswith("/api/generate")
    assert payload["stream"] is False and payload["model"] == "vision-model"
    assert payload["images"] == [base64.b64encode(PNG).decode("ascii")]
    assert clients[0].options["trust_env"] is False
    assert clients[0].options["follow_redirects"] is False


def test_ollama_model_vision_capability_uses_show_metadata_and_unknown_fails_closed(monkeypatch):
    import app.providers.ollama as module
    global show_response
    clients.clear()
    monkeypatch.setattr(module.httpx, "Client", Client)
    provider = OllamaProvider("http://localhost:11434")
    show_response = b'{"capabilities":["completion","vision"]}'
    assert provider.supports_model_image_input("text-model-named-vision") is True
    assert clients[-1].request == ("POST", "http://localhost:11434/api/show", {"model": "text-model-named-vision"})
    show_response = b'{"capabilities":["completion"]}'
    assert provider.supports_model_image_input("vision-looking-name") is False
    show_response = b'{"model":"text-only"}'
    assert provider.supports_model_image_input("text-only") is None


def test_ollama_model_vision_capability_requires_loopback_and_bounded_metadata(monkeypatch):
    import app.providers.ollama as module
    global show_response
    clients.clear()
    monkeypatch.setattr(module.httpx, "Client", Client)
    provider = OllamaProvider("https://remote.example")
    assert provider.supports_model_image_input("model") is None
    assert clients == []
    provider = OllamaProvider("http://localhost:11434")
    show_response = b'{"capabilities":' + b'[' + b'"x",' * 100 + b'"vision"]}'
    assert provider.supports_model_image_input("model") is None


def test_ollama_vision_rejects_unbounded_inputs_and_non_loopback_before_network(monkeypatch):
    import app.providers.ollama as module
    clients.clear()
    monkeypatch.setattr(module.httpx, "Client", Client)
    provider = OllamaProvider("https://remote.example")
    assert provider.supports_image_input is False
    with pytest.raises(RuntimeError, match="loopback"):
        provider.generate_with_images("model", "describe", ())
    store = ChatImageStore()
    image = store.attach("owner", "chat", PNG, "image/png")
    with pytest.raises(ValueError, match="one to four"):
        OllamaProvider().generate_with_images("model", "describe", ())
    with pytest.raises(ValueError, match="byte limit"):
        OllamaProvider().generate_with_images("model", "x" * 32769, (image,))
    assert clients == []
