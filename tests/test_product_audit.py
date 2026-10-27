"""Cross-page product checks using an isolated runtime and loopback browser."""
import socket
from pathlib import Path
from threading import Event, Thread
from html.parser import HTMLParser
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from tools.headless_browser import Browser
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
    app = create_local_app(password="test-only-audit-password", origin=origin,
                           application_service=runtime.application_service)
    paths = sorted({route.path for route in [*ui_router.routes, *app.routes] if getattr(route, "path", "").startswith("/ui")
                    and "{" not in route.path and "GET" in getattr(route, "methods", set())})
    started = Event()
    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            started.set()
    server = Server(uvicorn.Config(app, log_level="error", proxy_headers=False,
                                   timeout_graceful_shutdown=2))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        assert started.wait(10)
        with Browser() as browser:
            browser.viewport(1280,900)
            # This static/layout check must not invoke WMI or inspect devices.
            browser.stub_json(origin+'/api/system/hardware-profile',{})
            browser.navigate(origin+'/ui')
            browser.wait('document.querySelector("#setup-state")?.textContent.includes("SIGN")')
            assert browser.evaluate('[...document.querySelectorAll(".dashboard-grid .dashboard-card")].filter(e=>e.getClientRects().length).length === 0')
            browser.navigate(origin+'/ui/chat')
            browser.click('.chat-advanced-nav > summary')
            browser.click('[aria-label="Chat navigation"] a[href^="/ui/login"]')
            browser.wait('location.pathname === "/ui/login" && location.search === "?next=/ui/chat"')
            browser.fill('#password','test-only-audit-password');browser.click('#local-login button[type="submit"]')
            browser.wait('location.pathname === "/ui/chat"')
            findings=[];errors=[]
            for path in paths:
                browser.navigate(origin+path)
                browser.wait('document.querySelector("h1")?.getClientRects().length > 0')
                assert browser.evaluate('document.querySelectorAll("h1").length')==1,path
                for width in (1280,768,390):
                    browser.viewport(width,900)
                    if browser.evaluate('document.documentElement.scrollWidth > innerWidth'):
                        findings.append(f'{path}: horizontal overflow at {width}px')
                browser.viewport(1280,900)
                if path in {'/ui','/ui/chat','/ui/memory','/ui/visualization','/ui/provider-connections','/desktop/','/desktop/settings/'}:
                    browser.screenshot(tmp_path/(path.replace('/','_')+'.png'))
                browser.evaluate('true')
                errors.extend(event for event in browser.events if event.get('method')=='Runtime.exceptionThrown')
            print('Browser audit screenshots:',tmp_path)
            print('Browser audit page count:',len(paths))
            print('Browser audit layout findings:',findings)
            assert not errors,errors
            assert not findings,findings
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()
