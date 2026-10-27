"""Real Chromium network tripwires for the Python scoped-action adapter."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import time
from app.integrations.scoped_browser import Browser


def test_real_scoped_targets_deny_background_and_foreign_writes_before_dispatch():
    received=[];foreign=[]
    class Foreign(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):foreign.append(self.path);self.send_response(200);self.end_headers()
        do_POST=do_GET
    peer=ThreadingHTTPServer(('127.0.0.1',0),Foreign)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            received.append(('GET',self.path));self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
            other='http://127.0.0.1:'+str(peer.server_port)+'/foreign'
            html='''<title>Scoped fixture</title><body><input aria-label="Search" name="search" type="text">
              <button onclick="fetch('/write',{method:'POST'})">Save settings</button>
              <script>fetch('/background-write',{method:'POST'}).catch(()=>{});
              fetch('''+repr(other)+''',{method:'POST'}).catch(()=>{});
              try{new Worker('/worker.js')}catch(e){}
              try{new WebSocket('ws://127.0.0.1:'''+str(peer.server_port)+'''/socket')}catch(e){}
              try{window.open('''+repr(other)+''')}catch(e){}
              </script></body>'''
            self.wfile.write(html.encode())
        def do_POST(self):received.append(('POST',self.path));self.send_response(200);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threads=[Thread(target=s.serve_forever,daemon=True) for s in [server,peer]]
    for thread in threads:thread.start()
    browser=Browser(headless=True);allowed=False;decisions=[];local='http://127.0.0.1:'+str(server.server_port)
    try:
        context=browser.new_context(accept_downloads=False,java_script_enabled=True,permissions=[],service_workers='block')
        context.set_default_timeout(10000);context.set_default_navigation_timeout(10000)
        context.route_web_socket('**/*',lambda websocket:None)
        def route(request):
            accepted=request.request.url.startswith(local+'/') and (request.request.method in {'GET','HEAD'} or allowed)
            decisions.append((request.request.url,request.request.method,accepted))
            request.continue_() if accepted else request.abort()
        context.route('**/*',route);page=context.new_page()
        page.goto(local+'/',wait_until='domcontentloaded',timeout=10000)
        assert page.title()=='Scoped fixture'
        save=page.get_by_role('button',name='Save settings',exact=True)
        assert save.count()==1 and save.is_visible(timeout=10000) and save.is_enabled(timeout=10000)
        search=page.get_by_role('textbox',name='Search',exact=True)
        assert search.count()==1
        search.fill('Local reviewed text',timeout=10000)
        assert search.evaluate('e=>e.value',timeout=10000)=='Local reviewed text'
        assert not any(method=='POST' for method,_ in received) and not foreign
        assert ('GET','/worker.js') not in received
        allowed=True
        try:save.click(timeout=10000)
        finally:allowed=False
        deadline=time.monotonic()+2
        while ('POST','/write') not in received and time.monotonic()<deadline:
            page.title();time.sleep(.01)
        assert received.count(('POST','/write'))==1 and ('POST','/background-write') not in received and not foreign
        assert any(method=='POST' and not accepted for _,method,accepted in decisions)
    finally:
        browser.close()
        for item in [server,peer]:item.shutdown();item.server_close()
        for thread in threads:thread.join(timeout=5)
