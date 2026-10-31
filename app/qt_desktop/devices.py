"""One-shot Qt device adapters; callers must obtain an exact backend lease first.

No recording files, network calls, automatic device fallback or model transfers.
"""
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import wave
from PySide6.QtCore import QObject,Signal,QTimer,QBuffer,QIODevice,Qt
from PySide6.QtGui import QGuiApplication,QImage


def descriptor(kind,key,label):return kind+'|'+sha256(key).hexdigest()+'|'+label[:180]


def available_devices(kind):
    if kind=='screen':
        return [(descriptor(kind,(s.name()+str(s.geometry())+str(s.devicePixelRatio())).encode(),s.name()),s)
                for s in QGuiApplication.screens()]
    from PySide6.QtMultimedia import QMediaDevices
    devices=QMediaDevices.videoInputs() if kind=='camera' else QMediaDevices.audioInputs()
    return [(descriptor(kind,bytes(d.id()),d.description()),d) for d in devices]


def png_image(image):
    if image.isNull():raise ValueError('The device did not return an image.')
    image=image.scaled(1280,720,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
    # Copy pixels into a fresh image so source metadata is not retained.
    clean=QImage(image.size(),QImage.Format.Format_RGB32);clean.fill(Qt.GlobalColor.black)
    from PySide6.QtGui import QPainter
    painter=QPainter(clean);painter.drawImage(0,0,image);painter.end()
    buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not clean.save(buffer,'PNG'):raise ValueError('The image could not be prepared locally.')
    data=bytearray(buffer.data());buffer.close()
    if len(data)>2*1024*1024:raise ValueError('The captured image exceeds the two MB limit.')
    return data


class QtDeviceCapture(QObject):
    completed=Signal(object)
    failed=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent);self.camera=None;self.audio=None;self.session=None;self.image_capture=None
        self.result=None;self.error='';self.ended=False;self.capturing=False;self.pcm=bytearray();self.input=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)

    def start(self,kind,target):
        if kind not in {'screen','camera','microphone'}:raise ValueError('Unsupported capture kind.')
        if self.capturing or self.ended:raise ValueError('A capture adapter can only be used once.')
        self.kind=kind;self.target=target;self.capturing=True
        selected=[d for text,d in available_devices(kind) if text==target]
        if len(selected)!=1:self.stop('The approved device changed or is unavailable. No substitute was used.');return
        device=selected[0]
        try:
            if kind=='screen':
                self.result={'data':png_image(device.grabWindow(0).toImage()),'kind':kind,'captured_at':datetime.now(timezone.utc).isoformat()}
                self.stopped();return
            from PySide6.QtMultimedia import QCamera,QMediaCaptureSession,QImageCapture,QAudioSource,QAudioFormat
            if kind=='camera':
                self.session=QMediaCaptureSession(self);self.camera=QCamera(device,self)
                self.image_capture=QImageCapture(self);self.session.setCamera(self.camera);self.session.setImageCapture(self.image_capture)
                self.image_capture.readyForCaptureChanged.connect(self.camera_ready)
                self.image_capture.imageCaptured.connect(self.camera_image)
                self.image_capture.errorOccurred.connect(lambda *args:self.stop('The camera could not return a frame.'))
                self.camera.errorOccurred.connect(lambda *args:self.stop('Camera access failed or was denied.'))
                self.camera.activeChanged.connect(lambda active:self.stopped() if not active and (self.error or self.result is not None) else None)
                self.timer.start(10000);self.camera.start()
            else:
                fmt=QAudioFormat();fmt.setSampleRate(16000);fmt.setChannelCount(1);fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
                if not device.isFormatSupported(fmt):raise ValueError('This microphone does not support mono 16 kHz PCM. No alternate device was used.')
                self.audio=QAudioSource(device,fmt,self);self.input=self.audio.start()
                if self.input is None:raise ValueError('Microphone access failed or was denied.')
                self.input.readyRead.connect(self.audio_ready);self.timer.start(10000)
        except Exception as error:
            self.stop(str(error) if isinstance(error,ValueError) else 'The device could not start. No capture was transferred.')

    def camera_ready(self,ready):
        if ready and not self.ended and not self.error and not getattr(self,'requested_image',False):
            self.requested_image=True;self.image_capture.capture()  # QImage only; never captureToFile.

    def camera_image(self,_identifier,image):
        if self.ended or self.error:return
        try:self.result={'data':png_image(image),'kind':'camera','captured_at':datetime.now(timezone.utc).isoformat()}
        except ValueError as error:self.error=str(error)
        self.camera.stop()
        if not self.camera.isActive():self.stopped()

    def audio_ready(self):
        if self.ended or self.error:return
        maximum=320000
        data=bytes(self.input.read(min(8192,maximum-len(self.pcm))))
        self.pcm.extend(data)
        if len(self.pcm)>=maximum:self.timeout()

    def timeout(self):
        if self.kind!='microphone':self.stop('The camera did not return a frame before its deadline.');return
        self.finish_microphone()

    def finish_microphone(self):
        """Finish the current recording now and retain its bounded PCM as one WAV."""
        if self.ended or self.kind!='microphone':return
        if not self.pcm:self.stop('No microphone audio was received.');return
        self.audio.stop()
        stream=BytesIO()
        with wave.open(stream,'wb') as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000)
            output.writeframes(bytes(self.pcm[:len(self.pcm)//2*2]))
        self.result={'data':bytearray(stream.getvalue()),'kind':'microphone'};self.stopped()

    def stop(self,message='Capture cancelled. Nothing was transferred.'):
        if self.ended:return
        self.error=message
        if self.result is not None and isinstance(self.result.get('data'),bytearray):
            payload=self.result['data'];payload[:]=b'\0'*len(payload);payload.clear()
        self.result=None;self.timer.stop()
        if self.audio is not None:self.audio.stop()
        if self.camera is not None:
            self.camera.stop()
            if self.camera.isActive():return  # Retain ownership until the stop notification.
        self.stopped()

    def stopped(self):
        if self.ended:return
        self.ended=True;self.capturing=False;self.timer.stop()
        self.pcm[:]=b'\0'*len(self.pcm);self.pcm.clear()
        if self.error:self.failed.emit(self.error)
        elif self.result is not None:self.completed.emit(self.result)
        else:self.failed.emit('Capture ended without verified device data.')
        self.result=None
        self.deleteLater()  # Release Qt's image/device objects after actual stop.
