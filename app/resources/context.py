"""Request-local resource/cancellation context; never confers permission."""
from contextvars import ContextVar

application_service=ContextVar('ersel_model_application_service',default=None)
native_scope=ContextVar('ersel_native_window_scope',default=None)
resource_lease=ContextVar('ersel_resource_lease',default=None)
request_stop=ContextVar('ersel_request_stop_generation',default=None)
native_model_seconds=ContextVar('ersel_native_local_model_seconds',default=None)


def check_native_stop():
    scope=native_scope.get()
    global_stop=request_stop.get()
    if (scope is not None and scope.cancelled) or (global_stop is not None and global_stop.is_set()):
        from app.application.services.native_runtime import NativeRuntimeStopped
        raise NativeRuntimeStopped('This window was stopped; no further action is allowed for this request.')


class ModelContextMiddleware:
    """Preserve context through the entire ASGI response, including streams."""
    def __init__(self,app,application):self.app=app;self.application=application

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        request=Request(scope);service=getattr(self.application.state,'application_service',None)
        native=None;identifier=request.headers.get('x-native-window')
        seconds=request.headers.get('x-native-model-seconds')
        if seconds is not None and (not identifier or seconds not in {'30','60','90'}):
            return await JSONResponse({'detail':'Choose a registered native window and a 30, 60 or 90 second local model limit.'},400)(scope,receive,send)
        if not callable(getattr(service,'native_runtime',None)):
            # Small embedders may expose only non-model services. They have no
            # native window authority; never accept native headers there.
            if identifier:return await JSONResponse({'detail':'Native runtime unavailable'},503)(scope,receive,send)
            return await self.app(scope,receive,send)
        if identifier:
            principal=self.application.state.authentication_backend.authenticate(request)
            if principal is None:return await JSONResponse({'detail':'Authentication required'},401)(scope,receive,send)
            if seconds is not None:
                try:
                    self.application.state.capability_authorization_service.require(identity=principal.identity,permissions=principal.permissions,
                        session_grants=principal.session_grants,capability_id='model-runtime:manage',scope_type='principal',scope_id=principal.identity)
                except PermissionError:return await JSONResponse({'detail':'Model runtime management permission is required to override the local reply limit.'},403)(scope,receive,send)
            try:native=service.native_runtime().scope(principal.identity,identifier)
            except KeyError:return await JSONResponse({'detail':'Native window unavailable'},404)(scope,receive,send)
            generation=request.headers.get('x-native-generation','')
            if not generation.isdecimal() or len(generation)>12 or int(generation)!=native.generation:
                return await JSONResponse({'detail':'This request belongs to an earlier window generation. Start a new request after Resume.'},409)(scope,receive,send)
            control=(request.url.path.startswith('/api/native/windows/') or request.url.path.startswith('/api/memory/owner/native-cancel/')
                     or (request.url.path.startswith('/api/native/tools/') and request.url.path.endswith('/deny'))
                     or (request.url.path.startswith('/api/native/agent/') and request.url.path.endswith('/cancel'))
                     or (request.url.path.startswith('/api/native/capture/') and request.url.path.endswith('/finish')))
            control=control or (request.method=='DELETE' and request.url.path.startswith('/api/chat/conversations/') and '/images/' in request.url.path)
            if native.cancelled and request.method not in {'GET','HEAD'} and not control:
                return await JSONResponse({'detail':'This window is stopped. Resume permits new requests only.'},423)(scope,receive,send)
        service_token=application_service.set(service);window_token=native_scope.set(native)
        stop_token=request_stop.set(service.native_runtime().global_stop)
        budget_token=native_model_seconds.set(int(seconds) if seconds is not None else None)
        try:await self.app(scope,receive,send)
        finally:
            native_model_seconds.reset(budget_token)
            request_stop.reset(stop_token);native_scope.reset(window_token);application_service.reset(service_token)
