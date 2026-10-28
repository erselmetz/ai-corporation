"""Deterministic native-window screenshots at a process-selected Windows DPI."""
import argparse,json,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtCore import QSettings
from app.qt_desktop.shell import ShellManager
from app.qt_desktop.pages import PAGES

class FixtureSession:
    def request(self,method,path,body=None,**kwargs):
        if method!='GET':raise AssertionError('Screenshot fixture must never mutate or call a model')
        return {'items':[{'id':'sample-record','name':'Mahabang Taglish na pangalan para sa malinaw na native workspace','status':'AI-verified fixture','description':'Local fixture only. No real-provider or device claim.','content':'# Offline documentation\nNative Markdown with no remote assets.'}]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--light',action='store_true');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    preferences=QSettings(str(args.output/'preferences.ini'),QSettings.Format.IniFormat);preferences.setValue('lightTheme',args.light)
    manager=ShellManager(app,FixtureSession(),preferences=preferences);results=[]
    try:
        for title in ['Settings','Advanced',*PAGES]:
            w=manager.show_dialog(title) if title in {'Settings','Advanced'} else manager.open_page(title,QLabel())
            deadline=time.monotonic()+10
            while getattr(w,'loading',False) and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            app.processEvents()
            if getattr(w,'loading',False):raise AssertionError(title+' did not finish loading')
            for width,height in [(960,700),(700,560)]:
                w.resize(width,height);app.processEvents();path=args.output/(title.replace(' ','-').replace('/','-')+'-'+str(width)+'.png');assert w.grab().save(str(path))
                results.append({'window':title,'size':[w.width(),w.height()],'device_pixel_ratio':w.devicePixelRatioF(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'path':str(path)})
            w.close()
        (args.output/'matrix.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        print(str(len(results))+' native screenshots saved')
    finally:manager.shutdown()
if __name__=='__main__':main()
