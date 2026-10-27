"""Real installed Chromium, Python transport, and a local network tripwire."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import pytest
from app.integrations.offline_browser import BrowserError,sync_browser


def test_offline_renderer_blocks_scripts_resources_and_keeps_no_profile():
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):requests.append(self.path);self.send_response(200);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)+'/must-never-load'
    try:
        with sync_browser() as engine:
            browser=engine.chromium.launch(headless=True,chromium_sandbox=True,timeout=10000,args=['--no-proxy-server'])
            profile=Path(browser.transport.profile)
            try:
                context=browser.new_context(accept_downloads=False,java_script_enabled=False,permissions=[],service_workers='block')
                context.set_offline(True);context.route('**/*',lambda route:route.abort());page=context.new_page()
                page.set_content('<title>Safe title</title><script>document.title="executed";fetch('+repr(url)+')</script>'
                    '<body><p>Visible evidence</p><img src="'+url+'"><iframe src="'+url+'"></iframe></body>')
                assert page.title()=='Safe title' and 'Visible evidence' in page.locator('body').inner_text()
                assert requests==[]
                with pytest.raises(BrowserError,match='cannot be enabled'):context.set_offline(False)
                with pytest.raises(BrowserError,match='inert offline'):browser.new_context(accept_downloads=True)
            finally:browser.close()
            assert not profile.exists()
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
