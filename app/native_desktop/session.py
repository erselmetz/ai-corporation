"""Native owner session over the existing authenticated loopback application."""
from __future__ import annotations

import secrets
import threading
import uuid
import httpx

from app.desktop_launcher import LocalApplicationController
from app.local import create_local_app
from app.api.local_access import COOKIE


class NativeSession:
    def __init__(self, password=None, *, controller_factory=LocalApplicationController, application_service=None):
        token = secrets.token_urlsafe(48)
        self.controller = controller_factory(port=0, app_factory=lambda _password, origin: create_local_app(
            password=password, origin=origin, desktop_session_token=token, desktop_mode=True,
            application_service=application_service))
        # Owner lock is checked by the native launcher before this trusted session is constructed.
        self.origin = self.controller.start(password or secrets.token_urlsafe(32))
        self.client = httpx.Client(base_url=self.origin, timeout=180, trust_env=False,
                                   headers={"Origin": self.origin}, cookies={COOKIE: token})
        self.lock = threading.RLock()
        self.credentials = self.request("GET", "/api/local/session")

    def request(self, method, path, body=None):
        if not path.startswith("/api/") and path != "/openapi.json":
            raise ValueError("Only application API routes are allowed")
        headers = {}
        if method != "GET":
            headers["X-Local-CSRF"] = self.credentials["csrf"]
            headers["Content-Type"] = "application/json"
            if body is None: body = {}
        response = self.client.request(method, path, json=body, headers=headers)
        if not response.is_success:
            detail = response.json().get("detail", "Local request failed")
            raise RuntimeError(str(detail)[:1000])
        return response.json() if response.content else {}

    def close(self):
        self.client.close()
        self.controller.stop()

    def new_chat(self, model, agent="local_worker"):
        identifier = uuid.uuid4().hex
        self.request("POST", "/api/chat/workspaces", {"id": identifier, "agent_id": agent,
                     "provider_id": "ollama", "model_id": model})
        headers = {"X-Local-CSRF": self.credentials["csrf"], "X-Chat-Workspace": identifier}
        response = self.client.post("/api/chat/conversations", json={"agent_id": agent}, headers=headers)
        response.raise_for_status()
        return identifier, response.json()["conversation"]["id"]

    def models(self):
        # Read only local model metadata. Cloud stubs must never be treated as local inference.
        with httpx.Client(base_url="http://127.0.0.1:11434", timeout=5, trust_env=False) as client:
            response = client.get("/api/tags"); response.raise_for_status()
            found = []
            for item in response.json().get("models", [])[:100]:
                name = item["name"]
                if "cloud" in name.lower():
                    continue
                detail = client.post("/api/show", json={"model": name})
                detail.raise_for_status(); info = detail.json()
                if info.get("remote_host") or info.get("remote_model"):
                    continue
                capabilities = info.get("capabilities", [])
                if "completion" in capabilities:
                    found.append({"name": name, "tools": "tools" in capabilities,
                                  "thinking": "thinking" in capabilities, "size": item.get("size", 0)})
            return sorted(found, key=lambda item: (not item["tools"], not item["thinking"], item["size"]))

    def send(self, workspace, conversation, text, stop, emit):
        headers = {"X-Local-CSRF": self.credentials["csrf"], "X-Chat-Workspace": workspace}
        base=f"/api/chat/conversations/{conversation}"
        current=self.client.get(base,headers=headers); current.raise_for_status()
        from app.knowledge.shipped_pack import shipped_pack
        if not current.json().get("streaming_supported") or shipped_pack().instant(text) is not None:
            response=self.client.post(base+"/messages",json={"text":text,"shipped_pack_enabled":True},headers=headers)
            if not response.is_success: raise RuntimeError(str(response.json().get("detail","Chat unavailable"))[:1000])
            if not stop.is_set():
                result=response.json()
                messages=result.get("conversation",{}).get("messages",[])
                answer=next((item.get("content","") for item in reversed(messages) if item.get("role")=="assistant"),"")
                emit({"type":"chunk","text":answer}); emit({"type":"complete","shipped_guidance":result.get('shipped_guidance')})
            return
        # Existing backend owns conversation history, context, model routing and permissions.
        with self.client.stream("POST", base+"/messages/stream",
                                json={"text": text,"shipped_pack_enabled":True}, headers=headers) as response:
            if not response.is_success:
                response.read()
                raise RuntimeError(str(response.json().get("detail", "Chat unavailable"))[:1000])
            import json
            for line in response.iter_lines():
                if stop.is_set():
                    return
                if line:
                    event = json.loads(line)
                    emit(event)
