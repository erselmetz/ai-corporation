from datetime import datetime,timezone,timedelta
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from app.database import initialize_database
from app.knowledge.native_brain import NativeBrain,chunks,MAX_FILE_BYTES
from app.qt_desktop.intake import selected_files


class Embedding:
    identity="fake-embedding"
    def __init__(self): self.batches=[]; self.queries=[]
    def embed_batch(self,texts): self.batches.append(texts); return [[1.,0.] for _ in texts]
    def embed_one(self,text): self.queries.append(text); return [1.,0.]


@pytest.fixture
def brain(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); initialize_database(); return NativeBrain(Embedding())


def test_shared_store_stable_replace_unchanged_skip_and_restart(brain):
    result=brain.feed("owner","C:/chosen/facts.txt","facts.txt",b"alpha "*300,consent=True)
    assert result["chunks"]==3
    assert len(brain.rows("owner"))==3
    assert brain.rows("other")==[]
    calls=len(brain.embedding.batches)
    assert brain.feed("owner","C:/chosen/facts.txt","facts.txt",b"alpha "*300,consent=True)["state"]=="unchanged"
    assert len(brain.embedding.batches)==calls
    newer=brain.feed("owner","C:/chosen/facts.txt","facts.txt",b"replacement",consent=True)
    assert newer["replaced"]==3 and newer["chunks"]==1
    assert NativeBrain(Embedding()).rows("owner")[0]["content"]=="replacement"
    assert len(brain.graph("owner")["edges"])==1


def test_matrix_is_normalized_cached_and_forget_clears_derived_data(brain):
    brain.feed("owner","note-key","note.txt",b"alpha beta fact",consent=True)
    first=brain.recall("owner","alpha"); cached=brain.matrix
    second=brain.recall("owner","beta")
    assert brain.matrix is cached and first["hits"] and second["hits"]
    assert len(brain.embedding.batches)==1 and len(brain.embedding.queries)==2
    node=next(node for node in brain.graph("owner")["nodes"] if node["kind"]=="chunk")
    with pytest.raises(KeyError): brain.forget("other",node["record_id"],node["revision"])
    with pytest.raises(ValueError): brain.forget("owner",node["record_id"],"0"*64)
    brain.forget("owner",node["record_id"],node["revision"])
    assert not brain.rows("owner")
    import sqlite3
    with sqlite3.connect(brain.cache_path) as cache: assert cache.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]==0


def test_failed_save_rolls_back_without_replacing_previous_source(brain,monkeypatch):
    from app.memory import OwnerKnowledgeStore
    brain.feed("owner","same","a.txt",b"old fact",consent=True)
    original=OwnerKnowledgeStore._insert; count=0
    def fail(store,connection,record):
        nonlocal count
        count+=1
        if count==2: raise RuntimeError("injected storage failure")
        original(store,connection,record)
    monkeypatch.setattr(OwnerKnowledgeStore,"_insert",fail)
    with pytest.raises(RuntimeError): brain.feed("owner","same","a.txt",b"new "*500,consent=True)
    assert [row["content"] for row in brain.rows("owner")]==["old fact"]


def test_intake_bounds_consent_overlap_and_folder_pruning(brain,tmp_path):
    assert chunks("x"*900)==("x"*800,"x"*200)
    assert chunks('x'*800)==('x'*800,)  # No redundant trailing overlap-only node.
    assert chunks('x'*1500)==('x'*800,'x'*800)
    with pytest.raises(ValueError): brain.feed("owner","x","x.txt",b"x",consent=False)
    with pytest.raises(ValueError): brain.feed("owner","x",".env",b"secret",consent=True)
    with pytest.raises(ValueError): brain.feed("owner","x","x.txt",b"x"*(MAX_FILE_BYTES+1),consent=True)
    (tmp_path/".git").mkdir(); (tmp_path/".git"/"skip.txt").write_text("junk")
    (tmp_path/".env").write_text("secret"); (tmp_path/"safe.txt").write_text("keep")
    assert tmp_path/"safe.txt" in selected_files([tmp_path])
    assert all(path.name not in {"skip.txt",".env"} for path in selected_files([tmp_path]))


def test_native_feed_api_enforces_csrf_and_reports_real_graph(brain):
    from app.local import create_local_app
    from app.runtime.factory import create_corporation_runtime
    runtime=create_corporation_runtime()
    app=create_local_app(password="test-owner-password",origin="http://127.0.0.1:8000",application_service=runtime.application_service)
    app.state.native_brain=brain
    with TestClient(app,base_url="http://127.0.0.1:8000",client=("127.0.0.1",50000)) as client:
        assert client.get("/api/memory/owner/native-graph").status_code==401
        assert client.post("/api/local/login",json={"password":"test-owner-password"},headers={"Origin":"http://127.0.0.1:8000"}).status_code==200
        csrf=client.get("/api/local/session").json()["csrf"]
        fields={"stable_key":"chosen","consent":"true","days":"30","job_id":brain.new_job("local-owner")}
        assert client.post("/api/memory/owner/native-feed",data=fields,files={"file":("a.txt",b"a real fact")},headers={"Origin":"http://127.0.0.1:8000"}).status_code==403
        headers={"Origin":"http://127.0.0.1:8000","X-Local-CSRF":csrf}
        response=client.post("/api/memory/owner/native-feed",data=fields,files={"file":("a.txt",b"a real fact")},headers=headers)
        assert response.status_code==200,response.text
        graph=client.get("/api/memory/owner/native-graph").json()
        assert graph["total_chunks"]==1
        assert next(node for node in graph["nodes"] if node["kind"]=="chunk")["trust"]=="untrusted data"




def test_brain_cancel_before_and_during_embedding_never_commits_or_replays(brain):
    before=brain.new_job("owner"); brain.cancel_job("owner",before)
    with pytest.raises(RuntimeError): brain.feed("owner","a","a.txt",b"cancelled",consent=True,job_id=before)
    assert not brain.rows("owner")
    during=brain.new_job("owner")
    original=brain.embedding.embed_batch
    def cancel(texts): brain.cancel_job("owner",during); return original(texts)
    brain.embedding.embed_batch=cancel
    with pytest.raises(RuntimeError): brain.feed("owner","b","b.txt",b"also cancelled",consent=True,job_id=during)
    assert not brain.rows("owner")
    brain.embedding.embed_batch=original
    completed=brain.new_job("owner")
    brain.feed("owner","c","c.txt",b"retained",consent=True,job_id=completed)
    assert brain.cancel_job("owner",completed)=="completed"
    with pytest.raises(RuntimeError): brain.feed("owner","c","c.txt",b"retained",consent=True,job_id=completed)
    with pytest.raises(ValueError): brain.cancel_job("other",completed)


def test_brain_jobs_remain_bounded(brain):
    for _ in range(32): brain.new_job("owner")
    with pytest.raises(ValueError): brain.new_job("owner")


def test_cancellation_accepted_during_storage_rolls_back_source_replacement(brain,monkeypatch):
    from app.memory import OwnerKnowledgeStore
    brain.feed('owner','same','facts.txt',b'original fact',consent=True)
    job=brain.new_job('owner'); insert=OwnerKnowledgeStore._insert
    def cancel(store,connection,record):
        insert(store,connection,record)
        brain.cancel_job('owner',job)
    monkeypatch.setattr(OwnerKnowledgeStore,'_insert',cancel)
    with pytest.raises(RuntimeError,match='cancelled'):
        brain.feed('owner','same','facts.txt',b'replacement '*200,consent=True,job_id=job)
    assert [row['content'] for row in brain.rows('owner')]==['original fact']
    assert brain.cancel_job('owner',job)=='cancelled'


def test_advanced_memory_delete_erases_native_derived_cache_and_stale_hits(brain):
    import sqlite3
    from app.runtime.factory import create_corporation_runtime
    from app.memory import MemoryScope
    service=create_corporation_runtime().application_service
    shared=service.native_brain(stopper=lambda:False); shared.embedding=Embedding()
    shared.feed('owner','file','file.txt',b'private retained fact',consent=True)
    shared.recall('owner','private')
    row=shared.rows('owner')[0]
    assert shared.matrix
    service.memory_management().remove(row['id'],actor_id='owner',scope=MemoryScope.OWNER,scope_id='owner')
    assert not shared.rows('owner') and not shared.matrix
    with sqlite3.connect(shared.cache_path) as db: assert db.execute('SELECT COUNT(*) FROM vectors').fetchone()[0]==0
    assert shared.recall('owner','private')=={'mode':'empty','hits':[]}


def test_expiry_is_checked_as_aware_time_not_lexicographic_sql_text(brain):
    from app.database.connection import get_connection
    brain.feed("owner","time","time.txt",b"expired fact",consent=True)
    expiry=(datetime.now(timezone.utc)-timedelta(seconds=1)).astimezone(timezone(timedelta(hours=8))).isoformat()
    connection=get_connection()
    with connection: connection.execute("UPDATE owner_knowledge SET expires_at=? WHERE owner_id=?",(expiry,"owner"))
    connection.close()
    assert brain.rows("owner")==[]
    assert brain.graph("owner")["total_chunks"]==0
    assert brain.recall("owner","expired")=={"mode":"empty","hits":[]}
    assert not brain.embedding.queries
