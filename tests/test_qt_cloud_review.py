import httpx,json
from PySide6.QtWidgets import QPushButton,QPlainTextEdit
from test_qt_shell import manager


def wire(manager,qtbot,fail_message=None):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    window.composer.setPlainText('Explain the selected design')
    current=window.current();current.workspace='a'*32;current.conversation='b'*32
    calls=[];session=manager.session;original=session.request
    session.credentials={'csrf':'fixture'}
    def request(method,path,body=None,**kwargs):
        if path=='/api/local/provider-connections':return {'items':[{'provider_id':'compatible-free-pool','provider_type':'openai-compatible','state':'available','models':['auto'],'endpoint':{'enabled':True,'default_model':'auto'}}]}
        return original(method,path,body,**kwargs)
    session.request=request
    def handle(request):
        assert request.headers['X-Native-Window']==window.native_id
        assert request.headers['X-Native-Generation']==str(window.native_generation)
        if request.method=='GET':return httpx.Response(200,json={'workspace':{}})
        body=json.loads(request.content);calls.append(body)
        if body.get('outbound_preview'):
            return httpx.Response(409,json={'detail':{'kind':'outbound_preview','digest':'c'*64,'warning':'Your prompt may be sent to any provider enabled in that router.','destination':'http://127.0.0.1:3001/v1','requested_model':'auto','messages':[{'role':'user','content':body['text']}]}})
        assert body['cloud_consent'] is True and body['outbound_digest']=='c'*64
        if fail_message:return httpx.Response(422,json={'detail':{'state':'Key rejected','message':fail_message}})
        return httpx.Response(200,json={'conversation':{'messages':[{'role':'assistant','content':'Verified fake cloud answer'}]},'context_trace':{'endpoint':{'served_provider':'fake','served_model':'served','latency_ms':2,'retries':0}}})
    session.client=httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(handle))
    return window,calls


def test_cloud_preview_cancel_then_approve_is_one_turn_without_route_mutation(manager,qtbot):
    window,calls=wire(manager,qtbot);chat=window.current();original=(chat.model,chat.agent,chat.project,chat.workspace)
    button=next(b for b in window.findChildren(QPushButton) if b.text()=='Ask the free pool?')
    assert calls==[]
    button.click();qtbot.waitUntil(lambda:window.cloud_review.dialog is not None)
    dialog=window.cloud_review.dialog
    assert 'Explain the selected design' in dialog.findChild(QPlainTextEdit).toPlainText()
    next(b for b in dialog.findChildren(QPushButton) if b.text()=='Cancel cloud turn').click()
    assert len(calls)==1 and calls[0]['outbound_preview'] is True
    assert 'Cloud turn cancelled' in window.status.text()
    button.click();qtbot.waitUntil(lambda:window.cloud_review.dialog is not None)
    dialog=window.cloud_review.dialog
    next(b for b in dialog.findChildren(QPushButton) if b.text()=='Approve this cloud turn').click()
    qtbot.waitUntil(lambda:not window.busy)
    assert len(calls)==3 and not calls[-1]['outbound_preview']
    assert (chat.model,chat.agent,chat.project,chat.workspace)==original
    assert 'Verified fake cloud answer' in window.tabs.currentWidget().toPlainText()
    assert 'local model is still the default' in window.status.text()
    assert window.composer.toPlainText()==''
    assert any('Router-reported fake / served' in window.steps.item(i).text() for i in range(window.steps.count()))
    manager.session.client.close()


def test_stop_or_generation_change_invalidates_pending_cloud_approval(manager,qtbot):
    window,calls=wire(manager,qtbot)
    window.cloud_review.prepare();qtbot.waitUntil(lambda:window.cloud_review.dialog is not None)
    window.native_generation+=1
    window.cloud_review.approve()
    assert window.cloud_review.dialog is None and len(calls)==1
    window.pending_stop=True;window.cloud_review.prepare();qtbot.wait(50)
    assert len(calls)==1 and not window.busy
    manager.session.client.close()


def test_last_question_is_per_chat_and_never_part_of_saved_descriptors(manager,qtbot):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    first=window.current();first.last_local_prompt='Private question from only the first tab'
    window.new_tab();assert window.current().last_local_prompt==''
    assert first.last_local_prompt not in json.dumps(window.descriptor())


def test_cloud_error_is_friendly_and_does_not_retry(manager,qtbot):
    window,calls=wire(manager,qtbot,'The endpoint rejected the key. Check its API access settings.')
    window.cloud_review.prepare();qtbot.waitUntil(lambda:window.cloud_review.dialog is not None)
    window.cloud_review.approve();qtbot.waitUntil(lambda:not window.busy)
    assert 'rejected the key' in window.status.text()
    assert len(calls)==2 and window.response_error and window.current().model=='test-local'
    manager.session.client.close()
