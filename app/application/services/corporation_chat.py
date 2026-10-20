from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import uuid4

from app.agents import EmployeeRegistry
from app.conversations import ChatMessageSummary, EmployeeChatService, MessageRole, MessageStatus, ConversationStatus
from app.orchestrator import Orchestrator
from app.orchestrator.task import TaskStatus
from app.providers.base import ProviderCapacityError
from app.chat_prompt import build_chat_messages
from .chat_history import ChatHistoryError

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
        self.history = None

    def _durable(self, conversation_id):
        return self.history is not None and self.history.is_active(conversation_id)

    def _remember(self, conversation_id, message_id, role, content, status):
        if self._durable(conversation_id):
            self.history.record_message(conversation_id, message_id, role.value, content, status.value,
                                        datetime.now(timezone.utc))

    def _remember_status(self, conversation_id, message_id, status, *, strict):
        if not self._durable(conversation_id):
            return
        try:
            self.history.update_status(conversation_id, message_id, status.value)
        except ChatHistoryError:
            if strict:
                raise

    def start(self, conversation_id: str, coordinator_agent_id: str):
        self._chat.start_conversation(conversation_id, agent_id=coordinator_agent_id)
        return self.get(conversation_id)

    def get(self, conversation_id: str):
        record = self._chat.get_conversation(conversation_id)
        return CorporationConversationSummary(
            record.id, self._corporation_id, record.target.agent_id,
            record.status, record.messages,
        )

    def get_status(self, conversation_id: str) -> ConversationStatus:
        return self._chat.get_conversation_status(conversation_id)

    def close(self, conversation_id: str):
        self._chat.close_conversation(conversation_id)
        if self._durable(conversation_id):
            self.history.close(conversation_id)
        return self.get(conversation_id)

    def delete(self, owner_id: str, conversation_id: str):
        """Delete this owner's live conversation and any explicitly retained copy."""
        record = self.get(conversation_id)
        if any(message.status is MessageStatus.PENDING for message in record.messages):
            raise ValueError("Cannot delete a conversation with a pending message")
        if self._durable(conversation_id):
            self.history.delete(owner_id, conversation_id)
        self._chat.delete_conversation(conversation_id)
        related_reviews = [identifier for identifier, review in self._reviews.items()
                           if review.conversation_id == conversation_id]
        for identifier in related_reviews:
            self._reviews.pop(identifier, None)
            self._used_reviews.discard(identifier)
        return {"deleted": record.id}

    def retain_message(self, conversation_id: str, message_id: str, *, memory_id: str,
                       owner_id: str, expires_at, now, retention_opt_in: bool = False):
        """Explicit trusted-local retention; never called automatically by send."""
        from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
        record = self.get(conversation_id)
        source = next((m for m in record.messages if m.id == message_id), None)
        if source is None or source.status is not MessageStatus.COMPLETED:
            raise ValueError("Only completed conversation messages can be retained")
        memory = MemoryRecord(memory_id, owner_id, MemoryScope.CONVERSATION,
                              conversation_id, MemoryType.NOTE, source.content,
                              source.id, now, expires_at, retention_opt_in)
        ConversationMemoryStore().retain(memory, now=now)
        return memory

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

    def send(self, conversation_id: str, text: str, retrieved_context=None, presentation_preferences=None,
             tool_context=None,
             prompt_observer=None, turn_route: tuple[str, str] | None = None,
             expected_assignment: tuple[str, str] | None = None, brain_enabled: bool = False):
        record = self.get(conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot send to a closed conversation")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        if len(text.encode("utf-8")) > 8192:
            raise ValueError("Message exceeds byte limit")
        if brain_enabled and retrieved_context is None:
            return self.complete_without_provider(
                conversation_id, text, "I couldn't find relevant information about that in your Brain.")
        history = [{"role": m.role.value, "content": m.content}
                   for m in record.messages[-16:] if m.status is MessageStatus.COMPLETED]
        messages = build_chat_messages(
            text, history, retrieved_context=retrieved_context,
            tool_context=tool_context,
            presentation_preferences=presentation_preferences,
            brain_enabled=brain_enabled,
        )
        prompt = json.dumps(messages, ensure_ascii=True, separators=(",", ":"))
        if len(prompt.encode("utf-8")) > self.MAX_PROMPT_BYTES:
            raise ValueError("Prompt exceeds byte limit")
        if prompt_observer is not None:
            prompt_observer(prompt)
        user_id, reply_id = uuid4().hex, uuid4().hex
        self._chat.add_message(conversation_id, user_id, MessageRole.USER, text)
        try:
            self._remember(conversation_id, user_id, MessageRole.USER, text, MessageStatus.PENDING)
        except ChatHistoryError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            raise
        try:
            if turn_route is None:
                reply = self._orchestrator.run_agent_chat(record.coordinator_agent_id, messages)
            else:
                if expected_assignment is None:
                    raise ValueError("The configured Agent assignment snapshot is required")
                reply = self._orchestrator.run_agent_chat_for_turn(
                    record.coordinator_agent_id, messages,
                    provider_id=turn_route[0], model_id=turn_route[1],
                    expected_assignment=expected_assignment,
                )
            if not isinstance(reply, str) or not reply.strip():
                raise ValueError("Provider returned no reply")
            if len(reply.encode("utf-8")) > 8192:
                raise ValueError("Provider reply exceeds byte limit")
        except ProviderCapacityError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            self._remember_status(conversation_id, user_id, MessageStatus.FAILED, strict=False)
            raise
        except Exception:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            self._remember_status(conversation_id, user_id, MessageStatus.FAILED, strict=False)
            raise RuntimeError("Corporation chat response failed") from None
        self._chat.transition_message(conversation_id, user_id, MessageStatus.COMPLETED)
        self._chat.add_message(conversation_id, reply_id, MessageRole.ASSISTANT, reply)
        self._chat.transition_message(conversation_id, reply_id, MessageStatus.COMPLETED)
        self._remember(conversation_id, reply_id, MessageRole.ASSISTANT, reply, MessageStatus.COMPLETED)
        self._remember_status(conversation_id, user_id, MessageStatus.COMPLETED, strict=True)
        return self.get(conversation_id)

    def complete_without_provider(self, conversation_id: str, text: str, reply: str):
        """Record a deterministic local response when Brain retrieval found no excerpt."""
        record = self.get(conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot send to a closed conversation")
        if (not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 8192
                or not isinstance(reply, str) or not reply.strip() or len(reply.encode("utf-8")) > 8192):
            raise ValueError("Local chat response is outside the supported bounds")
        user_id, reply_id = uuid4().hex, uuid4().hex
        self._chat.add_message(conversation_id, user_id, MessageRole.USER, text)
        try:
            self._remember(conversation_id, user_id, MessageRole.USER, text, MessageStatus.PENDING)
        except ChatHistoryError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            raise
        self._chat.transition_message(conversation_id, user_id, MessageStatus.COMPLETED)
        self._chat.add_message(conversation_id, reply_id, MessageRole.ASSISTANT, reply)
        self._chat.transition_message(conversation_id, reply_id, MessageStatus.COMPLETED)
        self._remember(conversation_id, reply_id, MessageRole.ASSISTANT, reply, MessageStatus.COMPLETED)
        self._remember_status(conversation_id, user_id, MessageStatus.COMPLETED, strict=True)
        return self.get(conversation_id)

    def send_with_images(self, conversation_id: str, text: str, images, *, ocr_evidence=(), presentation_preferences=None):
        """One explicitly consented multimodal turn; image bytes never enter history."""
        record = self.get(conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot send to a closed conversation")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        if len(text.encode("utf-8")) > 8192:
            raise ValueError("Message exceeds byte limit")
        if not isinstance(images, tuple) or not 1 <= len(images) <= 4:
            raise ValueError("Select one to four images")
        if sum(image.size_bytes for image in images) > 8 * 1024 * 1024:
            raise ValueError("Selected images exceed the combined byte limit")
        history = [{"role": m.role.value, "content": m.content}
                   for m in record.messages[-16:] if m.status is MessageStatus.COMPLETED]
        image_digests = {image.id: image.sha256 for image in images}
        safe_ocr = tuple(result for result in ocr_evidence
                         if result.image_id in image_digests
                         and result.source_sha256 == image_digests[result.image_id]
                         and result.untrusted is True)
        ocr_context = None
        if safe_ocr:
            ocr_context = "\n\n".join(
                f"Image text ({result.status.value}):\n" + "\n".join(region.text for region in result.regions)
                for result in safe_ocr if result.regions
            ) or None
        messages = build_chat_messages(
            text, history, ocr_context=ocr_context,
            presentation_preferences=presentation_preferences,
        )
        prompt = json.dumps(messages, ensure_ascii=True, separators=(",", ":"))
        if len(prompt.encode("utf-8")) > self.MAX_PROMPT_BYTES:
            raise ValueError("Prompt exceeds byte limit")
        user_id, reply_id = uuid4().hex, uuid4().hex
        self._chat.add_message(conversation_id, user_id, MessageRole.USER, text)
        try:
            self._remember(conversation_id, user_id, MessageRole.USER, text, MessageStatus.PENDING)
        except ChatHistoryError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            raise
        try:
            assigned = self._orchestrator.agents.get(record.coordinator_agent_id)
            reply = self._orchestrator.run_agent_chat_with_images(
                record.coordinator_agent_id, messages, images, ocr_evidence=ocr_evidence,
                expected_assignment=(assigned.provider, assigned.model),
            )
            if not isinstance(reply, str) or not reply.strip() or len(reply.encode("utf-8")) > 8192:
                raise ValueError("Provider returned no bounded reply")
        except ProviderCapacityError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            self._remember_status(conversation_id, user_id, MessageStatus.FAILED, strict=False)
            raise
        except Exception:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            self._remember_status(conversation_id, user_id, MessageStatus.FAILED, strict=False)
            raise RuntimeError("Corporation chat response failed") from None
        self._chat.transition_message(conversation_id, user_id, MessageStatus.COMPLETED)
        self._chat.add_message(conversation_id, reply_id, MessageRole.ASSISTANT, reply)
        self._chat.transition_message(conversation_id, reply_id, MessageStatus.COMPLETED)
        self._remember(conversation_id, reply_id, MessageRole.ASSISTANT, reply, MessageStatus.COMPLETED)
        self._remember_status(conversation_id, user_id, MessageStatus.COMPLETED, strict=True)
        return self.get(conversation_id)

    def send_stream(self, conversation_id: str, text: str, retrieved_context=None, presentation_preferences=None,
                    *, brain_enabled: bool = False):
        record = self.get(conversation_id)
        if record.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot send to a closed conversation")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Message text is required")
        if len(text.encode("utf-8")) > 8192:
            raise ValueError("Message exceeds byte limit")
        if brain_enabled and retrieved_context is None:
            completed = self.complete_without_provider(
                conversation_id, text, "I couldn't find relevant information about that in your Brain.")
            yield {"type": "complete", "conversation": completed}
            return
        history = [
            {"role": message.role.value, "content": message.content}
            for message in record.messages[-16:]
            if message.status is MessageStatus.COMPLETED
        ]
        messages = build_chat_messages(
            text, history, retrieved_context=retrieved_context,
            presentation_preferences=presentation_preferences,
            brain_enabled=brain_enabled,
        )
        prompt = json.dumps(messages, ensure_ascii=True, separators=(",", ":"))
        if len(prompt.encode("utf-8")) > self.MAX_PROMPT_BYTES:
            raise ValueError("Prompt exceeds byte limit")
        user_id, reply_id = uuid4().hex, uuid4().hex
        self._chat.add_message(conversation_id, user_id, MessageRole.USER, text)
        try:
            self._remember(
                conversation_id, user_id, MessageRole.USER, text, MessageStatus.PENDING
            )
        except ChatHistoryError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            raise

        output = []
        output_bytes = 0
        try:
            for chunk in self._orchestrator.stream_agent_chat(
                record.coordinator_agent_id, messages
            ):
                if not isinstance(chunk, str):
                    raise ValueError("Provider returned an invalid response chunk")
                output_bytes += len(chunk.encode("utf-8"))
                if output_bytes > 8192:
                    raise ValueError("Provider reply exceeds byte limit")
                if chunk:
                    output.append(chunk)
                    yield {"type": "chunk", "text": chunk}
        except ProviderCapacityError:
            self._chat.transition_message(conversation_id, user_id, MessageStatus.FAILED)
            self._remember_status(
                conversation_id, user_id, MessageStatus.FAILED, strict=False
            )
            raise
        except Exception:
            raise RuntimeError("Corporation chat response stream failed") from None

        reply = "".join(output)
        if not reply.strip():
            raise RuntimeError("Corporation chat response stream was empty")
        self._chat.transition_message(conversation_id, user_id, MessageStatus.COMPLETED)
        self._chat.add_message(conversation_id, reply_id, MessageRole.ASSISTANT, reply)
        self._chat.transition_message(conversation_id, reply_id, MessageStatus.COMPLETED)
        self._remember(
            conversation_id, reply_id, MessageRole.ASSISTANT, reply, MessageStatus.COMPLETED
        )
        self._remember_status(conversation_id, user_id, MessageStatus.COMPLETED, strict=True)
        yield {
            "type": "complete",
            "conversation": self.get(conversation_id),
        }
