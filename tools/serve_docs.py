"""Loopback-only static documentation preview, with an explicit file allowlist."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse

ROOT=Path(__file__).resolve().parents[1]/'docs'
PAGES=['index.html','documentation.html','architecture.html','organization.html','how-it-works.html',
       'integrations.html','free-pool.html','security.html','roadmap.html','tasks.html','updates.html','about.html']
FILES={**{name:'text/html; charset=utf-8' for name in PAGES},'site.css':'text/css; charset=utf-8',
       'tasks-data.mjs':'text/javascript; charset=utf-8','tasks-data.json':'application/json; charset=utf-8',
       'tasks-page.js':'text/javascript; charset=utf-8','roadmap-status.js':'text/javascript; charset=utf-8',
       'design/task-190-code-execution-threat-model.md':'text/markdown; charset=utf-8'}
CSP="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'"


def create_server(root=ROOT,port=0):
    root=Path(root)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.serve()
        def do_HEAD(self):self.serve(head=True)
        def denied(self):
            self.send_response(405);self.send_header('Allow','GET, HEAD');self.send_header('Content-Length','0');self.end_headers()
        do_POST=do_PUT=do_PATCH=do_DELETE=do_OPTIONS=do_TRACE=denied
        def serve(self,head=False):
            name=urlsplit(self.path).path.removeprefix('/') or 'index.html'
            media=FILES.get(name)
            if media is None:status=404;body=b'Not found';media='text/plain; charset=utf-8'
            else:
                try:body=(root/name).read_bytes();status=200
                except OSError:status=500;body=b'Unable to serve documentation';media='text/plain; charset=utf-8'
            self.send_response(status);self.send_header('Content-Type',media);self.send_header('Content-Length',str(len(body)))
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
            self.send_header('Content-Security-Policy',CSP);self.end_headers()
            if not head:self.wfile.write(body)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=3000);args=parser.parse_args()
    server=create_server(port=args.port);print('Static docs preview: http://127.0.0.1:'+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
