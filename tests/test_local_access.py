from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.api.app import create_app
from app.api.local_access import COOKIE, LocalOwnerAuthentication
from app.local import create_local_app

PASSWORD = "test-only-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"


def client_for(**kwargs):
    app = create_local_app(password=PASSWORD, application_service=MagicMock(), **kwargs)
    return TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100))


def login(client):
    return client.post("/api/local/login", json={"password": PASSWORD},
                       headers={"Origin": ORIGIN})


def test_login_session_cookie_and_logout_revocation():
    with client_for() as client:
        assert client.get("/api/local/session").status_code == 401
        response = login(client)
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age=3600" in cookie
        token = client.cookies[COOKIE]
        record = client.get("/api/local/session")
        assert record.headers["cache-control"] == "no-store"
        assert "maintenance:approve" not in record.json()["permissions"]
        assert "task:create" not in record.json()["permissions"]
        assert "employee:read" in record.json()["permissions"]
        assert {
            "employee-chat:read",
            "employee-chat:start",
            "employee-chat:send",
            "employee-chat:close",
        }.issubset(record.json()["permissions"])
        assert "employee:manage" not in record.json()["permissions"]
        assert client.post("/api/local/logout", json={}, headers={"Origin": ORIGIN}).status_code == 403
        from starlette.requests import Request
        malformed = Request({"type": "http", "method": "POST", "scheme": "http",
            "path": "/api/local/logout", "query_string": b"", "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50100), "headers": [(b"host", b"127.0.0.1:8000"),
            (b"cookie", f"{COOKIE}={token}".encode()), (b"x-local-csrf", b"\xff")]})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as denied:
            client.app.state.authentication_backend.require_csrf(malformed)
        assert denied.value.status_code == 403
        csrf = record.json()["csrf"]
        assert client.post("/api/local/logout", json={}, headers={"Origin": ORIGIN,
                           "X-Local-CSRF": csrf}).status_code == 200
        client.cookies.set(COOKIE, token)
        assert client.get("/api/local/session").status_code == 401


def test_failed_login_limits_and_cooldown():
    now = [1.0]
    with client_for(clock=lambda: now[0]) as client:
        for _ in range(5):
            assert client.post("/api/local/login", json={"password": "wrong"},
                               headers={"Origin": ORIGIN}).status_code == 401
        assert login(client).status_code == 429
        now[0] += 301
        assert login(client).status_code == 200


def test_session_expires_and_restart_invalidates():
    now = [0.0]
    with client_for(clock=lambda: now[0]) as client:
        assert login(client).status_code == 200
        token = client.cookies[COOKIE]
        now[0] = 3600
        assert client.get("/api/local/session").status_code == 401
    with client_for() as restarted:
        restarted.cookies.set(COOKIE, token)
        assert restarted.get("/api/local/session").status_code == 401


def test_host_origin_peer_and_csrf_rejected():
    with client_for() as client:
        assert client.get("/health", headers={"Host": "evil.example"}).status_code == 403
        assert client.get("/health", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/local/login", json={"password": PASSWORD}).status_code == 403
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": "http://localhost:8000"}).status_code == 403
        assert login(client).status_code == 200
        assert client.post("/api/tasks", json={}, headers={"Origin": ORIGIN,
                           "X-Local-CSRF": "wrong"}).status_code == 403
    app = create_local_app(password=PASSWORD, application_service=MagicMock())
    with TestClient(app, base_url=ORIGIN, client=("192.0.2.1", 50100)) as remote:
        assert remote.get("/health").status_code == 403


def test_read_access_preserves_api_permissions_and_default_auth():
    service = MagicMock()
    service.list_employees.return_value = []
    app = create_local_app(password=PASSWORD, application_service=service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/employees").status_code == 401
        assert login(client).status_code == 200
        assert client.get("/api/employees").status_code == 200
        csrf = client.get("/api/local/session").json()["csrf"]
        assert client.post("/api/employees", json={"id": "x", "name": "X", "role": "Y"},
                           headers={"Origin": ORIGIN, "X-Local-CSRF": csrf}).status_code == 403
        service.create_employee.assert_not_called()
    with TestClient(create_app(application_service=service)) as default:
        assert default.get("/api/employees").status_code == 401
        assert default.get("/ui/login").status_code == 404


def test_invalid_login_payload_does_not_echo_password():
    with client_for() as client:
        for payload in [{"password": PASSWORD, "secret": PASSWORD}, {"password": [PASSWORD]},
                        {"password": PASSWORD * 50}]:
            response = client.post("/api/local/login", json=payload, headers={"Origin": ORIGIN})
            assert response.status_code == 422
            assert PASSWORD not in response.text
        response = client.post("/api/local/login", content="x" * 9000,
                               headers={"Origin": ORIGIN, "Content-Type": "application/json"})
        assert response.status_code == 413


def test_session_capacity_and_login_page_security():
    with client_for() as client:
        page = client.get("/ui/login")
        assert page.status_code == 200
        assert PASSWORD not in page.text
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        assert client.get("/ui/static/local-login.mjs").status_code == 200
        for _ in range(8):
            assert login(client).status_code == 200
        assert login(client).status_code == 429


@pytest.mark.parametrize("password,origin", [("short", ORIGIN), (PASSWORD, "http://0.0.0.0:8000"),
    (PASSWORD, "http://127.0.0.1:8000/path"), (PASSWORD, "https://127.0.0.1:8000"),
    (PASSWORD, "http://user@localhost:8000")])
def test_configuration_fails_closed(password, origin):
    with pytest.raises(ValueError):
        LocalOwnerAuthentication(password, origin)
