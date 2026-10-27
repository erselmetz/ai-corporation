"""Actual source-process restart/activation with fail-closed action sentinels."""
import ctypes,json,os,subprocess,sys,tempfile,time
from ctypes import wintypes as W
from pathlib import Path
import httpx,psutil
ROOT=Path(__file__).resolve().parents[1]


def main():
    with httpx.Client(trust_env=False,timeout=5) as client:
        try:response=client.get('http://127.0.0.1:11434/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
    profile=Path(tempfile.mkdtemp(prefix='ersel-restore-process-'));flag=profile/'unexpected-action.txt'
    bootstrap="""
import os,sys
from pathlib import Path
root,profile=sys.argv[1:];sys.path.insert(0,root)
def forbidden(*args,**kwargs):
    Path(profile,'unexpected-action.txt').write_text('Restore attempted a protected operation',encoding='utf-8')
    raise RuntimeError('No protected operation is authorized in this restore check')
import webbrowser;webbrowser.open=forbidden
from app.providers.ollama import OllamaProvider
for name in ['generate','generate_stream','generate_chat','generate_chat_stream','generate_native_step','generate_chat_with_images']:setattr(OllamaProvider,name,forbidden)
from app.application.services.native_tools import NativeToolService
NativeToolService.prepare=forbidden;NativeToolService.execute=forbidden
from app.application.services.native_capture import NativeCaptureService
NativeCaptureService.request=forbidden;NativeCaptureService.begin=forbidden
from app.qt_desktop.devices import QtDeviceCapture
QtDeviceCapture.start=forbidden
from app.qt_desktop.__main__ import main
sys.argv=['ERSELMETZ AI','--profile',profile]
raise SystemExit(main())
"""
    command=[sys.executable,'-c',bootstrap,str(ROOT),str(profile)]
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.EnumWindows.argtypes=[callback,W.LPARAM];user.IsWindowVisible.argtypes=[W.HWND]
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)];user.GetWindowThreadProcessId.restype=W.DWORD
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    user.PostThreadMessageW.argtypes=[W.DWORD,W.UINT,W.WPARAM,W.LPARAM];user.PostThreadMessageW.restype=W.BOOL
    def windows(process):
        pids={process.pid,*[p.pid for p in psutil.Process(process.pid).children(recursive=True)]};found=[]
        @callback
        def visit(handle,_):
            pid=W.DWORD();thread=user.GetWindowThreadProcessId(handle,ctypes.byref(pid));title=ctypes.create_unicode_buffer(256)
            if pid.value in pids and user.IsWindowVisible(handle):
                user.GetWindowTextW(handle,title,256)
                if title.value=='ERSELMETZ AI':found.append((int(handle),pid.value,thread))
            return True
        user.EnumWindows(visit,0);return found
    def wait(check):
        end=time.monotonic()+40
        while not check():
            if flag.exists():raise RuntimeError(flag.read_text())
            if time.monotonic()>end:raise RuntimeError('Source restore process check timed out')
            time.sleep(.05)
    def quit_app(process):
        active=windows(process);assert active
        from pywinauto import Application
        application=Application(backend='uia').connect(process=active[0][1])
        selected=application.window(handle=active[0][0])
        buttons=selected.descendants(control_type='Button',title='Settings');assert len(buttons)==1
        buttons[0].invoke()
        settings=application.window(title='Settings · ERSELMETZ AI');settings.wait('exists visible',timeout=10)
        buttons=settings.descendants(control_type='Button',title='Quit the app and save only window descriptors; never replay actions');assert len(buttons)==1
        buttons[0].invoke()
        assert process.wait(timeout=30)==0
    output=ROOT/'task227-review';output.mkdir(exist_ok=True);state=profile/'ERSELMETZ AI/windows.json'
    processes=[]
    with (output/'restore-process.log').open('w',encoding='utf-8') as log:
        try:
            first=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);processes.append(first)
            wait(lambda:len(windows(first))==1)
            second=subprocess.run(command,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
            assert second.returncode==0;wait(lambda:len(windows(first))==2)
            def saved():
                if not state.exists():return False
                records=json.loads(state.read_text())['windows']
                return len(records)==2 and all(record['tabs'][0]['model'] for record in records)
            wait(saved);before=json.loads(state.read_text());owner=windows(first)[0][1]
            assert len({item[1] for item in windows(first)})==1
            quit_app(first)
            assert len(json.loads(state.read_text())['windows'])==2,'Quit discarded a saved window'
            restarted=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);processes.append(restarted)
            wait(lambda:len(windows(restarted))==2);time.sleep(2.2)
            assert len({item[1] for item in windows(restarted)})==1
            assert not flag.exists()
            quit_app(restarted);after=json.loads(state.read_text())
            assert [[tab['model'] for tab in record['tabs']] for record in before['windows']]==[[tab['model'] for tab in record['tabs']] for record in after['windows']]
            report={'kind':'Actual Windows source restart, isolated profile, protected operations replaced by fail-closed sentinels; no packaged claim',
                'windows_before':2,'windows_after_restart':2,'one_ui_backend_process':True,'second_launch_exit':second.returncode,
                'protected_operation_attempts':0,'drafts_messages_actions_saved':False,'graceful_restarts':True}
            (output/'source-restore-process-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
        finally:
            for process in processes:
                if process.poll() is None:
                    try:quit_app(process)
                    except Exception:
                        for child in psutil.Process(process.pid).children(recursive=True):child.terminate()
                        process.terminate();process.wait(timeout=10)


if __name__=='__main__':main()
