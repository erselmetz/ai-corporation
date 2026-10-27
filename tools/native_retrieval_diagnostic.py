"""Fresh-profile local retrieval diagnosis over one fixed public repo document."""
import json,os,sys,tempfile
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    with httpx.Client(timeout=5,trust_env=False) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    source=ROOT/'review/task-223-qt-shell.md';data=source.read_bytes()
    profile=Path(tempfile.mkdtemp(prefix='ersel-retrieval-diagnostic-'))
    os.environ['LOCALAPPDATA']=str(profile);os.chdir(profile)
    from app.database import initialize_database
    from app.knowledge.native_brain import NativeBrain
    from app.runtime.factory import create_corporation_runtime
    from app.resources.context import application_service
    initialize_database();service=create_corporation_runtime().application_service
    token=application_service.set(service)
    try:
        brain=NativeBrain();brain.feed('diagnostic-owner','repo:task223',source.name,data,consent=True)
        report=[]
        for query,hybrid in [('Which UI toolkit won the comparison, and how many nodes were tested?',False),('ui toolkit won comparison nodes tested',False),('Which UI toolkit won the comparison, and how many nodes were tested?',True)]:
            recalled=brain.recall('diagnostic-owner',query,k=10,hybrid=hybrid,lexical_query='ui toolkit won comparison nodes tested')
            report.append({'query':query,'mode':recalled['mode'],'hits':[
                {'chunk':hit['id'].split(':')[-1],'score':hit['score'],'has_qpainter':'QPainter' in hit['text'],
                 'has_300':'300' in hit['text'],'snippet':hit['text'][:100]} for hit in recalled['hits']]})
        output=ROOT/'task226-review';output.mkdir(exist_ok=True)
        (output/'retrieval-diagnostic.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
    finally:application_service.reset(token)


if __name__=='__main__':main()
