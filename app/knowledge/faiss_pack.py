"""Explicit, hash-pinned, wheel-only installer for the optional FAISS Brain pack."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import sys
import tempfile
from urllib.parse import urlsplit
import urllib.request
from threading import Lock
from zipfile import ZipFile


@dataclass(frozen=True)
class WheelSpec:
    filename: str
    url: str
    size: int
    sha256: str


FAISS_WHEELS = (
    WheelSpec("faiss_cpu-1.15.1-cp314-cp314-win_amd64.whl",
              "https://files.pythonhosted.org/packages/98/82/4b1866e93b85247774dbd67afc95fbe5d02097ee125cf4ed11c90515717b/faiss_cpu-1.15.1-cp314-cp314-win_amd64.whl",
              16_574_394, "c18b569ec5d5e79f2156f0059fdb3ea79976f365d79291252ab6b45d40523c2c"),
    WheelSpec("numpy-2.5.4-cp314-cp314-win_amd64.whl",
              "https://files.pythonhosted.org/packages/52/9a/e1e512ebc948d5b9dd33b08736760f0ebbed2848fd4eda1f553088a6dcee/numpy-2.5.4-cp314-cp314-win_amd64.whl",
              12_703_552, "2ca144f15135b6212a5c47b1e2aeca6e412f102f95a2d5d88d8aec77eb255de3"),
    WheelSpec("packaging-26.3-py3-none-any.whl",
              "https://files.pythonhosted.org/packages/63/34/ba1c580383c9eada3711951fef0795c80b829a078d72188184bcab9dd527/packaging-26.3-py3-none-any.whl",
              129_956, "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"),
)
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
MAX_UNPACKED_BYTES = 400 * 1024 * 1024
MAX_WHEEL_FILES = 12_000


def application_data_root():
    local_app_data = os.environ.get("LOCALAPPDATA")
    return (Path(local_app_data) / "ERSELMETZ AI" if local_app_data else
            Path.home() / ".local" / "share" / "ERSELMETZ AI")


class OptionalFaissPack:
    def __init__(self, data_root: str | Path, *, downloader=None, activator=None,
                 wheels=FAISS_WHEELS, runtime_supported=None):
        self._root = Path(data_root).expanduser().resolve() / "capability-packs" / "faiss-cpu"
        self._downloader = downloader or self._download
        self._activator = activator or activate_faiss_pack
        self._wheels = tuple(wheels)
        self._runtime_supported = runtime_supported or self._supports_this_runtime
        self._install_lock = Lock()

    @staticmethod
    def _supports_this_runtime():
        return (sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 14)
                and sys.platform == "win32" and platform.machine().casefold() in {"amd64", "x86_64"})

    def _manifest_digest(self):
        payload = [{"filename": item.filename, "url": item.url, "size": item.size,
                    "sha256": item.sha256} for item in self._wheels]
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def preview(self):
        supported = bool(self._runtime_supported())
        return {
            "pack_id": "faiss-cpu",
            "state": "installed" if self._installed() else "not-installed",
            "supported": supported,
            "version": "1.15.1",
            "files": [item.filename for item in self._wheels],
            "download_bytes": sum(item.size for item in self._wheels),
            "manifest_digest": self._manifest_digest(),
            "source": "Official PyPI files; fixed wheel versions and SHA-256 digests",
            "install_action": "Owner confirmation required; wheels install into an app-local isolated pack directory.",
        }

    def _installed(self):
        site = self._root / "site-packages"
        if (not site.is_dir() or self._root.is_symlink() or self._root.parent.is_symlink()
                or site.is_symlink()):
            return False
        try:
            return self._root.resolve(strict=True) == self._root and site.resolve(strict=True) == site
        except OSError:
            return False

    @property
    def site_packages(self):
        return self._root / "site-packages"

    def install(self, *, confirmed: bool, manifest_digest: str):
        with self._install_lock:
            return self._install(confirmed=confirmed, manifest_digest=manifest_digest)

    def _install(self, *, confirmed: bool, manifest_digest: str):
        preview = self.preview()
        if not preview["supported"]:
            raise RuntimeError("The pinned FAISS wheels do not support this Python runtime and Windows architecture")
        if self._installed():
            return {"state": "installed", "already_installed": True, "pack_id": "faiss-cpu"}
        if confirmed is not True or manifest_digest != preview["manifest_digest"]:
            raise ValueError("Review the current wheel versions, size, and digest, then explicitly confirm installation")
        if sum(item.size for item in self._wheels) > MAX_DOWNLOAD_BYTES:
            raise RuntimeError("The selected optional pack exceeds its download limit")
        parent = self._root.parent
        parent.mkdir(parents=True, exist_ok=True)
        if parent.is_symlink():
            raise RuntimeError("Optional pack storage is not a safe local directory")
        stage = Path(tempfile.mkdtemp(prefix=".faiss-stage-", dir=parent))
        try:
            site = stage / "site-packages"
            site.mkdir()
            for spec in self._wheels:
                data = self._downloader(spec)
                if not isinstance(data, bytes) or len(data) != spec.size or sha256(data).hexdigest() != spec.sha256:
                    raise RuntimeError("A pinned optional wheel failed its size or SHA-256 check")
                self._extract_wheel(data, spec, site)
            if self._root.exists() or self._root.is_symlink():
                raise RuntimeError("Optional pack storage already exists; inspect it before retrying")
            stage.rename(self._root)
            try:
                self._activator(self._root / "site-packages")
            except Exception:
                shutil.rmtree(self._root, ignore_errors=True)
                raise RuntimeError("FAISS files were verified but could not be loaded by this app runtime") from None
            return {"state": "installed", "already_installed": False, "pack_id": "faiss-cpu"}
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)

    @staticmethod
    def _extract_wheel(data: bytes, spec: WheelSpec, destination: Path):
        try:
            OptionalFaissPack._extract_wheel_contents(data, spec, destination)
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("A pinned wheel archive is invalid") from None

    @staticmethod
    def _extract_wheel_contents(data: bytes, spec: WheelSpec, destination: Path):
        total = 0
        count = 0
        with ZipFile(BytesIO(data)) as archive:
            for item in archive.infolist():
                count += 1
                if count > MAX_WHEEL_FILES:
                    raise RuntimeError("A pinned wheel contains too many files")
                if item.is_dir():
                    continue
                original = PurePosixPath(item.filename)
                if (original.is_absolute() or ".." in original.parts or "\\" in item.filename
                        or not original.parts):
                    raise RuntimeError("A wheel entry has an unsafe path")
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise RuntimeError("A wheel contains an unsupported symbolic link")
                parts = original.parts
                if len(parts) >= 3 and parts[0].endswith(".data"):
                    if parts[1] not in {"purelib", "platlib"}:
                        raise RuntimeError("A wheel contains an unsupported install destination")
                    parts = parts[2:]
                relative = Path(*parts)
                target = destination / relative
                resolved = target.resolve()
                if destination.resolve() not in resolved.parents:
                    raise RuntimeError("A wheel entry escapes its isolated install directory")
                if item.file_size < 0 or item.file_size > MAX_UNPACKED_BYTES or total + item.file_size > MAX_UNPACKED_BYTES:
                    raise RuntimeError("A wheel expands beyond the optional pack size limit")
                payload = archive.read(item)
                if len(payload) != item.file_size:
                    raise RuntimeError("A pinned wheel entry did not match its declared size")
                total += len(payload)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)

    @staticmethod
    def _download(spec: WheelSpec):
        parsed = urlsplit(spec.url)
        if parsed.scheme != "https" or parsed.hostname != "files.pythonhosted.org" or parsed.username or parsed.password:
            raise RuntimeError("The pinned package source is not allowed")
        request = urllib.request.Request(spec.url, headers={"Accept": "application/octet-stream"})
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
            _NoRedirect(),
        )
        try:
            with opener.open(request, timeout=30) as response:
                if response.geturl() != spec.url:
                    raise RuntimeError("Package source redirected; installation was stopped")
                payload = response.read(spec.size + 1)
        except Exception:
            raise RuntimeError("A pinned package wheel could not be downloaded from the approved source") from None
        if len(payload) > spec.size:
            raise RuntimeError("A pinned package wheel exceeded its declared size")
        return payload


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


_DLL_HANDLES = []


def activate_faiss_pack(site_packages: str | Path):
    import importlib
    import os
    path = Path(site_packages).resolve(strict=True)
    if not path.is_dir() or path.name != "site-packages":
        raise RuntimeError("FAISS pack location is invalid")
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for directory in path.iterdir():
            if directory.is_dir() and directory.name.endswith(".libs"):
                _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    numpy = importlib.import_module("numpy")
    faiss = importlib.import_module("faiss")
    if not hasattr(numpy, "asarray") or not hasattr(faiss, "IndexFlatIP"):
        raise RuntimeError("The installed FAISS pack lacks required local APIs")
