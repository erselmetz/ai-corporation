"""Read-only/local-model stabilization evidence, with isolated application state.

Never installs packages/models, activates a device capture, or contacts cloud models.
Run only while Ollama is already listening on 127.0.0.1:11434.
"""
from pathlib import Path
import os
import sys
import tempfile
import time
import json
import hashlib
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
MODEL="qwen3.5:4b"


def main():
    local=httpx.Client(base_url="http://127.0.0.1:11434",timeout=5,trust_env=False)
    def running():
        try:
            response=local.get("/api/tags"); response.raise_for_status(); return response.json()
        except Exception: raise SystemExit("STOP: Ollama is not running at 127.0.0.1:11434. Start it before resuming Task 222.")
    inventory=running()
    model=next((item for item in inventory.get("models",[]) if item["name"]==MODEL),None)
    if model is None: raise SystemExit("Installed qwen3.5:4b is unavailable. No model will be downloaded or substituted.")
    info=local.post("/api/show",json={"model":MODEL}).json()
    if info.get("remote_host") or info.get("remote_model") or "cloud" in MODEL:
        raise SystemExit("Refusing a cloud/remote model")
    profile=Path(tempfile.mkdtemp(prefix="ersel-task222-live-"))
    original_local_app_data=os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"]=str(profile); os.environ["OLLAMA_BASE_URL"]="http://127.0.0.1:11434"
    os.environ["NO_PROXY"]="127.0.0.1,localhost,::1"
    os.chdir(profile)
    from app.runtime.factory import create_corporation_runtime
    from app.providers import OllamaProvider
    from app.native_desktop.session import NativeSession
    runtime=create_corporation_runtime(with_builtin_agent_team=True)
    runtime.providers.remove("ollama"); runtime.providers.register("ollama",OllamaProvider("http://127.0.0.1:11434"))
    service=runtime.application_service
    service.apply_builtin_default_routes("ollama",MODEL,installed_ollama_models=(MODEL,))
    session=NativeSession(application_service=service)
    output=ROOT/"task222-review"; output.mkdir(exist_ok=True)
    result={"source_commit":"e7ea9844567c74b8e7b4ac1a43a282b96bfd19a0","model":MODEL,
            "model_digest":model.get("digest"),"capabilities":info.get("capabilities",[]),
            "profile":str(profile),"task202":[],"task196":{"documents":[],"questions":[]},"task198":[],
            "limits":{"step_timeout_seconds":30,"step_token_budget":512,"context_bytes":1800},
            "notes":["Existing backend defaults are unchanged. Timeouts/empty answers remain failures; no turn is replayed.",
                     "Historical real repository documents are evidence inputs, not current product-status instructions."]}
    def save(): (output/"live-results.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    try:
        result["ollama_before"]=local.get("/api/ps").json()
        session.request("PUT","/api/local/preferences",{"autonomy_level":"ask_every_action"})
        cases=[("Review a Python function for a bug and propose a minimal patch without executing code.","developer"),
               ("Compare two approaches using owner-authorized references and cite the evidence.","researcher"),
               ("Organize the approved Brain notes by source and preserve their provenance.","librarian"),
               ("Describe the layout of an owner-provided screenshot, with no clicks or continuous capture.","observer"),
               ("Design unit tests for a Python parser and explain edge cases, without running commands.","developer")]
        for question,expected in cases:
            running(); started=time.perf_counter(); row={"question":question,"expected_agent":expected}
            try:
                with service.owned_chat_agent_execution("local_worker",wait_for_slot=True):
                    selected=service.choose_chat_delegate("local_worker",question)
                row.update(selected_agent=selected.id,valid_choice=True,correct=selected.id==expected)
            except Exception as error:
                running(); row.update(valid_choice=False,correct=False,error_type=type(error).__name__,error=str(error)[:300])
            row["elapsed_ms"]=round((time.perf_counter()-started)*1000,2); result["task202"].append(row); save()
            print(json.dumps({"stage":"202",**row}),flush=True)
        documents=["desktop/requirements-build.txt","requirements-knowledge.txt","review/task-223-native-python.md",
                   "review/task-214-window-review.md","review/task-223-prototype-shell.md"]
        expiry=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        for name in documents:
            path=ROOT/name; data=path.read_bytes()
            response=session.client.post("/api/memory/owner/upload?"+urlencode({"expires_at":expiry,"retention_opt_in":"true"}),
                headers={"X-Local-CSRF":session.credentials["csrf"]},files={"file":(path.name,data)})
            row={"path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"http_status":response.status_code}
            if response.is_success: row["id"]=response.json()["id"]
            else: row["error"]=str(response.json().get("detail","Upload failed"))[:300]
            result["task196"]["documents"].append(row); save()
        queries=[
            ("Which PyInstaller version is pinned in requirements-build.txt?","requirements-build.txt",["6.22.3"]),
            ("Which build tool is named in requirements-build.txt?","requirements-build.txt",["pyinstaller"]),
            ("Which sentence embedding library is listed in requirements-knowledge.txt?","requirements-knowledge.txt",["sentence-transformers"]),
            ("Which vector database is listed in requirements-knowledge.txt?","requirements-knowledge.txt",["chromadb"]),
            ("According to task-223-native-python.md, which native UI toolkit was used in that historical spike?","task-223-native-python.md",["tk"]),
            ("According to task-223-native-python.md, what forgery protection was retained alongside session cookies?","task-223-native-python.md",["csrf"]),
            ("According to task-214-window-review.md, what is the maximum number of saved window descriptors?","task-214-window-review.md",["ten","10"]),
            ("According to task-214-window-review.md, does restoring windows replay an action?","task-214-window-review.md",["not","no","never"]),
            ("Which optional image library caused the failed full Python gate in task-223-prototype-shell.md?","task-223-prototype-shell.md",["pillow"]),
            ("Which phase was stopped at the verification gate in task-223-prototype-shell.md?","task-223-prototype-shell.md",["223"]),
        ]
        for question,expected,answers in queries:
            running(); started=time.perf_counter(); row={"question":question,"expected_source":expected,"accepted_strings":answers}
            try:
                cid=session.request("POST","/api/chat/conversations",{"agent_id":"local_worker"})["conversation"]["id"]
                preview=session.request("POST",f"/api/chat/conversations/{cid}/knowledge-preview",{"query":question,"scopes":[{"scope":"owner"}]})
                row["retrieved_sources"]=[item["source"] for item in preview.get("items",[])]
                row["expected_source_retrieved"]=expected in row["retrieved_sources"]
                response=session.request("POST",f"/api/chat/conversations/{cid}/messages",{
                    "text":question,"knowledge_enabled":True,"knowledge_scopes":[{"scope":"owner"}],"knowledge_preview_digest":preview["digest"]})
                answer=next((message["content"] for message in reversed(response["conversation"]["messages"]) if message["role"]=="assistant"),"")
                row["answer"]=answer; row["strict_string_match"]=any(value in answer.lower() for value in answers)
                import re
                row["inline_citation"]=bool(re.search(r"\[\d+\]",answer)); row["context_trace"]=response.get("context_trace",{})
                row["completed"]=True
            except Exception as error:
                running(); row.update(completed=False,strict_string_match=False,inline_citation=False,error_type=type(error).__name__,error=str(error)[:300])
            row["elapsed_ms"]=round((time.perf_counter()-started)*1000,2); result["task196"]["questions"].append(row); save()
            print(json.dumps({"stage":"196","question":question,"completed":row["completed"],"retrieved":row.get("retrieved_sources"),"match":row["strict_string_match"],"ms":row["elapsed_ms"]}),flush=True)
        # Inspect existing installed media packs only. Never install or record/play audio.
        if original_local_app_data: os.environ["LOCALAPPDATA"]=original_local_app_data
        from app.integrations.capability_packs import OptionalMediaPacks
        packs=OptionalMediaPacks()
        for identifier in ("eyes","ears","voice"):
            before=packs.preview(identifier)
            checked=packs.self_test(identifier) if before["state"] in {"installed","working"} else {"state":"not-installed","detail":"No installation attempted"}
            row={"pack_id":identifier,"before":before["state"],"result":checked,"capture_or_playback":False}
            result["task198"].append(row); print(json.dumps({"stage":"198",**row}),flush=True)
        result["ollama_after"]=local.get("/api/ps").json()
        result["completed"]=True; save()
    finally:
        session.close(); local.close(); save()


if __name__=="__main__": main()
