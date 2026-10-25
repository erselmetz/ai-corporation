"""Deterministic Qt layout grabs; set QT_SCALE_FACTOR per process for DPI QA."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app.qt_desktop.shell import ShellManager
    from app.qt_desktop.theme import apply_theme
    class LayoutSession:
        def models(self): return [{'name':'Layout fixture (no inference)'}]
        def request(self, method, path, body=None):
            if path=='/api/agents': return {'items':[{'id':'local_worker','name':'Coordinator'}]}
            if path=='/api/projects': return {'items':[]}
            raise AssertionError('Layout fixture never executes actions')
    app=QApplication([]); manager=ShellManager(app,LayoutSession()); window=manager.new_window()
    output=ROOT/'task223-review'/'layout'; output.mkdir(parents=True,exist_ok=True)
    QTest.qWait(150)
    text='Mahabang Taglish na mensahe: pakisuri ang mga detalye bago tayo magpatuloy. Walang aksyon na pinatakbo sa layout fixture na ito. '
    window.tabs.currentWidget().setPlainText(text*12)
    window.composer.setPlainText(text*3)
    checks=[]
    try:
        for light in [False,True]:
            apply_theme(app,light)
            for width,height in [(1360,820),(800,580)]:
                window.resize(width,height); app.processEvents(); QTest.qWait(100)
                assert window.composer.isVisible() and window.tabs.isVisible()
                assert window.composer.width()>100 and window.tabs.width()>100
                assert window.sidebar.horizontalScrollBar().maximum()==0, 'Sidebar controls overflow horizontally'
                name=f'{os.environ.get("QT_SCALE_FACTOR","1")}-{"light" if light else "dark"}-{width}.png'
                window.grab().save(str(output/name))
                checks.append({'image':name,'logical_size':[window.width(),window.height()], 'dpr':window.devicePixelRatioF(),
                               'chat_width':window.tabs.width(),'composer_width':window.composer.width()})
        (output/f'{os.environ.get("QT_SCALE_FACTOR","1")}.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
        print(json.dumps(checks))
    finally:
        window.close(); manager.shutdown()


if __name__=='__main__': main()
