"""Embedding provider boundary and optional offline sentence-transformers adapter."""
from typing import Protocol, Sequence
from pathlib import Path
from threading import Lock
import hashlib


class EmbeddingProvider(Protocol):
    @property
    def identity(self) -> str: ...

    def embed_one(self, text: str) -> Sequence[float]: ...

    def embed_batch(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class SentenceTransformerEmbeddingProvider:
    """Loads only an already-present local model; it never downloads model files."""
    MAX_BATCH = 32

    def __init__(self, model_path: str):
        path = Path(model_path).expanduser().resolve(strict=True)
        if not path.is_dir():
            raise ValueError("Embedding model path must be an existing local directory")
        self._path = path
        digest = hashlib.sha256(str(path).casefold().encode("utf-8")).hexdigest()[:12]
        self._identity = f"local-embedding-{digest}"
        self._model = None
        self._lock = Lock()

    @property
    def identity(self) -> str:
        return self._identity

    def embed_one(self, text: str):
        return self.embed_batch((text,))[0]

    def _loaded_model(self):
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(
                        str(self._path), local_files_only=True, trust_remote_code=False)
                except Exception:
                    raise RuntimeError("The configured local embedding model could not be loaded") from None
            return self._model

    def embed_batch(self, texts):
        if not 1 <= len(texts) <= self.MAX_BATCH:
            raise ValueError("Embedding batch must contain 1 to 32 texts")
        if any(not isinstance(text, str) or not text or len(text.encode("utf-8")) > 8192 for text in texts):
            raise ValueError("Embedding inputs must be nonempty and at most 8192 UTF-8 bytes")
        try:
            vectors = self._loaded_model().encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
            return tuple(tuple(float(value) for value in row) for row in vectors)
        except Exception:
            raise RuntimeError("Local embedding failed") from None
