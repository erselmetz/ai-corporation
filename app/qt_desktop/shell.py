"""Three resizable panes with independent chat windows over one backend."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import webbrowser

from PySide6.QtCore import QObject, Signal, Slot, Qt, QSettings, QEvent
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QComboBox, QTabWidget, QTextBrowser, QPlainTextEdit,
    QScrollArea, QCheckBox, QInputDialog, QMessageBox, QListWidget, QFrame, QFileDialog,
    QLineEdit, QTextEdit, QFormLayout)
from .brain import BrainPanel

from app.api.advanced_launch import PAGES
from .transport import Transport, Chat
from .theme import apply_theme, TOKENS


def label(text):
    widget = QLabel(text); widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text); widget.setAccessibleName(name or text)
    widget.clicked.connect(callback)
    return widget


def column(parent=None):
    widget = QWidget(parent); layout = QVBoxLayout(widget)
    layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(TOKENS.space)
    return widget, layout


class Work(QObject):
    finished = Signal(object, object, object)
    event = Signal(object, object)


class ShellManager(QObject):
    def __init__(self, app, session, *, browser_open=webbrowser.open):
        super().__init__()
        self.app, self.session = app, session
        self.transport = Transport(session)
        self.browser_open = browser_open
        self.windows = []; self.dialogs = {}; self.catalog = None
        self.graph=None; self.brain_loading=False; self.brain_dirty=False
        app.installEventFilter(self)
        self.shutting_down=False
        self.work = Work(self); self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='qt-api')
        self.work.finished.connect(self.finished)
        self.work.event.connect(self.handle_event)
        self.preferences = QSettings('ERSELMETZ AI', 'Native shell')
        self.reduced_motion = self.preferences.value('reducedMotion', False, type=bool)
        apply_theme(app, self.preferences.value('lightTheme', False, type=bool))

    def submit(self, callback, accepted, failed=None):
        if self.shutting_down: return
        def work():
            try: result, error = callback(), None
            except Exception as exc: result, error = None, exc
            self.work.finished.emit((accepted, failed), result, error)
        self.pool.submit(work)

    @Slot(object, object)
    def handle_event(self, target, event):
        if not self.shutting_down and not target.closed: target.receive(event)

    @Slot(object, object, object)
    def finished(self, callbacks, result, error):
        if self.shutting_down: return
        accepted, failed = callbacks
        if error is None: accepted(result)
        elif failed: failed(error)

    def new_window(self):
        if len(self.windows) >= 16:
            self.windows[-1].raise_(); self.windows[-1].activateWindow()
            self.windows[-1].status.setText('Sixteen chat windows are open. Close one before opening another.')
            return None
        window = ChatWindow(self); self.windows.append(window)
        window.show(); window.raise_(); window.activateWindow(); window.composer.setFocus()
        return window

    def eventFilter(self, watched, event):
        kind=event.type()
        if kind not in (QEvent.Type.DragEnter,QEvent.Type.DragMove,QEvent.Type.Drop,QEvent.Type.KeyPress): return False
        if not hasattr(watched,'window'): return False
        top=watched.window()
        window=next((w for w in self.windows if top is w or top is w.full_brain),None)
        if window is None: return False
        if kind==QEvent.Type.KeyPress:
            if event.key()!=Qt.Key.Key_V or not event.modifiers() & Qt.KeyboardModifier.ControlModifier: return False
            focus=self.app.focusWidget()
            if isinstance(focus,(QPlainTextEdit,QTextEdit,QLineEdit)) and not focus.isReadOnly(): return False
            mime=self.app.clipboard().mimeData()
        else: mime=event.mimeData()
        if not (mime.hasText() or mime.hasUrls()): return False
        if kind in (QEvent.Type.DragEnter,QEvent.Type.DragMove): event.acceptProposedAction(); return True
        if mime.hasUrls() and all(url.isLocalFile() for url in mime.urls()):
            window.offer_paths([url.toLocalFile() for url in mime.urls()][:200])
        elif mime.hasText(): window.offer_text(mime.text())
        if kind==QEvent.Type.Drop: event.acceptProposedAction()
        return True

    def refresh_brain(self):
        if self.brain_loading: self.brain_dirty=True; return
        self.brain_loading=True
        def loaded(graph):
            from app.knowledge.shipped_pack import shipped_pack
            core=shipped_pack().graph()
            graph={**graph,'nodes':[*graph.get('nodes',[]),*core['nodes']],
                   'edges':[*graph.get('edges',[]),*core['edges']],
                   'user_chunks':graph.get('total_chunks',0),'core_chunks':core['total_chunks'],
                   'total_chunks':graph.get('total_chunks',0)+core['total_chunks']}
            self.brain_loading=False; self.graph=graph
            for window in self.windows:
                if not window.closed: window.brain.set_graph(graph)
            if self.brain_dirty:
                self.brain_dirty=False; self.refresh_brain()
        def failed(error):
            self.brain_loading=False
            for window in self.windows: window.brain.setToolTip('Brain could not refresh. Use the refresh button to try again.')
        self.submit(lambda:self.session.request('GET','/api/memory/owner/native-graph'),loaded,failed)

    def remove(self, window):
        if window in self.windows: self.windows.remove(window)
        if not self.windows:
            for dialog in self.dialogs.values(): dialog.close()
            self.app.quit()

    def shutdown(self):
        self.shutting_down=True; self.app.removeEventFilter(self)
        self.pool.shutdown(wait=True, cancel_futures=True)

    def show_dialog(self, kind):
        if kind in self.dialogs:
            dialog = self.dialogs[kind]; dialog.showNormal(); dialog.raise_(); dialog.activateWindow()
            return dialog
        dialog = QDialog(); dialog.setWindowTitle(f'{kind} · ERSELMETZ AI'); dialog.resize(560, 620)
        layout = QVBoxLayout(dialog); layout.addWidget(label(kind))
        if kind == 'Settings':
            light = QCheckBox('Light theme'); light.setAccessibleName('Light theme')
            light.setChecked(self.preferences.value('lightTheme', False, type=bool))
            def theme(checked):
                self.preferences.setValue('lightTheme', checked); apply_theme(self.app, checked)
            light.toggled.connect(theme); layout.addWidget(light)
            reduced = QCheckBox('Reduce motion'); reduced.setAccessibleName('Reduce motion')
            reduced.setChecked(self.reduced_motion)
            def motion(checked):
                self.reduced_motion = checked; self.preferences.setValue('reducedMotion', checked)
            reduced.toggled.connect(motion); layout.addWidget(reduced)
            layout.addWidget(label('Each chat window has its own model, agent and project. Provider and privacy changes keep their existing permission and consent checks.'))
            pages = ['Preferences', 'Providers', 'Online providers', 'Provider connections', 'Privacy and capabilities', 'Updates', 'Backup']
        else:
            layout.addWidget(label('Open the existing local pages in your browser. Sign-in is transferred once, on this computer only.'))
            pages = list(PAGES)
        status = label(''); layout.addWidget(status)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); content, links = column()
        for page in pages:
            links.addWidget(button(page, lambda checked=False, p=page: self.open_page(p, status)))
        links.addStretch(); scroll.setWidget(content); layout.addWidget(scroll)
        layout.addWidget(button('Close', dialog.close))
        self.dialogs[kind] = dialog; dialog.show()
        return dialog

    def open_page(self, page, status):
        status.setText('Opening local page…')
        def opened(url):
            result = self.browser_open(url, new=0)
            status.setText('Opened in your browser.' if result else 'The browser did not confirm opening. Try again.')
        self.submit(lambda: self.transport.launch(page), opened,
                    lambda error: status.setText('Could not open the page. Reopen the app if your session expired.'))


class ChatWindow(QMainWindow):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager; self.closed = False; self.busy = False
        self.feeding=False; self.checking_files=False; self.feed_stop=threading.Event(); self.full_brain=None; self.confirmation=None
        self.feed_frame=None; self.pending_feed=None
        self.stop_event = threading.Event(); self.chats = {}; self.sidebar_visible = True
        self.setWindowTitle('ERSELMETZ AI'); self.resize(1360, 820); self.setMinimumSize(800, 580)
        root, layout = column(); self.setCentralWidget(root); root.setAcceptDrops(True); self.setAcceptDrops(True)
        top = QHBoxLayout(); layout.addLayout(top)
        top.addWidget(button('☰', self.toggle_sidebar, 'Toggle sidebar'))
        top.addWidget(label('ERSELMETZ AI')); top.addStretch()
        top.addWidget(button('New window', manager.new_window)); top.addWidget(button('Settings', lambda: manager.show_dialog('Settings')))
        top.addWidget(button('Advanced', lambda: manager.show_dialog('Advanced')))
        self.splitter = QSplitter(Qt.Orientation.Horizontal); self.splitter.setAccessibleName('Resizable sidebar Brain and chat panes')
        layout.addWidget(self.splitter, 1)
        sidebar_scroll = QScrollArea(); sidebar_scroll.setWidgetResizable(True); self.sidebar = sidebar_scroll
        sidebar, side = column(); sidebar_scroll.setWidget(sidebar); self.splitter.addWidget(sidebar_scroll)
        side.addWidget(label('YOUR BRAIN'))
        side.addWidget(button('Feed file', self.choose_files))
        side.addWidget(button('Feed folder', self.choose_folder))
        side.addWidget(button('Add note', self.add_note))
        side.addWidget(button('Exact math', self.open_math))
        self.cancel_feed_button=button('Cancel feed',self.cancel_feed); self.cancel_feed_button.setEnabled(False); side.addWidget(self.cancel_feed_button)
        side.addWidget(label('THIS CHAT'))
        self.model, self.agent, self.project = QComboBox(), QComboBox(), QComboBox()
        for text, widget in [('Model', self.model), ('Agent', self.agent), ('Project', self.project)]:
            widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(6)
            widget.setAccessibleName(text); side.addWidget(label(text)); side.addWidget(widget)
            widget.currentIndexChanged.connect(self.selection_changed)
        side.addWidget(button('Refresh models', self.refresh))
        self.selection_hint = label('Loading installed models…'); side.addWidget(self.selection_hint)
        side.addStretch(); side.addWidget(label('Local-first · no automatic model downloads'))
        center, center_layout = column(); self.splitter.addWidget(center)
        self.brain_container = center_layout
        self.brain=BrainPanel(lambda:manager.reduced_motion); center_layout.addWidget(self.brain,3)
        self.brain.full_requested.connect(self.toggle_full_brain); self.brain.refresh_requested.connect(manager.refresh_brain)
        self.brain.inspect_requested.connect(self.inspect_node); self.brain.forget_requested.connect(self.forget_node)
        self.brain.search_requested.connect(self.search_brain)
        center_layout.addWidget(label('OBSERVED STEPS'))
        self.steps = QListWidget(); self.steps.setAccessibleName('Observed activity'); center_layout.addWidget(self.steps, 2)
        self.steps.addItem('Ready. No action has run.')
        right, chat_layout = column(); right.setMinimumWidth(274); self.splitter.addWidget(right); self.chat_layout=chat_layout
        chat_top = QHBoxLayout(); chat_layout.addLayout(chat_top)
        chat_top.addWidget(label('CHAT')); chat_top.addStretch(); chat_top.addWidget(button('+', self.new_tab, 'New chat tab'))
        self.tabs = QTabWidget(); self.tabs.setAccessibleName('Chat conversations'); self.tabs.currentChanged.connect(self.tab_changed)
        chat_layout.addWidget(self.tabs, 1)
        self.composer = QPlainTextEdit(); self.composer.setAccessibleName('Message'); self.composer.setPlaceholderText('Message your AI…'); self.composer.setMaximumHeight(130)
        chat_layout.addWidget(self.composer)
        self.send_button = button('Send', self.send); chat_layout.addWidget(self.send_button)
        self.status = label('Starting local workspace…'); layout.addWidget(self.status)
        self.splitter.setSizes([230, 540, 540]); self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1); self.splitter.setStretchFactor(2, 1)
        for shortcut, callback in [('Ctrl+N', manager.new_window), ('Ctrl+B', self.toggle_sidebar), ('Ctrl+Return', self.send)]:
            action = QAction(self); action.setShortcut(QKeySequence(shortcut)); action.triggered.connect(callback); self.addAction(action)
        self.new_tab(); self.refresh()
        if manager.graph is not None: self.brain.set_graph(manager.graph)
        manager.refresh_brain()

    def current(self): return self.chats.get(self.tabs.currentWidget())

    def new_tab(self):
        if self.busy or self.feeding: return
        box = QTextBrowser(); box.setOpenExternalLinks(False); box.setOpenLinks(False)
        box.setAccessibleName('Chat messages'); box.setPlainText('Start a conversation. Your selected local model will appear in the status below.')
        chat = Chat(self.model.currentData() or '', self.agent.currentData() or 'local_worker', self.project.currentData() or '')
        self.chats[box] = chat
        self.tabs.setCurrentIndex(self.tabs.addTab(box, f'Chat {self.tabs.count()+1}'))

    def selection_changed(self):
        if not hasattr(self, 'tabs'): return
        chat = self.current()
        if chat is None: return
        selection = (self.model.currentData() or '', self.agent.currentData() or 'local_worker', self.project.currentData() or '')
        if selection == (chat.model, chat.agent, chat.project): return
        if chat.conversation: self.new_tab()
        else: chat.model, chat.agent, chat.project = selection

    def tab_changed(self):
        chat = self.current()
        if chat is None: return
        for widget, value in [(self.model, chat.model), (self.agent, chat.agent), (self.project, chat.project)]:
            widget.blockSignals(True); index = widget.findData(value)
            if index >= 0: widget.setCurrentIndex(index)
            widget.blockSignals(False)

    def refresh(self):
        self.status.setText('Checking local models…')
        self.manager.submit(self.manager.transport.catalog, self.loaded, self.offline)

    def loaded(self, data):
        if self.closed: return
        self.manager.catalog = data
        current = self.current()
        for widget, records, key, default in [(self.model, data['models'], 'name', current.model),
                (self.agent, data['agents'], 'id', current.agent), (self.project, data['projects'], 'id', current.project)]:
            widget.blockSignals(True); widget.clear()
            if widget is self.project: widget.addItem('No project', '')
            for record in records: widget.addItem(record.get('name', record[key]), record[key])
            index = widget.findData(default)
            if index >= 0: widget.setCurrentIndex(index)
            widget.blockSignals(False)
        self.selection_changed()
        self.selection_hint.setText('Selections apply to this conversation. Changing an existing conversation starts a new tab.')
        self.status.setText('Ready · local model' if data['models'] else 'No local chat model found. Install one in Ollama, then Refresh.')

    def offline(self, error):
        if not self.closed:
            self.status.setText('Could not load this workspace. Start Ollama if it is stopped, or reopen the app if your session expired, then Refresh models. Your chat stays here.')
            self.selection_hint.setText('Offline · no model was downloaded or substituted.')

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible; self.sidebar.setVisible(self.sidebar_visible)
        if not self.sidebar_visible: self.splitter.setSizes([0, 500, 500])
        else: self.splitter.setSizes([230, 500, 500])

    def append(self, text):
        box = self.tabs.currentWidget(); cursor = box.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text); box.setTextCursor(cursor); box.ensureCursorVisible()

    def open_math(self):
        if self.busy or self.feeding:return
        dialog=QDialog(self);dialog.setWindowTitle('Reviewed local exact math');dialog.setMinimumWidth(360)
        layout=QVBoxLayout(dialog);layout.addWidget(label('Review the exact inputs, then Run locally. No model call or cloud transfer. Equations support x up to degree two.'))
        form=QFormLayout();layout.addLayout(form)
        operation=QComboBox();operation.addItems(['Calculate','Solve equation','Convert units']);operation.setAccessibleName('Math operation');form.addRow('Operation',operation)
        value=QLineEdit();value.setMaxLength(256);value.setAccessibleName('Math expression or equation');form.addRow('Expression / equation',value)
        from app.application.services.exact_math import UNITS
        source=QComboBox();target=QComboBox()
        for widget,name in [(source,'Source unit'),(target,'Target unit')]:widget.addItems(list(UNITS));widget.setAccessibleName(name)
        form.addRow('From unit',source);form.addRow('To unit',target)
        def changed():
            converting=operation.currentIndex()==2;source.setEnabled(converting);target.setEnabled(converting)
        operation.currentIndexChanged.connect(changed);changed()
        status=label('');layout.addWidget(status)
        def run():
            text=value.text().strip()
            if not text:status.setText('Enter an expression or equation.');value.setFocus();return
            tool=({'kind':'calculator','expression':text} if operation.currentIndex()==0 else
                  {'kind':'solve_equation','equation':text} if operation.currentIndex()==1 else
                  {'kind':'convert_units','value':text,'source_unit':source.currentText(),'target_unit':target.currentText()})
            dialog.accept();self.send(math_tool=tool)
        layout.addWidget(button('Run locally',run));layout.addWidget(button('Cancel',dialog.reject));dialog.exec()

    def send(self, *, math_tool=None):
        if self.busy or self.feeding: return
        text = self.composer.toPlainText().strip() if math_tool is None else 'Exact math: '+', '.join(str(v) for k,v in math_tool.items() if k!='kind')
        chat = self.current()
        if not text: return
        if not chat.model:
            self.status.setText('Choose an installed local model first.'); return
        if len(text.encode('utf-8')) > 16000:
            self.status.setText('That message is too long. Send a shorter message.'); return
        self.busy = True; self.response_error = False; self.stop_event.clear()
        if math_tool is None:self.composer.clear()
        for widget in [self.model, self.agent, self.project, self.tabs]: widget.setEnabled(False)
        self.send_button.setEnabled(False)
        self.append(f'\n\nYou\n{text}\n\nERSELMETZ AI\n')
        self.brain.scene.highlights.clear();self.brain.scene.update()
        from app.knowledge.shipped_pack import shipped_pack
        local_reply=math_tool is not None or shipped_pack().instant(text) is not None
        self.status.setText('Answering locally · no model call' if local_reply else f'Local · {chat.model} · replying…')
        self.steps.addItem('Reviewed local math or exact-match reply; no model call.' if local_reply else 'Sending this message to the selected local model with shipped general guidance.')
        emit = lambda event: self.manager.work.event.emit(self, event)
        self.manager.submit(lambda: self.manager.transport.send_math(chat,text,math_tool,emit) if math_tool is not None else self.manager.transport.send(chat, text, self.stop_event, emit),
                            lambda result: self.done(), self.failed)

    def receive(self, event):
        if event.get('type') == 'chunk': self.append(event.get('text', ''))
        elif event.get('type')=='complete' and event.get('shipped_guidance'):
            guidance=event['shipped_guidance'];self.brain.scene.highlights=set(guidance['ids']);self.brain.scene.update()
            self.steps.addItem(f"Used {len(guidance['ids'])} actual shipped Core entries ({guidance['mode']}).")
        elif event.get('type')=='brain-progress':
            self.steps.addItem(event['text']); self.manager.refresh_brain()
        elif event.get('type') == 'error':
            self.response_error = True
            self.append('\nThe provider could not finish this reply. Nothing was retried automatically.')

    def done(self):
        if self.closed: return
        self.busy = False
        for widget in [self.model, self.agent, self.project, self.tabs, self.send_button]: widget.setEnabled(True)
        if self.response_error:
            self.status.setText('The reply failed. Check your model before trying again.')
            self.steps.addItem('The response failed. No success was assumed.')
        else:
            self.status.setText('Ready · local'); self.steps.addItem('Response finished.')

    def failed(self, error):
        if self.closed: return
        self.done(); self.status.setText('Could not finish this reply. Check the model and try again. Nothing was retried automatically.')
        self.steps.addItem('The response failed. No success was assumed.')

    def add_note(self):
        content, accepted = QInputDialog.getMultiLineText(self, 'Add note', 'Keep this note locally for 30 days:')
        if not accepted or not content.strip(): return
        self.offer_text(content)

    def choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Feed your Brain')
        if paths: self.offer_paths(paths)

    def choose_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Choose a folder to feed')
        if path: self.offer_paths([path])

    def offer_paths(self, paths):
        if self.busy or self.feeding or self.checking_files: self.status.setText('Wait for this operation before feeding more files.'); return
        from .intake import selected_files
        self.feed_stop.clear(); self.checking_files=True; self.cancel_feed_button.setEnabled(True)
        self.status.setText('Checking the files you chose…')
        def checked(files):
            self.checking_files=False; self.cancel_feed_button.setEnabled(False)
            if self.closed: return
            if self.feed_stop.is_set(): self.status.setText('File check cancelled.'); return
            self.confirm_feed(files,None)
        def failed(error):
            self.checking_files=False; self.cancel_feed_button.setEnabled(False)
            if not self.closed: self.status.setText('Could not inspect those local files.')
        self.manager.submit(lambda:selected_files(paths,self.feed_stop),checked,failed)

    def offer_text(self,text):
        if self.busy or self.feeding or self.checking_files: return
        if not text.strip() or len(text.encode('utf-8'))>5*1024*1024:
            self.status.setText('Choose nonempty text up to 5 MB.'); return
        self.confirm_feed([],text)

    def confirm_feed(self,files,text):
        if self.closed: return
        if not files and text is None:
            self.status.setText('No eligible files. Junk, secrets, links, unsupported types and files over 5 MB are excluded.'); return
        if self.feed_frame is None:
            self.feed_frame=QFrame(); self.feed_frame.setObjectName('panel'); layout=QVBoxLayout(self.feed_frame)
            layout.addWidget(label('Save locally for 30 days to My Brain, shared across your chat windows? Local embeddings use installed nomic-embed-text; no model is downloaded.'))
            self.feed_preview=QPlainTextEdit(); self.feed_preview.setReadOnly(True); self.feed_preview.setAccessibleName('Brain feed preview'); self.feed_preview.setMaximumHeight(90); layout.addWidget(self.feed_preview)
            self.feed_summary=label(''); layout.addWidget(self.feed_summary)
            row=QHBoxLayout(); layout.addLayout(row)
            row.addWidget(button('Save locally',self.approve_feed)); row.addWidget(button('Cancel',self.dismiss_feed))
            self.chat_layout.insertWidget(self.chat_layout.indexOf(self.composer),self.feed_frame)
        self.pending_feed=(tuple(files),text)
        self.feed_preview.setPlainText(text[:1200] if text is not None else '\n'.join(str(path) for path in files))
        self.feed_summary.setText(f'{len(files)} eligible files · up to 200 files / 50 MB per selection. Excluded files are not fed.' if files else 'One local note.')
        self.confirmation=self.feed_frame; self.feed_frame.show()

    def approve_feed(self):
        if self.pending_feed is not None:
            files,text=self.pending_feed; self.start_feed(files,text)

    def dismiss_feed(self):
        if self.feed_frame: self.feed_frame.hide()
        self.confirmation=None; self.pending_feed=None

    def start_feed(self,files,text):
        if self.busy or self.feeding: return
        self.dismiss_feed(); self.feeding=True; self.feed_stop.clear(); self.cancel_feed_button.setEnabled(True); self.send_button.setEnabled(False)
        window_id=id(self)
        def work():
            sources=files if text is None else [None]; results=[]
            for path in sources:
                if self.feed_stop.is_set(): break
                try:
                    result=self.manager.transport.feed_text(window_id,text,self.feed_stop) if path is None else self.manager.transport.feed_file(window_id,path,self.feed_stop)
                    state=result['state']; name='Note' if path is None else path.name
                    message=f'{name}: unchanged, skipped.' if state=='unchanged' else f"{name}: saved {result['chunks']} chunks"+(' (keyword search; local embeddings unavailable).' if state=='lexical-ready' else '.')
                except Exception:
                    message=('Feed cancelled; no further files were started.' if self.feed_stop.is_set() else (str(path.name) if path else 'Note')+': not saved; check the file and local embedding model.')
                results.append(message); self.manager.work.event.emit(self,{'type':'brain-progress','text':message})
            return results
        self.manager.submit(work,self.feed_done,lambda error:self.feed_done([]))

    def feed_done(self,results):
        if self.closed: return
        self.feeding=False; self.cancel_feed_button.setEnabled(False); self.send_button.setEnabled(True)
        self.status.setText('Feed cancelled.' if self.feed_stop.is_set() else 'Feed finished. See the result for each selected source.')
        self.manager.refresh_brain()

    def cancel_feed(self):
        self.feed_stop.set(); self.status.setText('Cancellation requested. No further files will start; results show any files already saved.')
        self.manager.submit(lambda:self.manager.transport.cancel_feed(id(self)),lambda result:None,lambda error:None)

    def inspect_node(self,identifier):
        if identifier.startswith('core:'):
            from app.knowledge.shipped_pack import shipped_pack
            try:self.brain.show_detail(shipped_pack().inspect(identifier))
            except KeyError:self.status.setText('That shipped entry changed. Refresh the Brain.')
            return
        from urllib.parse import urlencode
        self.manager.submit(lambda:self.manager.session.request('GET','/api/memory/owner/native-node?'+urlencode({'identifier':identifier})),
            self.brain.show_detail,lambda error:self.status.setText('This chunk changed or expired. Refresh Brain.'))

    def forget_node(self,node):
        from urllib.parse import quote
        route='/api/memory/owner/native-item/'+quote(node['record_id'],safe='')+'?revision='+node['revision']
        def forgotten(result): self.steps.addItem('Forgot the selected note and derived index.'); self.manager.refresh_brain()
        self.manager.submit(lambda:self.manager.session.request('DELETE',route),forgotten,
                            lambda error:self.status.setText('The note changed or could not be removed. Inspect it again.'))

    def search_brain(self,query):
        input_snapshot=self.brain.search.text()
        def found(result):
            if self.closed or self.brain.search.text()!=input_snapshot: return
            self.brain.scene.highlights={hit['id'] for hit in result['hits']}; self.brain.scene.update()
            self.brain.show_hits(result['hits'])
            self.steps.addItem(f"Brain search: {len(result['hits'])} actual matches ({'keyword search' if result['mode']=='lexical' else 'local embeddings'}).")
        self.manager.submit(lambda:self.manager.session.request('POST','/api/memory/owner/native-recall',{'query':query}),found,
                            lambda error:self.status.setText('Brain search did not complete. Check your local model and try again.'))

    def toggle_full_brain(self):
        if self.full_brain is not None: self.full_brain.close(); return
        dialog=QDialog(self); dialog.setWindowTitle('Brain · ERSELMETZ AI'); dialog.resize(1200,800)
        self.full_brain=dialog; self.brain_container.removeWidget(self.brain); QVBoxLayout(dialog).addWidget(self.brain)
        self.brain.setProperty('fullWindow',True); self.brain.full.setText('Back')
        def restore(result):
            dialog.layout().removeWidget(self.brain); self.brain.setParent(self.brain_container.parentWidget()); self.brain_container.insertWidget(0,self.brain,3)
            self.brain.setProperty('fullWindow',False); self.brain.full.setText('Open Brain'); self.brain.show(); self.full_brain=None; dialog.deleteLater()
        dialog.finished.connect(restore); dialog.showMaximized(); self.brain.setFocus()

    def closeEvent(self, event):
        if self.busy or self.feeding:
            self.status.setText('Wait for this reply to finish before closing this window.'); event.ignore(); return
        if self.full_brain: self.full_brain.close()
        self.feed_stop.set()
        self.brain.scene.timer.stop()
        self.closed = True; self.manager.remove(self); event.accept()
