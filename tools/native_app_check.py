"""Owned source-app live Ollama/native journey and per-PID no-listener proof."""
import json,os,sys,tempfile,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    import httpx
    catalog=httpx.get('http://127.0.0.1:11434/api/tags',timeout=5).json()['models']
    model=next(m for m in catalog if m['name']=='qwen3.5:4b' and not m.get('remote_host'))
    output=ROOT/'task229-review/live';output.mkdir(parents=True,exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='ersel-qt229-'));os.environ['LOCALAPPDATA']=str(profile);os.chdir(profile)
    import webbrowser
    def forbidden(*a,**k):raise AssertionError('App navigation attempted an external surface')
    webbrowser.open=forbidden;os.startfile=forbidden
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl=forbidden
    from PySide6.QtWidgets import QApplication,QPushButton,QLabel
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    from app.qt_desktop.pages import PAGES
    app=QApplication([]);session=NativeSession();manager=ShellManager(app,session,browser_open=forbidden)
    report={'kind':'Windows visible source Qt, in-process policy facade; no packaged claim','pid':os.getpid(),'model':{'name':model['name'],'digest':model['digest']},'pages':[]}
    def wait(predicate,seconds=150):
        deadline=time.monotonic()+seconds
        while not predicate():
            app.processEvents();QTest.qWait(20)
            if time.monotonic()>deadline:raise RuntimeError('Native journey timed out')
    try:
        w=manager.new_window();wait(lambda:bool(w.native_id) and w.model.count()>0 and manager.graph is not None)
        w.model.setCurrentIndex(w.model.findData(model['name']));w.reply_limit.setCurrentIndex(w.reply_limit.findData(90))
        snapshot=subprocess.check_output(['netstat','-ano'],text=True)
        entries=[line for line in snapshot.splitlines() if line.split() and line.split()[-1]==str(os.getpid()) and 'LISTENING' in line]
        report['netstat']={'command':'netstat -ano','pid_filter':str(os.getpid()),'listening_entries':entries,'filtered_output':'\n'.join(entries) or '(no matching LISTENING entries)'}
        assert not entries,entries
        (output/'netstat.txt').write_text('Command: netstat -ano\nApp PID: '+str(os.getpid())+'\nLISTENING entries for app PID:\n'+report['netstat']['filtered_output']+'\n',encoding='utf-8')
        print('No TCP listener confirmed',flush=True)
        for title in PAGES:
            page=manager.open_page(title,QLabel());wait(lambda:not getattr(page,'loading',False))
            state=page.status.text() if hasattr(page,'status') else 'Native window ready'
            report['pages'].append({'title':title,'status':state,'native':page.isWindow()})
            page.grab().save(str(output/(title.replace(' ','-')+'.png')));page.close()
        manager.show_dialog('Settings').grab().save(str(output/'Settings.png'));manager.dialogs['Settings'].close()
        print('Native navigation completed',flush=True)
        providers=session.request('POST','/api/local/provider-connections/ollama',{'id':'qa-local','name':'QA installed Ollama','base_url':'http://127.0.0.1:11434','request_slots':1})
        report['providers_test']={'state':providers['state'],'models':providers.get('models',[])}
        assert providers['state']=='available',providers
        w.offer_text('Task 229 local-only QA note: the migration check phrase is amber desk. This isolated note is safe to retain in this temporary profile.')
        wait(lambda:w.confirmation is not None);next(b for b in w.confirmation.findChildren(QPushButton) if b.text()=='Save locally').click();wait(lambda:not w.feeding and not manager.brain_loading and not manager.brain_dirty)
        assert manager.graph['user_chunks']>0;report['brain_user_chunks']=manager.graph['user_chunks']
        w.composer.setPlainText('Give one short practical coding tip.');started=time.perf_counter();w.send();wait(lambda:not w.busy)
        assert not w.response_error,w.status.text();report['chat']={'ms':round((time.perf_counter()-started)*1000,2),'text':w.tabs.currentWidget().toPlainText()[-2000:]};w.grab().save(str(output/'chat-brain.png'))
        print('Real local chat and Brain feed completed',flush=True)
        w.new_tab();w.agent_loop.setChecked(True);w.ask_first.setChecked(True)
        w.composer.setPlainText('Use the calculate tool exactly once to calculate 17 * 19, then state its returned result. Do not do mental arithmetic.');started=time.perf_counter();w.send();wait(lambda:w.pending_tool is not None or not w.busy)
        assert w.pending_tool is not None,w.status.text();assert w.pending_tool[2]['tool']=='calculate',w.pending_tool
        next(b for b in w.tool_frame.findChildren(QPushButton) if b.text()=='Approve once').click();wait(lambda:not w.busy)
        assert not w.response_error and '323' in w.tabs.currentWidget().toPlainText(),w.status.text()
        report['agent']={'ms':round((time.perf_counter()-started)*1000,2),'status':w.status.text(),'text':w.tabs.currentWidget().toPlainText()[-2000:]};w.grab().save(str(output/'agent-result.png'))
        report['status']='Verified real';print('Real model tool proposal and approved calculator completed',flush=True)
    except Exception as e:
        report['status']='Broken';report['failure']=str(e);raise
    finally:
        (output/'evidence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        for window in list(manager.windows):
            if window.busy:window.stop_window(force=True)
        wait(lambda:all(not x.busy for x in manager.windows),60)
        for window in list(manager.windows):window.close()
        manager.shutdown();session.close()
if __name__=='__main__':main()
