"""Explicitly configured optional adapter for a locally installed Tesseract CLI."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from pathlib import Path
import re
import subprocess
from typing import Callable, Sequence

from app.integrations.ocr import OcrImage, OcrProviderTimeout, OcrRegion, OcrService


@dataclass(frozen=True)
class TesseractStatus:
    engine_available: bool
    languages: tuple[str, ...]
    diagnostic: str | None = None
    installation_guidance: str = (
        "Install Tesseract OCR and the desired traineddata language files separately, "
        "then configure the executable path. This adapter never downloads or installs them."
    )


class TesseractLocalProvider:
    """Runs Tesseract with stdin/stdout, no shell, and no image temporary files."""

    MAX_TSV_BYTES = 512 * 1024
    MAX_DIAGNOSTIC_BYTES = 4096
    _LANGUAGE = re.compile(r"^[A-Za-z0-9_+-]{2,32}$")

    def __init__(self, executable_path: str | Path, *, tessdata_directory: str | Path | None = None,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self._executable = Path(executable_path).expanduser()
        self._tessdata = Path(tessdata_directory).expanduser() if tessdata_directory is not None else None
        self._runner = runner

    def inspect(self, *, timeout_seconds: float = OcrService.DEFAULT_TIMEOUT_SECONDS) -> TesseractStatus:
        if not self._valid_configuration():
            return TesseractStatus(False, (), "Tesseract executable or language-data configuration is unavailable")
        try:
            version = self._run(["--version"], timeout_seconds=timeout_seconds)
            if version.returncode != 0:
                return TesseractStatus(False, (), "Tesseract engine check failed")
            language_result = self._run(self._list_arguments(), timeout_seconds=timeout_seconds)
            if language_result.returncode != 0:
                return TesseractStatus(False, (), "Tesseract language data could not be listed")
            languages = self._parse_languages(language_result.stdout)
            return TesseractStatus(True, languages, None if languages else "No language data is installed")
        except OcrProviderTimeout:
            return TesseractStatus(False, (), "Tesseract check timed out")
        except (OSError, ValueError):
            return TesseractStatus(False, (), "Tesseract engine or language data is unavailable")

    def is_available(self) -> bool:
        if not self._valid_configuration():
            return False
        try:
            result = self._run(["--version"], timeout_seconds=OcrService.DEFAULT_TIMEOUT_SECONDS)
            return result.returncode == 0
        except (OcrProviderTimeout, OSError, ValueError):
            return False

    def supports_language(self, language: str) -> bool:
        if not isinstance(language, str) or not self._LANGUAGE.fullmatch(language):
            return False
        result = self._run(self._list_arguments(), timeout_seconds=OcrService.DEFAULT_TIMEOUT_SECONDS)
        if result.returncode != 0:
            raise RuntimeError("Tesseract language check failed")
        return language in self._parse_languages(result.stdout)

    def recognize(self, image: OcrImage, *, timeout_seconds: float) -> Sequence[OcrRegion]:
        arguments = ["stdin", "stdout", "-l", image.language]
        if self._tessdata is not None:
            arguments.extend(["--tessdata-dir", str(self._tessdata)])
        arguments.append("tsv")
        result = self._run(arguments, input_data=image._data, timeout_seconds=timeout_seconds)
        if result.returncode != 0:
            raise RuntimeError("Tesseract recognition failed")
        if len(result.stdout) > self.MAX_TSV_BYTES:
            raise ValueError("Tesseract output exceeded supported limits")
        try:
            output = result.stdout.decode("utf-8", errors="strict")
            rows = csv.DictReader(io.StringIO(output), delimiter="\t")
            required = {"left", "top", "width", "height", "conf", "text"}
            if not rows.fieldnames or not required.issubset(rows.fieldnames):
                raise ValueError("Tesseract output format is invalid")
            regions: list[OcrRegion] = []
            total = 0
            for row in rows:
                text = (row.get("text") or "").strip()
                if not text:
                    continue
                try:
                    left, top = int(row["left"]), int(row["top"])
                    width, height = int(row["width"]), int(row["height"])
                    confidence = float(row["conf"]) / 100.0
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("Tesseract output format is invalid") from exc
                if confidence < 0:
                    continue
                total += len(text)
                if (len(regions) >= OcrService.MAX_REGIONS
                        or len(text) > OcrService.MAX_REGION_TEXT_CHARS
                        or total > OcrService.MAX_TOTAL_TEXT_CHARS):
                    raise ValueError("Tesseract output exceeded supported limits")
                regions.append(OcrRegion(text, confidence,
                                         (left, top, left + width, top + height)))
            return tuple(regions)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValueError("Tesseract output format is invalid") from exc

    def _run(self, arguments: list[str], *, timeout_seconds: float,
             input_data: bytes | None = None) -> subprocess.CompletedProcess:
        timeout = min(OcrService.MAX_TIMEOUT_SECONDS, max(0.05, timeout_seconds * 0.8))
        try:
            result = self._runner(
                [str(self._executable), *arguments],
                input=input_data,
                capture_output=True,
                check=False,
                shell=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrProviderTimeout("Tesseract operation timed out") from exc
        if len(result.stdout or b"") > self.MAX_TSV_BYTES or len(result.stderr or b"") > self.MAX_DIAGNOSTIC_BYTES:
            raise ValueError("Tesseract output exceeded supported limits")
        return result

    def _list_arguments(self) -> list[str]:
        arguments = ["--list-langs"]
        if self._tessdata is not None:
            arguments.extend(["--tessdata-dir", str(self._tessdata)])
        return arguments

    def _valid_configuration(self) -> bool:
        if not self._executable.is_absolute() or not self._executable.is_file():
            return False
        if self._tessdata is not None and (not self._tessdata.is_absolute() or not self._tessdata.is_dir()):
            return False
        return True

    @classmethod
    def _parse_languages(cls, output: bytes) -> tuple[str, ...]:
        text = output.decode("utf-8", errors="replace")
        languages = {
            line.strip() for line in text.splitlines()
            if cls._LANGUAGE.fullmatch(line.strip())
        }
        return tuple(sorted(languages)[:128])
