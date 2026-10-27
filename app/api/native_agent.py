"""Authenticated bounded local Agent turns; tool proposals use existing approvals."""
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,StrictBool,StrictInt
from .native_tools import context,components,safe_error
from .security import require_permission
from .chat import _autonomy_level,contains_gemini_key,SECRET_PASTE_GUIDANCE,KnowledgeScopeBody,_knowledge_preview,get_chat_now
from app.application.services.capability_approvals import CapabilityApprovalError
from app.application.services.capability_authorization import CapabilityAuthorizationDenied
from app.application.services.native_runtime import NativeRuntimeStopped

router=APIRouter(prefix='/api/native/agent')


class StartBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str=Field(min_length=1,max_length=80)
    text:str=Field(min_length=1,max_length=8192)
    max_steps:StrictInt=Field(default=5,ge=1,le=5)
    num_ctx:StrictInt=Field(default=8192,ge=2048,le=16384)
    thinking:StrictBool=False
    ask_first:StrictBool=True
    knowledge_enabled:StrictBool=False
    knowledge_scopes:list[KnowledgeScopeBody]=Field(default_factory=list,max_length=3)
    knowledge_preview_digest:str|None=Field(default=None,min_length=64,max_length=64)


class AdvanceBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed_digest:str|None=Field(default=None,min_length=64,max_length=64)


ERRORS=(ValueError,PermissionError,KeyError,CapabilityApprovalError,CapabilityAuthorizationDenied,NativeRuntimeStopped)


@router.post('')
def start(body:StartBody,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send')),now=Depends(get_chat_now)):
    if contains_gemini_key(body.text):raise HTTPException(422,SECRET_PASTE_GUIDANCE)
    autonomy=_autonomy_level(request,principal.identity)
    if autonomy=='chat_only':raise HTTPException(403,'Chat-only mode blocks Agent tool turns.')
    _,policy,approvals=components(request)
    retrieval=None;retrieved_context=None
    if body.knowledge_enabled:
        if not body.knowledge_scopes or not body.knowledge_preview_digest:raise HTTPException(422,'Review private Brain excerpts before using them.')
        service=request.app.state.application_service
        from .chat import chat_errors
        with chat_errors():current=service.owned_chat().get(principal.identity,body.conversation_id)
        profile=service.get_agent_profile(current['coordinator'].id)
        if (profile.builtin_key is not None or profile.brain_scopes) and any(s.scope.value not in profile.brain_scopes for s in body.knowledge_scopes):
            raise HTTPException(403,'This Agent profile cannot read the selected Brain scope.')
        selected=_knowledge_preview(service,principal.identity,body.conversation_id,body.text,body.knowledge_scopes,now)
        if selected['digest']!=body.knowledge_preview_digest:raise HTTPException(409,'Selected knowledge changed after preview. Review it again before sending.')
        retrieval={'enabled':True,**selected['trace']};retrieved_context=selected['prompt_context'] if selected['preview'] else None
    elif body.knowledge_scopes or body.knowledge_preview_digest:raise HTTPException(422,'Brain preview fields require an explicit Brain selection.')
    try:return request.app.state.application_service.native_agent().start(principal,scope,body.conversation_id,body.text,
        policy=policy,approvals=approvals,max_steps=body.max_steps,num_ctx=body.num_ctx,thinking=body.thinking,
        ask_first=body.ask_first or autonomy=='ask_every_action',brain_enabled=body.knowledge_enabled,
        retrieved_context=retrieved_context,retrieval=retrieval)
    except ERRORS as error:raise safe_error(error) from None


@router.post('/{identifier}/advance')
def advance(identifier:str,body:AdvanceBody,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    if _autonomy_level(request,principal.identity)=='chat_only':raise HTTPException(403,'Chat-only mode blocks Agent tool turns.')
    _,policy,approvals=components(request)
    try:return request.app.state.application_service.native_agent().advance(principal,scope,identifier,
        policy=policy,approvals=approvals,confirmed_digest=body.confirmed_digest)
    except ERRORS as error:raise safe_error(error) from None


@router.post('/{identifier}/cancel')
def cancel(identifier:str,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    _,_,approvals=components(request)
    try:return request.app.state.application_service.native_agent().cancel(principal,scope,identifier,approvals=approvals)
    except ERRORS as error:raise safe_error(error) from None
