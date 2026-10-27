import pytest
from PySide6.QtCore import Qt, QSettings, QProcess, QThread
import sys
from PySide6.QtWidgets import QPushButton, QComboBox, QDialog, QVBoxLayout, QLineEdit
from app.qt_desktop.shell import ShellManager
from app.qt_desktop.instance import Instance


class Session:
    def models(self): return [{'name':'test-local','tools':True}]
    def request(self, method, path, body=None, **kwargs):
        if path=='/api/native/windows':
            if method=='POST':
                import uuid
                return {'id':uuid.uuid4().hex}
            return {'windows':[],'operations':[],'capture':[],'global_stopped':False}
        if path.startswith('/api/native/windows/'):return {'closed':True}
        if path == '/api/memory/owner/native-graph': return {'nodes':[],'edges':[],'total_chunks':0}
        if path == '/api/agents': return {'items':[{'id':'local_worker','name':'Coordinator'}]}
        if path == '/api/projects': return {'items':[{'id':'project-a','name':'Project A'}]}
        raise AssertionError((method,path,body))


@pytest.fixture
def manager(qapp, qtbot, tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    manager = ShellManager(qapp, Session())
    yield manager
    for window in list(manager.windows): window.close()
    manager.shutdown()


def test_ctrl_n_creates_isolated_windows_and_ctrl_b_keeps_equal_panes(manager, qtbot):
    first = manager.new_window(); qtbot.waitUntil(lambda:first.model.count()==1)
    qtbot.keyClick(first, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda:len(manager.windows)==2)
    second=manager.windows[-1]; qtbot.waitUntil(lambda:second.model.count()==1)
    assert first.current() is not second.current()
    first.project.setCurrentIndex(1)
    assert first.current().project == 'project-a' and second.current().project == ''
    first.raise_(); first.activateWindow(); qtbot.waitUntil(first.isActiveWindow)
    first.composer.setFocus()
    qtbot.waitUntil(lambda:manager.app.focusWidget() is first.composer)
    qtbot.wait(100)  # Allow Windows' native focus handoff after Ctrl+N to settle.
    qtbot.keyClick(first.composer, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda:not first.sidebar.isVisible())
    sizes=first.splitter.sizes(); assert abs(sizes[1]-sizes[2]) <= 2
    assert all(c.accessibleName() for c in first.findChildren(QPushButton)+first.findChildren(QComboBox))


def test_settings_and_advanced_are_separate_singleton_windows(manager, qtbot):
    window=manager.new_window(); qtbot.waitUntil(lambda:window.model.count()==1)
    settings=manager.show_dialog('Settings'); advanced=manager.show_dialog('Advanced')
    assert settings is manager.show_dialog('Settings') and advanced is manager.show_dialog('Advanced')
    assert settings is not advanced and settings.isWindow() and advanced.isWindow()
    window.response_error = True
    window.done()
    assert 'failed' in window.status.text()
    assert window.send_button.isEnabled()
    assert window.status.textFormat() == Qt.TextFormat.PlainText
    threads=[]
    receive=window.receive
    def delivered(event):
        threads.append(QThread.currentThread()==manager.app.thread()); receive(event)
    window.receive=delivered
    manager.pool.submit(lambda:manager.work.event.emit(window,{'type':'chunk','text':'Queued on the UI thread'}))
    qtbot.waitUntil(lambda:len(threads)==1)
    assert threads==[True]


def test_local_second_launch_only_signals_the_existing_process(qapp, qtbot, tmp_path):
    first=Instance(tmp_path)
    assert first.acquire_or_notify()
    seen=[]; first.activated.connect(lambda:seen.append(True))
    try:
        process=QProcess()
        process.start(sys.executable, ['-c', 'import sys; from pathlib import Path; from PySide6.QtCore import QCoreApplication; from app.qt_desktop.instance import Instance; app=QCoreApplication([]); instance=Instance(Path(sys.argv[1])); assert not instance.acquire_or_notify()', str(tmp_path)])
        qtbot.waitUntil(lambda:seen==[True])
        qtbot.waitUntil(lambda:process.state()==QProcess.ProcessState.NotRunning)
        assert process.exitCode()==0, bytes(process.readAllStandardError()).decode()
        assert first.lock.isLocked()
    finally: first.close()


def test_refresh_keeps_missing_model_and_conversation_until_owner_changes_it(manager, qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    chat=window.current();chat.conversation='existing-conversation'
    catalog=dict(manager.catalog);catalog['models']=[{'name':'different-model','tools':True}]
    window.loaded(catalog)
    assert window.current() is chat and window.tabs.count()==1
    assert chat.model=='test-local' and window.model.currentData()=='test-local'
    assert 'unavailable' in window.model.currentText().lower()
    window.composer.setPlainText('Explain a binary tree')
    window.send()
    assert not window.busy and 'unavailable' in window.status.text().lower()
    window.model.setCurrentIndex(window.model.findData('different-model'))
    assert window.tabs.count()==2 and window.current().model=='different-model'


def test_thinking_control_only_applies_to_explicit_agent_loop(manager, qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    assert not window.thinking.isEnabled()
    window.agent_loop.setChecked(True)
    assert window.thinking.isEnabled()
    window.thinking.setChecked(True);window.agent_loop.setChecked(False)
    assert not window.thinking.isEnabled() and not window.thinking.isChecked()


def test_stop_shortcut_reaches_child_dialog_and_repeated_stop_never_resumes(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id))
    calls=[];original=manager.session.request
    def request(method,path,body=None,**kwargs):calls.append(path);return original(method,path,body,**kwargs)
    monkeypatch.setattr(manager.session,'request',request)
    dialog=QDialog(window);layout=QVBoxLayout(dialog);entry=QLineEdit();layout.addWidget(entry);dialog.show()
    qtbot.keyClick(entry,Qt.Key.Key_Period,Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda:window.window_stopped)
    qtbot.keyClick(entry,Qt.Key.Key_Period,Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda:sum(path.endswith('/stop') for path in calls)>=2)
    assert not any(path.endswith('/resume') for path in calls)
    dialog.close()


def test_global_stop_shortcut_works_from_singleton_settings(manager,qtbot,monkeypatch):
    manager.new_window();settings=manager.show_dialog('Settings');calls=[]
    monkeypatch.setattr(manager,'stop_all',lambda:calls.append('stop'))
    qtbot.keyClick(settings,Qt.Key.Key_Period,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    assert calls==['stop']
