"""A real loopback fake Gemini server; no real credential or paid provider call."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,threading
import pytest
from fastapi.testclient import TestClient
from test_local_online_provider import KEY,MODEL,ORIGIN,PASSWORD,login,patch_catalog
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime


@pytest.mark.parametrize('provider_status',[200,503])
def test_cloud_consent_role_payload_and_failure_no_retry_over_tcp(monkeypatch,provider_status):
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            length=int(self.headers['Content-Length']);assert length<=32768
            body=json.loads(self.rfile.read(length));calls.append((self.path,self.headers.get('x-goog-api-key'),body))
            payload=json.dumps({'candidates':[{'content':{'parts':[{'text':'Deterministic fake TCP reply.'}]}}]}).encode()
            self.send_response(provider_status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)))
            self.end_headers();self.wfile.write(payload)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    # The fixed production HTTPS destination remains unchanged outside this test.
    monkeypatch.setattr('app.integrations.gemini_chat._ENDPOINT','http://127.0.0.1:'+str(server.server_port)+'/v1beta/models')
    patch_catalog(monkeypatch);runtime=create_corporation_runtime();service=runtime.application_service
    original=service.get_model_assignment('local_worker')
    try:
        with TestClient(create_local_app(password=PASSWORD,application_service=service),base_url=ORIGIN,client=('127.0.0.1',50000)) as client:
            headers=login(client)
            assert client.post('/api/local/online-provider/catalog',headers=headers,json={'api_key':KEY}).status_code==200
            connected=client.put('/api/local/online-provider/connection',headers=headers,json={'agent_id':'local_worker','model_id':MODEL,
                'expected_provider_id':original.provider_id,'expected_model_id':original.model_id})
            assert connected.status_code==200,connected.text
            conversation=client.post('/api/chat/conversations',headers=headers,json={'agent_id':'local_worker'}).json()['conversation']['id']
            path='/api/chat/conversations/'+conversation+'/messages'
            denied=client.post(path,headers=headers,json={'text':'A private test question'})
            assert denied.status_code==403 and calls==[]
            result=client.post(path,headers=headers,json={'text':'A private test question','cloud_consent':True})
            assert result.status_code==(200 if provider_status==200 else 502),result.text
            assert len(calls)==1 and calls[0][0]=='/v1beta/models/'+MODEL+':generateContent'
            assert calls[0][1]==KEY and KEY not in calls[0][0] and KEY not in result.text
            payload=calls[0][2]
            assert payload['contents'][-1]=={'role':'user','parts':[{'text':'A private test question'}]}
            assert 'systemInstruction' in payload and payload['generationConfig']['maxOutputTokens']<=1024
            assert 'corporation_id' not in payload and 'request' not in payload
            assert service.get_model_assignment('local_worker').provider_id=='gemini'
            assert service.resource_manager().snapshot().global_capacity.allocated==0
            if provider_status==200:
                record=client.get('/api/chat/conversations/'+conversation,headers=headers).json()['conversation']
                assert [m['content'] for m in record['messages']]==['A private test question','Deterministic fake TCP reply.']
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
