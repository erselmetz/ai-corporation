"""Silent isolated install, real visible-window smoke, retain/uninstall/reinstall.

Never replaces production registration, shortcuts or owner data. The installer
must use the isolated Review AppId; clean-source QA installers are also allowed.
"""
import argparse,json,os,subprocess,sys,tempfile,time,winreg
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A08FF794-EB62-44CA-9DA7-83AEB9636607}_is1'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('installer',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    installer=args.installer.resolve(strict=True)
    if not installer.is_relative_to(ROOT/'dist') or not any(s in installer.name for s in ['-review-','-qa-']):raise SystemExit('Only our isolated QA installer is allowed')
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY):raise SystemExit('An existing review install must be preserved')
    except FileNotFoundError:pass
    folder=Path(tempfile.mkdtemp(prefix='task230-install-'));target=folder/'application';profile=folder/'profile';profile.mkdir()
    (profile/'.task230-owned-profile').write_text('Owned local installer QA profile.',encoding='utf-8')
    report={'new_windows_account':False,'isolated_current_user_profile':True,'installer':str(installer),'target':str(target),'profile':str(profile)}
    def install():subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/DIR='+str(target)],check=True,timeout=120)
    def uninstall():
        candidates=sorted(target.glob('unins*.exe'),key=lambda path:path.stat().st_mtime,reverse=True)
        if candidates:
            exe=candidates[0].resolve(strict=True)
            if not exe.is_relative_to(target.resolve()):raise RuntimeError('Unsafe QA uninstaller path')
            subprocess.run([str(exe),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=120)
        deadline=time.monotonic()+30
        while (target/'ERSELMETZ-AI.exe').exists() and time.monotonic()<deadline:time.sleep(.1)
        assert not (target/'ERSELMETZ-AI.exe').exists(),'Uninstall left the executable'
    try:
        install()
        shortcut=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/ERSELMETZ AI Review.lnk';assert shortcut.is_file()
        subprocess.run([sys.executable,str(ROOT/'tools/smoke_native.py'),str(target/'ERSELMETZ-AI.exe'),'--profile',str(profile),'--output',str(folder/'first.json'),'--require-no-node'],check=True,timeout=100,capture_output=True)
        data=profile/'ERSELMETZ AI';assert (data/'windows.json').is_file()
        events=json.loads((data/'native-events.json').read_text(encoding='utf-8'))
        assert events and all(set(row)=={'at','event','version','commit'} for row in events)
        assert all(row['event'] in {'startup','ready','shutdown'} for row in events)
        sentinel=data/'owned-retention-check.txt';sentinel.write_text('Task230 QA data',encoding='utf-8');retained=(data/'windows.json').read_bytes()
        uninstall();assert not shortcut.exists();assert sentinel.read_text(encoding='utf-8')=='Task230 QA data' and (data/'windows.json').read_bytes()==retained
        install()
        subprocess.run([sys.executable,str(ROOT/'tools/smoke_native.py'),str(target/'ERSELMETZ-AI.exe'),'--profile',str(profile),'--output',str(folder/'reinstalled.json'),'--require-no-node'],check=True,timeout=100,capture_output=True)
        assert sentinel.read_text(encoding='utf-8')=='Task230 QA data'
        report.update({'status':'passed','first':json.loads((folder/'first.json').read_text()),'reinstalled':json.loads((folder/'reinstalled.json').read_text()),'shortcut_created_and_removed':True,'uninstall_kept_data':True,'reinstall_recovered_profile':True,'metadata_log_whitelist_verified':True})
    finally:
        uninstall();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
