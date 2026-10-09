"""Principal-owned browser chat using the existing Corporation conversation domain."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock, RLock
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from app.agents.registry import AgentAssignmentBusy

from .corporation_chat import CorporationChatService

if TYPE_CHECKING:
    from .corporation import AgentSummary


class ChatNotFound(ValueError):
    pass


class ChatConflict(ValueError):
    pass


class ChatUnavailable(ValueError):
    pass


class ChatConsentRequired(ValueError):
    pass


class ChatLimit(ValueError):
    pass


@dataclass(frozen=True)
class _OwnedConversation:
    owner: str
    coordinator: AgentSummary
    provider: object = field(repr=False, compare=False)
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
                 get_provider: Callable[[str], object],
                 agent_execution: Callable[[str], object]):
        self._chat = chat
        self._get_agent = get_agent
        self._get_provider = get_provider
        self._agent_execution = agent_execution
        self._entries: dict[str, _OwnedConversation] = {}
        self._catalog_lock = RLock()
        self._active_agents: dict[str, int] = {}
        self._configuring_agents: set[str] = set()

    @contextmanager
    def configuration_change(self, agent_id):
        """Only this owned-chat instance coordinates; external mutations are unsynchronized."""
        with self._catalog_lock:
            if self._active_agents.get(agent_id, 0) or agent_id in self._configuring_agents:
                raise ChatConflict("Coordinator is busy; wait before changing its model")
            self._configuring_agents.add(agent_id)
        try:
            yield
        finally:
            with self._catalog_lock:
                self._configuring_agents.remove(agent_id)

    @contextmanager
    def _agent_request(self, agent_id):
        with self._catalog_lock:
            if agent_id in self._configuring_agents:
                raise ChatConflict("Coordinator model selection is busy; try again later")
            self._active_agents[agent_id] = self._active_agents.get(agent_id, 0) + 1
        try:
            yield
        finally:
            with self._catalog_lock:
                self._active_agents[agent_id] -= 1

    def _coordinator(self, agent_id):
        try:
            agent = self._get_agent(agent_id)
            provider = self._get_provider(agent.provider)
        except ValueError:
            raise ChatUnavailable("Coordinator or configured provider is missing") from None
        if not agent.model or not agent.model.strip():
            raise ChatUnavailable("Coordinator has no configured model")
        return agent, provider

    def start(self, owner: str, agent_id: str):
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner identity is required")
        with self._catalog_lock:
            if len(self._entries) >= self.MAX_CONVERSATIONS:
                raise ChatLimit("Conversation limit reached for this app run")
            with self.agent_request(agent_id):
                agent, provider = self._coordinator(agent_id)
                identifier = uuid4().hex
                record = self._chat.start(identifier, agent_id)
                self._entries[identifier] = _OwnedConversation(
                    owner, agent, provider, Lock()
                )
                return {
                    "conversation": record,
                    "coordinator": agent,
                    "streaming_supported": getattr(provider, "supports_streaming", False) is True,
                }

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
            return {
                "conversation": self._chat.get(identifier),
                "coordinator": entry.coordinator,
                "streaming_supported": getattr(entry.provider, "supports_streaming", False) is True,
            }

    def get_status(self, owner, identifier):
        with self._access(owner, identifier):
            return self._chat.get_status(identifier)

    def send(self, owner, identifier, text, retrieved_context=None):
        with self._access(owner, identifier) as entry:
            with self.agent_request(entry.coordinator.id):
                return self._send(entry, identifier, text, retrieved_context)

    def stream(self, owner, identifier, text, retrieved_context=None):
        with self._access(owner, identifier) as entry:
            if getattr(entry.provider, "supports_streaming", False) is not True:
                raise ChatUnavailable("The selected provider does not support response streaming")
            with self.agent_request(entry.coordinator.id):
                for event in self._chat.send_stream(identifier, text, retrieved_context):
                    if event["type"] == "complete":
                        yield {
                            **event,
                            "coordinator": entry.coordinator,
                            "streaming_supported": True,
                        }
                    else:
                        yield event

    def _send(self, entry, identifier, text, retrieved_context=None):
        current, provider = self._coordinator(entry.coordinator.id)
        if (current.provider, current.model) != (entry.coordinator.provider, entry.coordinator.model):
            raise ChatConflict("Coordinator assignment changed; start a new conversation")
        if provider is not entry.provider:
            raise ChatConflict("Coordinator connection changed; start a new conversation")
        if len(self._chat.get(identifier).messages) + 2 > self.MAX_MESSAGES:
            raise ChatLimit("Conversation message limit reached; start a new conversation")
        record = self._chat.send(identifier, text, retrieved_context)
        return {"conversation": record, "coordinator": entry.coordinator}

    def close(self, owner, identifier):
        with self._access(owner, identifier) as entry:
            return {"conversation": self._chat.close(identifier), "coordinator": entry.coordinator}

    @contextmanager
    def agent_request(self, agent_id: str):
        """Share admission guards across owned chat scopes and Agent executions."""
        with self._agent_request(agent_id):
            try:
                with self._agent_execution(agent_id):
                    yield
            except AgentAssignmentBusy:
                raise ChatConflict(
                    "Agent has active work or its connection is changing; retry shortly"
                ) from None
