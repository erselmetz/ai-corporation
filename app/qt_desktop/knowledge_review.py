"""Per-turn private-Brain preview using the existing digest/consent contract."""
from PySide6.QtCore import QObject,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QPushButton


class KnowledgeReview(QObject):
    def __init__(self,window):super().__init__(window);self.window=window;self.dialog=None

    def prepare(self,chat,text):
        w=self.window;generation=w.native_generation;w.busy=True;w.response_error=False;w.stop_event.clear()
        for widget in [w.model,w.agent,w.project,w.tabs,w.send_button]:widget.setEnabled(False)
        w.status.setText('Finding local Brain excerpts for review. No chat reply has been requested.')
        def loaded(preview):
            if w.closed:return
            if w.stop_event.is_set() or w.window_stopped or w.global_stopped or generation!=w.native_generation:
                w.done(cancelled=True);return
            dialog=QDialog(w);self.dialog=dialog;dialog.setWindowTitle('Review My Brain for this message')
            layout=QVBoxLayout(dialog)
            caption=QLabel('Question: '+text);caption.setTextFormat(Qt.TextFormat.PlainText);caption.setWordWrap(True);layout.addWidget(caption)
            content=QPlainTextEdit();content.setReadOnly(True);content.setAccessibleName('Exact private Brain excerpt preview')
            content.setPlainText('\n\n'.join('['+str(i)+'] '+item['source']+'\n'+item['content'] for i,item in enumerate(preview['items'],1)))
            if not preview['items']:content.setPlainText('No relevant excerpts were found. The app will say that the selected Brain does not contain an answer.')
            layout.addWidget(content)
            mode=QLabel({'lexical-only':'Keyword search','semantic-only':'Local semantic search','hybrid':'Keyword search and local embeddings'}.get(preview.get('trace',{}).get('mode'),'Local search from selected scopes'))
            layout.addWidget(mode)
            send=QPushButton('Use these sources for this message');send.setAccessibleName('Approve these exact Brain excerpts for one message');layout.addWidget(send)
            cancel=QPushButton('Cancel');cancel.setAccessibleName('Cancel Brain preview without sending');cancel.clicked.connect(dialog.reject);layout.addWidget(cancel)
            confirmed=[False]
            def approved():
                if (w.stop_event.is_set() or w.global_stopped or w.window_stopped or generation!=w.native_generation
                        or w.current() is not chat or w.composer.toPlainText().strip()!=text or not w.use_brain.isChecked()):
                    w.status.setText('The message, selection or stop state changed. Cancel and review it again before sending.');return
                confirmed[0]=True;dialog.accept();w.busy=False
                w.send(knowledge={'knowledge_enabled':True,'knowledge_scopes':[{'scope':'owner','scope_id':''}],
                                  'knowledge_preview_digest':preview['digest']})
            send.clicked.connect(approved)
            def closed(_code):
                self.dialog=None
                content.clear();caption.clear();dialog.deleteLater()
                if not confirmed[0]:w.done(cancelled=w.stop_event.is_set())
            dialog.finished.connect(closed);dialog.resize(640,520);dialog.show()
        w.manager.submit(lambda:w.manager.transport.preview_knowledge(chat,text,generation=generation),loaded,w.failed,model=True)

    def stop(self):
        if self.dialog:self.dialog.reject()
