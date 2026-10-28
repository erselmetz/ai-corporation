"""Launch an owned packaged EXE in a fresh profile and verify a real chat window.

Never sends a message, starts a model or opens a browser. JSON contains timings,
build identity, process names and memory only, never application content.
"""
import argparse,ctypes,json,struct,subprocess,sys,tempfile,time
from pathlib import Path
import psutil


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=60);parser.add_argument('--require-no-node',action='store_true')
    parser.add_argument('--profile',type=Path,help='Explicit isolated QA profile, never a production data directory');args=parser.parse_args()
    exe=args.exe.resolve(strict=True)
    if sys.platform!='win32' or exe.suffix.lower()!='.exe':raise SystemExit('A Windows packaged executable is required.')
    stamp=json.loads(exe.with_name('build-stamp.json').read_text(encoding='utf-8'))
    with exe.open('rb') as stream:
        stream.seek(0x3c);offset=struct.unpack('<I',stream.read(4))[0]
        stream.seek(offset);assert stream.read(4)==b'PE\0\0'
        stream.seek(offset+24+68);subsystem=struct.unpack('<H',stream.read(2))[0]
    if subsystem!=2:raise RuntimeError('The packaged executable is not a Windows GUI-subsystem build.')
    profile=args.profile.resolve() if args.profile else Path(tempfile.mkdtemp(prefix='ersel-packaged-smoke-'))
    profile.mkdir(parents=True,exist_ok=True);log=(profile/'process.log').open('wb')
    started=time.perf_counter();process=subprocess.Popen([str(exe),'--profile',str(profile)],cwd=exe.parent,stdout=log,stderr=log)
    owned=psutil.Process(process.pid);window=None
    try:
        from pywinauto import Desktop
        while time.perf_counter()-started<args.timeout:
            if process.poll() is not None:raise RuntimeError(f'Packaged executable exited early with code {process.returncode}')
            for candidate in Desktop(backend='uia').windows(process=process.pid,visible_only=True):
                if candidate.window_text()=='ERSELMETZ AI' and any(control.element_info.name=='Message' for control in candidate.descendants(control_type='Edit')):
                    window=candidate;break
            if window is not None:break
            time.sleep(.1)
        if window is None or time.perf_counter()-started>args.timeout:raise RuntimeError('No visible, accessible chat window was confirmed before the deadline.')
        startup=(time.perf_counter()-started)*1000
        time.sleep(2)
        if process.poll() is not None or not window.is_visible():raise RuntimeError('The packaged chat window exited after opening.')
        children=owned.children(recursive=True);names=sorted({child.name() for child in children})
        network=subprocess.check_output(['netstat','-ano'],text=True)
        listeners=[line for line in network.splitlines() if line.split() and line.split()[-1]==str(process.pid) and 'LISTENING' in line]
        if listeners:raise RuntimeError('The default packaged app opened a TCP listening port.')
        if any(name.lower() in {'chrome.exe','msedge.exe','firefox.exe','conhost.exe','openconsole.exe'} for name in names):
            raise RuntimeError('Default startup created a browser or console child process.')
        forbidden=[path.relative_to(exe.parent).as_posix() for path in exe.parent.rglob('*')
            if path.is_file() and (path.name.lower() in {'node.exe','node','package.json'} or 'playwright' in path.parts or 'node_modules' in path.parts)]
        if args.require_no_node and (forbidden or any(name.lower() in {'node','node.exe'} for name in names)):
            raise RuntimeError('The package still contains a Node runtime/dependency: '+str(forbidden[:10]))
        report={'build_stamp':stamp,'visible_chat_window':True,'startup_ms':round(startup,2),
            'pid':process.pid,'pe_subsystem':subsystem,'stayed_alive_seconds':2,
            'netstat_command':'netstat -ano','listening_entries':listeners,
            'working_set_mib':round(owned.memory_info().rss/1024**2,2),'child_process_names':names,
            'package_bytes':sum(path.stat().st_size for path in exe.parent.rglob('*') if path.is_file()),
            'forbidden_node_entries':forbidden,'qa_profile':str(profile),'no_action_sent':True}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
    finally:
        if window is not None:
            try:window.close()
            except Exception:pass
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            for child in owned.children(recursive=True):
                try:child.terminate()
                except psutil.Error:pass
            process.terminate();process.wait(timeout=5)
        log.close()


if __name__=='__main__':main()
