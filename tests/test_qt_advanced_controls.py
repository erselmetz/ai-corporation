"""Click every Settings/Advanced page action with a recorded local handoff."""
from PySide6.QtWidgets import QPushButton,QCheckBox
from app.api.advanced_launch import PAGES
from test_qt_shell import manager


def test_every_advanced_and_settings_page_button_has_one_working_handoff(manager,qtbot,monkeypatch):
    requests=[];opened=[];original=manager.session.request
    def request(method,path,body=None,**kwargs):
        if path=='/api/local/advanced-launch':
            assert method=='POST' and set(body)=={'page'} and body['page'] in PAGES
            requests.append(body['page']);return {'url':'http://127.0.0.1:8000/ui/advanced-launch?ticket=qa-only'}
        return original(method,path,body,**kwargs)
    monkeypatch.setattr(manager.session,'request',request)
    manager.browser_open=lambda url,**kwargs:opened.append(url) or True
    for kind in ['Settings','Advanced']:
        dialog=manager.show_dialog(kind)
        page_buttons=[button for button in dialog.findChildren(QPushButton) if button.text() in PAGES]
        assert len(page_buttons)==(7 if kind=='Settings' else len(PAGES))
        for button in page_buttons:
            before=len(opened);button.click()
            qtbot.waitUntil(lambda:len(opened)==before+1)
            assert requests[-1]==button.text() and button.accessibleName()
        dialog.findChildren(QPushButton)[-1].click();assert not dialog.isVisible()
    assert len(opened)==len(PAGES)+7


def test_theme_and_motion_controls_change_and_persist_actual_preferences(manager,qtbot):
    dialog=manager.show_dialog('Settings')
    boxes={box.text():box for box in dialog.findChildren(QCheckBox)}
    before=manager.app.styleSheet();light=boxes['Light theme'];light.click()
    assert manager.app.styleSheet()!=before
    assert manager.preferences.value('lightTheme',False,type=bool)==light.isChecked()
    motion=boxes['Reduce motion'];motion.click()
    assert manager.reduced_motion==motion.isChecked()==manager.preferences.value('reducedMotion',False,type=bool)
