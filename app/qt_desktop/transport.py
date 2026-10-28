"""Window-scoped adapter to the existing authenticated loopback API."""
from dataclasses import dataclass
import uuid
import threading
import hashlib
import os
import stat
import re
from pathlib import Path


@dataclass
class Chat:
    model: str
    agent: str
    project: str
    workspace: str = ''
    conversation: str = ''
    window_id: str = ''
    window_generation: int = 0
    title: str = ''
    title_pending: bool = False
    reply_seconds: int = 30
    read_only: bool = False
    last_local_prompt: str = ''


class Transport:
    def __init__(self, session):
        self.session = session
        self.jobs={}; self.jobs_lock=threading.RLock()

    def catalog(self, window_id=''):
        if not window_id:raise ValueError('Register this window before loading models')
        import httpx
        offline=False
        try:models=self.session.models()
        except (httpx.HTTPError,RuntimeError,ValueError):models=[];offline=True
        return {'window_id':window_id,'window_generation':None,'models':models,'model_offline':offline,
                'agents': self.session.request('GET', '/api/agents')['items'],
                'projects': self.session.request('GET', '/api/projects')['items']}

    def start(self, chat, *, generation=0):
        if not chat.model:
            if chat.project:raise ValueError('Choose a model before starting a Project conversation')
            response=self.session.client.post('/api/chat/conversations',json={'agent_id':chat.agent},headers={
                'X-Local-CSRF':self.session.credentials['csrf'],'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
            response.raise_for_status();chat.conversation=response.json()['conversation']['id'];return
        workspace = uuid.uuid4().hex
        self.session.request('POST', '/api/chat/workspaces', {'id': workspace,
            'agent_id': chat.agent, 'provider_id': 'ollama', 'model_id': chat.model,
            'project_id': chat.project},window=chat.window_id or None,generation=generation)
        response = self.session.client.post('/api/chat/conversations', json={'agent_id': chat.agent},
            headers={'X-Local-CSRF': self.session.credentials['csrf'], 'X-Chat-Workspace': workspace,
                     'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status()
        chat.workspace, chat.conversation = workspace, response.json()['conversation']['id']
        if chat.title_pending:
            self.rename(chat,chat.title,generation=generation);chat.title_pending=False

    def rename(self,chat,title,*,generation=0):
        base='/api/chat/history/' if chat.read_only else '/api/chat/conversations/'
        response=self.session.client.patch(base+chat.conversation+'/title',json={'title':title},
            headers={'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
                     'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status();return response.json()

    def delete(self,chat,*,generation=0):
        base='/api/chat/history/' if chat.read_only else '/api/chat/conversations/'
        response=self.session.client.request('DELETE',base+chat.conversation,json={},
            headers={'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
                     'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status();return response.json()

    def history(self,chat,*,generation=0):
        response=self.session.client.get('/api/chat/history/'+chat.conversation,headers={
            'X-Chat-Workspace':chat.workspace,'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status();return response.json()

    def send(self, chat, text, stop, emit, *, generation=0,knowledge=None):
        if chat.read_only:raise ValueError('Restored history is read-only. Open a new chat before sending.')
        if stop.is_set():raise RuntimeError('Request cancelled before submission')
        if not chat.conversation:
            self.start(chat,generation=generation)
        if stop.is_set():raise RuntimeError('Request cancelled before submission')
        options={'window':chat.window_id or None,'generation':generation}
        if knowledge is not None:options['knowledge']=knowledge
        if chat.reply_seconds!=30:options['seconds']=chat.reply_seconds
        self.session.send(chat.workspace, chat.conversation, text, stop, emit,**options)

    def preview_knowledge(self,chat,text,*,generation=0):
        if not chat.conversation:self.start(chat,generation=generation)
        response=self.session.client.post('/api/chat/conversations/'+chat.conversation+'/knowledge-preview',
            json={'query':text,'scopes':[{'scope':'owner','scope_id':''}]},headers={
            'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
            'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status();return response.json()

    def launch(self, page):
        return self.session.request('POST', '/api/local/advanced-launch', {'page': page})['url']

    def tool_api(self,chat,method,suffix='',body=None,*,generation=0):
        for value in [chat.window_id,chat.workspace,chat.conversation]:
            if value and not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Invalid native conversation identity')
        response=self.session.client.request(method,'/api/native/tools'+suffix,json=body or {},headers={
            'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
            'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        if not response.is_success:raise RuntimeError(str(response.json().get('detail','Tool request was not confirmed'))[:512])
        return response.json()

    def prepare_tool(self,chat,text,name,args,*,generation=0):
        if not chat.conversation:self.start(chat,generation=generation)
        return self.tool_api(chat,'POST',body={'conversation_id':chat.conversation,'user_text':text,
            'tool':name,'arguments':args,'ask_first':True},generation=generation)

    def agent_api(self,chat,suffix='',body=None,*,generation=0):
        if not chat.conversation:self.start(chat,generation=generation)
        headers={
            'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
            'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)}
        if chat.reply_seconds!=30:headers['X-Native-Model-Seconds']=str(chat.reply_seconds)
        response=self.session.client.post('/api/native/agent'+suffix,json=body or {},headers=headers)
        if not response.is_success:raise RuntimeError('The local Agent request was not confirmed')
        return response.json()

    def grant_root(self,chat,path,*,generation=0):
        if not chat.conversation:self.start(chat,generation=generation)
        return self.tool_api(chat,'POST','/roots',{'path':path,'consent':True},generation=generation)

    def capture_api(self,chat,method,suffix='',body=None,*,generation=0):
        response=self.session.client.request(method,'/api/native/capture'+suffix,json=body or {},headers={
            'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
            'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        if not response.is_success:raise RuntimeError('The device consent or release request was not confirmed.')
        return response.json()

    def send_image(self,chat,capture,text,*,generation=0):
        import base64
        if not chat.conversation:self.start(chat,generation=generation)
        headers={'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
                 'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)}
        base='/api/chat/conversations/'+chat.conversation
        body={'media_type':'image/png','data_base64':base64.b64encode(capture['data']).decode('ascii'),
              'captured_at':capture['captured_at']}
        if capture['kind']=='screen':body['display_surface']='monitor'
        response=self.session.client.post(base+('/screen-captures' if capture['kind']=='screen' else '/camera-captures'),json=body,headers=headers)
        response.raise_for_status();identifier=response.json()['image']['id']
        cleanup_confirmed=True
        try:
            response=self.session.client.post(base+'/messages',json={'text':text,'image_ids':[identifier],'image_consent':True},headers=headers)
            response.raise_for_status();answer=response.json()['conversation']['messages'][-1]['content']
        finally:
            import httpx
            try:self.session.client.request('DELETE',base+'/images/'+identifier,json={},headers=headers).raise_for_status()
            except httpx.HTTPError:cleanup_confirmed=False
        if not cleanup_confirmed:answer+='\n\nLocal image cleanup was not confirmed. The response above was received; nothing was resent. The temporary attachment remains subject to backend expiry.'
        return answer

    def transcribe_local(self,chat,data,*,generation=0):
        response=self.session.client.post('/api/local/voice/transcribe-local',content=bytes(data),headers={
            'Content-Type':'audio/wav','X-Local-CSRF':self.session.credentials['csrf'],
            'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status();return response.json()['transcript']

    def send_math(self,chat,text,tool,emit,*,generation=0):
        if not chat.conversation:self.start(chat,generation=generation)
        response=self.session.client.post('/api/chat/conversations/'+chat.conversation+'/messages',
            json={'text':text,'reviewed_tools':[tool],'exact_math_only':True},
            headers={'X-Local-CSRF':self.session.credentials['csrf'],'X-Chat-Workspace':chat.workspace,
                     'X-Native-Window':chat.window_id,'X-Native-Generation':str(generation)})
        response.raise_for_status();result=response.json()
        messages=result['conversation']['messages']
        emit({'type':'chunk','text':messages[-1]['content']})
        emit({'type':'complete'})

    def feed_data(self, window_id, stable_key, filename, data, stop, *, generation=0):
        if stop.is_set(): raise RuntimeError('Feed cancelled')
        job=self.session.request('POST','/api/memory/owner/native-job')['id']
        confirmed=False
        with self.jobs_lock: self.jobs.setdefault(window_id,set()).add(job)
        try:
            if stop.is_set():
                self.session.request('POST','/api/memory/owner/native-cancel/'+job)
                raise RuntimeError('Feed cancelled')
            response=self.session.client.post('/api/memory/owner/native-feed',
                headers={'X-Local-CSRF':self.session.credentials['csrf'],'X-Native-Window':window_id,'X-Native-Generation':str(generation)},
                data={'stable_key':stable_key,'consent':'true','days':'30','job_id':job},
                files={'file':(filename,data)})
            response.raise_for_status();result=response.json();confirmed=True;return result
        finally:
            if not confirmed:
                try:self.session.request('POST','/api/memory/owner/native-cancel/'+job)
                except Exception:pass  # Preserve the original failure, not a cleanup error.
            with self.jobs_lock: self.jobs.get(window_id,set()).discard(job)

    def feed_file(self, window_id, path, stop, *, generation=0):
        from app.knowledge.native_brain import MAX_FILE_BYTES, secret_path
        path=Path(path)
        if path.is_symlink() or path.is_junction() or secret_path(path): raise ValueError('Unsafe source path')
        before=path.stat(); resolved=path.resolve(strict=True)
        with path.open('rb') as handle:
            opened=os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino): raise ValueError('File changed; choose it again')
            data=handle.read(MAX_FILE_BYTES+1); after=os.fstat(handle.fileno())
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise ValueError('File changed; choose it again')
        if len(data)>MAX_FILE_BYTES: raise ValueError('File exceeds 5 MB')
        return self.feed_data(window_id,os.path.normcase(str(resolved)),resolved.name,data,stop,generation=generation)

    def feed_text(self, window_id, text, stop, *, generation=0):
        data=text.encode('utf-8')
        return self.feed_data(window_id,'text:'+hashlib.sha256(data).hexdigest(),'Owner note.txt',data,stop,generation=generation)

    def cancel_feed(self, window_id):
        with self.jobs_lock: jobs=tuple(self.jobs.get(window_id,()))
        for job in jobs: self.session.request('POST','/api/memory/owner/native-cancel/'+job)
