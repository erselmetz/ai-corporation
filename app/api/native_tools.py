"""Exact native action previews; no API input can manufacture approval authority."""
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,StrictBool
from app.resources.context import native_scope
from app.native_io import NativeIOError
from app.application.services.native_runtime import NativeRuntimeStopped,NativeRuntimeConflict
from app.application.services.capability_authorization import CapabilityAuthorizationDenied
from app.application.services.capability_approvals import CapabilityApprovalError
from .security import require_permission
from .chat import _autonomy_level,chat_errors,contains_gemini_key,SECRET_PASTE_GUIDANCE

router=APIRouter(prefix='/api/native/tools')


class PrepareBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str=Field(min_length=1,max_length=80)
    tool:str=Field(min_length=1,max_length=64)
    arguments:dict
    user_text:str=Field(min_length=1,max_length=8192)
    ask_first:StrictBool=True


class ExecuteBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed_digest:str|None=Field(default=None,min_length=64,max_length=64)


class RootBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    path:str=Field(min_length=1,max_length=4096)
    consent:StrictBool


def context(request:Request):
    scope=native_scope.get()
    if scope is None:raise HTTPException(400,'Use this action from a registered native chat window.')
    return scope


def components(request):
    state=request.app.state
    tools=state.application_service.native_tools()
    from .local_automation import _registry
    tools.desktop_registry=_registry(request)
    return tools,state.capability_authorization_service,state.capability_approval_service


def safe_error(error):
    if isinstance(error,KeyError):return HTTPException(404,'Tool review or folder permission unavailable')
    if isinstance(error,(PermissionError,CapabilityAuthorizationDenied)):return HTTPException(403,str(error)[:256])
    if isinstance(error,(NativeRuntimeStopped,NativeRuntimeConflict,CapabilityApprovalError)):return HTTPException(409,str(error)[:256])
    return HTTPException(422,str(error)[:256])


@router.post('/roots')
def root(body:RootBody,request:Request,scope=Depends(context),principal=Depends(require_permission('memory:manage'))):
    from app.application.services.chat_workspaces import current_workspace
    workspace=current_workspace.get()
    if workspace is None:raise HTTPException(409,'Start this conversation before choosing its tool folder.')
    if _autonomy_level(request,principal.identity)=='chat_only':raise HTTPException(403,'Chat-only mode blocks file tools.')
    tools,policy,_=components(request)
    try:
        tools.authorize(principal,'native-files:read','native-root','new-selection',policy)
        return tools.files.register(principal.identity,scope.window_id,body.path,consent=body.consent,workspace_id=workspace.id)
    except (ValueError,PermissionError,CapabilityAuthorizationDenied) as error:raise safe_error(error) from None


@router.post('')
def prepare(body:PrepareBody,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    if contains_gemini_key(body.user_text):raise HTTPException(422,SECRET_PASTE_GUIDANCE)
    if _autonomy_level(request,principal.identity)=='chat_only':raise HTTPException(403,'Chat-only mode blocks tools.')
    tools,policy,approvals=components(request)
    with chat_errors():current=request.app.state.application_service.owned_chat().get(principal.identity,body.conversation_id)
    if current['conversation'].status.value!='open':raise HTTPException(409,'Start a new conversation before requesting tools.')
    try:
        result=tools.prepare(principal,scope,current['coordinator'].id,body.tool,body.arguments,policy=policy,approvals=approvals,
            ask_first=body.ask_first or _autonomy_level(request,principal.identity)=='ask_every_action')
        action=tools.get(principal,scope,result['id']);action.conversation_id=body.conversation_id;action.raw_text=body.user_text
        return result
    except (ValueError,PermissionError,KeyError,CapabilityAuthorizationDenied,CapabilityApprovalError,NativeRuntimeStopped) as error:
        raise safe_error(error) from None


@router.get('/{identifier}')
def status(identifier:str,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:read'))):
    tools,policy,_=components(request)
    try:
        action=tools.get(principal,scope,identifier)
        tools.authorize(principal,action.capability,action.scope_type,action.scope_id,policy)
        return tools.snapshot(action)
    except (KeyError,PermissionError,CapabilityAuthorizationDenied) as error:raise safe_error(error) from None


@router.post('/{identifier}/execute')
def execute(identifier:str,body:ExecuteBody,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    if _autonomy_level(request,principal.identity)=='chat_only':raise HTTPException(403,'Chat-only mode blocks tools.')
    tools,policy,approvals=components(request)
    try:return tools.execute(principal,scope,identifier,policy=policy,approvals=approvals,confirmed_digest=body.confirmed_digest)
    except (ValueError,PermissionError,KeyError,CapabilityAuthorizationDenied,CapabilityApprovalError,NativeRuntimeStopped) as error:raise safe_error(error) from None


@router.post('/{identifier}/deny')
def deny(identifier:str,request:Request,scope=Depends(context),principal=Depends(require_permission('chat:send'))):
    tools,_,approvals=components(request)
    try:return tools.deny(principal,scope,identifier,approvals=approvals)
    except (ValueError,PermissionError,KeyError,CapabilityApprovalError) as error:raise safe_error(error) from None
