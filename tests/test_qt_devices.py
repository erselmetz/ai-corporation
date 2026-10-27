from io import BytesIO
import wave
import pytest
from PySide6.QtGui import QImage,QColor,QPixmap
from app.qt_desktop.devices import QtDeviceCapture,png_image


def test_one_screen_frame_is_bounded_and_metadata_is_removed(qapp,monkeypatch):
    image=QImage(16,12,QImage.Format.Format_RGB32);image.fill(QColor('red'));image.setText('location','private metadata')
    encoded=png_image(image);decoded=QImage.fromData(bytes(encoded),'PNG')
    assert not decoded.isNull() and not decoded.textKeys() and b'private metadata' not in encoded
    class Screen:
        calls=0
        def grabWindow(self,identifier):self.calls+=1;assert identifier==0;return QPixmap.fromImage(image)
    screen=Screen();monkeypatch.setattr('app.qt_desktop.devices.available_devices',lambda kind:[('exact-screen',screen)])
    capture=QtDeviceCapture();results=[];capture.completed.connect(results.append)
    assert screen.calls==0
    capture.start('screen','exact-screen')
    assert screen.calls==1 and len(results)==1 and results[0]['kind']=='screen'
    with pytest.raises(ValueError):capture.start('screen','exact-screen')


def test_missing_approved_device_never_substitutes_another(qapp,monkeypatch):
    monkeypatch.setattr('app.qt_desktop.devices.available_devices',lambda kind:[])
    capture=QtDeviceCapture();errors=[];results=[];capture.failed.connect(errors.append);capture.completed.connect(results.append)
    capture.start('camera','missing-camera')
    assert capture.ended and results==[] and 'No substitute' in errors[0]


def test_microphone_result_is_pcm_wav_and_owned_pcm_is_cleared(qapp):
    class Audio:
        stopped=False
        def stop(self):self.stopped=True
    capture=QtDeviceCapture();capture.kind='microphone';capture.audio=Audio();capture.pcm=bytearray(b'\0'*32000)
    results=[];capture.completed.connect(results.append);capture.timeout()
    assert capture.audio.stopped and capture.pcm==bytearray()
    with wave.open(BytesIO(results[0]['data']),'rb') as audio:
        assert (audio.getframerate(),audio.getnchannels(),audio.getsampwidth(),audio.getnframes())==(16000,1,2,16000)


def test_camera_stop_waits_for_actual_inactive_state_before_completion(qapp):
    class Camera:
        active=True
        stop_requested=False
        def stop(self):self.stop_requested=True
        def isActive(self):return self.active
    capture=QtDeviceCapture();capture.kind='camera';capture.camera=Camera();capture.capturing=True
    errors=[];capture.failed.connect(errors.append);capture.stop()
    assert capture.camera.stop_requested and not capture.ended and errors==[]
    capture.camera.active=False;capture.stopped()
    assert capture.ended and len(errors)==1
