"""Small Python CDP test client over an isolated installed Chromium profile.

No Node, npm, Playwright, user browser profile or WebGL dependency.
"""
import base64,json,os,subprocess,tempfile,time
from pathlib import Path
import httpx,websocket


def executable():
    choices=[os.environ.get('ERSELMETZ_TEST_BROWSER',''),
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe']
    for name in choices:
        if name and Path(name).is_file():return name
    raise RuntimeError('An installed Chromium browser is required for the Python browser checks; none will be downloaded.')


class Browser:
    def __init__(self):
        self.profile=Path(tempfile.mkdtemp(prefix='ersel-headless-'));self.sequence=0;self.events=[];self.socket=None
        self.dialog_handler=None;self.fixtures={};self.control_sequence=1000000
        self.log=(self.profile/'browser.log').open('wb')
        self.process=subprocess.Popen([executable(),'--headless=new','--disable-gpu','--disable-webgl','--disable-extensions',
            '--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check',
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
            self.socket=websocket.create_connection(url,timeout=10,suppress_origin=True)
            self.call('Page.enable');self.call('Runtime.enable');self.call('Log.enable')
        except BaseException:self.close();raise

    def call(self,method,params=None):
        self.sequence+=1;identifier=self.sequence
        self.socket.send(json.dumps({'id':identifier,'method':method,'params':params or {}}))
        while True:
            raw=self.socket.recv()
            if not raw or len(raw)>4*1024*1024:raise RuntimeError('Invalid browser test response')
            message=json.loads(raw)
            if message.get('method')=='Page.javascriptDialogOpening' and self.dialog_handler is not None:
                accepted=self.dialog_handler(message['params']['message'])
                self.control_sequence+=1
                self.socket.send(json.dumps({'id':self.control_sequence,'method':'Page.handleJavaScriptDialog','params':{'accept':bool(accepted)}}))
            if message.get('method')=='Fetch.requestPaused':
                params=message['params'];fixture=self.fixtures.get(params['request']['url'])
                self.control_sequence+=1
                command={'id':self.control_sequence,'method':'Fetch.failRequest','params':{'requestId':params['requestId'],'errorReason':'BlockedByClient'}}
                if fixture is not None:
                    command.update(method='Fetch.fulfillRequest',params={'requestId':params['requestId'],'responseCode':200,
                        'responseHeaders':[{'name':'Content-Type','value':'application/json'}],
                        'body':base64.b64encode(json.dumps(fixture).encode()).decode()})
                self.socket.send(json.dumps(command))
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

    def navigate(self,url):
        self.events=[];result=self.call('Page.navigate',{'url':url})
        if result.get('errorText'):raise RuntimeError(result['errorText'])
        loader=result.get('loaderId');deadline=time.monotonic()+15
        while loader and self.call('Page.getFrameTree')['frameTree']['frame'].get('loaderId')!=loader:
            if time.monotonic()>deadline:raise RuntimeError('Browser navigation did not commit')
            time.sleep(.025)
        self.wait('document.readyState === "complete"')

    def stub_json(self,url,value):
        self.fixtures[url]=value
        self.call('Fetch.enable',{'patterns':[{'urlPattern':target,'requestStage':'Request'} for target in self.fixtures]})

    def viewport(self,width,height):
        self.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})

    def fill(self,selector,value):
        self.wait('document.readyState === "complete" && document.querySelector('+json.dumps(selector)+') !== null')
        self.evaluate('(()=>{const element=document.querySelector('+json.dumps(selector)+');element.focus();element.value='+json.dumps(value)+';element.dispatchEvent(new Event("input",{bubbles:true}));})()')

    def click(self,selector):
        self.wait('document.readyState === "complete" && document.querySelector('+json.dumps(selector)+') !== null')
        self.evaluate('document.querySelector('+json.dumps(selector)+').click()')

    def enter(self,selector):
        self.evaluate('document.querySelector('+json.dumps(selector)+').focus()')
        for kind in ['keyDown','keyUp']:
            self.call('Input.dispatchKeyEvent',{'type':kind,'key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'nativeVirtualKeyCode':13})

    def screenshot(self,path):
        metrics=self.call('Page.getLayoutMetrics')['cssContentSize']
        result=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,
            'clip':{'x':0,'y':0,'width':metrics['width'],'height':metrics['height'],'scale':1}})
        Path(path).write_bytes(base64.b64decode(result['data']))

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

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
