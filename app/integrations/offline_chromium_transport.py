"""Offline Python CDP transport over a fresh installed Chromium profile.

No Node, npm, Playwright, user browser profile or WebGL dependency.
Internal Python transport only; application services retain their own authorization.
"""
import json,os,subprocess,tempfile,time
from pathlib import Path
import httpx,websocket


def executable():
    choices=[
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe']
    for name in choices:
        if name and Path(name).is_file():return name
    raise RuntimeError('A supported installed Chromium browser is required; none will be downloaded.')


class Browser:
    def __init__(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='ersel-offline-render-');self.profile=Path(self.temporary.name);self.sequence=0;self.events=[];self.socket=None
        self.log=(self.profile/'browser.log').open('wb')
        self.process=subprocess.Popen([executable(),'--headless=new','--disable-gpu','--disable-webgl','--disable-extensions',
            '--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check','--no-proxy-server',
            '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+str(self.profile),'about:blank'],
            stdout=self.log,stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            end=time.monotonic()+15;port_file=self.profile/'DevToolsActivePort'
            while not port_file.exists():
                if self.process.poll() is not None or time.monotonic()>end:raise RuntimeError('The isolated browser did not start its local test endpoint')
                time.sleep(.05)
            port=int(port_file.read_text().splitlines()[0]);assert 0<port<65536
            with httpx.Client(base_url='http://127.0.0.1:'+str(port),trust_env=False,timeout=10) as client:
                response=client.put('/json/new?about:blank');response.raise_for_status();url=response.json()['webSocketDebuggerUrl']
            if not url.startswith('ws://127.0.0.1:'+str(port)+'/devtools/page/'):raise RuntimeError('Invalid renderer target')
            self.socket=websocket.create_connection(url,timeout=10,suppress_origin=True)
            self.call('Page.enable');self.call('Runtime.enable');self.call('Log.enable')
            self.call('Network.enable')
            self.call('Network.setBlockedURLs',{'urls':['*']})
            self.call('Network.setBypassServiceWorker',{'bypass':True})
            self.call('Network.setCacheDisabled',{'cacheDisabled':True})
            self.call('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
            self.call('Emulation.setScriptExecutionDisabled',{'value':True})
            self.call('Browser.setDownloadBehavior',{'behavior':'deny'})
        except BaseException:self.close();raise

    def call(self,method,params=None):
        self.sequence+=1;identifier=self.sequence
        deadline=time.monotonic()+10
        self.socket.send(json.dumps({'id':identifier,'method':method,'params':params or {}}))
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise RuntimeError('Offline renderer operation timed out')
            self.socket.settimeout(remaining)
            raw=self.socket.recv()
            if not raw or len(raw)>4*1024*1024:raise RuntimeError('Invalid browser test response')
            message=json.loads(raw)
            if message.get('id')==identifier:
                if message.get('error'):raise RuntimeError(message['error'])
                return message.get('result',{})
            self.events.append(message)
            if len(self.events)>5000:raise RuntimeError('Browser event budget exceeded')

    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')

    def wait(self,expression,seconds=15):
        end=time.monotonic()+seconds
        while not self.evaluate(expression):
            if time.monotonic()>end:raise RuntimeError('Browser condition timed out: '+expression[:160])
            time.sleep(.05)

    def errors(self):
        self.evaluate('true')  # Drain queued browser events before inspection.
        return [event for event in self.events if event.get('method')=='Runtime.exceptionThrown' or
            (event.get('method')=='Log.entryAdded' and event['params']['entry'].get('level')=='error'
             and 'favicon' not in event['params']['entry'].get('url',''))]

    def close(self):
        if self.socket is not None:
            try:self.socket.send(json.dumps({'id':999999,'method':'Browser.close'}))
            except Exception:pass
            self.socket.close();self.socket=None
        if self.process.poll() is None:
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
        self.log.close()
        try:self.temporary.cleanup()
        except OSError:pass

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
