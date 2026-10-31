from types import SimpleNamespace
import pytest
from app.api.security import AuthenticatedPrincipal
from app.runtime.factory import create_corporation_runtime
from app.application.services.native_tools import NativeToolService
from app.application.services.capability_authorization import DEFAULT_CAPABILITY_AUTHORIZATION,CapabilityAuthorizationDenied
from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.native_runtime import NativeRuntimeStopped


@pytest.fixture
def tools():
    application=create_corporation_runtime().application_service
    opened=[];service=NativeToolService(application,browser_open=lambda url:opened.append(url) or True)
    runtime=application.native_runtime();wid=runtime.register('owner')['id'];scope=runtime.scope('owner',wid)
    actor=AuthenticatedPrincipal('owner',frozenset({'chat:send','memory:manage','desktop:act','browser:act','capability-approval:manage'}),session_id='qa-session')
    policy=DEFAULT_CAPABILITY_AUTHORIZATION;approvals=CapabilityApprovalService(policy)
    return service,application,actor,scope,policy,approvals,opened


def test_open_url_requires_exact_approval_and_returns_only_confirmed_handoff(tools):
    service,app,actor,scope,policy,approvals,opened=tools
    action=service.prepare(actor,scope,'local_worker','open_url',{'url':'https://www.youtube.com/'},policy=policy,approvals=approvals,ask_first=False)
    assert action['approval_required'] is True and opened==[]
    with pytest.raises(PermissionError):service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest='0'*64)
    assert opened==[]
    result=service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest=action['approval_digest'])
    assert result['state']=='submitted' and 'Page loading was not verified' in result['result']['message']
    service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest=action['approval_digest'])
    assert opened==['https://www.youtube.com/']


def test_denial_and_stop_resume_never_execute_a_stale_action(tools):
    service,app,actor,scope,policy,approvals,opened=tools
    action=service.prepare(actor,scope,'local_worker','open_url',{'url':'https://example.com/'},policy=policy,approvals=approvals)
    assert service.deny(actor,scope,action['id'],approvals=approvals)['state']=='denied'
    assert service.execute(actor,scope,action['id'],policy=policy,approvals=approvals)['state']=='denied'
    pending=service.prepare(actor,scope,'local_worker','open_url',{'url':'https://example.com/'},policy=policy,approvals=approvals)
    app.native_runtime().stop_all();app.native_runtime().resume_global()
    fresh=app.native_runtime().scope(actor.identity,scope.window_id)
    with pytest.raises(NativeRuntimeStopped):service.execute(actor,fresh,pending['id'],policy=policy,approvals=approvals,confirmed_digest=pending['approval_digest'])
    assert opened==[]


def test_registered_native_tool_cannot_be_invoked_without_guarded_callback(tools):
    service,*_=tools
    with pytest.raises(PermissionError):service.registry.get('native.open_url').execute(url='https://example.com/')


def test_write_requires_root_read_and_os_action_permissions_and_fresh_diff(tools,tmp_path):
    service,app,actor,scope,policy,approvals,_=tools
    root=service.files.register(actor.identity,scope.window_id,tmp_path,consent=True)['id']
    path=tmp_path/'fact.txt';path.write_bytes(b'Before\n')
    action=service.prepare(actor,scope,'local_worker','write_file',{'root_id':root,'path':'fact.txt','content':'After\n'},policy=policy,approvals=approvals,ask_first=False)
    assert '-Before' in action['details'] and '+After' in action['details'] and path.read_bytes()==b'Before\n'
    path.write_bytes(b'Changed meanwhile\n')
    result=service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest=action['approval_digest'])
    assert result['state']=='failed' and path.read_bytes()==b'Changed meanwhile\n'
    fresh=service.prepare(actor,scope,'local_worker','write_file',{'root_id':root,'path':'fact.txt','content':'Reviewed\n'},policy=policy,approvals=approvals)
    result=service.execute(actor,scope,fresh['id'],policy=policy,approvals=approvals,confirmed_digest=fresh['approval_digest'])
    assert result['state']=='completed' and path.read_bytes()==b'Reviewed\n'


def test_create_folder_requires_exact_approval_and_returns_os_receipt(tools,tmp_path):
    service,app,actor,scope,policy,approvals,_=tools
    root=service.files.register(actor.identity,scope.window_id,tmp_path,consent=True)['id']
    action=service.prepare(actor,scope,'local_worker','create_folder',{'root_id':root,'path':'Reports'},policy=policy,approvals=approvals,ask_first=False)
    assert action['approval_required'] is True and not (tmp_path/'Reports').exists()
    result=service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest=action['approval_digest'])
    assert result['state']=='completed' and result['result']['message']=='Folder creation confirmed: Reports'
    assert (tmp_path/'Reports').is_dir()


def test_permissions_and_current_agent_allowlist_are_rechecked_before_execution(tools,monkeypatch):
    service,app,actor,scope,policy,approvals,opened=tools
    denied=AuthenticatedPrincipal(actor.identity,frozenset({'chat:send'}),session_id=actor.session_id)
    with pytest.raises(CapabilityAuthorizationDenied):service.prepare(denied,scope,'local_worker','open_url',{'url':'https://example.com/'},policy=policy,approvals=approvals)
    action=service.prepare(actor,scope,'local_worker','open_url',{'url':'https://example.com/'},policy=policy,approvals=approvals)
    monkeypatch.setattr(app,'get_agent_profile',lambda _:SimpleNamespace(builtin_key='restricted',allowed_tools=(),brain_scopes=(),paused=False))
    with pytest.raises(PermissionError):service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest=action['approval_digest'])
    assert opened==[]


def test_unconfirmed_browser_result_is_never_reported_as_page_opened(tools):
    service,app,actor,scope,policy,approvals,_=tools;service.browser_open=lambda _:False
    action=service.prepare(actor,scope,'local_worker','open_url',{'url':'https://example.com/'},policy=policy,approvals=approvals)
    result=service.execute(actor,scope,action['id'],policy=policy,approvals=approvals,confirmed_digest=action['approval_digest'])
    assert result['state']=='unverified' and result['result']['confirmed'] is False
    assert 'page loading is unknown' in result['result']['message']
