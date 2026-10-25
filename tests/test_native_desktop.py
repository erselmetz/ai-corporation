"""Native desktop routing and local-only model boundary regressions."""
import httpx
import pytest
from app.native_desktop.session import NativeSession


def test_native_catalog_rejects_cloud_stubs_and_prefers_reported_tools_and_thinking(monkeypatch):
    original=httpx.Client
    seen=[]
    def handle(request):
        seen.append(request.url.path)
        if request.url.path=="/api/tags":
            return httpx.Response(200,json={"models":[{"name":name,"size":size} for name,size in
                [("small",10),("reasoner",20),("remote:cloud",1),("hidden-remote",1),("embed",2)]]})
        import json
        name=json.loads(request.content)["model"]
        body={"capabilities":["embedding"] if name=="embed" else ["completion","tools"]+(["thinking"] if name=="reasoner" else [])}
        if name=="hidden-remote": body["remote_host"]="https://remote.example"
        return httpx.Response(200,json=body)
    monkeypatch.setattr(httpx,"Client",lambda **kw:original(**kw,transport=httpx.MockTransport(handle)))
    session=NativeSession.__new__(NativeSession)
    assert [item["name"] for item in session.models()]==["reasoner","small"]
    assert all(path in {"/api/tags","/api/show"} for path in seen)


def test_native_api_bridge_refuses_non_application_destinations():
    session=NativeSession.__new__(NativeSession)
    for path in ["https://remote.example/api/chat","file:///etc/passwd","/ui/chat"]:
        with pytest.raises(ValueError): session.request("GET",path)


def test_native_bridge_sends_real_messages_through_existing_backend(tmp_path,monkeypatch):
    import threading
    from app.providers import AIProvider
    from app.providers.inventory import LocalModelInventory
    from app.runtime.factory import create_corporation_runtime
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path)); monkeypatch.chdir(tmp_path)
    class Provider(AIProvider):
        is_local=True
        def generate(self,model,prompt):
            assert "native bridge message" in prompt
            return "Native backend reply"
        def local_model_inventory(self): return LocalModelInventory("available",("installed-test",),True)
        def supports_model_chat(self,model): return True
    runtime=create_corporation_runtime(); runtime.providers.remove("ollama"); runtime.providers.register("ollama",Provider())
    session=NativeSession(application_service=runtime.application_service)
    try:
        workspace,conversation=session.new_chat("installed-test")
        events=[]; session.send(workspace,conversation,"native bridge message",threading.Event(),events.append)
        assert events==[{"type":"chunk","text":"Native backend reply"},{"type":"complete"}]
    finally: session.close()
