"""Owned EXE + real local Ollama + semantic UI actions; never paid/cloud calls."""
import argparse,json,os,re,subprocess,sys,tempfile,time
from pathlib import Path
import httpx,psutil
from pywinauto import Desktop

ROOT=Path(__file__).resolve().parents[1]


def text(control):
    try:return control.iface_text.DocumentRange.GetText(-1).replace('\r','')
    except Exception:return control.iface_value.CurrentValue.replace('\r','')


def wait(predicate,seconds=90):
    deadline=time.monotonic()+seconds
    while True:
        result=predicate()
        if result:return result
        if time.monotonic()>deadline:raise RuntimeError('The owned packaged workflow did not reach its expected state')
        time.sleep(.1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    with httpx.Client(base_url='http://127.0.0.1:11434',trust_env=False,timeout=5) as client:
        try:response=client.get('/api/tags');response.raise_for_status()
        except (httpx.HTTPError,OSError):raise SystemExit('STOP: Start Ollama at 127.0.0.1:11434.')
        model=next((item for item in response.json()['models'] if item['name']=='qwen3.5:4b'),None)
        if model is None:raise SystemExit('The installed qwen3.5:4b is required; no model will be downloaded.')
    exe=args.exe.resolve(strict=True);output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='packaged-chat-',dir=output.parent));log=(profile/'process.log').open('wb')
    process=subprocess.Popen([str(exe),'--profile',str(profile)],cwd=exe.parent,stdout=log,stderr=log)
    windows=lambda:[window for window in Desktop(backend='uia').windows(process=process.pid,visible_only=True) if window.window_text()=='ERSELMETZ AI' and window.rectangle().width()>=800]
    report={'build_stamp':json.loads(exe.with_name('build-stamp.json').read_text()),'model':{'name':model['name'],'digest':model['digest']},'checks':{}}
    try:
        window=wait(lambda:next(iter(windows()),None),60)
        def controls(name,kind=None):return [control for control in window.descendants() if control.element_info.name==name and (kind is None or control.element_info.control_type==kind)]
        def control(name,kind=None):return wait(lambda:next(iter(controls(name,kind)),None),15)
        def invoke(name):control(name).iface_invoke.Invoke()
        composer=control('Message');send=control('Send')
        selected=control('Model','ComboBox').iface_value.CurrentValue
        assert selected=='qwen3.5:4b','No unreviewed model selection or fallback is allowed: '+str(selected)
        conversation=lambda:text(control('Chat messages'))
        prompt='Reply only with the exact text PACKAGED-227. This is a local packaging check.'
        started=time.perf_counter();composer.iface_value.SetValue(prompt);invoke('Send')
        wait(lambda:prompt in conversation(),15);wait(send.is_enabled,90)
        answer=conversation().rsplit('ERSELMETZ AI',1)[-1].strip()
        assert 'PACKAGED-227' in answer and 'provider could not finish' not in answer
        report['checks']['local_chat']={'elapsed_ms':round((time.perf_counter()-started)*1000,2),'answer':answer}
        invoke('New chat tab');wait(lambda:conversation().startswith('Start a conversation'),10)
        loop=control('Use bounded local Agent tool loop');loop.iface_toggle.Toggle();wait(lambda:loop.iface_toggle.CurrentToggleState==1,10)
        agent_prompt='Use the calculate tool exactly once to calculate 17 * 19, then state its returned result. Do not do mental arithmetic.'
        started=time.perf_counter();composer.iface_value.SetValue(agent_prompt);invoke('Send')
        approval=control('Approve once');details=text(control('Exact tool action for approval'))
        assert '17' in details and '19' in details,'Review must show the actual proposed expression'
        approval.iface_invoke.Invoke();wait(send.is_enabled,90)
        answer=conversation().rsplit('ERSELMETZ AI',1)[-1].strip()
        assert re.search(r'\b323\b',answer) and 'provider could not finish' not in answer
        report['checks']['bounded_agent_calculator']={'elapsed_ms':round((time.perf_counter()-started)*1000,2),'answer':answer,'reviewed_once':True}
        invoke('New chat tab');wait(lambda:conversation().startswith('Start a conversation'),10)
        composer.iface_value.SetValue('open youtube');invoke('Send');control('Cancel action')
        assert 'https://www.youtube.com/' in text(control('Exact tool action for approval'))
        invoke('Cancel action');wait(send.is_enabled,30)
        assert 'No tool action was run' in conversation()
        assert not psutil.Process(process.pid).children(recursive=True),'The cancelled handoff must not launch a browser'
        report['checks']['open_url_cancel']={'exact_destination_reviewed':True,'no_browser_child':True,'cancelled':True}
        invoke('New window');wait(lambda:len(windows())==2,15)
        report['checks']['multi_window']={'windows':len(windows()),'python_ui_backend_processes':1}
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Packaged local chat, reviewed Agent calculator, URL cancellation and same-process windows passed.')
    finally:
        for window in windows():
            try:window.close()
            except Exception:pass
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
        log.close()


if __name__=='__main__':main()
