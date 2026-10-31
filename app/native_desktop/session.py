"""Native owner session over an in-process policy facade; no listening socket."""
from __future__ import annotations

import secrets
import threading
import uuid
import httpx

from .facade import InProcessController
from app.local import create_local_app
from app.api.local_access import COOKIE


class NativeSession:
    def __init__(self, password=None, *, controller_factory=InProcessController, application_service=None):
        token = secrets.token_urlsafe(48)
        self.controller = controller_factory(port=0, app_factory=lambda _password, origin: create_local_app(
            password=password, origin=origin, desktop_session_token=token, desktop_mode=True,
            application_service=application_service))
        # Owner lock is checked by the native launcher before this trusted session is constructed.
        self.origin = self.controller.start(password or secrets.token_urlsafe(32))
        self.client = httpx.Client(base_url=self.origin, timeout=180, trust_env=False,
                                   headers={"Origin": self.origin}, cookies={COOKIE: token},
                                   transport=getattr(self.controller,"transport",None))
        self.lock = threading.RLock()
        self.credentials = self.request("GET", "/api/local/session")

    def request(self, method, path, body=None, *, window=None, generation=0):
        if not path.startswith("/api/") and path != "/openapi.json":
            raise ValueError("Only application API routes are allowed")
        headers = {}
        if window:headers.update({'X-Native-Window':window,'X-Native-Generation':str(generation)})
        if method != "GET":
            headers["X-Local-CSRF"] = self.credentials["csrf"]
            headers["Content-Type"] = "application/json"
            if body is None: body = {}
        response = self.client.request(method, path, json=body, headers=headers)
        if not response.is_success:
            detail = response.json().get("detail", "Local request failed")
            if isinstance(detail,dict):detail=detail.get('message','The protected request was not completed. Review its fields and permissions.')
            if not isinstance(detail,str):detail='The protected request was not completed. Review its fields and permissions.'
            raise RuntimeError(detail[:1000])
        return response.json() if response.content else {}

    def lock_owner(self):
        # Synchronously stop before clearing authority, including direct client users.
        self.request('POST','/api/local/emergency-stop/stop')
        self.controller.application.state.authentication_backend.desktop_locked=True
        self._locked_cookie=self.client.cookies.get(COOKIE)
        self.client.cookies.clear()

    def unlock_owner(self,password):
        from app.local_owner_credential import LocalOwnerCredentialStore
        from app.local_owner_credential import OwnerCredentialError
        try:verified=LocalOwnerCredentialStore().verify(password)
        except OwnerCredentialError:verified=False
        if not verified:raise ValueError('Owner password did not match')
        if not getattr(self,'_locked_cookie',None):raise ValueError('No locked owner session')
        self.controller.application.state.authentication_backend.desktop_locked=False
        self.client.cookies.set(COOKIE,self._locked_cookie);self._locked_cookie=None
        self.credentials=self.request('GET','/api/local/session')

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
        # Detect every Ollama catalog entry, while only enabling verified local chat models.
        with httpx.Client(base_url="http://127.0.0.1:11434", timeout=5, trust_env=False) as client:
            response = client.get("/api/tags"); response.raise_for_status()
            found = []
            for item in response.json().get("models", [])[:100]:
                name = item["name"]
                detail = client.post("/api/show", json={"model": name})
                detail.raise_for_status(); info = detail.json()
                capabilities = info.get("capabilities", [])
                remote=bool(info.get("remote_host") or info.get("remote_model") or name.casefold().endswith((":cloud","-cloud")))
                chat="completion" in capabilities
                category=("cloud" if remote else "local-chat" if chat else
                          "embedding" if "embedding" in capabilities else "unsupported")
                found.append({"name":name,"tools":"tools" in capabilities,"thinking":"thinking" in capabilities,
                              "size":item.get("size",0),"available":chat and not remote,"category":category,
                              "reason":("Cloud via Ollama · connect and approve each cloud turn" if remote else
                                        "Embedding model · used by My Brain, not chat" if category=="embedding" else
                                        "Not reported as a chat model by Ollama" if not chat else "")})
            return sorted(found,key=lambda item:(not item["available"],item["category"],not item["tools"],not item["thinking"],item["size"],item["name"]))

    def send(self, workspace, conversation, text, stop, emit, *, window=None, generation=0,knowledge=None,seconds=None):
        headers = {"X-Local-CSRF": self.credentials["csrf"], "X-Chat-Workspace": workspace}
        if window:headers.update({'X-Native-Window':window,'X-Native-Generation':str(generation)})
        if seconds is not None:headers['X-Native-Model-Seconds']=str(seconds)
        base=f"/api/chat/conversations/{conversation}"
        body={"text":text,"shipped_pack_enabled":True}
        if knowledge is not None:body.update(knowledge)
        current=self.client.get(base,headers=headers); current.raise_for_status()
        from app.knowledge.shipped_pack import shipped_pack
        if not current.json().get("streaming_supported") or shipped_pack().instant(text) is not None:
            response=self.client.post(base+"/messages",json=body,headers=headers)
            if not response.is_success: raise RuntimeError(str(response.json().get("detail","Chat unavailable"))[:1000])
            if not stop.is_set():
                result=response.json()
                messages=result.get("conversation",{}).get("messages",[])
                answer=next((item.get("content","") for item in reversed(messages) if item.get("role")=="assistant"),"")
                emit({"type":"chunk","text":answer}); emit({"type":"complete","shipped_guidance":result.get('shipped_guidance'),'context_trace':result.get('context_trace')})
            return
        # Existing backend owns conversation history, context, model routing and permissions.
        with self.client.stream("POST", base+"/messages/stream",
                                json=body, headers=headers) as response:
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
