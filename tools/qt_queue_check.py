"""Observe real native two-window admission/cancel without replay or downloads."""
import json,os,sys,tempfile,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    with httpx.Client(timeout=5,trust_env=False) as client:
        try:r=client.get('http://127.0.0.1:11434/api/tags');r.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    assert any(m['name']=='qwen3.5:4b' for m in r.json()['models'])
    output=ROOT/'task226-review';output.mkdir(exist_ok=True)
    os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='ersel-queue226-')
    os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11434';os.chdir(os.environ['LOCALAPPDATA'])
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    app=QApplication([]);session=NativeSession();manager=ShellManager(app,session)
    def wait(predicate,seconds=120):
        end=time.monotonic()+seconds
        while not predicate():
            app.processEvents();QTest.qWait(20)
            if time.monotonic()>end:raise RuntimeError('Queue source check timed out')
    try:
        first=manager.new_window();second=manager.new_window()
        wait(lambda:first.model.count()>0 and second.model.count()>0)
        for window in [first,second]:window.model.setCurrentIndex(window.model.findData('qwen3.5:4b'))
        first.composer.setPlainText('Write a numbered list of 20 practical debugging tips, each with one short sentence.');first.send()
        wait(lambda:'replying' in first.status.text())
        second.composer.setPlainText('Say the unique marker SECOND.');second.send()
        seen=[]
        def queued():
            data=session.request('GET','/api/native/windows');seen.append(data)
            return any(o['window_id']==second.native_id and o['state']=='waiting' for o in data['operations'])
        wait(queued,40)
        manager.poll_queue();app.processEvents();QTest.qWait(100)
        second.grab().save(str(output/'two-window-queue.png'))
        started=time.perf_counter();second.stop_window();wait(lambda:not second.busy,45)
        cancel_ms=round((time.perf_counter()-started)*1000,2)
        wait(lambda:not first.busy,120)
        assert not first.response_error and not first.status.text().startswith('Could not'),first.status.text()
        chat=second.current()
        response=session.client.get('/api/chat/conversations/'+chat.conversation,headers={
            'X-Chat-Workspace':chat.workspace,'X-Native-Window':chat.window_id,'X-Native-Generation':str(second.native_generation)})
        response.raise_for_status();assert response.json()['conversation']['messages']==[]
        second.stop_window();wait(lambda:not second.window_stopped)
        QTest.qWait(500);app.processEvents()
        response=session.client.get('/api/chat/conversations/'+chat.conversation,headers={
            'X-Chat-Workspace':chat.workspace,'X-Native-Window':chat.window_id,'X-Native-Generation':str(second.native_generation)})
        response.raise_for_status();assert response.json()['conversation']['messages']==[]
        final=session.request('GET','/api/native/windows');assert final['operations']==[]
        evidence={'kind':'Visible Windows source Qt, real local Qwen; not packaged verification',
                  'queued_observation':next(d for d in seen if any(o['window_id']==second.native_id and o['state']=='waiting' for o in d['operations'])),
                  'cancel_ms':cancel_ms,'cancelled_conversation_messages':0,'resumed_generation':second.native_generation,
                  'no_replay_after_resume':True,'first_window_finished':True,'final_operations':final['operations']}
        (output/'source-queue-check.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(evidence))
    finally:
        for window in list(manager.windows):
            if window.busy:window.stop_window(force=True)
        try:wait(lambda:all(not w.busy for w in manager.windows),45)
        finally:
            for window in list(manager.windows):window.close()
            manager.shutdown();session.close()


if __name__=='__main__':main()
