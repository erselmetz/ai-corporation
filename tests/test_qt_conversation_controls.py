import pytest
import threading
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QInputDialog,QLineEdit,QPushButton
from test_qt_shell import manager


def test_f2_rename_and_confirmed_delete_of_unsent_chat(manager,qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    renamed=[]
    def fill():
        dialogs=[d for d in window.findChildren(QInputDialog) if d.isVisible()]
        if not dialogs:return
        dialog=dialogs[0];dialog.findChild(QLineEdit).setText('Bagong pangalan — Taglish');renamed.append(True);dialog.accept()
    QTimer.singleShot(100,fill)
    qtbot.keyClick(window.tabs,Qt.Key.Key_F2);qtbot.wait(150)
    assert renamed==[True],'F2 did not open a rename control'
    assert window.tabs.tabText(window.tabs.currentIndex())=='Bagong pangalan — Taglish'
    old=window.current()
    next(b for b in window.findChildren(QPushButton) if b.text()=='Delete chat').click()
    assert window.current() is old  # Requesting deletion is not confirmation.
    next(b for b in window.findChildren(QPushButton) if b.text()=='Confirm delete').click()
    qtbot.waitUntil(lambda:window.current() is not old)
    assert window.tabs.count()==1 and old not in window.chats.values()


def test_exact_owner_typed_link_runs_without_redundant_approval_and_preserves_unknown_handoff(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id) and window.model.count()==1)
    calls=[]
    def prepare(chat,text,name,args,**kwargs):
        calls.append(('prepare',text,name,args))
        return {'id':'action','summary':'Open the approved browser destination',
                'details':args['url'],'approval_digest':'exact-digest'}
    def execute(chat,method,path,body=None,**kwargs):
        calls.append((method,path,body))
        return {'state':'unverified','result':{'message':'Browser handoff was not confirmed; page loading is unknown.'}}
    monkeypatch.setattr(manager.transport,'prepare_tool',prepare)
    monkeypatch.setattr(manager.transport,'tool_api',execute)
    window.current().model=''  # Opening an explicitly approved URL needs no model inference.
    window.composer.setPlainText('open youtube');window.send()
    qtbot.waitUntil(lambda:not window.busy)
    assert calls[0]==('prepare','open youtube','open_url',{'url':'https://www.youtube.com/'})
    assert calls[-1]==('POST','/action/execute',{'confirmed_digest':'exact-digest'})
    assert window.pending_tool is None
    assert 'page loading is unknown' in window.tabs.currentWidget().toPlainText()
    assert 'unverified' in window.status.text()


def test_stop_denies_pending_link_without_browser_or_model_call(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id) and window.model.count()==1)
    calls=[]
    entered=threading.Event();release=threading.Event()
    def prepare(*args,**kwargs):
        entered.set();assert release.wait(3)
        return {'id':'action','summary':'Open link','details':'https://www.youtube.com/','approval_digest':'digest'}
    monkeypatch.setattr(manager.transport,'prepare_tool',prepare)
    def deny(chat,method,path,body=None,**kwargs):
        calls.append(path)
        return {'state':'denied','result':{'message':'Cancelled before execution. No tool action was run.'}}
    monkeypatch.setattr(manager.transport,'tool_api',deny)
    window.composer.setPlainText('open youtube');window.send()
    qtbot.waitUntil(entered.is_set);window.stop_window();release.set();qtbot.waitUntil(lambda:not window.busy)
    assert calls==['/action/deny'] and window.pending_tool is None
    assert 'No tool action was run' not in window.tabs.currentWidget().toPlainText()


def test_nonweb_open_command_is_rejected_before_any_submission(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    monkeypatch.setattr(manager.transport,'prepare_tool',lambda *a,**k:pytest.fail('Unapproved tool submission'))
    window.composer.setPlainText('open file:///C:/private.txt');window.send()
    assert not window.busy and window.composer.toPlainText()=='open file:///C:/private.txt'
    assert 'http or https' in window.status.text()
