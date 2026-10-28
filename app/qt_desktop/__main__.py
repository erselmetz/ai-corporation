"""Single-process Qt entry point; no Electron or Node startup dependency."""
import argparse
import os
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QLabel
from PySide6.QtCore import QSettings
from .instance import Instance
from .theme import apply_theme


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path, help='Isolated application-data root for QA')
    args = parser.parse_args()
    if args.profile: os.environ['LOCALAPPDATA'] = str(args.profile.resolve())
    data = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local'/'share'))/'ERSELMETZ AI'
    app = QApplication(sys.argv[:1]); app.setApplicationName('ERSELMETZ AI'); app.setOrganizationName('ERSELMETZ AI')
    apply_theme(app)
    instance = Instance(data); session = None; manager = None
    from .failures import record_failure,ui_exception_handler
    previous_hook=sys.excepthook;sys.excepthook=ui_exception_handler(data,lambda:manager)
    stamp=None
    from .events import record_event
    try:
        from app.build_stamp import BUILD_STAMP
        stamp=BUILD_STAMP
        record_event(data,'startup',stamp)
        if not instance.acquire_or_notify(): return 0
        from app.local_owner_credential import LocalOwnerCredentialStore
        store = LocalOwnerCredentialStore(); password = None
        if store.exists():
            password, accepted = QInputDialog.getText(None, 'Unlock ERSELMETZ AI', 'Owner password:', QLineEdit.EchoMode.Password)
            if not accepted: return 0
            if not store.verify(password): raise ValueError('Owner password did not match.')
        os.chdir(data)
        loading = QLabel('Opening your local workspace…'); loading.setWindowTitle('Opening local workspace'); loading.resize(420, 100); loading.show(); app.processEvents()
        from app.native_desktop.session import NativeSession
        session = NativeSession(password)
        from .shell import ShellManager
        from .windows import WindowStore
        preferences=QSettings(str(data/'native-preferences.ini'),QSettings.Format.IniFormat)
        if not args.profile and not (data/'native-preferences.ini').exists():
            previous=QSettings('ERSELMETZ AI','Native shell')
            for key in ['lightTheme','reducedMotion']:
                preferences.setValue(key,previous.value(key,False,type=bool))
            preferences.sync()
        manager = ShellManager(app, session,window_store=WindowStore(data/'windows.json'),preferences=preferences)
        instance.activated.connect(manager.new_window)
        manager.restore_windows(); loading.close()
        record_event(data,'ready',stamp)
        return app.exec()
    except Exception as error:
        record_failure(data,stage='startup',error=error)
        QMessageBox.critical(None, 'ERSELMETZ AI', str(error)[:400]); return 1
    finally:
        sys.excepthook=previous_hook
        if manager: manager.shutdown()
        if session: session.close()
        instance.close()
        if stamp:record_event(data,'shutdown',stamp)


if __name__ == '__main__': raise SystemExit(main())
