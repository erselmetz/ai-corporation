"""Optional pytest plugin recording actual native action signals during Qt tests."""
import json,weakref
from collections import Counter
from pathlib import Path

created=Counter();activated=Counter();originals=[]


def pytest_addoption(parser):parser.addoption('--qt-action-report',default=None)


def identity(widget):
    try:
        from PySide6.QtGui import QAction
        if isinstance(widget,QAction):return 'Shortcut: '+widget.shortcut().toString() if not widget.shortcut().isEmpty() else 'Action: '+widget.text()
        return widget.accessibleName() or widget.text()
    except RuntimeError:return ''


def pytest_configure(config):
    if not config.getoption('--qt-action-report'):return
    from PySide6.QtWidgets import QPushButton,QCheckBox
    from PySide6.QtGui import QAction
    def patch(kind,signal):
        original=kind.__init__;originals.append((kind,original))
        def initialize(self,*args,**kwargs):
            original(self,*args,**kwargs);reference=weakref.ref(self)
            # Names/shortcuts are assigned after construction. A queued callback
            # records them after the widget has been configured by its owner.
            from PySide6.QtCore import QTimer
            def seen():
                value=reference()
                if value is not None:
                    name=identity(value)
                    if name:created[name]+=1
            QTimer.singleShot(0,seen)
            def fired(*unused):
                value=reference()
                if value is not None:
                    name=identity(value)
                    if name:activated[name]+=1
            getattr(self,signal).connect(fired)
        kind.__init__=initialize
    patch(QPushButton,'clicked');patch(QCheckBox,'clicked');patch(QAction,'triggered')


def pytest_sessionfinish(session,exitstatus):
    path=session.config.getoption('--qt-action-report')
    for kind,original in originals:kind.__init__=original
    if path:
        target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({'test_exit':exitstatus,'created':dict(sorted(created.items())),
            'activated':dict(sorted(activated.items())),'not_activated':sorted(set(created)-set(activated))},indent=2)+'\n',encoding='utf-8')
