"""Native widget.grab baseline check; each DPI runs in a separate Python process.

Use --record only for a reviewed intentional baseline change. No provider calls.
"""
import argparse,json,os,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scale',choices=['1','1.25','1.5'],required=True)
    parser.add_argument('--theme',choices=['dark','light'],required=True);parser.add_argument('--record',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'task227-review'/'screenshots');args=parser.parse_args()
    os.environ['QT_SCALE_FACTOR']=args.scale
    from PySide6.QtCore import QSettings,Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from app.qt_desktop.shell import ShellManager
    from app.qt_desktop.theme import apply_theme
    import importlib.util
    spec=importlib.util.spec_from_file_location('shell_fixture',ROOT/'tests'/'test_qt_shell.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    app=QApplication([]);app.setApplicationName('ERSELMETZ AI screenshot check')
    args.output.mkdir(parents=True,exist_ok=True)
    preferences=QSettings(str(args.output/f'preferences-{args.scale}-{args.theme}.ini'),QSettings.Format.IniFormat)
    preferences.setValue('lightTheme',args.theme=='light');preferences.setValue('reducedMotion',True)
    manager=ShellManager(app,module.Session(),preferences=preferences)
    apply_theme(app,light=args.theme=='light')
    window=manager.new_window();deadline=time.monotonic()+10
    while not window.model.count():
        app.processEvents();time.sleep(.01)
        if time.monotonic()>deadline:raise RuntimeError('Catalog did not load')
    manager.queue_timer.stop()
    window.composer.setPlainText('Paki-check ang project natin: mahaba ang paliwanag pero dapat malinaw pa rin ang bawat button, model at status. '*3)
    window.status.setText('Ready · Local test model · No action running')
    window.setFocus(Qt.FocusReason.OtherFocusReason)
    reports=[];baseline_root=ROOT/'tests'/'baselines'/'qt-shell';baseline_root.mkdir(parents=True,exist_ok=True)
    try:
        for width,height in [(1100,720),(1280,900),(1600,1000)]:
            window.resize(width,height)
            for _ in range(15):app.processEvents();time.sleep(.01)
            image=window.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
            name=f'{args.theme}-{args.scale}-{width}x{height}.png';target=args.output/name;image.save(str(target))
            baseline=baseline_root/name
            if args.record:image.save(str(baseline))
            if not baseline.is_file():raise AssertionError(f'Missing reviewed baseline: {baseline}')
            expected=QImage(str(baseline)).convertToFormat(QImage.Format.Format_RGB32)
            if expected.size()!=image.size():raise AssertionError(f'Baseline size changed: {name}')
            # Small antialias/focus differences are bounded, not silently rebaselined.
            actual=bytes(image.constBits());prior=bytes(expected.constBits())
            changed=sum(abs(a-b)>20 for a,b in zip(actual,prior))/len(actual)
            reports.append({'name':name,'physical_size':[image.width(),image.height()],'changed_channels':changed})
            if changed>.015:raise AssertionError(f'Visual regression {name}: {changed:.2%} changed channels')
        print(json.dumps({'scale':args.scale,'theme':args.theme,'screenshots':reports}))
    finally:
        window.close();manager.shutdown();app.processEvents()


if __name__=='__main__':main()
