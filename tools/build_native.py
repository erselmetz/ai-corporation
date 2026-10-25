"""Build using already-installed Python tooling; no Node.js or dependency downloads."""
from pathlib import Path
import importlib.util
import subprocess
import sys


def main():
    root=Path(__file__).resolve().parents[1]
    if sys.platform!="win32": raise SystemExit("This artifact targets Windows.")
    if importlib.util.find_spec("PyInstaller") is None:
        raise SystemExit("Install desktop/requirements-build.txt first. No automatic downloads.")
    args=[sys.executable,"-m","PyInstaller","--noconfirm","--windowed","--onedir",
          "--name","ERSELMETZ-AI","--collect-submodules","app",
          "--add-data",f"{root/'app'/'webui'/'static'};app/webui/static",
          "--distpath",str(root/'dist'/'native'),"--workpath",str(root/'build'/'native'),
          "--specpath",str(root/'build'/'native'),str(root/'native_entry.py')]
    subprocess.run(args,cwd=root,check=True)
    print(root/'dist'/'native'/'ERSELMETZ-AI'/'ERSELMETZ-AI.exe')


if __name__=="__main__": main()
