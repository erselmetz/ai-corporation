"""In-process policy dispatcher: existing ASGI handlers, zero TCP sockets.

The virtual HTTP envelope is an internal adapter for the existing authorization,
ownership, CSRF, consent, resource and Stop policy chain. It is never bound to a
network interface. Production does not depend on Starlette TestClient/pytest.
"""
import asyncio
import queue
import threading
import httpx

ORIGIN='http://127.0.0.1:1'

class Body(httpx.SyncByteStream):
    def __init__(self,events,future):self.events=events;self.future=future
    def __iter__(self):
        while True:
            try:item=self.events.get(timeout=180)
            except queue.Empty:self.future.cancel();raise httpx.ReadTimeout('Native request exceeded its deadline') from None
            if item is None:return
            if isinstance(item,Exception):raise RuntimeError('Native request did not complete') from None
            yield item
    def close(self):
        if not self.future.done():self.future.cancel()

class PolicyTransport(httpx.BaseTransport):
    def __init__(self,application):
        self.application=application;self.loop=asyncio.new_event_loop();self.pending=set();self.mutex=threading.Lock();self.closed=False
        self.thread=threading.Thread(target=self.loop.run_forever,name='native-policy',daemon=True);self.thread.start()
        async def start():
            self.lifespan=application.router.lifespan_context(application)
            await self.lifespan.__aenter__()
        try:asyncio.run_coroutine_threadsafe(start(),self.loop).result(60)
        except BaseException:self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(timeout=10);raise
    def handle_request(self,request):
        if str(request.url.copy_with(path='/',query=None)).rstrip('/')!=ORIGIN:raise ValueError('Native facade accepts only its internal origin')
        if not (request.url.path.startswith('/api/') or request.url.path=='/openapi.json'):raise ValueError('Native facade accepts only application operations')
        content=request.read();events=queue.Queue();started=queue.Queue(maxsize=1)
        async def dispatch():
            received=False;done=asyncio.Event();headers_sent=False
            async def receive():
                nonlocal received
                if not received:received=True;return {'type':'http.request','body':content,'more_body':False}
                await done.wait();return {'type':'http.disconnect'}
            async def send(message):
                nonlocal headers_sent
                if message['type']=='http.response.start':headers_sent=True;started.put(message)
                elif message['type']=='http.response.body':
                    if message.get('body'):events.put(message['body'])
                    if not message.get('more_body',False):events.put(None);done.set()
            scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
                   'method':request.method,'scheme':'http','path':request.url.path,
                   'raw_path':request.url.raw_path.split(b'?')[0],'query_string':request.url.query,
                   'root_path':'','headers':[(key.lower(),value) for key,value in request.headers.raw],'client':('127.0.0.1',0),'server':('127.0.0.1',1),'state':{}}
            try:await self.application(scope,receive,send)
            except Exception as error:
                if not headers_sent:started.put(error)
                events.put(error);done.set()
            finally:
                if not done.is_set():events.put(None);done.set()
        with self.mutex:
            if self.closed:raise RuntimeError('Native facade is closed')
            future=asyncio.run_coroutine_threadsafe(dispatch(),self.loop);self.pending.add(future)
        future.add_done_callback(self._finished)
        try:header=started.get(timeout=180)
        except queue.Empty:future.cancel();raise httpx.ReadTimeout('Native request exceeded its deadline') from None
        if isinstance(header,Exception):raise RuntimeError('Native policy dispatch failed') from None
        return httpx.Response(header['status'],headers=header['headers'],stream=Body(events,future))
    def _finished(self,future):
        with self.mutex:self.pending.discard(future)
    def close(self):
        with self.mutex:
            if self.closed:return
            self.closed=True;pending=list(self.pending)
        for future in pending:future.cancel()
        async def finish():await self.lifespan.__aexit__(None,None,None)
        try:asyncio.run_coroutine_threadsafe(finish(),self.loop).result(30)
        finally:self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(timeout=10);self.loop.close()

class InProcessController:
    def __init__(self,*,app_factory,**unused):self.app_factory=app_factory;self.transport=None
    def start(self,password):
        self.application=self.app_factory(password,ORIGIN);self.transport=PolicyTransport(self.application);return ORIGIN
    def stop(self):
        if self.transport:self.transport.close()
