"""Explicit one-turn cloud escalation; the configured local route never changes."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QPushButton,QHBoxLayout


class CloudReview:
    def __init__(self,window):self.window=window;self.dialog=None;self.pending=None

    def request(self,chat,body,method='POST',*,generation):
        w=self.window
        headers={'X-Local-CSRF':w.manager.session.credentials['csrf'],'X-Native-Window':chat.window_id,
                 'X-Native-Generation':str(generation),'X-Chat-Workspace':chat.workspace}
        return w.manager.session.client.request(method,'/api/chat/conversations/'+chat.conversation+('/messages' if method=='POST' else ''),json=body if method=='POST' else None,headers=headers)

    def prepare(self):
        w=self.window
        if w.busy or w.feeding or w.checking_files or w.window_stopped or w.global_stopped or w.pending_stop or w.manager.pending_global_stop:return
        chat=w.current()
        if chat.read_only:return
        text=w.composer.toPlainText().strip() or chat.last_local_prompt
        if not text:w.status.setText('Write a message, or choose this after a local reply fails.');return
        if self.dialog is not None:self.dialog.raise_();self.dialog.activateWindow();return
        generation=w.native_generation;use_brain=w.use_brain.isChecked();self.pending=None
        w.busy=True;w.send_button.setEnabled(False);w.status.setText('Preparing a cloud preview locally; no cloud request is authorized yet.')
        def work():
            items=w.manager.session.request('GET','/api/local/provider-connections')['items']
            eligible=[item for item in items if item.get('state')=='available' and (
                item.get('provider_type')=='gemini' or
                (item.get('provider_type')=='openai-compatible' and item.get('endpoint',{}).get('enabled')))]
            # No automatic selection between destinations with different privacy
            # properties: an ambiguous configuration must be resolved in Settings.
            if len(eligible)!=1:raise ValueError('Connect exactly one reviewed cloud provider in Settings before using this action.')
            item=eligible[0]
            if not chat.conversation:w.manager.transport.start(chat,generation=generation)
            preferred=w.manager.preferences.value('cloudModel','',type=str)
            model=(preferred if preferred in item.get('models',[]) else
                   item.get('endpoint',{}).get('default_model') or next(iter(item.get('models',[])),None))
            body={'text':text,'route_provider_id':item['provider_id'],'route_model_id':model,'route_consent':True,'outbound_preview':True}
            current=self.request(chat,None,'GET',generation=generation);current.raise_for_status()
            brief=current.json().get('workspace',{}).get('project_brief_digest')
            if brief:body['project_brief_digest']=brief
            if use_brain:
                preview=w.manager.transport.preview_knowledge(chat,text,generation=generation)
                body.update(knowledge_enabled=True,knowledge_scopes=[{'scope':'owner','scope_id':''}],knowledge_preview_digest=preview['digest'])
            response=self.request(chat,body,generation=generation)
            data=response.json();detail=data.get('detail',{})
            if response.status_code!=409 or not isinstance(detail,dict) or detail.get('kind')!='outbound_preview':
                raise ValueError(detail.get('message','Could not prepare that cloud preview.') if isinstance(detail,dict) else str(detail))
            return chat,body,generation,detail
        def ready(pending):
            w.busy=False;w.send_button.setEnabled(True)
            if w.closed or generation!=w.native_generation or w.window_stopped or w.global_stopped or w.pending_stop or w.manager.pending_global_stop:return
            self.pending=pending;preview=pending[3]
            dialog=QDialog(w);self.dialog=dialog;dialog.setWindowTitle('Review cloud turn');dialog.setMinimumSize(620,480)
            layout=QVBoxLayout(dialog);label=QLabel(preview['warning']+'\nDestination: '+preview['destination']+'\nRequested model: '+preview['requested_model']+'\nThe local model remains the default. This is a text-only reply; the local Agent tool loop will not run. Costs and upstream retries are unknown.');label.setWordWrap(True);layout.addWidget(label)
            messages=QPlainTextEdit();messages.setReadOnly(True);messages.setAccessibleName('Exact redacted outbound cloud messages');messages.setPlainText('\n\n'.join({'system':'System instructions','user':'Owner message','assistant':'Previous assistant reply'}.get(item['role'],'Message')+':\n'+item['content'] for item in preview['messages']));layout.addWidget(messages)
            row=QHBoxLayout();layout.addLayout(row)
            approve=QPushButton('Approve this cloud turn');approve.setAccessibleName('Approve this cloud turn');approve.clicked.connect(self.approve);row.addWidget(approve)
            cancel=QPushButton('Cancel cloud turn');cancel.setAccessibleName('Cancel cloud turn');cancel.clicked.connect(dialog.reject);row.addWidget(cancel)
            def closed(result):
                self.pending=None;self.dialog=None
                if result==QDialog.DialogCode.Rejected and not w.closed:w.status.setText('Cloud turn cancelled. Nothing was sent to the cloud for this turn.')
                dialog.deleteLater()
            dialog.finished.connect(closed);dialog.setModal(True);dialog.show()
        def failed(error):
            w.busy=False;w.send_button.setEnabled(True);w.status.setText(str(error)[:400])
        w.manager.submit(work,ready,failed)

    def approve(self):
        w=self.window;pending=self.pending
        if pending is None:return
        chat,body,generation,preview=pending
        if w.closed or w.window_stopped or w.global_stopped or w.pending_stop or w.manager.pending_global_stop or generation!=w.native_generation or chat is not w.current():
            if self.dialog:self.dialog.reject()
            return
        if self.dialog:self.dialog.accept()
        body={**body,'outbound_preview':False,'outbound_digest':preview['digest'],'cloud_consent':True}
        w.busy=True;w.response_error=False;w.stop_event.clear();w.send_button.setEnabled(False)
        for widget in [w.model,w.agent,w.project,w.tabs]:widget.setEnabled(False)
        w.status.setText('Sending this one approved cloud turn; local remains the default.')
        def work():
            response=self.request(chat,body,generation=generation)
            if not response.is_success:
                detail=response.json().get('detail','Cloud reply failed. Nothing was retried.')
                raise ValueError(detail.get('message','The preview changed. Review it again; nothing was sent.') if isinstance(detail,dict) else str(detail))
            return response.json()
        def completed(result):
            if w.closed:return
            messages=result['conversation']['messages'];answer=next((m['content'] for m in reversed(messages) if m['role']=='assistant'),'No cloud answer was confirmed.')
            w.append('\n\nYou\n'+body['text']+'\n\nERSELMETZ AI (one cloud turn)\n'+answer)
            if w.composer.toPlainText().strip()==body['text']:w.composer.clear()
            w.receive({'type':'complete','context_trace':result.get('context_trace',{})});w.done(cancelled=w.stop_event.is_set())
            if not w.stop_event.is_set() and not w.window_stopped and not w.global_stopped:w.status.setText('Cloud turn finished. The local model is still the default.')
        def failed(error):
            w.failed(error)
            if not w.closed and not w.stop_event.is_set():w.status.setText(str(error)[:400])
        w.manager.submit(work,completed,failed,model=True)
