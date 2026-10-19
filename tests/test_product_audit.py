"""Cross-page product checks using an isolated runtime and loopback browser."""
import socket
from pathlib import Path
from threading import Event, Thread
from html.parser import HTMLParser
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
import uvicorn

from app.webui.router import router as ui_router
from app.local import create_local_app
from app.runtime import create_corporation_runtime


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value and value.startswith("/"):
                self.paths.add(urlsplit(value).path)


def test_all_ui_routes_local_links_and_assets_load():
    runtime = create_corporation_runtime()
    app = create_local_app(password="test-only-audit-password", application_service=runtime.application_service)
    routes = sorted({route.path for route in [*ui_router.routes, *app.routes] if getattr(route, "path", "").startswith("/ui")
                     and "{" not in route.path and "GET" in getattr(route, "methods", set())})
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 1234)) as client:
        assert client.post("/api/local/login", json={"password": "test-only-audit-password"}, headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200
        links = set()
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200, route
            parser = Links()
            parser.feed(response.text)
            links.update(parser.paths)
        for path in sorted(links):
            assert client.get(path).status_code == 200, path
    print(f"Audit route sweep: {len(routes)} UI routes; {len(links)} unique local link/asset targets")


def test_every_ui_page_browser_layout_and_script_health(tmp_path):
    runtime = create_corporation_runtime()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    desktop_export = Path(__file__).resolve().parents[1] / "desktop-ui" / "out"
    app = create_local_app(password="test-only-audit-password", origin=origin,
                           application_service=runtime.application_service,
                           desktop_ui_dir=desktop_export if desktop_export.is_dir() else None)
    paths = sorted({route.path for route in [*ui_router.routes, *app.routes] if getattr(route, "path", "").startswith("/ui")
                    and "{" not in route.path and "GET" in getattr(route, "methods", set())})
    if desktop_export.is_dir():
        paths.extend(["/desktop/", "/desktop/settings/"])
    started = Event()
    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            started.set()
    server = Server(uvicorn.Config(app, log_level="error", proxy_headers=False))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        assert started.wait(10)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(f"{page.url}: {error.stack}"))
                # This is a layout/script audit. Do not trigger host WMI or
                # hardware inspection from a browser test; those contracts
                # have separate deterministic service tests.
                page.route("**/api/system/hardware-profile", lambda route: route.fulfill(
                    status=200, content_type="application/json", body="{}"))
                page.goto(origin + "/ui")
                page.wait_for_function("document.querySelector('#setup-state').textContent.includes('SIGN')")
                assert page.locator(".dashboard-grid .dashboard-card:visible").count() == 0
                page.goto(origin + "/ui/chat")
                page.get_by_label("Chat navigation").get_by_role(
                    "link", name="Owner sign-in", exact=True).click()
                page.wait_for_url(origin + "/ui/login?next=/ui/chat")
                page.locator("#password").fill("test-only-audit-password")
                page.get_by_role("button", name="Sign in", exact=True).click()
                page.wait_for_url(origin + "/ui/chat")
                findings = []
                for path in paths:
                    # Settings hydrates bounded owner-protected summaries after
                    # the document loads. Those requests are not part of the
                    # static-page/layout health assertion, and networkidle can
                    # remain pending when the browser keeps an API request open.
                    page.goto(origin + path, wait_until="domcontentloaded")
                    page.locator("h1").wait_for(state="visible")
                    assert page.locator("h1").count() == 1, path
                    for width in (1280, 768, 390):
                        page.set_viewport_size({"width": width, "height": 900})
                        overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                        if overflow:
                            findings.append(f"{path}: horizontal overflow at {width}px")
                    page.set_viewport_size({"width": 1280, "height": 900})
                    if path in {"/ui", "/ui/chat", "/ui/memory", "/ui/visualization", "/ui/provider-connections", "/desktop/", "/desktop/settings/"}:
                        page.screenshot(path=str(tmp_path / (path.replace("/", "_") + ".png")), full_page=True)
                print("Browser audit screenshots:", tmp_path)
                print("Browser audit page count:", len(paths))
                print("Browser audit layout findings:", findings)
                assert not errors, errors
                assert not findings, findings
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()
