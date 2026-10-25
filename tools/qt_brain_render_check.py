"""Measure the actual shared widget using real tracked-file chunks, not random dots."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--nodes',type=int,choices=[300,2000],required=True); args=parser.parse_args()
    from app.knowledge.native_brain import chunks
    nodes=[]; edges=[]; sources=[]
    tracked=subprocess.check_output(['git','ls-files','-z','--','app','docs','tests'],cwd=ROOT).decode('utf-8').split('\0')
    for relative in tracked:
        path=ROOT/relative
        if path.suffix not in {'.py','.mjs','.md','.txt','.json','.html'} or not path.is_file() or path.stat().st_size>1_000_000: continue
        try: text=path.read_text(encoding='utf-8')
        except UnicodeError: continue
        if not text.strip(): continue
        cluster=hashlib.sha256(relative.encode()).hexdigest()
        sources.append({'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        for position,chunk in enumerate(chunks(text)):
            identifier=cluster+':'+str(position)
            nodes.append({'id':identifier,'kind':'chunk','cluster':cluster,'source':relative,'snippet':chunk})
            edges.append({'from':'source:'+cluster,'to':identifier,'kind':'same-source'})
            if len(nodes)==args.nodes: break
        if len(nodes)==args.nodes: break
    assert len(nodes)==args.nodes,'Not enough real source chunks; never fabricate filler nodes'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from app.qt_desktop.brain import BrainScene
    intervals=[]; paints=[]; previous=time.perf_counter()
    class Measured(BrainScene):
        def paintEvent(self,event):
            nonlocal previous
            started=time.perf_counter(); super().paintEvent(event); finished=time.perf_counter()
            intervals.append(finished-previous); previous=finished; paints.append(finished-started)
    app=QApplication([]); view=Measured(); view.limit=args.nodes
    view.set_graph({'nodes':nodes,'edges':edges}); assert len(view.nodes)==args.nodes
    view.resize(880,680); view.setWindowTitle('Renderer benchmark · real source chunks'); view.show(); view.timer.setInterval(0)
    output=ROOT/'task224-review'/'render'; output.mkdir(parents=True,exist_ok=True)
    def finish():
        view.timer.stop(); view.grab().save(str(output/f'{args.nodes}.png')); app.quit()
    QTimer.singleShot(4500,finish); app.exec()
    frames=intervals[10:]; durations=paints[10:]
    result={'nodes':args.nodes,'rendered_nodes':len(view.nodes),'repaint_fps':round(len(frames)/sum(frames),2),
            'mean_frame_ms':round(sum(frames)/len(frames)*1000,2),'p95_frame_ms':round(sorted(frames)[int(len(frames)*.95)]*1000,2),
            'mean_paint_ms':round(sum(durations)/len(durations)*1000,2),'dpr':view.devicePixelRatioF(),'dimensions':[880,680],
            'fixture':'Real tracked-file chunks, in memory only; not retained user knowledge or a model-activity claim',
            'measurement':'Uncapped CPU repaint throughput; production animation is capped at approximately 30 FPS',
            'sources':sources}
    (output/f'{args.nodes}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sources'}))


if __name__=='__main__': main()
