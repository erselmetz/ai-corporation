import pytest
from fastapi.testclient import TestClient
from app.local import create_local_app


def test_native_window_generation_rejects_pre_stop_requests_after_resume():
    app=create_local_app(password='native-window-test-password')
    with TestClient(app,base_url='http://127.0.0.1:8000',client=('127.0.0.1',50994)) as client:
        assert client.get('/api/native/windows').status_code==401
        origin={'Origin':'http://127.0.0.1:8000'}
        client.post('/api/local/login',headers=origin,json={'password':'native-window-test-password'})
        headers={**origin,'X-Local-CSRF':client.get('/api/local/session').json()['csrf']}
        registered=client.post('/api/native/windows',headers=headers,json={}).json()
        identifier=registered['id'];scoped={**headers,'X-Native-Window':identifier,'X-Native-Generation':'0'}
        response=client.post('/api/chat/conversations',headers=scoped,json={'agent_id':'local_worker'})
        assert response.status_code==200,response.text
        cid=response.json()['conversation']['id'];path=f'/api/chat/conversations/{cid}/messages'
        body={'text':'Hi!','shipped_pack_enabled':True}
        assert client.post('/api/native/windows/'+identifier+'/stop',headers=headers,json={}).status_code==200
        assert client.post(path,headers=scoped,json=body).status_code==423
        resumed=client.post('/api/native/windows/'+identifier+'/resume',headers=headers,json={'confirmed':True}).json()
        assert resumed['generation']==1
        assert client.post(path,headers=scoped,json=body).status_code==409
        scoped['X-Native-Generation']='1'
        reply=client.post(path,headers=scoped,json=body)
        assert reply.status_code==200 and reply.json()['context_trace']['provider_called'] is False
        assert client.post('/api/local/emergency-stop/stop',headers=headers,json={}).status_code==200
        assert client.post('/api/local/emergency-stop/resume',headers=headers,json={'confirmed':True}).status_code==200
        assert client.post(path,headers=scoped,json=body).status_code==409
        scoped['X-Native-Generation']='2'
        assert client.post(path,headers=scoped,json=body).status_code==200
        record=client.get('/api/chat/conversations/'+cid,headers=scoped).json()['conversation']
        assert len(record['messages'])==4  # Only the two explicitly NEW requests.
        assert client.request('DELETE','/api/native/windows/'+identifier,headers=headers,json={}).status_code==200
        assert client.get('/api/native/windows',headers=headers).json()['windows']==[]
