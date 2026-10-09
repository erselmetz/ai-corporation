from dataclasses import dataclass

from app.agents import AgentRegistry, EmployeeRegistry

from .models import Conversation, ConversationStatus, Message, MessageRole, MessageStatus


@dataclass(frozen=True)
class ChatTarget:
    """Selected identity captured at creation; no role routing or retargeting."""

    agent_id: str
    employee_id: str | None = None

    @property
    def scope(self) -> str:
        return "employee" if self.employee_id is not None else "agent"


@dataclass(frozen=True)
class ChatMessageSummary:
    id: str
    role: MessageRole
    content: str
    status: MessageStatus


@dataclass(frozen=True)
class ChatConversationSummary:
    id: str
    target: ChatTarget
    status: ConversationStatus
    messages: tuple[ChatMessageSummary, ...]


@dataclass(frozen=True)
class _ChatSession:
    conversation: Conversation
    target: ChatTarget


class EmployeeChatService:
    """In-memory, individually scoped chat records, without response generation.

    Callers explicitly record messages and their lifecycle outcomes. This service
    does not execute Agents, invoke Providers, retrieve context, or create Tasks.
    It owns its Conversations and returns immutable snapshots of their state.
    """

    MAX_CONTEXT_BYTES = 8192

    def __init__(self, employees: EmployeeRegistry, agents: AgentRegistry):
        self._employees = employees
        self._agents = agents
        self._sessions: dict[str, _ChatSession] = {}
        self._context: dict[str, str] = {}

    def start_conversation(
        self,
        conversation_id: str,
        *,
        employee_id: str | None = None,
        agent_id: str | None = None,
    ) -> ChatConversationSummary:
        conversation = Conversation(conversation_id)
        if conversation_id in self._sessions:
            raise ValueError(f"Conversation already exists: {conversation_id}")
        if (employee_id is None) == (agent_id is None):
            raise ValueError("Select exactly one Employee or Agent")

        if employee_id is not None:
            self._validate_id(employee_id, "Employee")
            employee = self._employees.get(employee_id)
            if employee.agent is None:
                raise ValueError(f"Employee has no assigned Agent: {employee_id}")
            selected_agent_id = employee.agent.id
        else:
            # Exactly one selector is required above.
            assert agent_id is not None
            selected_agent_id = agent_id

        self._validate_id(selected_agent_id, "Agent")
        agent = self._agents.get(selected_agent_id)
        session = _ChatSession(conversation, ChatTarget(agent.id, employee_id))
        self._sessions[conversation_id] = session
        return self._summary(session)

    def get_conversation(self, conversation_id: str) -> ChatConversationSummary:
        return self._summary(self._get_session(conversation_id))

    def get_conversation_status(self, conversation_id: str) -> ConversationStatus:
        return self._get_session(conversation_id).conversation.status

    def set_context(self, conversation_id: str, content: str) -> None:
        """Replace caller-authorized context for this conversation only.

        The trusted Core caller supplies relevant, authorized text, excluding
        secrets and internal runtime data. No resources are fetched. Text is
        untrusted data, not executable instructions. Empty text clears context.
        """
        session = self._get_session(conversation_id)
        if session.conversation.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot set context on a closed conversation")
        if not isinstance(content, str):
            raise TypeError("Context must be text")
        if len(content.encode("utf-8")) > self.MAX_CONTEXT_BYTES:
            raise ValueError("Context exceeds byte limit")
        if content:
            self._context[conversation_id] = content
        else:
            self._context.pop(conversation_id, None)

    def get_context(self, conversation_id: str) -> str:
        """Read current context; the trusted caller enforces access externally.

        Context is intentionally excluded from conversation snapshots so old
        snapshots do not retain it after replacement or successful closure.
        """
        self._get_session(conversation_id)
        return self._context.get(conversation_id, "")

    def add_message(
        self,
        conversation_id: str,
        message_id: str,
        role: MessageRole,
        content: str,
    ) -> ChatConversationSummary:
        session = self._get_session(conversation_id)
        session.conversation.add_message(Message(message_id, role, content))
        return self._summary(session)

    def transition_message(
        self,
        conversation_id: str,
        message_id: str,
        status: MessageStatus,
    ) -> ChatConversationSummary:
        session = self._get_session(conversation_id)
        self._validate_id(message_id, "Message")
        session.conversation.get_message(message_id).transition(status)
        return self._summary(session)

    def close_conversation(self, conversation_id: str) -> ChatConversationSummary:
        session = self._get_session(conversation_id)
        session.conversation.close()
        self._context.pop(conversation_id, None)
        return self._summary(session)

    def _get_session(self, conversation_id: str) -> _ChatSession:
        self._validate_id(conversation_id, "Conversation")
        try:
            return self._sessions[conversation_id]
        except KeyError:
            raise ValueError(f"Conversation not found: {conversation_id}") from None

    @staticmethod
    def _validate_id(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} id cannot be empty")

    @staticmethod
    def _summary(session: _ChatSession) -> ChatConversationSummary:
        conversation = session.conversation
        return ChatConversationSummary(
            id=conversation.id,
            target=session.target,
            status=conversation.status,
            messages=tuple(
                ChatMessageSummary(message.id, message.role, message.content, message.status)
                for message in conversation.messages
            ),
        )
