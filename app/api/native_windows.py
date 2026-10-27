"""Native window control plane, independent of occupied model worker slots."""
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,StrictBool,StrictInt,Field
from .security import require_permission
from app.application.services.native_runtime import NativeRuntimeConflict

router=APIRouter(prefix='/api/native/windows')


class ResumeBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:StrictBool


class RegisterBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_id:str=Field(default='',max_length=32,pattern='^(?:[0-9a-f]{32})?$')
    hwnd:StrictInt=Field(default=0,ge=0,le=2**64-1)


def runtime(request:Request):return request.app.state.application_service.native_runtime()


@router.post('')
def register(body:RegisterBody,principal=Depends(require_permission('chat:read')),service=Depends(runtime)):
    try:return service.register(principal.identity,body.client_id,body.hwnd)
    except NativeRuntimeConflict as error:raise HTTPException(409,str(error)) from None


@router.get('')
def status(request:Request,principal=Depends(require_permission('chat:read')),service=Depends(runtime)):
    agent=getattr(request.app.state.application_service,'_native_agent_service',None)
    if agent is not None:agent.reap()
    return service.snapshot(principal.identity)


@router.post('/{identifier}/stop')
def stop(identifier:str,principal=Depends(require_permission('chat:read')),service=Depends(runtime)):
    try:return service.stop_window(principal.identity,identifier)
    except KeyError:raise HTTPException(404,'Native window unavailable') from None


@router.post('/{identifier}/resume')
def resume(identifier:str,body:ResumeBody,principal=Depends(require_permission('chat:send')),service=Depends(runtime)):
    if not body.confirmed:raise HTTPException(409,'Confirm Resume to allow new requests; cancelled work will not restart.')
    try:return service.resume(principal.identity,identifier)
    except KeyError:raise HTTPException(404,'Native window unavailable') from None


@router.delete('/{identifier}')
def unregister(identifier:str,request:Request,principal=Depends(require_permission('chat:read')),service=Depends(runtime)):
    try:service.unregister(principal.identity,identifier)
    except KeyError:raise HTTPException(404,'Native window unavailable') from None
    except NativeRuntimeConflict as error:raise HTTPException(409,str(error)) from None
    application=request.app.state.application_service
    tools=getattr(application,'_native_tool_service',None)
    if tools is not None:tools.files.revoke_window(principal.identity,identifier)
    agent=getattr(application,'_native_agent_service',None)
    if agent is not None:agent.reap()
    return {'closed':True}
