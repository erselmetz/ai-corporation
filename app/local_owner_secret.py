"""Optional per-Windows-user DPAPI storage for one local provider credential."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import threading

from app.local_owner_credential import _dpapi_protect, _dpapi_unprotect


class LocalOwnerSecretError(RuntimeError):
    """A bounded error for an explicitly opted-in owner secret."""


class LocalOwnerSecretStore:
    MAX_FILE_BYTES = 8192
    MAX_SECRET_BYTES = 4096

    def __init__(self, path: Path | None = None, *, protect=None, unprotect=None):
        self.path = path or self._default_path()
        self._protect = protect or _dpapi_protect
        self._unprotect = unprotect or _dpapi_unprotect
        self._lock = threading.RLock()

    @staticmethod
    def _default_path() -> Path:
        if sys.platform != "win32":
            raise LocalOwnerSecretError("Windows user credential protection is unavailable")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise LocalOwnerSecretError("The current-user application data folder is unavailable")
        return Path(local_app_data) / "ERSELMETZ AI" / "gemini-credential.dpapi"

    def save(self, secret: str) -> None:
        if not isinstance(secret, str) or not secret.strip():
            raise LocalOwnerSecretError("A provider credential is required")
        payload = secret.encode("utf-8")
        if len(payload) > self.MAX_SECRET_BYTES:
            raise LocalOwnerSecretError("Provider credential exceeds the supported size")
        with self._lock:
            temporary = self.path.with_name(self.path.name + ".new")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                protected = self._protect(payload)
                with temporary.open("wb") as handle:
                    handle.write(protected)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            except Exception:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise LocalOwnerSecretError(
                    "The provider credential could not be protected for this Windows user"
                ) from None
            finally:
                payload = b"\0" * len(payload)

    def load(self) -> str | None:
        with self._lock:
            try:
                size = self.path.stat().st_size
            except FileNotFoundError:
                return None
            try:
                if not 1 <= size <= self.MAX_FILE_BYTES:
                    raise ValueError
                protected = self.path.read_bytes()
                secret = self._unprotect(protected)
                if not 1 <= len(secret) <= self.MAX_SECRET_BYTES:
                    raise ValueError
                return secret.decode("utf-8")
            except Exception:
                raise LocalOwnerSecretError(
                    "The saved provider credential is unavailable or unreadable"
                ) from None

    def clear(self) -> None:
        with self._lock:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                raise LocalOwnerSecretError("The saved provider credential could not be removed") from None
