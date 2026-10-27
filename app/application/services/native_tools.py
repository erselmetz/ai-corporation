"""Native tools behind the existing permission, approval and Agent boundaries."""
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from time import monotonic
from urllib.parse import urlsplit,urlencode
from uuid import uuid4
import webbrowser

from app.native_io import NativeFiles,NativeIOError,PublicWebReader,http_url
from app.resources.context import check_native_stop
from app.tools import Tool,ToolRegistry
from .capability_approvals import POLICY_VERSION
from .native_runtime import NativeRuntimeStopped


def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def clipped(text,limit=4000):return str(text).encode('utf-8')[:limit].decode('utf-8',errors='ignore')
def string(limit=512):return {'type':'string','maxLength':limit}


SPECS={
    'calculate':('Calculate exact bounded arithmetic','read','chat:send',{'expression':string(256)}),
    'solve_equation':('Solve a real linear or quadratic equation in x','read','chat:send',{'equation':string(256)}),
    'convert_units':('Convert between listed exact unit symbols','read','chat:send',{'value':string(256),'source_unit':string(16),'target_unit':string(16)}),
    'open_url':('Hand an approved http/https URL to the default browser','control','browser:act',{'url':string(2048)}),
    'read_webpage':('Retrieve a public text page; private addresses are blocked','control','browser:act',{'url':string(2048)}),
    'web_search':('Search the public web through an approved query','control','browser:act',{'query':string(256)}),
    'list_folder':('List at most 200 entries in a user-permitted folder','read','native-files:read',{'root_id':string(32),'path':string(512)}),
    'read_text_file':('Read at most 8 KB from a permitted UTF-8 file','read','native-files:read',{'root_id':string(32),'path':string(512)}),
    'write_file':('Write at most 8 KB only after exact diff approval','write','native-files:write',{'root_id':string(32),'path':string(512),'content':string(8192)}),
    'remember':('Save an explicitly approved note to shared My Brain for 30 days','write','memory:manage',{'text':string(4000)}),
    'learn_from_path':('Learn one approved UTF-8 file from a permitted folder','write','memory:manage',{'root_id':string(32),'path':string(512)}),
    'clipboard_write':('Copy explicitly approved text to the local clipboard','control','desktop:act',{'text':string(4000)}),
    'desktop_targets':('Inspect controls only for an owner-permitted executable','read','desktop:act',{'process_name':string(132)}),
}
_desktop_properties={'process_name':string(132),'process_id':{'type':'integer','minimum':1,'maximum':2**31-1},
                     'window_handle':{'type':'integer','minimum':1,'maximum':2**63-1},
                     'window_title':string(256),'automation_id':string(256),'control_name':string(160)}
SPECS['desktop_click']=('Invoke one exact owner-permitted button after approval','control','desktop:act',dict(_desktop_properties))
SPECS['desktop_type']=('Replace one non-password text field after exact approval','control','desktop:act',dict(_desktop_properties,value=string(2048)))
_execution=ContextVar('native_approved_tool_callback',default=None)
_principal=ContextVar('native_approved_tool_principal',default=None)


class NativeTool(Tool):
    def __init__(self,service,name):
        description,risk,capability,properties=SPECS[name]
        super().__init__('native.'+name,name,description,risk_class=risk,input_schema={
            'type':'object','properties':properties,'required':list(properties),'additionalProperties':False})
        self.service=service;self.name=name

    def execute(self,**kwargs):
        action=_execution.get()
        if action is None or action.name!=self.name or digest(kwargs)!=action.payload['arguments_digest']:
            raise PermissionError('Tool execution requires the guarded native application callback')
        return self.service.perform(action)


@dataclass
class NativeAction:
    id:str
    owner:str
    session_id:str|None
    scope:object
    agent_id:str
    name:str
    args:dict
    capability:str
    scope_type:str
    scope_id:str
    payload:dict
    target_digest:str
    summary:str
    target_ref:str
    details:str
    risk:str
    deadline:float
    approval_id:str|None=None
    approval_digest:str|None=None
    state:str='pending'
    result:dict|None=None
    conversation_id:str=''
    raw_text:str=''
    desktop_request:object=None


class NativeToolService:
    MAX_ACTIONS=128
    def __init__(self,application,*,browser_open=webbrowser.open,web_reader=None,clipboard_write=None):
        self.application=application;self.browser_open=browser_open;self.web=web_reader or PublicWebReader()
        self.clipboard_write=clipboard_write;self.desktop_registry=None;self.files=NativeFiles();self.lock=RLock();self.actions={};self.registry=ToolRegistry()
        for name in SPECS:self.registry.register(NativeTool(self,name))

    def check(self,actor,scope,agent_id,name,policy):
        check_native_stop()
        current=self.application.native_runtime().scope(actor.identity,scope.window_id)
        if scope.owner!=actor.identity or scope.cancelled or current.cancelled or current.generation!=scope.generation:
            raise NativeRuntimeStopped('This tool belongs to a stopped or earlier window request.')
        profile=self.application.get_agent_profile(agent_id)
        if profile.paused:raise PermissionError('The selected Agent is paused. Resume it in Advanced before using tools.')
        allowed='reviewed.calculator' if name in {'calculate','solve_equation','convert_units'} else 'native.'+name
        if (profile.builtin_key is not None or profile.allowed_tools) and allowed not in profile.allowed_tools:
            raise PermissionError('The selected Agent is not allowed to use this tool.')
        if name in {'remember','learn_from_path'} and (profile.builtin_key is not None or profile.brain_scopes) and 'owner' not in profile.brain_scopes:
            raise PermissionError('The selected Agent cannot write shared My Brain notes.')

    def authorize(self,actor,capability,scope_type,scope_id,policy):
        policy.require(identity=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,
                       capability_id=capability,scope_type=scope_type,scope_id=scope_id)

    @contextmanager
    def desktop(self):
        from app.integrations.scoped_desktop_automation import ScopedDesktopError
        if self.desktop_registry is None:raise NativeIOError('Configure desktop control permissions in this Python shell first.')
        try:
            with self.desktop_registry.desktop_operation() as service:yield service
        except ScopedDesktopError as error:raise NativeIOError(str(error)) from None

    def target(self,action):
        args=action.args;owner=action.owner;window=action.scope.window_id
        if action.name=='write_file':
            return digest(self.files.preview_write(owner,window,args['root_id'],args['path'],args['content']))
        if action.name in {'read_text_file','learn_from_path'}:
            path=self.files.resolve(owner,window,args['root_id'],args['path']);stat=path.stat()
            return digest([str(path),stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns])
        if action.name=='list_folder':
            path=self.files.resolve(owner,window,args['root_id'],args['path'],allow_root=True)
            stat=path.stat();return digest([str(path),stat.st_dev,stat.st_ino])
        return digest(action.args)

    def prepare(self,actor,scope,agent_id,name,args,*,policy,approvals,ask_first=True):
        if name not in SPECS:raise NativeIOError('This tool is unavailable; no action was run.')
        self.check(actor,scope,agent_id,name,policy)
        args=self.registry.validate_arguments('native.'+name,args)
        args=deepcopy(args);description,risk,capability,_=SPECS[name]
        scope_type='native-root' if capability.startswith('native-files:') else 'principal'
        scope_id=args['root_id'] if scope_type=='native-root' else actor.identity
        self.authorize(actor,capability,scope_type,scope_id,policy)
        if 'root_id' in args:
            # A remembered file needs both scoped read and memory-write authority.
            self.authorize(actor,'native-files:read','native-root',args['root_id'],policy)
            self.files.resolve(actor.identity,scope.window_id,args['root_id'],args['path'],allow_root=name=='list_folder')
        details=description;target_ref=name
        if name in {'open_url','read_webpage'}:
            args['url']=http_url(args['url']);details='Exact destination:\n'+args['url']
            if name=='open_url':details+='\nOnly browser handoff can be confirmed; page loading is not verified.'
            target_ref=urlsplit(args['url']).hostname[:200]
        elif name=='web_search':details='Send this exact query to DuckDuckGo:\n'+args['query']
        elif name=='write_file':
            preview=self.files.preview_write(actor.identity,scope.window_id,args['root_id'],args['path'],args['content'])
            details='Write '+args['path']+'? Full proposed diff:\n'+preview['diff'];target_ref=clipped(args['path'],200)
        elif name in {'read_text_file','list_folder','learn_from_path'}:
            details=('Read ' if name!='learn_from_path' else 'Save locally to shared My Brain for 30 days: ')+args['path']
            target_ref=clipped(args['path'] or 'Chosen folder',200)
        elif name=='remember':details='Save locally to My Brain, shared across windows, for 30 days:\n'+args['text']
        elif name=='clipboard_write':details='Copy this exact text to the local clipboard:\n'+args['text']
        elif name.startswith('desktop_'):details=description
        else:details=description+'\n'+'\n'.join(key+': '+value for key,value in args.items())
        action=NativeAction(uuid4().hex,actor.identity,actor.session_id,scope,agent_id,name,args,capability,scope_type,scope_id,
            {'arguments_digest':digest(args)},'',description,target_ref,details,policy.definition(capability).risk,monotonic()+300)
        if name in {'desktop_click','desktop_type'}:
            from app.integrations.scoped_desktop_automation import DesktopActionRequest
            action.desktop_request=DesktopActionRequest('fill_text' if name=='desktop_type' else 'invoke_button',args['process_id'],args['window_handle'],
                args['process_name'],args['window_title'],args['automation_id'],args['control_name'],args.get('value'))
            with self.desktop() as desktop:
                preview=desktop.preview(action.desktop_request,actor_id=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,session_id=actor.session_id)
                record=desktop.request_approval(action.desktop_request,actor_id=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,session_id=actor.session_id)
            action.target_digest=preview.target_digest;action.approval_id=record['approval_id'];action.approval_digest=record['approval_digest']
            action.details='Exact window: '+args['window_title']+'\nProcess: '+args['process_name']+'\nControl: '+args['control_name']+' ('+args['automation_id']+')'
            if name=='desktop_type':action.details+='\nReplace contents with exactly:\n'+args['value']
            else:action.details+='\nInvoke this button once.'
            action.details+='\nDispatch can be confirmed; application outcome is unverified. Stop cannot undo a dispatched action.'
        else:action.target_digest=self.target(action)
        required=risk!='read' or ask_first
        if required and action.desktop_request is None:
            approval_cap=capability if policy.definition(capability).risk!='low' else 'native-tool:review'
            approval_scope='principal' if approval_cap=='native-tool:review' else scope_type
            approval_scope_id=actor.identity if approval_scope=='principal' else scope_id
            action.payload.update({'approval_capability':approval_cap,'approval_scope':approval_scope,'approval_scope_id':approval_scope_id})
            approval=approvals.request(actor_id=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,
                capability_id=approval_cap,action_id='native.'+name,action_summary=description,target_ref=target_ref,
                scope_type=approval_scope,scope_id=approval_scope_id,payload_digest=digest(action.payload),
                target_digest=action.target_digest,irreversible=name in {'write_file','remember','learn_from_path'},ttl_seconds=300)
            action.approval_id=approval.approval_id;action.approval_digest=approval.approval_digest
        with self.lock:
            for key in [key for key,value in self.actions.items() if value.state!='executing' and value.deadline<monotonic()]:self.actions.pop(key,None)
            if len(self.actions)>=self.MAX_ACTIONS:
                for key in [key for key,value in self.actions.items() if value.state not in {'pending','executing'}][:32]:self.actions.pop(key,None)
            if len(self.actions)>=self.MAX_ACTIONS:raise NativeIOError('The tool review queue is full.')
            self.actions[action.id]=action
        return self.snapshot(action)

    def snapshot(self,action):
        return {'id':action.id,'tool':action.name,'state':action.state,'summary':action.summary,'details':action.details,
                'approval_required':action.approval_id is not None,'approval_digest':action.approval_digest,'result':action.result}

    def get(self,actor,scope,identifier):
        with self.lock:action=self.actions.get(identifier)
        if action is None or (action.owner,action.scope.window_id)!=(actor.identity,scope.window_id):raise KeyError('Tool review unavailable')
        return action

    def execute(self,actor,scope,identifier,*,policy,approvals,confirmed_digest=None):
        action=self.get(actor,scope,identifier)
        self.check(actor,action.scope,action.agent_id,action.name,policy)
        if actor.session_id!=action.session_id:raise PermissionError('The tool review belongs to another session.')
        self.authorize(actor,action.capability,action.scope_type,action.scope_id,policy)
        if policy.definition(action.capability).risk!=action.risk:raise PermissionError('Tool policy changed. Request a new preview.')
        with self.lock:
            if action.state in {'completed','submitted','unverified','failed','denied'}:return self.snapshot(action)
            if action.state!='pending' or monotonic()>action.deadline:raise NativeIOError('Tool review expired or is already executing.')
            if action.approval_id:
                if confirmed_digest!=action.approval_digest:raise PermissionError('Confirm this exact tool preview before execution.')
                approvals.approve(action.approval_id,approver_id=actor.identity,permissions=actor.permissions,confirmed_digest=confirmed_digest)
            action.state='executing'
        def operation():
            self.check(actor,action.scope,action.agent_id,action.name,policy)
            token=_execution.set(action)
            principal_token=_principal.set(actor)
            from app.resources.context import native_scope
            scope_token=native_scope.set(action.scope)
            try:
                result=self.registry.get('native.'+action.name).execute(**action.args)
                action.result=result  # Preserve a confirmed IO receipt across a later Stop.
                return result
            finally:native_scope.reset(scope_token);_execution.reset(token);_principal.reset(principal_token)
        try:
            def guarded():
                # The existing scoped desktop service consumes its own exact
                # action approval once; do not consume it in a second wrapper.
                if action.desktop_request is not None:return operation()
                if not action.approval_id:
                    if self.target(action)!=action.target_digest:raise NativeIOError('The target changed. Review the tool again.')
                    return operation()
                payload=action.payload
                return approvals.execute(action.approval_id,actor_id=actor.identity,permissions=actor.permissions,session_grants=actor.session_grants,
                    capability_id=payload['approval_capability'],action_id='native.'+action.name,action_summary=action.summary,
                    target_ref=action.target_ref,scope_type=payload['approval_scope'],scope_id=payload['approval_scope_id'],
                    payload_digest=digest(payload),current_policy_version=POLICY_VERSION,
                    read_current_target_digest=lambda:self.target(action),operation=operation)
            def turn():
                if action.conversation_id:
                    return self.application.owned_chat().complete_tool_turn(actor.identity,action.conversation_id,action.raw_text,guarded)
                return guarded()
            result=self.application.agent_runtime().run_tool_step(action.agent_id,turn)
            if not isinstance(result,dict) or result.get('state') not in {'completed','submitted','unverified'}:raise NativeIOError('The tool did not return a verified result.')
            action.result=result;action.state=result['state']
        except Exception as error:
            if action.result is not None:
                action.state=action.result['state'];action.result['history_recorded']=False
                action.result['note']='The tool result was received before a later stop or recording failure. No further action was run.'
                return self.snapshot(action)
            action.state='failed';action.result={'state':'failed','confirmed':False,
                'message':str(error)[:256] if isinstance(error,(NativeIOError,NativeRuntimeStopped,PermissionError)) else 'The tool did not complete with a verified result. Inspect any effects already reported; nothing was retried.'}
        return self.snapshot(action)

    def deny(self,actor,scope,identifier,*,approvals):
        action=self.get(actor,scope,identifier)
        if actor.session_id!=action.session_id:raise PermissionError('The tool review belongs to another session.')
        with self.lock:
            if action.state!='pending':raise NativeIOError('This tool review is no longer pending.')
            if action.approval_id:
                from .capability_approvals import CapabilityApprovalError
                try:approvals.deny(action.approval_id,approver_id=actor.identity,permissions=actor.permissions,confirmed_digest=action.approval_digest)
                except (CapabilityApprovalError,PermissionError):pass
            action.state='denied';action.result={'state':'denied','confirmed':False,'message':'Cancelled before execution. No tool action was run.'}
        return self.snapshot(action)

    def perform(self,action):
        check_native_stop();args=action.args;name=action.name;owner=action.owner;window=action.scope.window_id
        message='';data=None;state='completed'
        if name in {'calculate','solve_equation','convert_units'}:
            from .exact_math import calculate,solve_equation,convert_units
            message=(calculate(args['expression']) if name=='calculate' else solve_equation(args['equation']) if name=='solve_equation'
                     else convert_units(args['value'],args['source_unit'],args['target_unit']))
        elif name=='open_url':
            accepted=self.browser_open(args['url'])
            state='submitted' if accepted is True else 'unverified'
            message=('The default browser accepted the approved link. Page loading was not verified.' if accepted is True
                     else 'Browser handoff was not confirmed; page loading is unknown.')
        elif name in {'read_webpage','web_search'}:
            url=args['url'] if name=='read_webpage' else 'https://html.duckduckgo.com/html/?'+urlencode({'q':args['query']})
            data=self.web.read(url,stop=lambda:action.scope.cancelled);message=data['source']+'\n'+clipped(data['text'])
        elif name=='list_folder':
            data=self.files.list_folder(owner,window,args['root_id'],args['path'])
            message='\n'.join(item['kind']+': '+item['name'] for item in data['items']) or 'No supported entries in this folder.'
            if data['truncated']:message+='\nListing reached its entry or scan limit; more files may exist.'
        elif name=='read_text_file':
            data=self.files.read(owner,window,args['root_id'],args['path']);message=args['path']+'\n'+clipped(data['text'])
        elif name=='write_file':
            preview=self.files.preview_write(owner,window,args['root_id'],args['path'],args['content'])
            if digest(preview)!=action.target_digest:raise NativeIOError('The file changed after approval; nothing was written.')
            data=self.files.write(owner,window,args['root_id'],preview);message='File write confirmed: '+args['path']
        elif name in {'remember','learn_from_path'}:
            from app.knowledge.native_brain import NativeBrain
            brain=self.application.native_brain(stopper=lambda:self.application.native_runtime().global_stop.is_set())
            if name=='remember':
                content=args['text'].encode();key='text:'+sha256(content).hexdigest();filename='Owner note.txt'
            else:
                data=self.files.read(owner,window,args['root_id'],args['path']);content=data['text'].encode('utf-8')
                path=self.files.resolve(owner,window,args['root_id'],args['path']);key=str(path);filename=path.name
            data=brain.feed(owner,key,filename,content,consent=True,days=30)
            message=('Brain already had this unchanged source.' if data['state']=='unchanged' else 'Saved '+str(data['chunks'])+' chunks to shared My Brain for 30 days.')
        elif name=='clipboard_write':
            from app.native_io import write_clipboard
            callback=self.clipboard_write or (lambda text:write_clipboard(text,self.application.native_runtime().window_handle(owner,window)))
            if callback(args['text']) is not True:raise NativeIOError('Clipboard write was not confirmed; previous clipboard contents may have been cleared.')
            message='Local clipboard write confirmed: '+str(len(args['text']))+' characters.'
        elif name.startswith('desktop_'):
            actor=_principal.get()
            if actor is None:raise PermissionError('A fresh approved owner context is required')
            context={'actor_id':actor.identity,'permissions':actor.permissions,'session_grants':actor.session_grants,'session_id':actor.session_id}
            with self.desktop() as desktop:
                if name=='desktop_targets':
                    from app.integrations.scoped_desktop_automation import DesktopWindowRequest
                    targets=[]
                    for item in desktop.list_windows(args['process_name'],**context)[:5]:
                        check_native_stop()
                        controls=desktop.list_controls(DesktopWindowRequest(**item),**context)
                        targets.append(dict(item,controls=controls[:40]))
                    message=json.dumps(targets,ensure_ascii=False)
                else:
                    receipt=desktop.execute(action.desktop_request,action.approval_id,**context)
                    state='unverified';message='Approved desktop action '+receipt['status']+'. Its application outcome is unverified. Do not retry automatically.'
        else:raise NativeIOError('The selected tool is not implemented; no action was run.')
        return {'state':state,'confirmed':state in {'completed','submitted'},'message':clipped(message,6000),
                'untrusted':True,'brain_changed':name in {'remember','learn_from_path'}}
