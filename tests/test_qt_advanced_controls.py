"""Click every Settings/Advanced page action with a recorded local handoff."""
from PySide6.QtWidgets import QPushButton,QCheckBox
from app.qt_desktop.pages import PAGES
from test_qt_shell import manager


def test_every_advanced_and_settings_page_button_has_one_working_handoff(manager,qtbot,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('App navigation opened an external surface')
    import webbrowser,os
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(webbrowser,'open',forbidden)
    monkeypatch.setattr(os,'startfile',forbidden,raising=False)
    monkeypatch.setattr(QDesktopServices,'openUrl',forbidden)
    manager.browser_open=forbidden
    for kind in ['Settings','Advanced']:
        dialog=manager.show_dialog(kind)
        page_buttons=[b for b in dialog.findChildren(QPushButton) if b.text() in PAGES]
        assert len(page_buttons)==(7 if kind=='Settings' else len(PAGES))
        for b in page_buttons:
            b.click();native=manager.dialogs['Page: '+b.text()]
            assert native.isVisible() and native.isWindow() and b.accessibleName()
            assert manager.open_page(b.text(),dialog.findChildren(__import__('PySide6.QtWidgets',fromlist=['QLabel']).QLabel)[0]) is native
        dialog.close()
    calls=[];manager.browser_open=lambda *a,**k:calls.append(a)
    manager.open_online_docs();assert calls==[('https://ai.erselmetz.com',)]


def test_theme_and_motion_controls_change_and_persist_actual_preferences(manager,qtbot):
    dialog=manager.show_dialog('Settings')
    boxes={box.text():box for box in dialog.findChildren(QCheckBox)}
    before=manager.app.styleSheet();light=boxes['Light theme'];light.click()
    assert manager.app.styleSheet()!=before
    assert manager.preferences.value('lightTheme',False,type=bool)==light.isChecked()
    motion=boxes['Reduce motion'];motion.click()
    assert manager.reduced_motion==motion.isChecked()==manager.preferences.value('reducedMotion',False,type=bool)
