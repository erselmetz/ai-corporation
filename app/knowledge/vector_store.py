"""Vector store protocol and optional ChromaDB adapter."""
from typing import Protocol, Sequence
import os


class VectorStore(Protocol):
    def upsert(self, ids: Sequence[str], vectors: Sequence[Sequence[float]], metadata: Sequence[dict]) -> None: ...

    def search(self, vector: Sequence[float], where: dict, limit: int) -> Sequence[tuple[str, float, dict]]: ...

    def delete_source(self, source_key: str) -> None: ...

    def delete_memory(self, scope: str, scope_id: str, memory_id: str) -> None: ...

    def inspect_source(self, source_key: str, limit: int) -> Sequence[dict]: ...

    def stats(self) -> dict: ...


class ChromaVectorStore:
    COLLECTION = "erselmetz_approved_knowledge_v1"

    def __init__(self, path: str):
        from pathlib import Path

        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise RuntimeError("Optional local vector-store dependency is unavailable") from None
        directory = Path(path).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        self._directory = directory
        self._collection = chromadb.PersistentClient(
            path=str(directory), settings=Settings(anonymized_telemetry=False)
        ).get_or_create_collection(
            self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def upsert(self, ids, vectors, metadata):
        # Content is not copied into Chroma; every hit loads current content from
        # the authoritative memory store after owner/scope/revision checks.
        self._collection.upsert(ids=list(ids), embeddings=[list(v) for v in vectors], metadatas=list(metadata))

    def search(self, vector, where, limit):
        result = self._collection.query(query_embeddings=[list(vector)], where=where, n_results=limit)
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadata = result.get("metadatas", [[]])[0]
        return tuple((str(item_id), float(distance), dict(meta)) for item_id, distance, meta in zip(ids, distances, metadata))

    def delete_source(self, source_key):
        self._collection.delete(where={"source_key": source_key})

    def delete_memory(self, scope, scope_id, memory_id):
        self._collection.delete(where={"$and": [
            {"scope": scope}, {"scope_id": scope_id}, {"memory_id": memory_id}
        ]})

    def inspect_source(self, source_key, limit):
        result = self._collection.get(where={"source_key": source_key}, limit=limit,
                                      include=["metadatas"])
        return tuple(dict(item) for item in result.get("metadatas", []) if item is not None)

    def stats(self):
        # Measure only the explicitly configured vector-store directory. Bound
        # traversal and do not follow symlinks; no path or file names are exposed.
        max_entries = 4096
        pending = [self._directory]
        total_bytes = 0
        entries = 0
        complete = True
        try:
            while pending:
                directory = pending.pop()
                with os.scandir(directory) as children:
                    for child in children:
                        entries += 1
                        if entries > max_entries:
                            complete = False
                            pending.clear()
                            break
                        if child.is_dir(follow_symlinks=False):
                            pending.append(self._directory / child.path if not os.path.isabs(child.path) else child.path)
                        elif child.is_file(follow_symlinks=False):
                            total_bytes += child.stat(follow_symlinks=False).st_size
        except OSError:
            complete = False
        try:
            vector_count = self._collection.count()
        except Exception:
            vector_count = None
        return {"vector_count": vector_count,
                "storage_bytes": total_bytes if complete else None,
                "storage_complete": complete,
                "storage_entries_scanned": min(entries, max_entries)}
