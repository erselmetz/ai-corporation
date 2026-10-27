"""Exact native device consent. No frame/audio data passes through these routes."""
from typing import Literal
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from .native_tools import context,components,safe_error
from .security import require_permission
from app.application.services.capability_authorization import CapabilityAuthorizationDenied
from app.application.services.capability_approvals import CapabilityApprovalError
from app.application.services.native_runtime import NativeRuntimeConflict,NativeRuntimeStopped

router=APIRouter(prefix='/api/native/capture')
ERRORS=(ValueError,KeyError,PermissionError,CapabilityAuthorizationDenied,CapabilityApprovalError,NativeRuntimeConflict,NativeRuntimeStopped)


class CaptureBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['camera','screen','microphone']
    target:str=Field(min_length=1,max_length=512)


class BeginBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed_digest:str=Field(min_length=64,max_length=64)


@router.post('')
def review(body:CaptureBody,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    _,policy,approvals=components(request)
    try:return request.app.state.application_service.native_capture().request(principal,scope,body.kind,body.target,policy=policy,approvals=approvals)
    except ERRORS as error:raise safe_error(error) from None


@router.post('/{identifier}/begin')
def begin(identifier:str,body:BeginBody,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    _,policy,approvals=components(request)
    try:return request.app.state.application_service.native_capture().begin(principal,scope,identifier,body.confirmed_digest,policy=policy,approvals=approvals)
    except ERRORS as error:raise safe_error(error) from None


@router.get('/{identifier}')
def status(identifier:str,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:read'))):
    service=request.app.state.application_service.native_capture()
    try:return service.snapshot(service.get(principal,scope,identifier))
    except ERRORS as error:raise safe_error(error) from None


@router.post('/{identifier}/finish')
def finish(identifier:str,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:read'))):
    _,_,approvals=components(request)
    try:return request.app.state.application_service.native_capture().finish(principal,scope,identifier,approvals=approvals)
    except ERRORS as error:raise safe_error(error) from None
