from test_qt_shell import manager


def test_checked_private_brain_is_used_without_a_second_approval(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    window.agent_loop.setChecked(False)  # This regression exercises the explicit direct-chat path.
    previews=[];sent=[]
    def preview(chat,text,**kwargs):
        previews.append(text);return {'digest':'d'*64,'items':[{'source':'Owner note','content':'A private reference fact.'}],
                                    'trace':{'mode':'semantic-only'}}
    def send(chat,text,stop,emit,**kwargs):sent.append((text,kwargs));emit({'type':'chunk','text':'A cited answer [1].'})
    monkeypatch.setattr(manager.transport,'preview_knowledge',preview);monkeypatch.setattr(manager.transport,'send',send)
    window.use_brain.setChecked(True);window.composer.setPlainText('What is the private reference fact?');window.send()
    qtbot.waitUntil(lambda:not window.busy)
    assert previews==['What is the private reference fact?']
    assert sent[0][1]['knowledge']=={'knowledge_enabled':True,'knowledge_scopes':[{'scope':'owner','scope_id':''}],'knowledge_preview_digest':'d'*64}


def test_changed_message_cancels_automatic_brain_submission(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    def preview(*args,**kwargs):
        window.composer.setPlainText('Changed draft')
        return {'digest':'d'*64,'items':[],'trace':{'mode':'lexical-only'}}
    sent=[]
    monkeypatch.setattr(manager.transport,'preview_knowledge',preview)
    monkeypatch.setattr(manager.transport,'send',lambda *args,**kwargs:sent.append(args))
    window.use_brain.setChecked(True);window.composer.setPlainText('Keep this as a draft');window.send()
    qtbot.waitUntil(lambda:not window.busy)
    assert sent==[] and window.composer.toPlainText()=='Changed draft'


def test_opted_in_chat_learning_saves_only_explicit_owner_fact_after_success(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    window.agent_loop.setChecked(False);window.learn_chat.setChecked(True)
    saved=[]
    monkeypatch.setattr(manager.transport,'send',lambda chat,text,stop,emit,**kwargs:emit({'type':'chunk','text':'Okay.'}))
    monkeypatch.setattr(manager.transport,'remember_owner_fact',lambda text:saved.append(text) or {'id':'memory'})
    window.composer.setPlainText('Remember that my preferred editor is VS Code');window.send()
    qtbot.waitUntil(lambda:bool(saved))
    assert saved==['Remember that my preferred editor is VS Code']
    window.composer.setPlainText('hello');window.send();qtbot.waitUntil(lambda:not window.busy)
    assert saved==['Remember that my preferred editor is VS Code']
