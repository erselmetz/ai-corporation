"""Current-Windows-user protected local owner credential verifier."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import threading

_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class OwnerCredentialError(RuntimeError):
    """A safe-to-display local owner credential setup/verification failure."""


class LocalOwnerCredentialStore:
    """Persist only a DPAPI-protected password verifier, never the password."""

    ITERATIONS = 600_000
    MAX_FILE_BYTES = 8192

    def __init__(self, path: Path | None = None, *, protect=None, unprotect=None):
        self.path = path or self._default_path()
        self._protect = protect or _dpapi_protect
        self._unprotect = unprotect or _dpapi_unprotect
        self._lock = threading.RLock()

    @staticmethod
    def _default_path() -> Path:
        if sys.platform != "win32":
            raise OwnerCredentialError("The desktop launcher is supported on Windows only")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise OwnerCredentialError("The current-user application data folder is unavailable")
        return Path(local_app_data) / "ERSELMETZ AI" / "owner-credential.dpapi"

    def exists(self) -> bool:
        return self.path.exists()

    def create(self, password: str, confirmation: str) -> None:
        _validate_password(password)
        if not isinstance(confirmation, str) or not hmac.compare_digest(
                password.encode("utf-8"), confirmation.encode("utf-8")):
            raise OwnerCredentialError("The password entries do not match")
        with self._lock:
            if self.path.exists():
                raise OwnerCredentialError("An owner credential already exists")
            salt = secrets.token_bytes(32)
            verifier = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, self.ITERATIONS
            )
            payload = json.dumps({
                "version": 1,
                "salt": base64.b64encode(salt).decode("ascii"),
                "verifier": base64.b64encode(verifier).decode("ascii"),
                "iterations": self.ITERATIONS,
            }, separators=(",", ":")).encode("utf-8")
            try:
                encrypted = self._protect(payload)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation prevents one launcher from silently
                # replacing another launcher's already-created owner record.
                with self.path.open("xb") as credential_file:
                    credential_file.write(encrypted)
                    credential_file.flush()
                    os.fsync(credential_file.fileno())
            except FileExistsError:
                raise OwnerCredentialError("An owner credential already exists") from None
            except OwnerCredentialError:
                raise
            except Exception:
                raise OwnerCredentialError("The owner credential could not be protected and saved") from None

    def verify(self, password: str) -> bool:
        _validate_password(password)
        with self._lock:
            try:
                size = self.path.stat().st_size
                if not 1 <= size <= self.MAX_FILE_BYTES:
                    raise ValueError("invalid credential file size")
                encrypted = self.path.read_bytes()
                payload = self._unprotect(encrypted)
                record = json.loads(payload.decode("utf-8"))
                if (record.get("version") != 1
                        or record.get("iterations") != self.ITERATIONS):
                    raise ValueError("unsupported credential record")
                salt = base64.b64decode(record["salt"], validate=True)
                expected = base64.b64decode(record["verifier"], validate=True)
                if len(salt) != 32 or len(expected) != 32:
                    raise ValueError("invalid credential record")
                actual = hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"), salt, self.ITERATIONS
                )
                return hmac.compare_digest(actual, expected)
            except FileNotFoundError:
                raise OwnerCredentialError("Owner setup has not been completed") from None
            except OwnerCredentialError:
                raise
            except Exception:
                raise OwnerCredentialError("The saved owner credential is unavailable or unreadable") from None


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise OwnerCredentialError("Owner password must contain 12 to 1024 characters")


def _dpapi_protect(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise OwnerCredentialError("Windows user credential protection is unavailable")
    import win32crypt

    return win32crypt.CryptProtectData(
        data, "ERSELMETZ AI owner verifier", None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN,
    )


def _dpapi_unprotect(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise OwnerCredentialError("Windows user credential protection is unavailable")
    import win32crypt

    return win32crypt.CryptUnprotectData(
        data, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN
    )[1]
