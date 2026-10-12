"""Shared current-user exclusive lease for the local desktop backend."""

from __future__ import annotations

import os
from pathlib import Path


class DesktopLeaseError(RuntimeError):
    """Raised when this process cannot establish exclusive launcher ownership."""


class CurrentUserLease:
    """Hold a nonblocking Windows current-user file lock until release."""

    def __init__(self, path: Path | None = None, *, error_type=DesktopLeaseError):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if path is None and not local_app_data:
            raise error_type("The current-user application data folder is unavailable")
        self.path = path or Path(local_app_data) / "ERSELMETZ AI" / "launcher.lock"
        self._file = None
        self._locking = None
        self._error_type = error_type

    def acquire(self):
        import msvcrt

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+b")
            if self.path.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
        except Exception:
            try:
                handle.close()
            except (UnboundLocalError, OSError):
                pass
            raise self._error_type("Exclusive launcher ownership could not be established") from None
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            raise self._error_type("Another managed launcher already owns the local backend") from None
        except Exception:
            handle.close()
            raise self._error_type("Exclusive launcher ownership could not be established") from None
        self._file = handle
        self._locking = msvcrt

    def release(self):
        if self._file is None:
            return
        handle, self._file = self._file, None
        try:
            handle.seek(0)
            self._locking.locking(handle.fileno(), self._locking.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            try:
                handle.close()
            except OSError:
                pass
            finally:
                self._locking = None
