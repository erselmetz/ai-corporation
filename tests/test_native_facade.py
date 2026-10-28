"""Real policy/middleware chain, in memory, including lock and concurrency."""
import asyncio,threading,time
import httpx,pytest
from app.native_desktop.session import NativeSession
from app.native_desktop.facade import PolicyTransport,ORIGIN
from app.local import create_local_app
from app.api.local_access import COOKIE

@pytest.fixture
def session(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path));monkeypatch.chdir(tmp_path)
    value=NativeSession();yield value;value.close()

def test_inprocess_policy_keeps_auth_csrf_origin_default_deny_and_stop(session):
    transport=session.controller.transport
    assert transport.thread.is_alive()
    # Same dispatcher, no credential: protected operations still fail.
    request=httpx.Request('GET',ORIGIN+'/api/employees',headers={'Origin':ORIGIN})
    response=transport.handle_request(request);response.read();assert response.status_code==401
    r=session.client.post('/api/projects',json={'name':'deny'});assert r.status_code==403
    assert session.client.get('/api/employees',headers={'Origin':'https://wrong.invalid'}).status_code==403
    assert session.client.post('/api/projects',json={'name':'deny'},headers={'X-Local-CSRF':session.credentials['csrf']}).status_code==403
    assert session.request('PUT','/api/local/preferences',{'detail_level':'brief'})['preferences']['detail_level']=='brief'
    original=session.client
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(422,json={'detail':{'state':'Key rejected','message':'The endpoint rejected the key.'}})),base_url=ORIGIN) as fake:
        session.client=fake
        try:
            with pytest.raises(RuntimeError,match='The endpoint rejected the key') as friendly:
                session.request('POST','/api/local/provider-connections/example/test',{'consent':True})
            assert '{' not in str(friendly.value)
        finally:session.client=original
    session.request('POST','/api/local/emergency-stop/stop')
    assert session.client.post('/api/projects',json={'name':'blocked'},headers={'X-Local-CSRF':session.credentials['csrf']}).status_code==423
    for path in ['/ui','/ui/login','/ui/providers','/ui/static/chat.mjs','/local/advanced-launch','/docs','/redoc']:
        with pytest.raises(ValueError):session.client.get(path)
    from fastapi.testclient import TestClient
    probe=TestClient(session.controller.application,base_url=ORIGIN,client=('127.0.0.1',50000))
    for path in ['/ui','/ui/login','/ui/providers','/ui/static/chat.mjs','/local/advanced-launch','/docs','/redoc']:
        assert probe.get(path).status_code==404
    with pytest.raises(ValueError):session.request('GET','https://example.invalid/api/employees')

def test_lock_blocks_previously_captured_authority_and_unlock_never_resumes(session,monkeypatch):
    from app.local_owner_credential import LocalOwnerCredentialStore
    cookie=session.client.cookies.get(COOKIE)
    monkeypatch.setattr(LocalOwnerCredentialStore,'verify',lambda self,password:password=='valid owner password')
    session.lock_owner()
    assert session.client.get('/api/local/session',headers={'Cookie':COOKIE+'='+cookie}).status_code==401
    with pytest.raises(ValueError):session.unlock_owner('wrong')
    assert session.controller.application.state.authentication_backend.desktop_locked
    session.unlock_owner('valid owner password')
    assert session.request('GET','/api/native/windows')['global_stopped'] is True
    assert session.request('GET','/api/local/session')['identity']=='local-owner'

def test_native_stream_delivers_before_completion_and_dispatches_concurrently():
    from fastapi import FastAPI
    from starlette.responses import StreamingResponse
    application=FastAPI();gate=threading.Event()
    @application.get('/api/stream')
    async def stream():
        async def body():
            yield b'first\n'
            while not gate.is_set():await asyncio.sleep(.01)
            yield b'last\n'
        return StreamingResponse(body())
    @application.get('/api/ping')
    def ping():return {'ok':True}
    transport=PolicyTransport(application)
    with httpx.Client(transport=transport,base_url=ORIGIN) as client:
        with client.stream('GET','/api/stream') as response:
            chunks=response.iter_lines();assert next(chunks)=='first'
            assert not gate.is_set() and client.get('/api/ping').json()=={'ok':True}
            gate.set();assert next(chunks)=='last'
    assert not transport.thread.is_alive()

def test_real_native_record_readers_and_project_action(session):
    from app.qt_desktop.page_schema import PAGES
    for title in ['Employees','Positions','Projects','Tasks','Workflows','Workflow map','Structure','Providers','Agents','Approvals','Activity','Documentation','Preferences','Session grants','Capability policy']:
        assert isinstance(session.request('GET',PAGES[title].endpoint),dict),title
    before=len(session.request('GET','/api/projects')['items'])
    response=session.client.post('/api/projects',json={'name':'Native owner created'},headers={'X-Local-CSRF':session.credentials['csrf']})
    assert response.status_code==403  # Existing owner session deliberately lacks project:create.
    assert len(session.request('GET','/api/projects')['items'])==before
