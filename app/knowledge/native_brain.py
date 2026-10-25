"""One owner Brain: atomic source replacement in existing private knowledge storage."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import RLock
from uuid import uuid4
import json
import math
import sqlite3

from app.database.connection import get_connection, DATABASE_PATH
from app.memory import MemoryRecord, MemoryScope, MemoryType, OwnerKnowledgeStore
from .intake import source_name, _TEXT_SUFFIXES
from .providers import OllamaEmbeddingProvider

MAX_FILE_BYTES=5*1024*1024
MAX_CHUNKS=2000
MAX_ROWS=10000
MAX_MATRIX_CELLS=4_000_000
MAX_GRAPH_CHUNKS=2000
SKIP_DIRS={".git","node_modules","__pycache__",".venv","venv","env","dist","build",".idea",".vscode"}


def secret_path(path):
    name=Path(str(path)).name.lower()
    return (name.startswith(".env") or name in {"id_rsa","id_ed25519","credentials.json","secrets.json"}
            or Path(name).suffix in {".key",".pem",".pfx",".p12"} or "private_key" in name)


def chunks(text):
    if not isinstance(text,str) or not text.strip(): raise ValueError("Source contains no text")
    pieces=[]
    for start in range(0,len(text),700):
        piece=text[start:start+800].strip()
        if piece: pieces.append(piece)
        if start+800>=len(text): break
    result=tuple(pieces)
    if len(result)>MAX_CHUNKS: raise ValueError("Source exceeds the 2000-chunk safety limit")
    return result


def extract(filename,data):
    if not data or len(data)>MAX_FILE_BYTES: raise ValueError("Choose a nonempty file up to 5 MB")
    if secret_path(filename): raise ValueError("Secret-looking files cannot be fed")
    suffix=Path(filename).suffix.lower()
    if suffix in _TEXT_SUFFIXES: return data.decode("utf-8-sig",errors="strict")
    if suffix==".pdf":
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(data),strict=True)
        if reader.is_encrypted or not 1<=len(reader.pages)<=100: raise ValueError("PDF must be unencrypted and at most 100 pages")
        parts=[]; size=0
        for page in reader.pages:
            text=page.extract_text() or ""; size+=len(text.encode("utf-8"))
            if size>MAX_FILE_BYTES: raise ValueError("Extracted PDF exceeds 5 MB")
            parts.append(text)
        return "\n".join(parts)
    if suffix==".docx":
        from .intake import _extract_docx
        return _extract_docx(data)
    raise ValueError("Unsupported file type")


def normalized(vector):
    values=tuple(float(value) for value in vector)
    if not 1<=len(values)<=4096 or any(not math.isfinite(value) for value in values): raise ValueError("Invalid embedding")
    length=math.sqrt(sum(value*value for value in values))
    if not length: raise ValueError("Zero embedding")
    return tuple(value/length for value in values)


class NativeBrain:
    def __init__(self,embedding=None,*,prefixed=True,invalidator=None,stopper=lambda:False):
        self.embedding=embedding or OllamaEmbeddingProvider("nomic-embed-text:latest")
        self.prefixed=prefixed; self.lock=RLock(); self.matrix=(); self.signature=None
        self.invalidator=invalidator
        self.stopper=stopper
        self.faiss_index=None; self.numpy=None
        self.jobs={}; self.jobs_lock=RLock()
        self.cache_path=Path(DATABASE_PATH).parent/"native_embedding_cache.sqlite3"

    def _key(self,text,query=False):
        prefix=("search_query: " if query else "search_document: ") if self.prefixed else ""
        return prefix+text

    def new_job(self,owner):
        with self.jobs_lock:
            active=[job for job in self.jobs.values() if job[0]==owner and job[1] in {"pending","running"}]
            if len(active)>=32: raise ValueError("Too many active Brain jobs")
            if len(self.jobs)>=256:
                for key,value in list(self.jobs.items()):
                    if value[1] not in {"pending","running"}: del self.jobs[key]
                    if len(self.jobs)<192: break
            if len(self.jobs)>=256: raise ValueError("Brain job capacity reached")
            identifier=uuid4().hex; self.jobs[identifier]=(owner,"pending"); return identifier

    def cancel_job(self,owner,identifier):
        with self.jobs_lock:
            job=self.jobs.get(identifier)
            if job is None or job[0]!=owner: raise ValueError("Brain job unavailable")
            if job[1] in {"pending","running"}: self.jobs[identifier]=(owner,"cancelled")
            return self.jobs[identifier][1]

    def finish_job(self,owner,identifier,state="completed"):
        with self.jobs_lock:
            if self.jobs.get(identifier)==(owner,"running"): self.jobs[identifier]=(owner,state)

    def check_job(self,owner,identifier):
        if self.stopper(): raise RuntimeError("Protected activity is stopped")
        if identifier is None: return
        with self.jobs_lock:
            if self.jobs.get(identifier)!=(owner,"running"): raise RuntimeError("Brain ingestion cancelled or job unavailable")

    def vectors(self,texts,*,persist=True,check=lambda:None):
        self.cache_path.parent.mkdir(parents=True,exist_ok=True)
        identity=self.embedding.identity
        keys=[sha256((identity+"\0"+self._key(text)).encode()).hexdigest() for text in texts]
        with self.lock, closing(sqlite3.connect(self.cache_path,timeout=30)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS vectors(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            result=[None]*len(texts); missing=[]
            for i,key in enumerate(keys):
                check()
                row=db.execute("SELECT value FROM vectors WHERE key=?",(key,)).fetchone()
                try: result[i]=normalized(json.loads(row[0])) if row else None
                except (ValueError,TypeError): result[i]=None
                if result[i] is not None and len(texts)*len(result[i])>MAX_MATRIX_CELLS: raise RuntimeError("Semantic matrix budget exceeded")
                if result[i] is None: missing.append(i)
            for start in range(0,len(missing),32):
                check()
                indices=missing[start:start+32]
                batch=self.embedding.embed_batch([self._key(texts[i]) for i in indices])
                check()
                if len(batch)!=len(indices): raise ValueError("Embedding count mismatch")
                for i,vector in zip(indices,batch):
                    result[i]=normalized(vector)
                    if len(texts)*len(result[i])>MAX_MATRIX_CELLS: raise RuntimeError("Semantic matrix budget exceeded")
                    db.execute("INSERT OR REPLACE INTO vectors VALUES(?,?)",(keys[i],json.dumps(result[i])))
            if persist: db.commit()
        return tuple(result)

    def _save_vectors(self,texts,vectors):
        with closing(sqlite3.connect(self.cache_path,timeout=30)) as db,db:
            db.executemany("INSERT OR REPLACE INTO vectors VALUES(?,?)",[(sha256((self.embedding.identity+"\0"+self._key(text)).encode()).hexdigest(),json.dumps(vector)) for text,vector in zip(texts,vectors)])

    def _drop_vectors(self,texts):
        if not self.cache_path.exists(): return
        keys=[sha256((self.embedding.identity+"\0"+prefix+text).encode()).hexdigest()
              for text in texts for prefix in ("","search_document: ")]
        with closing(sqlite3.connect(self.cache_path,timeout=30)) as db,db:
            db.executemany("DELETE FROM vectors WHERE key=?",[(key,) for key in keys])

    def invalidate_derived(self):
        """A memory edit/delete invalidates rebuildable vectors, never user notes."""
        with self.lock:
            self.signature=None; self.matrix=(); self.faiss_index=None; self.numpy=None
            if self.cache_path.exists():
                with closing(sqlite3.connect(self.cache_path,timeout=30)) as db,db:
                    db.execute('DELETE FROM vectors')

    def feed(self,owner,stable_key,filename,data,*,consent,days=30,job_id=None):
        with self.lock:
            return self._feed(owner,stable_key,filename,data,consent=consent,days=days,job_id=job_id)

    def _feed(self,owner,stable_key,filename,data,*,consent,days,job_id):
        if job_id is not None:
            with self.jobs_lock:
                if self.jobs.get(job_id)!=(owner,"pending"): raise RuntimeError("Brain ingestion cancelled or job unavailable")
                self.jobs[job_id]=(owner,"running")
        check=lambda:self.check_job(owner,job_id)
        check()
        if consent is not True: raise ValueError("Explicit local retention consent is required")
        if not isinstance(stable_key,str) or not 1<=len(stable_key)<=4096: raise ValueError("Invalid source key")
        if type(days) is not int or not 1<=days<=30: raise ValueError("Retention must be 1 to 30 days")
        now=datetime.now(timezone.utc); digest=sha256(data).hexdigest()
        key=sha256((owner+"\0"+stable_key).encode()).hexdigest(); prefix="native:"+key+":"
        text=extract(filename,data); pieces=chunks(text)
        with closing(get_connection()) as db:
            old=db.execute("SELECT id,content,expires_at FROM owner_knowledge WHERE owner_id=? AND substr(id,1,?)=?",
                           (owner,len(prefix),prefix)).fetchall()
        expected={prefix+digest+":"+str(i):piece for i,piece in enumerate(pieces)}
        if len(old)==len(pieces) and all(expected.get(row["id"])==row["content"] and datetime.fromisoformat(row["expires_at"])>now for row in old):
            return {"state":"unchanged","chunks":len(pieces),"source":source_name(filename)}
        semantic="ready"
        vectors=None
        try: vectors=self.vectors(pieces,persist=False,check=check)
        except (ValueError,RuntimeError,OSError,sqlite3.Error): semantic="lexical-ready"
        check()
        expiry=now+timedelta(days=days); name=source_name(filename)
        reference=stable_key if Path(stable_key).is_absolute() and len(stable_key.encode())<=256 else name+" ["+key[:12]+"]"
        reference=reference.encode()[:256].decode("utf-8",errors="ignore")
        records=[MemoryRecord(prefix+digest+":"+str(i),owner,MemoryScope.OWNER,owner,MemoryType.NOTE,
                              piece,reference,now,expiry,True) for i,piece in enumerate(pieces)]
        store=OwnerKnowledgeStore()
        if self.invalidator:
            for row in old: self.invalidator(row["id"],scope=MemoryScope.OWNER,scope_id=owner)
        self._drop_vectors([row["content"] for row in old])
        with self.lock, closing(get_connection()) as db, db:
            check()
            db.execute("BEGIN IMMEDIATE")
            count=db.execute("SELECT COUNT(*) FROM owner_knowledge WHERE owner_id=?",(owner,)).fetchone()[0]
            replacing=db.execute("SELECT COUNT(*) FROM owner_knowledge WHERE owner_id=? AND substr(id,1,?)=?",(owner,len(prefix),prefix)).fetchone()[0]
            if count-replacing+len(records)>MAX_ROWS: raise ValueError("Owner Brain capacity reached")
            db.execute("DELETE FROM owner_knowledge WHERE owner_id=? AND substr(id,1,?)=?",(owner,len(prefix),prefix))
            for record in records: store._insert(db,record)
            with self.jobs_lock:
                check()  # Accepted cancellation/stop during storage rolls back too.
                db.commit()
                if job_id is not None: self.jobs[job_id]=(owner,"completed")
            self.signature=None
        if vectors is not None:
            try: self._save_vectors(pieces,vectors)
            except (OSError,sqlite3.Error): semantic="lexical-ready"
        return {"state":semantic,"chunks":len(records),"replaced":len(old),"source":name}

    def rows(self,owner):
        now=datetime.now(timezone.utc); result=[]; store=OwnerKnowledgeStore()
        with closing(get_connection()) as db:
            rows=db.execute("SELECT * FROM owner_knowledge WHERE owner_id=? AND scope_id=? AND retention_opt_in=1 ORDER BY id LIMIT ?",(owner,owner,MAX_ROWS)).fetchall()
            for row in rows:
                try: record=store._record(row)
                except (ValueError,TypeError): continue
                if record.created_at<=now<record.expires_at: result.append(dict(row))
        return result

    def graph(self,owner):
        nodes=[]; sources={}; edges=[]; total=0
        for row in self.rows(owner):
            key=row["id"].split(":")[1] if row["id"].startswith("native:") else row["id"]
            source="source:"+key
            sources[source]={"id":source,"kind":"document","label":row["source_id"],"cluster":key}
            for i,piece in enumerate(chunks(row["content"])):
                total+=1
                if len(nodes)>=MAX_GRAPH_CHUNKS: continue
                identifier=row["id"]+"#"+str(i)
                nodes.append({"id":identifier,"record_id":row["id"],"kind":"chunk","cluster":key,
                              "source":row["source_id"],"snippet":piece,"date":row["created_at"],"trust":"untrusted data",
                              "expires_at":row["expires_at"],
                              "revision":sha256(row["content"].encode()).hexdigest()})
                edges.append({"from":source,"to":identifier,"kind":"same-source"})
        return {"nodes":[*sources.values(),*nodes],"edges":edges,"total_chunks":total,"grouped_chunks":total-len(nodes)}

    def inspect(self,owner,identifier):
        memory_id,separator,position=identifier.rpartition("#")
        if not separator or not position.isdecimal() or not 0<=int(position)<16: raise KeyError("Brain chunk unavailable")
        for row in self.rows(owner):
            if row["id"]==memory_id:
                parts=chunks(row["content"]); index=int(position)
                if index>=len(parts): break
                return {"id":identifier,"record_id":memory_id,"source":row["source_id"],"snippet":parts[index],
                        "date":row["created_at"],"expires_at":row["expires_at"],"trust":"untrusted data",
                        "revision":sha256(row["content"].encode()).hexdigest()}
        raise KeyError("Brain chunk unavailable or expired")

    def forget(self,owner,record_id,revision):
        with self.lock,closing(get_connection()) as db,db:
            row=db.execute("SELECT content FROM owner_knowledge WHERE owner_id=? AND scope_id=? AND id=?",(owner,owner,record_id)).fetchone()
            if row is None: raise KeyError("Brain item is unavailable")
            if sha256(row[0].encode()).hexdigest()!=revision: raise ValueError("Brain item changed; inspect it again")
            if self.invalidator: self.invalidator(record_id,scope=MemoryScope.OWNER,scope_id=owner)
            self._drop_vectors(chunks(row[0]))
            deleted=db.execute("DELETE FROM owner_knowledge WHERE owner_id=? AND scope_id=? AND id=? AND content=?",(owner,owner,record_id,row[0]))
            if not deleted.rowcount: raise ValueError("Brain item changed; inspect it again")
            self.signature=None

    def recall(self,owner,query,k=5,threshold=.35):
        with self.lock:
            return self._recall(owner,query,k,threshold)

    def _recall(self,owner,query,k,threshold):
        rows=self.rows(owner); entries=[(row,i,text) for row in rows for i,text in enumerate(chunks(row["content"]))]
        if not entries: return {"mode":"empty","hits":[]}
        signature=(owner,self.prefixed,tuple((row["id"],row["content"],row["expires_at"]) for row in rows))
        mode="semantic"
        try:
            with self.lock:
                if signature!=self.signature:
                    vectors=self.vectors([text for _,_,text in entries]) if entries else ()
                    if vectors and len(vectors)*len(vectors[0])>MAX_MATRIX_CELLS: raise RuntimeError("Semantic matrix budget exceeded; use lexical retrieval")
                    self.matrix=tuple(zip(entries,vectors)); self.signature=signature
                    self.faiss_index=None; self.numpy=None
                    try:
                        from .faiss_pack import OptionalFaissPack,application_data_root,activate_faiss_pack
                        pack=OptionalFaissPack(application_data_root())
                        if vectors and pack.preview()["state"]=="installed":
                            activate_faiss_pack(pack.site_packages)
                            import numpy,faiss
                            index=faiss.IndexFlatIP(len(vectors[0])); index.add(numpy.asarray(vectors,dtype=numpy.float32))
                            self.faiss_index=index; self.numpy=numpy
                    except (ImportError,RuntimeError,OSError,ValueError): pass
                matrix=self.matrix
            q=normalized(self.embedding.embed_one(self._key(query,query=True)))
            if self.faiss_index is not None and matrix and len(q)==len(matrix[0][1]):
                distances,indices=self.faiss_index.search(self.numpy.asarray([q],dtype=self.numpy.float32),min(10,k,len(matrix)))
                scores=[(float(score),matrix[int(index)][0]) for score,index in zip(distances[0],indices[0]) if index>=0]
                mode="semantic-faiss"
            else: scores=[(sum(a*b for a,b in zip(vector,q)),entry) for entry,vector in matrix if len(vector)==len(q)]
        except (ValueError,RuntimeError,OSError,sqlite3.Error):
            import re
            mode="lexical"; terms=set(re.findall(r"\w+",query.lower()))
            scores=[(len(terms & set(re.findall(r"\w+",text.lower())))/max(1,len(terms)),(row,i,text)) for row,i,text in entries]
        active={row['id']:row['content'] for row in self.rows(owner)}
        return {"mode":mode,"hits":[{"id":row["id"]+"#"+str(i),"source":row["source_id"],"text":text,"score":score,"trust":"untrusted data"}
                for score,(row,i,text) in sorted(scores,key=lambda item:item[0],reverse=True)[:min(10,k)]
                if score>=threshold and active.get(row['id'])==row['content']]}
