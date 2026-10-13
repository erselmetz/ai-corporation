"""Bounded, owner-scoped image attachments for the process-local chat service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import struct
from threading import RLock
from uuid import uuid4


class ChatImageError(ValueError):
    """An image attachment cannot be accepted in the current chat state."""


@dataclass(frozen=True)
class ChatImageAttachment:
    id: str
    conversation_id: str
    media_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    source: str
    retention: str
    created_at: datetime
    expires_at: datetime
    display_surface: str | None = None
    captured_at: datetime | None = None
    provider_transfer_authorized: bool = False
    _data: bytes = field(default=b"", repr=False, compare=False)

    def snapshot(self) -> dict[str, object]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "source": self.source,
            "retention": self.retention,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "display_surface": self.display_surface,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "provider_transfer_authorized": self.provider_transfer_authorized,
        }


class ChatImageStore:
    """Ephemeral image bytes tied to an authenticated owner's open conversation.

    Images remain in process memory until expiry/removal and are sent only through an explicitly consented one-use chat turn.
    """

    MAX_IMAGE_BYTES = 2 * 1024 * 1024
    MAX_WIDTH = 4096
    MAX_HEIGHT = 4096
    MAX_PIXELS = 8_000_000
    MAX_PER_CONVERSATION = 4
    MAX_TOTAL_BYTES = 20 * 1024 * 1024
    TTL = timedelta(minutes=15)

    def __init__(self, *, clock=lambda: datetime.now(timezone.utc)):
        self._clock = clock
        self._items: dict[tuple[str, str], dict[str, ChatImageAttachment]] = {}
        self._total_bytes = 0
        self._lock = RLock()

    def attach(self, owner: str, conversation_id: str, data: bytes,
               media_type: str, *, source: str = "explicit_user_upload",
               display_surface: str | None = None,
               captured_at: datetime | None = None,
               now: datetime | None = None) -> ChatImageAttachment:
        if not isinstance(owner, str) or not owner.strip():
            raise ChatImageError("Owner identity is required")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ChatImageError("Conversation identity is required")
        if not isinstance(data, bytes) or not data or len(data) > self.MAX_IMAGE_BYTES:
            raise ChatImageError("Image is empty or exceeds the byte limit")
        actual_type, width, height = image_dimensions(data)
        if media_type != actual_type:
            raise ChatImageError("Image type does not match its content")
        if width > self.MAX_WIDTH or height > self.MAX_HEIGHT or width * height > self.MAX_PIXELS:
            raise ChatImageError("Image dimensions exceed the limit")
        if source not in {"explicit_user_upload", "screen_capture", "camera_capture"}:
            raise ChatImageError("Image source is unsupported")
        if source in {"screen_capture", "camera_capture"}:
            if source == "screen_capture" and display_surface not in {"monitor", "window", "browser"}:
                raise ChatImageError("Selected display surface is unsupported")
            if source == "camera_capture" and display_surface is not None:
                raise ChatImageError("Camera captures do not have a display surface")
            if not isinstance(captured_at, datetime) or captured_at.tzinfo is None:
                raise ChatImageError("Capture timestamp must include a timezone")
            captured_at = captured_at.astimezone(timezone.utc)
        elif display_surface is not None or captured_at is not None:
            raise ChatImageError("Capture details require a screen-capture source")
        current = self._now(now)
        key = (owner, conversation_id)
        with self._lock:
            self._purge(current)
            items = self._items.setdefault(key, {})
            if len(items) >= self.MAX_PER_CONVERSATION:
                raise ChatImageError("Conversation image limit reached")
            if self._total_bytes + len(data) > self.MAX_TOTAL_BYTES:
                raise ChatImageError("Temporary image capacity is full")
            item = ChatImageAttachment(
                id=uuid4().hex,
                conversation_id=conversation_id,
                media_type=actual_type,
                width=width,
                height=height,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                source=source,
                retention="process_memory_until_expiry_or_removal",
                created_at=current,
                expires_at=current + self.TTL,
                display_surface=display_surface,
                captured_at=captured_at,
                _data=data,
            )
            items[item.id] = item
            self._total_bytes += len(data)
            return item

    def list_for(self, owner: str, conversation_id: str,
                 *, now: datetime | None = None) -> tuple[ChatImageAttachment, ...]:
        current = self._now(now)
        with self._lock:
            self._purge(current)
            return tuple(self._items.get((owner, conversation_id), {}).values())

    def selected_for(self, owner: str, conversation_id: str, image_ids: tuple[str, ...],
                     *, now: datetime | None = None) -> tuple[ChatImageAttachment, ...]:
        if (not isinstance(image_ids, tuple) or not 1 <= len(image_ids) <= self.MAX_PER_CONVERSATION
                or any(not isinstance(item, str) or not item.strip() for item in image_ids)
                or len(set(image_ids)) != len(image_ids)):
            raise ChatImageError("Select one to four distinct conversation images")
        current = self._now(now)
        with self._lock:
            self._purge(current)
            items = self._items.get((owner, conversation_id), {})
            selected = tuple(items[item] for item in image_ids if item in items)
            if len(selected) != len(image_ids):
                raise ChatImageError("A selected image is unavailable or expired")
            return selected

    def remove(self, owner: str, conversation_id: str, image_id: str,
               *, now: datetime | None = None) -> bool:
        current = self._now(now)
        key = (owner, conversation_id)
        with self._lock:
            self._purge(current)
            item = self._items.get(key, {}).pop(image_id, None)
            if item is None:
                return False
            self._total_bytes -= item.size_bytes
            if not self._items[key]:
                self._items.pop(key, None)
            return True

    def clear_conversation(self, owner: str, conversation_id: str) -> None:
        with self._lock:
            items = self._items.pop((owner, conversation_id), {})
            self._total_bytes -= sum(item.size_bytes for item in items.values())

    def _purge(self, now: datetime) -> None:
        for key, items in tuple(self._items.items()):
            for image_id, item in tuple(items.items()):
                if item.expires_at <= now:
                    self._total_bytes -= item.size_bytes
                    del items[image_id]
            if not items:
                self._items.pop(key, None)

    def _now(self, now: datetime | None) -> datetime:
        value = self._clock() if now is None else now
        if value.tzinfo is None:
            raise ChatImageError("Image timestamp must include a timezone")
        return value.astimezone(timezone.utc)


def image_dimensions(data: bytes) -> tuple[str, int, int]:
    """Read bounded PNG/JPEG dimensions from their structural headers."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 45 or data[12:16] != b"IHDR" or data[-8:-4] != b"IEND":
            raise ChatImageError("Image data is malformed or truncated")
        width, height = struct.unpack(">II", data[16:24])
        if width == 0 or height == 0:
            raise ChatImageError("Image dimensions are invalid")
        return "image/png", width, height
    if data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        width, height = _jpeg_dimensions(data)
        return "image/jpeg", width, height
    raise ChatImageError("Only PNG and JPEG images are supported")


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    position = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                   0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while position + 4 <= len(data) and position < 65536:
        if data[position] != 0xFF:
            raise ChatImageError("Image data is malformed or truncated")
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            continue
        if position + 2 > len(data):
            break
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            raise ChatImageError("Image data is malformed or truncated")
        if marker in sof_markers:
            if length < 7:
                break
            height = int.from_bytes(data[position + 3:position + 5], "big")
            width = int.from_bytes(data[position + 5:position + 7], "big")
            if width == 0 or height == 0:
                break
            return width, height
        if marker == 0xDA:
            break
        position += length
    raise ChatImageError("Image dimensions are unavailable")
