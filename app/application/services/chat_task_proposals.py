"""Owner-reviewed coordinator proposals that create pending Tasks only."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from threading import RLock
from uuid import uuid4

from app.conversations import ConversationStatus, MessageRole, MessageStatus
from app.memory import MemoryScope
from .task_planning import OutcomeCriteria


class ChatTaskProposalNotFound(ValueError):
    pass


class ChatTaskProposalConflict(ValueError):
    pass


class ChatTaskProposalExpired(ChatTaskProposalConflict):
    pass


@dataclass(frozen=True, slots=True)
class _Proposal:
    owner_id: str
    conversation_id: str
    coordinator: tuple
    source_message_id: str
    source_content: str
    objective: str
    project: tuple
    agent: tuple
    criteria: OutcomeCriteria
    context_query: str | None
    context_scope: MemoryScope | None
    context_scope_id: str | None
    context: object | None
    description: str
    created_at: datetime
    expires_at: datetime
    digest: str
    fingerprint: str


class ChatTaskProposalService:
    MAX_PROPOSALS_PER_OWNER = 100
    MAX_OWNERS = 8
    MAX_CREATED_FINGERPRINTS = 1000
    PROPOSAL_TTL = timedelta(minutes=15)

    def __init__(self, application, *, clock=lambda: datetime.now(timezone.utc)):
        self._application = application
        self._clock = clock
        self._proposals: dict[str, _Proposal] = {}
        self._created_fingerprints: set[str] = set()
        self._lock = RLock()

    def create(
        self,
        owner_id: str,
        conversation_id: str,
        *,
        source_message_id: str,
        objective: str,
        project_id: str,
        agent_id: str,
        expected_outcome: str,
        verification_method: str,
        expected_evidence: str,
        context_query: str | None = None,
        context_scope: MemoryScope | None = None,
        context_scope_id: str | None = None,
    ) -> dict:
        now = self._now()
        _text(owner_id, "owner_id", 256)
        _text(conversation_id, "conversation_id", 256)
        _text(source_message_id, "source_message_id", 256)
        _text(objective, "objective", 1024)
        _text(project_id, "project_id", 256)
        _text(agent_id, "agent_id", 256)
        criteria = OutcomeCriteria(expected_outcome, verification_method, expected_evidence)
        supplied_context = (
            context_query is not None,
            context_scope is not None,
            context_scope_id is not None,
        )
        if any(supplied_context) and not all(supplied_context):
            raise ValueError("Authorized context requires an explicit query, scope, and scope ID")
        if context_query is not None:
            _text(context_query, "context_query", 1024)
            _text(context_scope_id, "context_scope_id", 256)
            if not isinstance(context_scope, MemoryScope):
                raise TypeError("Expected a MemoryScope")

        chat = self._application.owned_chat()
        current = chat.get(owner_id, conversation_id)
        conversation = current["conversation"]
        if conversation.status is not ConversationStatus.OPEN:
            raise ValueError("Cannot propose a Task from a closed conversation")
        message = next(
            (item for item in conversation.messages if item.id == source_message_id),
            None,
        )
        if (
            message is None
            or message.role is not MessageRole.ASSISTANT
            or message.status is not MessageStatus.COMPLETED
        ):
            raise ValueError("Proposal source must be a completed coordinator message")

        coordinator = _agent_snapshot(self._application.get_agent(current["coordinator"].id))
        if coordinator != _agent_snapshot(current["coordinator"]):
            raise ChatTaskProposalConflict("Coordinator assignment changed; start a new conversation")
        project = _project_snapshot(self._application.get_project(project_id))
        agent = _agent_snapshot(self._application.get_agent(agent_id))
        context = self._retrieve_context(
            owner_id,
            project_id,
            now,
            context_query,
            context_scope,
            context_scope_id,
        )
        description = _task_description(
            owner_id,
            objective,
            criteria,
            conversation_id,
            source_message_id,
            context,
        )
        identifier = uuid4().hex
        expires_at = now + self.PROPOSAL_TTL
        proposal_fields = {
            "conversation_id": conversation_id,
            "confirmation_identity": owner_id,
            "coordinator": coordinator,
            "source_message_id": source_message_id,
            "source_content": message.content,
            "objective": objective,
            "project": project,
            "agent": agent,
            "criteria": asdict(criteria),
            "context_query": context_query,
            "context_scope": context_scope.value if context_scope else None,
            "context_scope_id": context_scope_id,
            "context": _jsonable(context),
            "description": description,
        }
        fingerprint = _digest({"owner_id": owner_id, **proposal_fields})
        digest = _digest({
            "proposal_id": identifier,
            **proposal_fields,
            "created_at": now,
            "expires_at": expires_at,
        })
        record = _Proposal(
            owner_id=owner_id,
            conversation_id=conversation_id,
            coordinator=coordinator,
            source_message_id=source_message_id,
            source_content=message.content,
            objective=objective,
            project=project,
            agent=agent,
            criteria=criteria,
            context_query=context_query,
            context_scope=context_scope,
            context_scope_id=context_scope_id,
            context=context,
            description=description,
            created_at=now,
            expires_at=expires_at,
            digest=digest,
            fingerprint=fingerprint,
        )
        with self._lock:
            self._prune(now)
            if fingerprint in self._created_fingerprints or any(
                item.owner_id == owner_id and item.fingerprint == fingerprint
                for item in self._proposals.values()
            ):
                raise ChatTaskProposalConflict("An identical proposal already exists or created a Task")
            if sum(item.owner_id == owner_id for item in self._proposals.values()) >= self.MAX_PROPOSALS_PER_OWNER:
                raise ChatTaskProposalConflict("Task proposal owner limit reached")
            if (
                not any(item.owner_id == owner_id for item in self._proposals.values())
                and len({item.owner_id for item in self._proposals.values()}) >= self.MAX_OWNERS
            ):
                raise ChatTaskProposalConflict("Task proposal owner limit reached")
            self._proposals[identifier] = record
        return _public(identifier, record)

    def confirm(
        self,
        owner_id: str,
        conversation_id: str,
        proposal_id: str,
        *,
        proposal_digest: str,
        confirmed: bool,
    ) -> dict:
        if confirmed is not True:
            raise ValueError("Explicit owner confirmation is required")
        _text(owner_id, "owner_id", 256)
        _text(conversation_id, "conversation_id", 256)
        _text(proposal_id, "proposal_id", 256)
        _text(proposal_digest, "proposal_digest", 64)
        now = self._now()
        with self._lock:
            self._prune(now)
            record = self._proposals.get(proposal_id)
            if (
                record is None
                or record.owner_id != owner_id
                or record.conversation_id != conversation_id
            ):
                raise ChatTaskProposalNotFound("Task proposal not found")
            if now >= record.expires_at:
                self._proposals.pop(proposal_id, None)
                raise ChatTaskProposalExpired("Task proposal expired; prepare it again")
            if proposal_digest != record.digest:
                raise ChatTaskProposalConflict("Confirmed proposal differs from the reviewed proposal")
            if record.fingerprint in self._created_fingerprints:
                raise ChatTaskProposalConflict("This proposal already created a Task")
            self._revalidate(record, now)
            if len(self._created_fingerprints) >= self.MAX_CREATED_FINGERPRINTS:
                raise ChatTaskProposalConflict("Task proposal creation limit reached for this app run")

            self._proposals.pop(proposal_id)
            self._created_fingerprints.add(record.fingerprint)
            task = self._application.create_task(
                title=record.objective,
                description=record.description,
                project_id=record.project[0],
                agent_id=record.agent[0],
            )
            if task.status != "pending":
                raise RuntimeError("Confirmed proposal did not create a pending Task")
            return {
                "proposal_id": proposal_id,
                "task_id": task.id,
                "status": task.status,
                "project_id": record.project[0],
                "agent_id": record.agent[0],
                "confirmed_by": owner_id,
            }

    def _revalidate(self, record: _Proposal, now: datetime) -> None:
        try:
            current = self._application.owned_chat().get(record.owner_id, record.conversation_id)
            conversation = current["conversation"]
            message = next(
                (item for item in conversation.messages if item.id == record.source_message_id),
                None,
            )
            if (
                conversation.status is not ConversationStatus.OPEN
                or current["coordinator"].id != record.coordinator[0]
                or message is None
                or message.role is not MessageRole.ASSISTANT
                or message.status is not MessageStatus.COMPLETED
                or message.content != record.source_content
            ):
                raise ChatTaskProposalConflict("Proposal source changed; prepare it again")
            if _agent_snapshot(self._application.get_agent(record.agent[0])) != record.agent:
                raise ChatTaskProposalConflict("Responsible Agent changed; prepare it again")
            if _agent_snapshot(self._application.get_agent(record.coordinator[0])) != record.coordinator:
                raise ChatTaskProposalConflict("Coordinator changed; prepare it again")
            if _project_snapshot(self._application.get_project(record.project[0])) != record.project:
                raise ChatTaskProposalConflict("Project changed; prepare it again")
            context = self._retrieve_context(
                record.owner_id,
                record.project[0],
                now,
                record.context_query,
                record.context_scope,
                record.context_scope_id,
            )
            if context != record.context:
                raise ChatTaskProposalConflict("Authorized context changed or expired; prepare it again")
        except ChatTaskProposalConflict:
            raise
        except ValueError:
            raise ChatTaskProposalConflict("Proposal references changed; prepare it again") from None

    def _retrieve_context(
        self,
        owner_id: str,
        project_id: str,
        now: datetime,
        query: str | None,
        scope: MemoryScope | None,
        scope_id: str | None,
    ):
        if query is None:
            return None
        if scope is MemoryScope.PROJECT and scope_id != project_id:
            raise ValueError("Project context must match the Task Project")
        return self._application.context_retrieval().retrieve(
            query,
            actor_id=owner_id,
            scope=scope,
            scope_id=scope_id,
            now=now,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Proposal clock must return a timezone-aware datetime")
        return now

    def _prune(self, now: datetime) -> None:
        expired = [identifier for identifier, item in self._proposals.items()
                   if item.expires_at <= now]
        for identifier in expired:
            self._proposals.pop(identifier, None)


def _public(identifier: str, proposal: _Proposal) -> dict:
    return {
        "proposal_id": identifier,
        "proposal_digest": proposal.digest,
        "created_at": proposal.created_at.isoformat(),
        "expires_at": proposal.expires_at.isoformat(),
        "confirmation_identity": proposal.owner_id,
        "objective": proposal.objective,
        "responsible_agent": {
            "id": proposal.agent[0],
            "name": proposal.agent[1],
            "role": proposal.agent[2],
            "provider": proposal.agent[3],
            "model": proposal.agent[4],
            "capabilities": list(proposal.agent[5]),
        },
        "project": {
            "id": proposal.project[0],
            "name": proposal.project[1],
            "description": proposal.project[2],
            "status": proposal.project[3],
        },
        "source": {
            "conversation_id": proposal.conversation_id,
            "coordinator_id": proposal.coordinator[0],
            "message_id": proposal.source_message_id,
            "content": proposal.source_content,
        },
        "authorized_context": {
            "selected": proposal.context is not None,
            "query": proposal.context_query,
            "scope": (
                proposal.context_scope.value if proposal.context_scope is not None else None
            ),
            "scope_id": proposal.context_scope_id,
            "hits": (
                _jsonable(proposal.context)["hits"]
                if proposal.context is not None else []
            ),
            "limitations": (
                {
                    "scanned_records": proposal.context.scanned_records,
                    "candidate_limit_reached": proposal.context.candidate_limit_reached,
                    "result_limit_reached": proposal.context.result_limit_reached,
                    "byte_limit_reached": proposal.context.byte_limit_reached,
                }
                if proposal.context is not None else None
            ),
        },
        "outcome": asdict(proposal.criteria),
        "task": {
            "title": proposal.objective,
            "description": proposal.description,
            "project_id": proposal.project[0],
            "agent_id": proposal.agent[0],
        },
    }


def _agent_snapshot(agent) -> tuple:
    return (
        agent.id,
        agent.name,
        agent.role,
        agent.provider,
        agent.model,
        tuple(agent.capabilities),
    )


def _project_snapshot(project) -> tuple:
    return project.id, project.name, project.description, project.status


def _task_description(
    owner_id,
    objective,
    criteria,
    conversation_id,
    message_id,
    context,
) -> str:
    lines = [
        f"Objective: {objective}",
        f"Owner confirmation identity: {owner_id}",
        f"Expected outcome: {criteria.expected_outcome}",
        f"Verification method: {criteria.verification_method}",
        f"Expected evidence: {criteria.expected_evidence}",
        f"Coordinator proposal source: conversation={conversation_id}; message={message_id}",
    ]
    hits = getattr(context, "hits", ()) if context is not None else ()
    references = [
        f"{hit.source.scope.value}:{hit.source.scope_id}/{hit.source.memory_id}"
        for hit in hits
    ]
    lines.append(
        "Authorized context references: " + (", ".join(references) if references else "none selected")
    )
    description = "\n".join(lines)
    if len(description.encode("utf-8")) > 8192:
        raise ValueError("Canonical Task description exceeds 8192 UTF-8 bytes")
    return description


def _text(value: str | None, label: str, limit: int) -> None:
    try:
        valid = (
            isinstance(value, str)
            and bool(value.strip())
            and len(value.encode("utf-8")) <= limit
            and not any(ord(character) < 32 for character in value)
        )
    except UnicodeEncodeError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be nonempty text of at most {limit} UTF-8 bytes")


def _digest(value: dict) -> str:
    encoded = json.dumps(
        _jsonable(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    raise TypeError(f"Unsupported proposal value: {type(value).__name__}")
