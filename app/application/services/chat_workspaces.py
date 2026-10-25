"""Owner-scoped workspace metadata; no transcript, approval or action replay."""
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
import json
import re
from threading import RLock
from datetime import datetime, timezone
import hashlib

from app.database.connection import get_connection

current_workspace = ContextVar("chat_workspace", default=None)
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


@dataclass(frozen=True)
class WorkspaceContext:
    owner: str
    id: str
    agent_id: str
    provider_id: str
    model_id: str
    project_id: str
    project_brief: str = ""


class ChatWorkspaceService:
    MAX_WORKSPACES = 100

    def __init__(self, corporation_id, application):
        self._corporation = corporation_id
        self._application = application
        self._lock = RLock()

    @contextmanager
    def _connection(self):
        connection = get_connection()
        try:
            yield connection
        finally:
            connection.close()

    def open(self, owner, workspace_id, *, agent_id, provider_id="", model_id="", project_id=""):
        if not isinstance(workspace_id, str) or not _IDENTIFIER.fullmatch(workspace_id):
            raise ValueError("Workspace identifier is invalid")
        agent = self._application.get_agent(agent_id)
        provider_id, model_id = provider_id or agent.provider, model_id or agent.model
        if any(not isinstance(value, str) or not value.strip() or len(value) > 256 for value in (provider_id, model_id)):
            raise ValueError("Choose a registered provider and model")
        self._application.get_provider(provider_id)
        # An explicit local route must be installed; checking never pulls or loads it.
        if self._application.provider_is_local(provider_id):
            inventory = self._application.local_model_inventory(provider_id)
            if inventory.state != "available" or model_id not in inventory.models:
                raise ValueError("The selected local model is not confirmed installed")
            if self._application.model_supports_chat(provider_id, model_id) is False:
                raise ValueError("This installed model does not report chat completion support")
        elif (provider_id, model_id) != (agent.provider, agent.model):
            raise ValueError("Online workspace routes must use an existing Agent assignment")
        if project_id:
            self._application.get_project(project_id)
        selection = dict(agent_id=agent_id, provider_id=provider_id, model_id=model_id, project_id=project_id)
        with self._lock, self._connection() as connection, connection:
            row = connection.execute("SELECT owner_id FROM chat_workspaces WHERE corporation_id=? AND workspace_id=?",
                                     (self._corporation, workspace_id)).fetchone()
            if row and row[0] != owner:
                raise PermissionError("Workspace unavailable")
            count = connection.execute("SELECT count(*) FROM chat_workspaces WHERE corporation_id=?", (self._corporation,)).fetchone()[0]
            if not row and count >= self.MAX_WORKSPACES:
                raise ValueError("Workspace capacity reached")
            connection.execute("INSERT INTO chat_workspaces VALUES(?,?,?,?) ON CONFLICT(corporation_id,workspace_id) DO UPDATE SET selection_json=excluded.selection_json",
                               (self._corporation, owner, workspace_id, json.dumps(selection)))
        return WorkspaceContext(owner, workspace_id, **selection)

    def get(self, owner, workspace_id):
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT owner_id,selection_json FROM chat_workspaces WHERE corporation_id=? AND workspace_id=?",
                                     (self._corporation, workspace_id)).fetchone()
        if row is None or row[0] != owner:
            raise PermissionError("Workspace unavailable")
        selection = json.loads(row[1])
        return WorkspaceContext(owner, workspace_id, **selection,
                                project_brief=self.brief(owner, selection["project_id"]))

    def bind(self, owner, conversation_id):
        context = current_workspace.get()
        if context is None:
            return
        if context.owner != owner:
            raise PermissionError("Workspace unavailable")
        selection = dict(agent_id=context.agent_id, provider_id=context.provider_id,
                         model_id=context.model_id, project_id=context.project_id)
        with self._lock, self._connection() as connection, connection:
            connection.execute("INSERT INTO chat_workspace_conversations VALUES(?,?,?,?,?)",
                               (self._corporation, owner, context.id, conversation_id, json.dumps(selection)))

    def permits(self, owner, conversation_id):
        context = current_workspace.get()
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT owner_id,workspace_id,selection_json FROM chat_workspace_conversations WHERE corporation_id=? AND conversation_id=?",
                                     (self._corporation, conversation_id)).fetchone()
        if context is None:
            return row is None
        return bool(row and row[0] == owner == context.owner and row[1] == context.id)

    def conversation_selection(self, owner, conversation_id):
        if not self.permits(owner, conversation_id):
            raise PermissionError("Conversation unavailable in this workspace")
        with self._connection() as connection:
            row = connection.execute("SELECT selection_json FROM chat_workspace_conversations WHERE corporation_id=? AND conversation_id=?",
                                     (self._corporation, conversation_id)).fetchone()
        return json.loads(row[0]) if row else None

    def conversation_context(self, context, conversation_id):
        with self._connection() as connection:
            row = connection.execute("SELECT owner_id,workspace_id,selection_json FROM chat_workspace_conversations WHERE corporation_id=? AND conversation_id=?",
                                     (self._corporation, conversation_id)).fetchone()
        if row is None:
            return context
        if row[0] != context.owner or row[1] != context.id:
            raise PermissionError("Conversation unavailable")
        selection = json.loads(row[2])
        return WorkspaceContext(context.owner, context.id, **selection,
                                project_brief=self.brief(context.owner, selection["project_id"]))

    def brief(self, owner, project_id):
        if not project_id:
            return ""
        with self._connection() as connection:
            row = connection.execute("SELECT brief FROM chat_project_briefs WHERE corporation_id=? AND owner_id=? AND project_id=?",
                                     (self._corporation, owner, project_id)).fetchone()
        return row[0] if row else ""

    def save_brief(self, owner, project_id, brief):
        self._application.get_project(project_id)
        if not isinstance(brief, str) or len(brief.encode("utf-8")) > 2000:
            raise ValueError("Project brief is limited to 2000 UTF-8 bytes")
        from .chat_knowledge import SECRET_PATTERN
        if SECRET_PATTERN.search(brief):
            raise ValueError("Keep keys and credentials out of the project brief")
        with self._lock, self._connection() as connection, connection:
            connection.execute("INSERT INTO chat_project_briefs VALUES(?,?,?,?) ON CONFLICT(corporation_id,owner_id,project_id) DO UPDATE SET brief=excluded.brief",
                               (self._corporation, owner, project_id, brief))
        return {"project_id": project_id, "brief": brief}

    def prompt_brief(self, conversation_id):
        context = current_workspace.get()
        if context is None or not context.project_brief:
            return None
        selection = self.conversation_selection(context.owner, conversation_id)
        if selection is None or context.project_id != selection["project_id"]:
            raise PermissionError("Project brief is outside this conversation")
        return context.project_brief

    @staticmethod
    def brief_digest(brief):
        return hashlib.sha256(brief.encode("utf-8")).hexdigest()

    def has_project_knowledge(self, owner, project_id):
        if not project_id:
            return False
        from app.memory import MemoryScope
        items = self._application.memory_management().list(actor_id=owner, scope=MemoryScope.PROJECT,
            scope_id=project_id, limit=100, now=datetime.now(timezone.utc))
        return any(not item["expired"] for item in items)
