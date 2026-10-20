"""Owner-authorized Brain graph records; relationships are source-to-chunk only."""
from __future__ import annotations

from pathlib import PurePosixPath

from app.memory import MemoryScope
from .chunking import chunk_text

MAX_GRAPH_SOURCES = 100


def build_owner_brain_graph(manager, owner_id: str, now):
    records = manager.list(actor_id=owner_id, scope=MemoryScope.OWNER,
                           scope_id=owner_id, limit=MAX_GRAPH_SOURCES, now=now)
    nodes, edges = [], []
    for item in records:
        if item.get("expired") is True:
            continue
        try:
            record = manager.inspect(item["id"], actor_id=owner_id,
                                     scope=MemoryScope.OWNER, scope_id=owner_id,
                                     now=now)
            chunks = chunk_text(record["content"])
        except (KeyError, PermissionError, ValueError):
            # The source may expire or be withdrawn between list and inspection.
            continue
        source_id = record["id"]
        reference = str(record.get("source_reference") or "Owner note")[:128]
        suffix = PurePosixPath(reference.replace("\\", "/")).suffix.lower().lstrip(".")
        cluster = suffix if suffix else "note"
        document_node = f"document:{source_id}"
        nodes.append({
            "id": document_node, "kind": "document", "source_id": source_id,
            "source_reference": reference, "label": reference, "cluster": cluster,
            "state": "ready", "chunk_count": len(chunks),
            "expires_at": record["expires_at"].isoformat(),
        })
        for position in range(1, len(chunks) + 1):
            chunk_id = f"chunk:{source_id}#{position}"
            nodes.append({
                "id": chunk_id, "kind": "chunk", "source_id": source_id,
                "source_reference": reference, "label": f"Chunk {position}",
                "cluster": cluster, "chunk_position": position, "state": "ready",
                "expires_at": record["expires_at"].isoformat(),
            })
            edges.append({"from": document_node, "to": chunk_id, "kind": "same-source"})
    return {"nodes": nodes, "edges": edges,
            "basis": "Derived file-type/note groups from authorized source metadata and source-to-chunk relationships; no semantic similarity is asserted.",
            "limits": {"sources": MAX_GRAPH_SOURCES}}


def inspect_owner_brain_node(manager, owner_id: str, node_id: str, now):
    if not isinstance(node_id, str) or len(node_id) > 300:
        raise ValueError("Brain node identifier is invalid")
    if node_id.startswith("document:"):
        memory_id, position = node_id[len("document:"):], None
    elif node_id.startswith("chunk:"):
        reference = node_id[len("chunk:"):]
        memory_id, separator, raw_position = reference.rpartition("#")
        if not separator or not raw_position.isascii() or not raw_position.isdecimal():
            raise ValueError("Brain chunk identifier is invalid")
        position = int(raw_position)
        if not 1 <= position <= 16:
            raise ValueError("Brain chunk identifier is invalid")
    else:
        raise ValueError("Brain node identifier is invalid")
    record = manager.inspect(memory_id, actor_id=owner_id, scope=MemoryScope.OWNER,
                             scope_id=owner_id, now=now)
    content = record["content"]
    if position is not None:
        chunks = chunk_text(content)
        if position > len(chunks):
            raise KeyError(memory_id)
        content = chunks[position - 1]
    return {"id": node_id, "source_id": memory_id,
            "source_reference": str(record.get("source_reference") or "Owner note")[:128],
            "kind": "chunk" if position is not None else "document",
            "chunk_position": position, "content": content,
            "expires_at": record["expires_at"].isoformat()}
