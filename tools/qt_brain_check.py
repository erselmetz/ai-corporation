"""Real installed local embedding + visible Qt Brain/intake source check."""
from pathlib import Path
import os
import sys
import json
import shutil
import tempfile
import time
import hashlib
import subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import httpx
    with httpx.Client(timeout=5,trust_env=False) as client:
        try:
            response=client.get('http://127.0.0.1:11434/api/tags'); response.raise_for_status()
        except Exception: raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434 before continuing.')
        installed=response.json()['models']
        assert any(m['name']=='nomic-embed-text:latest' for m in installed),'Install/restore your local embedding model; no download is attempted.'
    profile=Path(tempfile.mkdtemp(prefix='ersel-qt-brain-')); os.environ['LOCALAPPDATA']=str(profile)
    os.environ['OLLAMA_BASE_URL']='http://127.0.0.1:11434'; os.chdir(profile)
    folder=profile/'chosen-folder'; folder.mkdir()
    for name in ['requirements-knowledge.txt','README.md']:
        # Keep the real corpus fixed for the prefix comparison in Task 225.
        (folder/name).write_bytes(subprocess.check_output(['git','show','f074a8aac9c23a24d04751b2d0c0d501414a3aad:'+name],cwd=ROOT))
    output=ROOT/'task224-review'; output.mkdir(exist_ok=True)
    from PySide6.QtWidgets import QApplication, QPushButton
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    app=QApplication([]); session=NativeSession(); manager=ShellManager(app,session)
    def wait(predicate,seconds=90):
        deadline=time.monotonic()+seconds
        while not predicate():
            app.processEvents(); QTest.qWait(20)
            if time.monotonic()>deadline: raise RuntimeError('Brain source check timed out')
    def approve_feed(paths):
        window.offer_paths(paths); wait(lambda:window.confirmation is not None)
        assert not window.feeding
        next(b for b in window.confirmation.findChildren(QPushButton) if b.text()=='Save locally').click()
        wait(lambda:not window.feeding,180)
        wait(lambda:not manager.brain_loading and not manager.brain_dirty)
    try:
        window=manager.new_window(); wait(lambda:window.model.count()>0)
        files=[ROOT/n for n in ['desktop/requirements-build.txt','requirements-knowledge.txt','review/task-223-native-python.md','review/task-214-window-review.md','review/task-223-prototype-shell.md']]
        manifest=[{'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]
        started=time.perf_counter(); approve_feed(files); ingest_ms=round((time.perf_counter()-started)*1000,2)
        first_graph=manager.graph; assert first_graph['total_chunks']>5
        before=first_graph['total_chunks']; approve_feed([files[0]])
        assert manager.graph['total_chunks']==before
        approve_feed([folder]); assert manager.graph['total_chunks']>before
        queries=[('Which PyInstaller version is pinned?','requirements-build.txt'),('What is the build tool?','requirements-build.txt'),
                 ('Which sentence embedding library is listed?','requirements-knowledge.txt'),('Which vector database is listed?','requirements-knowledge.txt'),
                 ('Which native toolkit was used in the historical native Python spike?','task-223-native-python.md'),('What forgery protection was retained with session cookies?','task-223-native-python.md'),
                 ('What is the maximum number of saved window descriptors?','task-214-window-review.md'),('Does restoring windows replay an action?','task-214-window-review.md'),
                 ('Which optional image library caused the failed full Python gate?','task-223-prototype-shell.md'),('Which phase was stopped at its verification gate?','task-223-prototype-shell.md')]
        cases=[]
        for query,expected in queries:
            started=time.perf_counter(); result=session.request('POST','/api/memory/owner/native-recall',{'query':query,'k':5,'threshold':0})
            sources=[hit['source'].replace('\\','/').split('/')[-1] for hit in result['hits']]
            rank=next((i+1 for i,name in enumerate(sources) if name==expected),None)
            cases.append({'question':query,'expected':expected,'sources':sources,'rank':rank,'mode':result['mode'],'ms':round((time.perf_counter()-started)*1000,2)})
        window.brain.search.setText('forgery protection session cookies')
        QTest.keyClick(window.brain.search,Qt.Key.Key_Return); wait(lambda:bool(window.brain.scene.highlights))
        window.toggle_full_brain(); app.processEvents(); QTest.qWait(250)
        scene=window.brain.scene; assert scene.points
        point,radius,node=scene.points[0]
        QTest.mouseClick(scene,Qt.MouseButton.LeftButton,pos=point.toPoint())
        wait(lambda:window.brain.selected is not None and 'record_id' in window.brain.selected and window.brain.forget.isVisible())
        window.brain.window().grab().save(str(output/'brain-node-card.png'))
        before_forget=manager.graph['total_chunks']; forgotten=window.brain.selected['record_id']
        window.brain.forget.click(); assert manager.graph['total_chunks']==before_forget
        window.brain.forget.click()
        wait(lambda:manager.graph['total_chunks']==before_forget-1)
        assert all(n.get('record_id')!=forgotten for n in manager.graph['nodes'])
        window.brain.close_card(); window.brain.window().grab().save(str(output/'brain.png'))
        window.brain.toggle_list(); window.brain.window().grab().save(str(output/'brain-list.png')); window.brain.toggle_list()
        QTest.keyClick(window.brain,Qt.Key.Key_Escape); wait(lambda:window.full_brain is None)
        window.grab().save(str(output/'shell-brain.png'))
        result={'model':'nomic-embed-text:latest','model_digest':next(m['digest'] for m in installed if m['name']=='nomic-embed-text:latest'),
                'documents':manifest,'five_file_ingest_ms':ingest_ms,'five_file_chunks':first_graph['total_chunks'],
                'folder_fed':True,'unchanged_refeed_kept_chunk_count':True,'final_chunks':manager.graph['total_chunks'],
                'folder_source_commit':'f074a8aac9c23a24d04751b2d0c0d501414a3aad',
                'folder_documents':[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir())],
                'confirmed_forget':True,'before_forget_chunks':before_forget,'after_forget_chunks':manager.graph['total_chunks'],
                'recall_at_5':sum(c['rank'] is not None for c in cases)/len(cases),'mrr':sum(1/c['rank'] if c['rank'] else 0 for c in cases)/len(cases),
                'cases':cases,'answer_quality':'Not measured here; retrieval only. Native chat-context wiring belongs to agent-loop parity.',
                'ui_checks':['actual source grows after file/folder intake','anchored real-node card','list fallback','same-widget full-window and Esc return','real retrieval highlight'],
                'activity':[window.steps.item(i).text() for i in range(window.steps.count())]}
        (output/'source-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    finally:
        for window in list(manager.windows): window.close()
        manager.shutdown(); session.close()


if __name__=='__main__': main()
