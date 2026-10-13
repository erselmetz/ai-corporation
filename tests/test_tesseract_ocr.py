from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from app.application.services.chat_images import ChatImageStore
from app.integrations.ocr import OcrStatus
from app.integrations.tesseract_ocr import TesseractLocalProvider

from tests.test_ocr import png


TSV = (
    b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    b"5\t1\t1\t1\t1\t1\t0\t0\t2\t1\t96.5\tHello\n"
)


def make_provider(tmp_path: Path, runner):
    tmp_path.mkdir(parents=True, exist_ok=True)
    exe = tmp_path / "tesseract.exe"
    exe.write_bytes(b"test executable placeholder")
    data = tmp_path / "tessdata"
    data.mkdir()
    return TesseractLocalProvider(exe, tessdata_directory=data, runner=runner)


def image():
    return ChatImageStore().attach("owner", "conversation", png(), "image/png")


def fake_runner(arguments, *, input, capture_output, check, shell, timeout):
    assert shell is False
    assert check is False
    assert capture_output is True
    if "--version" in arguments:
        return subprocess.CompletedProcess(arguments, 0, b"tesseract 5.4.0\n", b"")
    if "--list-langs" in arguments:
        return subprocess.CompletedProcess(arguments, 0, b"List of available languages in tessdata directory (2):\neng\nosd\n", b"")
    assert input == png()
    assert "stdin" in arguments and "stdout" in arguments and "tsv" in arguments
    assert timeout <= 2.0
    return subprocess.CompletedProcess(arguments, 0, TSV, b"")


def test_tesseract_is_optional_explicit_and_reports_external_setup(tmp_path):
    provider = make_provider(tmp_path, fake_runner)
    status = provider.inspect()
    assert status.engine_available is True
    assert status.languages == ("eng", "osd")
    assert "Install Tesseract OCR" in status.installation_guidance
    assert provider.is_available()
    assert provider.supports_language("eng")
    assert not provider.supports_language("spa")
    assert str(tmp_path) not in repr(status)
    assert str(tmp_path) not in repr(status)


def test_tesseract_converts_tsv_words_into_bounded_provenance_results(tmp_path):
    provider = make_provider(tmp_path, fake_runner)
    result = provider_service(provider).recognize(image(), language="eng")
    assert result.status is OcrStatus.SUCCESS
    assert result.regions[0].text == "Hello"
    assert result.regions[0].confidence == pytest.approx(0.965)
    assert result.regions[0].bounding_box == (0, 0, 2, 1)
    assert result.untrusted is True


def provider_service(provider):
    from app.integrations.ocr import OcrService
    return OcrService(provider)


def test_missing_engine_and_language_data_are_reported_without_downloads(tmp_path):
    missing = TesseractLocalProvider(tmp_path / "missing.exe", runner=fake_runner)
    result = provider_service(missing).recognize(image(), language="eng")
    assert result.status is OcrStatus.UNAVAILABLE
    assert "download" not in (result.diagnostic or "").lower()

    provider = make_provider(tmp_path, fake_runner)
    result = provider_service(provider).recognize(image(), language="spa")
    assert result.status is OcrStatus.UNSUPPORTED


def test_process_timeout_permission_error_and_malformed_image_fail_safely(tmp_path):
    def timed_runner(*args, **kwargs):
        if "--version" in args[0]:
            return subprocess.CompletedProcess(args[0], 0, b"version", b"")
        if "--list-langs" in args[0]:
            return subprocess.CompletedProcess(args[0], 0, b"eng\n", b"")
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    provider = make_provider(tmp_path, timed_runner)
    timed = provider_service(provider).recognize(image(), language="eng")
    assert timed.status is OcrStatus.TIMEOUT

    def denied_runner(arguments, **kwargs):
        raise PermissionError("C:\\private\\secret executable")

    denied = provider_service(make_provider(tmp_path / "denied", denied_runner)).recognize(image(), language="eng")
    assert denied.status is OcrStatus.UNAVAILABLE
    assert "private" not in (denied.diagnostic or "")
    assert "secret" not in (denied.diagnostic or "")

    attachment = image()
    malformed = replace(attachment, _data=b"not an image")
    with pytest.raises(ValueError, match="provenance"):
        provider_service(provider).recognize(malformed, language="eng")


def test_malformed_or_oversized_engine_output_is_sanitized(tmp_path):
    def malformed_runner(arguments, **kwargs):
        if "--version" in arguments:
            return subprocess.CompletedProcess(arguments, 0, b"version", b"")
        if "--list-langs" in arguments:
            return subprocess.CompletedProcess(arguments, 0, b"eng\n", b"")
        return subprocess.CompletedProcess(arguments, 0, b"not-tsv", b"token=hidden")

    result = provider_service(make_provider(tmp_path, malformed_runner)).recognize(image(), language="eng")
    assert result.status is OcrStatus.FAILED
    assert "hidden" not in (result.diagnostic or "")

    class LargeOutput:
        returncode = 0
        stdout = b"x" * (TesseractLocalProvider.MAX_TSV_BYTES + 1)
        stderr = b""

    def large_runner(arguments, **kwargs):
        if "--version" in arguments:
            return subprocess.CompletedProcess(arguments, 0, b"version", b"")
        if "--list-langs" in arguments:
            return subprocess.CompletedProcess(arguments, 0, b"eng\n", b"")
        return LargeOutput()

    output = make_provider(tmp_path / "large", large_runner)
    assert provider_service(output).recognize(image(), language="eng").status is OcrStatus.FAILED
