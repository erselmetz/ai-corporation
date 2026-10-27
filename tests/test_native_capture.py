import pytest
from app.application.services.native_capture import NativeCaptureService
from app.application.services.native_runtime import NativeRuntimeConflict
from app.application.services.capability_authorization import CapabilityAuthorizationDenied
from app.api.security import AuthenticatedPrincipal
from test_native_tools import tools


def test_capture_review_owns_nothing_until_exact_consent_and_stop_retains_real_device_ownership(tools):
    _,app,actor,scope,policy,approvals,_=tools;service=NativeCaptureService(app)
    actor=AuthenticatedPrincipal(actor.identity,actor.permissions|{'camera:capture'},session_id=actor.session_id)
    review=service.request(actor,scope,'camera','Camera 0',policy=policy,approvals=approvals)
    assert app.native_runtime().snapshot(actor.identity)['capture']==[]
    with pytest.raises(PermissionError):service.begin(actor,scope,review['id'],'0'*64,policy=policy,approvals=approvals)
    active=service.begin(actor,scope,review['id'],review['approval_digest'],policy=policy,approvals=approvals)
    assert active['state']=='active'
    runtime=app.native_runtime();other=runtime.scope(actor.identity,runtime.register(actor.identity)['id'])
    with pytest.raises(NativeRuntimeConflict):
        with runtime.capture(other,'screen'):pytest.fail('Another window acquired capture')
    runtime.stop_window(actor.identity,scope.window_id)
    assert service.snapshot(service.get(actor,scope,review['id']))['cancelled'] is True
    assert len(runtime.snapshot(actor.identity)['capture'])==1  # Stop requests closure; it does not fabricate release.
    service.finish(actor,scope,review['id'],approvals=approvals)
    assert runtime.snapshot(actor.identity)['capture']==[]
    with runtime.capture(other,'screen'):pass


def test_microphone_requires_exact_review_and_never_grants_camera_permission(tools):
    _,app,actor,scope,policy,approvals,_=tools;service=NativeCaptureService(app)
    chat_only=AuthenticatedPrincipal(actor.identity,frozenset({'chat:send','capability-approval:manage'}),session_id=actor.session_id)
    review=service.request(chat_only,scope,'microphone','Default microphone, at most ten seconds',policy=policy,approvals=approvals)
    assert review['state']=='review'
    with pytest.raises(CapabilityAuthorizationDenied):service.request(chat_only,scope,'camera','Camera 0',policy=policy,approvals=approvals)
    service.finish(chat_only,scope,review['id'],approvals=approvals)
    assert app.native_runtime().snapshot(actor.identity)['capture']==[]


def test_capture_review_cannot_cross_window_or_replay_after_resume(tools):
    _,app,actor,scope,policy,approvals,_=tools;service=NativeCaptureService(app)
    review=service.request(actor,scope,'microphone','Microphone',policy=policy,approvals=approvals)
    runtime=app.native_runtime();other=runtime.scope(actor.identity,runtime.register(actor.identity)['id'])
    with pytest.raises(KeyError):service.get(actor,other,review['id'])
    runtime.stop_window(actor.identity,scope.window_id);runtime.resume(actor.identity,scope.window_id)
    fresh=runtime.scope(actor.identity,scope.window_id)
    with pytest.raises(ValueError):service.begin(actor,fresh,review['id'],review['approval_digest'],policy=policy,approvals=approvals)
    assert runtime.snapshot(actor.identity)['capture']==[]
