"""Native navigation/actions replace app-page browser handoffs."""
import pytest
from PySide6.QtWidgets import QPushButton,QLineEdit,QCheckBox,QDialog
from app.qt_desktop.page_schema import PAGES
from app.qt_desktop.native_pages import RecordWindow,Fields,OfflineText
from test_qt_shell import manager

def test_all_native_records_search_details_actions_cancel_and_singleton(manager,qtbot,monkeypatch):
    calls=[]
    def request(method,path,body=None,**kw):
        calls.append((method,path,body))
        if method!='GET':raise AssertionError('Cancel must not submit an action')
        return {'items':[{'id':'sample','name':'Mahabang Taglish na pangalan para hindi masira ang layout','status':'ready','content':'# Offline document\nOwner scoped content.'}]}
    monkeypatch.setattr(manager.session,'request',request)
    status=__import__('PySide6.QtWidgets',fromlist=['QLabel']).QLabel()
    for title,spec in PAGES.items():
        window=manager.open_page(title,status);qtbot.waitUntil(lambda:not window.loading)
        assert isinstance(window,RecordWindow) and window is manager.open_page(title,status)
        assert window.isWindow() and window.table.rowCount()==1
        window.search.setText('not present');assert window.table.isRowHidden(0)
        window.search.clear();assert not window.table.isRowHidden(0)
        for action,b in zip(spec.actions,window.action_buttons):
            b.click();dialog=window.action_dialog
            assert dialog.isVisible()
            submit=next(x for x in dialog.findChildren(QPushButton) if x.text()=='Confirm action')
            assert not submit.isEnabled()
            next(x for x in dialog.findChildren(QPushButton) if x.text()=='Cancel').click()
            assert not dialog.isVisible()
        assert all(b.accessibleName() for b in window.findChildren(QPushButton))
        window.close()
    assert all(method=='GET' for method,path,body in calls)

def test_typed_native_action_requires_confirmation_and_clears_secret(manager,qtbot,monkeypatch):
    calls=[]
    def request(method,path,body=None,**kwargs):
        calls.append((method,path,body));return {'items':[]}
    monkeypatch.setattr(manager.session,'request',request)
    window=RecordWindow(manager,'Providers');qtbot.addWidget(window);window.show();qtbot.waitUntil(lambda:not window.loading)
    action=next(a for a in window.page.actions if a.title=='Add Free pool');window.action(action)
    d=window.action_dialog;fields=d.findChild(Fields)
    assert fields.values()['preset'] is True and fields.values()['enabled'] is False and fields.values()['allow_brain_context'] is False
    fields.entries['id'][0].setText('free');fields.entries['api_key'][0].setText('PRIVATE_KEY')
    submit=next(x for x in d.findChildren(QPushButton) if x.text()=='Confirm action')
    assert not submit.isEnabled()
    next(x for x in d.findChildren(QCheckBox) if x.text().startswith('I reviewed')).click();submit.click()
    qtbot.waitUntil(lambda:not d.isVisible())
    post=next(x for x in calls if x[0]=='POST');assert post[1].endswith('/openai-compatible') and post[2]['api_key']=='PRIVATE_KEY'
    assert fields.entries['api_key'][0].text()==''
    assert 'PRIVATE_KEY' not in window.detail.toPlainText()

def test_offline_markdown_never_loads_external_resources(qapp):
    w=OfflineText();w.setMarkdown('# Local\n![remote](https://example.invalid/pixel)\n[link](https://example.invalid)')
    assert not w.openExternalLinks() and not w.openLinks()
    assert w.loadResource(2,__import__('PySide6.QtCore',fromlist=['QUrl']).QUrl('https://example.invalid/pixel')) is None

def test_dedicated_backup_and_owner_windows(manager,qtbot):
    from PySide6.QtWidgets import QLabel
    from app.qt_desktop.native_pages import BackupWindow,OwnerWindow
    for title,cls in [('Backup',BackupWindow),('Owner sign-in',OwnerWindow)]:
        window=manager.open_page(title,QLabel());assert isinstance(window,cls)
        assert window is manager.open_page(title,QLabel())
        assert all(x.accessibleName() for x in window.findChildren(QPushButton)+window.findChildren(QLineEdit))
        window.close()


def test_backup_restore_requires_inspected_unchanged_bytes(manager,qtbot,monkeypatch,tmp_path):
    import httpx
    from app.qt_desktop.native_pages import BackupWindow
    from PySide6.QtWidgets import QFileDialog
    requests=[]
    def handle(request):
        requests.append(request.url.path);return httpx.Response(200,json={'summary':'Inspected encrypted backup fixture'})
    manager.session.client=httpx.Client(transport=httpx.MockTransport(handle),base_url='http://127.0.0.1:1')
    manager.session.credentials={'csrf':'test-token'}
    path=tmp_path/'sample.erselbackup';path.write_bytes(b'encrypted fixture')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    window=BackupWindow(manager);qtbot.addWidget(window)
    try:
        window.confirm.setText('RESTORE');window.upload(True)
        assert requests==[] and 'Inspect' in window.status.text()
        window.password.setText('long fixture passphrase');window.upload(False)
        qtbot.waitUntil(lambda:window.inspected is not None)
        assert requests==['/api/local/backup/inspect'] and window.password.text()==''
        path.write_bytes(b'changed encrypted fixture');window.password.setText('long fixture passphrase');window.upload(True)
        qtbot.waitUntil(lambda:'changed after inspection' in window.status.text())
        assert requests==['/api/local/backup/inspect']
    finally:manager.session.client.close()


def test_action_failure_result_survives_inventory_refresh(manager,qtbot,monkeypatch):
    def request(method,path,body=None,**kwargs):
        if method=='GET':return {'items':[{'pack_id':'voice','title':'Voice','state':'installed'},{'pack_id':'eyes','title':'Eyes','state':'installed'}]}
        assert path=='/api/capability-packs/eyes/self-test'
        return {'pack_id':'eyes','state':'failed','detail':'The software self-test failed; inventory installation is not proof of working.'}
    monkeypatch.setattr(manager.session,'request',request)
    window=RecordWindow(manager,'Privacy and capabilities');qtbot.addWidget(window);window.show();qtbot.waitUntil(lambda:not window.loading)
    window.table.selectRow(1)
    action=next(a for a in window.page.actions if a.title=='Self-test pack');window.action(action)
    dialog=window.action_dialog
    next(w for w in dialog.findChildren(QCheckBox) if w.text().startswith('I reviewed')).click()
    next(w for w in dialog.findChildren(QPushButton) if w.text()=='Confirm action').click()
    qtbot.waitUntil(lambda:not dialog.isVisible() and not window.loading)
    assert window.selected['id']=='eyes'
    assert 'software self-test failed' in window.detail.toPlainText()
    assert window.status.text()=='Result: failed'
