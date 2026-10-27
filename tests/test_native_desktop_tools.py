from contextlib import nullcontext
from hashlib import sha256
from types import SimpleNamespace
from test_native_tools import tools
from test_scoped_desktop_automation import FakeBackend
from app.integrations.scoped_desktop_automation import ScopedDesktopAutomation,DesktopAutomationPolicy
from app.application.services.emergency_stop import EmergencyStopService
from app.resources.context import native_scope


def test_native_type_delegates_exact_approval_to_existing_desktop_service_once(tools,monkeypatch):
    service,app,actor,scope,policy,approvals,_=tools
    monkeypatch.setattr(app,'get_agent_profile',lambda _:SimpleNamespace(builtin_key='operator',paused=False,
        allowed_tools=('native.desktop_type','native.desktop_click','native.desktop_targets'),brain_scopes=()))
    backend=FakeBackend();backend.state.update(control_type='Edit',password=False,read_only=False,value_digest=sha256(b'original').hexdigest())
    desktop=ScopedDesktopAutomation(DesktopAutomationPolicy(frozenset({'notepad.exe'}),frozenset({'fill_text','invoke_button'})),
        approvals,authorization=policy,emergency_stop=EmergencyStopService(),backend=backend)
    service.desktop_registry=SimpleNamespace(desktop_operation=lambda:nullcontext(desktop))
    args={'process_id':4242,'window_handle':161616,'process_name':'notepad.exe','window_title':'Document - Notepad',
          'automation_id':'saveButton','control_name':'Save','value':'Exact reviewed text'}
    token=native_scope.set(scope)
    try:
        review=service.prepare(actor,scope,'local_worker','desktop_type',args,policy=policy,approvals=approvals,ask_first=False)
        assert review['approval_required'] and args['value'] in review['details'] and backend.invocations==0
        action=service.get(actor,scope,review['id'])
        assert approvals.get(action.approval_id).action_id=='desktop.fill_text'
        result=service.execute(actor,scope,review['id'],policy=policy,approvals=approvals,confirmed_digest=review['approval_digest'])
        assert result['state']=='unverified' and result['result']['confirmed'] is False
        assert backend.invocations==1
        assert service.execute(actor,scope,review['id'],policy=policy,approvals=approvals)['state']=='unverified'
        assert backend.invocations==1
    finally:native_scope.reset(token)
