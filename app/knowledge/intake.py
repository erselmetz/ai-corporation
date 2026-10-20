"""Bounded local text extraction for owner-approved knowledge intake."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePath
import re
from xml.etree import ElementTree
from zipfile import ZipFile

MAX_UPLOAD_BYTES = 1_048_576
MAX_EXTRACTED_BYTES = 8192
MAX_PDF_PAGES = 20
MAX_DOCX_ENTRIES = 256
MAX_DOCX_XML_BYTES = 2 * 1024 * 1024

_TEXT_SUFFIXES = {
    ".txt", ".md", ".csv", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".jsx", ".json", ".html", ".htm", ".css", ".scss", ".yaml", ".yml",
    ".toml", ".ini", ".xml", ".sql", ".sh", ".ps1", ".bat", ".java",
    ".c", ".h", ".cpp", ".hpp", ".go", ".rs", ".rb", ".php", ".cs",
    ".kt", ".swift", ".vue", ".svelte", ".mdx", ".rst", ".log",
}


def source_name(filename: str | None) -> str:
    value = PurePath((filename or "note.txt").replace("\\", "/")).name
    value = re.sub(r"[^\w .()\[\]-]", "_", value, flags=re.UNICODE).strip(" .")
    return (value or "note.txt")[:128]


def extract_upload(filename: str | None, data: bytes) -> tuple[str, str]:
    if not isinstance(data, bytes) or not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Choose a non-empty file no larger than 1 MiB")
    name = source_name(filename)
    suffix = PurePath(name).suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        try:
            text = data.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            raise ValueError("Text, data, and code files must use UTF-8 encoding") from None
    elif suffix == ".docx":
        text = _extract_docx(data)
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
        raise ValueError("Choose a supported text, code, CSV, Markdown, PDF, or DOCX file")
    if not text.strip() or len(text.encode("utf-8")) > MAX_EXTRACTED_BYTES:
        raise ValueError("Extracted content must be non-empty and at most 8192 UTF-8 bytes")
    return text, name


def _extract_docx(data: bytes) -> str:
    """Read only the bounded main document XML; never unpack Office files to disk."""
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise ValueError("DOCX contains too many internal entries")
            document = next((item for item in entries if item.filename == "word/document.xml"), None)
            if (document is None or document.file_size <= 0
                    or document.file_size > MAX_DOCX_XML_BYTES
                    or (document.compress_size == 0 and document.file_size > 0)
                    or (document.compress_size > 0 and document.file_size / document.compress_size > 200)):
                raise ValueError("DOCX document content is missing or exceeds the extraction limit")
            payload = archive.read(document)
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise ValueError("DOCX document declarations are not supported")
        root = ElementTree.fromstring(payload)
    except ValueError:
        raise
    except Exception:
        raise ValueError("DOCX text could not be extracted; the file may be malformed") from None
    pieces = []
    extracted_bytes = 0
    for element in root.iter():
        if element.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t" and element.text:
            pieces.append(element.text)
            extracted_bytes += len(element.text.encode("utf-8"))
            if extracted_bytes > MAX_EXTRACTED_BYTES:
                raise ValueError("Extracted DOCX text exceeds the 8192-byte note limit")
        elif element.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p":
            pieces.append("\n")
    return "".join(pieces)
