from dataclasses import dataclass
import json
from uuid import uuid4

from app.agents import EmployeeRegistry
from app.conversations import ChatMessageSummary, EmployeeChatService, MessageRole, MessageStatus, ConversationStatus
from app.orchestrator import Orchestrator
from app.orchestrator.task import TaskStatus


@dataclass(frozen=True)
class CorporationConversationSummary:
    id: str
    corporation_id: str
    coordinator_agent_id: str
    status: ConversationStatus
    messages: tuple[ChatMessageSummary, ...]


@dataclass(frozen=True)
class ChatTaskReview:
    id: str
    conversation_id: str
    message_id: str
    title: str
    description: str
    project_id: str
    agent_id: str


@dataclass(frozen=True)
class ChatTaskCreation:
    task_id: str
    status: TaskStatus
    project_id: str
    agent_id: str
    review_id: str


class CorporationChatService:
    """Trusted local organization chat; explicit coordinator, no task execution."""

    MAX_PROMPT_BYTES = 32768

    def __init__(self, corporation_id: str, orchestrator: Orchestrator):
        if not isinstance(corporation_id, str) or not corporation_id.strip():
            raise ValueError("Corporation id is required")
        self._corporation_id = corporation_id
        self._orchestrator = orchestrator
        self._reviews: dict[str, ChatTaskReview] = {}
        self._used_reviews: set[str] = set()
        self._chat = EmployeeChatService(EmployeeRegistry(), orchestrator.agents)

    def start(self, conversation_id: str, coordinator_agent_id: str):
        self._chat.start_conversation(conversation_id, agent_id=coordinator_agent_id)
        return self.get(conversation_id)

    def get(self, conversation_id: str):
        record = self._chat.get_conversation(conversation_id)
        return CorporationConversationSummary(
            record.id, self._corporation_id, record.target.agent_id,
            record.status, record.messages,
        )

    def close(self, conversation_id: str):
        self._chat.close_conversation(conversation_id)
        return self.get(conversation_id)

    def review_task(self, conversation_id: str, message_id: str, title: str,
                    project_id: str, agent_id: str) -> ChatTaskReview:
        """Prepare immutable fields for local human review; never create a Task."""
        record = self.get(conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot review a closed conversation")
        if not isinstance(title, str) or not title.strip() or len(title.encode("utf-8")) > 1024:
            raise ValueError("Task title is required and limited to 1024 bytes")
        message = next((m for m in record.messages if m.id == message_id), None)
        if message is None or message.role is not MessageRole.USER or message.status is not MessageStatus.COMPLETED:
            raise ValueError("Task source must be a completed user message")
        self._orchestrator.projects.get(project_id)
        self._orchestrator.agents.get(agent_id)
        review = ChatTaskReview(uuid4().hex, conversation_id, message_id, title,
                               message.content, project_id, agent_id)
        self._reviews[review.id] = review
        return review

    def confirm_task(self, review_id: str, *, confirmed: bool = False) -> ChatTaskCreation:
        """Explicit local human confirmation creates a pending Task, never runs it.

        Each review is consumed before creation so partial persistence/logging
        failures cannot be retried into duplicate Tasks. Human inspection is
        required after such a failure; this is not a transactional recovery API.
        """
        if confirmed is not True:
            raise ValueError("Explicit human confirmation is required")
        if review_id not in self._reviews or review_id in self._used_reviews:
            raise ValueError("Task review missing or already consumed")
        review = self._reviews[review_id]
        record = self.get(review.conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot confirm a closed conversation")
        self._orchestrator.projects.get(review.project_id)
        self._orchestrator.agents.get(review.agent_id)
        self._used_reviews.add(review_id)
        task = self._orchestrator.create_task(
            review.title, review.description, review.project_id, agent_id=review.agent_id)
        return ChatTaskCreation(task.id, task.status, review.project_id,
                                review.agent_id, review.id)

    def send(self, conversation_id: str, text: str):
        record = self.get(conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot send to a closed conversation")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        if len(text.encode("utf-8")) > 8192:
            raise ValueError("Message exceeds byte limit")
        history = [{"role": m.role.value, "content": m.content}
                   for m in record.messages[-16:] if m.status is MessageStatus.COMPLETED]
        prompt = json.dumps({"corporation_id": self._corporation_id,
                             "context": self._chat.get_context(conversation_id),
                             "history": history, "request": text}, ensure_ascii=True)
        if len(prompt.encode("utf-8")) > self.MAX_PROMPT_BYTES:
            raise ValueError("Prompt exceeds byte limit")
        user_id, reply_id = uuid4().hex, uuid4().hex
        self._chat.add_message(conversation_id, user_id, MessageRole.USER, text)
        try:
            reply = self._orchestrator.run_agent(record.coordinator_agent_id, prompt)
            if not isinstance(reply, str) or not reply.strip():
                raise ValueError("Provider returned no reply")
            if len(reply.encode("utf-8")) > 8192:
                raise ValueError("Provider reply exceeds byte limit")
        except Exception:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            raise RuntimeError("Corporation chat response failed") from None
        self._chat.transition_message(conversation_id, user_id, MessageStatus.COMPLETED)
        self._chat.add_message(conversation_id, reply_id, MessageRole.ASSISTANT, reply)
        self._chat.transition_message(conversation_id, reply_id, MessageStatus.COMPLETED)
        return self.get(conversation_id)
