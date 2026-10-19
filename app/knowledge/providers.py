"""Embedding provider boundary and optional offline sentence-transformers adapter."""
from typing import Protocol, Sequence
from pathlib import Path
from threading import Lock
import hashlib
import json
import math
import urllib.error
import urllib.request


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


class OllamaEmbeddingProvider:
    """Calls an already-installed embedding model through Ollama on loopback only.

    This adapter never installs or pulls models. The explicit model name is part
    of its identity so vectors from different models cannot be mixed.
    """
    MAX_BATCH = 32
    MAX_INPUT_BYTES = 8192
    MAX_VECTOR_DIMENSIONS = 16384
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024
    TIMEOUT_SECONDS = 60
    ENDPOINT = "http://127.0.0.1:11434/api/embed"

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, file_pointer, code, message, headers, new_url):
            return None

    def __init__(self, model: str):
        if (not isinstance(model, str) or not model.strip() or len(model) > 128
                or any(ord(char) < 32 for char in model)):
            raise ValueError("A bounded local Ollama embedding model name is required")
        self._model = model.strip()
        safe = hashlib.sha256(self._model.encode("utf-8")).hexdigest()[:12]
        self._identity = f"ollama-embedding-{safe}"

    @property
    def identity(self) -> str:
        return self._identity

    def embed_one(self, text: str):
        return self.embed_batch((text,))[0]

    def embed_batch(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not isinstance(texts, (tuple, list)) or not 1 <= len(texts) <= self.MAX_BATCH:
            raise ValueError("Embedding batch must contain 1 to 32 texts")
        if any(not isinstance(text, str) or not text.strip()
               or len(text.encode("utf-8")) > self.MAX_INPUT_BYTES for text in texts):
            raise ValueError("Embedding inputs must be nonempty and at most 8192 UTF-8 bytes")
        body = json.dumps({"model": self._model, "input": list(texts)},
                          ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.ENDPOINT, data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST")
        try:
            opener = urllib.request.build_opener(self._NoRedirect())
            with opener.open(request, timeout=self.TIMEOUT_SECONDS) as response:
                payload = response.read(self.MAX_RESPONSE_BYTES + 1)
            if len(payload) > self.MAX_RESPONSE_BYTES:
                raise RuntimeError("Local Ollama embedding response exceeded its size limit")
            decoded = json.loads(payload.decode("utf-8"))
            vectors = decoded.get("embeddings") if isinstance(decoded, dict) else None
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise ValueError("invalid response shape")
            normalized = []
            dimensions = None
            for vector in vectors:
                if not isinstance(vector, list) or not 1 <= len(vector) <= self.MAX_VECTOR_DIMENSIONS:
                    raise ValueError("invalid vector shape")
                if dimensions is None:
                    dimensions = len(vector)
                if len(vector) != dimensions:
                    raise ValueError("inconsistent vector dimensions")
                values = tuple(float(value) for value in vector)
                if any(not math.isfinite(value) for value in values):
                    raise ValueError("non-finite vector")
                normalized.append(values)
            return tuple(normalized)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("Local Ollama embedding request failed or timed out") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, OverflowError):
            raise RuntimeError("Local Ollama returned an invalid embedding response") from None
