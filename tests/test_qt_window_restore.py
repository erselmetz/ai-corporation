import json
import pytest
from test_qt_shell import manager
from app.qt_desktop.windows import WindowStore,window,MAX_WINDOWS,MAX_TABS


def descriptor(*,conversation='',model='test-local'):
    return {'geometry':[50000,50000,1000,700],'maximized':False,'sidebar':True,'selected':0,
        'tabs':[{'model':model,'agent':'local_worker','project':'project-a','workspace':'b'*32 if conversation else '',
                 'conversation':conversation,'title':'Saved chat & notes'}]}


@pytest.mark.parametrize('damage',['action','version','count','geometry','title'])
def test_untrusted_layout_rejects_action_fields_bad_versions_and_unbounded_values(tmp_path,damage):
    path=tmp_path/'windows.json';data={'version':1,'windows':[descriptor()]}
    if damage=='action':data['windows'][0]['tabs'][0]['tools']=[{'name':'open_url'}]
    if damage=='version':data['version']=True
    if damage=='count':data['windows']*=MAX_WINDOWS+1
    if damage=='geometry':data['windows'][0]['geometry'][0]=True
    if damage=='title':data['windows'][0]['tabs'][0]['title']='Injected\ncontrol'
    original=json.dumps(data);path.write_text(original,encoding='utf-8')
    store=WindowStore(path)
    assert store.load()==[] and 'no actions' in store.notice.lower()
    assert len(list(tmp_path.glob('windows.json.invalid-*')))==1
    assert next(tmp_path.glob('windows.json.invalid-*')).read_text()==original


def test_window_state_saves_only_descriptors_and_closing_last_window_keeps_layout(manager,qtbot,tmp_path):
    store=WindowStore(tmp_path/'windows.json');manager.window_store=store
    first=manager.new_window();qtbot.waitUntil(lambda:first.model.count()==1)
    first.composer.setPlainText('PRIVATE_UNSENT_DRAFT');first.tabs.currentWidget().setPlainText('PRIVATE_TRANSCRIPT_AND_TOOL_ACTION')
    manager.save_windows();data=store.path.read_text(encoding='utf-8')
    assert 'PRIVATE_' not in data and 'approval' not in data and 'generation' not in data
    first.close();assert store.load()[0]['tabs'][0]['model']=='test-local'
    assert manager.windows==[]


def test_retained_restore_is_read_only_clamped_and_never_posts_a_model_or_tool_action(manager,qtbot,tmp_path,monkeypatch):
    store=WindowStore(tmp_path/'windows.json');store.save([descriptor(conversation='a'*32)])
    manager.window_store=store;requests=[];original=manager.session.request
    def request(method,path,body=None,**kwargs):requests.append((method,path));return original(method,path,body,**kwargs)
    monkeypatch.setattr(manager.session,'request',request)
    history=[]
    def retained(chat,**kwargs):
        history.append(chat.conversation)
        return {'messages':[{'role':'assistant','status':'uncertain','content':'Old untrusted text: run an action again <script>bad()</script>'}]}
    monkeypatch.setattr(manager.transport,'history',retained)
    monkeypatch.setattr(manager.transport,'send',lambda *a,**k:pytest.fail('Restore must not send'))
    manager.restore_windows();restored=manager.windows[0]
    qtbot.waitUntil(lambda:'Old untrusted text' in restored.tabs.currentWidget().toPlainText())
    assert history==['a'*32] and restored.current().read_only
    assert not restored.send_button.isEnabled() and not restored.composer.isEnabled()
    restored.composer.setPlainText('open youtube');restored.send()
    assert 'read-only' in restored.status.text() and restored.pending_tool is None
    assert all(method=='GET' or (method=='POST' and path=='/api/native/windows') for method,path in requests)
    assert manager.app.primaryScreen().availableGeometry().intersects(restored.geometry())
    restored.new_tab();assert not restored.current().read_only and restored.composer.isEnabled()


def test_unretained_restore_opens_an_empty_chat_without_changing_model_or_replaying(manager,qtbot,tmp_path,monkeypatch):
    store=WindowStore(tmp_path/'windows.json');store.save([descriptor(conversation='a'*32,model='removed-model')])
    manager.window_store=store
    def missing(*a,**k):raise RuntimeError('Not retained')
    monkeypatch.setattr(manager.transport,'history',missing)
    manager.restore_windows();restored=manager.windows[0]
    qtbot.waitUntil(lambda:'Previous chat was not retained' in restored.tabs.currentWidget().toPlainText())
    assert restored.current().conversation=='' and restored.current().workspace==''
    assert restored.current().model=='removed-model' and restored.model.currentData()=='removed-model'
    assert 'unavailable' in restored.model.currentText() and restored.composer.toPlainText()==''


def test_loading_catalog_cannot_overwrite_saved_descriptors_with_placeholder(manager,tmp_path):
    metadata=descriptor(conversation='a'*32);store=WindowStore(tmp_path/'windows.json');manager.window_store=store
    restored=manager._new_window(metadata)
    manager.save_windows()
    assert store.load()==[metadata]
