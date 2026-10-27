"""Open a protected Advanced page in a fresh owned browser, without reading secrets."""
import argparse,json,os,shlex,subprocess,tempfile,time
from pathlib import Path
import httpx,psutil,websocket
from pywinauto import Desktop
from packaged_chat_check import wait
from headless_browser import Browser,executable


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    exe=args.exe.resolve(strict=True);args.output.parent.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='advanced-launch-',dir=args.output.parent.resolve()));profile=folder/'browser'
    command=[Path(executable()).as_posix(),'--user-data-dir='+profile.as_posix(),'--no-first-run','--no-default-browser-check',
        '--disable-sync','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--new-window','%s','&']
    environment=dict(os.environ);environment['BROWSER']=' '.join(shlex.quote(part) for part in command)
    owned=[];socket=None
    with (folder/'app.log').open('wb') as log:
        process=subprocess.Popen([str(exe),'--profile',str(folder/'application-data')],cwd=exe.parent,env=environment,stdout=log,stderr=log)
        try:
            window=wait(lambda:next((item for item in Desktop(backend='uia').windows(process=process.pid,visible_only=True) if item.window_text()=='ERSELMETZ AI'),None),60)
            def control(parent,name):return wait(lambda:next((item for item in parent.descendants() if item.element_info.name==name),None),15)
            assert not psutil.Process(process.pid).children(recursive=True)
            control(window,'Advanced').iface_invoke.Invoke()
            dialog=wait(lambda:next((item for item in Desktop(backend='uia').windows(process=process.pid,visible_only=True) if item.window_text()=='Advanced · ERSELMETZ AI'),None),15)
            control(dialog,'Preferences').iface_invoke.Invoke()
            wait(lambda:(profile/'DevToolsActivePort').is_file(),30)
            port=int((profile/'DevToolsActivePort').read_text().splitlines()[0])
            with httpx.Client(trust_env=False,timeout=5) as client:
                def page():
                    targets=client.get('http://127.0.0.1:'+str(port)+'/json/list').json()
                    return next((item for item in targets if item.get('type')=='page' and '/ui/preferences' in item.get('url','')),None)
                target=wait(page,30)
                from urllib.parse import urlsplit
                parsed=urlsplit(target['url']);assert parsed.hostname=='127.0.0.1' and parsed.path=='/ui/preferences'
                unauthenticated=client.get(parsed.scheme+'://'+parsed.netloc+'/api/agents')
                assert unauthenticated.status_code in {401,403}
            socket=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=10,suppress_origin=True)
            browser=Browser.__new__(Browser);browser.socket=socket;browser.sequence=0;browser.events=[];browser.dialog_handler=None;browser.fixtures={};browser.control_sequence=1000000
            browser.call('Runtime.enable');browser.wait('document.readyState === "complete"')
            status=browser.evaluate('fetch("/api/agents",{credentials:"same-origin"}).then(response=>response.status)')
            assert status==200,'The launched browser did not receive an authenticated session'
            assert browser.evaluate('document.body.innerText.length > 100')
            owned=psutil.Process(process.pid).children(recursive=True)
            assert any('chrome' in item.name().lower() or 'msedge' in item.name().lower() for item in owned)
            report={'build_stamp':json.loads(exe.with_name('build-stamp.json').read_text()),'protected_page':'/ui/preferences',
                'browser_authenticated_api_status':status,'unauthenticated_api_status':unauthenticated.status_code,
                'fresh_owned_browser_profile':True,'no_cookie_csrf_or_launch_token_recorded':True,
                'scope':'Actual packaged Advanced handoff and session exchange; ticket expiry/replay are covered separately by source regressions.'}
            args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print('Packaged Advanced launch reached the protected page and authenticated API in an owned browser.')
        finally:
            if socket is not None:socket.close()
            try:owned=psutil.Process(process.pid).children(recursive=True)
            except psutil.Error:pass
            for child in reversed(owned):
                try:child.terminate()
                except psutil.Error:pass
            for item in Desktop(backend='uia').windows(process=process.pid,visible_only=True):
                try:item.close()
                except Exception:pass
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
