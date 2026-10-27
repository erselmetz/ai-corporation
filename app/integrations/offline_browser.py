"""Narrow Python adapter for inert offline documents; never navigates or acts."""
from contextlib import contextmanager
from .offline_chromium_transport import Browser as Transport,executable


class BrowserError(RuntimeError):pass


class Route:
    def abort(self):pass  # Protocol-level offline and deny-all policy is immutable.


class Browser:
    def __init__(self):
        try:self.transport=Transport()
        except Exception as error:raise BrowserError('Offline renderer unavailable') from error
    def new_context(self,**options):
        if options!={'accept_downloads':False,'java_script_enabled':False,'permissions':[],'service_workers':'block'}:
            raise BrowserError('Only an inert offline context is supported')
        return Context(self.transport)
    def close(self):self.transport.close()


class Context:
    def __init__(self,transport):self.transport=transport;self.offline=False;self.handler=None
    def set_offline(self,value):
        if value is not True:raise BrowserError('Network access cannot be enabled')
        self.offline=True
    def route(self,pattern,handler):
        if pattern!='**/*':raise BrowserError('All resources must remain denied')
        self.handler=handler
    def new_page(self):return Page(self)
    def close(self):pass  # The outer Browser.close owns and destroys this profile.


class Page:
    def __init__(self,context):self.context=context;self.transport=context.transport
    def set_content(self,markup,**options):
        if not self.context.offline or self.context.handler is None:raise BrowserError('Offline policy is required')
        if not isinstance(markup,str) or len(markup.encode('utf-8'))>2*1024*1024:raise BrowserError('Markup exceeds its bound')
        try:
            frame=self.transport.call('Page.getFrameTree')['frameTree']['frame']['id']
            self.transport.call('Page.setDocumentContent',{'frameId':frame,'html':markup})
        except Exception as error:raise BrowserError('Offline document rendering failed') from error
    def title(self):
        try:return self.transport.evaluate('document.title') or ''
        except Exception as error:raise BrowserError('Offline title inspection failed') from error
    def locator(self,selector):
        if selector!='body':raise BrowserError('Only document text can be inspected')
        return Body(self.transport)


class Body:
    def __init__(self,transport):self.transport=transport
    def inner_text(self,**options):
        try:return self.transport.evaluate("(document.body?.innerText || '').slice(0,20001)") or ''
        except Exception as error:raise BrowserError('Offline text inspection failed') from error


class Chromium:
    @property
    def executable_path(self):
        try:return executable()
        except RuntimeError:return ''
    def launch(self,**options):
        if options!={'headless':True,'chromium_sandbox':True,'timeout':10000,'args':['--no-proxy-server']}:
            raise BrowserError('Only sandboxed offline rendering is supported')
        return Browser()


@contextmanager
def sync_browser():
    yield type('OfflineEngine',(),{'chromium':Chromium()})()
