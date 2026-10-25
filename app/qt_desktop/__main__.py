"""Single-process Qt entry point; no Electron or Node startup dependency."""
import argparse
import os
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QLabel
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
    try:
        if not instance.acquire_or_notify(): return 0
        from app.local_owner_credential import LocalOwnerCredentialStore
        store = LocalOwnerCredentialStore(); password = None
        if store.exists():
            password, accepted = QInputDialog.getText(None, 'Unlock ERSELMETZ AI', 'Owner password:', QLineEdit.EchoMode.Password)
            if not accepted: return 0
            if not store.verify(password): raise ValueError('Owner password did not match.')
        os.chdir(data)
        loading = QLabel('Opening your local workspace…'); loading.setWindowTitle('Opening local workspace'); loading.resize(420, 100); loading.show(); app.processEvents()
        from app.desktop_launcher import LocalApplicationController
        from app.native_desktop.session import NativeSession
        class OwnedLease:
            def acquire(self):
                if not instance.lock.isLocked(): raise RuntimeError('The application lock is required.')
            def release(self): pass
        # The Qt lock is authoritative; do not acquire another application lock.
        factory = lambda **kwargs: LocalApplicationController(**kwargs, lease_factory=OwnedLease)
        session = NativeSession(password, controller_factory=factory)
        from .shell import ShellManager
        manager = ShellManager(app, session)
        instance.activated.connect(manager.new_window)
        manager.new_window(); loading.close()
        return app.exec()
    except Exception as error:
        QMessageBox.critical(None, 'ERSELMETZ AI', str(error)[:400]); return 1
    finally:
        if manager: manager.shutdown()
        if session: session.close()
        instance.close()


if __name__ == '__main__': raise SystemExit(main())
