"""Exercise descriptor-only restore and singleton windows in an owned package."""
import argparse,json,subprocess,tempfile,time
from pathlib import Path
from pywinauto import Desktop
from packaged_chat_check import wait,text


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    exe=args.exe.resolve(strict=True);args.output.parent.mkdir(parents=True,exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='packaged-restore-',dir=args.output.parent.resolve()))
    command=[str(exe),'--profile',str(profile)];processes=[]
    draft='UNSENT-PRIVATE-DRAFT-MUST-NOT-BE-SAVED-227'
    def windows(process,title='ERSELMETZ AI'):
        return [item for item in Desktop(backend='uia').windows(process=process.pid,visible_only=True) if item.window_text()==title]
    def control(window,name):
        return wait(lambda:next((item for item in window.descendants() if item.element_info.name==name),None),15)
    def singleton(process,window,kind):
        control(window,kind).iface_invoke.Invoke()
        dialog=wait(lambda:next(iter(windows(process,kind+' · ERSELMETZ AI')),None),15)
        handle=dialog.handle;control(window,kind).iface_invoke.Invoke()
        assert len(windows(process,kind+' · ERSELMETZ AI'))==1
        assert windows(process,kind+' · ERSELMETZ AI')[0].handle==handle
        return dialog
    def quit_app(process):
        window=windows(process)[0];dialog=singleton(process,window,'Settings')
        control(dialog,'Quit the app and save only window descriptors; never replay actions').iface_invoke.Invoke()
        assert process.wait(timeout=30)==0
    with (profile/'qa-process.log').open('wb') as log:
        try:
            first=subprocess.Popen(command,cwd=exe.parent,stdout=log,stderr=log);processes.append(first)
            window=wait(lambda:next(iter(windows(first)),None),60)
            control(window,'Optional text message').iface_value.SetValue(draft)
            advanced=singleton(first,window,'Advanced');control(advanced,'Close').iface_invoke.Invoke()
            second=subprocess.run(command,cwd=exe.parent,stdout=log,stderr=log,timeout=30)
            assert second.returncode==0;wait(lambda:len(windows(first))==2,20)
            quit_app(first)
            state=profile/'ERSELMETZ AI/windows.json';saved=state.read_text(encoding='utf-8')
            assert len(json.loads(saved)['windows'])==2 and draft not in saved
            restarted=subprocess.Popen(command,cwd=exe.parent,stdout=log,stderr=log);processes.append(restarted)
            wait(lambda:len(windows(restarted))==2,60);time.sleep(2)
            for window in windows(restarted):
                assert text(control(window,'Optional text message')).strip()==''
                assert draft not in text(control(window,'Chat messages'))
            quit_app(restarted)
            report={'build_stamp':json.loads(exe.with_name('build-stamp.json').read_text()),
                'second_launch_exit':second.returncode,'windows_restored':2,'single_ui_backend_pid':True,
                'settings_and_advanced_singletons':True,'unsent_draft_not_saved_or_restored':True,
                'no_send_or_approval_invoked':True,'profile':str(profile)}
            args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print('Packaged second launch, singleton dialogs and two-window descriptor-only restart passed.')
        finally:
            for process in processes:
                if process.poll() is None:
                    try:quit_app(process)
                    except Exception:process.terminate();process.wait(timeout=10)


if __name__=='__main__':main()
