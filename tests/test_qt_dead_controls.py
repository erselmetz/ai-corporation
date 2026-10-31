"""Click shell actions through their real connections; fake only external boundaries."""
from PySide6.QtCore import QTimer,QPoint,Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton,QFileDialog,QInputDialog,QDialog
from test_qt_shell import manager


def test_shell_static_actions_are_connected_and_operate_without_external_effects(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id) and window.model.count()==1)
    def click(name):
        candidates=[button for button in window.findChildren(QPushButton) if button.accessibleName()==name]
        assert len(candidates)==1,name
        assert candidates[0].isEnabled(),name
        candidates[0].click()
    click('New window');assert len(manager.windows)==2
    for kind in ['Settings','Advanced']:
        click(kind);dialog=manager.dialogs[kind];assert dialog.isVisible()
        next(button for button in dialog.findChildren(QPushButton) if button.text()=='Close').click()
        assert not dialog.isVisible()
    click('Toggle sidebar');assert not window.sidebar.isVisible()
    click('Toggle sidebar');assert window.sidebar.isVisible()
    count=window.tabs.count();click('New chat tab');assert window.tabs.count()==count+1
    calls=[];original=manager.session.request
    def request(method,path,body=None,**kwargs):
        calls.append((method,path))
        if path.startswith('/api/native/windows/') and path.endswith('/resume'):return {'generation':1}
        return original(method,path,body,**kwargs)
    monkeypatch.setattr(manager.session,'request',request)
    manager.catalog=None;click('Refresh models');qtbot.waitUntil(lambda:window.model.count()==1 and not window.registering)
    qtbot.waitUntil(lambda:not manager.brain_loading);before=len(calls);click('Refresh Brain')
    qtbot.waitUntil(lambda:any(path=='/api/memory/owner/native-graph' for _,path in calls[before:]))
    chooser=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *a,**k:chooser.append('files') or ([],''))
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a,**k:chooser.append('folder') or '')
    monkeypatch.setattr(QInputDialog,'getMultiLineText',lambda *a,**k:chooser.append('note') or ('',False))
    for name in ['Feed file','Feed folder','Add note','Choose a local file-tool root for this conversation']:click(name)
    assert chooser==['files','folder','note','folder']
    def cancel_owned_dialog():
        for dialog in manager.app.topLevelWidgets():
            if isinstance(dialog,QDialog) and dialog.parent() is window and dialog.isVisible():
                cancel=next((button for button in dialog.findChildren(QPushButton) if button.text()=='Cancel'),None)
                cancel.click() if cancel else dialog.reject()
    for name in ['Exact math','Rename current chat (F2)']:
        QTimer.singleShot(50,cancel_owned_dialog);click(name)
    click('Choose and approve one exact desktop action')
    assert any(isinstance(item,QDialog) and item.parent() is window and item.isVisible() for item in manager.app.topLevelWidgets())
    for dialog in manager.app.topLevelWidgets():
        if isinstance(dialog,QDialog) and dialog.parent() is window:dialog.close()
    import app.qt_desktop.capture_controls as captures
    device_checks=[];monkeypatch.setattr(captures,'available_devices',lambda kind:device_checks.append(kind) or [])
    for kind in ['camera','microphone','screen']:click('Request one '+kind+' capture after exact consent')
    assert device_checks==['camera','microphone','screen']
    def send(chat,text,stop,emit,**kwargs):emit({'type':'chunk','text':'Fake local reply'});emit({'type':'complete'})
    monkeypatch.setattr(manager.transport,'send',send)
    window.agent_loop.setChecked(False)
    window.composer.setPlainText('A harmless UI fixture question');click('Send');qtbot.waitUntil(lambda:not window.busy)
    assert 'Fake local reply' in window.tabs.currentWidget().toPlainText()
    window.composer.setPlainText('Another harmless UI fixture question')
    next(action for action in window.actions() if action.shortcut().toString()=='Ctrl+Return').trigger()
    qtbot.waitUntil(lambda:not window.busy)
    assert window.tabs.currentWidget().toPlainText().count('Fake local reply')==2
    click('Open full-window Brain');assert window.full_brain is not None
    click('Brain list fallback');assert window.brain.stack.currentWidget() is window.brain.list
    click('Open full-window Brain');assert window.full_brain is None
    click('Brain list fallback');qtbot.waitUntil(lambda:bool(window.brain.scene.points))
    point,_,_=window.brain.scene.points[0];QTest.mouseClick(window.brain.scene,Qt.MouseButton.LeftButton,pos=QPoint(round(point.x()),round(point.y())))
    qtbot.waitUntil(window.brain.card.isVisible);click('Close Brain node card');assert not window.brain.card.isVisible()
    click('Open full-window Brain')
    click('Stop or resume this window from full Brain');assert window.window_stopped
    click('Emergency stop all windows from full Brain');assert window.global_stopped
    click('Open full-window Brain')
    click('Stop or resume this chat window');click('Emergency stop all windows')
    settings=manager.show_dialog('Settings')
    next(button for button in settings.findChildren(QPushButton) if button.text()=='Resume protected work').click()
    qtbot.waitUntil(lambda:any('resume' in path for _,path in calls))
    settings.close()


def test_stateful_cancel_release_and_draft_buttons_do_not_run_unapproved_work(manager,qtbot,monkeypatch):
    import base64,threading
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id) and window.model.count()==1)
    def click(parent,name):
        buttons=[item for item in parent.findChildren(QPushButton) if item.accessibleName()==name]
        assert len(buttons)==1 and buttons[0].isEnabled(),name
        buttons[0].click()
    entered=threading.Event();cancelled=[]
    def feed(window_id,text,stop,**kwargs):entered.set();assert stop.wait(3);return {'state':'unchanged'}
    monkeypatch.setattr(manager.transport,'feed_text',feed)
    monkeypatch.setattr(manager.transport,'cancel_feed',lambda window_id:cancelled.append(window_id) or {})
    window.confirm_feed([],'Harmless fixture note');click(window.feed_frame,'Save locally')
    qtbot.waitUntil(entered.is_set);click(window,'Cancel feed');qtbot.waitUntil(lambda:not window.feeding and bool(cancelled))
    assert window.feed_stop.is_set() and cancelled==[window.native_id]
    window.confirm_feed([],'Do not retain this second fixture note');click(window.feed_frame,'Cancel');assert window.pending_feed is None
    capture=window.capture_controls;capture.chat=window.current();capture.lease='a'*32;releases=[]
    monkeypatch.setattr(capture,'api',lambda method,suffix='',body=None:releases.append((method,suffix)) or {})
    window.release_capture_button.setEnabled(True);click(window,'Stop capture or retry its ownership release; does not capture data')
    qtbot.waitUntil(lambda:capture.lease is None)
    assert releases==[('POST','/'+'a'*32+'/finish')]
    frame={'kind':'screen','data':bytearray(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='))}
    capture.show_image(frame);click(capture.preview,'Discard local capture');assert frame['data']==bytearray()
    sent=[]
    monkeypatch.setattr(manager.transport,'preview_knowledge',lambda *a,**k:{'items':[],'digest':'d'*64})
    monkeypatch.setattr(manager.transport,'send',lambda chat,text,stop,emit,**kwargs:sent.append(kwargs))
    window.use_brain.setChecked(True);window.composer.setPlainText('Review private fixture context')
    click(window,'Send');qtbot.waitUntil(lambda:not window.busy)
    assert sent[0]['knowledge']['knowledge_preview_digest']=='d'*64
    window.use_brain.setChecked(False)
    calls=[]
    monkeypatch.setattr(manager.transport,'tool_api',lambda chat,method,suffix,body=None,**kwargs:calls.append((method,suffix)) or {'state':'denied','result':{'message':'No tool action was run.'}})
    action={'id':'b'*32,'summary':'Fixture calculation','details':'Expression: 17 * 19','approval_digest':'c'*64}
    window.busy=True;window.show_tool_review(window.current(),window.native_generation,action)
    click(window.tool_frame,'Cancel action');qtbot.waitUntil(lambda:not window.busy)
    assert calls==[('POST','/'+'b'*32+'/deny')]
    monkeypatch.setattr(manager.transport,'transcribe_local',lambda *a,**k:'Harmless local transcript')
    for button in ['Use reviewed transcript as an unsent draft','Discard local transcript']:
        audio={'data':bytearray(b'fixture audio; decoder boundary is mocked')}
        capture.transcribe(audio);qtbot.waitUntil(lambda:capture.preview is not None)
        click(capture.preview,button);assert not audio['data']
        assert window.composer.toPlainText()=='Harmless local transcript'


def test_voice_first_transcript_sends_directly_and_text_stays_optional(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id) and window.model.count()==1)
    assert window.voice_button.text()=='🎙 Speak'
    assert window.voice_button.accessibleName()=='Speak a message; press again to finish and send'
    assert 'optional' in window.composer.placeholderText().lower() and window.speak_replies.isChecked()
    sent=[]
    def send(chat,text,stop,emit,**kwargs):
        sent.append(text);emit({'type':'chunk','text':'Short spoken answer.'});emit({'type':'complete'})
    monkeypatch.setattr(manager.transport,'send',send)
    spoken=[];monkeypatch.setattr(manager.transport,'speak_local',lambda text:spoken.append(text) or {'active':True})
    monkeypatch.setattr(manager.transport,'transcribe_local',lambda *a,**k:'Voice-first question')
    audio={'data':bytearray(b'fixture audio')};window.capture_controls.chat=window.current()
    window.capture_controls.transcribe(audio,direct=True)
    qtbot.waitUntil(lambda:not window.busy and sent==['Voice-first question'])
    qtbot.waitUntil(lambda:spoken==['Short spoken answer.'])
    assert window.capture_controls.preview is None and not audio['data']


def test_quit_button_and_shortcut_request_the_same_saved_shutdown(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id))
    calls=[]
    monkeypatch.setattr(manager.app,'quit',lambda:calls.append('quit'))
    settings=manager.show_dialog('Settings')
    next(button for button in settings.findChildren(QPushButton) if button.accessibleName()=='Quit the app and save only window descriptors; never replay actions').click()
    assert calls==['quit'] and manager.quitting
    manager.quitting=False
    next(action for action in window.actions() if action.shortcut().toString()=='Ctrl+Q').trigger()
    assert calls==['quit','quit'] and manager.quitting
    settings.close()


def test_chat_option_checkboxes_change_only_the_next_request_options(manager,qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    count=window.tabs.count();window.agent_loop.click();assert window.agent_loop.isChecked() and window.thinking.isEnabled()
    window.thinking.click();assert window.thinking.isChecked()
    assert not window.ask_first.isChecked()
    window.ask_first.click();assert window.ask_first.isChecked()
    window.ask_first.click();assert not window.ask_first.isChecked()
    window.use_brain.click();assert window.use_brain.isChecked()
    window.use_brain.click();assert not window.use_brain.isChecked()
    window.agent_loop.click();assert not window.agent_loop.isChecked() and not window.thinking.isChecked()
    assert window.tabs.count()==count and not window.busy and not window.current().conversation
