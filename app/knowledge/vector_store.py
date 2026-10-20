"""Vector store protocol and optional ChromaDB adapter."""
from typing import Protocol, Sequence
from contextlib import contextmanager
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


class FaissVectorStore:
    """Bounded local FAISS search with SQLite metadata and vectors as its source of truth.

    FAISS is optional and imported only when this adapter is explicitly constructed.
    SQLite remains authoritative so an interrupted index write can be rebuilt safely.
    """

    MAX_VECTORS = 50_000
    MAX_DIMENSIONS = 16_384
    MAX_METADATA_BYTES = 8_192

    def __init__(self, path: str, *, faiss_module=None, numpy_module=None):
        from pathlib import Path
        import sqlite3
        from threading import RLock

        try:
            if faiss_module is None:
                import faiss as faiss_module
            if numpy_module is None:
                import numpy as numpy_module
        except ImportError:
            raise RuntimeError("Optional local FAISS capability is unavailable") from None
        self._faiss = faiss_module
        self._numpy = numpy_module
        self._directory = Path(path).expanduser().resolve()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._database = self._directory / "brain-vectors.sqlite3"
        self._lock = RLock()
        self._initialize()
        self._rebuild_indices()

    def _connect(self):
        import sqlite3
        connection = sqlite3.connect(self._database, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS brain_vectors (
                vector_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id TEXT NOT NULL UNIQUE,
                dimension INTEGER NOT NULL,
                vector BLOB NOT NULL,
                metadata_json TEXT NOT NULL
            )""")

    @classmethod
    def _validated_vector(cls, vector):
        import math
        import struct
        try:
            values = tuple(float(value) for value in vector)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Embedding vector is invalid") from None
        if (not 1 <= len(values) <= cls.MAX_DIMENSIONS
                or any(not math.isfinite(value) for value in values)):
            raise ValueError("Embedding vector is invalid")
        magnitude = math.sqrt(sum(value * value for value in values))
        if not math.isfinite(magnitude) or magnitude <= 1e-12:
            raise ValueError("Embedding vector is invalid")
        normalized = tuple(value / magnitude for value in values)
        return normalized, struct.pack(f"<{len(normalized)}f", *normalized)

    @staticmethod
    def _matches(metadata, where):
        conditions = where.get("$and", []) if isinstance(where, dict) else None
        if conditions is None or not isinstance(conditions, list):
            raise ValueError("Vector search filter is invalid")
        for condition in conditions:
            if not isinstance(condition, dict) or len(condition) != 1:
                raise ValueError("Vector search filter is invalid")
            key, expected = next(iter(condition.items()))
            if not isinstance(key, str) or metadata.get(key) != expected:
                return False
        return True

    def _rebuild_indices(self):
        import os
        import struct
        import tempfile
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT vector_id, dimension, vector FROM brain_vectors ORDER BY vector_id").fetchall()
            if len(rows) > self.MAX_VECTORS:
                raise RuntimeError("Local vector index exceeds its configured capacity")
            grouped = {}
            for row in rows:
                grouped.setdefault(int(row["dimension"]), []).append(row)
            indices = {}
            expected_files = set()
            for dimension, items in grouped.items():
                base = self._faiss.IndexFlatIP(dimension)
                index = self._faiss.IndexIDMap2(base)
                vectors = [struct.unpack(f"<{dimension}f", row["vector"]) for row in items]
                ids = [int(row["vector_id"]) for row in items]
                matrix = self._numpy.asarray(vectors, dtype="float32")
                labels = self._numpy.asarray(ids, dtype="int64")
                index.add_with_ids(matrix, labels)
                path = self._index_path(dimension)
                expected_files.add(path.name)
                descriptor, temporary_name = tempfile.mkstemp(prefix=".brain-index-", suffix=".tmp", dir=self._directory)
                os.close(descriptor)
                try:
                    self._faiss.write_index(index, temporary_name)
                    os.replace(temporary_name, path)
                finally:
                    if os.path.exists(temporary_name):
                        os.unlink(temporary_name)
                indices[dimension] = index
            for item in self._directory.glob("brain-vectors-*.faiss"):
                if item.name not in expected_files:
                    item.unlink(missing_ok=True)
            self._indices = indices

    def _index_path(self, dimension):
        return self._directory / f"brain-vectors-{dimension}.faiss"

    def upsert(self, ids: Sequence[str], vectors: Sequence[Sequence[float]], metadata: Sequence[dict]) -> None:
        import json
        if not (len(ids) == len(vectors) == len(metadata)) or not ids:
            raise ValueError("Vector batch is invalid")
        if len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item or len(item) > 256 for item in ids):
            raise ValueError("Vector identifiers are invalid")
        rows = []
        for chunk_id, vector, item_metadata in zip(ids, vectors, metadata):
            normalized, packed = self._validated_vector(vector)
            if not isinstance(item_metadata, dict):
                raise ValueError("Vector metadata is invalid")
            encoded = json.dumps(item_metadata, ensure_ascii=True, separators=(",", ":"))
            if len(encoded) > self.MAX_METADATA_BYTES:
                raise ValueError("Vector metadata exceeds its size limit")
            rows.append((chunk_id, len(normalized), packed, encoded))
        with self._lock, self._connection() as connection:
            current = connection.execute("SELECT COUNT(*) FROM brain_vectors").fetchone()[0]
            additions = sum(1 for chunk_id in ids if connection.execute(
                "SELECT 1 FROM brain_vectors WHERE chunk_id = ?", (chunk_id,)).fetchone() is None)
            if current + additions > self.MAX_VECTORS:
                raise ValueError("Local vector index is at capacity")
            connection.executemany("""INSERT INTO brain_vectors(chunk_id, dimension, vector, metadata_json)
                VALUES (?, ?, ?, ?) ON CONFLICT(chunk_id) DO UPDATE SET
                dimension=excluded.dimension, vector=excluded.vector, metadata_json=excluded.metadata_json""", rows)
        self._rebuild_indices()

    def search(self, vector: Sequence[float], where: dict, limit: int) -> Sequence[tuple[str, float, dict]]:
        import json
        import math
        normalized, _ = self._validated_vector(vector)
        if type(limit) is not int or not 1 <= limit <= self.MAX_VECTORS:
            raise ValueError("Vector search result limit is invalid")
        with self._lock, self._connection() as connection:
            index = self._indices.get(len(normalized))
            if index is None or index.ntotal == 0:
                return ()
            rows = connection.execute("SELECT vector_id, chunk_id, metadata_json FROM brain_vectors").fetchall()
            allowed = {}
            for row in rows:
                try:
                    metadata = json.loads(row["metadata_json"])
                except (ValueError, TypeError):
                    continue
                if self._matches(metadata, where):
                    allowed[int(row["vector_id"])] = (row["chunk_id"], metadata)
            if not allowed:
                return ()
            query = self._numpy.asarray([normalized], dtype="float32")
            scores, labels = index.search(query, min(int(index.ntotal), self.MAX_VECTORS))
            matches = []
            for score, label in zip(scores[0], labels[0]):
                vector_id = int(label)
                if vector_id not in allowed:
                    continue
                similarity = float(score)
                if not math.isfinite(similarity):
                    continue
                chunk_id, metadata = allowed[vector_id]
                matches.append((chunk_id, 1.0 - max(-1.0, min(1.0, similarity)), metadata))
            matches.sort(key=lambda item: (item[1], item[0]))
            return tuple(matches[:limit])

    def delete_source(self, source_key: str) -> None:
        import json
        with self._lock, self._connection() as connection:
            rows = connection.execute("SELECT vector_id, metadata_json FROM brain_vectors").fetchall()
            ids = [row["vector_id"] for row in rows if json.loads(row["metadata_json"]).get("source_key") == source_key]
            connection.executemany("DELETE FROM brain_vectors WHERE vector_id = ?", [(item,) for item in ids])
        if ids:
            self._rebuild_indices()

    def delete_memory(self, scope: str, scope_id: str, memory_id: str) -> None:
        import json
        with self._lock, self._connection() as connection:
            rows = connection.execute("SELECT vector_id, metadata_json FROM brain_vectors").fetchall()
            ids = []
            for row in rows:
                data = json.loads(row["metadata_json"])
                if (data.get("scope"), data.get("scope_id"), data.get("memory_id")) == (scope, scope_id, memory_id):
                    ids.append(row["vector_id"])
            connection.executemany("DELETE FROM brain_vectors WHERE vector_id = ?", [(item,) for item in ids])
        if ids:
            self._rebuild_indices()

    def inspect_source(self, source_key: str, limit: int) -> Sequence[dict]:
        import json
        if type(limit) is not int or not 1 <= limit <= self.MAX_VECTORS:
            raise ValueError("Vector inspection limit is invalid")
        with self._connection() as connection:
            rows = connection.execute("SELECT metadata_json FROM brain_vectors").fetchall()
        found = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            if metadata.get("source_key") == source_key:
                found.append(metadata)
                if len(found) >= limit:
                    break
        return tuple(found)

    def stats(self) -> dict:
        import os
        with self._connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM brain_vectors").fetchone()[0]
        try:
            files = [self._database, *self._directory.glob("brain-vectors-*.faiss")]
            size = sum(item.stat().st_size for item in files if item.is_file())
            return {"vector_count": count, "storage_bytes": size,
                    "storage_complete": True, "storage_entries_scanned": len(files)}
        except OSError:
            return {"vector_count": count, "storage_bytes": None,
                    "storage_complete": False, "storage_entries_scanned": 0}
