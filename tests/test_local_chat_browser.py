"""Actual loopback browser flow; fake provider and pytest-isolated SQLite."""
import socket
from threading import Event, Thread

from tools.headless_browser import Browser
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
        with Browser() as browser:
            def approve_reviewed_chat_plan(message):
                assert "Review this chat plan before work begins" in message
                assert "No Task execution" in message
                return True
            browser.dialog_handler=approve_reviewed_chat_plan
            browser.viewport(1200,1000)
            browser.navigate(origin+"/ui/login")
            browser.fill('#password','test-only-browser-password')
            browser.click('#local-login button[type="submit"]')
            browser.wait('location.pathname === "/ui"')
            browser.wait('document.querySelector("#setup-state")?.textContent.includes("PARTIALLY CONFIGURED")')
            browser.screenshot(tmp_path/'local-dashboard.png')
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
            browser.viewport(390,844)
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
            browser.wait("""[...document.querySelectorAll('a')].some(a=>{const clone=a.cloneNode(true);clone.querySelectorAll('[aria-hidden="true"]').forEach(e=>e.remove());return clone.textContent.trim()==='Start Chat' && a.getClientRects().length})""")
            browser.navigate(origin+'/ui/chat?desktop=1')
            browser.wait('document.querySelector("#chat-identity")?.textContent.includes("Local Worker")')
            browser.wait('document.querySelector("#chat-input")?.disabled === false')
            assert browser.evaluate('!document.querySelector("#chat-settings").hasAttribute("open")')
            browser.fill('#chat-input','Hello from the browser');browser.enter('#chat-input')
            browser.wait('document.querySelector("#chat-history")?.textContent.includes("Fake browser reply")')
            assert browser.evaluate('document.querySelector("#chat-history").textContent.includes("user - completed")')
            assert browser.evaluate('window.providerInjected === undefined && document.querySelectorAll("#chat-history script").length === 0')
            assert provider.calls==1
            browser.screenshot(tmp_path/'local-chat.png')
            browser.viewport(390,844)
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert browser.evaluate('document.querySelector("#chat-sidebar").getBoundingClientRect().right <= 0')
            browser.click('#chat-menu-button')
            browser.wait('document.querySelector("#chat-menu-button").getAttribute("aria-expanded") === "true"')
            browser.wait('document.querySelector("#chat-sidebar").getBoundingClientRect().right > 0')
            browser.click('.chat-advanced-nav > summary');browser.click('#chat-close')
            browser.wait('document.querySelector("#chat-input").disabled === true')
            browser.click('a[href^="/ui/login"]')
            browser.wait('location.pathname === "/ui/login"')
            browser.click('#local-logout')
            browser.wait('document.querySelector("#login-state")?.textContent === "Signed out"')
            browser.navigate(origin+'/ui/chat')
            browser.wait('document.querySelector("#chat-state")?.textContent.includes("Sign in")')
            assert provider.calls==1
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive(), "Local test server did not stop"
