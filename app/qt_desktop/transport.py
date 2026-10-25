"""Window-scoped adapter to the existing authenticated loopback API."""
from dataclasses import dataclass
import uuid
import threading
import hashlib
import os
import stat
from pathlib import Path


@dataclass
class Chat:
    model: str
    agent: str
    project: str
    workspace: str = ''
    conversation: str = ''


class Transport:
    def __init__(self, session):
        self.session = session
        self.jobs={}; self.jobs_lock=threading.RLock()

    def catalog(self):
        return {'models': self.session.models(),
                'agents': self.session.request('GET', '/api/agents')['items'],
                'projects': self.session.request('GET', '/api/projects')['items']}

    def start(self, chat):
        workspace = uuid.uuid4().hex
        self.session.request('POST', '/api/chat/workspaces', {'id': workspace,
            'agent_id': chat.agent, 'provider_id': 'ollama', 'model_id': chat.model,
            'project_id': chat.project})
        response = self.session.client.post('/api/chat/conversations', json={'agent_id': chat.agent},
            headers={'X-Local-CSRF': self.session.credentials['csrf'], 'X-Chat-Workspace': workspace})
        response.raise_for_status()
        chat.workspace, chat.conversation = workspace, response.json()['conversation']['id']

    def send(self, chat, text, stop, emit):
        if not chat.conversation:
            self.start(chat)
        self.session.send(chat.workspace, chat.conversation, text, stop, emit)

    def launch(self, page):
        return self.session.request('POST', '/api/local/advanced-launch', {'page': page})['url']

    def feed_data(self, window_id, stable_key, filename, data, stop):
        if stop.is_set(): raise RuntimeError('Feed cancelled')
        job=self.session.request('POST','/api/memory/owner/native-job')['id']
        with self.jobs_lock: self.jobs.setdefault(window_id,set()).add(job)
        try:
            if stop.is_set():
                self.session.request('POST','/api/memory/owner/native-cancel/'+job)
                raise RuntimeError('Feed cancelled')
            response=self.session.client.post('/api/memory/owner/native-feed',
                headers={'X-Local-CSRF':self.session.credentials['csrf']},
                data={'stable_key':stable_key,'consent':'true','days':'30','job_id':job},
                files={'file':(filename,data)})
            response.raise_for_status(); return response.json()
        finally:
            with self.jobs_lock: self.jobs.get(window_id,set()).discard(job)

    def feed_file(self, window_id, path, stop):
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
        return self.feed_data(window_id,os.path.normcase(str(resolved)),resolved.name,data,stop)

    def feed_text(self, window_id, text, stop):
        data=text.encode('utf-8')
        return self.feed_data(window_id,'text:'+hashlib.sha256(data).hexdigest(),'Owner note.txt',data,stop)

    def cancel_feed(self, window_id):
        with self.jobs_lock: jobs=tuple(self.jobs.get(window_id,()))
        for job in jobs: self.session.request('POST','/api/memory/owner/native-cancel/'+job)
