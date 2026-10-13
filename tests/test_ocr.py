import hashlib
import time

import pytest

from app.application.services.chat_images import ChatImageStore
from app.integrations.ocr import OcrRegion, OcrService, OcrStatus


def png(width=2, height=2):
    import struct
    import zlib

    def chunk(name, data):
        body = name + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\x00" * (height * (width * 3 + 1))))
            + chunk(b"IEND", b""))


class FakeOcr:
    def __init__(self, regions=(), *, available=True, languages=("eng",)):
        self.regions = regions
        self.available = available
        self.languages = set(languages)
        self.calls = []

    def supports_language(self, language):
        return language in self.languages

    def is_available(self):
        return self.available

    def recognize(self, image, *, timeout_seconds):
        self.calls.append((image, timeout_seconds))
        return self.regions


@pytest.fixture
def attachment():
    return ChatImageStore().attach("owner", "conversation", png(), "image/png")


def test_ocr_result_carries_source_image_provenance_and_bounded_regions(attachment):
    provider = FakeOcr((OcrRegion("hello", 0.95, (0, 0, 2, 1)),))
    result = OcrService(provider).recognize(attachment, language="eng")
    assert result.status is OcrStatus.SUCCESS
    assert (result.image_id, result.source, result.source_sha256) == (
        attachment.id, "explicit_user_upload", hashlib.sha256(png()).hexdigest())
    assert result.language == "eng"
    assert result.regions == (OcrRegion("hello", 0.95, (0, 0, 2, 1)),)
    assert result.untrusted is True
    assert provider.calls[0][0]._data == png()


def test_distinguishes_unsupported_unavailable_and_low_confidence(attachment):
    assert OcrService(FakeOcr(languages=())).recognize(attachment, language="eng").status is OcrStatus.UNSUPPORTED
    assert OcrService(FakeOcr(available=False)).recognize(attachment, language="eng").status is OcrStatus.UNAVAILABLE
    low = OcrService(FakeOcr((OcrRegion("maybe", 0.2, (0, 0, 1, 1)),))).recognize(attachment, language="eng")
    assert low.status is OcrStatus.LOW_CONFIDENCE
    assert low.regions[0].text == "maybe"


def test_missing_provider_and_provider_errors_are_truthful_and_sanitized(attachment):
    assert OcrService().recognize(attachment, language="eng").status is OcrStatus.UNAVAILABLE

    class Broken(FakeOcr):
        def recognize(self, image, *, timeout_seconds):
            raise RuntimeError("token=super-secret C:\\private\\model")

    result = OcrService(Broken()).recognize(attachment, language="eng")
    assert result.status is OcrStatus.FAILED
    assert result.diagnostic == "OCR processing failed"
    assert "super-secret" not in result.diagnostic
    assert "private" not in result.diagnostic


def test_timeout_is_bounded_and_a_stuck_provider_cannot_spawn_unbounded_calls(attachment):
    class Slow(FakeOcr):
        def recognize(self, image, *, timeout_seconds):
            time.sleep(0.2)
            return ()

    service = OcrService(Slow(), timeout_seconds=0.05)
    started = time.monotonic()
    first = service.recognize(attachment, language="eng")
    elapsed = time.monotonic() - started
    second = service.recognize(attachment, language="eng")
    assert first.status is OcrStatus.TIMEOUT
    assert elapsed < 0.15
    assert second.status is OcrStatus.UNAVAILABLE
    time.sleep(0.2)


def test_provider_capability_checks_share_the_bounded_deadline(attachment):
    class SlowCheck(FakeOcr):
        def supports_language(self, language):
            time.sleep(0.2)
            return True

    service = OcrService(SlowCheck(), timeout_seconds=0.05)
    started = time.monotonic()
    result = service.recognize(attachment, language="eng")
    assert result.status is OcrStatus.TIMEOUT
    assert time.monotonic() - started < 0.15
    time.sleep(0.2)


@pytest.mark.parametrize("regions", [
    tuple(OcrRegion("x", 1, (0, 0, 1, 1)) for _ in range(OcrService.MAX_REGIONS + 1)),
    (OcrRegion("x" * (OcrService.MAX_REGION_TEXT_CHARS + 1), 1, (0, 0, 1, 1)),),
    (OcrRegion("x", 1, (0, 0, 3, 1)),),
    (OcrRegion("x", 1.1, (0, 0, 1, 1)),),
])
def test_invalid_or_over_limit_provider_output_fails_closed(attachment, regions):
    result = OcrService(FakeOcr(regions)).recognize(attachment, language="eng")
    assert result.status is OcrStatus.FAILED
    assert result.regions == ()
    assert len(result.diagnostic) <= OcrService.MAX_DIAGNOSTIC_CHARS


def test_language_and_timeout_configuration_are_bounded(attachment):
    with pytest.raises(ValueError, match="language"):
        OcrService(FakeOcr()).recognize(attachment, language="../../secret")
    with pytest.raises(ValueError, match="timeout"):
        OcrService(FakeOcr(), timeout_seconds=99)
