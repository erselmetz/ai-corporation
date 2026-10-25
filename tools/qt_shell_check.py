"""Visible Qt source check with isolated data and an installed local Ollama model."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import httpx
    with httpx.Client(timeout=5, trust_env=False) as client:
        response=client.get('http://127.0.0.1:11434/api/tags'); response.raise_for_status()
        assert any(m['name']=='qwen3.5:4b' for m in response.json()['models']), 'Start Ollama with installed qwen3.5:4b; no download is attempted.'
    output=ROOT/'task223-review'; output.mkdir(exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='ersel-qt223-'))
    os.environ['LOCALAPPDATA']=str(profile); os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11434'; os.chdir(profile)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    app=QApplication([]); session=NativeSession(); manager=ShellManager(app,session)
    checks=[]; result={}
    def wait(check, timeout=20):
        deadline=time.monotonic()+timeout
        while not check():
            app.processEvents(); QTest.qWait(20)
            if time.monotonic()>deadline: raise RuntimeError('Qt source check timed out')
    try:
        first=manager.new_window(); wait(lambda:first.model.count()>0)
        first.model.setCurrentIndex(first.model.findData('qwen3.5:4b'))
        assert first.current().model=='qwen3.5:4b'
        first.composer.setPlainText('Say hello in one short sentence.'); started=time.perf_counter(); first.send()
        wait(lambda:not first.busy,60)
        assert first.current().conversation and not first.status.text().startswith('Could not')
        transcript=first.tabs.currentWidget().toPlainText(); assert len(transcript.split('ERSELMETZ AI\n')[-1].strip())>0
        result['reply']=transcript.split('ERSELMETZ AI\n')[-1].strip(); result['chat_ms']=round((time.perf_counter()-started)*1000,2)
        checks.append('Real installed qwen chat through authenticated workspace API')
        QTest.keyClick(first.composer,Qt.Key.Key_N,Qt.KeyboardModifier.ControlModifier)
        wait(lambda:len(manager.windows)==2); second=manager.windows[-1]; wait(lambda:second.model.count()>0)
        assert first.current() is not second.current() and second.current().conversation==''
        checks.append('Ctrl+N creates another independent chat window')
        settings=manager.show_dialog('Settings'); assert manager.show_dialog('Settings') is settings
        app.processEvents(); settings.grab().save(str(output/'settings.png')); settings.close()
        advanced=manager.show_dialog('Advanced'); assert manager.show_dialog('Advanced') is advanced
        app.processEvents(); advanced.grab().save(str(output/'advanced.png')); advanced.close()
        checks.append('Singleton separate Settings and Advanced windows')
        url=manager.transport.launch('Employees')
        with httpx.Client(timeout=5,trust_env=False) as browser:
            opened=browser.get(url,follow_redirects=False); assert opened.status_code==303
            assert browser.get(session.origin+opened.headers['location']).status_code==200
            assert browser.get(session.origin+'/api/local/session').status_code==200
            assert browser.get(url,follow_redirects=False).status_code==403
        checks.append('One-use launch token exchanges for a browser cookie, then fails replay')
        second.close(); first.activateWindow(); first.raise_(); first.composer.setFocus(); QTest.qWait(150)
        app.processEvents(); first.grab().save(str(output/'shell.png'))
        QTest.keyClick(first.composer,Qt.Key.Key_B,Qt.KeyboardModifier.ControlModifier); QTest.qWait(100)
        assert not first.sidebar.isVisible()
        sizes=first.splitter.sizes(); assert abs(sizes[1]-sizes[2])<=2
        first.grab().save(str(output/'sidebar-hidden.png'))
        checks.append('Ctrl+B leaves equal Brain/chat panes')
        result.update(checks=checks,process_id=os.getpid(),model='qwen3.5:4b',dpr=first.devicePixelRatioF(),kind='Windows visible source mode; no packaged claim')
        (output/'source-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    finally:
        for window in list(manager.windows): window.close()
        manager.shutdown(); session.close()


if __name__=='__main__': main()
