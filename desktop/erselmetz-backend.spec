# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

repo = Path(SPECPATH).resolve().parents[0]
datas = []
for name in ("corporation_docs",):
    source = repo / name
    if source.exists():
        datas.append((str(source), name))
updates = repo / "corporation_updates.json"
if updates.exists():
    datas.append((str(updates), "."))
datas.append((str(repo / "app" / "webui" / "static"), "app/webui/static"))

analysis = Analysis(
    [str(repo / "app" / "desktop_runtime.py")],
    pathex=[str(repo)],
    binaries=[],
    datas=datas,
    hiddenimports=["app.api.local_voice", "app.integrations.gemini_voice"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="erselmetz-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=True,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="erselmetz-backend",
)
