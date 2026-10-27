"""Legacy browser assertions preserved under Python/CDP; no Node test runner.

JavaScript fixtures exercise JavaScript Advanced clients. Python owns collection,
isolated Chromium, result accounting and failure reporting. WebGL is disabled.
"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,threading
import pytest
from test_public_docs import tool,ROOT

FIXTURES=ROOT/'tests/browser_contracts'
MANIFEST=json.loads((FIXTURES/'manifest.json').read_text())
CASES=[(item['file'],name) for item in MANIFEST['files'] for name in item['cases']]


@pytest.fixture(scope='session')
def contract_results():
    allowed={item['file'] for item in MANIFEST['files']}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            path=unquote(urlsplit(self.path).path)
            source=None
            if path=='/':body=b'<!doctype html><html><body>Isolated browser contract fixture</body></html>';media='text/html'
            else:
                if path=='/__contracts/harness.mjs':source=FIXTURES/'harness.mjs'
                elif path=='/__contracts/worker.mjs':source=FIXTURES/'worker.mjs'
                elif path.startswith('/tests/') and path.removeprefix('/tests/') in allowed:source=FIXTURES/path.removeprefix('/tests/')
                elif path.startswith('/app/webui/static/'):
                    candidate=(ROOT/path.removeprefix('/')).resolve()
                    if candidate.is_relative_to((ROOT/'app/webui/static').resolve()) and candidate.suffix in {'.mjs','.js','.css'}:source=candidate
                if source is None or not source.is_file():
                    self.send_response(404);self.end_headers();return
                body=source.read_bytes();media='text/javascript' if source.suffix in {'.mjs','.js'} else 'text/plain'
            self.send_response(200);self.send_header('Content-Type',media+'; charset=utf-8');self.send_header('Content-Length',str(len(body)))
            # Eval is confined to this test-only origin, for the two legacy
            # VM fixtures. Application/public-page CSP remains unchanged.
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-eval'; connect-src 'self'; object-src 'none'")
            self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    cache={};origin='http://127.0.0.1:'+str(server.server_port)
    try:
        with tool('headless_browser').Browser() as browser:
            def results(filename):
                if filename not in cache:
                    browser.navigate(origin+'/')
                    result=browser.evaluate('new Promise((resolve,reject)=>{const worker=new Worker("/__contracts/worker.mjs",{type:"module"});'
                        'worker.onmessage=event=>{worker.terminate();resolve(event.data);};worker.onerror=event=>{worker.terminate();reject(new Error(event.message));};'
                        'worker.postMessage({filename:'+json.dumps(filename)+'});})')
                    assert not result.get('error'),result.get('error')
                    output=result['results']
                    expected=next(item['cases'] for item in MANIFEST['files'] if item['file']==filename)
                    assert [item['name'] for item in output]==expected,'Contract case count/name changed without retirement accounting'
                    cache[filename]={item['name']:item for item in output}
                return cache[filename]
            yield results
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


@pytest.mark.parametrize('filename,name',CASES,ids=[name for _,name in CASES])
def test_browser_contract_without_node(contract_results,filename,name):
    result=contract_results(filename)[name]
    assert result['passed'],result.get('message',name)
