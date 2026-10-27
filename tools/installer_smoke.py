"""Install/uninstall only the isolated Review AppId, preserving its real QA data."""
import argparse,json,subprocess,sys,tempfile,time,winreg
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REVIEW_KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A08FF794-EB62-44CA-9DA7-83AEB9636607}_is1'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('installer',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    installer=args.installer.resolve(strict=True)
    if '-review-' not in installer.name or not installer.is_relative_to(ROOT/'dist'):
        raise SystemExit('Only an isolated local review installer may be installed by this QA tool')
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,REVIEW_KEY):raise SystemExit('A review installation already exists; preserve it rather than overwriting it')
    except FileNotFoundError:pass
    qa_root=ROOT/'task227-review';qa_root.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='installer-',dir=qa_root)).resolve()
    target=(folder/'application').resolve();profile=(folder/'data').resolve()
    if not target.is_relative_to(qa_root.resolve()) or target==qa_root.resolve():raise SystemExit('Unsafe installation target')
    profile.mkdir();data=profile/'ERSELMETZ AI';data.mkdir();sentinel=data/'uninstall-retention-check.txt';sentinel.write_text('Owned QA data must survive uninstall.',encoding='utf-8')
    blocked=folder/'legacy-blocked';(blocked/'resources').mkdir(parents=True)
    legacy=blocked/'resources'/'app.asar';legacy.write_bytes(b'Owned inert legacy-installation marker')
    rejected=subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/DIR='+str(blocked)],timeout=60)
    if rejected.returncode==0 or (blocked/'ERSELMETZ-AI.exe').exists() or legacy.read_bytes()!=b'Owned inert legacy-installation marker':
        raise RuntimeError('Installer did not refuse mixing native files with the legacy installation')
    subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/DIR='+str(target),'/LOG='+str(folder/'install.log')],check=True,timeout=120)
    try:
        stamp=json.loads((target/'build-stamp.json').read_text(encoding='utf-8'))
        if stamp.get('review_build') is not True:raise RuntimeError('A release artifact was installed instead of the isolated review build')
        subprocess.run([sys.executable,str(ROOT/'tools/smoke_native.py'),str(target/'ERSELMETZ-AI.exe'),
            '--profile',str(profile),'--output',str(folder/'installed-smoke.json')],check=True,timeout=100,capture_output=True)
        if not (data/'windows.json').is_file():raise RuntimeError('The installed app did not save its real window descriptors')
        retained=(data/'windows.json').read_bytes()
    finally:
        uninstaller=(target/'unins000.exe').resolve()
        if uninstaller.is_relative_to(target) and uninstaller.is_file():
            subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(folder/'uninstall.log')],check=True,timeout=120)
    deadline=time.monotonic()+30
    while (target/'ERSELMETZ-AI.exe').exists() and time.monotonic()<deadline:time.sleep(.1)
    if (target/'ERSELMETZ-AI.exe').exists():raise RuntimeError('Uninstall left the application executable')
    if sentinel.read_text(encoding='utf-8')!='Owned QA data must survive uninstall.' or (data/'windows.json').read_bytes()!=retained:
        raise RuntimeError('Uninstall modified the separate application data')
    report={'installed_visible_chat':True,'uninstalled_executable_removed':True,'real_window_descriptors_preserved':True,
        'owner_data_sentinel_preserved':True,'legacy_folder_mixing_rejected':True,'review_app_id_isolated':True,'build_stamp':stamp,
        'startup':json.loads((folder/'installed-smoke.json').read_text(encoding='utf-8')),'evidence_directory':str(folder)}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Installed chat window verified; uninstall removed binaries and preserved the actual QA data.')


if __name__=='__main__':main()
