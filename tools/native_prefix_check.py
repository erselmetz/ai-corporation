"""Local-only Task 225 before/after retrieval on Task 224's frozen real corpus."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


@contextmanager
def isolated_profile():
    previous=Path.cwd()
    with tempfile.TemporaryDirectory(prefix='ersel-prefix-') as directory:
        try:yield directory
        finally:os.chdir(previous)


def main():
    import argparse
    from frozen_corpus import document
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.output:args.output=args.output.resolve();args.output.parent.mkdir(parents=True,exist_ok=True)
    with httpx.Client(trust_env=False,timeout=5) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434 before this check.')
    model=next((m for m in response.json()['models'] if m['name']=='nomic-embed-text:latest'),None)
    if model is None:raise SystemExit('Installed nomic-embed-text:latest is required; no model will be downloaded.')
    baseline=json.loads((ROOT/'review/task-224-brain-evidence.json').read_text())['source_check']
    output=ROOT/'task225-review';output.mkdir(exist_ok=True)
    with isolated_profile() as directory:
        profile=Path(directory);os.environ['LOCALAPPDATA']=directory;os.chdir(profile)
        from app.database import initialize_database
        from app.knowledge.native_brain import NativeBrain
        initialize_database();brain=NativeBrain(prefixed=False);manifest=[]
        for item in baseline['documents']:
            path,data=document(ROOT,item)
            assert hashlib.sha256(data).hexdigest()==item['sha256'],'The real corpus changed; do not silently change the comparison.'
            brain.feed('prefix-check',str(path),path.name,data,consent=True);manifest.append(item)
        folder=profile/'chosen-folder';folder.mkdir()
        for name in ['requirements-knowledge.txt','README.md']:
            data=subprocess.check_output(['git','show','f074a8aac9c23a24d04751b2d0c0d501414a3aad:'+name],cwd=ROOT)
            path=folder/name;path.write_bytes(data)
            brain.feed('prefix-check',str(path),name,data,consent=True)
            manifest.append({'path':'frozen-folder/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        results=[]
        for prefixed in [False,True]:
            brain.prefixed=prefixed;brain.signature=None;cases=[]
            for case in baseline['cases']:
                started=time.perf_counter();found=brain.recall('prefix-check',case['question'],5,0)
                assert found['mode'].startswith('semantic'),'Lexical fallback is not a prefix comparison.'
                hits=found['hits'];sources=[hit['source'].replace('\\','/').split('/')[-1] for hit in hits]
                rank=next((i+1 for i,name in enumerate(sources) if name==case['expected']),None)
                cases.append({'question':case['question'],'expected':case['expected'],'rank':rank,'sources':sources,
                              'scores':[hit['score'] for hit in hits],'ms':round((time.perf_counter()-started)*1000,2)})
            thresholds=[]
            for threshold in [0,.25,.35,.45,.55,.65]:
                ranks=[next((i+1 for i,(source,score) in enumerate(zip(c['sources'],c['scores'])) if source==c['expected'] and score>=threshold),None) for c in cases]
                thresholds.append({'threshold':threshold,'recall_at_5':sum(r is not None for r in ranks)/len(ranks),
                                   'mrr':sum(1/r if r else 0 for r in ranks)/len(ranks)})
            results.append({'prefixed':prefixed,'cases':cases,'thresholds':thresholds})
        result={'model':model['name'],'model_digest':model['digest'],'corpus':manifest,'chunks':len(brain.rows('prefix-check')),
                'results':results,'measurement':'Expected-source retrieval only, not answer quality or independently held-out threshold tuning.'}
        (args.output or output/'prefix-comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'chunks':result['chunks'],'results':[{'prefixed':r['prefixed'],'thresholds':r['thresholds']} for r in results]}))


if __name__=='__main__':main()
