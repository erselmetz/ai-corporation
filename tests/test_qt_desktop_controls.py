from PySide6.QtWidgets import QMessageBox
from test_qt_shell import manager


def test_desktop_review_sends_exact_text_only_after_approval_and_stop_closes_dialog(manager,qtbot,monkeypatch):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    calls=[];original=manager.session.request
    target={'process_id':12,'window_handle':34,'process_name':'fixture.exe','window_title':'Owned fixture'}
    control={'automation_id':'input','control_name':'Public draft','action':'fill_text'}
    def request(method,path,body=None,**kwargs):
        calls.append((method,path,body,kwargs))
        if path.endswith('/desktop/process'):return {}
        if path.endswith('/desktop/windows'):return {'items':[target]}
        if path.endswith('/desktop/controls'):return {'items':[control]}
        if path.endswith('/desktop/request-approval'):return {'approval':{'approval_id':'a'*32,'approval_digest':'d'*64}}
        if path.endswith('/approve'):return {'status':'approved'}
        if path.endswith('/desktop/execute'):return {'status':'action_dispatched','remote_outcome':'unknown'}
        return original(method,path,body,**kwargs)
    monkeypatch.setattr(manager.session,'request',request)
    ui=window.desktop_controls;ui.show();ui.process.setText('fixture.exe');ui.allow.click()
    qtbot.waitUntil(lambda:ui.windows.count()==1 and not ui.pending)
    ui.inspect.click();qtbot.waitUntil(lambda:ui.controls.count()==1 and not ui.pending)
    assert not any(path.endswith('/desktop/execute') for _,path,_,_ in calls)
    monkeypatch.setattr(QMessageBox,'exec',lambda self:QMessageBox.StandardButton.Yes)
    ui.value.setText('Exact reviewed Taglish — kumusta');ui.review.click()
    qtbot.waitUntil(lambda:any(path.endswith('/desktop/execute') for _,path,_,_ in calls) and not ui.pending)
    executed=next(item for item in calls if item[1].endswith('/desktop/execute'))
    assert executed[2]==dict(target,**control,value='Exact reviewed Taglish — kumusta',approval_id='a'*32)
    assert executed[3]=={'window':window.native_id,'generation':window.native_generation}
    assert 'unverified' in ui.status.text()
    window.stop_window(force=True);assert ui.dialog is None
