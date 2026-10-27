from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QInputDialog,QMessageBox,QPushButton
import app.qt_desktop.capture_controls as controls
from test_qt_shell import manager
from test_chat_images import png


def setup_capture(manager,qtbot,monkeypatch,*,approve=True):
    window=manager.new_window();qtbot.waitUntil(lambda:bool(window.native_id) and window.model.count()==1)
    calls=[];payload=bytearray(png())
    monkeypatch.setattr(controls,'available_devices',lambda kind:[('screen|identity|Test display',object())])
    monkeypatch.setattr(QInputDialog,'getItem',lambda *a,**k:('1. Test display',True))
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes if approve else QMessageBox.StandardButton.No)
    def api(chat,method,suffix='',body=None,**kwargs):
        calls.append((method,suffix,body))
        return ({'id':'lease','approval_digest':'d'*64} if not suffix else
                {'state':'active','cancelled':False} if suffix.endswith('/begin') else
                {'state':'finished','cancelled_before_finish':False})
    monkeypatch.setattr(manager.transport,'capture_api',api)
    class Adapter(QObject):
        completed=Signal(object);failed=Signal(str)
        ended=False
        def start(self,kind,target):
            calls.append(('device',kind,target));self.ended=True
            self.completed.emit({'data':payload,'kind':kind,'captured_at':'2026-10-26T00:00:00+00:00'})
        def stop(self):self.ended=True;self.failed.emit('Cancelled')
    monkeypatch.setattr(controls,'QtDeviceCapture',Adapter)
    return window,calls,payload


def test_device_opens_only_after_exact_consent_then_preview_requires_separate_transfer(manager,qtbot,monkeypatch):
    window,calls,payload=setup_capture(manager,qtbot,monkeypatch)
    transfers=[]
    def send(chat,capture,text,**kwargs):transfers.append((bytes(capture['data']),text,chat));return 'Actual test image reply'
    monkeypatch.setattr(manager.transport,'send_image',send)
    window.capture_controls.start('screen')
    qtbot.waitUntil(lambda:window.capture_controls.preview is not None)
    assert [call[1] for call in calls]==['','/lease/begin','screen','/lease/finish']
    assert calls[1][2]=={'confirmed_digest':'d'*64} and transfers==[]
    assert window.capture_controls.lease is None and not window.busy
    preview=window.capture_controls.preview
    next(b for b in preview.findChildren(QPushButton) if b.text().startswith('Send this frame once')).click()
    qtbot.waitUntil(lambda:not window.busy)
    assert len(transfers)==1 and transfers[0][0]==png() and payload==bytearray()
    assert 'Actual test image reply' in window.tabs.currentWidget().toPlainText()


def test_capture_denial_never_opens_a_device(manager,qtbot,monkeypatch):
    window,calls,payload=setup_capture(manager,qtbot,monkeypatch,approve=False)
    window.capture_controls.start('screen');qtbot.waitUntil(lambda:not window.busy)
    assert [c[1] for c in calls]==['','/lease/finish']
    assert window.capture_controls.preview is None


def test_discarded_frame_is_cleared_without_model_transfer(manager,qtbot,monkeypatch):
    window,calls,payload=setup_capture(manager,qtbot,monkeypatch)
    window.capture_controls.start('screen');qtbot.waitUntil(lambda:window.capture_controls.preview is not None)
    window.capture_controls.preview.reject()
    assert payload==bytearray() and window.capture_controls.preview is None


def test_image_preview_cannot_send_after_model_or_chat_selection_changes(manager,qtbot,monkeypatch):
    window,calls,payload=setup_capture(manager,qtbot,monkeypatch)
    transfers=[];monkeypatch.setattr(manager.transport,'send_image',lambda *a,**k:transfers.append(True))
    window.capture_controls.start('screen');qtbot.waitUntil(lambda:window.capture_controls.preview is not None)
    window.current().model='another-model'
    next(b for b in window.capture_controls.preview.findChildren(QPushButton) if b.text().startswith('Send this frame once')).click()
    assert transfers==[] and 'selection changed' in window.status.text()
    window.capture_controls.preview.reject();assert payload==bytearray()
