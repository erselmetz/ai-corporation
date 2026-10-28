"""UIA-only journeys against our owned installed EXE; no backend QA bypass."""
import argparse,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
import psutil
from pywinauto import Desktop

ROOT=Path(__file__).resolve().parents[1]

def wait(callback,seconds=60):
    end=time.monotonic()+seconds;last=None
    while time.monotonic()<end:
        try:
            result=callback()
            if result:return result
        except Exception as e:last=e
        time.sleep(.15)
    raise RuntimeError('Owned native UI did not reach its expected state: '+type(last).__name__)

def control(parent,name,kind=None):
    rows=parent.descendants(title=name,**({'control_type':kind} if kind else {}))
    rows=[r for r in rows if r.is_visible() and r.parent().element_info.control_type!='TitleBar']
    if name=='Open' and len(rows)>1:return max(rows,key=lambda item:item.rectangle().width())
    if len(rows)!=1:raise RuntimeError('Expected one native control: '+name+'; found '+str(len(rows)))
    return rows[0]

def value(item):
    try:return item.iface_value.CurrentValue
    except Exception:
        try:return item.iface_text.DocumentRange.GetText(-1)
        except Exception:return item.window_text()

def gone(window):
    try:return not window.is_visible()
    except Exception:return True

def button(parent,name):control(parent,name,'Button').invoke()

def screenshot(window,path):
    # Keep Qt's COM/message-loop initialization out of the UIA controller process.
    script="from PySide6.QtGui import QGuiApplication;import sys;app=QGuiApplication([]);assert app.primaryScreen().grabWindow(int(sys.argv[1])).save(sys.argv[2])"
    subprocess.run([sys.executable,'-c',script,str(window.handle),str(path)],check=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--mode',choices=['discover','basic','feed','pack','recover','inference'],default='basic');args=parser.parse_args()
    exe=args.exe.resolve(strict=True);profile=args.profile.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    marker=profile/'.task230-owned-profile'
    if not marker.is_file():raise SystemExit('Only a profile explicitly created by the Task230 installer check may be used')
    report={'kind':'Real frozen EXE controlled only through native UI Automation','mode':args.mode,'build_stamp':json.loads(exe.with_name('build-stamp.json').read_text()),'new_windows_account':False}
    process=subprocess.Popen([str(exe),'--profile',str(profile)],cwd=exe.parent,creationflags=subprocess.CREATE_NO_WINDOW)
    desktop=Desktop(backend='uia');window=None
    try:
        def ready():
            if process.poll() is not None:raise RuntimeError('Packaged app exited before chat')
            windows=desktop.windows(process=process.pid,title='ERSELMETZ AI',visible_only=True)
            return next((w for w in windows if any(c.element_info.name=='Message' for c in w.descendants(control_type='Edit'))),None)
        started=time.monotonic();window=wait(ready,60);report['window_ms']=round((time.monotonic()-started)*1000,2)
        report['pid']=process.pid
        net=subprocess.check_output(['netstat','-ano'],text=True);report['netstat']={'command':'netstat -ano','pid':process.pid,'listening_entries':[l for l in net.splitlines() if l.split() and l.split()[-1]==str(process.pid) and 'LISTENING' in l]};assert not report['netstat']['listening_entries']
        wait(lambda:control(window,'Send','Button').is_enabled())
        if args.mode=='discover':
            report['controls']=[{'name':c.element_info.name,'type':c.element_info.control_type} for c in window.descendants() if c.element_info.name]
        if args.mode in {'basic','recover'}:
            model=control(window,'Model','ComboBox')
            try:selected=model.selected_text()
            except Exception:selected=value(model)
            report['automatic_model']=selected
            assert 'qwen3.5:4b' in selected,'The installed local model was not selected automatically'
            message=control(window,'Message','Edit');message.set_edit_text('hello');button(window,'Send')
            wait(lambda:control(window,'Send','Button').is_enabled() and 'hello' in value(control(window,'Chat messages')),90)
            transcript=value(control(window,'Chat messages'));assert len(transcript.split('hello',1)[-1].strip())>10
            report['hello_reply_present']=True
            button(window,'Settings');settings=wait(lambda:next(iter(desktop.windows(process=process.pid,title='Settings · ERSELMETZ AI',visible_only=True)),None))
            button(settings,'About');about=wait(lambda:next(iter(desktop.windows(process=process.pid,title='About · ERSELMETZ AI',visible_only=True)),None))
            labels='\n'.join(c.element_info.name for c in about.descendants())
            assert report['build_stamp']['commit'] in labels and report['build_stamp']['version'] in labels
            report['about_stamp_matches']=True;screenshot(about,output/'about.png');button(about,'Close');button(settings,'Close')
            if args.mode=='basic':
                message.set_edit_text('open youtube');button(window,'Send')
                approval=wait(lambda:next(iter(window.descendants(title='Approve once',control_type='Button')),None))
                labels='\n'.join(value(c) for c in window.descendants() if c.element_info.name=='Exact tool action preview')
                # Existing native tool review shows the exact HTTPS destination.
                visible='\n'.join(c.element_info.name for c in window.descendants())
                screenshot(window,output/'url-approval.png');approval.invoke()
                wait(lambda:control(window,'Send','Button').is_enabled(),30)
                report['open_url_approved_once']=True;report['tool_result']=value(control(window,'Chat messages'))[-1200:]
        if args.mode=='inference':
            message=control(window,'Message','Edit');message.set_edit_text('Give one short practical coding tip.');started=time.monotonic();button(window,'Send')
            wait(lambda:control(window,'Send','Button').is_enabled() and 'ERSELMETZ AI' in value(control(window,'Chat messages')),140)
            transcript=value(control(window,'Chat messages'));answer=transcript.rsplit('ERSELMETZ AI',1)[-1].strip()
            assert len(answer)>10 and 'unavailable' not in answer.lower()
            report['real_local_generation']={'milliseconds':round((time.monotonic()-started)*1000,2),'answer':answer}
        if args.mode=='recover':
            button(window,'Brain list fallback')
            chunks=wait(lambda:control(window,'Retained Brain chunks','List'))
            seen=set()
            for _ in range(12):
                seen.update(c.element_info.name.lower() for c in chunks.descendants(control_type='ListItem'))
                if any('readme.md' in name for name in seen) and any('requirements.txt' in name for name in seen):break
                chunks.set_focus();chunks.type_keys('{PGDN}',set_foreground=False);time.sleep(.15)
            report['recovered_brain_list_items_sampled']=len(seen)
            assert any('readme.md' in name for name in seen) and any('requirements.txt' in name for name in seen)
        if args.mode=='feed':
            sources=[ROOT/'README.md',ROOT/'packaging/README.md',ROOT/'requirements.txt']
            report['files']=[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sources]
            for source in sources:
                button(window,'Feed file')
                dialog=wait(lambda:control(window,'Feed your Brain','Window'),30)
                edit=next(c for c in dialog.descendants(control_type='Edit') if 'file name' in c.element_info.name.lower().replace('&',''))
                edit.set_edit_text(str(source));edit.set_focus();edit.type_keys('{ENTER}',set_foreground=False)
                save=wait(lambda:next(iter(window.descendants(title='Save locally',control_type='Button')),None),30)
                screenshot(window,output/('brain-approval-'+str(sources.index(source))+'.png'));save.invoke()
                wait(lambda:control(window,'Send','Button').is_enabled() and any('Feed finished.' in c.element_info.name for c in window.descendants()),180)
            activity=control(window,'Observed activity');messages=[c.element_info.name for c in activity.descendants(control_type='ListItem')]
            report['feed_receipts']=[m for m in messages if 'saved ' in m or 'unchanged, skipped' in m]
            assert len(report['feed_receipts'])>=3,'Three successful native feed receipts were not observed'
            report['three_real_files_fed']=True;screenshot(window,output/'brain-fed.png')
        if args.mode=='pack':
            button(window,'Advanced');advanced=wait(lambda:next(iter(desktop.windows(process=process.pid,title='Advanced · ERSELMETZ AI',visible_only=True)),None))
            button(advanced,'Privacy and capabilities');packs=wait(lambda:next(iter(desktop.windows(process=process.pid,title='Privacy and capabilities · ERSELMETZ AI',visible_only=True)),None))
            eyes=wait(lambda:next(iter(packs.descendants(title='Eyes: image and OCR libraries')),None));eyes.click_input()
            detail=control(packs,'Privacy and capabilities detail');preview=value(detail);digest=re.search(r'Manifest digest:\s*([a-f0-9]{64})',preview,re.I).group(1)
            report['owner_preview_digest']=digest;screenshot(packs,output/'pack-preview.png');button(packs,'Install reviewed pack')
            form=wait(lambda:control(packs,'Install reviewed pack','Window'))
            control(form,'Manifest digest','Edit').set_edit_text(digest)
            control(form,'Confirmed','CheckBox').toggle();control(form,'Confirm Install reviewed pack','CheckBox').toggle();button(form,'Confirm action')
            wait(lambda:not packs.descendants(title='Install reviewed pack',control_type='Window'),180)
            eyes=wait(lambda:next(iter(packs.descendants(title='Eyes: image and OCR libraries')),None));eyes.click_input();button(packs,'Self-test pack')
            test=wait(lambda:control(packs,'Self-test pack','Window'))
            control(test,'Confirm Self-test pack','CheckBox').toggle();button(test,'Confirm action');wait(lambda:not packs.descendants(title='Self-test pack',control_type='Window'),60)
            result=value(detail);report['self_test_visible_detail']=result
            assert 'Required local module is unavailable' not in result
            report['pack_self_test_invoked_inside_exe']=True;screenshot(packs,output/'pack-self-test.png');button(packs,'Close');button(advanced,'Close')
        screenshot(window,output/'chat.png');report['working_set_mib']=round(psutil.Process(process.pid).memory_info().rss/1024**2,2)
        report['status']='passed'
    except Exception as e:
        report['status']='failed';report['failure_type']=type(e).__name__;report['failure']=str(e)
        if window is not None:
            try:report['visible_windows']=[{'title':w.window_text(),'controls':[{'name':c.element_info.name,'type':c.element_info.control_type} for c in w.descendants() if c.element_info.name]} for w in desktop.windows(process=process.pid,visible_only=True)]
            except Exception:pass
            try:report['visible_controls']=[{'name':c.element_info.name,'type':c.element_info.control_type} for c in window.descendants() if c.element_info.name]
            except Exception:pass
        raise
    finally:
        (output/'journey.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        if window is not None:
            try:
                for w in desktop.windows(process=process.pid,visible_only=True):
                    if w.handle!=window.handle:w.close()
                window.close()
            except Exception:pass
        try:process.wait(timeout=30)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)

if __name__=='__main__':main()
