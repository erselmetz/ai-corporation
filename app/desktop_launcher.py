"""Small Windows GUI controller for the existing loopback Python/Web UI."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import socket
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

from app.local import create_local_app
from app.local_owner_credential import LocalOwnerCredentialStore, OwnerCredentialError
from app.desktop_lock import CurrentUserLease

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
START_TIMEOUT_SECONDS = 15.0
STOP_TIMEOUT_SECONDS = 10.0


class LifecycleError(RuntimeError):
    """A safe-to-display local application lifecycle failure."""


class _NullLease:
    def acquire(self):
        return None

    def release(self):
        return None


class _SingleInstanceLease(CurrentUserLease):
    """Task 126 compatibility adapter for the shared desktop lease."""

    def __init__(self, path=None):
        super().__init__(path, error_type=LifecycleError)


class LocalApplicationController:
    """Own one in-process Uvicorn server and its pre-bound loopback socket."""

    def __init__(self, *, host=DEFAULT_HOST, port=DEFAULT_PORT, app_factory=None,
                 server_factory=None, clock=time.monotonic, sleep=time.sleep,
                 health_probe=None, lease_factory=None):
        if host != DEFAULT_HOST:
            raise ValueError("The local application may bind only to 127.0.0.1")
        if not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("Invalid local application port")
        self.host = host
        self.port = port
        self._app_factory = app_factory or (
            lambda password, origin: create_local_app(password=password, origin=origin)
        )
        self._server_factory = server_factory
        self._clock = clock
        self._sleep = sleep
        self._health_probe = health_probe or _probe_health
        if lease_factory is None:
            import sys
            lease_factory = _SingleInstanceLease if sys.platform == "win32" else _NullLease
        self._lease_factory = lease_factory
        self._lock = threading.RLock()
        self._server = None
        self._thread = None
        self._bound_socket = None
        self._state = "stopped"
        self._failure = None
        self._events = deque(maxlen=100)
        self._origin = None
        self._lease = None

    @property
    def state(self):
        with self._lock:
            if self._thread is not None and not self._thread.is_alive() and self._state in {"starting", "running", "stopping"}:
                self._state = "failed" if self._failure else "stopped"
            return self._state

    @property
    def origin(self):
        return self._origin

    @property
    def is_active(self):
        return self._thread is not None and self._thread.is_alive()

    def events(self):
        with self._lock:
            return tuple(self._events)

    def start(self, password: str) -> str:
        if not isinstance(password, str) or not 12 <= len(password) <= 1024:
            raise LifecycleError("Owner password must contain 12 to 1024 characters")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise LifecycleError("The managed local application is already running")
            try:
                lease = self._lease_factory()
                lease.acquire()
            except LifecycleError:
                raise
            except Exception:
                self._record("Exclusive launcher ownership could not be established; details withheld.")
                raise LifecycleError("Exclusive launcher ownership could not be established") from None
            self._lease = lease
            try:
                listener = self._reserve_loopback()
            except Exception:
                lease.release()
                self._lease = None
                raise
            port = listener.getsockname()[1]
            origin = f"http://{self.host}:{port}"
            try:
                application = self._app_factory(password, origin)
                server = self._make_server(application, port)
            except Exception:
                listener.close()
                lease.release()
                self._lease = None
                self._record("Startup failed during application initialization; details withheld.")
                raise LifecycleError("The local application could not be initialized") from None
            self.port = port
            self._origin = origin
            self._bound_socket = listener
            self._server = server
            self._failure = None
            self._state = "starting"
            thread = threading.Thread(
                target=self._serve, args=(server, listener),
                name="erselmetz-local-backend", daemon=True,
            )
            self._thread = thread
            self._record("Starting the loopback backend.")
            try:
                thread.start()
            except Exception:
                listener.close()
                lease.release()
                self._lease = None
                self._thread = None
                self._server = None
                self._bound_socket = None
                self._state = "failed"
                self._record("Backend startup failed; details withheld.")
                raise LifecycleError("The local application could not start its backend") from None

        deadline = self._clock() + START_TIMEOUT_SECONDS
        while self._clock() < deadline:
            with self._lock:
                if self._failure is not None or not thread.is_alive():
                    self._state = "failed"
                    self._record("Backend startup failed; details withheld.")
                    raise LifecycleError("The local application failed to start; see the redacted event log")
                started = bool(getattr(server, "started", False))
            if started:
                try:
                    healthy = bool(self._health_probe(origin))
                except Exception:
                    healthy = False
                if healthy:
                    with self._lock:
                        self._state = "running"
                        self._record("Backend health check passed on loopback.")
                    return origin
            self._sleep(0.05)

        with self._lock:
            server.should_exit = True
            self._state = "failed"
            self._record("Backend startup timed out; shutdown was requested.")
        thread.join(timeout=STOP_TIMEOUT_SECONDS)
        raise LifecycleError("The local application did not become healthy before the startup timeout")

    def health(self) -> bool:
        if self.state != "running" or not self._origin:
            return False
        try:
            healthy = bool(self._health_probe(self._origin))
        except Exception:
            healthy = False
        with self._lock:
            if healthy:
                self._record("Backend health check passed on loopback.")
            else:
                self._record("Backend health check failed; response details withheld.")
        return healthy

    def stop(self) -> None:
        with self._lock:
            thread, server = self._thread, self._server
            if thread is None or not thread.is_alive():
                self._state = "stopped"
                return
            self._state = "stopping"
            server.should_exit = True
            self._record("Graceful backend shutdown requested.")
        thread.join(timeout=STOP_TIMEOUT_SECONDS)
        with self._lock:
            if thread.is_alive():
                self._state = "stopping"
                self._record("Backend has not stopped yet; no force termination was attempted.")
                raise LifecycleError("The backend is still shutting down; wait before restarting")
            self._state = "stopped"
            self._server = None
            self._thread = None
            self._bound_socket = None
            self._origin = None
            if self._lease is not None:
                self._lease.release()
                self._lease = None
            self._record("Backend stopped cleanly.")

    def restart(self, password: str) -> str:
        if self.is_active:
            self.stop()
        return self.start(password)

    def _reserve_loopback(self):
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError:
            self._state = "failed"
            self._record("Startup failed while preparing the loopback socket.")
            raise LifecycleError("A local loopback socket could not be created") from None
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((self.host, self.port))
            listener.listen(128)
            listener.setblocking(False)
            return listener
        except OSError:
            listener.close()
            self._state = "failed"
            self._record("Startup blocked because the configured loopback port is unavailable.")
            raise LifecycleError(
                f"Loopback port {self.port} is unavailable; close the other application before starting"
            ) from None

    def _make_server(self, application, port):
        if self._server_factory is not None:
            return self._server_factory(application, port)
        import uvicorn

        config = uvicorn.Config(
            application, host=self.host, port=port, workers=1,
            log_config=None, log_level="warning", access_log=False,
            proxy_headers=False, lifespan="on",
        )
        return uvicorn.Server(config)

    def _serve(self, server, listener):
        try:
            server.run(sockets=[listener])
        except BaseException:
            with self._lock:
                self._failure = "backend_failed"
                self._state = "failed"
                self._record("Backend exited unexpectedly; exception details withheld.")
        finally:
            try:
                listener.close()
            except OSError:
                pass
            with self._lock:
                if self._lease is not None:
                    self._lease.release()
                    self._lease = None

    def _record(self, message):
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._events.append(f"{timestamp} {message}")


def _probe_health(origin: str) -> bool:
    with urlopen(f"{origin}/health", timeout=2.0) as response:
        if response.status != 200:
            return False
        try:
            return json.loads(response.read(256)).get("status") == "ok"
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return False


def main():
    """Compatibility entry point; the optional API controller is not auto-started."""
    from app.qt_desktop.__main__ import main as native_main
    return native_main()


if __name__ == '__main__':raise SystemExit(main())
