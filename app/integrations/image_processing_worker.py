from __future__ import annotations

"""Private worker for optional image transforms; input and output use bounded stdio JSON."""

import base64
import binascii
from io import BytesIO
import json
import sys
import warnings


MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_WIDTH = 4096
MAX_HEIGHT = 4096
MAX_PIXELS = 8_000_000
MAX_DECODED_BYTES = MAX_PIXELS * 4
MAX_REDACTION_BOXES = 64


def run(payload: dict) -> bytes:
    from PIL import Image, ImageDraw, ImageOps

    if not isinstance(payload, dict) or set(payload) != {"operation", "options", "media_type", "data"}:
        raise ValueError
    operation, options, media_type = payload["operation"], payload["options"], payload["media_type"]
    if not isinstance(options, dict) or media_type not in {"image/png", "image/jpeg"}:
        raise ValueError
    source = base64.b64decode(payload["data"], validate=True)
    if not source or len(source) > MAX_INPUT_BYTES:
        raise ValueError
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        image = Image.open(BytesIO(source), formats=["PNG", "JPEG"])
        expected_format = "PNG" if media_type == "image/png" else "JPEG"
        if image.format != expected_format:
            raise ValueError
        width, height = image.size
        if (width < 1 or height < 1 or width > MAX_WIDTH or height > MAX_HEIGHT
                or width * height > MAX_PIXELS or width * height * 4 > MAX_DECODED_BYTES):
            raise ValueError
        image.load()
        image = ImageOps.exif_transpose(image)
    if operation == "resize":
        if set(options) != {"max_width", "max_height"}:
            raise ValueError
        max_width, max_height = options["max_width"], options["max_height"]
        if type(max_width) is not int or type(max_height) is not int or not (1 <= max_width <= MAX_WIDTH and 1 <= max_height <= MAX_HEIGHT):
            raise ValueError
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        output_format = "PNG" if expected_format == "PNG" else "JPEG"
    elif operation == "convert":
        if set(options) != {"output_format"} or options["output_format"] not in {"png", "jpeg"}:
            raise ValueError
        output_format = "PNG" if options["output_format"] == "png" else "JPEG"
    elif operation == "redact":
        if set(options) != {"boxes"} or not isinstance(options["boxes"], list) or not 1 <= len(options["boxes"]) <= MAX_REDACTION_BOXES:
            raise ValueError
        image = image.convert("RGBA")
        draw = ImageDraw.Draw(image)
        for box in options["boxes"]:
            if (not isinstance(box, list) or len(box) != 4
                    or any(type(item) is not int for item in box)):
                raise ValueError
            x, y, box_width, box_height = box
            if (x < 0 or y < 0 or box_width < 1 or box_height < 1
                    or x + box_width > image.width or y + box_height > image.height):
                raise ValueError
            draw.rectangle((x, y, x + box_width - 1, y + box_height - 1), fill=(0, 0, 0, 255))
        output_format = "PNG" if expected_format == "PNG" else "JPEG"
    else:
        raise ValueError
    if output_format == "JPEG":
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
    elif image.mode not in {"RGB", "RGBA", "L", "LA", "P", "1"}:
        image = image.convert("RGBA")
    output = BytesIO()
    if output_format == "JPEG":
        image.save(output, format="JPEG", quality=85, optimize=False, progressive=False)
    else:
        image.save(output, format="PNG", compress_level=6)
    result = output.getvalue()
    if not result or len(result) > MAX_OUTPUT_BYTES:
        raise ValueError
    return result


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES * 2 + 4096)
        if not raw or len(raw) > MAX_INPUT_BYTES * 2 + 4096:
            return 2
        payload = json.loads(raw)
        result = run(payload)
        sys.stdout.write(json.dumps({"data": base64.b64encode(result).decode("ascii")}, separators=(",", ":")))
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
