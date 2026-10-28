"""Build using already-installed Python tooling; no Node.js or dependency downloads."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import argparse
import hashlib
import json
import os
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--review',action='store_true',help='Allow uncommitted source with an explicit review stamp')
    parser.add_argument('--version',default='0.1.0');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if sys.platform!="win32": raise SystemExit("This artifact targets Windows.")
    if importlib.util.find_spec("PyInstaller") is None:
        raise SystemExit("Install requirements-build.txt first. No automatic downloads.")
    status=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
    if status and not args.review:raise SystemExit('Final builds require a committed source tree. Use --review for a clearly labelled parity artifact.')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
    digest=hashlib.sha256()
    for name in sorted(set(paths)):
        path=root/name
        if not name or not path.is_file() or name.startswith(('desktop/','desktop-ui/')):continue
        digest.update(name.encode()+b'\0'+hashlib.sha256(path.read_bytes()).digest())
    stamp={'version':args.version,'commit':commit,'source_sha256':digest.hexdigest(),'review_build':bool(status) or args.review}
    identity=time.strftime('%Y%m%d-%H%M%S')+'-'+stamp['source_sha256'][:8]
    work=root/'build'/'native'/identity;work.mkdir(parents=True,exist_ok=False)
    metadata=work/'build_metadata.json';metadata.write_text(json.dumps(stamp,indent=2)+'\n',encoding='utf-8')
    dist=root/'dist'/'native'/identity
    args=[sys.executable,"-m","PyInstaller","--noconfirm","--windowed","--onedir",
          "--name","ERSELMETZ-AI","--collect-submodules","app",
          "--add-data",f"{root/'app'/'knowledge'/'knowledge_pack.json'};app/knowledge",
          "--add-data",f"{metadata};app",
          "--add-data",f"{root/'corporation_docs'};corporation_docs",
          "--add-data",f"{root/'corporation_updates.json'};.",
          "--distpath",str(dist),"--workpath",str(work/'analysis'),
          "--specpath",str(work)]
    args.extend(['--additional-hooks-dir',str(root/'packaging'/'hooks')])
    # Exclude unused SDK modules and large optional inference stacks. Ollama remains
    # an external local service; missing optional providers must report unavailable.
    excluded=['playwright','PIL','cv2','numpy','ctranslate2','faster_whisper','onnxruntime','av','tokenizers','sounddevice','pyttsx3','pytesseract','mss','faiss','huggingface_hub','hf_xet','tkinter','customtkinter','pytest','torch','tensorflow','sentence_transformers','transformers',
              'matplotlib','IPython','jupyter','notebook','PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets',
              'PySide6.QtWebEngineQuick','PySide6.QtQml','PySide6.QtQuick','PySide6.QtQuickWidgets',
              'PySide6.Qt3DCore','PySide6.Qt3DRender','PySide6.QtCharts','PySide6.QtDataVisualization',
              'PySide6.QtPdf','PySide6.QtPdfWidgets','PySide6.QtVirtualKeyboard','PySide6.QtPrintSupport',
              'PySide6.QtGraphs','PySide6.QtQuick3D','PySide6.QtMultimediaWidgets']
    for module in excluded:args.extend(['--exclude-module',module])
    if stamp['review_build']:
        # Review-only opt-in diagnostics use a fresh QA profile. This hook is
        # absent from final clean-tree artifacts; product failure metadata stays
        # whitelisted and contains no stack or exception message.
        hook=work/'review_logging.py'
        hook.write_text("import os,sys,logging\np=os.environ.get('ERSELMETZ_QA_STARTUP_LOG')\nif p:\n f=open(p,'a',encoding='utf-8')\n sys.stderr=f\n logging.basicConfig(stream=f,level=logging.WARNING)\n",encoding='utf-8')
        args.extend(['--runtime-hook',str(hook)])
    args.append(str(root/'native_entry.py'))
    subprocess.run(args,cwd=root,check=True)
    artifact=dist/'ERSELMETZ-AI';(artifact/'build-stamp.json').write_text(json.dumps(stamp,indent=2)+'\n',encoding='utf-8')
    for notice in ['THIRD_PARTY_NOTICES.md','LICENSE']:
        if (root/notice).is_file():
            import shutil
            shutil.copy2(root/notice,artifact/notice)
    from package_notices import collect
    collect(root,work,artifact)
    print(artifact/'ERSELMETZ-AI.exe')


if __name__=="__main__": main()
