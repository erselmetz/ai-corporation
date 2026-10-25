"""Visible source check: installed local models, exact replies and math review."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    with httpx.Client(timeout=5,trust_env=False) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    installed=response.json()['models']
    assert all(any(m['name']==name for m in installed) for name in ['qwen3.5:4b','nomic-embed-text:latest']),'Installed models required; no download.'
    output=ROOT/'task225-review';output.mkdir(exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='ersel-qt225-'));os.environ['LOCALAPPDATA']=str(profile);os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11434';os.chdir(profile)
    from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QComboBox,QPushButton
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    from app.knowledge.shipped_pack import shipped_pack
    app=QApplication([]);session=NativeSession();manager=ShellManager(app,session);captured=[]
    original=session.client.post
    def post(*args,**kwargs):
        result=original(*args,**kwargs)
        if str(args[0]).endswith('/messages') and result.is_success:captured.append(result.json())
        return result
    session.client.post=post
    def wait(predicate,seconds=120):
        deadline=time.monotonic()+seconds
        while not predicate():
            app.processEvents();QTest.qWait(20)
            if time.monotonic()>deadline:raise RuntimeError('Visible pack check timed out')
    result={'kind':'Visible Windows source Qt; no packaged claim','models':[{k:m[k] for k in ['name','digest']} for m in installed if m['name'] in ['qwen3.5:4b','nomic-embed-text:latest']],'math':[]}
    try:
        window=manager.new_window();wait(lambda:window.model.count()>0 and manager.graph is not None)
        core=[n for n in manager.graph['nodes'] if n.get('kind')=='chunk' and n.get('trust')=='shipped knowledge']
        assert len(core)==len(shipped_pack().entries)
        window.toggle_full_brain();app.processEvents();QTest.qWait(150)
        point=next(point for point,radius,node in window.brain.scene.points if node['id']==core[0]['id'])
        from PySide6.QtCore import Qt
        QTest.mouseClick(window.brain.scene,Qt.MouseButton.LeftButton,pos=point.toPoint())
        wait(lambda:window.brain.selected is not None and window.brain.selected.get('read_only'))
        assert not window.brain.forget.isVisible()
        window.brain.window().grab().save(str(output/'core-read-only-card.png'))
        window.brain.close_card();window.toggle_full_brain()
        result['actual_core_entries']=len(core)
        window.model.setCurrentIndex(window.model.findData('qwen3.5:4b'))
        window.composer.setPlainText('Hello!');started=time.perf_counter();window.send();wait(lambda:not window.busy)
        assert captured[-1]['context_trace']['provider_called'] is False
        result['instant_ms']=round((time.perf_counter()-started)*1000,2)
        result['instant_reply']=captured[-1]['conversation']['messages'][-1]['content']
        for operation,value,expected in [(0,'0.1+0.2','0.3'),(1,'x*x-5*x+6=0','x = 2, 3'),(2,'1','100 cm')]:
            def approve():
                dialog=next(d for d in window.findChildren(QDialog) if d.isVisible() and d.windowTitle()=='Reviewed local exact math')
                combos=dialog.findChildren(QComboBox);combos[0].setCurrentIndex(operation)
                dialog.findChild(QLineEdit).setText(value)
                if operation==2:combos[1].setCurrentText('m');combos[2].setCurrentText('cm')
                dialog.grab().save(str(output/f'math-review-{operation}.png'))
                next(b for b in dialog.findChildren(QPushButton) if b.text()=='Run locally').click()
            started=time.perf_counter();QTimer.singleShot(150,approve);window.open_math();wait(lambda:not window.busy)
            record=captured[-1];answer=record['conversation']['messages'][-1]['content']
            assert answer==expected and record['context_trace']['provider_called'] is False,record
            result['math'].append({'operation':operation,'input':value,'answer':answer,'ms':round((time.perf_counter()-started)*1000,2),'trace':record['context_trace']})
        window.composer.setPlainText('Give one short coding debugging tip.');started=time.perf_counter();window.send();wait(lambda:not window.busy)
        answer=window.tabs.currentWidget().toPlainText().split('ERSELMETZ AI\n')[-1].strip()
        assert answer and not window.response_error and not window.status.text().startswith('Could not'),window.status.text()
        assert len(window.brain.scene.highlights)==3 and window.brain.scene.highlights.issubset({n['id'] for n in core})
        result['highlighted_core_ids']=sorted(window.brain.scene.highlights)
        result['model_reply']=answer;result['model_reply_ms']=round((time.perf_counter()-started)*1000,2)
        result['pack_hash']=shipped_pack().digest
        window.grab().save(str(output/'shell-pack-math.png'))
        (output/'source-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'instant_ms':result['instant_ms'],'math':[{k:v for k,v in m.items() if k!='trace'} for m in result['math']],'model_reply':answer,'model_reply_ms':result['model_reply_ms']}))
    finally:
        for window in list(manager.windows):window.close()
        manager.shutdown();session.close()


if __name__=='__main__':main()
