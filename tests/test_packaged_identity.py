import json
from pathlib import Path
from PySide6.QtWidgets import QLabel,QPushButton
from app.qt_desktop.events import record_event
from test_qt_shell import manager

def test_metadata_log_rejects_messages_and_stays_bounded(tmp_path):
    stamp={'version':'0.1.0','commit':'a'*40}
    assert not record_event(tmp_path,'prompt: private data',stamp)
    assert not record_event(tmp_path,'startup',{'version':'secret / path','commit':'a'*40})
    for _ in range(65):assert record_event(tmp_path,'ready',stamp)
    data=json.loads((tmp_path/'native-events.json').read_text())
    assert len(data)==60
    assert all(set(row)=={'at','event','version','commit'} for row in data)
    assert 'private' not in (tmp_path/'native-events.json').read_text()

def test_about_shows_actual_stamp_and_is_a_singleton(manager,qtbot):
    from app.build_stamp import BUILD_STAMP
    window=manager.show_dialog('About')
    labels='\n'.join(w.text() for w in window.findChildren(QLabel))
    assert BUILD_STAMP['version'] in labels and BUILD_STAMP['commit'] in labels
    assert manager.show_dialog('About') is window and window.isWindow()
    assert all(w.accessibleName() for w in window.findChildren(QPushButton))
    window.close()

def test_installer_data_removal_is_explicit_and_silent_default_keeps_data():
    source=(Path(__file__).resolve().parents[1]/'packaging/native.iss').read_text()
    assert 'PrivilegesRequired=lowest' in source
    assert 'RemoveOwnerData := False' in source and 'if not UninstallSilent then' in source
    assert 'MB_DEFBUTTON2' in source and 'SafeDataTree(Folder, 0)' in source
    assert "{localappdata}\\ERSELMETZ AI Review\\ERSELMETZ AI" in source
    assert 'Parameters: "--profile' in source
