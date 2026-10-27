from fastapi.testclient import TestClient
from app.local import create_local_app


def test_capture_api_requires_native_scope_exact_consent_and_releases_after_stop():
    app=create_local_app(password='native-capture-test-password')
    with TestClient(app,base_url='http://127.0.0.1:8000',client=('127.0.0.1',50997)) as client:
        origin={'Origin':'http://127.0.0.1:8000'}
        assert client.post('/api/native/capture',headers=origin,json={'kind':'screen','target':'Test display'}).status_code==401
        client.post('/api/local/login',headers=origin,json={'password':'native-capture-test-password'})
        headers={**origin,'X-Local-CSRF':client.get('/api/local/session').json()['csrf']}
        body={'kind':'screen','target':'Test display metadata; no device adapter is invoked'}
        assert client.post('/api/native/capture',headers=headers,json=body).status_code==400
        wid=client.post('/api/native/windows',headers=headers,json={}).json()['id']
        scoped={**headers,'X-Native-Window':wid,'X-Native-Generation':'0'}
        review=client.post('/api/native/capture',headers=scoped,json=body)
        assert review.status_code==200,review.text
        review=review.json();path='/api/native/capture/'+review['id']
        assert client.get('/api/native/windows',headers=headers).json()['capture']==[]
        assert client.post(path+'/begin',headers=scoped,json={'confirmed_digest':'0'*64}).status_code==403
        assert client.post(path+'/begin',headers=scoped,json={'confirmed_digest':review['approval_digest']}).status_code==200
        assert client.request('DELETE','/api/native/windows/'+wid,headers=headers,json={}).status_code==409
        assert client.post('/api/native/windows/'+wid+'/stop',headers=headers,json={}).status_code==200
        assert client.get(path,headers=scoped).json()['cancelled'] is True
        assert len(client.get('/api/native/windows',headers=headers).json()['capture'])==1
        result=client.post(path+'/finish',headers=scoped,json={})
        assert result.status_code==200 and result.json()['cancelled_before_finish'] is True
        assert client.get('/api/native/windows',headers=headers).json()['capture']==[]
        assert client.request('DELETE','/api/native/windows/'+wid,headers=headers,json={}).status_code==200
