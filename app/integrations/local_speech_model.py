"""Owner-confirmed, revision-pinned Faster-Whisper Tiny model files."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from threading import Lock
from urllib.parse import urlsplit
import urllib.request


MODEL_ID = "Systran/faster-whisper-tiny"
MODEL_REVISION = "d90ca5fe260221311c53c58e660288d3deb8d356"
MAX_MODEL_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class ModelFile:
    name: str
    size: int
    blob_sha1: str
    sha256_digest: str | None = None

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{self.name}"


TINY_FILES = (
    ModelFile("config.json", 2_249, "3baa18e2b321a2f489614607852a729fcd516480"),
    ModelFile("model.bin", 75_538_270, "ee1fa0720a33a1e4a7b698cf5e4aacfcb360b99a",
              "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1"),
    ModelFile("tokenizer.json", 2_203_239, "7818adb6de9fa3064d3ff81226fdd675be1f6344"),
    ModelFile("vocabulary.txt", 459_861, "c9074644d9d1205686f16d411564729461324b75"),
)


def git_blob_sha1(data: bytes) -> str:
    return sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


class LocalSpeechModelCatalog:
    """No model bytes are requested unless the explicit manifest is confirmed."""

    def __init__(self, root: str | Path, *, downloader=None):
        self._root = Path(root).expanduser().absolute()
        self._downloader = downloader or self._download
        self._lock = Lock()

    @property
    def model_root(self) -> Path:
        return self._root

    @staticmethod
    def _manifest_digest() -> str:
        value = {"model": MODEL_ID, "revision": MODEL_REVISION,
                 "files": [{"name": item.name, "size": item.size, "blob_sha1": item.blob_sha1,
                            "sha256": item.sha256_digest} for item in TINY_FILES]}
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _installed(self) -> bool:
        target = self._root / "faster-whisper-tiny"
        try:
            return (target.is_dir() and not target.is_symlink() and target.resolve(strict=True) == target
                    and all((target / item.name).is_file() and not (target / item.name).is_symlink()
                            and (target / item.name).stat().st_size == item.size for item in TINY_FILES))
        except OSError:
            return False

    def preview(self) -> dict:
        return {"model_id": MODEL_ID, "revision": MODEL_REVISION,
                "state": "installed" if self._installed() else "not-installed",
                "download_bytes": sum(item.size for item in TINY_FILES),
                "manifest_digest": self._manifest_digest(),
                "files": [{"name": item.name, "size": item.size,
                           "digest": item.sha256_digest or f"Git blob SHA-1 {item.blob_sha1}"}
                          for item in TINY_FILES],
                "source": "Hugging Face model repository at a fixed commit; every file is digest checked",
                "note": "Tiny is a 75 MB multilingual CPU model. Runtime speed and language quality are device-dependent."}

    def install(self, *, confirmed: bool, manifest_digest: str) -> dict:
        with self._lock:
            preview = self.preview()
            if self._installed():
                return {"state": "installed", "already_installed": True, "model_id": MODEL_ID}
            if confirmed is not True or manifest_digest != preview["manifest_digest"]:
                raise ValueError("Review the exact model revision, files, total size and digest, then explicitly confirm the download")
            if preview["download_bytes"] > MAX_MODEL_BYTES:
                raise RuntimeError("Selected local speech model exceeds its download size limit")
            self._root.mkdir(parents=True, exist_ok=True)
            if self._root.is_symlink() or self._root.resolve() != self._root:
                raise RuntimeError("Local speech model storage is not a safe directory")
            destination = self._root / "faster-whisper-tiny"
            if destination.exists() or destination.is_symlink():
                raise RuntimeError("Local model folder already exists but does not match the pinned manifest; inspect it before retrying")
            stage = Path(tempfile.mkdtemp(prefix=".faster-whisper-tiny-", dir=self._root))
            published = False
            try:
                for item in TINY_FILES:
                    data = self._downloader(item)
                    if not isinstance(data, bytes) or len(data) != item.size:
                        raise RuntimeError("Pinned speech model file failed its size check")
                    if item.sha256_digest:
                        valid = sha256(data).hexdigest() == item.sha256_digest
                    else:
                        valid = git_blob_sha1(data) == item.blob_sha1
                    if not valid:
                        raise RuntimeError("Pinned speech model file failed its digest check")
                    (stage / item.name).write_bytes(data)
                stage.rename(destination)
                published = True
                return {"state": "installed", "already_installed": False, "model_id": MODEL_ID}
            except Exception:
                if published and destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                raise
            finally:
                if stage.exists():
                    shutil.rmtree(stage, ignore_errors=True)

    @staticmethod
    def _download(item: ModelFile) -> bytes:
        request = urllib.request.Request(item.url, headers={"Accept": "application/octet-stream"})
        opener = urllib.request.build_opener(_SafeModelRedirects(), urllib.request.HTTPSHandler())
        try:
            with opener.open(request, timeout=30) as response:
                if response.geturl() != item.url and _host(response.geturl()) not in _MODEL_HOSTS:
                    raise RuntimeError
                data = response.read(item.size + 1)
        except Exception:
            raise RuntimeError("Pinned local speech model file could not be downloaded from the approved model source") from None
        if len(data) > item.size:
            raise RuntimeError("Local speech model file exceeded its reviewed size")
        return data


_MODEL_HOSTS = frozenset({"huggingface.co", "hf.co", "cdn-lfs.huggingface.co",
                         "cdn-lfs.hf.co", "us.aws.cdn.hf.co", "cas-bridge.xethub.hf.co",
                         "cas-server.xethub.hf.co"})


def _host(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return ""
    return (parsed.hostname or "").casefold()


class _SafeModelRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        if _host(new_url) not in _MODEL_HOSTS:
            return None
        return super().redirect_request(request, response, code, message, headers, new_url)
