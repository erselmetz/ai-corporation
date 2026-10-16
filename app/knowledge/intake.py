"""Bounded local text extraction for owner-approved knowledge intake."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePath
import re

MAX_UPLOAD_BYTES = 1_048_576
MAX_EXTRACTED_BYTES = 8192
MAX_PDF_PAGES = 20


def source_name(filename: str | None) -> str:
    value = PurePath((filename or "note.txt").replace("\\", "/")).name
    value = re.sub(r"[^\w .()\[\]-]", "_", value, flags=re.UNICODE).strip(" .")
    return (value or "note.txt")[:128]


def extract_upload(filename: str | None, data: bytes) -> tuple[str, str]:
    if not isinstance(data, bytes) or not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Choose a non-empty file no larger than 1 MiB")
    name = source_name(filename)
    suffix = PurePath(name).suffix.lower()
    if suffix in {".txt", ".md"}:
        try:
            text = data.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            raise ValueError("Text and Markdown files must use UTF-8 encoding") from None
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported")
            if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
                raise ValueError("PDF must contain 1 to 20 pages")
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
                if len("\n".join(parts).encode("utf-8")) > MAX_EXTRACTED_BYTES:
                    raise ValueError("Extracted PDF text exceeds the 8192-byte note limit")
            text = "\n".join(parts)
        except ValueError:
            raise
        except Exception:
            raise ValueError("PDF text could not be extracted; scanned or malformed PDFs are unsupported") from None
    else:
        raise ValueError("Choose a .txt, .md, or .pdf file")
    if not text.strip() or len(text.encode("utf-8")) > MAX_EXTRACTED_BYTES:
        raise ValueError("Extracted content must be non-empty and at most 8192 UTF-8 bytes")
    return text, name
