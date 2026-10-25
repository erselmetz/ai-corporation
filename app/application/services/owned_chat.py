"""Principal-owned browser chat using the existing Corporation conversation domain."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from threading import Lock, RLock
from time import perf_counter
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from app.agents.registry import AgentAssignmentBusy
from app.conversations.models import ConversationStatus

from .chat_images import ChatImageError, ChatImageStore
from .corporation_chat import CorporationChatService

if TYPE_CHECKING:
    from .corporation import AgentSummary


class ChatNotFound(ValueError):
    pass


class ChatConflict(ValueError):
    pass


class ChatUnavailable(ValueError):
    pass


class ChatStorageError(RuntimeError):
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    workspace_provider: object | None = field(default=None, repr=False, compare=False)


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
                 agent_execution: Callable[[str], object],
                 get_agent_profile: Callable[[str], object] | None = None, *, workspaces=None):
        self._chat = chat
        self._get_agent = get_agent
        self._get_provider = get_provider
        self._agent_execution = agent_execution
        self._get_agent_profile = get_agent_profile or get_agent
        self._workspaces = workspaces
        self._entries: dict[str, _OwnedConversation] = {}
        self._catalog_lock = RLock()
        self._active_agents: dict[str, int] = {}
        self._configuring_agents: set[str] = set()
        self._image_store = ChatImageStore()

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
        from .chat_workspaces import current_workspace
        workspace = current_workspace.get()
        if workspace is not None and (workspace.owner != owner or workspace.agent_id != agent_id):
            raise ChatConflict("Choose this workspace's selected Agent")
        with self._catalog_lock:
            if len(self._entries) >= self.MAX_CONVERSATIONS:
                raise ChatLimit("Conversation limit reached for this app run")
            with self._agent_request(agent_id):
                agent, provider = self._coordinator(agent_id)
                identifier = uuid4().hex
                record = self._chat.start(identifier, agent_id)
                self._entries[identifier] = _OwnedConversation(
                    owner, agent, provider, Lock(),
                    workspace_provider=self._get_provider(workspace.provider_id) if workspace else None,
                )
                if self._workspaces is not None:
                    self._workspaces.bind(owner, identifier)
                result = {
                    "conversation": record,
                    "coordinator": agent,
                    "streaming_supported": getattr(provider, "supports_streaming", False) is True,
                    "image_input_supported": getattr(provider, "supports_image_input", False) is True,
                    "local_model": getattr(provider, "is_local", False) is True,
                }
                return self._workspace_response(owner, identifier, result)

    def _workspace_route(self, owner, identifier, entry):
        selection = self._workspaces.conversation_selection(owner, identifier) if self._workspaces else None
        if selection is None:
            return None
        provider = self._get_provider(selection["provider_id"])
        if entry.workspace_provider is not None and provider is not entry.workspace_provider:
            raise ChatConflict("Workspace provider changed; start a new conversation")
        route = (selection["provider_id"], selection["model_id"])
        return route if route != (entry.coordinator.provider, entry.coordinator.model) else None

    def _workspace_response(self, owner, identifier, result):
        if self._workspaces is None:
            return result
        selection = self._workspaces.conversation_selection(owner, identifier)
        if selection is None:
            return result
        agent = result["coordinator"]
        provider = self._get_provider(selection["provider_id"])
        override = (agent.provider, agent.model) != (selection["provider_id"], selection["model_id"])
        return {**result, "coordinator": replace(agent, provider=selection["provider_id"], model=selection["model_id"]),
                "workspace": {**selection,
                              "project_brief": self._workspaces.prompt_brief(identifier) or "",
                              "project_brief_digest": self._workspaces.brief_digest(self._workspaces.prompt_brief(identifier) or ""),
                              "brain_non_empty": self._workspaces.has_project_knowledge(owner, selection["project_id"])
                              if selection["project_id"] else None},
                "streaming_supported": not override and result.get("streaming_supported", False),
                "image_input_supported": not override and result.get("image_input_supported", False),
                "local_model": getattr(provider, "is_local", False) is True}

    def list(self, owner: str):
        with self._catalog_lock:
            return tuple({"id": identifier, "coordinator": entry.coordinator,
                          "created_at": entry.created_at.isoformat()}
                         for identifier, entry in self._entries.items() if entry.owner == owner
                         and (self._workspaces is None or self._workspaces.permits(owner, identifier)))

    @contextmanager
    def _access(self, owner, identifier):
        with self._catalog_lock:
            entry = self._entries.get(identifier)
            if entry is None or entry.owner != owner or (self._workspaces is not None and not self._workspaces.permits(owner, identifier)):
                raise ChatNotFound("Conversation not found")
        if not entry.lock.acquire(blocking=False):
            raise ChatConflict("Conversation is busy; wait for the current request")
        try:
            yield entry
        finally:
            entry.lock.release()

    def get(self, owner, identifier):
        with self._access(owner, identifier) as entry:
            return self._workspace_response(owner, identifier, {
                "conversation": self._chat.get(identifier),
                "coordinator": entry.coordinator,
                "streaming_supported": getattr(entry.provider, "supports_streaming", False) is True,
                "image_input_supported": getattr(entry.provider, "supports_image_input", False) is True,
                "local_model": getattr(entry.provider, "is_local", False) is True,
            })

    def authorize_owner(self, owner, identifier):
        """Check a conversation's owner without competing with its active turn lock."""
        with self._catalog_lock:
            entry = self._entries.get(identifier)
            if entry is None or entry.owner != owner or (self._workspaces is not None and not self._workspaces.permits(owner, identifier)):
                raise ChatNotFound("Conversation not found")
            return True

    def get_status(self, owner, identifier):
        with self._access(owner, identifier):
            return self._chat.get_status(identifier)

    def complete_without_provider(self, owner, identifier, text, reply):
        """Complete an owner-scoped safe response without reserving a model slot."""
        with self._access(owner, identifier) as entry:
            if len(self._chat.get(identifier).messages) + 2 > self.MAX_MESSAGES:
                raise ChatLimit("Conversation message limit reached; start a new conversation")
            record = self._chat.complete_without_provider(identifier, text, reply)
            return self._workspace_response(
                owner, identifier,
                {"conversation": record, "coordinator": entry.coordinator},
            )

    def send(self, owner, identifier, text, retrieved_context=None, *, presentation_preferences=None,
             tool_context=None, image_ids=(),
             image_consent=False, ocr_evidence=(), prompt_observer=None, turn_route=None,
             route_consent=False, brain_enabled=False):
        if turn_route is not None:
            if (route_consent is not True or not isinstance(turn_route, tuple) or len(turn_route) != 2
                    or any(not isinstance(value, str) or not value.strip() or len(value) > 256
                           for value in turn_route)):
                raise ChatConsentRequired("Explicit per-turn route consent and a bounded provider/model are required")
        elif route_consent is True:
            raise ValueError("Route consent requires an alternate provider and model")
        with self._access(owner, identifier) as entry:
            if self._chat.get_status(identifier) is not ConversationStatus.OPEN:
                raise ValueError("Cannot send to a closed conversation")
            current, provider = self._coordinator(entry.coordinator.id)
            if ((current.provider, current.model) != (entry.coordinator.provider, entry.coordinator.model)
                    or provider is not entry.provider):
                raise ChatConflict("Coordinator assignment changed; start a new conversation")
            workspace_route = self._workspace_route(owner, identifier, entry)
            if workspace_route and (image_ids or turn_route):
                raise ChatConflict("Workspace model selection cannot combine with images or a second route override")
            turn_route = turn_route or workspace_route
            with self.agent_request(entry.coordinator.id, route=turn_route,
                                    wait_for_slot=getattr(self._get_provider(turn_route[0]) if turn_route else provider, "is_local", False) is True):
                if image_ids:
                    if image_consent is not True:
                        raise ChatConsentRequired("Explicit consent is required to send selected images to the configured provider")
                    current, provider = self._coordinator(entry.coordinator.id)
                    if (current.provider, current.model) != (entry.coordinator.provider, entry.coordinator.model) or provider is not entry.provider:
                        raise ChatConflict("Coordinator assignment changed; start a new conversation")
                    if getattr(provider, "supports_image_input", False) is not True:
                        raise ChatUnavailable("The selected provider does not support image input")
                    images = self._image_store.selected_for(owner, identifier, tuple(image_ids))
                    if len(self._chat.get(identifier).messages) + 2 > self.MAX_MESSAGES:
                        raise ChatLimit("Conversation message limit reached; start a new conversation")
                    try:
                        record = self._chat.send_with_images(
                            identifier, text, images, ocr_evidence=tuple(ocr_evidence),
                            presentation_preferences=presentation_preferences,
                        )
                        return self._workspace_response(owner, identifier, {
                            "conversation": record,
                            "coordinator": entry.coordinator,
                            "image_transfer": {
                                "image_ids": [image.id for image in images],
                                "provider_id": current.provider,
                                "model_id": current.model,
                                "local": getattr(provider, "is_local", False) is True,
                                "outcome": "completed",
                                "ocr_regions_included": sum(len(item.regions) for item in ocr_evidence),
                                "ocr_statuses": [{
                                    "image_id": item.image_id, "status": item.status.value,
                                    "diagnostic": item.diagnostic,
                                } for item in ocr_evidence],
                                "retention": "discarded_after_one_use",
                            },
                        })
                    finally:
                        for image in images:
                            self._image_store.remove(owner, identifier, image.id)
                return self._send(entry, identifier, text, retrieved_context, presentation_preferences,
                                  tool_context=tool_context,
                                  prompt_observer=prompt_observer, turn_route=turn_route,
                                  brain_enabled=brain_enabled)

    def send_delegated(self, owner, identifier, text, choose_agent: Callable,
                       *, handoff_observer: Callable[[dict], None] | None = None):
        """Run one local Coordinator selection step and one local Agent answer step."""
        if not callable(choose_agent):
            raise TypeError("A trusted Coordinator selector is required")
        with self._access(owner, identifier) as entry:
            if self._workspace_route(owner, identifier, entry):
                raise ChatUnavailable("One-step delegation uses the Agent's configured model; select Agent default first")
            if self._chat.get_status(identifier) is not ConversationStatus.OPEN:
                raise ValueError("Cannot send to a closed conversation")
            if len(self._chat.get(identifier).messages) + 2 > self.MAX_MESSAGES:
                raise ChatLimit("Conversation message limit reached; start a new conversation")
            selection_started = perf_counter()
            with self.agent_request(entry.coordinator.id,
                                    wait_for_slot=getattr(entry.provider, "is_local", False) is True):
                selected = choose_agent(entry.coordinator.id, text)
            selection_ms = max(0, int((perf_counter() - selection_started) * 1000))
            try:
                target = self._get_agent_profile(selected.id)
            except (AttributeError, ValueError):
                raise ChatUnavailable("The selected Agent is no longer available") from None
            if (target.id == entry.coordinator.id or target.paused
                    or (target.provider, target.model) != (selected.provider, selected.model)):
                raise ChatConflict("The selected Agent changed or is paused; no handoff was started")
            try:
                provider = self._get_provider(target.provider)
            except ValueError:
                raise ChatUnavailable("The selected Agent provider is unavailable") from None
            if getattr(provider, "is_local", False) is not True:
                raise ChatConsentRequired("Delegation is limited to a verified local model; no cloud request was made")
            handoff = {
                "status": "selected", "selection_source": "Coordinator model proposal",
                "max_handoffs": 1, "step_count": 2,
                "coordinator": {"id": entry.coordinator.id, "name": entry.coordinator.name},
                "agent": {"id": target.id, "name": target.name, "role": target.role,
                          "provider": target.provider, "model": target.model},
                "selection_ms": selection_ms,
            }
            if handoff_observer is not None:
                handoff_observer(dict(handoff))
            answer_started = perf_counter()
            with self.agent_request(target.id, wait_for_slot=True):
                current = self._get_agent_profile(target.id)
                if (current.provider, current.model, current.system_prompt, current.paused) != (
                        target.provider, target.model, target.system_prompt, target.paused):
                    raise ChatConflict("The selected Agent changed before handoff; no answer was requested")
                record = self._chat.send(
                    identifier, text, responding_agent_id=target.id,
                    role_instructions=target.system_prompt or None,
                    expected_assignment=(target.provider, target.model),
                )
            handoff["answer_ms"] = max(0, int((perf_counter() - answer_started) * 1000))
            handoff["status"] = "completed"
            if handoff_observer is not None:
                handoff_observer(dict(handoff))
            return self._workspace_response(owner, identifier, {
                "conversation": record, "coordinator": entry.coordinator,
                "handoff": handoff,
            })

    def stream(self, owner, identifier, text, retrieved_context=None, presentation_preferences=None,
               *, brain_enabled=False):
        with self._access(owner, identifier) as entry:
            if self._workspace_route(owner, identifier, entry):
                raise ChatUnavailable("This selected workspace model uses the non-streaming chat endpoint")
            if self._chat.get_status(identifier) is not ConversationStatus.OPEN:
                raise ValueError("Cannot send to a closed conversation")
            current, provider = self._coordinator(entry.coordinator.id)
            if ((current.provider, current.model) != (entry.coordinator.provider, entry.coordinator.model)
                    or provider is not entry.provider):
                raise ChatConflict("Coordinator assignment changed; start a new conversation")
            if getattr(entry.provider, "supports_streaming", False) is not True:
                raise ChatUnavailable("The selected provider does not support response streaming")
            with self.agent_request(entry.coordinator.id,
                                    wait_for_slot=getattr(entry.provider, "is_local", False) is True):
                for event in self._chat.send_stream(identifier, text, retrieved_context,
                                                    presentation_preferences, brain_enabled=brain_enabled):
                    if event["type"] == "complete":
                        yield self._workspace_response(owner, identifier, {
                            **event,
                            "coordinator": entry.coordinator,
                            "streaming_supported": True,
                        })
                    else:
                        yield event

    def _send(self, entry, identifier, text, retrieved_context=None, presentation_preferences=None,
              tool_context=None, prompt_observer=None, turn_route=None, brain_enabled=False):
        current, provider = self._coordinator(entry.coordinator.id)
        if (current.provider, current.model) != (entry.coordinator.provider, entry.coordinator.model):
            raise ChatConflict("Coordinator assignment changed; start a new conversation")
        if provider is not entry.provider:
            raise ChatConflict("Coordinator connection changed; start a new conversation")
        if len(self._chat.get(identifier).messages) + 2 > self.MAX_MESSAGES:
            raise ChatLimit("Conversation message limit reached; start a new conversation")
        record = self._chat.send(identifier, text, retrieved_context, presentation_preferences,
                                 tool_context=tool_context,
                                 prompt_observer=prompt_observer, turn_route=turn_route,
                                 brain_enabled=brain_enabled,
                                 expected_assignment=(entry.coordinator.provider, entry.coordinator.model)
                                 if turn_route is not None else None)
        result = {"conversation": record, "coordinator": entry.coordinator}
        if turn_route is not None:
            result["turn_route"] = {"provider_id": turn_route[0], "model_id": turn_route[1]}
        return self._workspace_response(entry.owner, identifier, result)

    def close(self, owner, identifier):
        with self._access(owner, identifier) as entry:
            result = self._chat.close(identifier)
            self._image_store.clear_conversation(owner, identifier)
            return self._workspace_response(
                owner, identifier,
                {"conversation": result, "coordinator": entry.coordinator},
            )

    def delete(self, owner, identifier):
        with self._catalog_lock:
            entry = self._entries.get(identifier)
            if entry is None or entry.owner != owner or (self._workspaces is not None and not self._workspaces.permits(owner, identifier)):
                raise ChatNotFound("Conversation not found")
            if not entry.lock.acquire(blocking=False):
                raise ChatConflict("Conversation is busy; wait for the current request")
            try:
                result = self._chat.delete(owner, identifier)
                self._image_store.clear_conversation(owner, identifier)
                del self._entries[identifier]
                return result
            finally:
                entry.lock.release()

    def attach_image(self, owner, identifier, data: bytes, media_type: str, **provenance):
        with self._access(owner, identifier):
            if self._chat.get_status(identifier) is not ConversationStatus.OPEN:
                raise ChatImageError("Images can only be attached to an open conversation")
            return self._image_store.attach(owner, identifier, data, media_type, **provenance)

    def list_images(self, owner, identifier):
        with self._access(owner, identifier):
            return self._image_store.list_for(owner, identifier)

    def image_capability(self, owner, identifier):
        with self._access(owner, identifier) as entry:
            route = self._workspace_route(owner, identifier, entry)
            if route:
                return {"provider_id": route[0], "model_id": route[1],
                        "local": getattr(self._get_provider(route[0]), "is_local", False) is True,
                        "state": "unsupported"}
            probe = getattr(entry.provider, "supports_model_image_input", None)
            supported = probe(entry.coordinator.model) if callable(probe) else (
                True if getattr(entry.provider, "supports_image_input", False) is True else False
            )
            state = "supported" if supported is True else "unsupported" if supported is False else "unknown"
            return {
                "provider_id": entry.coordinator.provider,
                "model_id": entry.coordinator.model,
                "local": getattr(entry.provider, "is_local", False) is True,
                "state": state,
            }

    def selected_images_for_ocr(self, owner, identifier, image_ids):
        with self._access(owner, identifier):
            return self._image_store.selected_for(owner, identifier, tuple(image_ids))

    def remove_image(self, owner, identifier, image_id):
        with self._access(owner, identifier):
            return self._image_store.remove(owner, identifier, image_id)

    @contextmanager
    def agent_request(self, agent_id: str, *, wait_for_slot: bool = False, route=None):
        """Share admission guards across owned chat scopes and Agent executions."""
        with self._agent_request(agent_id):
            try:
                options = {"wait_for_slot": wait_for_slot}
                if route is not None:
                    options["route"] = route
                with self._agent_execution(agent_id, **options):
                    yield
            except AgentAssignmentBusy:
                raise ChatConflict(
                    "Agent has active work or its connection is changing; retry shortly"
                ) from None
