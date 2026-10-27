"""Compile the native per-user installer with an explicitly installed Inno compiler."""
import argparse,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def validate(package,*,review=False):
    package=Path(package).resolve(strict=True)
    if not (package/'ERSELMETZ-AI.exe').is_file():raise ValueError('The one-folder executable is missing')
    stamp=json.loads((package/'build-stamp.json').read_text(encoding='utf-8'))
    inner=package/'_internal'/'app'/'build_metadata.json'
    if json.loads(inner.read_text(encoding='utf-8'))!=stamp:raise ValueError('Inner and outer build stamps do not match')
    if stamp.get('review_build') and not review:raise ValueError('Review artifacts require --review and are not release installers')
    forbidden=[path for path in package.rglob('*') if path.is_file() and
        (path.name.lower() in {'node.exe','node','package.json'} or any(part.lower() in {'playwright','node_modules'} for part in path.parts))]
    if forbidden and not review:raise ValueError('Final installers cannot contain Node or Playwright')
    return package,stamp


def main():
    parser=argparse.ArgumentParser();parser.add_argument('package',type=Path);parser.add_argument('--compiler',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--review',action='store_true');args=parser.parse_args()
    package,stamp=validate(args.package,review=args.review);compiler=args.compiler.resolve(strict=True)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    version=stamp['version']+('-review' if stamp['review_build'] else '')
    if any(character not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-' for character in version):raise ValueError('Invalid installer version')
    for path in [package,output]:
        if any(c in str(path) for c in ['"','\n','\r']):raise ValueError('Invalid compiler path')
    command=[str(compiler),'/Qp','/DPackageRoot='+str(package),'/DInstallerOutput='+str(output),'/DAppVersion='+version]
    if stamp['review_build']:command.append('/DReviewBuild')
    subprocess.run(command+[str(ROOT/'packaging'/'native.iss')],cwd=ROOT,check=True)
    print(output/f'ERSELMETZ-AI-Setup-{version}-win-x64.exe')


if __name__=='__main__':main()
