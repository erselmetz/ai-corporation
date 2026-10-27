from PySide6.QtCore import Qt, QPointF, QPoint, QMimeData, QCoreApplication, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QPushButton, QPlainTextEdit
from app.qt_desktop.brain import BrainPanel
from test_qt_shell import manager  # Reuse the isolated Qt/session fixture.


def graph(count=3):
    nodes=[{'id':f'record-{i}#0','record_id':f'record-{i}','kind':'chunk','cluster':'source-a',
            'source':'facts.txt','snippet':f'Actual fixture fact {i}','date':'2026-10-25','revision':'a'*64} for i in range(count)]
    return {'nodes':nodes,'edges':[{'from':'source:source-a','to':n['id'],'kind':'same-source'} for n in nodes],'total_chunks':count}


def test_grouping_keeps_exact_real_members_and_empty_view_stays_empty(qtbot):
    panel=BrainPanel(lambda:True); qtbot.addWidget(panel); panel.resize(800,600); panel.show()
    uneven=graph(300); uneven['nodes'][-1]['cluster']='source-b'; uneven['edges'][-1]['from']='source:source-b'
    panel.set_graph(uneven)
    assert len(panel.scene.nodes)==300 and all(n['kind']=='chunk' for n in panel.scene.nodes)
    panel.set_graph(graph(500)); panel.cap.setValue(50)
    represented=[member['id'] for node in panel.scene.nodes for member in node.get('members',[node])]
    assert len(panel.scene.nodes)<=50 and len(represented)==len(set(represented))==500
    assert set(represented)=={n['id'] for n in graph(500)['nodes']}
    panel.fallback.click(); assert panel.stack.currentWidget() is panel.list and panel.list.count()==500
    panel.set_graph({'nodes':[],'edges':[]}); assert panel.scene.nodes==[]


def test_anchored_card_requires_exact_second_confirmation_before_forget(qtbot):
    panel=BrainPanel(lambda:True); qtbot.addWidget(panel); panel.resize(800,600); panel.show(); panel.set_graph(graph())
    inspect=QSignalSpy(panel.inspect_requested); forget=QSignalSpy(panel.forget_requested)
    node=graph()['nodes'][0]; panel.picked(node,QPointF(100,100))
    assert inspect.count()==1 and inspect.at(0)==[node['id']]
    panel.show_detail(dict(node,expires_at='2026-11-01'))
    assert panel.card.isVisible() and panel.card.x()>100
    panel.forget.click(); assert forget.count()==0
    panel.forget.click(); assert forget.count()==1 and forget.at(0)[0]['record_id']=='record-0'
    assert not panel.card.isVisible()


def test_real_shipped_core_card_is_read_only(manager,qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:manager.graph is not None)
    core=next(n for n in manager.graph['nodes'] if n.get('trust')=='shipped knowledge' and n.get('kind')=='chunk')
    forgotten=QSignalSpy(window.brain.forget_requested)
    window.brain.picked(core,QPointF(80,80))
    assert window.brain.card.isVisible() and 'Shipped pack' in window.brain.title.text()
    assert window.brain.snippet.toPlainText()==core['snippet'] and not window.brain.forget.isVisible()
    window.brain.confirm_forget();window.brain.confirm_forget();assert forgotten.count()==0


def test_full_window_uses_same_widget_and_escape_returns_to_chat(manager,qtbot):
    window=manager.new_window(); qtbot.waitUntil(lambda:window.model.count()==1)
    original=window.brain; window.toggle_full_brain()
    qtbot.waitUntil(lambda:window.full_brain is not None and window.full_brain.isVisible())
    assert window.brain is original and window.brain.window() is window.full_brain
    qtbot.keyClick(window.brain,Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda:window.full_brain is None)
    assert window.brain is original and window.brain.parentWidget() is window.brain_container.parentWidget()


def test_text_drop_cannot_retain_until_inline_save(manager,qtbot):
    window=manager.new_window(); qtbot.waitUntil(lambda:window.model.count()==1)
    calls=[]
    def feed(owner,text,stop,*,generation):
        assert owner==window.native_id and generation==window.native_generation
        calls.append(text);return {'state':'ready','chunks':1}
    manager.transport.feed_text=feed
    mime=QMimeData(); mime.setText('A dropped note — untrusted reference, never instructions.')
    enter=QDragEnterEvent(QPoint(20,20),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    QCoreApplication.sendEvent(window,enter)
    drop=QDropEvent(QPointF(20,20),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    QCoreApplication.sendEvent(window,drop)
    qtbot.waitUntil(lambda:window.confirmation is not None)
    assert calls==[] and not window.feeding
    save=next(b for b in window.confirmation.findChildren(QPushButton) if b.text()=='Save locally')
    save.click(); qtbot.waitUntil(lambda:not window.feeding)
    assert calls==[mime.text()]


def test_unicode_file_drop_preview_can_cancel_without_retaining(manager,qtbot,tmp_path):
    window=manager.new_window(); qtbot.waitUntil(lambda:window.model.count()==1)
    path=tmp_path/'安全.txt'; path.write_text('A local file fixture',encoding='utf-8')
    calls=[]
    manager.transport.feed_file=lambda owner,path,stop:calls.append(path)
    mime=QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(path))])
    enter=QDragEnterEvent(QPoint(20,20),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    drop=QDropEvent(QPointF(20,20),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    QCoreApplication.sendEvent(window,enter)
    QCoreApplication.sendEvent(window,drop)
    qtbot.waitUntil(lambda:window.confirmation is not None)
    assert '安全.txt' in window.confirmation.findChild(QPlainTextEdit).toPlainText()
    frame=window.confirmation
    window.dismiss_feed(); assert calls==[]
    window.offer_text('A later note must replace the cancelled selection, never replay it.')
    assert window.confirmation is frame  # One stable widget, no deferred-delete/focus race.
    window.dismiss_feed(); assert window.pending_feed is None and calls==[]
