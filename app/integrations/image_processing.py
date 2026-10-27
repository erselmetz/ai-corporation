from __future__ import annotations

"""Optional, bounded local image transformations for explicitly supplied images."""

from dataclasses import dataclass, field
import base64
import binascii
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from app.application.services.chat_images import ChatImageError, image_dimensions


MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_WIDTH = 4096
MAX_HEIGHT = 4096
MAX_PIXELS = 8_000_000
MAX_DECODED_BYTES = MAX_PIXELS * 4
MAX_REDACTION_BOXES = 64
MAX_TIMEOUT_SECONDS = 5.0


class ImageProcessingError(ValueError):
    """Image input or transformation is unsupported, invalid, or out of bounds."""


@dataclass(frozen=True)
class ImageProcessingStatus:
    state: str
    library: str
    version: str | None
    message: str


@dataclass(frozen=True)
class ImageProcessingResult:
    data: bytes = field(repr=False, compare=False)
    media_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    source_sha256: str
    operation: str
    elapsed_ms: int


class PillowImageProcessingAdapter:
    """One-shot Pillow adapter. Pillow is optional and imported only by its worker."""

    backend = "optional-local"

    def __init__(self, *, timeout_seconds: float = 2.0, worker_runner=None):
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or not 0.05 <= timeout_seconds <= MAX_TIMEOUT_SECONDS):
            raise ValueError("Image processing timeout is outside the supported range")
        self._timeout_seconds = float(timeout_seconds)
        self._worker_runner = worker_runner or subprocess.run

    @staticmethod
    def status() -> ImageProcessingStatus:
        if getattr(sys,'frozen',False):
            # The native bundle owns one Python UI/backend process. Reusing its
            # GUI executable as the old bounded decoder would start another app,
            # and moving decoding in-process would discard the hard timeout.
            return ImageProcessingStatus('unavailable','Pillow',None,
                'This image editing tool is not included in this build. Image attachments and reviewed captures remain available.')
        try:
            spec = importlib.util.find_spec("PIL")
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            return ImageProcessingStatus("unavailable", "Pillow", None,
                                         "Optional image processing library is not installed")
        try:
            from importlib.metadata import PackageNotFoundError, version
            try:
                selected_version = version("Pillow")
            except PackageNotFoundError:
                selected_version = "unknown"
        except Exception:
            selected_version = "unknown"
        return ImageProcessingStatus("available", "Pillow", selected_version,
                                     "Optional local image processing is available")

    def resize(self, data: bytes, *, max_width: int, max_height: int) -> ImageProcessingResult:
        if not self._valid_dimension(max_width) or not self._valid_dimension(max_height):
            raise ImageProcessingError("Resize dimensions must be between 1 and 4096")
        return self._run(data, "resize", {"max_width": max_width, "max_height": max_height})

    def convert(self, data: bytes, *, output_format: str) -> ImageProcessingResult:
        if not isinstance(output_format, str) or output_format not in {"png", "jpeg"}:
            raise ImageProcessingError("Output format must be PNG or JPEG")
        return self._run(data, "convert", {"output_format": output_format})

    def redact(self, data: bytes, *, boxes: tuple[tuple[int, int, int, int], ...]) -> ImageProcessingResult:
        try:
            width, height = self._preflight(data)
        except ChatImageError as exc:
            raise ImageProcessingError(str(exc)) from None
        if not isinstance(boxes, tuple) or not 1 <= len(boxes) <= MAX_REDACTION_BOXES:
            raise ImageProcessingError("Redaction requires 1 to 64 pixel-coordinate boxes")
        normalized = []
        for box in boxes:
            if (not isinstance(box, tuple) or len(box) != 4
                    or any(type(value) is not int for value in box)):
                raise ImageProcessingError("Redaction boxes must contain integer x, y, width, and height")
            x, y, box_width, box_height = box
            if (x < 0 or y < 0 or box_width < 1 or box_height < 1
                    or x + box_width > width or y + box_height > height):
                raise ImageProcessingError("Redaction box is outside the source image")
            normalized.append([x, y, box_width, box_height])
        return self._run(data, "redact", {"boxes": normalized})

    def _run(self, data: bytes, operation: str, options: dict[str, object]) -> ImageProcessingResult:
        self._preflight(data)
        if self.status().state != "available":
            raise ImageProcessingError("Optional Pillow image processing is unavailable")
        source_digest = hashlib.sha256(data).hexdigest()
        payload = json.dumps({
            "operation": operation,
            "options": options,
            "media_type": image_dimensions(data)[0],
            "data": base64.b64encode(data).decode("ascii"),
        }, separators=(",", ":"))
        started = time.monotonic()
        worker = Path(__file__).with_name("image_processing_worker.py")
        project_root = worker.resolve().parents[2]
        # Optional capability packs add their verified runtime to the parent's
        # import path. A fresh worker needs that same Pillow root explicitly;
        # do not inherit unrelated dynamic import paths or weaken worker limits.
        import os
        environment = dict(os.environ)
        spec = importlib.util.find_spec("PIL")
        if spec is not None and spec.origin:
            pillow_root = Path(spec.origin).resolve().parent.parent
            environment["PYTHONPATH"] = os.pathsep.join((str(project_root), str(pillow_root)))
        try:
            result = self._worker_runner(
                [sys.executable, str(worker)],
                input=payload,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                cwd=project_root,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ImageProcessingError("Image processing exceeded its time limit") from None
        except (OSError, ValueError):
            raise ImageProcessingError("Image processing worker is unavailable") from None
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if result.returncode != 0:
            raise ImageProcessingError("Image processing failed or the image is malformed")
        if not isinstance(result.stdout, str) or len(result.stdout) > 3_000_000:
            raise ImageProcessingError("Image processing output exceeded its size limit")
        try:
            response = json.loads(result.stdout)
            encoded = response["data"]
            if not isinstance(encoded, str) or len(encoded) > 2_800_000:
                raise ValueError
            output = base64.b64decode(encoded, validate=True)
            media_type, output_width, output_height = image_dimensions(output)
        except (KeyError, TypeError, ValueError, binascii.Error, ChatImageError):
            raise ImageProcessingError("Image processing returned invalid output") from None
        if (not output or len(output) > MAX_OUTPUT_BYTES or output_width > MAX_WIDTH
                or output_height > MAX_HEIGHT or output_width * output_height > MAX_PIXELS
                or len(output) > MAX_DECODED_BYTES):
            raise ImageProcessingError("Processed image exceeds an output limit")
        return ImageProcessingResult(
            data=output,
            media_type=media_type,
            width=output_width,
            height=output_height,
            size_bytes=len(output),
            sha256=hashlib.sha256(output).hexdigest(),
            source_sha256=source_digest,
            operation=operation,
            elapsed_ms=elapsed_ms,
        )

    @staticmethod
    def _preflight(data: bytes) -> tuple[int, int]:
        if not isinstance(data, bytes) or not data or len(data) > MAX_INPUT_BYTES:
            raise ImageProcessingError("Image is empty or exceeds the 2 MiB input limit")
        try:
            media_type, width, height = image_dimensions(data)
        except ChatImageError as exc:
            raise ImageProcessingError(str(exc)) from None
        if (media_type not in {"image/png", "image/jpeg"} or width > MAX_WIDTH
                or height > MAX_HEIGHT or width * height > MAX_PIXELS
                or width * height * 4 > MAX_DECODED_BYTES):
            raise ImageProcessingError("Image dimensions or decoded size exceed the limits")
        return width, height

    @staticmethod
    def _valid_dimension(value: object) -> bool:
        return type(value) is int and 1 <= value <= MAX_WIDTH
