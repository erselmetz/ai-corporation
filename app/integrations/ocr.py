"""Bounded OCR provider contract and untrusted, traceable OCR results."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import hmac
import queue
import re
import threading
import time
from typing import Protocol, Sequence

from app.application.services.chat_images import ChatImageAttachment, ChatImageStore, image_dimensions


class OcrStatus(StrEnum):
    SUCCESS = "success"
    LOW_CONFIDENCE = "low_confidence"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    FAILED = "failed"


@dataclass(frozen=True)
class OcrRegion:
    text: str
    confidence: float
    # Pixel coordinates: left, top, right, bottom.
    bounding_box: tuple[int, int, int, int]


@dataclass(frozen=True)
class OcrImage:
    image_id: str
    source: str
    sha256: str
    media_type: str
    width: int
    height: int
    language: str
    _data: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class OcrResult:
    status: OcrStatus
    image_id: str
    source: str
    source_sha256: str
    language: str
    regions: tuple[OcrRegion, ...] = ()
    elapsed_ms: int = 0
    diagnostic: str | None = None
    untrusted: bool = True


class OcrProvider(Protocol):
    """Replaceable local OCR implementation; providers must honor the deadline."""

    def supports_language(self, language: str) -> bool: ...

    def is_available(self) -> bool: ...

    def recognize(self, image: OcrImage, *, timeout_seconds: float) -> Sequence[OcrRegion]: ...


class OcrProviderTimeout(TimeoutError):
    """A provider's bounded operation exceeded its deadline."""


class OcrService:
    MAX_REGIONS = 128
    MAX_REGION_TEXT_CHARS = 4096
    MAX_TOTAL_TEXT_CHARS = 32_768
    MAX_DIAGNOSTIC_CHARS = 256
    MAX_LANGUAGE_CHARS = 32
    DEFAULT_TIMEOUT_SECONDS = 2.0
    MIN_TIMEOUT_SECONDS = 0.05
    MAX_TIMEOUT_SECONDS = 5.0
    LOW_CONFIDENCE_THRESHOLD = 0.5
    _LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$")

    def __init__(self, provider: OcrProvider | None = None, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
            raise ValueError("OCR timeout is invalid")
        if not self.MIN_TIMEOUT_SECONDS <= timeout_seconds <= self.MAX_TIMEOUT_SECONDS:
            raise ValueError("OCR timeout is outside the supported range")
        self._provider = provider
        self._timeout_seconds = float(timeout_seconds)
        # One hung provider cannot create an unbounded number of daemon threads.
        self._active = threading.BoundedSemaphore(1)

    def recognize(self, attachment: ChatImageAttachment, *, language: str) -> OcrResult:
        image = self._image(attachment, language)
        if self._provider is None:
            return self._result(image, OcrStatus.UNAVAILABLE, diagnostic="No OCR provider is configured")
        provider = self._provider
        if not self._active.acquire(blocking=False):
            return self._result(image, OcrStatus.UNAVAILABLE, diagnostic="OCR provider is busy")

        outcome: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)
        started = time.monotonic()

        def run() -> None:
            try:
                if not provider.is_available():
                    outcome.put((True, ("status", OcrStatus.UNAVAILABLE)))
                    return
                if not provider.supports_language(image.language):
                    outcome.put((True, ("status", OcrStatus.UNSUPPORTED)))
                    return
                outcome.put((True, ("regions", provider.recognize(image, timeout_seconds=self._timeout_seconds))))
            except OcrProviderTimeout:
                outcome.put((True, ("status", OcrStatus.TIMEOUT)))
            except Exception:
                outcome.put((False, exc))
            finally:
                self._active.release()

        threading.Thread(target=run, name="bounded-ocr-provider", daemon=True).start()
        try:
            succeeded, value = outcome.get(timeout=self._timeout_seconds)
        except queue.Empty:
            return self._result(image, OcrStatus.TIMEOUT, elapsed=started, diagnostic="OCR processing timed out")
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if not succeeded:
            return self._result(image, OcrStatus.FAILED, elapsed=started, diagnostic="OCR processing failed")
        kind, value = value
        if kind == "status":
            status = value
            diagnostic = ({OcrStatus.UNSUPPORTED: "Requested language is unsupported",
                           OcrStatus.UNAVAILABLE: "OCR provider is unavailable",
                           OcrStatus.TIMEOUT: "OCR processing timed out"}[status])
            return self._result(image, status, elapsed=started, diagnostic=diagnostic)
        try:
            regions = self._validate_regions(value, image)
        except (TypeError, ValueError):
            return self._result(image, OcrStatus.FAILED, elapsed=started, diagnostic="OCR result exceeded supported limits")
        if not regions:
            return self._result(image, OcrStatus.LOW_CONFIDENCE, elapsed=started, regions=())
        status = (OcrStatus.LOW_CONFIDENCE
                  if min(region.confidence for region in regions) < self.LOW_CONFIDENCE_THRESHOLD
                  else OcrStatus.SUCCESS)
        return self._result(image, status, elapsed_ms=elapsed_ms, regions=regions)

    @classmethod
    def _image(cls, attachment: ChatImageAttachment, language: str) -> OcrImage:
        if not isinstance(attachment, ChatImageAttachment):
            raise ValueError("A supported chat image attachment is required")
        if (not isinstance(language, str) or len(language) > cls.MAX_LANGUAGE_CHARS
                or not cls._LANGUAGE.fullmatch(language)):
            raise ValueError("OCR language tag is invalid")
        data = attachment._data
        if (not isinstance(data, bytes) or not data or len(data) > ChatImageStore.MAX_IMAGE_BYTES
                or len(attachment.sha256) != 64
                or not hmac.compare_digest(hashlib.sha256(data).hexdigest(), attachment.sha256)
                or attachment.media_type not in {"image/png", "image/jpeg"}
                or attachment.width < 1 or attachment.height < 1
                or attachment.width > ChatImageStore.MAX_WIDTH or attachment.height > ChatImageStore.MAX_HEIGHT
                or attachment.width * attachment.height > ChatImageStore.MAX_PIXELS):
            raise ValueError("Image attachment provenance or limits are invalid")
        if image_dimensions(data) != (attachment.media_type, attachment.width, attachment.height):
            raise ValueError("Image attachment metadata does not match its bytes")
        return OcrImage(attachment.id, attachment.source, attachment.sha256, attachment.media_type,
                        attachment.width, attachment.height, language, data)

    @classmethod
    def _validate_regions(cls, value: object, image: OcrImage) -> tuple[OcrRegion, ...]:
        if not isinstance(value, (tuple, list)) or len(value) > cls.MAX_REGIONS:
            raise ValueError("OCR region count is invalid")
        regions: list[OcrRegion] = []
        total = 0
        for region in value:
            if not isinstance(region, OcrRegion) or not isinstance(region.text, str):
                raise ValueError("OCR region type is invalid")
            text = region.text.strip()
            if not text or len(text) > cls.MAX_REGION_TEXT_CHARS:
                raise ValueError("OCR text size is invalid")
            total += len(text)
            if total > cls.MAX_TOTAL_TEXT_CHARS:
                raise ValueError("OCR text total is invalid")
            if (not isinstance(region.confidence, (int, float)) or isinstance(region.confidence, bool)
                    or not 0 <= region.confidence <= 1):
                raise ValueError("OCR confidence is invalid")
            box = region.bounding_box
            if (not isinstance(box, tuple) or len(box) != 4
                    or any(not isinstance(part, int) or isinstance(part, bool) for part in box)):
                raise ValueError("OCR box is invalid")
            left, top, right, bottom = box
            if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                raise ValueError("OCR box is outside the source image")
            regions.append(OcrRegion(text, float(region.confidence), box))
        return tuple(regions)

    @classmethod
    def _result(cls, image: OcrImage, status: OcrStatus, *, elapsed: float | None = None,
                elapsed_ms: int | None = None, regions: tuple[OcrRegion, ...] = (),
                diagnostic: str | None = None) -> OcrResult:
        if elapsed_ms is None:
            elapsed_ms = int((time.monotonic() - elapsed) * 1000) if elapsed is not None else 0
        safe_diagnostic = diagnostic[:cls.MAX_DIAGNOSTIC_CHARS] if diagnostic else None
        return OcrResult(status, image.image_id, image.source, image.sha256, image.language,
                         regions, min(max(elapsed_ms, 0), int(cls.MAX_TIMEOUT_SECONDS * 1000)),
                         safe_diagnostic, True)
