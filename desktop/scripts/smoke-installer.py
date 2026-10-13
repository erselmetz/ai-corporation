"""Install and exercise the actual Windows Electron package in a temp profile."""

from __future__ import annotations

import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import ctypes
from ctypes import wintypes

from playwright.sync_api import sync_playwright

PASSWORD = "electron-installer-smoke-password"
ORIGIN = "http://127.0.0.1:8765"


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _install(installer: Path, install_dir: Path):
    result = subprocess.run([str(installer), "/S", f"/D={install_dir}"],
                            timeout=180, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0:
        raise RuntimeError("Per-user installer did not finish successfully")
    executable = install_dir / "ERSELMETZ AI.exe"
    if not executable.is_file():
        raise RuntimeError("Installed Electron application is missing")
    return executable


def _start(executable: Path, local_app_data: Path, debug_port: int):
    env = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "PATH")
        if os.environ.get(key)
    }
    env["LOCALAPPDATA"] = str(local_app_data)
    return subprocess.Popen([str(executable), f"--remote-debugging-port={debug_port}"],
                            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _wait_for_context(playwright, debug_port: int, timeout=30):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=1500)
            if browser.contexts:
                return browser, browser.contexts[0]
        except Exception as error:
            last_error = error
        time.sleep(0.2)
    raise RuntimeError("The installed Electron window did not become available for smoke verification") from last_error


def _wait_browser_page(context, predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for page in context.pages:
            if predicate(page.url):
                return page
        time.sleep(0.1)
    raise RuntimeError("The expected bootstrap window did not open")


def _wait_page(playwright, debug_port: int, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        browser = None
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=1_500)
            for context in browser.contexts:
                for page in context.pages:
                    if predicate(page.url):
                        return browser, page
        except Exception as error:
            last_error = error
        if browser is not None:
            browser.close()
        time.sleep(0.1)
    raise RuntimeError("The expected local application window did not open") from last_error


def _owner_setup(page, playwright, debug_port: int, *, first_run: bool):
    page.locator("#password").wait_for(timeout=10_000)
    page.locator("#password").fill(PASSWORD)
    if first_run:
        page.locator("#confirmation").fill(PASSWORD)
    page.locator("#start-button").click(no_wait_after=True)
    try:
        return _wait_page(playwright, debug_port, lambda url: url.startswith(ORIGIN + "/desktop/"), timeout=30)
    except RuntimeError:
        try:
            message = page.locator("#state").inner_text(timeout=1_000)
        except Exception:
            message = "bootstrap window closed before the command-center page was observed"
        pages = []
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=1_500)
            pages = [candidate.url for current in browser.contexts for candidate in current.pages]
            browser.close()
        except Exception:
            pass
        raise RuntimeError(f"Electron startup did not complete: {message}; open pages: {pages}") from None


def _verify_app(page, *, must_sign_in: bool):
    page.get_by_role("heading", name=re.compile(r"Welcome to ERSELMETZ AI")).wait_for(timeout=15_000)
    session_status = page.evaluate("fetch('/api/local/session').then(response => response.status)")
    if must_sign_in and session_status != 401:
        raise RuntimeError("A prior owner session survived application restart")
    page.goto(ORIGIN + "/ui/login")
    page.locator("#password").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    try:
        page.wait_for_url(ORIGIN + "/ui", timeout=10_000)
    except Exception:
        message = page.locator("#login-state").inner_text()
        raise RuntimeError(f"Owner sign-in failed in the installed application: {message or 'no session redirect'}") from None
    if page.evaluate("fetch('/api/local/session').then(response => response.status)") != 200:
        raise RuntimeError("The installed application did not establish an authenticated owner session")
    for route in ("/ui/chat", "/ui/providers", "/ui/online-provider", "/ui/local-models"):
        response = page.goto(ORIGIN + route)
        if response is None or response.status != 200:
            raise RuntimeError("A shared chat/provider page is missing from the installed application")


def _stop_window(page, process):
    _request_window_close(process.pid)
    try:
        code = process.wait(timeout=40)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Closing the Electron window did not gracefully stop its Python backend") from None
    if code != 0:
        raise RuntimeError("Electron did not exit cleanly after backend shutdown")


def _request_window_close(process_id: int) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_windows = user32.EnumWindows
    enum_windows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    enum_windows.restype = wintypes.BOOL
    get_window_process_id = user32.GetWindowThreadProcessId
    get_window_process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    post_message = user32.PostMessageW
    post_message.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        get_window_process_id(hwnd, ctypes.byref(owner))
        if owner.value == process_id and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    enum_windows(visit, 0)
    if not found or not post_message(found[0], 0x0010, 0, 0):
        raise RuntimeError("The installed Electron window could not receive a normal close request")


def _cleanup(context, process):
    if process is None or process.poll() is not None:
        return
    try:
        _request_window_close(process.pid)
    except RuntimeError:
        pass
    try:
        process.wait(timeout=40)
    except subprocess.TimeoutExpired:
        print("Smoke-test Electron process remained open after a normal window-close request.", flush=True)


def main():
    if os.name != "nt":
        raise SystemExit("The installer smoke test requires Windows")
    root = Path(__file__).resolve().parents[2]
    release = root / "desktop" / "release"
    installers = list(release.glob("ERSELMETZ-AI-Setup-*-win-x64.exe"))
    if len(installers) != 1:
        raise SystemExit("Build exactly one Windows installer before running this smoke test")
    with tempfile.TemporaryDirectory(prefix="erselmetz-installer-smoke-", ignore_cleanup_errors=True) as temporary:
        temp = Path(temporary)
        install_dir = temp / "installed-app"
        local_app_data = temp / "local-app-data"
        executable = _install(installers[0], install_dir)
        credential = local_app_data / "ERSELMETZ AI" / "owner-credential.dpapi"
        debug_port = _free_port()

        with sync_playwright() as playwright:
            process = None
            context = None
            try:
                process = _start(executable, local_app_data, debug_port)
                _browser, context = _wait_for_context(playwright, debug_port)
                bootstrap = _wait_browser_page(context, lambda url: url.endswith("bootstrap.html"))
                if bootstrap.evaluate("window.desktopBridge.getSetupState()") is not True:
                    raise RuntimeError("A fresh installed profile did not expose first-run owner setup")
                app_browser, app_page = _owner_setup(bootstrap, playwright, debug_port, first_run=True)
                _verify_app(app_page, must_sign_in=False)
                _stop_window(app_page, process)
                app_browser.close()
            finally:
                _cleanup(context, process)
            if not credential.is_file():
                raise RuntimeError("First-run setup did not preserve its DPAPI owner verifier")

            debug_port = _free_port()
            process = None
            context = None
            try:
                process = _start(executable, local_app_data, debug_port)
                _browser_again, context = _wait_for_context(playwright, debug_port)
                bootstrap = _wait_browser_page(context, lambda url: url.endswith("bootstrap.html"))
                if bootstrap.evaluate("window.desktopBridge.getSetupState()") is not False:
                    raise RuntimeError("An existing installed profile did not request owner-password verification")
                app_browser, app_page = _owner_setup(bootstrap, playwright, debug_port, first_run=False)
                _verify_app(app_page, must_sign_in=True)
                _stop_window(app_page, process)
                app_browser.close()
            finally:
                _cleanup(context, process)

        uninstaller = next((path for path in install_dir.glob("*uninstall*.exe")), None)
        if uninstaller is None:
            uninstaller = next((path for path in install_dir.glob("Uninstall*.exe")), None)
        if uninstaller is None:
            raise RuntimeError("Per-user uninstaller was not installed")
        result = subprocess.run([str(uninstaller), "/S"], timeout=120, check=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0 or not credential.is_file():
            raise RuntimeError("Uninstall did not preserve owner data")
        _install(installers[0], install_dir)
        debug_port = _free_port()
        with sync_playwright() as playwright:
            process = _start(executable, local_app_data, debug_port)
            _browser, context = _wait_for_context(playwright, debug_port)
            bootstrap = _wait_browser_page(context, lambda url: url.endswith("bootstrap.html"))
            app_browser, app_page = _owner_setup(bootstrap, playwright, debug_port, first_run=False)
            _verify_app(app_page, must_sign_in=True)
            _stop_window(app_page, process)
            app_browser.close()
    print("Installed Electron first-run, auth/chat/providers, graceful stop/restart, uninstall retention, and reinstall recovery passed.")


if __name__ == "__main__":
    main()
