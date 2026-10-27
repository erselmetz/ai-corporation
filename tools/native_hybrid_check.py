"""Frozen Task 224 source-retrieval comparison, not an answer-quality claim."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile,time
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    with httpx.Client(trust_env=False,timeout=5) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    model=next((m for m in response.json()['models'] if m['name']=='nomic-embed-text:latest'),None)
    if model is None:raise SystemExit('An installed local nomic-embed-text:latest is required. No download.')
    baseline=json.loads((ROOT/'review/task-224-brain-evidence.json').read_text())['source_check']
    profile=Path(tempfile.mkdtemp(prefix='ersel-hybrid-check-'));os.environ['LOCALAPPDATA']=str(profile);os.chdir(profile)
    from app.database import initialize_database
    from app.knowledge.native_brain import NativeBrain
    from app.application.services.chat_knowledge import AUTO_RETRIEVAL_STOPWORDS
    from app.runtime.factory import create_corporation_runtime
    from app.resources.context import application_service
    initialize_database();service=create_corporation_runtime().application_service;token=application_service.set(service)
    try:
        brain=NativeBrain(prefixed=True);manifest=[]
        for item in baseline['documents']:
            path=ROOT/item['path'];data=path.read_bytes()
            assert hashlib.sha256(data).hexdigest()==item['sha256'],'Frozen corpus changed'
            brain.feed('hybrid-check',str(path),path.name,data,consent=True);manifest.append(item)
        for name in ['requirements-knowledge.txt','README.md']:
            data=subprocess.check_output(['git','show','f074a8aac9c23a24d04751b2d0c0d501414a3aad:'+name],cwd=ROOT)
            brain.feed('hybrid-check','frozen-folder/'+name,name,data,consent=True)
            manifest.append({'path':'frozen-folder/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        results=[]
        for hybrid in [False,True]:
            cases=[]
            for case in baseline['cases']:
                words=tuple(dict.fromkeys(re.findall(r'[^\W_]+',case['question'].casefold())))
                lexical=' '.join(word for word in words if word not in AUTO_RETRIEVAL_STOPWORDS)
                started=time.perf_counter();found=brain.recall('hybrid-check',case['question'],5,.35,hybrid=hybrid,lexical_query=lexical)
                assert found['mode'].startswith('semantic') or found['mode']=='hybrid','Unexpected semantic outage'
                sources=[hit['source'].replace('\\','/').split('/')[-1] for hit in found['hits']]
                rank=next((i+1 for i,source in enumerate(sources) if source==case['expected']),None)
                cases.append(dict(case,rank=rank,sources=sources,ms=round((time.perf_counter()-started)*1000,2)))
            results.append({'hybrid':hybrid,'recall_at_5':sum(c['rank'] is not None for c in cases)/len(cases),
                'mrr':sum(1/c['rank'] if c['rank'] else 0 for c in cases)/len(cases),'cases':cases})
        report={'measurement':'Expected-source retrieval, same frozen questions/corpus; not held out or answer accuracy. Current table-aware chunking in both arms.',
            'model':model['name'],'model_digest':model['digest'],'threshold':.35,'rrf_k':60,'lexical':'BM25 k1=1.2 b=0.75',
            'corpus':manifest,'chunks':len(brain.rows('hybrid-check')),'results':results}
        (ROOT/'task226-review/hybrid-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({**{k:v for k,v in report.items() if k not in {'results','corpus'}},'results':[{k:v for k,v in result.items() if k!='cases'} for result in results]}))
    finally:application_service.reset(token)


if __name__=='__main__':main()
