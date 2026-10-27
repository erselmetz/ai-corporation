from PySide6.QtWidgets import QPushButton
from test_qt_shell import manager


def test_private_brain_excerpts_require_review_before_chat_submission(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    previews=[];sent=[]
    def preview(chat,text,**kwargs):
        previews.append(text);return {'digest':'d'*64,'items':[{'source':'Owner note','content':'A private reference fact.'}],
                                    'trace':{'mode':'semantic-only'}}
    def send(chat,text,stop,emit,**kwargs):sent.append((text,kwargs));emit({'type':'chunk','text':'A cited answer [1].'})
    monkeypatch.setattr(manager.transport,'preview_knowledge',preview);monkeypatch.setattr(manager.transport,'send',send)
    window.use_brain.setChecked(True);window.composer.setPlainText('What is the private reference fact?');window.send()
    qtbot.waitUntil(lambda:window.knowledge_review.dialog is not None)
    assert sent==[] and previews==['What is the private reference fact?']
    next(b for b in window.knowledge_review.dialog.findChildren(QPushButton) if b.text()=='Use these sources for this message').click()
    qtbot.waitUntil(lambda:not window.busy)
    assert sent[0][1]['knowledge']=={'knowledge_enabled':True,'knowledge_scopes':[{'scope':'owner','scope_id':''}],'knowledge_preview_digest':'d'*64}


def test_cancelled_brain_preview_keeps_the_unsent_message(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    monkeypatch.setattr(manager.transport,'preview_knowledge',lambda *a,**k:{'digest':'d'*64,'items':[],'trace':{'mode':'lexical-only'}})
    window.use_brain.setChecked(True);window.composer.setPlainText('Keep this as a draft');window.send()
    qtbot.waitUntil(lambda:window.knowledge_review.dialog is not None);window.knowledge_review.dialog.reject()
    assert not window.busy and window.composer.toPlainText()=='Keep this as a draft'
