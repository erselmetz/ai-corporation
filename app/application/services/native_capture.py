"""Exact capture consent and ownership leases; this service does not capture data.

The native device adapter must release its real device before finishing a lease.
Stop sets a cancellation event and retains ownership until that finish arrives.
"""
from dataclasses import dataclass,field
from threading import RLock,Event
from time import monotonic
from uuid import uuid4
from app.native_io import NativeIOError
from .native_tools import digest
from .capability_approvals import POLICY_VERSION
from .capability_approvals import CapabilityApprovalError


CAPABILITIES={'camera':'camera:capture','screen':'screen:capture','microphone':'native-microphone:capture'}


@dataclass
class CaptureLease:
    id:str
    owner:str
    session_id:str|None
    scope:object
    kind:str
    target:str
    capability:str
    approval_id:str
    approval_digest:str
    payload_digest:str
    target_digest:str
    deadline:float
    state:str='review'
    cancelled:Event=field(default_factory=Event,repr=False)
    context:object|None=field(default=None,repr=False)
    runtime_id:str=''


class NativeCaptureService:
    def __init__(self,application):self.application=application;self.lock=RLock();self.leases={}

    def request(self,actor,scope,kind,target,*,policy,approvals):
        if kind not in CAPABILITIES or not isinstance(target,str) or not 1<=len(target.encode())<=512 or any(ord(c)<32 for c in target):
            raise NativeIOError('Choose one bounded native capture device.')
        current=self.application.native_runtime().scope(actor.identity,scope.window_id)
        if scope.cancelled or current.generation!=scope.generation:raise NativeIOError('This window is stopped; capture was not started.')
        capability=CAPABILITIES[kind]
        policy.require(identity=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,
                       capability_id=capability,scope_type='principal',scope_id=actor.identity)
        with self.lock:
            for key in [key for key,value in self.leases.items() if value.state!='active' and value.deadline<monotonic()]:self.leases.pop(key,None)
            if len(self.leases)>=32:raise NativeIOError('The capture review queue is full.')
            payload=digest([scope.window_id,scope.generation,kind,target]);target_digest=digest([kind,target])
            approval=approvals.request(actor_id=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,
                capability_id=capability,action_id='native.capture.'+kind,action_summary='Capture once from '+kind,
                target_ref=kind,scope_type='principal',scope_id=actor.identity,payload_digest=payload,
                target_digest=target_digest,ttl_seconds=60)
            lease=CaptureLease(uuid4().hex,actor.identity,actor.session_id,scope,kind,target,capability,
                approval.approval_id,approval.approval_digest,payload,target_digest,monotonic()+60)
            self.leases[lease.id]=lease
            return self.snapshot(lease)

    def get(self,actor,scope,identifier):
        with self.lock:lease=self.leases.get(identifier)
        if lease is None or (lease.owner,lease.session_id,lease.scope.window_id)!=(actor.identity,actor.session_id,scope.window_id):
            raise KeyError('Capture review unavailable')
        return lease

    def snapshot(self,lease):
        return {'id':lease.id,'kind':lease.kind,'target':lease.target,'state':lease.state,
                'approval_digest':lease.approval_digest,'cancelled':lease.cancelled.is_set() or lease.scope.cancelled,
                'message':'Permission review only; no capture has run.' if lease.state=='review' else
                    'Native capture owns this lease; device data is not held by this service.'}

    def begin(self,actor,scope,identifier,confirmed_digest,*,policy,approvals):
        lease=self.get(actor,scope,identifier)
        with self.lock:
            current=self.application.native_runtime().scope(actor.identity,scope.window_id)
            if lease.state!='review' or monotonic()>lease.deadline or lease.scope.cancelled or current.generation!=lease.scope.generation:
                raise NativeIOError('Capture review expired, stopped or already used.')
            if confirmed_digest!=lease.approval_digest:raise PermissionError('Confirm the exact device capture review.')
            approvals.approve(lease.approval_id,approver_id=actor.identity,permissions=actor.permissions,confirmed_digest=confirmed_digest)
            def reserve():
                runtime=self.application.native_runtime();context=runtime.capture(lease.scope,lease.kind)
                runtime_id=context.__enter__()
                try:runtime.set_capture_closer(lease.scope,runtime_id,lease.cancelled.set)
                except Exception:context.__exit__(None,None,None);raise
                lease.context=context;lease.runtime_id=runtime_id;lease.state='active'
                return self.snapshot(lease)
            return approvals.execute(lease.approval_id,actor_id=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,
                capability_id=lease.capability,action_id='native.capture.'+lease.kind,action_summary='Capture once from '+lease.kind,
                target_ref=lease.kind,scope_type='principal',scope_id=actor.identity,payload_digest=lease.payload_digest,
                current_policy_version=POLICY_VERSION,read_current_target_digest=lambda:lease.target_digest,operation=reserve)

    def finish(self,actor,scope,identifier,*,approvals):
        lease=self.get(actor,scope,identifier)
        with self.lock:
            was_cancelled=lease.cancelled.is_set() or lease.scope.cancelled
            if lease.state=='review':
                try:approvals.deny(lease.approval_id,approver_id=actor.identity,permissions=actor.permissions,confirmed_digest=lease.approval_digest)
                except (CapabilityApprovalError,PermissionError):pass  # Closing a lease never approves or executes the action.
            lease.cancelled.set()
            if lease.context is not None:
                lease.context.__exit__(None,None,None);lease.context=None
            lease.state='finished';return {**self.snapshot(lease),'cancelled_before_finish':was_cancelled}
