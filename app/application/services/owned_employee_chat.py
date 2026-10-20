"""Principal-owned, Employee-associated chat with immutable assignment snapshots."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
from app.chat_prompt import build_chat_messages

from .owned_chat import (
    ChatConflict,
    ChatConsentRequired,
    ChatLimit,
    ChatNotFound,
    ChatStorageError,
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
    history_retained: bool = False
    read_only: bool = False


@dataclass(frozen=True)
class EmployeeChatListItem:
    conversation_id: str
    employee: EmployeeChatIdentity
    agent: EmployeeChatAssignment
    status: ConversationStatus
    history_retained: bool = False
    read_only: bool = False


@dataclass(frozen=True)
class _OwnedEmployeeConversation:
    owner: str
    employee: EmployeeChatIdentity
    agent: EmployeeChatAssignment
    provider: object = field(repr=False, compare=False)
    history_retained: bool = False
    read_only: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
        *,
        persistence=None,
    ):
        self._employees = employees
        self._agents = agents
        self._providers = providers
        self._orchestrator = orchestrator
        self._agent_request = agent_request
        self._chat = EmployeeChatService(employees, agents)
        self._entries: dict[str, _OwnedEmployeeConversation] = {}
        self._catalog_lock = RLock()
        self._persistence = persistence
        self._restored_owners: set[str] = set()

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

    def start(self, owner: str, employee_id: str, *, history_opt_in: bool = False) -> EmployeeChatSnapshot:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner identity is required")
        if not isinstance(employee_id, str) or not employee_id.strip():
            raise ValueError("Employee identity is required")
        if type(history_opt_in) is not bool:
            raise ValueError("Conversation history choice must be explicit")
        with self._catalog_lock:
            self._restore_owner(owner)
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
                    owner, employee_snapshot, agent_snapshot, provider,
                    history_retained=history_opt_in,
                )
                self._entries[identifier] = entry
                snapshot = EmployeeChatSnapshot(
                    conversation, employee_snapshot, agent_snapshot,
                    history_retained=history_opt_in,
                )
                try:
                    self._persist(entry, snapshot)
                except Exception:
                    self._entries.pop(identifier, None)
                    self._chat.discard_restored_conversation(identifier)
                    raise ChatStorageError("Conversation state could not be stored; no provider request was made") from None
                return snapshot

    def list(self, owner: str) -> tuple[EmployeeChatListItem, ...]:
        with self._catalog_lock:
            self._restore_owner(owner)
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
                            entry.history_retained,
                            entry.read_only,
                        )
                    )
            return tuple(items)

    @contextmanager
    def _access(self, owner: str, identifier: str):
        with self._catalog_lock:
            self._restore_owner(owner)
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
                history_retained=entry.history_retained,
                read_only=entry.read_only,
            )

    def delete_history(self, owner: str, identifier: str) -> None:
        with self._access(owner, identifier) as entry:
            if not entry.history_retained or self._persistence is None:
                raise ChatNotFound("Retained conversation not found")
            try:
                self._persistence.delete_conversation(owner, identifier)
            except Exception:
                raise ChatStorageError("Retained conversation history could not be deleted") from None
            with self._catalog_lock:
                self._entries.pop(identifier, None)
                self._chat.discard_restored_conversation(identifier)

    def _restore_owner(self, owner: str) -> None:
        if self._persistence is None or owner in self._restored_owners:
            self._restored_owners.add(owner)
            return
        try:
            records = self._persistence.load_conversations(owner)
        except Exception:
            raise ChatStorageError("Stored Employee conversation history is unavailable") from None
        restored_ids = []
        for record in records:
            try:
                conversation = record["conversation"]
                employee = EmployeeChatIdentity(**record["employee"])
                agent = EmployeeChatAssignment(**record["agent"])
                if any(not isinstance(value, str) or not value.strip() or len(value) > 256
                       for value in (employee.id, employee.name, employee.role,
                                     agent.id, agent.name, agent.role,
                                     agent.provider_id, agent.model_id)):
                    raise ValueError
                if type(agent.supports_streaming) is not bool:
                    raise ValueError
                if len(conversation["messages"]) > self.MAX_MESSAGES:
                    raise ValueError
                messages = tuple((item["id"], MessageRole(item["role"]), item["content"],
                                  MessageStatus(item["status"]))
                                 for item in conversation["messages"])
                if any(not isinstance(message_id, str) or not message_id.strip()
                       or len(message_id) > 256 or not isinstance(content, str)
                       or not content.strip() or len(content.encode("utf-8")) > self.MAX_MESSAGE_BYTES
                       for message_id, _role, content, _status in messages):
                    raise ValueError
                restored = self._chat.restore_conversation(
                    conversation["id"], employee_id=employee.id,
                    agent_id=agent.id, status=ConversationStatus(conversation["status"]),
                    messages=messages,
                )
                created_at = datetime.fromisoformat(record["created_at"])
                if created_at.tzinfo is None:
                    raise ValueError
                self._entries[restored.id] = _OwnedEmployeeConversation(
                    owner, employee, agent, None, history_retained=True,
                    read_only=True, created_at=created_at,
                )
                restored_ids.append(restored.id)
            except Exception:
                for conversation_id in restored_ids:
                    self._entries.pop(conversation_id, None)
                    self._chat.discard_restored_conversation(conversation_id)
                raise ChatStorageError("Stored Employee conversation failed validation; no history was loaded") from None
        self._restored_owners.add(owner)

    def _persist(self, entry: _OwnedEmployeeConversation, snapshot: EmployeeChatSnapshot) -> None:
        if not entry.history_retained or self._persistence is None:
            return
        conversation = snapshot.conversation
        try:
            self._persistence.save_conversation(
                owner_id=entry.owner,
                conversation_id=conversation.id,
                created_at=entry.created_at,
                record={
                "created_at": entry.created_at.isoformat(),
                "employee": {
                    "id": entry.employee.id, "name": entry.employee.name,
                    "role": entry.employee.role,
                },
                "agent": {
                    "id": entry.agent.id, "name": entry.agent.name,
                    "role": entry.agent.role, "provider_id": entry.agent.provider_id,
                    "model_id": entry.agent.model_id,
                    "supports_streaming": entry.agent.supports_streaming,
                },
                "conversation": {
                    "id": conversation.id,
                    "status": conversation.status.value,
                    "messages": [{
                        "id": item.id, "role": item.role.value,
                        "content": item.content, "status": item.status.value,
                    } for item in conversation.messages],
                },
                },
            )
        except Exception:
            raise ChatStorageError("Conversation history could not be saved; inspect its status before resending") from None

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
            if entry.read_only:
                raise ChatConflict("Recovered history is read-only; start a new conversation to continue")
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
                messages = build_chat_messages(text, history)
                if sum(len(message["content"].encode("utf-8")) for message in messages) > self.MAX_PROMPT_BYTES:
                    raise ValueError("Prompt exceeds byte limit")
                user_id, reply_id = uuid4().hex, uuid4().hex
                self._chat.add_message(
                    identifier, user_id, MessageRole.USER, text
                )
                self._persist_current(entry, identifier)
                try:
                    reply = self._orchestrator.run_agent_chat(entry.agent.id, messages)
                    if not isinstance(reply, str) or not reply.strip():
                        raise ValueError("Provider returned no reply")
                    if len(reply.encode("utf-8")) > self.MAX_MESSAGE_BYTES:
                        raise ValueError("Provider reply exceeds byte limit")
                except ProviderCapacityError:
                    self._chat.transition_message(
                        identifier, user_id, MessageStatus.FAILED
                    )
                    self._persist_current(entry, identifier)
                    raise
                except Exception:
                    self._chat.transition_message(
                        identifier, user_id, MessageStatus.FAILED
                    )
                    self._persist_current(entry, identifier)
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
                self._persist_current(entry, identifier)
                return EmployeeChatSnapshot(
                    self._chat.get_conversation(identifier),
                    entry.employee,
                    entry.agent,
                    history_retained=entry.history_retained,
                    read_only=entry.read_only,
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
            if entry.read_only:
                raise ChatConflict("Recovered history is read-only; start a new conversation to continue")
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
                messages = build_chat_messages(text, history)
                if sum(len(message["content"].encode("utf-8")) for message in messages) > self.MAX_PROMPT_BYTES:
                    raise ValueError("Prompt exceeds byte limit")
                user_id, reply_id = uuid4().hex, uuid4().hex
                self._chat.add_message(identifier, user_id, MessageRole.USER, text)
                self._persist_current(entry, identifier)
                output = []
                output_bytes = 0
                try:
                    for chunk in self._orchestrator.stream_agent_chat(
                        entry.agent.id,
                        messages,
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
                    self._persist_current(entry, identifier)
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
                self._persist_current(entry, identifier)
                yield {
                    "type": "complete",
                    "snapshot": EmployeeChatSnapshot(
                        self._chat.get_conversation(identifier),
                        entry.employee,
                        entry.agent,
                        history_retained=entry.history_retained,
                        read_only=entry.read_only,
                    ),
                }

    def close(self, owner: str, identifier: str) -> EmployeeChatSnapshot:
        with self._access(owner, identifier) as entry:
            if entry.read_only:
                raise ChatConflict("Recovered history is read-only; delete it or start a new conversation")
            conversation = self._chat.close_conversation(identifier)
            self._persist(entry, EmployeeChatSnapshot(
                conversation, entry.employee, entry.agent,
                history_retained=entry.history_retained,
            ))
            return EmployeeChatSnapshot(
                conversation, entry.employee, entry.agent,
                history_retained=entry.history_retained,
            )

    def _persist_current(self, entry: _OwnedEmployeeConversation, identifier: str) -> None:
        self._persist(entry, EmployeeChatSnapshot(
            self._chat.get_conversation(identifier), entry.employee, entry.agent,
            history_retained=entry.history_retained,
            read_only=entry.read_only,
        ))
