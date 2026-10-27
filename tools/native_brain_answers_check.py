"""Real local answer measurements through owned chat over the frozen real corpus.

No facts or expected answers are inserted into prompts; checks are evaluation only.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile,threading,time
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def fact_match(index,answer):
    patterns=[r'6\.22\.3',r'pyinstaller',r'sentence[- ]transformers',r'chroma(?:db)?',r'\btk(?:inter)?\b',r'\bcsrf\b',
              r'\b(?:ten|10)\b',r'\b(?:no|not|never|without|doesn.t)\b',r'pillow|\bPIL\b',r'\b223\b']
    return bool(re.search(patterns[index],answer,re.I))


def main():
    with httpx.Client(trust_env=False,timeout=5) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    installed={m['name']:m for m in response.json()['models']}
    assert {'qwen3.5:4b','nomic-embed-text:latest'}.issubset(installed),'Required installed models missing; no download'
    baseline=json.loads((ROOT/'review/task-224-brain-evidence.json').read_text())['source_check']
    profile=Path(tempfile.mkdtemp(prefix='ersel-real-brain-answers-'));os.environ['LOCALAPPDATA']=str(profile);os.chdir(profile)
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.transport import Transport,Chat
    session=NativeSession();transport=Transport(session);report={'kind':'Real local owned API, frozen repository documents, not physical UI or held-out quality',
        'models':{name:installed[name]['digest'] for name in ['qwen3.5:4b','nomic-embed-text:latest']},'corpus':[],'cases':[]}
    output=ROOT/'task226-review/real-brain-answers.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    try:
        wid=session.request('POST','/api/native/windows',{})['id'];stop=threading.Event()
        for item in baseline['documents']:
            path=ROOT/item['path'];data=path.read_bytes()
            assert hashlib.sha256(data).hexdigest()==item['sha256'],'Frozen corpus changed'
            result=transport.feed_data(wid,str(path),path.name,data,stop)
            assert result['state']=='ready',result
            report['corpus'].append(item)
        folder=profile/'chosen-folder';folder.mkdir()
        for name in ['requirements-knowledge.txt','README.md']:
            data=subprocess.check_output(['git','show','f074a8aac9c23a24d04751b2d0c0d501414a3aad:'+name],cwd=ROOT)
            (folder/name).write_bytes(data);transport.feed_file(wid,folder/name,stop)
            report['corpus'].append({'path':'frozen-folder/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        for index,case in enumerate(baseline['cases']):
            chat=Chat('qwen3.5:4b','local_worker','',window_id=wid,reply_seconds=60)
            preview=transport.preview_knowledge(chat,case['question']);events=[];error=None;started=time.perf_counter()
            try:transport.send(chat,case['question'],stop,events.append,knowledge={'knowledge_enabled':True,
                'knowledge_scopes':[{'scope':'owner','scope_id':''}],'knowledge_preview_digest':preview['digest']})
            except Exception as failure:error=str(failure)[:300]
            answer=''.join(event.get('text','') for event in events if event.get('type')=='chunk')
            completed=any(event.get('type')=='complete' for event in events) and not any(event.get('type')=='error' for event in events) and error is None
            citations=[int(value) for value in re.findall(r'\[(\d+)\]',answer)]
            valid=[value for value in citations if 1<=value<=len(preview['items'])]
            supported=any(preview['items'][value-1]['source'].replace('\\','/').split('/')[-1]==case['expected'] for value in valid)
            # Read through the exact owning workspace; never treat a permission
            # failure as evidence of empty history.
            response=session.client.get('/api/chat/conversations/'+chat.conversation,headers={'X-Chat-Workspace':chat.workspace,
                'X-Native-Window':wid,'X-Native-Generation':'0'});response.raise_for_status();record=response.json()
            users=[m['content'] for m in record['conversation']['messages'] if m['role']=='user']
            assert users==[case['question']],users
            sources=[p['source'].replace('\\','/').split('/')[-1] for p in preview['items']]
            item={'question':case['question'],'expected':case['expected'],
                'baseline_retrieval':{key:value for key,value in case.items() if key not in {'question','expected'}},
                'answer':answer,'completed':completed,'error':error,'events':[e for e in events if e.get('type')=='error'],
                'fact_match':completed and fact_match(index,answer),'has_valid_citation':completed and bool(valid),
                'cites_expected_source':completed and supported,'sources':sources,
                'retrieval_rank':next((i+1 for i,name in enumerate(sources) if name==case['expected']),None),
                'retrieval_mode':preview.get('trace',{}).get('mode'),'preview':preview,
                'ms':round((time.perf_counter()-started)*1000,2),'raw_user_history_verified':True}
            report['cases'].append(item);save();print(json.dumps(item),flush=True)
        report['summary']={key:sum(bool(item[key]) for item in report['cases']) for key in ['completed','fact_match','has_valid_citation','cites_expected_source']}
        report['summary']['questions']=len(report['cases'])
        report['summary']['interpretation']='fact_match is a named-fact token check, not full semantic accuracy. Valid citation markers and expected-source citations do not establish that every claim is supported.'
        save();print(json.dumps(report['summary']))
    finally:session.close()


if __name__=='__main__':main()
