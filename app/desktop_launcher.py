"""Small Windows GUI controller for the existing loopback Python/Web UI."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
import socket
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

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
        return response.status == 200 and response.read(256) == b'{"status":"ok"}'


class DesktopLauncherWindow:
    """Tkinter owner setup and lifecycle UI; no raw server logs are displayed."""

    def __init__(self, root, credential_store=None, controller=None):
        import tkinter as tk
        self.tk = tk
        self.root = root
        self.credentials = credential_store or LocalOwnerCredentialStore()
        self.controller = controller or LocalApplicationController()
        self.password = tk.StringVar()
        self.confirmation = tk.StringVar()
        self.status = tk.StringVar(value="Set up owner access to start the local app." if not self.credentials.exists() else "Enter the owner password to start.")
        root.title("ERSELMETZ AI — Local Application")
        root.geometry("620x500")
        root.minsize(560, 420)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self._refresh_events()

    def _build(self):
        tk = self.tk
        frame = tk.Frame(self.root, padx=20, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="ERSELMETZ AI", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(frame, text="Local application control", font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 10))
        tk.Label(frame, textvariable=self.status, wraplength=560, justify="left").pack(anchor="w", pady=6)

        is_setup = not self.credentials.exists()
        tk.Label(frame, text="Create an owner password (12–1024 characters)" if is_setup else "Owner password").pack(anchor="w")
        self.password_entry = tk.Entry(frame, textvariable=self.password, show="•", width=60)
        self.password_entry.pack(fill="x", pady=(2, 8))
        self.confirm_entry = None
        if is_setup:
            tk.Label(frame, text="Confirm owner password").pack(anchor="w")
            self.confirm_entry = tk.Entry(frame, textvariable=self.confirmation, show="•", width=60)
            self.confirm_entry.pack(fill="x", pady=(2, 8))
        self.start_button = tk.Button(frame, text="Save owner setup and start" if is_setup else "Start local app", command=self.start)
        self.start_button.pack(anchor="w", pady=6)

        controls = tk.Frame(frame)
        controls.pack(anchor="w", pady=6)
        self.open_button = tk.Button(controls, text="Open local UI", command=self.open_ui, state="disabled")
        self.open_button.pack(side="left", padx=(0, 6))
        self.health_button = tk.Button(controls, text="Check health", command=self.check_health, state="disabled")
        self.health_button.pack(side="left", padx=6)
        self.restart_button = tk.Button(controls, text="Restart", command=self.restart, state="disabled")
        self.restart_button.pack(side="left", padx=6)
        self.stop_button = tk.Button(controls, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)

        tk.Label(frame, text="Redacted lifecycle events").pack(anchor="w", pady=(10, 2))
        self.events_box = tk.Text(frame, height=10, wrap="word", state="disabled", font=("Consolas", 9))
        self.events_box.pack(fill="both", expand=True)

    def start(self):
        password = self.password.get()
        try:
            if self.credentials.exists():
                if not self.credentials.verify(password):
                    self.status.set("Owner password did not match; no service was started.")
                    self.password.set("")
                    return
            else:
                self.credentials.create(password, self.confirmation.get())
            origin = self.controller.start(password)
            self.status.set(f"Running and healthy at {origin}. Owner sign-in is still required in the browser.")
            self.open_button.configure(state="normal")
            self.health_button.configure(state="normal")
            self.restart_button.configure(state="normal")
            self.stop_button.configure(state="normal")
            self.open_ui()
        except (OwnerCredentialError, LifecycleError) as error:
            self.status.set(str(error))
        finally:
            self.password.set("")
            self.confirmation.set("")
            self._refresh_events()

    def open_ui(self):
        if self.controller.state != "running" or not self.controller.origin:
            self.status.set("The local application is not running.")
            return
        webbrowser.open(f"{self.controller.origin}/ui/login", new=2)

    def check_health(self):
        self.status.set("Backend health check passed." if self.controller.health()
                        else "Backend is unavailable or not healthy; response details are withheld.")
        self._refresh_events()

    def restart(self):
        password = self.password.get()
        try:
            if not self.credentials.verify(password):
                self.status.set("Owner password did not match; the running app was left unchanged.")
                return
            origin = self.controller.restart(password)
            self.status.set(f"Restarted and healthy at {origin}. Browser sign-in is required again.")
            self.open_button.configure(state="normal")
            self.open_ui()
        except (OwnerCredentialError, LifecycleError) as error:
            self.status.set(str(error))
        finally:
            self.password.set("")
            self._refresh_events()

    def stop(self):
        try:
            self.controller.stop()
            self.status.set("Local application stopped.")
            for button in (self.open_button, self.health_button, self.restart_button, self.stop_button):
                button.configure(state="disabled")
        except LifecycleError as error:
            self.status.set(str(error))
        self._refresh_events()

    def _refresh_events(self):
        events = self.controller.events()
        self.events_box.configure(state="normal")
        self.events_box.delete("1.0", "end")
        self.events_box.insert("end", "\n".join(events))
        self.events_box.configure(state="disabled")
        if self.root.winfo_exists():
            self.root.after(1000, self._refresh_events)

    def close(self):
        try:
            if self.controller.is_active:
                self.controller.stop()
        except LifecycleError as error:
            self.status.set(f"{error}. Keep this window open until shutdown completes.")
            self._refresh_events()
            return
        self.root.destroy()


def main():
    if not __import__("sys").platform == "win32":
        raise RuntimeError("The local desktop launcher is supported on Windows only")
    import tkinter as tk

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(logger_name)
        logger.handlers[:] = [logging.NullHandler()]
        logger.propagate = False
    root = tk.Tk()
    DesktopLauncherWindow(root)
    root.mainloop()
