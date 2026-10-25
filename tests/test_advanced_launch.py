import pytest
from fastapi.testclient import TestClient
from app.local import create_local_app
from app.api.local_access import COOKIE


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path)); monkeypatch.chdir(tmp_path)
    now = [100.0]
    app = create_local_app(password=None, origin='http://127.0.0.1:8765',
                           desktop_session_token='x'*48, desktop_mode=True, clock=lambda: now[0])
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 12345)) as client:
        client.cookies.set(COOKIE, 'x'*48)
        csrf = client.get('/api/local/session').json()['csrf']
        yield client, {'Origin':'http://127.0.0.1:8765', 'X-Local-CSRF':csrf}, now


def test_launch_exchanges_once_for_a_separate_httponly_browser_cookie(bridge):
    client, headers, now = bridge
    response = client.post('/api/local/advanced-launch', json={'page':'Employees'}, headers=headers)
    assert response.status_code == 200
    url = response.json()['url']; assert 'x'*48 not in url
    client.cookies.clear()
    opened = client.get(url, follow_redirects=False)
    assert opened.status_code == 303 and opened.headers['location'] == '/ui/employees'
    assert opened.headers['cache-control'] == 'no-store'
    assert opened.headers['referrer-policy'] == 'no-referrer'
    assert 'HttpOnly' in opened.headers['set-cookie'] and 'SameSite=strict' in opened.headers['set-cookie']
    assert client.get('/api/local/session').status_code == 200
    assert client.get(url, follow_redirects=False).status_code == 403


@pytest.mark.parametrize('failure', ['expired', 'logout', 'origin', 'peer', 'invalid'])
def test_launch_fails_closed(bridge, failure):
    client, headers, now = bridge
    url = client.post('/api/local/advanced-launch', json={'page':'Backup'}, headers=headers).json()['url']
    if failure == 'expired': now[0] += 31
    elif failure == 'logout': client.post('/api/local/logout', headers=headers, json={})
    elif failure == 'invalid': url += 'invalid'
    client.cookies.clear()
    extra = {'Origin': 'https://evil.example'} if failure == 'origin' else {'Host': 'evil.example'} if failure == 'peer' else {}
    assert client.get(url, headers=extra, follow_redirects=False).status_code == 403


def test_launch_requires_auth_csrf_and_an_allowlisted_page(bridge):
    client, headers, now = bridge
    assert client.post('/api/local/advanced-launch', json={'page':'Employees'}, headers={'Origin':headers['Origin']}).status_code == 403
    assert client.post('/api/local/advanced-launch', json={'page':'https://evil.example'}, headers=headers).status_code == 422
    for _ in range(12):
        url = client.post('/api/local/advanced-launch', json={'page':'Providers'}, headers=headers).json()['url']
        assert client.get(url, follow_redirects=False).status_code == 303
    client.cookies.clear()
    assert client.post('/api/local/advanced-launch', json={'page':'Employees'}, headers=headers).status_code in (401,403)
