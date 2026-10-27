"""Owner-bound native windows, cancellation generations and capture ownership.

These records carry no prompts or model authority. Existing API permissions,
exact-action approvals, consent and spending policy remain mandatory.
"""
from contextlib import contextmanager
from dataclasses import dataclass,field
from threading import Event,RLock
from uuid import uuid4


class NativeRuntimeConflict(RuntimeError):pass
class NativeRuntimeStopped(RuntimeError):pass


@dataclass(frozen=True)
class NativeScope:
    owner:str
    window_id:str
    generation:int
    stop:Event=field(repr=False,compare=False)
    global_stop:Event=field(repr=False,compare=False)

    @property
    def cancelled(self):return self.stop.is_set() or self.global_stop.is_set()


@dataclass
class Window:
    owner:str
    id:str
    client_id:str=''
    hwnd:int=0
    generation:int=0
    stop:Event=field(default_factory=Event,repr=False)


class NativeRuntimeService:
    MAX_WINDOWS=16
    MAX_OPERATIONS=64

    def __init__(self):
        self.lock=RLock();self.windows={};self.operations={};self.devices={};self.global_stop=Event()

    def register(self,owner,client_id='',hwnd=0):
        if hwnd:
            import ctypes,os
            from ctypes import wintypes
            pid=wintypes.DWORD();user=ctypes.WinDLL('user32',use_last_error=True)
            function=user.GetWindowThreadProcessId;function.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];function.restype=wintypes.DWORD
            if not function(hwnd,ctypes.byref(pid)) or pid.value!=os.getpid():raise NativeRuntimeConflict('The native window does not belong to this application process.')
        with self.lock:
            if client_id:
                prior=next((w for w in self.windows.values() if w.owner==owner and w.client_id==client_id),None)
                if prior:return self.snapshot_window(owner,prior.id)
            if len(self.windows)>=self.MAX_WINDOWS:raise NativeRuntimeConflict('Close a chat window before opening another.')
            identifier=uuid4().hex;self.windows[identifier]=Window(owner,identifier,client_id,hwnd)
            return self.snapshot_window(owner,identifier)

    def scope(self,owner,identifier):
        with self.lock:
            window=self.windows.get(identifier)
            if window is None or window.owner!=owner:raise KeyError('Native window unavailable')
            return NativeScope(owner,identifier,window.generation,window.stop,self.global_stop)

    def window_handle(self,owner,identifier):
        with self.lock:
            self.scope(owner,identifier)
            return self.windows[identifier].hwnd

    def snapshot_window(self,owner,identifier):
        scope=self.scope(owner,identifier)
        return {'id':scope.window_id,'generation':scope.generation,'stopped':scope.cancelled,'window_stopped':scope.stop.is_set()}

    def stop_window(self,owner,identifier):
        with self.lock:
            scope=self.scope(owner,identifier);scope.stop.set()
            closers=[lease['close'] for lease in self.devices.values() if lease['window_id']==identifier and lease['close'] is not None]
            for item in self.operations.values():
                if item['window_id']==identifier:item['state']='stopping'
        for close in closers:
            try:close()
            except Exception:pass  # Keep ownership until the real capture finally releases it.
        return self.snapshot_window(owner,identifier)

    def stop_all(self):
        with self.lock:
            self.global_stop.set()
            closers=[lease['close'] for lease in self.devices.values() if lease['close'] is not None]
            for item in self.operations.values():item['state']='stopping'
        for close in closers:
            try:close()
            except Exception:pass

    def resume_global(self):
        with self.lock:
            self.global_stop=Event()
            for window in self.windows.values():window.generation+=1

    def resume(self,owner,identifier):
        with self.lock:
            scope=self.scope(owner,identifier);window=self.windows[identifier]
            if scope.stop.is_set():
                window.generation+=1;window.stop=Event()
            # Old scopes retain their SET Event; this never restarts old work.
            return self.snapshot_window(owner,identifier)

    def unregister(self,owner,identifier):
        self.stop_window(owner,identifier)
        with self.lock:
            if any(lease['window_id']==identifier for lease in self.devices.values()):
                raise NativeRuntimeConflict('Wait for the capture adapter to close its device and release ownership before closing this window.')
            self.windows.pop(identifier,None)

    def begin(self,scope,provider,model):
        with self.lock:
            if scope is not None:
                current=self.scope(scope.owner,scope.window_id)
                if scope.cancelled or current.generation!=scope.generation:raise NativeRuntimeStopped('This window was stopped. Start a new request after Resume.')
            if len(self.operations)>=self.MAX_OPERATIONS:raise NativeRuntimeConflict('The local request queue is full.')
            identifier=uuid4().hex
            self.operations[identifier]={'id':identifier,'owner':scope.owner if scope else None,
                'window_id':scope.window_id if scope else None,'provider':provider,'model':model,'state':'waiting'}
            return identifier

    def mark(self,identifier,state,*,provider=None,model=None):
        with self.lock:
            if identifier in self.operations:
                if self.operations[identifier]['state']!='stopping':self.operations[identifier]['state']=state
                if provider is not None:self.operations[identifier]['provider']=provider
                if model is not None:self.operations[identifier]['model']=model

    def finish(self,identifier):
        with self.lock:self.operations.pop(identifier,None)

    @contextmanager
    def capture(self,scope,kind):
        if kind not in {'microphone','camera','screen'}:raise ValueError('Unsupported capture device')
        with self.lock:
            current=self.scope(scope.owner,scope.window_id)
            if scope.cancelled or current.generation!=scope.generation:raise NativeRuntimeStopped('Capture is stopped for this window.')
            if any(lease['window_id']!=scope.window_id for lease in self.devices.values()):
                raise NativeRuntimeConflict('Another chat window owns capture. Stop it before using this device.')
            if any(lease['kind']==kind for lease in self.devices.values()):raise NativeRuntimeConflict('This device is already in use.')
            identifier=uuid4().hex
            self.devices[identifier]={'owner':scope.owner,'window_id':scope.window_id,'kind':kind,'close':None}
        try:yield identifier
        finally:
            with self.lock:self.devices.pop(identifier,None)

    def set_capture_closer(self,scope,identifier,close):
        if not callable(close):raise TypeError('Capture stop callback is required')
        with self.lock:
            lease=self.devices.get(identifier)
            if lease is None or lease['owner']!=scope.owner or lease['window_id']!=scope.window_id:raise KeyError('Capture lease unavailable')
            lease['close']=close
        if scope.cancelled:close()

    def snapshot(self,owner):
        with self.lock:
            return {'global_stopped':self.global_stop.is_set(),'windows':[self.snapshot_window(owner,w.id) for w in self.windows.values() if w.owner==owner],
                'operations':[{k:v for k,v in item.items() if k!='owner'} for item in self.operations.values() if item['owner']==owner],
                'capture':[{k:v for k,v in lease.items() if k not in {'owner','close'}} for lease in self.devices.values() if lease['owner']==owner],
                'other_capture_active':any(lease['owner']!=owner for lease in self.devices.values()),
                'reload_notice':'Different models can require Ollama to reload weights. This is not a residency or GPU measurement.'}
