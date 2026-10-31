"""Native exact-consent capture, local preview and separately approved transfers."""
from PySide6.QtCore import QObject,Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QInputDialog,QMessageBox,QDialog,QVBoxLayout,QLabel,QPushButton,QPlainTextEdit
from .devices import QtDeviceCapture,available_devices


def wipe(value):
    if isinstance(value,bytearray):value[:]=b'\0'*len(value);value.clear()


class CaptureControls(QObject):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.adapter=None;self.lease=None;self.chat=None;self.preview=None;self.preparing=False
        self.direct_voice=False

    def api(self,method,suffix='',body=None):
        w=self.window
        return w.manager.transport.capture_api(self.chat,method,suffix,body,generation=w.native_generation)

    def toggle_voice(self):
        if self.adapter is not None and not self.adapter.ended and self.direct_voice:
            self.window.status.setText('Finishing your voice message locally…')
            self.adapter.finish_microphone();return
        self.start('microphone',direct=True)

    def start(self,kind,direct=False):
        w=self.window
        if w.busy or w.feeding or w.window_stopped or w.global_stopped or not w.native_id:return
        if w.current().read_only:w.status.setText('Open a new chat before capturing; restored history is read-only.');return
        if self.preview is not None:w.status.setText('Finish reviewing the previous capture first.');return
        if self.lease is not None:w.status.setText('Release the previous capture before starting another.');return
        try:devices=available_devices(kind)
        except ImportError:w.status.setText('Qt Multimedia is unavailable. Install the Python desktop requirements before using devices.');return
        if not devices:w.status.setText('No supported '+kind+' device is available.');return
        labels=[str(i+1)+'. '+text.split('|',2)[-1] for i,(text,_) in enumerate(devices)]
        if direct:
            selected=labels[0]
        else:
            selected,accepted=QInputDialog.getItem(w,'Choose one '+kind,'Capture once from:',labels,0,False)
            if not accepted:return
        target=devices[labels.index(selected)][0];self.chat=w.current();self.direct_voice=bool(direct);w.stop_event.clear();w.busy=True;self.preparing=True
        if direct and hasattr(w,'voice_button'):w.voice_button.setText('Preparing mic…')
        w.release_capture_button.setEnabled(True)
        for widget in [w.tabs,w.model,w.agent,w.project,w.send_button]:widget.setEnabled(False)
        def prepare():
            if kind=='microphone' and w.manager.session.request('GET','/api/local/voice')['local_speech']['state']!='ready':
                raise ValueError('Configure the local Ears runtime and an installed Whisper model in Advanced first. Nothing was recorded.')
            return self.api('POST',body={'kind':kind,'target':target})
        def review(result):
            self.preparing=False;self.lease=result['id']
            if w.stop_event.is_set() or w.window_stopped or w.global_stopped:self.release(None);return
            description=('Record at most ten seconds and transcribe on this PC. You review the draft before using it.' if kind=='microphone'
                         else 'Capture one frame locally. You preview it before any model transfer.')
            answer=(QMessageBox.StandardButton.Yes if direct else QMessageBox.question(w,'Approve one '+kind+' capture',selected+'\n\n'+description,
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No))
            if answer!=QMessageBox.StandardButton.Yes or w.stop_event.is_set() or w.window_stopped or w.global_stopped:
                self.release(None);return
            def begun(state):
                if state.get('cancelled') or w.stop_event.is_set() or w.window_stopped or w.global_stopped:
                    self.release(None);return
                self.adapter=QtDeviceCapture(w);self.adapter.completed.connect(self.release)
                self.adapter.failed.connect(self.device_failed)
                w.status.setText(('Listening locally · press Stop & send when finished.' if direct else
                                  'Using '+kind+' here · Stop ends this capture · nothing has been sent to a model.'))
                if direct and hasattr(w,'voice_button'):w.voice_button.setText('■ Stop & send')
                try:self.adapter.start(kind,target)
                except Exception:self.device_failed('The approved device could not start. No substitute was used.')
            w.manager.submit(lambda:self.api('POST','/'+self.lease+'/begin',{'confirmed_digest':result['approval_digest']}),begun,self.begin_failed,control=True)
        w.status.setText('Preparing exact device consent. No device has opened.')
        w.manager.submit(prepare,review,lambda error:self.initial_failed(str(error)))

    def initial_failed(self,message):
        self.preparing=False
        self.direct_voice=False
        if hasattr(self.window,'voice_button'):self.window.voice_button.setText('🎙 Speak')
        self.window.release_capture_button.setEnabled(False)
        self.window.done();self.window.status.setText(message[:300])

    def begin_failed(self,error):
        self.window.status.setText('Capture permission was not confirmed. No device was opened. Releasing its review…')
        self.release(None)

    def device_failed(self,message):
        self.direct_voice=False
        if hasattr(self.window,'voice_button'):self.window.voice_button.setText('🎙 Speak')
        self.window.status.setText(message);self.release(None)

    def release(self,result=None):
        w=self.window
        if self.lease is None:
            if result:wipe(result.get('data'))
            return
        identifier=self.lease
        def released(state):
            self.lease=None
            w.release_capture_button.setEnabled(False)
            if self.adapter:self.adapter.deleteLater();self.adapter=None
            if hasattr(w,'voice_button'):w.voice_button.setText('🎙 Speak')
            w.done(cancelled=w.stop_event.is_set())
            if result is None:
                self.direct_voice=False;return
            if state.get('cancelled_before_finish') or w.stop_event.is_set() or w.global_stopped or w.window_stopped:
                wipe(result.get('data'));w.status.setText('Capture ended after Stop; no data was transferred.');return
            if result['kind']=='microphone':self.transcribe(result,direct=self.direct_voice)
            else:self.show_image(result)
            self.direct_voice=False
        def failed(error):
            if result:wipe(result.get('data'))
            self.direct_voice=False
            if hasattr(w,'voice_button'):w.voice_button.setText('🎙 Speak')
            w.done();w.status.setText('Device capture ended; backend release was not confirmed. Use Release capture before another capture.')
        w.manager.submit(lambda:self.api('POST','/'+identifier+'/finish'),released,failed,control=True)

    def stop(self):
        if self.preview:self.preview.reject()
        if self.adapter and not self.adapter.ended:self.adapter.stop()

    def retry_release(self):
        if self.window.busy and (self.lease is not None or self.preparing):
            self.window.stop_window(force=True)
            return
        if self.lease is None:self.window.status.setText('No capture is awaiting release.');return
        self.release(None)

    def show_image(self,result):
        w=self.window;chat=self.chat;selection=(chat.model,chat.agent,chat.project)
        dialog=QDialog(w);self.preview=dialog;dialog.setWindowTitle('Local capture preview · not sent')
        layout=QVBoxLayout(dialog);explanation=QLabel('This frame stays local unless you approve one transfer to the selected local model.');explanation.setWordWrap(True);layout.addWidget(explanation)
        picture=QLabel();picture.setAccessibleName('Captured frame preview');pixmap=QPixmap();pixmap.loadFromData(bytes(result['data']))
        picture.setPixmap(pixmap.scaled(640,400,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));layout.addWidget(picture)
        prompt=QPlainTextEdit();prompt.setAccessibleName('Question about this frame');prompt.setPlainText('Describe this frame and state any uncertainty.');layout.addWidget(prompt)
        destination=QLabel('Local model destination: '+(chat.model or 'Choose an installed local model first.'));destination.setTextFormat(Qt.TextFormat.PlainText);destination.setWordWrap(True);layout.addWidget(destination)
        send=QPushButton('Send this frame once');send.setAccessibleName('Approve one local model image transfer');layout.addWidget(send)
        discard=QPushButton('Discard');discard.setAccessibleName('Discard local capture');discard.clicked.connect(dialog.reject);layout.addWidget(discard)
        submitted=[False]
        def transfer():
            if w.busy or w.global_stopped or w.window_stopped or not self.chat.model or not prompt.toPlainText().strip():return
            if w.current() is not chat or (chat.model,chat.agent,chat.project)!=selection:
                w.status.setText('The originating chat or model selection changed. Restore it or discard this preview before sending.');return
            text=prompt.toPlainText().strip();submitted[0]=True;dialog.accept();w.busy=True;w.stop_event.clear()
            for widget in [w.tabs,w.model,w.agent,w.project,w.send_button]:widget.setEnabled(False)
            w.append('\n\nYou\n'+text+'\n\nERSELMETZ AI\n');generation=w.native_generation
            def finished(answer):
                wipe(result['data']);w.append(answer);w.done(cancelled=w.stop_event.is_set())
            def failed(error):wipe(result['data']);w.failed(error)
            w.manager.submit(lambda:w.manager.transport.send_image(chat,result,text,generation=generation),finished,failed,model=True)
        send.clicked.connect(transfer)
        def closed(_code):
            self.preview=None
            picture.clear();prompt.clear();dialog.deleteLater()
            if not submitted[0]:wipe(result['data'])
        dialog.finished.connect(closed);dialog.resize(680,650);dialog.show()

    def transcribe(self,result,direct=False):
        w=self.window;w.busy=True;generation=w.native_generation
        for widget in [w.tabs,w.model,w.agent,w.project,w.send_button]:widget.setEnabled(False)
        w.status.setText('Transcribing on this PC; no cloud service is used.')
        def finished(text):
            wipe(result['data']);w.done(cancelled=w.stop_event.is_set())
            if w.stop_event.is_set() or w.global_stopped or w.window_stopped:return
            if direct:
                if w.current() is not self.chat:
                    w.status.setText('The originating chat changed. The local transcript was discarded.');return
                text=text.strip()
                if not text:w.status.setText('No speech was recognized. Press Speak and try again.');return
                w.composer.setPlainText(text);w.send();return
            dialog=QDialog(w);self.preview=dialog;dialog.setWindowTitle('Review local transcript · not sent');layout=QVBoxLayout(dialog)
            draft=QPlainTextEdit();draft.setAccessibleName('Review local speech transcript');draft.setPlainText(text);layout.addWidget(draft)
            use=QPushButton('Use as draft');use.setAccessibleName('Use reviewed transcript as an unsent draft');layout.addWidget(use)
            discard=QPushButton('Discard');discard.setAccessibleName('Discard local transcript');discard.clicked.connect(dialog.reject);layout.addWidget(discard)
            def accepted():
                if w.current() is self.chat:w.composer.setPlainText(draft.toPlainText())
                dialog.accept()
            def closed(_code):
                self.preview=None;draft.clear();dialog.deleteLater()
            use.clicked.connect(accepted);dialog.finished.connect(closed);dialog.resize(500,320);dialog.show()
        def failed(error):
            wipe(result['data']);w.done(cancelled=w.stop_event.is_set() or w.global_stopped or w.window_stopped)
            if not (w.stop_event.is_set() or w.global_stopped or w.window_stopped):
                w.status.setText('Local speech could not finish. Check the local Ears runtime and Whisper model. No cloud request was made.')
        w.manager.submit(lambda:w.manager.transport.transcribe_local(self.chat,result['data'],generation=generation),finished,failed,model=True)
