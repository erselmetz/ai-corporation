"""One-owner Gemini assignment path; general model management stays separate."""
import time

from app.integrations.gemini_chat import (
    GeminiConnectionError,
    GeminiConnectionManager,
)


class LocalOnlineProviderService:
    PROVIDER_ID = "gemini"

    def __init__(self, corporation, connection: GeminiConnectionManager):
        self._corporation = corporation
        self._connection = connection

    def inventory(self):
        connection = self._connection.connection()
        agent_id = self._connected_agent_id()
        selected = self._connection.selected(agent_id) if agent_id else None
        if connection is None:
            return {"connected": False, "models": [], "selected": None,
                    "checked_at": None, "expires_at": None,
                    "expired_assignment": ({"agent_id": selected[0], "agent_name": selected[1],
                                            "previous_provider": selected[2], "model_id": selected[4]}
                                           if selected else None),
                    "generation_calls_used": 0, "generation_calls_limit": 5}
        return {"connected": selected is not None,
                "models": list(connection.models),
                "selected": {"agent_id": selected[0], "agent_name": selected[1],
                             "previous_provider": selected[2], "model_id": selected[4]} if selected else None,
                "checked_at": connection.checked_at.isoformat(),
                "expires_in_seconds": max(0, int(connection.expires_at - time.monotonic())),
                "generation_calls_used": self._connection.calls_used(connection),
                "generation_calls_limit": 5}

    def _connected_agent_id(self):
        for agent in self._corporation.list_agents():
            target = self._connection.selected(agent.id)
            if target:
                return agent.id
        return ""

    def discover(self, api_key):
        connection = self._connection.discover(api_key)
        return {"models": list(connection.models), "checked_at": connection.checked_at.isoformat(),
                "expires_in_seconds": max(0, int(connection.expires_at - time.monotonic()))}

    def refresh(self):
        connection = self._connection.refresh()
        return {"models": list(connection.models), "checked_at": connection.checked_at.isoformat(),
                "expires_in_seconds": max(0, int(connection.expires_at - time.monotonic()))}

    def connect(self, agent_id: str, model_id: str):
        # Refresh immediately before mutation; inventory shown earlier is only a hint.
        with self._corporation.owned_chat().configuration_change(agent_id):
            agent = self._corporation.get_agent(agent_id)
            if self._connection.selected(agent_id):
                raise GeminiConnectionError("This coordinator is already connected; disconnect before changing its model.")
            if any(self._connection.selected(item.id) for item in self._corporation.list_agents()):
                raise GeminiConnectionError("Disconnect the current coordinator before selecting another.")
            if self._corporation.provider_exists(self.PROVIDER_ID):
                raise GeminiConnectionError("A Gemini provider is already configured outside local setup.")
            connection = self._connection.refresh()
            if model_id not in connection.models:
                raise GeminiConnectionError("Selected model is no longer available; refresh the Gemini model list.")
            key = connection.configuration.api_key
            provider = self._connection.provider(key, model_id)
            self._connection.select_model(
                agent.id, agent.name, agent.provider, agent.model, model_id)
            target = self._connection.selected(agent.id)
            try:
                self._corporation.register_local_provider(self.PROVIDER_ID, provider)
                result = self._corporation.replace_model(agent.id, self.PROVIDER_ID, model_id)
            except Exception:
                if self._corporation.provider_exists(self.PROVIDER_ID):
                    self._corporation.remove_local_provider(self.PROVIDER_ID)
                self._connection.disconnect(agent.id)
                raise GeminiConnectionError("Gemini could not be connected to this coordinator.") from None
            return {"agent_id": result.agent_id, "provider_id": result.provider_id,
                    "model_id": result.model_id, "previous_provider": target[2]}

    def disconnect(self, agent_id: str):
        with self._corporation.owned_chat().configuration_change(agent_id):
            target = self._connection.selected(agent_id)
            if target is None:
                raise GeminiConnectionError("This coordinator is not connected to Gemini.")
            agent = self._corporation.get_agent(agent_id)
            if agent.provider != self.PROVIDER_ID or agent.model != target[4]:
                raise GeminiConnectionError("Coordinator assignment changed outside local setup; resolve it before disconnecting.")
            self._corporation.replace_model(agent_id, target[2], target[3])
            self._corporation.remove_local_provider(self.PROVIDER_ID)
            self._connection.disconnect(agent_id)
            return {"agent_id": agent_id, "provider_id": target[2],
                    "model_id": target[3], "connected": False}

    def clear_staged_credential(self):
        self._connection.clear_staged()
        return {"connected": False, "credential_erased": True}
