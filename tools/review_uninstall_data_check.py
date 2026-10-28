"""Explicit remove-data UI test, restricted to our marked disposable Review data."""
import json,os,subprocess,time
from pathlib import Path
import psutil
from pywinauto import Desktop

ROOT=Path(__file__).resolve().parents[1]

def main():
    state=json.loads((ROOT/'task230-review/install-state.json').read_text())
    target=Path(state['target']).resolve(strict=True);profile=Path(state['profile']).resolve(strict=True)
    expected=(Path(os.environ['LOCALAPPDATA'])/'ERSELMETZ AI Review').resolve()
    if profile!=expected or not (profile/'.task230-owned-profile').is_file() or not target.is_relative_to(ROOT/'task230-review'):
        raise SystemExit('Only marked disposable Task230 Review data may be removed')
    data=profile/'ERSELMETZ AI';assert data.is_dir() and not data.is_symlink() and not data.is_junction()
    for p in psutil.process_iter(['name','exe']):
        if (p.info['name'] or '').lower()=='erselmetz-ai.exe' and p.info['exe'] and Path(p.info['exe']).resolve()==target/'ERSELMETZ-AI.exe':raise SystemExit('Close the owned QA app before uninstalling')
    process=subprocess.Popen([str(target/'unins000.exe'),'/NORESTART'],creationflags=subprocess.CREATE_NO_WINDOW)
    pids={process.pid};decisions=[];deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        for pid in list(pids):
            try:pids.update(p.pid for p in psutil.Process(pid).children(recursive=True))
            except psutil.Error:pass
        windows=[w for w in Desktop(backend='uia').windows(visible_only=True) if w.process_id() in pids]
        for w in windows:
            text=' '.join(c.element_info.name for c in w.descendants())
            buttons=w.descendants(control_type='Button')
            if 'Also permanently remove your local chats' in text:
                chosen=next(b for b in buttons if b.element_info.name.replace('&','')=='Yes');chosen.invoke();decisions.append('explicit-remove-owned-review-data')
            elif 'completely remove' in text.lower() and 'ERSELMETZ' in text:
                next(b for b in buttons if b.element_info.name.replace('&','')=='Yes').invoke();decisions.append('confirm-owned-review-uninstall')
            elif any(b.element_info.name=='OK' for b in buttons):
                next(b for b in buttons if b.element_info.name=='OK').invoke()
        if process.poll() is not None and not windows and not (target/'ERSELMETZ-AI.exe').exists():break
        time.sleep(.15)
    assert 'explicit-remove-owned-review-data' in decisions
    assert not data.exists() and not (target/'ERSELMETZ-AI.exe').exists()
    report={'status':'passed','explicit_remove_data_selected':True,'only_marked_disposable_review_profile':True,'production_data_not_targeted':True,'default_silent_retention_tested_separately':True,'decisions':decisions}
    (ROOT/'task230-review/remove-data-proof.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
