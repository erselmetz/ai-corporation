from time import monotonic
from fastapi.testclient import TestClient
from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.agent_runtime import current_invocation,RuntimeLimits,_step_seconds
from app.runtime.factory import create_corporation_runtime
from app.resources.context import application_service,native_scope,native_model_seconds


class Auth:
    def authenticate(self,request):
        permissions={'chat:read','chat:send','chat:start'}
        if request.headers.get('x-owner-mode')=='manager':permissions.add('model-runtime:manage')
        return AuthenticatedPrincipal('owner',frozenset(permissions))


def test_local_reply_override_requires_runtime_permission_and_preserves_token_cap(monkeypatch):
    runtime=create_corporation_runtime();observed=[]
    def generate(model,messages):
        invocation=current_invocation();observed.append((invocation.step_deadline-monotonic(),invocation.output_token_budget));return 'A bounded reply.'
    monkeypatch.setattr(runtime.providers.get('ollama'),'generate_chat',generate)
    with TestClient(create_app(application_service=runtime.application_service,authentication_backend=Auth())) as client:
        wid=client.post('/api/native/windows',json={}).json()['id']
        scoped={'X-Native-Window':wid,'X-Native-Generation':'0'}
        cid=client.post('/api/chat/conversations',headers=scoped,json={'agent_id':'local_worker'}).json()['conversation']['id']
        path='/api/chat/conversations/'+cid+'/messages';body={'text':'A bounded local reply'}
        assert client.post(path,headers={**scoped,'X-Native-Model-Seconds':'60'},json=body).status_code==403
        assert observed==[]
        manager={**scoped,'X-Native-Model-Seconds':'60','x-owner-mode':'manager'}
        response=client.post(path,headers=manager,json=body)
        assert response.status_code==200,response.text
        assert 55<observed[0][0]<=60 and observed[0][1]==512
        assert runtime.application_service.agent_runtime().limits.step_timeout_seconds==30
        assert client.post(path,headers={**manager,'X-Native-Model-Seconds':'999'},json=body).status_code==400
        assert len(observed)==1


def test_local_override_cannot_increase_total_turn_limit_or_apply_to_remote_provider():
    service=create_corporation_runtime().application_service;runtime=service.native_runtime()
    scope=runtime.scope('owner',runtime.register('owner')['id'])
    a=application_service.set(service);w=native_scope.set(scope);b=native_model_seconds.set(90)
    try:
        with service.model_request('ollama','fake-local-model'):
            assert _step_seconds(RuntimeLimits(total_timeout_seconds=45,step_timeout_seconds=30))==45
            service._orchestrator.providers.get('ollama').base_url='https://remote.invalid'
            assert _step_seconds(RuntimeLimits())==30
    finally:native_model_seconds.reset(b);native_scope.reset(w);application_service.reset(a)
