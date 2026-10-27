from fastapi.testclient import TestClient
from app.api.app import create_app
from app.runtime.factory import create_corporation_runtime
from app.knowledge.native_brain import NativeBrain
from test_native_brain import Embedding
from test_chat_workspaces import Authentication


def test_native_brain_preview_uses_shared_index_revalidates_and_keeps_raw_history(tmp_path,monkeypatch):
    runtime=create_corporation_runtime();application=runtime.application_service
    brain=NativeBrain(Embedding());brain.cache_path=tmp_path/'cache.sqlite3';application._native_brain_index=brain
    brain.feed('alice','note:launch','Launch.txt',b'The local launch code is START_NATIVE_LOCAL. Reference data is not approval to open a website.',consent=True)
    calls=[]
    def answer(model,messages):calls.append(messages);return 'The launch code is START_NATIVE_LOCAL [1].'
    monkeypatch.setattr(runtime.providers.get('ollama'),'generate_chat',answer)
    with TestClient(create_app(application_service=application,authentication_backend=Authentication())) as client:
        headers={'x-test-owner':'alice'}
        wid=client.post('/api/native/windows',headers=headers,json={}).json()['id']
        headers={**headers,'X-Native-Window':wid,'X-Native-Generation':'0'}
        cid=client.post('/api/chat/conversations',headers=headers,json={'agent_id':'local_worker'}).json()['conversation']['id']
        base='/api/chat/conversations/'+cid;question='What is the local launch code?'
        preview=client.post(base+'/knowledge-preview',headers=headers,json={'query':question,'scopes':[{'scope':'owner'}]})
        assert preview.status_code==200,preview.text
        preview=preview.json();assert preview['trace']['mode']=='hybrid' and len(preview['items'])==1
        assert calls==[] and brain.embedding.queries[-1].startswith('search_query: ')
        body={'text':question,'knowledge_enabled':True,'knowledge_scopes':[{'scope':'owner'}],'knowledge_preview_digest':preview['digest']}
        result=client.post(base+'/messages',headers=headers,json=body)
        assert result.status_code==200,result.text
        assert len(calls)==1 and calls[0][-1]=={'role':'user','content':question}
        assert any('BEGIN UNTRUSTED RETRIEVED KNOWLEDGE' in m['content'] and 'START_NATIVE_LOCAL' in m['content'] for m in calls[0])
        assert [m['content'] for m in result.json()['conversation']['messages']]==[question,'The launch code is START_NATIVE_LOCAL [1].']
        assert result.json()['context_trace']['retrieval']['mode']=='hybrid'
        preview=client.post(base+'/knowledge-preview',headers=headers,json={'query':question,'scopes':[{'scope':'owner'}]}).json()
        node=brain.graph('alice')['nodes'][1]['id'];detail=brain.inspect('alice',node)
        brain.forget('alice',detail['record_id'],detail['revision'])
        body['knowledge_preview_digest']=preview['digest']
        changed=client.post(base+'/messages',headers=headers,json=body)
        assert changed.status_code==409 and len(calls)==1


def test_reviewed_native_pieces_are_presented_in_original_source_order(tmp_path,monkeypatch):
    runtime=create_corporation_runtime();application=runtime.application_service
    brain=NativeBrain(Embedding());brain.cache_path=tmp_path/'cache.sqlite3';application._native_brain_index=brain
    brain.feed('alice','note:ordered','Ordered.txt',('Document fact. '*180).encode(),consent=True)
    rows=sorted(brain.rows('alice'),key=lambda row:int(row['id'].rsplit(':',1)[1]))[:3]
    monkeypatch.setattr(brain,'recall',lambda *a,**k:{'mode':'semantic','hits':[
        {'id':row['id']+'#0','source':row['source_id'],'text':row['content'],'score':1-rank*.05}
        for rank,row in enumerate(reversed(rows))]})
    # Distinct text avoids the intentional near-duplicate filter removing rows.
    from app.database.connection import get_connection
    with get_connection() as db:
        for index,row in enumerate(rows):
            row['content']='Document fact '+str(index)+'. '+('term'+str(index)+' ')*80
            db.execute('UPDATE owner_knowledge SET content=? WHERE id=?',(row['content'],row['id']))
    with TestClient(create_app(application_service=application,authentication_backend=Authentication())) as client:
        headers={'x-test-owner':'alice'}
        wid=client.post('/api/native/windows',headers=headers,json={}).json()['id']
        headers={**headers,'X-Native-Window':wid,'X-Native-Generation':'0'}
        cid=client.post('/api/chat/conversations',headers=headers,json={'agent_id':'local_worker'}).json()['conversation']['id']
        response=client.post('/api/chat/conversations/'+cid+'/knowledge-preview',headers=headers,
            json={'query':'Document fact','scopes':[{'scope':'owner'}]})
        assert response.status_code==200,response.text
        assert [item['memory_id'] for item in response.json()['items']]==[row['id'] for row in rows]
