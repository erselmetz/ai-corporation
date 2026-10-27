"""Python/CDP implementation of the existing exact-origin browser boundary.

Each operation owns a fresh browser profile. Services still own capability checks,
approval digests, action budgets, stop checks and honest dispatch receipts.
"""
from contextlib import contextmanager
import json,time
from urllib.parse import urlsplit
from .offline_browser import BrowserError
from .scoped_chromium_transport import Browser as Transport


class Route:
    def __init__(self,context,params):
        self.context=context;self.identifier=params['requestId'];self.finished=False
        request=params['request'];self.request=type('Request',(),{'url':request['url'],'method':request['method']})()
    def abort(self):self._finish('Fetch.failRequest',{'errorReason':'BlockedByClient'})
    def continue_(self):self._finish('Fetch.continueRequest',{})
    def _finish(self,method,params):
        if self.finished:raise BrowserError('The resource decision was already consumed')
        self.finished=True;self.context.call(method,{'requestId':self.identifier,**params})


def origin(url):
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:return ''
    return parsed.scheme+'://'+parsed.netloc


class Browser:
    def __init__(self,*,headless=False,startup_timeout=10000):
        try:self.transport=Transport(headless=headless,startup_timeout=startup_timeout)
        except Exception as error:raise BrowserError('The isolated browser could not start') from error
    def new_context(self,**options):
        if options!={'accept_downloads':False,'java_script_enabled':True,'permissions':[],'service_workers':'block'}:
            raise BrowserError('Unsupported browser context policy')
        return Context(self.transport)
    def close(self):self.transport.close()


class Context:
    def __init__(self,transport):
        self.transport=transport;self.route_handler=None;self.websocket_policy=False;self.timeout=2500;self.origin='';self.resources=0;self.quarantined=set()
    def call(self,method,params=None):
        try:return self.transport.call(method,params)
        except BrowserError:raise
        except Exception as error:raise BrowserError('The scoped browser operation failed') from error
    def set_default_timeout(self,value):
        if type(value) is not int or not 1<=value<=10000:raise BrowserError('Invalid browser timeout')
        self.timeout=value
    def set_default_navigation_timeout(self,value):self.set_default_timeout(value)
    def route_web_socket(self,pattern,handler):
        if pattern!='**/*':raise BrowserError('All WebSockets must remain denied')
        self.websocket_policy=True
    def route(self,pattern,handler):
        if pattern!='**/*':raise BrowserError('Every request must pass the origin policy')
        self.route_handler=handler
    def new_page(self):
        if self.route_handler is None or not self.websocket_policy:raise BrowserError('Browser resource policies must be installed first')
        self.deadline()
        self.transport.handler=self.event
        self.call('Network.setBlockedURLs',{'urls':['ws://*','wss://*']})
        self.call('Page.addScriptToEvaluateOnNewDocument',{'source':"""
          Object.defineProperty(globalThis,'WebSocket',{value:class {constructor(){throw new DOMException('WebSockets are disabled','SecurityError')}},writable:false,configurable:false});
          for(const name of ['Worker','SharedWorker']) Object.defineProperty(globalThis,name,{value:class {constructor(){throw new DOMException('Workers are disabled','SecurityError')}},writable:false,configurable:false});
          Object.defineProperty(globalThis,'open',{value:()=>{throw new DOMException('New windows are disabled','SecurityError')},writable:false,configurable:false});
        """})
        self.call('Target.setAutoAttach',{'autoAttach':True,'waitForDebuggerOnStart':True,'flatten':True})
        self.call('Fetch.enable',{'handleAuthRequests':True,'patterns':[
            {'urlPattern':'*','requestStage':'Request'},{'urlPattern':'*','requestStage':'Response'}]})
        return Page(self)
    def event(self,event):
        method=event.get('method');params=event.get('params',{})
        if method=='Target.attachedToTarget':
            identifier=params['targetInfo']['targetId']
            # Chromium can create a worker target before checking worker-src.
            # Dedicated workers do not support closeTarget. Keep every related
            # target paused from birth instead: never detach it or call
            # runIfWaitingForDebugger. Closing the owned browser destroys it.
            if params.get('waitingForDebugger') is not True:raise BrowserError('A related browser target was not isolated before execution')
            self.quarantined.add(identifier)
            if len(self.quarantined)>16:raise BrowserError('Related browser target budget exceeded')
            return
        if method=='Page.javascriptDialogOpening':
            self.call('Page.handleJavaScriptDialog',{'accept':False});return
        if method=='Fetch.authRequired':
            self.call('Fetch.continueWithAuth',{'requestId':params['requestId'],'authChallengeResponse':{'response':'CancelAuth'}});return
        if method!='Fetch.requestPaused':return
        if 'responseStatusCode' in params:
            if not self.origin:raise BrowserError('No approved navigation origin is active')
            policy="worker-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action "+self.origin+'; connect-src '+self.origin
            headers=params.get('responseHeaders',[])
            if len(headers)>256:raise BrowserError('Response header budget exceeded')
            self.call('Fetch.continueResponse',{'requestId':params['requestId'],'responseCode':params['responseStatusCode'],
                'responseHeaders':headers+[{'name':'Content-Security-Policy','value':policy}]});return
        route=Route(self,params);self.resources+=1
        if self.resources>256:route.abort();raise BrowserError('Browser resource budget exceeded')
        self.route_handler(route)
        if not route.finished:route.abort();raise BrowserError('A resource had no explicit policy decision')
    def close(self):self.transport.close()
    def deadline(self,timeout=None):self.transport.operation_deadline=time.monotonic()+(timeout or self.timeout)/1000


class Page:
    def __init__(self,context):self.context=context
    def evaluate(self,expression):
        result=self.context.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise BrowserError('The page could not complete inspection')
        return result.get('result',{}).get('value')
    @property
    def url(self):self.context.deadline();return self.evaluate('location.href')
    def title(self):self.context.deadline();return self.evaluate('document.title') or ''
    def goto(self,url,*,wait_until,timeout):
        if wait_until!='domcontentloaded':raise BrowserError('Unsupported navigation policy')
        self.context.deadline(timeout);self.context.origin=origin(url)
        if not self.context.origin:raise BrowserError('Invalid browser navigation origin')
        result=self.context.call('Page.navigate',{'url':url})
        if result.get('errorText'):raise BrowserError('The scoped page did not load')
        loader=result.get('loaderId')
        while True:
            frame=self.context.call('Page.getFrameTree')['frameTree']['frame']
            if (not loader or frame.get('loaderId')==loader) and self.evaluate('document.readyState !== "loading"'):return
            time.sleep(.01)
    def get_by_role(self,role,*,name,exact):
        if role not in {'button','link','textbox'} or exact is not True:raise BrowserError('Only exact accessible targets are supported')
        return Target(self,role,name)
    def locator(self,selector):
        if selector!='body':raise BrowserError('Only bounded document evidence can be read')
        return Body(self)


class Body:
    def __init__(self,page):self.page=page
    def evaluate(self,expression,*,timeout):
        self.page.context.deadline(timeout)
        return self.page.evaluate('('+expression+')(document.body)')


class Target:
    def __init__(self,page,role,name):self.page=page;self.role=role;self.name=name;self.backend=None
    def ids(self):
        nodes=self.page.context.call('Accessibility.getFullAXTree').get('nodes',[])
        if len(nodes)>10000:raise BrowserError('Accessible target budget exceeded')
        return [node['backendDOMNodeId'] for node in nodes if not node.get('ignored') and node.get('backendDOMNodeId')
            and node.get('role',{}).get('value')==self.role and node.get('name',{}).get('value')==self.name]
    def count(self):self.page.context.deadline();return len(self.ids())
    def run(self,expression,args=None,*,timeout):
        self.page.context.deadline(timeout);ids=self.ids()
        if len(ids)!=1 or self.backend is not None and ids[0]!=self.backend:raise BrowserError('The accessible target is missing, ambiguous or changed')
        self.backend=ids[0]
        obj=self.page.context.call('DOM.resolveNode',{'backendNodeId':self.backend})['object']['objectId']
        try:
            result=self.page.context.call('Runtime.callFunctionOn',{'objectId':obj,
                'functionDeclaration':'function(...args){return ('+expression+')(this,...args)}',
                'arguments':[{'value':value} for value in args or []],'returnByValue':True,'awaitPromise':True})
            if result.get('exceptionDetails'):raise BrowserError('The accessible target operation failed')
            return result.get('result',{}).get('value')
        finally:
            self.page.context.call('Runtime.releaseObject',{'objectId':obj})
    def evaluate(self,expression,*,timeout):return self.run(expression,timeout=timeout)
    def is_visible(self,*,timeout):
        return self.run("e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'}",timeout=timeout)
    def is_enabled(self,*,timeout):return self.run("e=>!e.matches(':disabled')&&!e.closest('[aria-disabled=true]')",timeout=timeout)
    def get_attribute(self,name,*,timeout):return self.run('(e,name)=>e.getAttribute(name)',[name],timeout=timeout)
    def click(self,*,timeout):
        return self.run('e=>{e.click();return new Promise(resolve=>setTimeout(resolve,50))}',timeout=timeout)
    def fill(self,value,*,timeout):
        return self.run('(e,value)=>{e.value=value;e.dispatchEvent(new Event("input",{bubbles:true}));e.dispatchEvent(new Event("change",{bubbles:true}));return new Promise(resolve=>setTimeout(resolve,50))}',[value],timeout=timeout)


class Chromium:
    def launch(self,**options):
        if options!={'headless':False,'chromium_sandbox':True,'timeout':10000,'args':['--no-proxy-server']}:
            # Service policy may choose a smaller startup bound; it cannot loosen
            # sandbox, process isolation or network policy through this adapter.
            if (set(options)!={'headless','chromium_sandbox','timeout','args'} or options['headless'] is not False
                or options['chromium_sandbox'] is not True or options['args']!=['--no-proxy-server']
                or type(options['timeout']) is not int or not 1<=options['timeout']<=10000):raise BrowserError('Unsupported scoped browser startup policy')
        return Browser(startup_timeout=options['timeout'])


@contextmanager
def sync_browser():
    yield type('ScopedEngine',(),{'chromium':Chromium()})()
