import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.knowledge.shipped_pack import ShippedPack
from app.providers import OllamaProvider
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime


class Embedding:
    identity='pack-test-embedding'
    def __init__(self):self.calls=[]
    def embed_batch(self,texts):self.calls.extend(texts);return [[1.,0.] for _ in texts]
    def embed_one(self,text):self.calls.append(text);return [1.,0.]


def test_pack_separate_cache_prefixes_and_rebuild(tmp_path):
    embedding=Embedding();pack=ShippedPack(embedding,tmp_path)
    assert pack.instant(' Hello! ')=='Hello! How can I help you today?'
    assert pack.instant('hello, open youtube') is None
    assert pack.instant('thanks but delete everything') is None
    assert embedding.calls==[]
    assert len(pack.retrieve('coding bug')['entries'])==3
    assert all(text.startswith(('search_document: ','search_query: ')) for text in embedding.calls)
    assert pack.digest in str(pack.index.cache_path)
    assert list(tmp_path.rglob('*.sqlite3'))==[pack.index.cache_path]
    second=Embedding();again=ShippedPack(second,tmp_path);again.retrieve('math')
    assert second.calls==['search_query: math']
    pack.index.cache_path.unlink();again=ShippedPack(Embedding(),tmp_path)
    assert again.retrieve('math')['mode']=='semantic'


def test_core_graph_is_exact_shipped_entries_without_user_store_or_embedding(tmp_path):
    embedding=Embedding();pack=ShippedPack(embedding,tmp_path);graph=pack.graph()
    chunks=[n for n in graph['nodes'] if n['kind']=='chunk']
    assert {n['snippet'] for n in chunks}=={e['text'] for e in pack.entries}
    assert len(chunks)==graph['total_chunks'] and embedding.calls==[]
    assert all(pack.inspect(n['id'])['read_only'] for n in chunks)
    assert not list(tmp_path.rglob('*.sqlite3'))


@pytest.fixture
def pack_chat(monkeypatch,tmp_path):
    import importlib
    module=importlib.import_module('app.knowledge.shipped_pack')
    pack=ShippedPack(Embedding(),tmp_path);monkeypatch.setattr(module,'_pack',pack)
    prompts=[]
    monkeypatch.setattr(OllamaProvider,'generate_chat',lambda self,model,messages:prompts.append(messages) or 'Verified fake reply.')
    runtime=create_corporation_runtime();app=create_local_app(password='test-owner-passphrase',application_service=runtime.application_service)
    with TestClient(app,base_url='http://127.0.0.1:8000',client=('127.0.0.1',50992)) as client:
        client.post('/api/local/login',json={'password':'test-owner-passphrase'},headers={'Origin':'http://127.0.0.1:8000'})
        headers={'Origin':'http://127.0.0.1:8000','X-Local-CSRF':client.get('/api/local/session').json()['csrf']}
        response=client.post('/api/chat/conversations',json={'agent_id':'local_worker'},headers=headers)
        assert response.status_code==200,response.text
        yield client,headers,response.json()['conversation']['id'],prompts


def test_instant_uses_owned_history_and_truthful_no_provider_trace(pack_chat):
    client,headers,cid,prompts=pack_chat
    path=f'/api/chat/conversations/{cid}/messages'
    response=client.post(path,json={'text':'Hello!','shipped_pack_enabled':True},headers=headers)
    assert response.status_code==200,response.text
    result=response.json();assert prompts==[]
    assert [m['content'] for m in result['conversation']['messages']]==['Hello!','Hello! How can I help you today?']
    assert result['context_trace']['answer_source']=='shipped-instant-reply'
    assert result['context_trace']['provider_called'] is False
    denied=client.post(path,json={'text':'hi','shipped_pack_enabled':True},headers={'Origin':headers['Origin']})
    assert denied.status_code==403
    client.post(f'/api/chat/conversations/{cid}/close',json={},headers=headers)
    closed=client.post(path,json={'text':'hi','shipped_pack_enabled':True},headers=headers)
    assert closed.status_code==422
    record=client.get(f'/api/chat/conversations/{cid}',headers=headers).json()['conversation']
    assert record['status']=='closed' and len(record['messages'])==2


def test_pack_system_and_untrusted_references_never_replace_raw_history(pack_chat):
    client,headers,cid,prompts=pack_chat
    response=client.post(f'/api/chat/conversations/{cid}/messages',headers=headers,json={'text':'Explain a coding bug','shipped_pack_enabled':True})
    assert response.status_code==200,response.text
    assert prompts[0][0]['role']=='system'
    assert 'spend limits' in prompts[0][0]['content']
    assert 'BEGIN UNTRUSTED SHIPPED GENERAL GUIDANCE' in json.dumps(prompts[0])
    assert response.json()['conversation']['messages'][0]['content']=='Explain a coding bug'
    guidance=response.json()['shipped_guidance']
    assert len(guidance['ids'])==3 and all(i.startswith('core:'+guidance['pack_hash']+':') for i in guidance['ids'])


@pytest.mark.parametrize('tool',[
    {'kind':'solve_equation','equation':'x*x=4'},
    {'kind':'convert_units','value':'1','source_unit':'in','target_unit':'cm'}])
@pytest.mark.parametrize('local_only',[False,True])
def test_new_math_tools_go_through_existing_reviewed_turn_trace(pack_chat,tool,local_only):
    client,headers,cid,prompts=pack_chat
    response=client.post(f'/api/chat/conversations/{cid}/messages',headers=headers,json={'text':'Use this reviewed exact tool','reviewed_tools':[tool],'exact_math_only':local_only})
    assert response.status_code==200,response.text
    trace=response.json()['context_trace']
    assert trace['tools'][0]['outcome']=='completed'
    assert trace['tools'][0]['tool']==tool['kind']
    if local_only:
        assert prompts==[] and trace['provider_called'] is False
        assert trace['answer_source']=='reviewed-exact-math'
        assert response.json()['conversation']['messages'][-1]['content'] in {'x = -2, 2','2.54 cm'}
    else:assert 'UNTRUSTED REVIEWED TOOL RESULTS' in json.dumps(prompts[0])


def test_local_math_invalid_combination_and_emergency_stop_fail_closed(pack_chat):
    client,headers,cid,prompts=pack_chat
    path=f'/api/chat/conversations/{cid}/messages'
    invalid=client.post(path,headers=headers,json={'text':'hi','shipped_pack_enabled':True,'exact_math_only':True})
    assert invalid.status_code==422 and prompts==[]
    stopped=client.post('/api/local/emergency-stop/stop',headers=headers,json={})
    assert stopped.status_code==200
    denied=client.post(path,headers=headers,json={'text':'math','exact_math_only':True,'reviewed_tools':[{'kind':'calculator','expression':'0.1+0.2'}]})
    assert denied.status_code==423 and prompts==[]


def test_streamed_instant_has_no_provider_call(pack_chat):
    client,headers,cid,prompts=pack_chat
    response=client.post(f'/api/chat/conversations/{cid}/messages/stream',headers=headers,json={'text':'Salamat!','shipped_pack_enabled':True})
    assert response.status_code==200,response.text
    events=[json.loads(line) for line in response.text.splitlines()]
    assert events[0]=={'type':'chunk','text':'Walang anuman!'}
    assert events[-1]['context_trace']['provider_called'] is False and prompts==[]
