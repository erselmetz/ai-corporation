from dataclasses import dataclass, field
from enum import Enum


class ConversationStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


_MESSAGE_TRANSITIONS: dict[MessageStatus, set[MessageStatus]] = {
    MessageStatus.PENDING: {MessageStatus.COMPLETED, MessageStatus.FAILED},
    MessageStatus.COMPLETED: set(),
    MessageStatus.FAILED: set(),
}


@dataclass
class Message:
    id: str
    role: MessageRole
    content: str
    _status: MessageStatus = field(
        default=MessageStatus.PENDING,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Message id cannot be empty")
        if not isinstance(self.role, MessageRole):
            raise TypeError("Message role must be a MessageRole")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Message content cannot be empty")

    @property
    def status(self) -> MessageStatus:
        return self._status

    def transition(self, status: MessageStatus) -> None:
        if not isinstance(status, MessageStatus):
            raise TypeError("Message status must be a MessageStatus")
        if status not in _MESSAGE_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid message transition: {self.status.value} -> {status.value}"
            )
        self._status = status


@dataclass
class Conversation:
    id: str
    _status: ConversationStatus = field(
        default=ConversationStatus.OPEN,
        init=False,
        repr=False,
    )
    _messages: list[Message] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Conversation id cannot be empty")

    @property
    def status(self) -> ConversationStatus:
        return self._status

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def add_message(self, message: Message) -> None:
        if self.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot add a message to a closed conversation")
        if not isinstance(message, Message):
            raise TypeError("Only Message instances can be added to a conversation")
        if any(existing.id == message.id for existing in self._messages):
            raise ValueError(f"Message already exists in conversation: {message.id}")
        self._messages.append(message)

    def get_message(self, message_id: str) -> Message:
        for message in self._messages:
            if message.id == message_id:
                return message
        raise ValueError(f"Message not found in conversation: {message_id}")

    def close(self) -> None:
        if self.status is not ConversationStatus.OPEN:
            raise ValueError("Conversation is already closed")
        if any(message.status is MessageStatus.PENDING for message in self._messages):
            raise ValueError("Cannot close a conversation with pending messages")
        self._status = ConversationStatus.CLOSED
