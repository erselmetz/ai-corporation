"""Visible local-only native runtime evidence; never downloads or opens a website."""
import json,os,sys,tempfile,time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    import faulthandler
    faulthandler.dump_traceback_later(60,repeat=True)
    with httpx.Client(timeout=5,trust_env=False) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    model=next((m for m in response.json()['models'] if m['name']=='qwen3.5:4b'),None)
    assert model,'The installed qwen3.5:4b model is required; no model is downloaded.'
    output=ROOT/'task226-review';output.mkdir(exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='ersel-qt226-'));os.environ['LOCALAPPDATA']=str(profile)
    os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11434';os.chdir(profile)
    from PySide6.QtWidgets import QApplication,QPushButton
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    app=QApplication([]);session=NativeSession();manager=ShellManager(app,session);captured=[]
    original=session.client.post
    def post(path,*args,**kwargs):
        result=original(path,*args,**kwargs)
        if '/api/native/agent' in str(path) or '/api/native/tools' in str(path):
            captured.append({'path':str(path),'status':result.status_code,'body':result.json()})
        return result
    session.client.post=post
    def wait(predicate,seconds=140):
        deadline=time.monotonic()+seconds
        while not predicate():
            app.processEvents();QTest.qWait(20)
            if time.monotonic()>deadline:raise RuntimeError('Visible runtime check timed out')
    result={'kind':'Visible Windows source Qt; installed local Ollama; not packaged verification',
            'model':{'name':model['name'],'digest':model['digest']}}
    try:
        window=manager.new_window();wait(lambda:window.model.count()>0 and bool(window.native_id));print('Catalog ready',flush=True)
        window.model.setCurrentIndex(window.model.findData(model['name']))
        window.composer.setPlainText('open youtube');window.send();wait(lambda:window.pending_tool is not None or not window.busy)
        assert window.pending_tool is not None,{'status':window.status.text(),'capture':captured}
        print('Exact URL review ready',flush=True)
        assert window.tool_details.toPlainText().startswith('Exact destination:\nhttps://www.youtube.com/')
        window.grab().save(str(output/'exact-browser-approval.png'))
        next(b for b in window.tool_frame.findChildren(QPushButton) if b.text()=='Cancel action').click()
        wait(lambda:not window.busy)
        assert 'No tool action was run' in window.tabs.currentWidget().toPlainText()
        result['browser_proposal']='exact https destination shown; owner cancellation confirmed; browser was not launched'
        window.new_tab();window.agent_loop.setChecked(True);window.ask_first.setChecked(True)
        window.composer.setPlainText('Use the calculate tool exactly once to calculate 17 * 19, then state its returned result. Do not do mental arithmetic.')
        started=time.perf_counter();window.send()
        wait(lambda:window.pending_tool is not None or not window.busy)
        assert window.pending_tool is not None,{'status':window.status.text(),'capture':captured}
        action=window.pending_tool[2];assert action['tool']=='calculate',action
        result['proposal_ms']=round((time.perf_counter()-started)*1000,2)
        window.grab().save(str(output/'real-model-calculator-proposal.png'))
        next(b for b in window.tool_frame.findChildren(QPushButton) if b.text()=='Approve once').click()
        wait(lambda:not window.busy)
        last=captured[-1];assert last['status']==200,last
        run=last['body'];assert run['state']=='completed' and run['receipts'][0]['message']=='323',run
        result['agent_ms']=round((time.perf_counter()-started)*1000,2)
        result['agent']=run;result['requests']=captured
        window.grab().save(str(output/'real-model-calculator-result.png'))
        chat=window.current()
        response=session.client.get('/api/chat/conversations/'+chat.conversation,headers={
            'X-Chat-Workspace':chat.workspace,'X-Native-Window':chat.window_id,'X-Native-Generation':str(window.native_generation)})
        response.raise_for_status();record=response.json()
        assert len(record['conversation']['messages'])==2
        assert record['conversation']['messages'][0]['content'].startswith('Use the calculate tool exactly once')
        result['raw_history_only']=True
        (output/'source-runtime-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
    finally:
        for window in list(manager.windows):
            if window.busy:window.stop_window(force=True)
        try:wait(lambda:all(not w.busy for w in manager.windows),45)
        finally:
            for window in list(manager.windows):window.close()
            manager.shutdown();session.close()


if __name__=='__main__':main()
