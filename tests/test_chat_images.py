import base64
from datetime import datetime, timezone
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.application.services.chat_images import ChatImageError, ChatImageStore
from app.providers import AIProvider
from app.runtime.factory import create_corporation_runtime


def png(width=1, height=1):
    def chunk(name, data):
        body = name + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


JPEG_1X1 = bytes.fromhex("ffd8ffc0000b080001000101011100ffd9")
NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


def test_ephemeral_owner_scoped_attachment_limits_and_expiry():
    store = ChatImageStore(clock=lambda: NOW)
    image = store.attach("alice", "chat-1", png(), "image/png")
    assert image.snapshot() == {
        "id": image.id,
        "conversation_id": "chat-1",
        "media_type": "image/png",
        "width": 1,
        "height": 1,
        "size_bytes": len(png()),
        "sha256": image.sha256,
        "source": "explicit_user_upload",
        "retention": "process_memory_until_expiry_or_removal",
        "created_at": NOW.isoformat(),
        "expires_at": (NOW + store.TTL).isoformat(),
        "provider_transfer_authorized": False,
    }
    assert store.list_for("alice", "chat-1") == (image,)
    assert store.list_for("bob", "chat-1") == ()
    assert image._data == png()
    assert "_data" not in repr(image)
    assert store.list_for("alice", "chat-1", now=NOW + store.TTL) == ()
    assert store.remove("alice", "chat-1", image.id, now=NOW + store.TTL) is False


def test_only_supported_content_types_and_bounded_dimensions_are_accepted():
    store = ChatImageStore(clock=lambda: NOW)
    jpeg = store.attach("alice", "chat-1", JPEG_1X1, "image/jpeg")
    assert (jpeg.media_type, jpeg.width, jpeg.height) == ("image/jpeg", 1, 1)
    with pytest.raises(ChatImageError, match="does not match"):
        store.attach("alice", "chat-1", png(), "image/jpeg")
    with pytest.raises(ChatImageError, match="malformed or truncated"):
        store.attach("alice", "chat-1", b"\x89PNG\r\n\x1a\nshort", "image/png")
    with pytest.raises(ChatImageError, match="dimensions are unavailable"):
        store.attach("alice", "chat-1", b"\xff\xd8\xff\xd9", "image/jpeg")
    with pytest.raises(ChatImageError, match="dimensions exceed"):
        store.attach("alice", "chat-1", png(4097, 1), "image/png")
    with pytest.raises(ChatImageError, match="byte limit"):
        store.attach("alice", "chat-1", b"x" * (store.MAX_IMAGE_BYTES + 1), "image/png")


def test_conversation_and_global_capacity_are_bounded_and_removal_releases_bytes():
    store = ChatImageStore(clock=lambda: NOW)
    items = [store.attach("alice", "chat-1", png(), "image/png")
             for _ in range(store.MAX_PER_CONVERSATION)]
    with pytest.raises(ChatImageError, match="image limit"):
        store.attach("alice", "chat-1", png(), "image/png")
    assert store.remove("alice", "chat-1", items[0].id)
    assert len(store.list_for("alice", "chat-1")) == store.MAX_PER_CONVERSATION - 1
    store.clear_conversation("alice", "chat-1")
    assert store.list_for("alice", "chat-1") == ()
    store.MAX_TOTAL_BYTES = len(png())
    store.attach("alice", "chat-1", png(), "image/png")
    with pytest.raises(ChatImageError, match="capacity is full"):
        store.attach("alice", "chat-2", png(), "image/png")
    store.remove("alice", "chat-1", store.list_for("alice", "chat-1")[0].id)
    assert store.attach("alice", "chat-2", png(), "image/png")


class Provider(AIProvider):
    def __init__(self):
        self.calls = []

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        return "reply"


class Authentication:
    def authenticate(self, request):
        identity = request.headers.get("x-owner")
        if identity is None:
            return None
        permissions = {"chat:read", "chat:start", "chat:send", "chat:close"}
        if identity == "reader":
            permissions = {"chat:read"}
        return AuthenticatedPrincipal(identity, frozenset(permissions))


def test_chat_api_requires_owner_and_send_permission_and_never_transfers_image():
    runtime = create_corporation_runtime()
    provider = Provider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    app = create_app(application_service=runtime.application_service,
                     authentication_backend=Authentication())
    with TestClient(app) as client:
        headers = {"x-owner": "alice"}
        path = "/api/chat/conversations"
        started = client.post(path, json={"agent_id": "local_worker"}, headers=headers)
        assert started.status_code == 200
        identifier = started.json()["conversation"]["id"]
        image_path = f"{path}/{identifier}/images"
        upload = client.post(image_path, json={
            "media_type": "image/png",
            "data_base64": base64.b64encode(png()).decode("ascii"),
        }, headers=headers)
        assert upload.status_code == 200
        assert upload.json()["provider_transfer_supported"] is False
        assert upload.json()["image"]["provider_transfer_authorized"] is False
        image_id = upload.json()["image"]["id"]
        listing = client.get(image_path, headers=headers)
        assert [item["id"] for item in listing.json()["items"]] == [image_id]
        assert listing.json()["provider_transfer_supported"] is False
        assert client.post(image_path, json={"media_type": "image/png", "data_base64": "YQ=="}).status_code == 401
        assert client.get(image_path, headers={"x-owner": "bob"}).status_code == 404
        assert client.post(image_path, json={"media_type": "image/png", "data_base64": "YQ=="},
                           headers={"x-owner": "reader"}).status_code == 403
        assert client.delete(f"{image_path}/{image_id}", headers={"x-owner": "bob"}).status_code == 404
        assert client.post(f"{path}/{identifier}/messages", json={"text": "Describe this"},
                           headers=headers).status_code == 200
        assert len(provider.calls) == 1
        assert base64.b64encode(png()).decode("ascii") not in provider.calls[0][1]
        assert client.post(f"{path}/{identifier}/close", headers=headers).status_code == 200
        closed_upload = client.post(image_path, json={
            "media_type": "image/png", "data_base64": base64.b64encode(png()).decode("ascii"),
        }, headers=headers)
        assert closed_upload.status_code == 422
        assert client.get(image_path, headers=headers).json()["items"] == []
        assert client.delete(f"{image_path}/{image_id}", headers=headers).status_code == 404
    assert len(provider.calls) == 1
