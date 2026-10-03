"""Actual loopback browser flow; fake provider and pytest-isolated SQLite."""
import socket
from threading import Event, Thread

from playwright.sync_api import sync_playwright, expect
import uvicorn

from app.local import create_local_app
from app.providers import AIProvider
from app.runtime.factory import create_corporation_runtime


class BrowserProvider(AIProvider):
    def __init__(self):
        self.calls = 0

    def generate(self, model, prompt):
        self.calls += 1
        return "<script>window.providerInjected = true</script> Fake browser reply"


def test_local_owner_signin_chat_safe_reply_close_and_logout(tmp_path):
    runtime = create_corporation_runtime()
    provider = BrowserProvider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    app = create_local_app(password="test-only-browser-password", origin=origin,
                           application_service=runtime.application_service)
    started = Event()

    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            started.set()

    server = Server(uvicorn.Config(app, log_level="error", proxy_headers=False))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        assert started.wait(10), "Local test server did not start"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 1000})
                page.goto(origin + "/ui/login")
                page.locator("#password").fill("test-only-browser-password")
                page.get_by_role("button", name="Sign in", exact=True).click()
                page.wait_for_url(origin + "/ui")
                page.get_by_role("link", name="Coordinator chat", exact=True).click()
                expect(page.locator("#chat-state")).to_contain_text("Choose a coordinator")
                page.get_by_role("button", name="New conversation", exact=True).click()
                expect(page.locator("#chat-identity")).to_contain_text("Local Worker")
                page.locator("#chat-input").fill("Hello from the browser")
                page.get_by_role("button", name="Send", exact=True).click()
                expect(page.locator("#chat-history")).to_contain_text("Fake browser reply")
                expect(page.locator("#chat-history")).to_contain_text("user - completed")
                assert page.evaluate("window.providerInjected === undefined")
                assert page.locator("#chat-history script").count() == 0
                assert provider.calls == 1
                screenshot = tmp_path / "local-chat.png"
                page.screenshot(path=str(screenshot), full_page=True)
                print(f"Browser review screenshot: {screenshot}")
                # Check narrow-screen usability without another model request.
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.get_by_role("button", name="Close conversation", exact=True).click()
                expect(page.locator("#chat-input")).to_be_disabled()
                page.get_by_role("link", name="Local sign-in / sign-out", exact=True).click()
                page.get_by_role("button", name="Sign out", exact=True).click()
                expect(page.locator("#login-state")).to_have_text("Signed out")
                page.goto(origin + "/ui/chat")
                expect(page.locator("#chat-state")).to_contain_text("Sign in")
                assert provider.calls == 1
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive(), "Local test server did not stop"
