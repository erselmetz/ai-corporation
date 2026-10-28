import socket
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import sys

from fastapi import FastAPI
import pytest

from app.desktop_launcher import LifecycleError, LocalApplicationController, _SingleInstanceLease
from app.local import create_local_app


PASSWORD = "test-only-owner-passphrase"


def test_controller_starts_health_checks_restarts_and_stops_owned_loopback_app():
    applications = []

    def make_app(password, origin):
        assert password == PASSWORD
        assert origin.startswith("http://127.0.0.1:")
        application = FastAPI()
        @application.get("/health")
        def health():
            return {"status": "ok"}
        applications.append(application)
        return application

    controller = LocalApplicationController(port=0, app_factory=make_app)
    first_origin = controller.start(PASSWORD)
    assert controller.state == "running"
    assert controller.health() is True
    assert first_origin == controller.origin
    controller.stop()
    assert controller.state == "stopped"
    second_origin = controller.start(PASSWORD)
    assert controller.state == "running"
    assert second_origin.startswith("http://127.0.0.1:")
    assert len(applications) == 2
    controller.stop()
    assert "Backend stopped cleanly." in " ".join(controller.events())


def test_loopback_port_conflict_does_not_take_over_the_existing_listener():
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    port = occupied.getsockname()[1]
    controller = LocalApplicationController(port=port)
    try:
        with pytest.raises(LifecycleError, match="Loopback port"):
            controller.start(PASSWORD)
        assert controller.state == "failed"
        assert "port is unavailable" in " ".join(controller.events())
        # The launcher never signals, kills, or adopts the unrelated listener.
        assert occupied.getsockname()[1] == port
    finally:
        occupied.close()


def test_controller_rejects_non_loopback_bind_addresses():
    with pytest.raises(ValueError, match="127.0.0.1"):
        LocalApplicationController(host="0.0.0.0")


def test_second_managed_controller_is_denied_until_the_first_releases_ownership():
    ownership = {"held": False}

    class Lease:
        def acquire(self):
            if ownership["held"]:
                raise LifecycleError("Another managed launcher already owns the local backend")
            ownership["held"] = True

        def release(self):
            ownership["held"] = False

    def make_app(_password, _origin):
        application = FastAPI()
        @application.get("/health")
        def health():
            return {"status": "ok"}
        return application

    first = LocalApplicationController(port=0, app_factory=make_app, lease_factory=Lease)
    second = LocalApplicationController(port=0, app_factory=make_app, lease_factory=Lease)
    first.start(PASSWORD)
    with pytest.raises(LifecycleError, match="Another managed launcher"):
        second.start(PASSWORD)
    first.stop()
    second.start(PASSWORD)
    second.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows current-user file-lock behavior")
def test_windows_single_instance_lease_rejects_a_second_owner_until_release(tmp_path):
    first = _SingleInstanceLease(tmp_path / "launcher.lock")
    second = _SingleInstanceLease(tmp_path / "launcher.lock")
    first.acquire()
    try:
        with pytest.raises(LifecycleError, match="Another managed launcher"):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_managed_server_keeps_explicit_owner_sign_in():
    applications = []

    def make_local_app(password, origin):
        application = create_local_app(password=password, origin=origin)
        applications.append(application)
        return application

    controller = LocalApplicationController(port=0, app_factory=make_local_app)
    origin = controller.start(PASSWORD)
    try:
        with pytest.raises(HTTPError) as removed:
            urlopen(f"{origin}/ui/login", timeout=3)
        assert removed.value.code == 404
        with pytest.raises(HTTPError) as denied:
            urlopen(f"{origin}/api/local/session", timeout=3)
        assert denied.value.code == 401

        request = Request(
            f"{origin}/api/local/login",
            data=json.dumps({"password": PASSWORD}).encode(),
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 200
            assert "HttpOnly" in response.headers["Set-Cookie"]
        assert len(applications) == 1
    finally:
        controller.stop()


def test_startup_health_failure_is_safe_and_stop_is_requested_without_force_kill():
    class Server:
        started = True
        should_exit = False

        def run(self, sockets):
            self.socket = sockets[0]
            while not self.should_exit:
                time.sleep(0.005)

    holder = {}

    def server_factory(_application, _port):
        holder["server"] = Server()
        return holder["server"]

    controller = LocalApplicationController(
        port=0,
        app_factory=lambda _password, _origin: object(),
        server_factory=server_factory,
        health_probe=lambda _origin: False,
    )
    # A short fake clock keeps the timeout deterministic without waiting 15 s.
    ticks = [0.0]
    controller._clock = lambda: ticks[0]
    controller._sleep = lambda _seconds: ticks.__setitem__(0, ticks[0] + 1.0)
    with pytest.raises(LifecycleError, match="did not become healthy"):
        controller.start(PASSWORD)
    assert holder["server"].should_exit is True
    assert "startup timed out; shutdown was requested" in " ".join(controller.events())
    controller.stop()
