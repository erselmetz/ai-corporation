import base64
import json

from app.application.services.chat_images import ChatImageStore
from app.integrations.gemini_chat import GeminiProvider

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00IHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0bIDATx\x9cc`\x00\x02\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND\xaeB`\x82"


class Manager:
    def __init__(self): self.started = []; self.ended = 0
    def begin_call(self, identity, model): self.started.append((identity, model)); return "secret-test-key"
    def end_call(self): self.ended += 1


class Response:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def raise_for_status(self): pass
    def iter_bytes(self): yield b'{"candidates":[{"content":{"parts":[{"text":"vision reply"}]}}]}'


class Client:
    def __init__(self, **kwargs): self.options = kwargs
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def stream(self, method, endpoint, *, headers, json):
        clients.append((self, method, endpoint, headers, json))
        return Response()


clients = []


def test_gemini_multimodal_payload_uses_existing_bounded_credential_and_no_retry(monkeypatch):
    import app.integrations.gemini_chat as module
    clients.clear()
    monkeypatch.setattr(module.httpx, "Client", Client)
    manager = Manager()
    provider = GeminiProvider("gemini-model", b"identity", manager)
    store = ChatImageStore()
    image = store.attach("owner", "chat", PNG, "image/png")
    assert provider.supports_image_input is True
    assert provider.requires_explicit_cloud_consent is True
    assert provider.generate_with_images("gemini-model", "describe", (image,)) == "vision reply"
    client, method, endpoint, headers, payload = clients[0]
    assert method == "POST" and endpoint.endswith("/gemini-model:generateContent")
    assert headers["x-goog-api-key"] == "secret-test-key"
    assert payload["contents"][0]["parts"][0] == {"text": "describe"}
    assert payload["contents"][0]["parts"][1] == {
        "inline_data": {"mime_type": "image/png", "data": base64.b64encode(PNG).decode("ascii")},
    }
    assert client.options == {"timeout": module._TIMEOUT_SECONDS, "follow_redirects": False, "trust_env": False}
    assert manager.started == [(b"identity", "gemini-model")] and manager.ended == 1
    assert "secret-test-key" not in json.dumps(payload)
