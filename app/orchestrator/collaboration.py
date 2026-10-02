"""Bounded, caller-driven Agent handoffs without Provider execution."""

from dataclasses import dataclass
from enum import Enum
import json
from threading import RLock

from app.agents import AgentRegistry
from app.database import TaskLogger
from app.orchestrator.task import TaskStatus
from app.orchestrator.task_registry import TaskRegistry
from app.resources.manager import identifier


class CollaborationStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class CollaborationEventType(Enum):
    INITIAL_CONTEXT = "initial_context"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    FAILED = "failed"


class CollaborationFailureReason(Enum):
    PARTICIPANT_DECLINED = "participant_declined"
    BLOCKED = "blocked"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True, slots=True)
class CollaborationParticipant:
    agent_id: str
    role: str

    def __post_init__(self):
        identifier(self.agent_id)
        _validate_text(self.role, "role", 256, allow_empty=False)


@dataclass(frozen=True, slots=True)
class CollaborationEvent:
    sequence: int
    type: CollaborationEventType
    agent_id: str | None
    role: str | None
    recipient_agent_id: str | None
    content: str
    failure_reason: CollaborationFailureReason | None = None


@dataclass(frozen=True, slots=True)
class CollaborationSnapshot:
    collaboration_id: str
    task_id: str
    participants: tuple[CollaborationParticipant, ...]
    status: CollaborationStatus
    active_agent_id: str | None
    events: tuple[CollaborationEvent, ...]
    failure_reason: CollaborationFailureReason | None = None


class TaskCollaborationService:
    """Explicit, record-only collaboration owned by a trusted application caller."""

    MAX_PARTICIPANTS = 10
    MAX_ENTRY_BYTES = 8192
    MAX_CONTEXT_BYTES = 32768

    def __init__(
        self,
        *,
        agents: AgentRegistry,
        tasks: TaskRegistry,
        logger: TaskLogger,
    ):
        self._agents = agents
        self._tasks = tasks
        self._logger = logger
        self._sessions: dict[str, CollaborationSnapshot] = {}
        self._lock = RLock()

    def start(
        self,
        collaboration_id: str,
        task_id: str,
        participants: tuple[CollaborationParticipant, ...],
        initial_context: str,
    ) -> CollaborationSnapshot:
        identifier(collaboration_id)
        identifier(task_id)
        if not isinstance(participants, tuple) or not 2 <= len(participants) <= self.MAX_PARTICIPANTS:
            raise ValueError("Supply an immutable tuple of 2 to 10 collaboration participants")
        if not all(isinstance(item, CollaborationParticipant) for item in participants):
            raise TypeError("Expected CollaborationParticipant")
        if len({item.agent_id for item in participants}) != len(participants):
            raise ValueError("An Agent may participate only once")
        _validate_text(initial_context, "initial_context", self.MAX_ENTRY_BYTES)
        if len(initial_context.encode("utf-8")) > self.MAX_CONTEXT_BYTES:
            raise ValueError("Initial context exceeds collaboration context limit")

        with self._lock:
            if collaboration_id in self._sessions:
                raise ValueError(f"Collaboration already exists: {collaboration_id}")
            task = self._tasks.get(task_id)
            if task.status is not TaskStatus.PENDING:
                raise ValueError("Collaboration requires a pending Task")
            registered: list[CollaborationParticipant] = []
            for participant in participants:
                agent = self._agents.get(participant.agent_id)
                if agent.role != participant.role:
                    raise ValueError(
                        f"Participant role does not match registered Agent: {participant.agent_id}"
                    )
                registered.append(participant)
            snapshot = CollaborationSnapshot(
                collaboration_id=collaboration_id,
                task_id=task_id,
                participants=tuple(registered),
                status=CollaborationStatus.ACTIVE,
                active_agent_id=registered[0].agent_id,
                events=(
                    CollaborationEvent(
                        sequence=0,
                        type=CollaborationEventType.INITIAL_CONTEXT,
                        agent_id=None,
                        role=None,
                        recipient_agent_id=registered[0].agent_id,
                        content=initial_context,
                    ),
                ),
            )
            self._audit(
                task_id,
                "COLLABORATION_STARTED",
                collaboration_id,
                {"participants": [item.agent_id for item in registered]},
            )
            self._sessions[collaboration_id] = snapshot
            return snapshot

    def handoff(
        self,
        collaboration_id: str,
        acting_agent_id: str,
        recipient_agent_id: str,
        content: str,
    ) -> CollaborationSnapshot:
        _validate_id(collaboration_id, "Collaboration")
        _validate_id(acting_agent_id, "Agent")
        _validate_id(recipient_agent_id, "Agent")
        _validate_text(content, "content", self.MAX_ENTRY_BYTES, allow_empty=False)
        with self._lock:
            snapshot = self._active_session(collaboration_id, acting_agent_id)
            self._require_pending_task(snapshot.task_id)
            index = self._participant_index(snapshot, acting_agent_id)
            if index == len(snapshot.participants) - 1:
                raise ValueError("Final participant must complete or fail collaboration")
            expected_recipient = snapshot.participants[index + 1].agent_id
            if recipient_agent_id != expected_recipient:
                raise ValueError("Handoff recipient must be the next listed participant")
            self._validate_context_size(snapshot, content)
            participant = snapshot.participants[index]
            event = CollaborationEvent(
                len(snapshot.events),
                CollaborationEventType.HANDOFF,
                participant.agent_id,
                participant.role,
                expected_recipient,
                content,
            )
            self._audit(
                snapshot.task_id,
                "COLLABORATION_HANDOFF",
                collaboration_id,
                {"from": participant.agent_id, "to": expected_recipient},
            )
            updated = CollaborationSnapshot(
                snapshot.collaboration_id,
                snapshot.task_id,
                snapshot.participants,
                CollaborationStatus.ACTIVE,
                expected_recipient,
                snapshot.events + (event,),
            )
            self._sessions[collaboration_id] = updated
            return updated

    def complete(
        self,
        collaboration_id: str,
        acting_agent_id: str,
        content: str,
    ) -> CollaborationSnapshot:
        _validate_id(collaboration_id, "Collaboration")
        _validate_id(acting_agent_id, "Agent")
        _validate_text(content, "content", self.MAX_ENTRY_BYTES, allow_empty=False)
        with self._lock:
            snapshot = self._active_session(collaboration_id, acting_agent_id)
            self._require_pending_task(snapshot.task_id)
            if acting_agent_id != snapshot.participants[-1].agent_id:
                raise ValueError("Only the final listed participant may complete collaboration")
            self._validate_context_size(snapshot, content)
            participant = snapshot.participants[-1]
            event = CollaborationEvent(
                len(snapshot.events),
                CollaborationEventType.COMPLETED,
                participant.agent_id,
                participant.role,
                None,
                content,
            )
            self._audit(
                snapshot.task_id,
                "COLLABORATION_COMPLETED",
                collaboration_id,
                {"agent_id": participant.agent_id},
            )
            updated = CollaborationSnapshot(
                snapshot.collaboration_id,
                snapshot.task_id,
                snapshot.participants,
                CollaborationStatus.COMPLETED,
                None,
                snapshot.events + (event,),
            )
            self._sessions[collaboration_id] = updated
            return updated

    def fail(
        self,
        collaboration_id: str,
        acting_agent_id: str,
        reason: CollaborationFailureReason,
    ) -> CollaborationSnapshot:
        _validate_id(collaboration_id, "Collaboration")
        _validate_id(acting_agent_id, "Agent")
        if not isinstance(reason, CollaborationFailureReason):
            raise TypeError("Expected CollaborationFailureReason")
        with self._lock:
            snapshot = self._active_session(collaboration_id, acting_agent_id)
            participant = snapshot.participants[self._participant_index(snapshot, acting_agent_id)]
            event = CollaborationEvent(
                len(snapshot.events),
                CollaborationEventType.FAILED,
                participant.agent_id,
                participant.role,
                None,
                "",
                reason,
            )
            self._audit(
                snapshot.task_id,
                "COLLABORATION_FAILED",
                collaboration_id,
                {"agent_id": participant.agent_id, "reason": reason.value},
            )
            updated = CollaborationSnapshot(
                snapshot.collaboration_id,
                snapshot.task_id,
                snapshot.participants,
                CollaborationStatus.FAILED,
                None,
                snapshot.events + (event,),
                reason,
            )
            self._sessions[collaboration_id] = updated
            return updated

    def get(self, collaboration_id: str) -> CollaborationSnapshot:
        _validate_id(collaboration_id, "Collaboration")
        with self._lock:
            try:
                return self._sessions[collaboration_id]
            except KeyError:
                raise ValueError(f"Collaboration not found: {collaboration_id}") from None

    def _active_session(
        self,
        collaboration_id: str,
        acting_agent_id: str,
    ) -> CollaborationSnapshot:
        snapshot = self.get(collaboration_id)
        if snapshot.status is not CollaborationStatus.ACTIVE:
            raise ValueError("Collaboration is not active")
        if snapshot.active_agent_id != acting_agent_id:
            raise ValueError("Acting Agent is not the active participant")
        return snapshot

    def _require_pending_task(self, task_id: str) -> None:
        if self._tasks.get(task_id).status is not TaskStatus.PENDING:
            raise ValueError("Collaboration requires a pending Task")

    @staticmethod
    def _participant_index(snapshot: CollaborationSnapshot, agent_id: str) -> int:
        for index, participant in enumerate(snapshot.participants):
            if participant.agent_id == agent_id:
                return index
        raise ValueError("Agent is not a collaboration participant")

    def _validate_context_size(self, snapshot: CollaborationSnapshot, content: str) -> None:
        size = sum(len(event.content.encode("utf-8")) for event in snapshot.events)
        if size + len(content.encode("utf-8")) > self.MAX_CONTEXT_BYTES:
            raise ValueError("Collaboration context exceeds byte limit")

    def _audit(
        self,
        task_id: str,
        event: str,
        collaboration_id: str,
        details: dict[str, str | list[str]],
    ) -> None:
        self._logger.log(
            task_id,
            event,
            json.dumps(
                {"collaboration_id": collaboration_id, **details},
                separators=(",", ":"),
                sort_keys=True,
            ),
        )


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} ID must be text")
    identifier(value)


def _validate_text(value: str, name: str, max_bytes: int, *, allow_empty: bool = True) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} cannot be empty")
    try:
        encoded_size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain valid Unicode text") from exc
    if encoded_size > max_bytes:
        raise ValueError(f"{name} exceeds byte limit")
