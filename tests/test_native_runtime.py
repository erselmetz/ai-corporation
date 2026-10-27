from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import pytest
from app.application.services.native_runtime import NativeRuntimeService,NativeRuntimeStopped,NativeRuntimeConflict
from app.resources.context import native_scope
from app.runtime.factory import create_corporation_runtime


def test_window_and_global_resume_never_revive_old_scopes():
    runtime=NativeRuntimeService();window=runtime.register('owner')['id'];original=runtime.scope('owner',window)
    runtime.stop_window('owner',window);runtime.resume('owner',window)
    fresh=runtime.scope('owner',window)
    assert original.cancelled and not fresh.cancelled and fresh.generation>original.generation
    runtime.stop_all();runtime.resume_global()
    assert fresh.cancelled and not runtime.scope('owner',window).cancelled
    with pytest.raises(NativeRuntimeStopped):runtime.begin(original,'ollama','fake')
    with pytest.raises(KeyError):runtime.scope('other-owner',window)


def test_capture_owner_held_until_real_release_even_after_stop():
    runtime=NativeRuntimeService();a=runtime.register('owner')['id'];b=runtime.register('owner')['id']
    first=runtime.scope('owner',a);second=runtime.scope('owner',b);closed=[]
    with runtime.capture(first,'microphone') as lease:
        runtime.set_capture_closer(first,lease,lambda:closed.append(True))
        with pytest.raises(NativeRuntimeConflict):
            with runtime.capture(second,'screen'):pass
        runtime.stop_window('owner',a);assert closed==[True]
        # Stop request is not a fabricated release acknowledgement.
        with pytest.raises(NativeRuntimeConflict):
            with runtime.capture(second,'camera'):pass
    with runtime.capture(second,'camera'):
        assert runtime.snapshot('owner')['capture'][0]['window_id']==b
    assert runtime.snapshot('owner')['capture']==[]


def test_cancelled_queue_item_never_enters_model_body_and_resume_is_new_work():
    application=create_corporation_runtime().application_service
    application.configure_agent_slots(global_slots=1)
    runtime=application.native_runtime();a=runtime.register('owner')['id'];b=runtime.register('owner')['id']
    first=runtime.scope('owner',a);second=runtime.scope('owner',b)
    entered=Event();release=Event();calls=[]
    def running():
        token=native_scope.set(first)
        try:
            with application.model_request('ollama','first-model'):
                entered.set();assert release.wait(5);calls.append('first')
        finally:native_scope.reset(token)
    def pending():
        token=native_scope.set(second)
        try:
            with application.model_request('ollama','second-model'):calls.append('cancelled-body')
        finally:native_scope.reset(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        active=pool.submit(running);assert entered.wait(5);queued=pool.submit(pending)
        try:
            deadline=time.monotonic()+5
            while not any(o['window_id']==b for o in runtime.snapshot('owner')['operations']):
                assert time.monotonic()<deadline;Event().wait(.01)
            runtime.stop_window('owner',b);runtime.resume('owner',b)
            with pytest.raises(NativeRuntimeStopped):queued.result(5)
        finally:release.set()
        active.result(5)
    assert calls==['first'] and runtime.snapshot('owner')['operations']==[]
    token=native_scope.set(runtime.scope('owner',b))
    try:
        with application.model_request('ollama','second-model'):calls.append('new-work')
    finally:native_scope.reset(token)
    assert calls==['first','new-work']


def test_window_limit_and_owner_status_do_not_leak_other_owners():
    runtime=NativeRuntimeService();runtime.register('private-owner')
    assert runtime.snapshot('other-owner')['windows']==[]
    for _ in range(runtime.MAX_WINDOWS-1):runtime.register('owner')
    with pytest.raises(NativeRuntimeConflict):runtime.register('owner')
