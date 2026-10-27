"""Audit the actual one-folder artifact, not the installed SDK or dependencies."""
import argparse,ctypes,hashlib,json,os
from pathlib import Path

QT_DLLS={'Qt6Core.dll','Qt6Gui.dll','Qt6Widgets.dll','Qt6Network.dll','Qt6Multimedia.dll'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('package',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=args.package.resolve(strict=True);files=[path for path in root.rglob('*') if path.is_file()]
    forbidden=[path.relative_to(root).as_posix() for path in files if path.name.lower() in {'node.exe','node','package.json','package-lock.json'}
        or any(part.lower() in {'node_modules','playwright'} for part in path.relative_to(root).parts)]
    if forbidden:raise SystemExit('Unexpected Node dependency in artifact: '+str(forbidden[:10]))
    qt=[path for path in files if path.name.startswith('Qt6') and path.suffix=='.dll']
    if {path.name for path in qt}!=QT_DLLS:raise SystemExit('Unexpected/missing Qt modules: '+str([path.name for path in qt]))
    ffmpeg=[]
    for prefix in ['avcodec','avformat','avutil','swresample','swscale']:
        for path in root.rglob(prefix+'-*.dll'):
            with os.add_dll_directory(str(path.parent)):
                library=ctypes.CDLL(str(path));license_fn=getattr(library,prefix+'_license');license_fn.restype=ctypes.c_char_p
                configuration_fn=getattr(library,prefix+'_configuration');configuration_fn.restype=ctypes.c_char_p
                license_text=license_fn().decode();configuration=configuration_fn().decode()
            if 'LGPL' not in license_text or any(flag in configuration.split() for flag in ['--enable-gpl','--enable-nonfree']):
                raise SystemExit('Unexpected FFmpeg licensing configuration')
            ffmpeg.append({'path':path.relative_to(root).as_posix(),'license':license_text,'configuration':configuration,
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if not ffmpeg:raise SystemExit('The Qt Multimedia dependency inventory is missing')
    licenses=json.loads((root/'third-party-python-inventory.json').read_text(encoding='utf-8'))
    if any(not entry['license_files'] for entry in licenses):raise SystemExit('A frozen Python distribution has no copied license text')
    for entry in licenses:
        for item in entry['license_files']:
            if hashlib.sha256((root/item['artifact_path']).read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Copied license text drift')
    report={'build_stamp':json.loads((root/'build-stamp.json').read_text()),'node_entries':forbidden,
        'qt_dlls':[{'path':path.relative_to(root).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in qt],
        'ffmpeg':ffmpeg,'licensed_python_distributions':len(licenses),'package_bytes':sum(path.stat().st_size for path in files),
        'source_and_distribution_obligations':'See bundled third-party-sources.json and THIRD_PARTY_NOTICES.md; local audit is not public-release approval.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Artifact audit passed: no Node/Playwright, five required Qt DLLs, FFmpeg LGPL configuration, copied license hashes.')


if __name__=='__main__':main()
