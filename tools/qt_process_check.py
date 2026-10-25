"""Actual Windows entry-point/second-launch smoke with an isolated profile."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='win32': raise SystemExit('Windows process check requires Windows')
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    titles=[]; owners=set()
    def windows(pid):
        found=[]
        titles.clear(); owners.clear()
        process_ids={pid, *(p.pid for p in psutil.Process(pid).children(recursive=True))}
        @callback
        def visit(handle, param):
            owner=wintypes.DWORD(); user.GetWindowThreadProcessId(handle,ctypes.byref(owner))
            title=ctypes.create_unicode_buffer(512); user.GetWindowTextW(handle,title,512)
            if owner.value in process_ids and user.IsWindowVisible(handle):
                titles.append(title.value)
                if title.value.startswith('ERSELMETZ AI'):
                    found.append(handle); owners.add(owner.value)
            return True
        user.EnumWindows(visit,0); return found
    def wait(check,timeout=30):
        deadline=time.monotonic()+timeout
        while not check():
            if time.monotonic()>deadline: raise RuntimeError(f'Qt process/window check timed out; observed titles: {titles}')
            time.sleep(.05)
    output=ROOT/'task223-review'; output.mkdir(exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='ersel-qt-process-'))
    command=[sys.executable,'-m','app.native_desktop','--profile',str(profile)]
    with (output/'entry-process.log').open('w',encoding='utf-8') as log:
        first=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            wait(lambda:len(windows(first.pid))==1)
            second=subprocess.run(command,cwd=ROOT,stdout=log,stderr=log,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            assert second.returncode==0
            wait(lambda:len(windows(first.pid))==2)
            assert len(owners)==1
            worker=next(iter(owners))
            children=psutil.Process(worker).children(recursive=True)
            assert not children, 'The UI/backend entry point spawned another process'
            result={'launcher_pid':first.pid,'process_id':worker,'source_venv_redirector':worker!=first.pid,
                    'second_launch_exit':second.returncode,'windows_same_pid':2,
                    'child_processes':0,'profile_isolated':True,'kind':'Actual Windows source entry point; no packaged claim'}
            for handle in windows(first.pid): user.PostMessageW(handle,0x10,0,0)
            assert first.wait(timeout=30)==0
            result['graceful_exit']=True
            (output/'process-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result))
        finally:
            if first.poll() is None: first.terminate(); first.wait(timeout=10)


if __name__=='__main__': main()
