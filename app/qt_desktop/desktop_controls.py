"""Explicit owner-selected Windows controls through existing guarded API routes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QMessageBox


class DesktopControls:
    def __init__(self,window):self.window=window;self.dialog=None;self.pending=False

    def show(self):
        w=self.window
        if self.pending:
            w.status.setText('Wait for the previous desktop request to finish. Nothing was retried.');return
        if self.dialog is not None:self.dialog.raise_();self.dialog.activateWindow();return
        if w.busy or not w.native_id or w.window_stopped or w.global_stopped:return
        self.generation=w.native_generation
        dialog=QDialog(w);dialog.setWindowTitle('Choose an exact desktop action');dialog.resize(540,420)
        layout=QVBoxLayout(dialog)
        notice=QLabel('Allow one executable for this app session, then choose its exact window and control. Each click or single-line text replacement needs a new approval. Stop blocks further dispatch; an action already dispatched cannot be undone.')
        notice.setWordWrap(True);notice.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(notice)
        self.process=QLineEdit();self.process.setPlaceholderText('Exact executable name, for example notepad.exe');self.process.setAccessibleName('Executable to permit for this session');layout.addWidget(self.process)
        self.allow=QPushButton('Allow process and list its windows');self.allow.setAccessibleName(self.allow.text());self.allow.clicked.connect(self.list_windows);layout.addWidget(self.allow)
        self.windows=QComboBox();self.windows.setAccessibleName('Exact desktop window');layout.addWidget(self.windows)
        self.inspect=QPushButton('List buttons and editable fields');self.inspect.setAccessibleName(self.inspect.text());self.inspect.clicked.connect(self.list_controls);layout.addWidget(self.inspect)
        self.controls=QComboBox();self.controls.setAccessibleName('Exact button or text field');layout.addWidget(self.controls)
        self.value=QLineEdit();self.value.setMaxLength(2048);self.value.setPlaceholderText('Replacement text for an editable field; no Enter or shortcuts');self.value.setAccessibleName('Exact text replacement');layout.addWidget(self.value)
        self.review=QPushButton('Review one action');self.review.setAccessibleName(self.review.text());self.review.clicked.connect(self.prepare);layout.addWidget(self.review)
        self.status=QLabel('No process allowed or action requested here.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        close=QPushButton('Close');close.setAccessibleName(close.text());close.clicked.connect(dialog.close);layout.addWidget(close)
        dialog.finished.connect(lambda:self.closed(dialog));self.dialog=dialog;dialog.show()

    def closed(self,dialog):
        if self.dialog is dialog:
            self.value.clear();self.dialog=None
        dialog.deleteLater()

    def active(self):
        w=self.window
        return self.dialog is not None and not w.closed and not w.window_stopped and not w.global_stopped and w.native_generation==self.generation

    def api(self,method,path,body=None):
        w=self.window
        return w.manager.session.request(method,path,body,window=w.native_id,generation=self.generation)

    def run(self,work,accepted):
        if self.pending or not self.active():return
        self.pending=True;self.dialog.setEnabled(False)
        def finished(result):
            self.pending=False
            if not self.active():return
            self.dialog.setEnabled(True);accepted(result)
        def failed(error):
            self.pending=False
            if not self.active():return
            self.dialog.setEnabled(True);self.status.setText('The requested step was not confirmed. No automatic retry. Check the selected process, control and local permissions.')
        self.window.manager.submit(work,finished,failed)

    def list_windows(self):
        process=self.process.text().strip().lower()
        def work():
            self.api('PUT','/api/local/automation/desktop/process',{'process_name':process,'allowed':True})
            return self.api('POST','/api/local/automation/desktop/windows',{'process_name':process})
        def listed(result):
            self.windows.clear();self.controls.clear()
            for item in result['items']:self.windows.addItem(item['window_title'],item)
            self.status.setText('Choose a window; no click or text replacement has run.' if result['items'] else 'No supported visible window found. No action ran.')
        self.run(work,listed)

    def list_controls(self):
        target=self.windows.currentData()
        if not target:return
        def listed(result):
            self.controls.clear()
            for item in result['items']:
                self.controls.addItem(('Click: ' if item['action']=='invoke_button' else 'Replace text: ')+item['control_name'],dict(target,**item))
            self.status.setText('Only visible enabled direct-child buttons and non-password writable text fields are supported. No action has run.')
        self.run(lambda:self.api('POST','/api/local/automation/desktop/controls',target),listed)

    def prepare(self):
        target=self.controls.currentData()
        if not target:return
        payload=dict(target)
        if payload['action']=='fill_text':payload['value']=self.value.text()
        def review(result):
            approval=result['approval'];identifier=approval['approval_id'];digest=approval['approval_digest']
            text=('Window: '+payload['window_title']+'\nProcess: '+payload['process_name']+
                  '\nControl: '+payload['control_name']+' ('+payload['automation_id']+')\nAction: '+payload['action'])
            if payload['action']=='fill_text':text+='\nReplace the field contents with exactly:\n'+payload['value']
            question=QMessageBox(QMessageBox.Icon.Question,'Approve exactly one desktop action',text,
                                 QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,self.dialog)
            question.setTextFormat(Qt.TextFormat.PlainText);question.setDefaultButton(QMessageBox.StandardButton.No)
            approved=question.exec()==QMessageBox.StandardButton.Yes and self.active()
            def execute():
                self.api('POST','/api/capabilities/approvals/'+identifier+('/approve' if approved else '/deny'),{'confirmed_digest':digest})
                if not approved:return {'status':'denied','message':'Cancelled. No action was dispatched.'}
                return self.api('POST','/api/local/automation/desktop/execute',dict(payload,approval_id=identifier))
            def completed(outcome):
                message=outcome.get('message') or 'Action dispatched to the approved control. Its application result is unverified; do not retry automatically.'
                self.status.setText(message);self.window.steps.addItem(message)
            self.run(execute,completed)
        self.run(lambda:self.api('POST','/api/local/automation/desktop/request-approval',payload),review)

    def stop(self):
        if self.dialog is not None:self.dialog.close()
