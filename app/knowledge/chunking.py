"""Deterministic bounded text chunking."""

MAX_SOURCE_BYTES = 8192
MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP_CHARS = 120
MAX_CHUNKS = 16


def chunk_text(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("Knowledge content must be text")
    if not text.strip() or len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Knowledge content must be nonempty and at most 8192 UTF-8 bytes")
    normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + MAX_CHUNK_CHARS)
        if end < len(normalized):
            boundary = normalized.rfind(" ", start + MAX_CHUNK_CHARS // 2, end)
            if boundary > start:
                end = boundary
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if len(chunks) > MAX_CHUNKS:
            raise ValueError("Knowledge content produces too many chunks")
        if end >= len(normalized):
            break
        start = max(start + 1, end - CHUNK_OVERLAP_CHARS)
    return tuple(chunks)
