"""Bind local Brain retrieval to the exact turn without a redundant prompt."""
from PySide6.QtCore import QObject


class KnowledgeReview(QObject):
    def __init__(self,window):super().__init__(window);self.window=window

    def prepare(self,chat,text):
        w=self.window;generation=w.native_generation;w.busy=True;w.response_error=False;w.stop_event.clear()
        for widget in [w.model,w.agent,w.project,w.tabs,w.send_button]:widget.setEnabled(False)
        w.status.setText('Finding relevant local Brain sources…')
        def loaded(preview):
            if w.closed:return
            if w.stop_event.is_set() or w.window_stopped or w.global_stopped or generation!=w.native_generation:
                w.done(cancelled=True);return
            if (w.stop_event.is_set() or w.global_stopped or w.window_stopped or generation!=w.native_generation
                    or w.current() is not chat or w.composer.toPlainText().strip()!=text or not w.use_brain.isChecked()):
                w.done(cancelled=w.stop_event.is_set())
                if not w.stop_event.is_set():w.status.setText('The message or Brain selection changed. Send again to use the current selection.')
                return
            count=len(preview.get('items',[]));mode=preview.get('trace',{}).get('mode','local search')
            w.steps.addItem(f'Found {count} relevant local Brain source(s) using {mode}.')
            w.busy=False
            w.send(knowledge={'knowledge_enabled':True,'knowledge_scopes':[{'scope':'owner','scope_id':''}],
                              'knowledge_preview_digest':preview['digest']})
        w.manager.submit(lambda:w.manager.transport.preview_knowledge(chat,text,generation=generation),loaded,w.failed,model=True)

    def stop(self):pass
