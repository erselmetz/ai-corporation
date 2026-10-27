"""Real local private-Brain preview/citation journey over one repository document."""
import json,os,sys,tempfile,time,re
from hashlib import sha256
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    with httpx.Client(timeout=5,trust_env=False) as client:
        try:r=client.get('http://127.0.0.1:11434/api/tags');r.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    required={'qwen3.5:4b','nomic-embed-text:latest'}
    assert required.issubset({m['name'] for m in r.json()['models']}),'Required installed local models are missing; no download.'
    source=ROOT/'review/task-223-qt-shell.md';data=source.read_bytes()
    output=ROOT/'task226-review';output.mkdir(exist_ok=True)
    os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='ersel-brain-chat226-')
    os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11434';os.chdir(os.environ['LOCALAPPDATA'])
    from PySide6.QtWidgets import QApplication,QPushButton
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    app=QApplication([]);session=NativeSession();manager=ShellManager(app,session);previews=[];chunks=[]
    original_post=session.client.post;original_send=session.send
    def post(path,*args,**kwargs):
        response=original_post(path,*args,**kwargs)
        if str(path).endswith('/knowledge-preview') and response.is_success:previews.append(response.json())
        return response
    def send(workspace,conversation,text,stop,emit,**kwargs):
        def observe(event):
            if event.get('type')=='chunk':chunks.append(event['text'])
            emit(event)
        return original_send(workspace,conversation,text,stop,observe,**kwargs)
    session.client.post=post;session.send=send
    def wait(predicate,seconds=120):
        end=time.monotonic()+seconds
        while not predicate():
            app.processEvents();QTest.qWait(20)
            if time.monotonic()>end:raise RuntimeError('Private-Brain source check timed out')
    try:
        window=manager.new_window();wait(lambda:window.model.count()>0)
        window.model.setCurrentIndex(window.model.findData('qwen3.5:4b'))
        result=manager.transport.feed_data(window.native_id,str(source),source.name,data,window.feed_stop,generation=window.native_generation)
        assert result['state']=='ready',result
        manager.refresh_brain();wait(lambda:manager.graph is not None and manager.graph.get('user_chunks',0)>0)
        window.use_brain.setChecked(True)
        window.reply_limit.setCurrentIndex(window.reply_limit.findData(60))
        question='Which UI toolkit won the comparison, and how many nodes were tested?'
        window.composer.setPlainText(question);started=time.perf_counter();window.send()
        wait(lambda:window.knowledge_review.dialog is not None or not window.busy)
        assert window.knowledge_review.dialog is not None,window.status.text()
        window.knowledge_review.dialog.grab().save(str(output/'private-brain-source-preview.png'))
        next(b for b in window.knowledge_review.dialog.findChildren(QPushButton) if b.text()=='Use these sources for this message').click()
        wait(lambda:not window.busy)
        answer=window.tabs.currentWidget().toPlainText().split('ERSELMETZ AI\n')[-1]
        evidence={'kind':'Visible source Qt with real local Qwen/Nomic, one real repository document; not a corpus quality benchmark',
                  'source':str(source.relative_to(ROOT)),'sha256':sha256(data).hexdigest(),'bytes':len(data),
                  'question':question,'answer':answer,'ms':round((time.perf_counter()-started)*1000,2),'selected_local_reply_seconds':60,
                  'status':window.status.text(),'actual_highlights':sorted(window.brain.scene.highlights),
                  'preview':previews[-1] if previews else None,'stream_chunks':len(chunks)}
        (output/'source-brain-chat-check.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        window.grab().save(str(output/'private-brain-cited-answer.png'))
        assert not window.response_error and 'PySide6' in answer and '300' in answer and ('2,000' in answer or '2000' in answer),evidence
        assert re.search(r'\[\d+\]',answer),evidence
        assert any(not item.startswith('core:') for item in window.brain.scene.highlights),evidence
        print(json.dumps(evidence))
    finally:
        for window in list(manager.windows):
            if window.busy:window.stop_window(force=True)
        try:wait(lambda:all(not w.busy for w in manager.windows),45)
        finally:
            for window in list(manager.windows):window.close()
            manager.shutdown();session.close()


if __name__=='__main__':main()
