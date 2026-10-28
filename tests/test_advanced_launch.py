"""Retired ticket flow must remain absent; no credential handoff to browsers."""
from fastapi.testclient import TestClient
from app.local import create_local_app

def test_browser_launch_token_routes_removed(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    app=create_local_app(password='a safe local password',origin='http://127.0.0.1:8000')
    with TestClient(app,base_url='http://127.0.0.1:8000',client=('127.0.0.1',50000)) as client:
        client.post('/api/local/login',json={'password':'a safe local password'},headers={'Origin':'http://127.0.0.1:8000'})
        csrf=client.get('/api/local/session').json()['csrf']
        assert client.post('/api/local/advanced-launch',json={'page':'Employees'},headers={'Origin':'http://127.0.0.1:8000','X-Local-CSRF':csrf}).status_code==404
        assert client.get('/local/advanced-launch?token=anything').status_code==404
