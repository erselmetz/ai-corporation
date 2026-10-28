import asyncio,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from app.integrations.openai_compatible import OpenAICompatibleProvider,EndpointError,approved_turn,endpoint_url,last_receipt

KEY='sk-fixture-'+ 'a'*24
MESSAGES=[{'role':'system','content':'You are a test assistant.'},{'role':'user','content':'Explain amber'}]


@pytest.fixture
def endpoint():
    state={'status':200,'models':['pool-model'],'header':'fixture/actual-model','tools':False,'stream':False,'calls':[],'answer':'Safe answer'}
    class Handler(BaseHTTPRequestHandler):
        def _write(self,data):
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            state['calls'].append(('GET',self.path,None))
            self.send_response(state['status']);self.send_header('Content-Type','application/json');self.end_headers()
            self._write(json.dumps({'data':[{'id':m} for m in state['models']]}).encode())
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));state['calls'].append(('POST',self.path,body))
            if state.get('observe'):state['observe']()
            self.send_response(state['status']);self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json')
            if state['header']:self.send_header('X-Routed-Via',state['header'])
            self.end_headers()
            if body.get('stream'):
                for part in [state['answer'][:8],state['answer'][8:]]:
                    delta={'tool_calls':[{'id':'unsafe'}]} if state['tools'] else {'content':part}
                    self._write(('data: '+json.dumps({'choices':[{'delta':delta}]})+'\n\n').encode())
                self._write(b'data: [DONE]\n\n')
            else:
                message={'content':state['answer']}
                if state['tools']:message['tool_calls']=[{'function':{'name':'open_url','arguments':'{}'}}]
                self._write(json.dumps({'choices':[{'message':message}]}).encode())
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)+'/v1',state
    finally:server.shutdown();server.server_close();worker.join(timeout=5)


def configured(endpoint):
    url,state=endpoint;p=OpenAICompatibleProvider(url,KEY,enabled=True);p.list_models();return p,state


def test_default_off_no_network_and_no_secret_repr(endpoint):
    url,state=endpoint;p=OpenAICompatibleProvider(url,KEY)
    assert not p.enabled and not p.allow_brain_context and p.is_local is False
    assert state['calls']==[] and KEY not in repr(p) and KEY not in json.dumps(p.settings())
    with pytest.raises(EndpointError,match='off'):p.preview_outbound('pool-model',MESSAGES)
    with pytest.raises(EndpointError):p.test_connection()
    assert state['calls']==[]


@pytest.mark.parametrize('url',['http://example.org/v1','https://example.org/v1','http://user:pass@127.0.0.1/v1','http://127.0.0.1/v1?key=x','http://127.0.0.1\\@example.org/v1','file:///v1','http://127.0.0.1:0/v1'])
def test_loopback_and_parser_rules(url):
    with pytest.raises(EndpointError):endpoint_url(url)


def test_confirmed_https_only_for_remote():
    assert endpoint_url('https://example.org/v1',remote_confirmed=True)=='https://example.org/v1'
    with pytest.raises(EndpointError):endpoint_url('http://example.org/v1',remote_confirmed=True)
    assert endpoint_url('http://[::1]:3001/v1')


def test_preview_redaction_consent_and_exact_model_binding(endpoint):
    p,state=configured(endpoint);messages=[MESSAGES[0],{'role':'user','content':'api_key='+KEY+' password=hunter2'}]
    preview=p.preview_outbound('pool-model',messages)
    assert KEY not in json.dumps(preview) and 'hunter2' not in json.dumps(preview)
    before=len(state['calls'])
    with pytest.raises(EndpointError):p.generate_chat('pool-model',messages)
    with approved_turn(True,'0'*64),pytest.raises(EndpointError):p.generate_chat('pool-model',messages)
    assert len(state['calls'])==before
    with approved_turn(True,preview['digest']):
        assert p.generate_chat('pool-model',messages)=='Safe answer'
        receipt=last_receipt();assert receipt['served_provider']=='fixture' and receipt['served_model']=='actual-model' and receipt['retries']==0
    assert KEY not in json.dumps(state['calls'][-1][2]) and 'hunter2' not in json.dumps(state['calls'][-1][2])


def test_streaming_sanitizes_split_secret_and_missing_header_is_unknown(endpoint):
    p,state=configured(endpoint);state['answer']='Echo '+KEY;state['header']=None
    preview=p.preview_outbound('pool-model',MESSAGES)
    with approved_turn(True,preview['digest']):
        result=''.join(p.generate_chat_stream('pool-model',MESSAGES))
        assert KEY not in result and '[REDACTED]' in result
        assert last_receipt()['served_model'] is None


@pytest.mark.parametrize('status,label',[(401,'Key rejected'),(429,'Reachable'),(503,'Reachable')])
def test_friendly_failures_no_retries(endpoint,status,label):
    url,state=endpoint;state['status']=status;p=OpenAICompatibleProvider(url,KEY)
    result=p.test_connection(consent=True)
    assert result['state_label']==label and not result['chat_test']
    assert len(state['calls'])==1 and KEY not in json.dumps(result)


def test_empty_models_do_not_generate(endpoint):
    url,state=endpoint;state['models']=[];p=OpenAICompatibleProvider(url,KEY)
    assert p.test_connection(consent=True)['state_label']=='No models'
    assert not any(call[0]=='POST' for call in state['calls'])


@pytest.mark.parametrize('stream',[False,True])
def test_tool_proposals_never_execute(endpoint,stream):
    p,state=configured(endpoint);state['tools']=True;preview=p.preview_outbound('pool-model',MESSAGES)
    with approved_turn(True,preview['digest']),pytest.raises(EndpointError,match='tool'):
        list(p.generate_chat_stream('pool-model',MESSAGES)) if stream else p.generate_chat('pool-model',MESSAGES)
    assert len([c for c in state['calls'] if c[0]=='POST'])==1


def test_fixed_test_and_bounded_calls(endpoint):
    url,state=endpoint;p=OpenAICompatibleProvider(url,KEY)
    assert p.test_connection(consent=True)['chat_test']
    assert state['calls'][-1][2]['messages']==[{'role':'user','content':'Hi'}] and state['calls'][-1][2]['max_tokens']==1
    p.configure(True,False);preview=p.preview_outbound('pool-model',MESSAGES)
    with approved_turn(True,preview['digest']):
        for _ in range(4):p.generate_chat('pool-model',MESSAGES)
        with pytest.raises(EndpointError,match='allowance'):p.generate_chat('pool-model',MESSAGES)
    assert len([c for c in state['calls'] if c[0]=='POST'])==5


def test_brain_opt_in_and_prompt_limit(endpoint):
    p,state=configured(endpoint)
    with pytest.raises(EndpointError,match='Brain'):p.preview_outbound('pool-model',MESSAGES,brain=True)
    p.configure(True,True);assert p.preview_outbound('pool-model',MESSAGES,brain=True)
    with pytest.raises((ValueError,EndpointError)):p.preview_outbound('pool-model',[{'role':'user','content':'x'*32768}])


def test_async_adapters_preserve_approval_context(endpoint):
    p,state=configured(endpoint);preview=p.preview_outbound('pool-model',MESSAGES)
    async def run():
        with approved_turn(True,preview['digest']):
            assert await p.agenerate_chat('pool-model',MESSAGES)=='Safe answer'
            assert ''.join([c async for c in p.agenerate_chat_stream('pool-model',MESSAGES)])=='Safe answer'
    asyncio.run(run())


def test_owned_chat_preview_is_read_only_and_approval_binds_actual_history(endpoint):
    from test_owned_chat import InstalledLocalProvider,client_for,start
    from app.runtime.factory import create_corporation_runtime
    from app.application.services.provider_connections import ProviderConnectionsService
    url,state=endpoint;runtime=create_corporation_runtime();runtime.providers.remove('ollama');runtime.providers.register('ollama',InstalledLocalProvider())
    service=ProviderConnectionsService(runtime.application_service)
    item=service.add_compatible('pool','Pool',url,KEY,enabled=True)
    provider_id=item['provider_id'];assert item['models']==[] and state['calls']==[]
    service.test_compatible(provider_id,consent=True)
    with client_for(runtime) as client:
        client.app.state.provider_connections_service=service
        identifier=start(client).json()['conversation']['id'];headers={'x-test-owner':'alice'}
        path=f'/api/chat/conversations/{identifier}/messages'
        body={'text':'Explain amber '+KEY,'route_provider_id':provider_id,'route_model_id':'pool-model','route_consent':True}
        denied=client.post(path,json=body,headers=headers);assert denied.status_code==403,denied.text
        before=len(state['calls'])
        preview=client.post(path,json={**body,'outbound_preview':True},headers=headers)
        assert preview.status_code==409,preview.text
        detail=preview.json()['detail'];assert detail['kind']=='outbound_preview' and KEY not in preview.text
        assert len(state['calls'])==before
        record=client.get(f'/api/chat/conversations/{identifier}',headers=headers).json()
        assert record['conversation']['messages']==[]
        stale=client.post(path,json={**body,'text':'Different prompt','cloud_consent':True,'outbound_digest':detail['digest']},headers=headers)
        assert stale.status_code==409 and len(state['calls'])==before
        answer=client.post(path,json={**body,'cloud_consent':True,'outbound_digest':detail['digest']},headers=headers)
        assert answer.status_code==200,answer.text
        assert len(state['calls'])==before+1
        trace=answer.json()['context_trace'];assert trace['endpoint']['served_model']=='actual-model'
        assert trace['route']['requested_model']=='pool-model' and trace['route']['model']=='actual-model'
        assert runtime.application_service.get_agent('local_worker').provider=='ollama'


def test_assigned_endpoint_stream_uses_same_preview_and_reports_unknown_identity(endpoint):
    from test_owned_chat import InstalledLocalProvider,client_for,start
    from app.runtime.factory import create_corporation_runtime
    from app.application.services.provider_connections import ProviderConnectionsService
    url,state=endpoint;state['header']=None
    runtime=create_corporation_runtime();runtime.providers.remove('ollama');runtime.providers.register('ollama',InstalledLocalProvider())
    service=ProviderConnectionsService(runtime.application_service)
    provider_id=service.add_compatible('stream','Stream',url,KEY,enabled=True)['provider_id']
    service.test_compatible(provider_id,consent=True)
    service.assign('local_worker',provider_id,'pool-model','ollama','llama3.2:3b')
    with client_for(runtime) as client:
        client.app.state.provider_connections_service=service;identifier=start(client).json()['conversation']['id'];headers={'x-test-owner':'alice'}
        path=f'/api/chat/conversations/{identifier}/messages';body={'text':'Explain amber'}
        preview=client.post(path,json={**body,'outbound_preview':True},headers=headers)
        assert preview.status_code==409,preview.text
        denied=client.post(path+'/stream',json={**body,'outbound_preview':True,'cloud_consent':True},headers=headers)
        assert denied.status_code==422
        response=client.post(path+'/stream',json={**body,'cloud_consent':True,'outbound_digest':preview.json()['detail']['digest']},headers=headers)
        assert response.status_code==200
        events=[json.loads(line) for line in response.text.splitlines()]
        assert ''.join(e.get('text','') for e in events)=='Safe answer',events
        trace=next(e['context_trace'] for e in events if e['type']=='complete')
        assert trace['endpoint']['served_model'] is None and trace['route']['model'] is None
        assert trace['route']['requested_model']=='pool-model'


def test_endpoint_management_requires_owner_permission_csrf_and_test_consent(endpoint):
    from fastapi.testclient import TestClient
    from app.local import create_local_app
    from app.runtime.factory import create_corporation_runtime
    from test_provider_connections import sign_in,ORIGIN,PASSWORD
    url,state=endpoint;runtime=create_corporation_runtime();app=create_local_app(password=PASSWORD,application_service=runtime.application_service)
    body={'id':'pool','name':'Free pool','base_url':url,'api_key':KEY}
    path='/api/local/provider-connections'
    with TestClient(app,base_url=ORIGIN,client=('127.0.0.1',50000)) as client:
        assert client.get(path).status_code==401
        assert client.post(path+'/openai-compatible',json=body).status_code==403
        headers=sign_in(client)
        created=client.post(path+'/openai-compatible',json=body,headers=headers)
        assert created.status_code==201,created.text
        assert KEY not in created.text and not created.json()['endpoint']['enabled'] and state['calls']==[]
        provider=created.json()['provider_id']
        assert client.post(path+'/'+provider+'/test',json={'consent':True},headers={'Origin':ORIGIN}).status_code==403
        denied=client.post(path+'/'+provider+'/test',json={'consent':False},headers=headers)
        assert denied.status_code==422 and state['calls']==[]
        result=client.post(path+'/'+provider+'/test',json={'consent':True},headers=headers)
        assert result.status_code==200 and result.json()['test']['chat_test']
        assert KEY not in result.text
        result=client.patch(path+'/'+provider+'/privacy',json={'enabled':True,'allow_brain_context':False},headers=headers)
        assert result.status_code==200 and result.json()['endpoint']['enabled']
        from app.api.security import AuthenticatedPrincipal
        client.app.state.authentication_backend.principal=AuthenticatedPrincipal('local-owner',frozenset({'provider-connection:read'}))
        assert client.patch(path+'/'+provider+'/privacy',json={'enabled':False},headers=headers).status_code==403


def test_timeout_error_is_safe_and_not_retried():
    import httpx
    calls=[]
    def fail(request):calls.append(request);raise httpx.ReadTimeout('secret '+KEY,request=request)
    provider=OpenAICompatibleProvider('http://127.0.0.1:3001/v1',KEY,transport=httpx.MockTransport(fail))
    result=provider.test_connection(consent=True)
    assert result['state_label']=='Not reachable' and KEY not in json.dumps(result) and len(calls)==1


def test_native_style_local_workspace_keeps_its_selection_after_cloud_escalation(endpoint):
    from test_owned_chat import InstalledLocalProvider,client_for
    from app.runtime.factory import create_corporation_runtime
    from app.application.services.provider_connections import ProviderConnectionsService
    url,state=endpoint;runtime=create_corporation_runtime();runtime.providers.remove('ollama');runtime.providers.register('ollama',InstalledLocalProvider())
    service=ProviderConnectionsService(runtime.application_service);pid=service.add_compatible('pool','Pool',url,KEY,enabled=True)['provider_id'];service.test_compatible(pid,consent=True)
    with client_for(runtime) as client:
        client.app.state.provider_connections_service=service;headers={'x-test-owner':'alice','X-Chat-Workspace':'d'*32}
        opened=client.post('/api/chat/workspaces',json={'id':'d'*32,'agent_id':'local_worker','provider_id':'ollama','model_id':'llama3.2:3b'},headers={'x-test-owner':'alice'})
        assert opened.status_code==200,opened.text
        started=client.post('/api/chat/conversations',json={'agent_id':'local_worker'},headers=headers)
        assert started.status_code==200,started.text
        cid=started.json()['conversation']['id'];path=f'/api/chat/conversations/{cid}/messages'
        body={'text':'Explain amber','route_provider_id':pid,'route_model_id':'pool-model','route_consent':True}
        preview=client.post(path,json={**body,'outbound_preview':True},headers=headers)
        assert preview.status_code==409,preview.text
        reply=client.post(path,json={**body,'cloud_consent':True,'outbound_digest':preview.json()['detail']['digest']},headers=headers)
        assert reply.status_code==200,reply.text
        assert reply.json()['workspace']['provider_id']=='ollama'
        assert reply.json()['context_trace']['route']['provider']==pid
        assert runtime.application_service.get_agent('local_worker').provider=='ollama'


def test_brain_markers_cannot_bypass_provider_toggle_and_redirects_never_forward_key(endpoint):
    p,state=configured(endpoint)
    messages=[MESSAGES[0],{'role':'user','content':'--- BEGIN UNTRUSTED RETRIEVED KNOWLEDGE ---\nprivate fact'}]
    with pytest.raises(EndpointError,match='Brain'):p.preview_outbound('pool-model',messages)
    import httpx
    calls=[]
    def redirect(request):calls.append(str(request.url));return httpx.Response(307,headers={'Location':'https://example.org/steal'})
    p=OpenAICompatibleProvider('http://127.0.0.1:3001/v1',KEY,transport=httpx.MockTransport(redirect))
    result=p.test_connection(consent=True)
    assert not result['chat_test'] and len(calls)==1 and all('example.org' not in call for call in calls)


@pytest.mark.parametrize('status,message',[(401,'rejected the key'),(429,'rate limited'),(503,'temporarily unavailable')])
def test_chat_endpoint_preserves_friendly_errors_and_never_retries_or_falls_back(endpoint,status,message):
    from test_owned_chat import InstalledLocalProvider,client_for,start
    from app.runtime.factory import create_corporation_runtime
    from app.application.services.provider_connections import ProviderConnectionsService
    url,state=endpoint;runtime=create_corporation_runtime();local=InstalledLocalProvider();runtime.providers.remove('ollama');runtime.providers.register('ollama',local)
    service=ProviderConnectionsService(runtime.application_service);pid=service.add_compatible('pool','Pool',url,KEY,enabled=True)['provider_id'];service.test_compatible(pid,consent=True)
    with client_for(runtime) as client:
        client.app.state.provider_connections_service=service;cid=start(client).json()['conversation']['id'];headers={'x-test-owner':'alice'}
        path=f'/api/chat/conversations/{cid}/messages';body={'text':'Explain amber','route_provider_id':pid,'route_model_id':'pool-model','route_consent':True}
        preview=client.post(path,json={**body,'outbound_preview':True},headers=headers);assert preview.status_code==409
        state['status']=status;before=len(state['calls'])
        response=client.post(path,json={**body,'cloud_consent':True,'outbound_digest':preview.json()['detail']['digest']},headers=headers)
        assert response.status_code==422,response.text
        assert message in response.json()['detail']['message'] and KEY not in response.text
        assert len(state['calls'])==before+1 and local.calls==[]


def test_stopped_request_cannot_test_send_or_consume_a_cloud_allowance(endpoint):
    from app.resources.context import request_stop
    from app.application.services.native_runtime import NativeRuntimeStopped
    p,state=configured(endpoint);preview=p.preview_outbound('pool-model',MESSAGES);before=len(state['calls'])
    stopped=threading.Event();stopped.set();token=request_stop.set(stopped)
    try:
        with approved_turn(True,preview['digest']),pytest.raises(NativeRuntimeStopped):p.generate_chat('pool-model',MESSAGES)
        with pytest.raises(NativeRuntimeStopped):p.test_connection(consent=True)
    finally:request_stop.reset(token)
    assert len(state['calls'])==before and p.settings()['calls_used']==0


def test_settings_test_generation_uses_shared_resource_admission(endpoint):
    from app.runtime.factory import create_corporation_runtime
    from app.application.services.provider_connections import ProviderConnectionsService
    from app.application.services.owned_chat import ChatLimit
    url,state=endpoint;runtime=create_corporation_runtime();service=ProviderConnectionsService(runtime.application_service)
    pid=service.add_compatible('pool','Pool',url,KEY)['provider_id']
    resources=runtime.application_service.configure_agent_slots()
    assignment=runtime.application_service.get_agent('local_worker')
    resources.allocate('occupied',provider_id=assignment.provider,model_id=assignment.model)
    try:
        with pytest.raises(ChatLimit):service.test_compatible(pid,consent=True)
        assert not any(call[0]=='POST' for call in state['calls'])
        assert service.get(pid)['endpoint']['calls_used']==0
    finally:resources.release('occupied')
    seen=[];state['observe']=lambda:seen.append([(item.provider_id,item.model_id) for item in resources.snapshot().allocations])
    assert service.test_compatible(pid,consent=True)['test']['chat_test']
    assert seen==[[(pid,'pool-model')]] and resources.snapshot().allocations==()


def test_generic_test_uses_owner_selected_model_instead_of_always_first(endpoint):
    url,state=endpoint;state['models']=['other-model','pool-model'];p=OpenAICompatibleProvider(url,KEY)
    assert p.test_connection(consent=True,model_id='pool-model')['chat_test']
    assert state['calls'][-1][2]['model']=='pool-model' and p.settings()['default_model']=='pool-model'
    before=len([c for c in state['calls'] if c[0]=='POST'])
    result=p.test_connection(consent=True,model_id='missing-model')
    assert not result['chat_test'] and len([c for c in state['calls'] if c[0]=='POST'])==before


@pytest.mark.parametrize('value',['GROQ_API_KEY=gsk_'+ 'a'*24,'{"MY_API_KEY":"other_sensitive_value"}','hf_'+ 'b'*24,'xoxb-'+ 'c'*24,'AKIA'+'D'*16,'-----BEGIN PRIVATE KEY-----\nprivate_body\n-----END PRIVATE KEY-----','-----BEGIN RSA PRIVATE KEY-----\ntruncated_private_body'])
def test_obvious_config_tokens_and_private_key_blocks_are_redacted(value):
    from app.integrations.openai_compatible import redact
    result=redact(value)
    assert '[REDACTED' in result
    for fragment in ['private_body','truncated_private_body','other_sensitive_value','a'*24,'b'*24,'c'*24,'D'*16]:assert fragment not in result


def test_empty_one_token_probe_is_reachable_but_empty_user_answer_still_fails(endpoint):
    url,state=endpoint;state['answer']='';p=OpenAICompatibleProvider(url,KEY)
    assert p.test_connection(consent=True)['chat_test'] and p.state=='Reachable'
    p.configure(True,False);preview=p.preview_outbound('pool-model',MESSAGES)
    with approved_turn(True,preview['digest']),pytest.raises(EndpointError,match='no bounded text'):p.generate_chat('pool-model',MESSAGES)
