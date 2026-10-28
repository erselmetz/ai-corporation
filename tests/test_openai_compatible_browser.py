"""Actual browser/settings/preview journey with a fake loopback upstream only."""
import json,socket
from threading import Event,Thread
import uvicorn
from tools.headless_browser import Browser
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime
from test_openai_compatible import endpoint,KEY
from test_owned_chat import InstalledLocalProvider


def test_free_pool_setup_test_and_explicit_chat_preview_in_real_browser(endpoint,tmp_path):
    url,state=endpoint;runtime=create_corporation_runtime();runtime.providers.remove('ollama');runtime.providers.register('ollama',InstalledLocalProvider())
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(5);origin='http://127.0.0.1:'+str(listener.getsockname()[1])
    app=create_local_app(password='test-browser-password',origin=origin,application_service=runtime.application_service)
    started=Event()
    class Server(uvicorn.Server):
        async def startup(self,sockets=None):await super().startup(sockets=sockets);started.set()
    server=Server(uvicorn.Config(app,log_level='error',proxy_headers=False));thread=Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        assert started.wait(10)
        with Browser() as browser:
            allowed=[]
            def approve(message):
                assert any(text in message for text in ['Test sends the fixed text Hi','Apply these cloud settings','Review this chat plan before work begins']),message
                allowed.append(message);return True
            browser.dialog_handler=approve;browser.viewport(1280,1000)
            browser.navigate(origin+'/ui/login');browser.fill('#password','test-browser-password');browser.click('#local-login button[type="submit"]');browser.wait('location.pathname === "/ui"')
            browser.navigate(origin+'/ui/provider-connections#free-pool')
            browser.wait('document.querySelector("#connection-type").value === "free-pool" && !document.querySelector("#connection-add").disabled')
            assert browser.evaluate('document.querySelector("#connection-url").value')=='http://127.0.0.1:3001/v1'
            assert browser.evaluate('!document.querySelector("#endpoint-enabled").checked && !document.querySelector("#endpoint-brain").checked')
            browser.fill('#connection-url',url);browser.fill('#connection-key',KEY);browser.click('#connection-add')
            browser.wait('document.querySelector("#connection-list").textContent.includes("compatible-free-pool") && !document.querySelector("#endpoint-test").disabled')
            assert state['calls']==[] and browser.evaluate('document.querySelector("#connection-key").value')==''
            browser.click('#endpoint-test');browser.wait('document.querySelector("#connection-state").textContent.startsWith("Reachable")')
            assert state['calls'][-1][2]['model']=='auto' and state['calls'][-1][2]['max_tokens']==1
            browser.click('#endpoint-enabled');browser.click('#endpoint-save');browser.wait('document.querySelector("#connection-state").textContent.includes("settings saved")')
            browser.screenshot(tmp_path/'endpoint-setup.png')
            browser.navigate(origin+'/ui/chat?desktop=1');browser.wait('document.querySelector("#chat-input").disabled === false')
            browser.fill('#chat-input','Explain amber')
            browser.click('#chat-route-check');browser.wait('document.querySelector("#chat-route-select").options.length > 1 && !document.querySelector("#chat-route-select").disabled')
            browser.evaluate('(()=>{const select=document.querySelector("#chat-route-select");select.value=[...select.options].find(option=>option.value.includes("compatible-free-pool")).value;select.dispatchEvent(new Event("change",{bubbles:true}));})()')
            browser.click('#cloud-consent');before=len([c for c in state['calls'] if c[0]=='POST'])
            browser.enter('#chat-input')
            browser.wait("document.querySelector("+json.dumps('[aria-label="Exact outbound cloud preview"]')+") !== null")
            assert len([c for c in state['calls'] if c[0]=='POST'])==before
            assert browser.evaluate("document.querySelector("+json.dumps('[aria-label="Redacted outbound messages"]')+').value.includes("Explain amber")')
            assert browser.evaluate("document.querySelector("+json.dumps('[aria-label="Redacted outbound messages"]')+').getBoundingClientRect().width > 600')
            assert browser.evaluate('document.querySelector("#chat-state").textContent.includes("No cloud generation")')
            browser.screenshot(tmp_path/'endpoint-preview.png')
            browser.evaluate('[...document.querySelectorAll("button")].find(button=>button.textContent === "Approve this cloud turn").click()')
            browser.wait('document.querySelector("#chat-history").textContent.includes("Safe answer")')
            assert len([c for c in state['calls'] if c[0]=='POST'])==before+1
            assert browser.evaluate('document.querySelector("#chat-history").textContent.includes("Router-reported: fixture / actual-model")')
            assert runtime.application_service.get_agent('local_worker').provider=='ollama'
            browser.wait('document.querySelector("#chat-input").disabled === false')
            browser.click('.chat-answer-trace summary')
            browser.screenshot(tmp_path/'endpoint-answer.png')
            errors=browser.errors()
            # The deliberate 409 is the read-only preview negotiation, already
            # asserted above; Chrome logs this HTTP status as a network entry.
            expected=[error for error in errors if error.get('method')=='Log.entryAdded'
                      and error['params']['entry'].get('source')=='network'
                      and '409' in error['params']['entry'].get('text','')
                      and error['params']['entry'].get('url','').startswith(origin+'/api/chat/conversations/')
                      and error['params']['entry'].get('url','').endswith('/messages')]
            assert len(expected)==1 and errors==expected,errors
    finally:
        server.should_exit=True;thread.join(timeout=10);listener.close();assert not thread.is_alive()
