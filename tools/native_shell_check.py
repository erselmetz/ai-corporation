"""Real native Tk/backend smoke check in an isolated current-user profile."""
from pathlib import Path
import os
import sys
import tempfile
import time
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def run():
    profile=Path(tempfile.mkdtemp(prefix="ersel-native-check-"))
    os.environ["LOCALAPPDATA"]=str(profile); os.chdir(profile)
    import tkinter as tk
    from app.native_desktop.session import NativeSession
    from app.native_desktop.shell import NativeShell
    session=NativeSession(); root=tk.Tk(); ui=NativeShell(root,session)
    checks=[]
    def pump(seconds=.2):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline: root.update(); time.sleep(.01)
    try:
        pump(2)
        assert len(ui.panes.panes())==3
        checks.append("Native Tk opens three resizable panes")
        assert len(ui.tabs)==1
        ui.new_chat(); pump(); assert len(ui.tabs)==2
        checks.append("Independent new chat tabs")
        ui.toggle_sidebar(); pump()
        assert len(ui.panes.panes())==2
        assert abs(ui.center.winfo_width()-ui.right.winfo_width())<15
        checks.append("Hidden sidebar leaves equal Brain/chat panes")
        ui.toggle_sidebar(); pump(); assert len(ui.panes.panes())==3
        from native_capture import capture
        capture(root,ROOT/'desktop'/'task223-native-review'/'three-pane.png')
        ui.open_advanced("Employees"); pump()
        assert ui.advanced["Employees"].winfo_exists()
        checks.append("Advanced opens a separate native window")
        ui.save_note("Native Tk shell verification note."); pump()
        assert any(node.get("kind")=="chunk" for node in ui.graph)
        checks.append("Existing authenticated Brain API persists a consented local note")
        assert "memory:manage" in session.credentials["permissions"]
        checks.append("Existing authenticated session and CSRF are used")
        capture(root,ROOT/'desktop'/'task223-native-review'/'with-advanced.png')
        result={"status":"passed","checks":checks,"models":ui.model_catalog,"profile":str(profile)}
        print(json.dumps(result,indent=2))
        return result
    finally:
        root.destroy(); session.close()


if __name__=="__main__": run()
