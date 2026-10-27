from io import BytesIO
from types import SimpleNamespace
import subprocess
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from app.integrations.image_processing import (
    ImageProcessingError,
    ImageProcessingStatus,
    PillowImageProcessingAdapter,
)


def png_header(width=8, height=6):
    def chunk(name, data):
        body = name + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixel = zlib.compress(b"\x00\xff\x00\x00")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", pixel) + chunk(b"IEND", b""))


def pil_image(*, size=(8, 6), color=(255, 0, 0, 255), info=None):
    pil = pytest.importorskip("PIL.Image")
    image = pil.new("RGBA", size, color)
    output = BytesIO()
    image.save(output, format="PNG", pnginfo=info)
    return output.getvalue()


def assert_worker_ready(monkeypatch):
    monkeypatch.setattr(
        PillowImageProcessingAdapter,
        "status",
        staticmethod(lambda: ImageProcessingStatus("available", "Pillow", "test", "ready")),
    )


def test_optional_image_dependency_is_not_part_of_core_requirements():
    root = Path(__file__).resolve().parents[1]
    assert "Pillow" not in (root / "requirements.txt").read_text(encoding="utf-8")
    assert "Pillow==12.3.0" in (root / "requirements-image-processing.txt").read_text(encoding="utf-8")


def test_single_process_bundle_does_not_spawn_the_gui_executable_as_an_image_worker(monkeypatch):
    monkeypatch.setattr(sys,'frozen',True,raising=False);calls=[]
    adapter=PillowImageProcessingAdapter(worker_runner=lambda *a,**k:calls.append(a))
    assert adapter.status().state=='unavailable' and 'not included' in adapter.status().message
    with pytest.raises(ImageProcessingError,match='unavailable'):adapter.resize(png_header(),max_width=4,max_height=4)
    assert calls==[]


def test_importing_image_adapter_does_not_import_pillow():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import app.integrations.image_processing; assert 'PIL' not in sys.modules"],
        cwd=root, capture_output=True, text=True, timeout=5, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_optional_pillow_status_is_explicit():
    status = PillowImageProcessingAdapter.status()
    assert status.library == "Pillow"
    assert status.state in {"available", "unavailable"}
    assert (status.version is not None) is (status.state == "available")


def test_resize_convert_and_redact_with_optional_pillow():
    pytest.importorskip("PIL.Image")
    from PIL import Image, PngImagePlugin

    adapter = PillowImageProcessingAdapter()
    source = pil_image(size=(80, 60))
    resized = adapter.resize(source, max_width=20, max_height=10)
    assert (resized.width, resized.height) == (13, 10)
    assert resized.operation == "resize"
    assert resized.source_sha256 and resized.sha256
    assert resized.size_bytes == len(resized.data) <= 2 * 1024 * 1024
    converted = adapter.convert(resized.data, output_format="jpeg")
    assert converted.media_type == "image/jpeg"
    assert converted.data.startswith(b"\xff\xd8")
    assert converted.width == 13 and converted.height == 10

    info = PngImagePlugin.PngInfo()
    info.add_text("private", "remove this metadata")
    source = pil_image(size=(8, 6), info=info)
    redacted = adapter.redact(source, boxes=((2, 1, 3, 2),))
    with Image.open(BytesIO(redacted.data)) as output:
        assert output.info.get("private") is None
        assert output.getpixel((2, 1))[:3] == (0, 0, 0)
        assert output.getpixel((4, 2))[:3] == (0, 0, 0)
        assert output.getpixel((1, 1))[:3] == (255, 0, 0)
        assert output.getpixel((5, 2))[:3] == (255, 0, 0)


def test_invalid_input_and_redaction_boxes_are_rejected_before_worker(monkeypatch):
    assert_worker_ready(monkeypatch)
    adapter = PillowImageProcessingAdapter(worker_runner=lambda *args, **kwargs: pytest.fail("worker must not run"))
    with pytest.raises(ImageProcessingError, match="2 MiB"):
        adapter.convert(b"x" * (2 * 1024 * 1024 + 1), output_format="png")
    with pytest.raises(ImageProcessingError, match="Output format"):
        adapter.convert(png_header(), output_format="bmp")
    with pytest.raises(ImageProcessingError, match="outside"):
        adapter.redact(png_header(), boxes=((7, 5, 2, 2),))
    with pytest.raises(ImageProcessingError, match="integer"):
        adapter.redact(png_header(), boxes=((0, 0, True, 2),))


def test_bad_encoded_pixels_fail_with_sanitized_error():
    source = bytearray(pil_image())
    idat = source.find(b"IDAT")
    source[idat + 8] ^= 0xFF
    adapter = PillowImageProcessingAdapter()
    with pytest.raises(ImageProcessingError, match="malformed"):
        adapter.resize(bytes(source), max_width=4, max_height=4)


def test_worker_timeout_and_failure_are_bounded_and_sanitized(monkeypatch):
    assert_worker_ready(monkeypatch)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    adapter = PillowImageProcessingAdapter(timeout_seconds=.1, worker_runner=timeout)
    with pytest.raises(ImageProcessingError, match="time limit"):
        adapter.convert(png_header(), output_format="png")

    failing = PillowImageProcessingAdapter(
        worker_runner=lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="secret path")
    )
    with pytest.raises(ImageProcessingError, match="malformed") as error:
        failing.convert(png_header(), output_format="png")
    assert "secret path" not in str(error.value)


def test_missing_optional_dependency_is_reported_without_startup_failure(monkeypatch):
    monkeypatch.setattr("app.integrations.image_processing.importlib.util.find_spec", lambda _name: None)
    status = PillowImageProcessingAdapter.status()
    assert status.state == "unavailable"
    assert status.version is None
    with pytest.raises(ImageProcessingError, match="unavailable"):
        PillowImageProcessingAdapter().convert(png_header(), output_format="png")
