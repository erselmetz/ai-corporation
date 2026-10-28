"""Run the actual desktop main/lock/startup path in an isolated profile."""
import json,os,sys,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    output=ROOT/'task229-review/startup';output.mkdir(parents=True,exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='ersel-startup229-'))
    os.environ['LOCALAPPDATA']=str(profile)
    import webbrowser
    def forbidden(*a,**k):raise AssertionError('Actual app startup/navigation opened a browser')
    webbrowser.open=forbidden;os.startfile=forbidden
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl=forbidden
    from PySide6.QtCore import QTimer
    from app.qt_desktop.shell import ShellManager
    from app.qt_desktop.__main__ import main as desktop_main
    original=ShellManager.restore_windows;errors=[]
    def restore(manager):
        original(manager);started=time.monotonic();manager._startup_check=QTimer(manager)
        def inspect():
            if not manager.windows:return
            window=manager.windows[0]
            if not window.native_id or manager.catalog is None:
                if time.monotonic()-started<90:return
                errors.append('Actual desktop startup did not become ready')
            manager._startup_check.stop()
            try:
                snapshot=subprocess.check_output(['netstat','-ano'],text=True)
                matches=[line for line in snapshot.splitlines() if line.split() and line.split()[-1]==str(os.getpid()) and 'LISTENING' in line]
                assert not matches,matches
                assert window.isVisible() and window.native_id
                assert window.grab().save(str(output/'actual-entry.png'))
                result={'entry':'app.qt_desktop.__main__.main','pid':os.getpid(),'window_visible':True,'native_window_registered':True,'command':'netstat -ano','listening_entries':matches,'output':'(no matching LISTENING entries)','browser_apis':'patched to fail','instance_lock':'actual main QLockFile and QLocalServer','status':'Verified real'}
                (output/'evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result),flush=True)
            except Exception as e:errors.append(str(e))
            manager.app.quit()
        manager._startup_check.timeout.connect(inspect);manager._startup_check.start(250)
    ShellManager.restore_windows=restore
    sys.argv=[sys.argv[0],'--profile',str(profile)]
    code=desktop_main()
    if errors:raise RuntimeError('; '.join(errors))
    if code:raise SystemExit(code)
if __name__=='__main__':main()
