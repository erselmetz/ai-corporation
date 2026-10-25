"""Window-scoped adapter to the existing authenticated loopback API."""
from dataclasses import dataclass
import uuid


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
