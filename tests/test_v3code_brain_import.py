import json

import pytest

from app.knowledge.v3code_import import MAX_IMPORT_BYTES, build_v3code_brain_plan


def encoded(rows):
    return json.dumps(rows, ensure_ascii=False).encode("utf-8")


def test_v3code_plan_keeps_text_and_source_but_ignores_legacy_vectors():
    payload = encoded([
        {"source": "notes/first.md", "text": "Alpha fact", "vec": [0.1, 0.2]},
        {"source": "notes/first.md", "text": "Beta fact", "vec": [0.3, 0.4], "key": "legacy"},
        {"source": "other.txt", "text": "Gamma fact", "vec": [0.5, 0.6]},
    ])

    plan = build_v3code_brain_plan(payload, owner_id="owner")

    assert plan.chunk_count == 3
    assert plan.source_count == 2
    assert len(plan.notes) == 2
    assert plan.digest == __import__("hashlib").sha256(payload).hexdigest()
    assert all(note.content.encode("utf-8") and len(note.content.encode("utf-8")) <= 8192 for note in plan.notes)
    assert "Alpha fact" in plan.notes[0].content
    assert "Beta fact" in plan.notes[0].content
    assert "0.1" not in plan.notes[0].content
    assert plan.notes[0].source_reference.endswith("first.md (part 1)")
    assert len({note.id for note in plan.notes}) == len(plan.notes)


def test_v3code_plan_is_deterministic_and_splits_large_sources_into_bounded_notes():
    text = "é" * 4000
    payload = encoded([{"source": "large.md", "text": text, "vec": []} for _ in range(5)])

    first = build_v3code_brain_plan(payload, owner_id="owner")
    second = build_v3code_brain_plan(payload, owner_id="owner")

    assert len(first.notes) > 1
    assert [(note.id, note.content) for note in first.notes] == [(note.id, note.content) for note in second.notes]
    assert all(len(note.content.encode("utf-8")) <= 8192 for note in first.notes)
    assert all("large.md" in note.source_reference for note in first.notes)


@pytest.mark.parametrize("payload", [
    b"{}",
    b"[]",
    b"[{\"source\":\"x\",\"text\":\" \"}]",
    b"[{\"source\":\"x\",\"text\":4}]",
    b"[{\"source\":\"x\"}]",
])
def test_v3code_plan_rejects_empty_or_malformed_brains(payload):
    with pytest.raises(ValueError):
        build_v3code_brain_plan(payload, owner_id="owner")


def test_v3code_plan_rejects_oversized_upload_before_json_parsing():
    payload = b" " * (MAX_IMPORT_BYTES + 1)

    with pytest.raises(ValueError, match="12 MiB"):
        build_v3code_brain_plan(payload, owner_id="owner")


def test_v3code_plan_rejects_escaped_invalid_unicode_without_server_error():
    payload = b'[{"source":"x","text":"\\ud800"}]'

    with pytest.raises(ValueError, match="UTF-8"):
        build_v3code_brain_plan(payload, owner_id="owner")


def test_v3code_plan_keeps_source_references_within_utf8_identifier_limit():
    payload = encoded([{"source": "é" * 130, "text": "A fact", "vec": []}])

    plan = build_v3code_brain_plan(payload, owner_id="owner")

    assert len(plan.notes[0].source_reference.encode("utf-8")) <= 256
    assert plan.notes[0].content == "A fact"
