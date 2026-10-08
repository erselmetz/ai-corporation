"""Principal-owned, Employee-associated chat with immutable assignment snapshots."""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock, RLock
from uuid import uuid4

from app.agents import AgentRegistry, EmployeeRegistry
from app.conversations import (
    ChatConversationSummary,
    ConversationStatus,
    EmployeeChatService,
    MessageRole,
    MessageStatus,
)
from app.orchestrator import Orchestrator
from app.providers import ProviderRegistry
from app.providers.base import ProviderCapacityError

from .owned_chat import (
    ChatConflict,
    ChatConsentRequired,
    ChatLimit,
    ChatNotFound,
    ChatUnavailable,
)


@dataclass(frozen=True)
class EmployeeChatIdentity:
    id: str
    name: str
    role: str


@dataclass(frozen=True)
class EmployeeChatAssignment:
    id: str
    name: str
    role: str
    provider_id: str
    model_id: str
    supports_streaming: bool = False


@dataclass(frozen=True)
class EmployeeChatSnapshot:
    conversation: ChatConversationSummary
    employee: EmployeeChatIdentity
    agent: EmployeeChatAssignment


@dataclass(frozen=True)
class EmployeeChatListItem:
    conversation_id: str
    employee: EmployeeChatIdentity
    agent: EmployeeChatAssignment
    status: ConversationStatus


@dataclass(frozen=True)
class _OwnedEmployeeConversation:
    owner: str
    employee: EmployeeChatIdentity
    agent: EmployeeChatAssignment
    provider: object = field(repr=False, compare=False)
    lock: Lock = field(default_factory=Lock, repr=False, compare=False)


class OwnedEmployeeChatService:
    MAX_CONVERSATIONS = 100
    MAX_MESSAGES = 200
    MAX_MESSAGE_BYTES = 8192
    MAX_PROMPT_BYTES = 32768

    def __init__(
        self,
        employees: EmployeeRegistry,
        agents: AgentRegistry,
        providers: ProviderRegistry,
        orchestrator: Orchestrator,
        agent_request,
    ):
        self._employees = employees
        self._agents = agents
        self._providers = providers
        self._orchestrator = orchestrator
        self._agent_request = agent_request
        self._chat = EmployeeChatService(employees, agents)
        self._entries: dict[str, _OwnedEmployeeConversation] = {}
        self._catalog_lock = RLock()

    def _assignment(self, agent_id: str):
        try:
            agent = self._agents.get(agent_id)
            provider = self._providers.get(agent.provider)
        except ValueError:
            raise ChatUnavailable("Assigned Agent or provider is unavailable") from None
        if not agent.model or not agent.model.strip():
            raise ChatUnavailable("Assigned Agent has no configured model")
        return (
            EmployeeChatAssignment(
                agent.id,
                agent.name,
                agent.role,
                agent.provider,
                agent.model,
                getattr(provider, "supports_streaming", False) is True,
            ),
            provider,
        )

    def start(self, owner: str, employee_id: str) -> EmployeeChatSnapshot:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner identity is required")
        if not isinstance(employee_id, str) or not employee_id.strip():
            raise ValueError("Employee identity is required")
        with self._catalog_lock:
            if len(self._entries) >= self.MAX_CONVERSATIONS:
                raise ChatLimit("Individual conversation limit reached for this app run")
            try:
                employee = self._employees.get(employee_id)
            except ValueError:
                raise ChatUnavailable("Selected Employee is unavailable") from None
            if employee.agent is None:
                raise ChatUnavailable("Selected Employee has no assigned Agent")
            selected_agent_id = employee.agent.id
            with self._agent_request(selected_agent_id):
                current = self._employees.get(employee_id)
                if current.agent is None or current.agent.id != selected_agent_id:
                    raise ChatConflict("Employee Agent assignment changed; refresh and select again")
                agent_snapshot, provider = self._assignment(selected_agent_id)
                employee_snapshot = EmployeeChatIdentity(
                    current.id, current.name, current.role
                )
                identifier = uuid4().hex
                conversation = self._chat.start_conversation(
                    identifier, employee_id=employee_id
                )
                entry = _OwnedEmployeeConversation(
                    owner, employee_snapshot, agent_snapshot, provider
                )
                self._entries[identifier] = entry
                return EmployeeChatSnapshot(conversation, employee_snapshot, agent_snapshot)

    def list(self, owner: str) -> tuple[EmployeeChatListItem, ...]:
        with self._catalog_lock:
            items = []
            for identifier, entry in self._entries.items():
                if entry.owner != owner:
                    continue
                with entry.lock:
                    conversation = self._chat.get_conversation(identifier)
                    items.append(
                        EmployeeChatListItem(
                            identifier,
                            entry.employee,
                            entry.agent,
                            conversation.status,
                        )
                    )
            return tuple(items)

    @contextmanager
    def _access(self, owner: str, identifier: str):
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

    def get(self, owner: str, identifier: str) -> EmployeeChatSnapshot:
        with self._access(owner, identifier) as entry:
            return EmployeeChatSnapshot(
                self._chat.get_conversation(identifier),
                entry.employee,
                entry.agent,
            )

    def _assert_assignment(self, entry: _OwnedEmployeeConversation) -> None:
        try:
            employee = self._employees.get(entry.employee.id)
        except ValueError:
            raise ChatConflict("Employee or assigned Agent was removed; start a new conversation") from None
        if employee.agent is None or employee.agent.id != entry.agent.id:
            raise ChatConflict("Employee Agent assignment changed; start a new conversation")
        try:
            agent = self._agents.get(entry.agent.id)
        except ValueError:
            raise ChatConflict("Employee or assigned Agent was removed; start a new conversation") from None
        if (agent.provider, agent.model) != (entry.agent.provider_id, entry.agent.model_id):
            raise ChatConflict("Agent connection changed; start a new conversation")
        try:
            provider = self._providers.get(agent.provider)
        except ValueError:
            raise ChatUnavailable("Assigned provider is no longer available") from None
        if provider is not entry.provider:
            raise ChatConflict("Agent connection changed; start a new conversation")

    def send(
        self,
        owner: str,
        identifier: str,
        text: str,
        *,
        cloud_consent: bool = False,
    ) -> EmployeeChatSnapshot:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        if len(text.encode("utf-8")) > self.MAX_MESSAGE_BYTES:
            raise ValueError("Message exceeds byte limit")
        with self._access(owner, identifier) as entry:
            with self._agent_request(entry.agent.id):
                self._assert_assignment(entry)
                conversation = self._chat.get_conversation(identifier)
                if conversation.status is not ConversationStatus.OPEN:
                    raise ValueError("Cannot send to a closed conversation")
                if (
                    (
                        entry.agent.provider_id == "gemini"
                        or getattr(
                            entry.provider, "requires_explicit_cloud_consent", False
                        ) is True
                    )
                    and cloud_consent is not True
                ):
                    raise ChatConsentRequired(
                        "Explicit consent is required before sending this turn and recent chat history to Google Gemini."
                    )
                if len(conversation.messages) + 2 > self.MAX_MESSAGES:
                    raise ChatLimit("Conversation message limit reached; start a new conversation")
                history = [
                    {"role": item.role.value, "content": item.content}
                    for item in conversation.messages[-16:]
                    if item.status is MessageStatus.COMPLETED
                ]
                prompt = json.dumps(
                    {"history": history, "request": text}, ensure_ascii=True
                )
                if len(prompt.encode("utf-8")) > self.MAX_PROMPT_BYTES:
                    raise ValueError("Prompt exceeds byte limit")
                user_id, reply_id = uuid4().hex, uuid4().hex
                self._chat.add_message(
                    identifier, user_id, MessageRole.USER, text
                )
                try:
                    reply = self._orchestrator.run_agent(entry.agent.id, prompt)
                    if not isinstance(reply, str) or not reply.strip():
                        raise ValueError("Provider returned no reply")
                    if len(reply.encode("utf-8")) > self.MAX_MESSAGE_BYTES:
                        raise ValueError("Provider reply exceeds byte limit")
                except ProviderCapacityError:
                    self._chat.transition_message(
                        identifier, user_id, MessageStatus.FAILED
                    )
                    raise
                except Exception:
                    self._chat.transition_message(
                        identifier, user_id, MessageStatus.FAILED
                    )
                    raise RuntimeError(
                        "Individual chat response failed; no automatic retry occurred"
                    ) from None
                self._chat.transition_message(
                    identifier, user_id, MessageStatus.COMPLETED
                )
                self._chat.add_message(
                    identifier, reply_id, MessageRole.ASSISTANT, reply
                )
                self._chat.transition_message(
                    identifier, reply_id, MessageStatus.COMPLETED
                )
                return EmployeeChatSnapshot(
                    self._chat.get_conversation(identifier),
                    entry.employee,
                    entry.agent,
                )

    def stream(
        self,
        owner: str,
        identifier: str,
        text: str,
        *,
        cloud_consent: bool = False,
    ):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        if len(text.encode("utf-8")) > self.MAX_MESSAGE_BYTES:
            raise ValueError("Message exceeds byte limit")
        with self._access(owner, identifier) as entry:
            if not entry.agent.supports_streaming:
                raise ChatUnavailable("The assigned provider does not support response streaming")
            with self._agent_request(entry.agent.id):
                self._assert_assignment(entry)
                conversation = self._chat.get_conversation(identifier)
                if conversation.status is not ConversationStatus.OPEN:
                    raise ValueError("Cannot send to a closed conversation")
                if (
                    entry.agent.provider_id == "gemini"
                    or getattr(entry.provider, "requires_explicit_cloud_consent", False) is True
                ) and cloud_consent is not True:
                    raise ChatConsentRequired(
                        "Explicit consent is required before sending this turn and recent chat history to Google Gemini."
                    )
                if len(conversation.messages) + 2 > self.MAX_MESSAGES:
                    raise ChatLimit("Conversation message limit reached; start a new conversation")
                history = [
                    {"role": item.role.value, "content": item.content}
                    for item in conversation.messages[-16:]
                    if item.status is MessageStatus.COMPLETED
                ]
                prompt = json.dumps(
                    {"history": history, "request": text}, ensure_ascii=True
                )
                if len(prompt.encode("utf-8")) > self.MAX_PROMPT_BYTES:
                    raise ValueError("Prompt exceeds byte limit")
                user_id, reply_id = uuid4().hex, uuid4().hex
                self._chat.add_message(identifier, user_id, MessageRole.USER, text)
                output = []
                output_bytes = 0
                try:
                    for chunk in self._orchestrator.stream_agent(
                        entry.agent.id,
                        prompt,
                        expected_assignment=(entry.agent.provider_id, entry.agent.model_id),
                    ):
                        if not isinstance(chunk, str):
                            raise ValueError("Provider returned an invalid response chunk")
                        output_bytes += len(chunk.encode("utf-8"))
                        if output_bytes > self.MAX_MESSAGE_BYTES:
                            raise ValueError("Provider reply exceeds byte limit")
                        if chunk:
                            output.append(chunk)
                            yield {"type": "chunk", "text": chunk}
                except ProviderCapacityError:
                    self._chat.transition_message(
                        identifier, user_id, MessageStatus.FAILED
                    )
                    raise
                except Exception:
                    raise RuntimeError(
                        "Individual chat response stream failed; no automatic retry occurred"
                    ) from None
                reply = "".join(output)
                if not reply.strip():
                    raise RuntimeError("Individual chat response stream was empty")
                self._chat.transition_message(
                    identifier, user_id, MessageStatus.COMPLETED
                )
                self._chat.add_message(
                    identifier, reply_id, MessageRole.ASSISTANT, reply
                )
                self._chat.transition_message(
                    identifier, reply_id, MessageStatus.COMPLETED
                )
                yield {
                    "type": "complete",
                    "snapshot": EmployeeChatSnapshot(
                        self._chat.get_conversation(identifier),
                        entry.employee,
                        entry.agent,
                    ),
                }

    def close(self, owner: str, identifier: str) -> EmployeeChatSnapshot:
        with self._access(owner, identifier) as entry:
            conversation = self._chat.close_conversation(identifier)
            return EmployeeChatSnapshot(
                conversation, entry.employee, entry.agent
            )
