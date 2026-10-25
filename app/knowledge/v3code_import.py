"""Parse legacy v3code Brain data into bounded, owner-private note bundles."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json

from .intake import source_name

MAX_IMPORT_BYTES = 12 * 1024 * 1024
MAX_IMPORT_ROWS = 2000
MAX_TOTAL_TEXT_BYTES = 2 * 1024 * 1024
MAX_NOTE_BYTES = 8100
_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class V3CodeBrainNote:
    id: str
    source_reference: str
    content: str


@dataclass(frozen=True)
class V3CodeBrainPlan:
    digest: str
    chunk_count: int
    source_count: int
    total_text_bytes: int
    notes: tuple[V3CodeBrainNote, ...]


def _utf8_size(value: str, label: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError(f"{label} must contain valid UTF-8 text") from None


def _truncate_utf8(value: str, limit: int) -> str:
    return value.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def build_v3code_brain_plan(data: bytes, *, owner_id: str) -> V3CodeBrainPlan:
    """Validate legacy rows, discard stored vectors, and bundle chunks by source.

    The result contains only text and sanitized source names. It never trusts or
    reuses vectors from the legacy JSON file.
    """
    if not isinstance(data, bytes) or not data or len(data) > MAX_IMPORT_BYTES:
        raise ValueError("Choose a non-empty Brain export no larger than 12 MiB")
    if not isinstance(owner_id, str) or not owner_id.strip() or _utf8_size(owner_id, "Owner identity") > 256:
        raise ValueError("Owner identity is invalid")
    try:
        rows = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("The selected file is not valid UTF-8 Brain JSON") from None
    if not isinstance(rows, list) or not rows or len(rows) > MAX_IMPORT_ROWS:
        raise ValueError(f"Brain JSON must contain 1 to {MAX_IMPORT_ROWS} entries")

    grouped: OrderedDict[str, list[str]] = OrderedDict()
    total_text_bytes = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("source"), str) or not isinstance(row.get("text"), str):
            raise ValueError("Each Brain entry must contain text and a source name")
        if not row["source"].strip():
            raise ValueError("Each Brain entry must contain a nonempty source name")
        _utf8_size(row["source"], "Brain source name")
        source = source_name(row["source"])
        text = row["text"]
        text_bytes = _utf8_size(text, "Brain entry")
        if not text.strip() or text_bytes > MAX_NOTE_BYTES:
            raise ValueError("Brain entries must contain non-empty text within the note size limit")
        total_text_bytes += text_bytes
        if total_text_bytes > MAX_TOTAL_TEXT_BYTES:
            raise ValueError("Brain text exceeds the 2 MiB import limit")
        grouped.setdefault(source, []).append(text)

    digest = hashlib.sha256(data).hexdigest()
    notes: list[V3CodeBrainNote] = []
    position = 0
    for source, chunks in grouped.items():
        part = 1
        content = ""
        for text in chunks:
            candidate = text if not content else content + _SEPARATOR + text
            if _utf8_size(candidate, "Brain note") > MAX_NOTE_BYTES and content:
                position += 1
                notes.append(_make_note(owner_id, digest, position, source, part, content))
                part += 1
                content = text
            else:
                content = candidate
        if content:
            position += 1
            notes.append(_make_note(owner_id, digest, position, source, part, content))

    return V3CodeBrainPlan(digest, len(rows), len(grouped), total_text_bytes, tuple(notes))


def _make_note(owner_id: str, digest: str, position: int, source: str,
               part: int, content: str) -> V3CodeBrainNote:
    identity = hashlib.sha256(f"v3code-brain:{owner_id}:{digest}:{position}".encode("utf-8")).hexdigest()
    prefix = "Legacy v3code: "
    suffix = f" (part {part})"
    source_limit = 256 - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    reference = prefix + _truncate_utf8(source, source_limit) + suffix
    return V3CodeBrainNote(identity, reference, content)
