"""Approve one exact YouTube handoff using a fresh, owned browser profile.

The BROWSER override exists only in the owned QA application's environment. It
never changes Windows defaults or attaches to the owner's existing browser.
"""
import argparse,json,os,shlex,subprocess,tempfile,time
from pathlib import Path
import psutil
from pywinauto import Desktop
from packaged_chat_check import wait,text
from headless_browser import executable


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    exe=args.exe.resolve(strict=True);args.output.parent.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='browser-handoff-',dir=args.output.parent.resolve()));profile=folder/'browser'
    command=[Path(executable()).as_posix(),'--user-data-dir='+profile.as_posix(),'--no-first-run','--no-default-browser-check',
        '--disable-sync','--disable-background-networking','--new-window','%s','&']
    environment=dict(os.environ);environment['BROWSER']=' '.join(shlex.quote(part) for part in command)
    log=(folder/'app.log').open('wb');process=subprocess.Popen([str(exe),'--profile',str(folder/'application-data')],
        cwd=exe.parent,env=environment,stdout=log,stderr=log);owned=[];window=None
    try:
        def windows():return [item for item in Desktop(backend='uia').windows(process=process.pid,visible_only=True)
            if item.window_text()=='ERSELMETZ AI' and item.rectangle().width()>=800]
        window=wait(lambda:next(iter(windows()),None),60)
        def control(name):return wait(lambda:next((item for item in window.descendants() if item.element_info.name==name),None),15)
        control('Optional text message').iface_value.SetValue('open youtube');control('Send').iface_invoke.Invoke()
        approval=control('Approve once');assert 'https://www.youtube.com/' in text(control('Exact tool action for approval'))
        assert not psutil.Process(process.pid).children(recursive=True),'No browser may launch before approval'
        approval.iface_invoke.Invoke()
        wait(lambda:'The default browser accepted the approved link. Page loading was not verified.' in text(control('Chat messages')),20)
        def browser_started():
            nonlocal owned
            owned=psutil.Process(process.pid).children(recursive=True)
            return [child for child in owned if '--user-data-dir='+profile.as_posix() in child.cmdline()]
        roots=wait(browser_started,15)
        assert any('https://www.youtube.com/' in child.cmdline() for child in roots)
        report={'build_stamp':json.loads(exe.with_name('build-stamp.json').read_text()),'reviewed_exact_url':'https://www.youtube.com/',
            'no_browser_before_approval':True,'browser_process_after_approval':True,'page_load_claimed':False,
            'browser_profile_isolated':True,'system_default_unchanged':True,'model_call_requested':False}
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print('Exact approved handoff launched the isolated browser; page loading remains unverified.')
    finally:
        if process.poll() is None:
            try:owned=psutil.Process(process.pid).children(recursive=True)
            except psutil.Error:pass
        for child in reversed(owned):
            try:child.terminate()
            except psutil.Error:pass
        if window is not None:
            try:window.close()
            except Exception:pass
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
        log.close()


if __name__=='__main__':main()
