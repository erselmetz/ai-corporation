"""Principal-owned browser chat using the existing Corporation conversation domain."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock, RLock
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from .corporation_chat import CorporationChatService

if TYPE_CHECKING:
    from .corporation import AgentSummary, ProviderSummary


class ChatNotFound(ValueError):
    pass


class ChatConflict(ValueError):
    pass


class ChatUnavailable(ValueError):
    pass


class ChatLimit(ValueError):
    pass


@dataclass(frozen=True)
class _OwnedConversation:
    owner: str
    coordinator: AgentSummary
    lock: Lock


class OwnedChatService:
    """One process, bounded in-memory ownership; no autonomous actions or retries.

    This owns a separate CorporationChatService from the trusted CLI chat path.
    Overlapping get/send/close calls are rejected rather than queued. Configuration
    outside this path is not synchronized; a changed assignment requires new chat.
    """
    MAX_CONVERSATIONS = 100
    MAX_MESSAGES = 200

    def __init__(self, chat: CorporationChatService,
                 get_agent: Callable[[str], AgentSummary],
                 get_provider: Callable[[str], ProviderSummary]):
        self._chat = chat
        self._get_agent = get_agent
        self._get_provider = get_provider
        self._entries: dict[str, _OwnedConversation] = {}
        self._catalog_lock = RLock()

    def _coordinator(self, agent_id):
        try:
            agent = self._get_agent(agent_id)
            self._get_provider(agent.provider)
        except ValueError:
            raise ChatUnavailable("Coordinator or configured provider is missing") from None
        if not agent.model or not agent.model.strip():
            raise ChatUnavailable("Coordinator has no configured model")
        return agent

    def start(self, owner: str, agent_id: str):
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner identity is required")
        with self._catalog_lock:
            if len(self._entries) >= self.MAX_CONVERSATIONS:
                raise ChatLimit("Conversation limit reached for this app run")
            agent = self._coordinator(agent_id)
            identifier = uuid4().hex
            record = self._chat.start(identifier, agent_id)
            self._entries[identifier] = _OwnedConversation(owner, agent, Lock())
            return {"conversation": record, "coordinator": agent}

    def list(self, owner: str):
        with self._catalog_lock:
            return tuple({"id": identifier, "coordinator": entry.coordinator}
                         for identifier, entry in self._entries.items() if entry.owner == owner)

    @contextmanager
    def _access(self, owner, identifier):
        with self._catalog_lock:
            entry = self._entries.get(identifier)
            if entry is None or entry.owner != owner:
                raise ChatNotFound("Conversation not found")
        if not entry.lock.acquire(blocking=False):
            raise ChatConflict("Conversation is busy; wait for the current request")
        try:
            yield entry
        finally:
            entry.lock.release()

    def get(self, owner, identifier):
        with self._access(owner, identifier) as entry:
            return {"conversation": self._chat.get(identifier), "coordinator": entry.coordinator}

    def send(self, owner, identifier, text):
        with self._access(owner, identifier) as entry:
            current = self._coordinator(entry.coordinator.id)
            if (current.provider, current.model) != (entry.coordinator.provider, entry.coordinator.model):
                raise ChatConflict("Coordinator assignment changed; start a new conversation")
            if len(self._chat.get(identifier).messages) + 2 > self.MAX_MESSAGES:
                raise ChatLimit("Conversation message limit reached; start a new conversation")
            record = self._chat.send(identifier, text)
            return {"conversation": record, "coordinator": entry.coordinator}

    def close(self, owner, identifier):
        with self._access(owner, identifier) as entry:
            return {"conversation": self._chat.close(identifier), "coordinator": entry.coordinator}
