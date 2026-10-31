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
        if path == '/api/local/provider-connections': return {'items':[]}
        raise AssertionError((method,path,body))


@pytest.fixture
def manager(qapp, qtbot, tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    manager = ShellManager(qapp, Session())
    yield manager
    for window in list(manager.windows): window.close()
    manager.shutdown()


def test_ctrl_n_creates_isolated_windows_and_ctrl_b_keeps_neural_workspace_dominant(manager, qtbot):
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
    sizes=first.splitter.sizes();assert sizes[1]>sizes[2] and sizes[2]>=320
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


def test_model_picker_lists_all_detected_ollama_entries_but_disables_non_chat_models(manager,qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    data=dict(manager.catalog);data['models']=[
        {'name':'llama3.2:3b','available':True,'category':'local-chat'},
        {'name':'nomic-embed-text:latest','available':False,'category':'embedding','reason':'Embedding model · used by My Brain, not chat'},
        {'name':'gemma3:31b-cloud','available':False,'category':'cloud','reason':'Cloud via Ollama · connect and approve each cloud turn'}]
    window.current().model='llama3.2:3b'
    window.loaded(data)
    assert window.model.count()==3 and window.available_models=={'llama3.2:3b'}
    assert window.model.model().item(0).isEnabled()
    assert not window.model.model().item(1).isEnabled() and 'Embedding model' in window.model.itemText(1)
    assert not window.model.model().item(2).isEnabled() and 'Cloud via Ollama' in window.model.itemText(2)
    assert '3 Ollama entries detected' in window.status.text()


def test_settings_opens_simple_provider_setup_with_no_cloud_call(manager,qtbot):
    manager.new_window();settings=manager.show_dialog('Settings')
    setup=manager.show_provider_setup();qtbot.waitUntil(lambda:'Ollama detection complete' in setup.status.text())
    assert setup is manager.show_provider_setup() and setup.key.echoMode()==QLineEdit.EchoMode.Password
    assert 'test-local' in setup.local.toPlainText() and 'optional' in setup.status.text().lower()
    setup.close();settings.close()


def test_failed_request_adds_one_fail_closed_trace_line(manager, qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    before=sum(window.steps.item(i).text()=='The response failed. No success was assumed.'
               for i in range(window.steps.count()))
    window.busy=True;window.send_button.setEnabled(False)
    window.failed(RuntimeError('private provider detail'))
    after=sum(window.steps.item(i).text()=='The response failed. No success was assumed.'
              for i in range(window.steps.count()))
    assert after == before + 1
    assert window.send_button.isEnabled() and not window.busy
    assert 'private provider detail' not in window.status.text()


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
    assert not window.agent_loop.isChecked() and not window.thinking.isEnabled()
    assert not window.ask_first.isChecked()
    window.agent_loop.setChecked(True);assert window.thinking.isEnabled()
    window.thinking.setChecked(True);window.agent_loop.setChecked(False)
    assert not window.thinking.isEnabled() and not window.thinking.isChecked()


def test_desktop_folder_request_executes_exact_owner_command_without_second_prompt(manager,qtbot,tmp_path,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1 and bool(window.native_id))
    calls=[]
    monkeypatch.setattr('app.native_io.desktop_directory',lambda:tmp_path)
    monkeypatch.setattr(manager.transport,'grant_root',lambda chat,path,**kwargs:calls.append(('root',path)) or {'id':'a'*32})
    monkeypatch.setattr(manager.transport,'prepare_tool',lambda chat,text,name,args,**kwargs:
        calls.append((name,args)) or {'id':'b'*32,'tool':name,'state':'pending','summary':'Create folder',
            'details':'Create this empty folder:\nNew folder','approval_required':True,'approval_digest':'c'*64,'result':None})
    monkeypatch.setattr(manager.transport,'tool_api',lambda chat,method,suffix,body=None,**kwargs:
        calls.append((method,suffix,body)) or {'state':'completed','result':{'message':'Folder creation confirmed: New folder'}})
    window.composer.setPlainText('create folder in desktop');window.send()
    qtbot.waitUntil(lambda:not window.busy)
    assert calls==[('root',str(tmp_path)),('create_folder',{'root_id':'a'*32,'path':'New folder'}),
                   ('POST','/'+'b'*32+'/execute',{'confirmed_digest':'c'*64})]
    assert 'Folder creation confirmed' in window.tabs.currentWidget().toPlainText()


@pytest.mark.parametrize('prompt',["can you open youtube", "open youtube in chrome"])
def test_natural_youtube_request_executes_exact_owner_command_without_second_prompt(manager,qtbot,monkeypatch,prompt):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1 and bool(window.native_id))
    calls=[]
    monkeypatch.setattr(manager.transport,'prepare_tool',lambda chat,text,name,args,**kwargs:
        calls.append((text,name,args)) or {'id':'b'*32,'tool':name,'state':'pending','summary':'Open site',
            'details':'Exact destination:\n'+args['url'],'approval_required':True,
            'approval_digest':'c'*64,'result':None})
    monkeypatch.setattr(manager.transport,'tool_api',lambda chat,method,suffix,body=None,**kwargs:
        calls.append((method,suffix,body)) or {'state':'submitted','result':{'message':'Browser handoff confirmed'}})
    window.composer.setPlainText(prompt);window.send()
    qtbot.waitUntil(lambda:not window.busy)
    assert calls==[(prompt,'open_url',{'url':'https://www.youtube.com/'}),
                   ('POST','/'+'b'*32+'/execute',{'confirmed_digest':'c'*64})]
    assert 'cannot directly open' not in window.tabs.currentWidget().toPlainText().casefold()


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
