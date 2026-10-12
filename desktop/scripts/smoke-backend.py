"""Exercise the frozen Windows backend without real providers or retained data."""

from __future__ import annotations

from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


PASSWORD = "frozen-desktop-smoke-passphrase"
HOST = "127.0.0.1"
PORT = 18765
ORIGIN = f"http://{HOST}:{PORT}"


def _start(executable: Path, ui_dir: Path, local_app_data: Path, working_dir: Path,
           *, first_run: bool):
    env = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA")
        if os.environ.get(key)
    }
    env["LOCALAPPDATA"] = str(local_app_data)
    process = subprocess.Popen(
        [str(executable), "--port", str(PORT), "--ui-dir", str(ui_dir)],
        cwd=working_dir, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = queue.Queue()
    reader = threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True)
    reader.start()
    setup = {"password": PASSWORD, "confirmation": PASSWORD if first_run else ""}
    process.stdin.write(json.dumps(setup, separators=(",", ":")) + "\n")
    process.stdin.flush()
    try:
        line = output.get(timeout=20)
    except queue.Empty:
        process.stdin.close()
        process.wait(timeout=10)
        raise RuntimeError("Frozen backend startup timed out") from None
    if line.rstrip("\r\n") != f"ERSELMETZ_READY:{PORT}":
        process.stdin.close()
        process.wait(timeout=10)
        raise RuntimeError("Frozen backend did not report owned-service readiness")
    return process


def _request(opener, path: str, *, method="GET", payload=None, origin=False):
    headers = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if origin:
        headers["Origin"] = ORIGIN
    request = Request(ORIGIN + path, data=data, headers=headers, method=method)
    with opener.open(request, timeout=5) as response:
        return response.status, response.read(2_000_000), response.headers


def _stop(process):
    process.stdin.write('{"command":"shutdown"}\n')
    process.stdin.flush()
    process.stdin.close()
    try:
        code = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Frozen backend did not stop gracefully") from None
    if code != 0:
        raise RuntimeError("Frozen backend exited unexpectedly")


def _exercise(opener):
    status, html, _headers = _request(opener, "/desktop/")
    if status != 200 or b"Your AI organization" not in html or b"/desktop/_next/static" not in html:
        raise RuntimeError("Static desktop command center did not render")
    css_path = next((line.split(b' href="', 1)[1].split(b'"', 1)[0]
                     for line in html.split(b"<link")
                     if b"stylesheet" in line and b"/desktop/_next/" in line), None)
    if not css_path:
        raise RuntimeError("Static desktop styles are missing")
    css_status, _css, _ = _request(opener, css_path.decode("ascii"))
    if css_status != 200:
        raise RuntimeError("Static desktop stylesheet was not served")
    login_status, _body, headers = _request(
        opener, "/api/local/login", method="POST", payload={"password": PASSWORD}, origin=True)
    if login_status != 200 or "HttpOnly" not in headers.get("Set-Cookie", ""):
        raise RuntimeError("Owner sign-in did not issue an HttpOnly session")
    session_status, session_body, _ = _request(opener, "/api/local/session")
    if session_status != 200 or b'"identity":"local-owner"' not in session_body:
        raise RuntimeError("Owner session did not authenticate")
    for route in ("/ui/chat", "/ui/providers", "/ui/online-provider", "/ui/local-models"):
        route_status, _body, _ = _request(opener, route)
        if route_status != 200:
            raise RuntimeError("Existing chat or provider setup page was unavailable")


def main():
    if sys.platform != "win32":
        raise SystemExit("This smoke test requires Windows DPAPI and the Windows frozen backend")
    root = Path(__file__).resolve().parents[2]
    executable = root / "desktop" / "build" / "backend" / "erselmetz-backend" / "erselmetz-backend.exe"
    ui_dir = root / "desktop-ui" / "out"
    if not executable.is_file() or not (ui_dir / "index.html").is_file():
        raise SystemExit("Build the frozen backend and Next.js static export first")
    with tempfile.TemporaryDirectory(prefix="erselmetz-desktop-smoke-") as temporary:
        temp = Path(temporary)
        local_app_data = temp / "local-app-data"
        working = temp / "working"
        working.mkdir()
        credential = local_app_data / "ERSELMETZ AI" / "owner-credential.dpapi"
        cookie_jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookie_jar))
        process = _start(executable, ui_dir, local_app_data, working, first_run=True)
        try:
            _exercise(opener)
        finally:
            _stop(process)
        if not credential.is_file():
            raise RuntimeError("Owner verifier was not retained across service stop")
        process = _start(executable, ui_dir, local_app_data, working, first_run=False)
        try:
            cookie_jar.clear()
            _exercise(opener)
        finally:
            _stop(process)
    print("Frozen sidecar first-run, chat/provider pages, DPAPI credential retention, restart, and graceful stop passed.")


if __name__ == "__main__":
    main()
