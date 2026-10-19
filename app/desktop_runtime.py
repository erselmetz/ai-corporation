"""Packaged Electron sidecar for the Windows local application."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import time

from app.desktop_lock import CurrentUserLease
from app.local import create_local_app
from app.local_owner_credential import LocalOwnerCredentialStore, OwnerCredentialError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_STARTUP_REQUEST = 8192


class DesktopStartupError(RuntimeError):
    """Safe, bounded desktop startup failure."""


def _read_message(stream, limit: int = MAX_STARTUP_REQUEST) -> dict:
    line = stream.readline(limit + 1)
    if not line or len(line) > limit or not line.endswith(b"\n"):
        raise DesktopStartupError("A bounded owner setup request is required")
    try:
        payload = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        raise DesktopStartupError("Owner setup request is invalid") from None
    if not isinstance(payload, dict):
        raise DesktopStartupError("Owner setup request is invalid")
    return payload


def _prepare_owner(payload: dict, credential_store=None) -> str | None:
    store = credential_store or LocalOwnerCredentialStore()
    password = payload.get("password")
    confirmation = payload.get("confirmation")
    if password in (None, "") and not store.exists():
        token = payload.get("session_token")
        if not isinstance(token, str) or not 43 <= len(token) <= 128 or not token.isascii():
            raise DesktopStartupError("Desktop session token is invalid")
        return None
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise DesktopStartupError("Owner password must contain 12 to 1024 characters")
    try:
        if store.exists():
            if confirmation not in (None, ""):
                raise DesktopStartupError("Password confirmation is accepted only during first-run setup")
            if not store.verify(password):
                raise DesktopStartupError("Owner password did not match")
        else:
            if not isinstance(confirmation, str):
                raise DesktopStartupError("Confirm the owner password during first-run setup")
            store.create(password, confirmation)
    except OwnerCredentialError as error:
        raise DesktopStartupError(str(error)) from None
    return password


def _reserve_loopback(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((DEFAULT_HOST, port))
        listener.listen(128)
        listener.setblocking(False)
        return listener
    except OSError:
        listener.close()
        raise DesktopStartupError("The configured loopback port is unavailable") from None


def run_backend(*, port: int, ui_dir: Path, stdin=None, credential_store=None,
                lease_factory=None, server_factory=None) -> None:
    """Verify DPAPI owner setup, acquire exclusive ownership and serve loopback."""
    stream = stdin or sys.stdin.buffer
    raw = stream.readline(MAX_STARTUP_REQUEST + 1)
    if not raw or len(raw) > MAX_STARTUP_REQUEST or not raw.endswith(b"\n"):
        raise DesktopStartupError("A bounded owner setup request is required")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) - {"password", "confirmation", "first_owner_run", "session_token"}:
            raise ValueError
        if "first_owner_run" in payload and type(payload["first_owner_run"]) is not bool:
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        raise DesktopStartupError("Owner setup request is invalid") from None
    del raw
    startup_token = payload.get("session_token")
    if startup_token is not None and (not isinstance(startup_token, str) or not 43 <= len(startup_token) <= 128 or not startup_token.isascii()):
        raise DesktopStartupError("Desktop session token is invalid")
    password = _prepare_owner(payload, credential_store)
    first_owner_run = payload.get("first_owner_run", False)
    payload.clear()
    ownership = lease_factory() if lease_factory else CurrentUserLease(error_type=DesktopStartupError)
    listener = None
    server = None
    stop_event = threading.Event()
    try:
        ownership.acquire()
        listener = _reserve_loopback(port)
        bound_port = listener.getsockname()[1]
        origin = f"http://{DEFAULT_HOST}:{bound_port}"
        application = create_local_app(password=password, origin=origin, desktop_ui_dir=ui_dir,
                                       desktop_mode=True, first_owner_run=first_owner_run,
                                       desktop_session_token=startup_token)
        del password
        for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
            logger = logging.getLogger(logger_name)
            logger.handlers[:] = [logging.NullHandler()]
            logger.propagate = False
        if server_factory is None:
            import uvicorn
            config = uvicorn.Config(application, host=DEFAULT_HOST, port=bound_port, workers=1,
                                    log_config=None, log_level="warning", access_log=False,
                                    proxy_headers=False, lifespan="on")
            server = uvicorn.Server(config)
        else:
            server = server_factory(application, bound_port)

        def watch_parent_pipe():
            try:
                while not stop_event.is_set():
                    command = _read_message(stream)
                    if command == {"command": "shutdown"}:
                        server.should_exit = True
                        return
            except (DesktopStartupError, OSError, ValueError):
                # An Electron parent disappearing also ends its owned service.
                server.should_exit = True

        control = threading.Thread(target=watch_parent_pipe, name="desktop-parent-control", daemon=True)
        control.start()
        server_thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]},
                                        name="desktop-http-server", daemon=False)
        server_thread.start()
        deadline = time.monotonic() + 15
        while not getattr(server, "started", False) and server_thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not getattr(server, "started", False):
            server.should_exit = True
            server_thread.join(timeout=10)
            raise DesktopStartupError("The local service did not become ready")
        sys.stdout.write(f"ERSELMETZ_READY:{bound_port}\n")
        sys.stdout.flush()
        server_thread.join()
    finally:
        stop_event.set()
        if server is not None and getattr(server, "started", False):
            server.should_exit = True
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        try:
            ownership.release()
        except Exception:
            pass


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("The packaged desktop runtime supports Windows only")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--ui-dir", required=True)
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        raise SystemExit("Invalid local application port")
    ui_dir = Path(options.ui_dir)
    try:
        run_backend(port=options.port, ui_dir=ui_dir)
    except (DesktopStartupError, OwnerCredentialError, OSError, ValueError):
        # The parent app deliberately receives no raw diagnostics, user paths or secrets.
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
