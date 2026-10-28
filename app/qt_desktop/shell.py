"""Three resizable panes with independent chat windows over one backend."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import webbrowser
import uuid

from PySide6.QtCore import QObject, Signal, Slot, Qt, QSettings, QEvent, QTimer
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QComboBox, QTabWidget, QTextBrowser, QPlainTextEdit,
    QScrollArea, QCheckBox, QInputDialog, QMessageBox, QListWidget, QFrame, QFileDialog,
    QLineEdit, QTextEdit, QFormLayout, QSpinBox)
from .brain import BrainPanel

from .pages import PAGES
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
    def __init__(self, app, session, *, browser_open=webbrowser.open,window_store=None,preferences=None):
        super().__init__()
        self.app, self.session = app, session
        self.transport = Transport(session)
        self.browser_open = browser_open
        self.windows = []; self.dialogs = {}; self.catalog = None
        self.graph=None; self.brain_loading=False; self.brain_dirty=False
        app.installEventFilter(self)
        self.shutting_down=False
        self.quitting=False
        self.pending_global_stop=False
        self.work = Work(self); self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='qt-api')
        self.model_pool=ThreadPoolExecutor(max_workers=16,thread_name_prefix='qt-model')
        self.control_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='qt-control')
        self.queue_loading=False;self.queue_timer=QTimer(self);self.queue_timer.timeout.connect(self.poll_queue);self.queue_timer.start(750)
        self.work.finished.connect(self.finished)
        self.work.event.connect(self.handle_event)
        self.preferences = preferences if preferences is not None else QSettings('ERSELMETZ AI', 'Native shell')
        self.window_store=window_store
        self.layout_timer=QTimer(self);self.layout_timer.timeout.connect(self.save_windows)
        if window_store is not None:self.layout_timer.start(2000)
        self.reduced_motion = self.preferences.value('reducedMotion', False, type=bool)
        apply_theme(app, self.preferences.value('lightTheme', False, type=bool))

    def submit(self, callback, accepted, failed=None, *, model=False, control=False):
        if self.shutting_down: return
        def work():
            try: result, error = callback(), None
            except Exception as exc: result, error = None, exc
            self.work.finished.emit((accepted, failed), result, error)
        (self.control_pool if control else self.model_pool if model else self.pool).submit(work)

    def poll_queue(self):
        if self.queue_loading or self.shutting_down:return
        self.queue_loading=True
        def loaded(data):
            self.queue_loading=False
            for window in self.windows:
                if not window.closed:window.show_runtime(data)
        def failed(error):
            self.queue_loading=False
            for window in self.windows:window.queue_status.setText('Request and capture status unavailable.')
        self.submit(lambda:self.session.request('GET','/api/native/windows'),loaded,failed,control=True)

    def stop_all(self):
        self.pending_global_stop=True
        for window in self.windows:
            window.stop_event.set();window.feed_stop.set();window.global_stopped=True
            window.capture_controls.stop()
            window.knowledge_review.stop()
            window.desktop_controls.stop()
            if window.pending_tool is not None:window.finish_tool_review(False)
            window.status.setText('Global stop requested; waiting for backend confirmation.')
        def confirmed(result):self.pending_global_stop=False;self.poll_queue()
        def failed(error):
            for window in self.windows:window.status.setText('Global stop was not confirmed. Retry Stop all or close the app.')
        self.submit(lambda:self.session.request('POST','/api/local/emergency-stop/stop'),
            confirmed,failed,control=True)

    def resume_all(self,status):
        def resumed(result):
            self.pending_global_stop=False;status.setText('New requests are allowed. Cancelled work was not restarted.');self.poll_queue()
        self.submit(lambda:self.session.request('POST','/api/local/emergency-stop/resume',{'confirmed':True}),
            resumed,
            lambda error:status.setText('Could not resume. Check the local session and try again.'),control=True)

    @Slot(object, object)
    def handle_event(self, target, event):
        if not self.shutting_down and not target.closed: target.receive(event)

    @Slot(object, object, object)
    def finished(self, callbacks, result, error):
        if self.shutting_down: return
        accepted, failed = callbacks
        if error is None: accepted(result)
        elif failed: failed(error)

    def new_window(self):return self._new_window()

    def _new_window(self,descriptor=None):
        if len(self.windows) >= 16:
            self.windows[-1].raise_(); self.windows[-1].activateWindow()
            self.windows[-1].status.setText('Sixteen chat windows are open. Close one before opening another.')
            return None
        window = ChatWindow(self,descriptor); self.windows.append(window)
        window.show(); window.raise_(); window.activateWindow(); window.composer.setFocus()
        if descriptor is not None:
            from PySide6.QtCore import QRect
            rectangle=QRect(*descriptor['geometry'])
            screens=self.app.screens();screen=next((s for s in screens if s.availableGeometry().intersects(rectangle)),self.app.primaryScreen())
            area=screen.availableGeometry();width=min(max(800,rectangle.width()),area.width());height=min(max(580,rectangle.height()),area.height())
            window.setGeometry(max(area.left(),min(rectangle.x(),area.right()-width+1)),
                max(area.top(),min(rectangle.y(),area.bottom()-height+1)),width,height)
            if not descriptor['sidebar']:window.toggle_sidebar()
            if descriptor['maximized']:window.showMaximized()
        return window

    def restore_windows(self):
        records=self.window_store.load() if self.window_store is not None else []
        for descriptor in records:self._new_window(descriptor)
        if not records:
            window=self.new_window()
            if self.window_store is not None and self.window_store.notice:window.status.setText(self.window_store.notice)

    def save_windows(self,windows=None):
        if self.window_store is None:return
        windows=self.windows if windows is None else windows
        if not windows:return  # Preserve the final window when quitting via X.
        try:self.window_store.save([window.descriptor() for window in windows])
        except (OSError,ValueError):
            for window in windows:
                if not window.closed:window.status.setText('Window layout could not be saved. Your chat and permission settings were not changed.')

    def quit(self):
        if any(w.busy or w.feeding or w.capture_controls.lease is not None or w.desktop_controls.pending for w in self.windows):
            self.stop_all()
            for window in self.windows:window.status.setText('Stop requested. Wait for active work and capture release, then Quit again.')
            return
        self.save_windows();self.quitting=True;self.app.quit()

    def eventFilter(self, watched, event):
        kind=event.type()
        if kind not in (QEvent.Type.DragEnter,QEvent.Type.DragMove,QEvent.Type.Drop,QEvent.Type.KeyPress): return False
        if not hasattr(watched,'window'): return False
        top=watched.window()
        if (kind==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Period
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.stop_all();return True
            parent=top
            while parent is not None:
                owner=next((w for w in self.windows if parent is w or parent is w.full_brain),None)
                if owner is not None:
                    owner.stop_window(force=True);return True
                parent=parent.parentWidget()
            return False
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
        if not self.quitting and len(self.windows)==1:self.save_windows([window])
        if window in self.windows: self.windows.remove(window)
        if self.windows and not self.quitting:self.save_windows()
        if not self.windows:
            for dialog in self.dialogs.values(): dialog.close()
            self.app.quit()

    def shutdown(self):
        self.layout_timer.stop();self.save_windows()
        self.queue_timer.stop()
        self.shutting_down=True; self.app.removeEventFilter(self)
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.model_pool.shutdown(wait=True,cancel_futures=True);self.control_pool.shutdown(wait=True,cancel_futures=True)

    def show_dialog(self, kind):
        if kind in self.dialogs:
            dialog = self.dialogs[kind]; dialog.showNormal(); dialog.raise_(); dialog.activateWindow()
            return dialog
        dialog = QDialog(); dialog.setWindowTitle(f'{kind} · ERSELMETZ AI'); dialog.resize(560, 620)
        layout = QVBoxLayout(dialog); layout.addWidget(label(kind))
        if kind == 'Settings':
            resume_status=label('Resume allows new requests only; it never replays stopped work.')
            layout.addWidget(resume_status);layout.addWidget(button('Resume protected work',lambda:self.resume_all(resume_status)))
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
            layout.addWidget(button('Quit ERSELMETZ AI',self.quit,'Quit the app and save only window descriptors; never replay actions'))
            pages = ['Preferences', 'Providers', 'Online providers', 'Provider connections', 'Privacy and capabilities', 'Updates', 'Backup']
        else:
            layout.addWidget(label('Native management windows. Browser navigation is disabled.'))
            pages = list(PAGES)
        status = label(''); layout.addWidget(status)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); content, links = column()
        for page in pages:
            links.addWidget(button(page, lambda checked=False, p=page: self.open_page(p, status)))
        links.addStretch(); scroll.setWidget(content); layout.addWidget(scroll)
        layout.addWidget(button('Open online docs', self.open_online_docs))
        layout.addWidget(button('Close', dialog.close))
        self.dialogs[kind] = dialog; dialog.show()
        return dialog

    def open_page(self, page, status):
        if page not in PAGES: raise ValueError('Unknown native page')
        key='Page: '+page
        if key not in self.dialogs:
            from .native_pages import RecordWindow,BackupWindow,OwnerWindow
            if page=='Backup':dialog=BackupWindow(self)
            elif page=='Owner sign-in':dialog=OwnerWindow(self)
            else:dialog=RecordWindow(self,page)
            self.dialogs[key]=dialog
        dialog=self.dialogs[key];dialog.showNormal();dialog.raise_();dialog.activateWindow()
        status.setText('Opened native window: '+page)
        return dialog

    def open_online_docs(self):
        return self.browser_open('https://ai.erselmetz.com',new=2)


class ChatWindow(QMainWindow):
    def __init__(self, manager,descriptor=None):
        super().__init__()
        self.manager = manager; self.closed = False; self.busy = False;self.response_error=False
        self.pending_restore=descriptor
        self.native_id='';self.native_generation=0;self.window_stopped=False;self.global_stopped=False;self.pending_stop=False
        self.client_id=uuid.uuid4().hex;self.registering=False;self.refresh_version=0;self.available_models=set()
        self.feeding=False; self.checking_files=False; self.feed_stop=threading.Event(); self.full_brain=None; self.confirmation=None
        self.feed_frame=None; self.pending_feed=None
        self.delete_frame=None;self.pending_delete=None
        self.tool_frame=None;self.pending_tool=None;self.pending_run=None
        self.stop_event = threading.Event(); self.chats = {}; self.sidebar_visible = True
        from .capture_controls import CaptureControls
        self.capture_controls=CaptureControls(self)
        from .desktop_controls import DesktopControls
        self.desktop_controls=DesktopControls(self)
        from .knowledge_review import KnowledgeReview
        self.knowledge_review=KnowledgeReview(self)
        self.setWindowTitle('ERSELMETZ AI'); self.resize(1360, 820); self.setMinimumSize(800, 580)
        root, layout = column(); self.setCentralWidget(root); root.setAcceptDrops(True); self.setAcceptDrops(True)
        top = QHBoxLayout(); layout.addLayout(top)
        top.addWidget(button('☰', self.toggle_sidebar, 'Toggle sidebar'))
        top.addWidget(label('ERSELMETZ AI')); top.addStretch()
        top.addWidget(button('New window', manager.new_window)); top.addWidget(button('Settings', lambda: manager.show_dialog('Settings')))
        top.addWidget(button('Advanced', lambda: manager.show_dialog('Advanced')))
        from .cloud_review import CloudReview
        self.cloud_review=CloudReview(self)
        top.addWidget(button('Ask the free pool?',self.cloud_review.prepare,'Ask an optional cloud endpoint after reviewing the exact outbound prompt'))
        self.stop_button=button('Stop',self.stop_window,'Stop or resume this chat window');top.addWidget(self.stop_button)
        top.addWidget(button('Stop all',manager.stop_all,'Emergency stop all windows'))
        self.splitter = QSplitter(Qt.Orientation.Horizontal); self.splitter.setAccessibleName('Resizable sidebar Brain and chat panes')
        layout.addWidget(self.splitter, 1)
        sidebar_scroll = QScrollArea(); sidebar_scroll.setWidgetResizable(True); self.sidebar = sidebar_scroll
        sidebar, side = column(); sidebar_scroll.setWidget(sidebar); self.splitter.addWidget(sidebar_scroll)
        side.addWidget(label('YOUR BRAIN'))
        side.addWidget(button('Feed file', self.choose_files))
        side.addWidget(button('Feed folder', self.choose_folder))
        side.addWidget(button('Add note', self.add_note))
        side.addWidget(button('Exact math', self.open_math))
        side.addWidget(button('Desktop click / type',self.desktop_controls.show,'Choose and approve one exact desktop action'))
        for caption,kind in [('Camera frame','camera'),('Screen frame','screen'),('Microphone draft','microphone')]:
            side.addWidget(button(caption,lambda checked=False,kind=kind:self.capture_controls.start(kind),'Request one '+kind+' capture after exact consent'))
        self.release_capture_button=button('Release capture',self.capture_controls.retry_release,'Stop capture or retry its ownership release; does not capture data')
        self.release_capture_button.setEnabled(False);side.addWidget(self.release_capture_button)
        self.cancel_feed_button=button('Cancel feed',self.cancel_feed); self.cancel_feed_button.setEnabled(False); side.addWidget(self.cancel_feed_button)
        side.addWidget(label('THIS CHAT'))
        self.model, self.agent, self.project = QComboBox(), QComboBox(), QComboBox()
        for text, widget in [('Model', self.model), ('Agent', self.agent), ('Project', self.project)]:
            widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(6)
            widget.setAccessibleName(text); side.addWidget(label(text)); side.addWidget(widget)
            widget.currentIndexChanged.connect(self.selection_changed)
        side.addWidget(button('Refresh models', self.refresh))
        self.agent_loop=QCheckBox('Bounded tool loop');self.agent_loop.setAccessibleName('Use bounded local Agent tool loop');side.addWidget(self.agent_loop)
        self.use_brain=QCheckBox('Use My Brain for this message');self.use_brain.setAccessibleName('Review private Brain excerpts before sending this message');side.addWidget(self.use_brain)
        self.ask_first=QCheckBox('Ask before every tool');self.ask_first.setChecked(True);self.ask_first.setAccessibleName('Ask before every tool');side.addWidget(self.ask_first)
        self.thinking=QCheckBox('Show native thinking');self.thinking.setAccessibleName('Show actual native model thinking when supported');side.addWidget(self.thinking)
        self.thinking.setEnabled(False)
        self.agent_loop.toggled.connect(self.thinking_mode)
        self.step_limit=QSpinBox();self.step_limit.setRange(1,5);self.step_limit.setValue(5);self.step_limit.setAccessibleName('Maximum Agent model and tool steps')
        side.addWidget(label('Maximum steps (model + tool)'));side.addWidget(self.step_limit)
        self.context_size=QComboBox();self.context_size.addItems(['2048','4096','8192','16384']);self.context_size.setCurrentText('8192');self.context_size.setAccessibleName('Local model context size');side.addWidget(label('Context size'));side.addWidget(self.context_size)
        self.reply_limit=QComboBox();self.reply_limit.setAccessibleName('Local reply time limit')
        for seconds in [30,60,90]:self.reply_limit.addItem(str(seconds)+' seconds',seconds)
        self.reply_limit.setToolTip('For the next local Ollama reply only. Requires model runtime management permission; total turn and token limits still apply.')
        side.addWidget(label('Local reply limit'));side.addWidget(self.reply_limit)
        self.thinking_mode(False)
        side.addWidget(button('Permit tool folder',self.permit_tool_folder,'Choose a local file-tool root for this conversation'))
        self.selection_hint = label('Loading installed models…'); side.addWidget(self.selection_hint)
        side.addStretch(); side.addWidget(label('Local-first · no automatic model downloads'))
        center, center_layout = column(); self.splitter.addWidget(center)
        self.brain_container = center_layout
        self.brain=BrainPanel(lambda:manager.reduced_motion); center_layout.addWidget(self.brain,3)
        self.brain.full_requested.connect(self.toggle_full_brain); self.brain.refresh_requested.connect(manager.refresh_brain)
        self.brain.inspect_requested.connect(self.inspect_node); self.brain.forget_requested.connect(self.forget_node)
        self.brain.search_requested.connect(self.search_brain)
        self.brain.window_stop_requested.connect(self.stop_window);self.brain.global_stop_requested.connect(manager.stop_all)
        center_layout.addWidget(label('OBSERVED STEPS'))
        self.steps = QListWidget(); self.steps.setAccessibleName('Observed activity');self.steps.setWordWrap(True)
        self.steps.model().rowsInserted.connect(self.trim_activity)
        center_layout.addWidget(self.steps, 2)
        self.steps.addItem('Ready. No action has run.')
        right, chat_layout = column(); right.setMinimumWidth(274); self.splitter.addWidget(right); self.chat_layout=chat_layout
        chat_top = QHBoxLayout(); chat_layout.addLayout(chat_top)
        chat_top.addWidget(label('CHAT')); chat_top.addStretch()
        chat_top.addWidget(button('Rename',self.rename_tab,'Rename current chat (F2)'))
        chat_top.addWidget(button('Delete chat',self.ask_delete_chat,'Delete current chat after confirmation'))
        chat_top.addWidget(button('+', self.new_tab, 'New chat tab'))
        self.tabs = QTabWidget(); self.tabs.setAccessibleName('Chat conversations'); self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.tabBarDoubleClicked.connect(lambda index:self.rename_tab() if index>=0 else None)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        chat_layout.addWidget(self.tabs, 1)
        self.composer = QPlainTextEdit(); self.composer.setAccessibleName('Message'); self.composer.setPlaceholderText('Message your AI…'); self.composer.setMaximumHeight(130)
        chat_layout.addWidget(self.composer)
        self.send_button = button('Send', self.send); chat_layout.addWidget(self.send_button)
        self.status = label('Starting local workspace…'); layout.addWidget(self.status)
        self.queue_status=label('Checking request and capture ownership…');layout.addWidget(self.queue_status)
        self.splitter.setSizes([230, 540, 540]); self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1); self.splitter.setStretchFactor(2, 1)
        for shortcut, callback in [('Ctrl+N', manager.new_window), ('Ctrl+Q',manager.quit), ('Ctrl+B', self.toggle_sidebar), ('Ctrl+Return', self.send),('F2',self.rename_tab)]:
            action = QAction(self); action.setShortcut(QKeySequence(shortcut)); action.triggered.connect(callback); self.addAction(action)
        self.new_tab(); self.refresh()
        if manager.graph is not None: self.brain.set_graph(manager.graph)
        manager.refresh_brain()

    def current(self): return self.chats.get(self.tabs.currentWidget())

    def new_tab(self,chat=None):
        if self.busy or self.feeding: return
        from .windows import MAX_TABS
        if self.tabs.count()>=MAX_TABS:self.status.setText('Close a chat tab before opening another; sixteen tabs fit in one window.');return
        box = QTextBrowser(); box.setOpenExternalLinks(False); box.setOpenLinks(False)
        box.setAccessibleName('Chat messages'); box.setPlainText('Start a conversation. Your selected local model will appear in the status below.')
        chat = chat or Chat(self.model.currentData() or '', self.agent.currentData() or 'local_worker', self.project.currentData() or '')
        chat.window_id=self.native_id
        chat.window_generation=self.native_generation
        chat.title=chat.title or f'Chat {self.tabs.count()+1}'
        self.chats[box] = chat
        self.tabs.setCurrentIndex(self.tabs.addTab(box,chat.title.replace('&','&&')))
        return box

    def descriptor(self):
        from .windows import window
        if self.pending_restore is not None:return window(self.pending_restore)
        rectangle=self.normalGeometry() if self.isMaximized() else self.geometry()
        tabs=[{key:getattr(self.chats[self.tabs.widget(i)],key) for key in ('model','agent','project','workspace','conversation','title')}
              for i in range(self.tabs.count())]
        return window({'geometry':[rectangle.x(),rectangle.y(),rectangle.width(),rectangle.height()],
            'maximized':self.isMaximized(),'sidebar':self.sidebar_visible,'selected':self.tabs.currentIndex(),'tabs':tabs})

    def restore_tabs(self,descriptor):
        if any(not item['model'] for item in descriptor['tabs']) and self.model.findData('')<0:
            self.model.addItem('No model selected','')
        self.tabs.blockSignals(True)
        for box in list(self.chats):self.chats.pop(box);self.tabs.removeTab(self.tabs.indexOf(box));box.deleteLater()
        for item in descriptor['tabs']:
            chat=Chat(**item,read_only=bool(item['conversation']),title_pending=bool(item['title']) and not item['conversation'])
            box=self.new_tab(chat)
            if chat.conversation:
                box.setPlainText('Checking retained history. Nothing will be replayed.')
                def loaded(record,chat=chat,box=box):
                    if self.closed or box not in self.chats:return
                    selection=record.get('selection')
                    if selection:
                        chat.model=selection['model_id'];chat.agent=selection['agent_id'];chat.project=selection['project_id']
                    elif record.get('agent_id'):chat.agent=record['agent_id']
                    lines=['Restored history is read-only. Open a new chat to send a message; no action was replayed.']
                    for message in record.get('messages',[])[-32:]:
                        if message.get('role') in {'user','assistant'}:
                            lines.extend(['\n'+('You' if message['role']=='user' else 'ERSELMETZ AI')+' ('+message['status']+')',message['content']])
                    box.setPlainText('\n'.join(lines)[-65536:]);self.tab_changed()
                def missing(error,chat=chat,box=box):
                    if self.closed or box not in self.chats:return
                    chat.conversation='';chat.workspace='';chat.read_only=False;chat.title_pending=True
                    box.setPlainText('Previous chat was not retained, expired, removed or unavailable. This is a new empty chat. No model request, approval, capture or tool action was replayed.')
                    self.tab_changed()
                self.manager.submit(lambda chat=chat:self.manager.transport.history(chat,generation=self.native_generation),loaded,missing)
        self.tabs.setCurrentIndex(descriptor['selected']);self.tabs.blockSignals(False);self.tab_changed()

    def rename_tab(self):
        if self.busy or self.feeding:return
        box=self.tabs.currentWidget();chat=self.chats.get(box)
        if chat is None:return
        dialog=QInputDialog(self);dialog.setWindowTitle('Rename chat');dialog.setLabelText('Chat name (up to 120 characters)')
        dialog.setTextValue(chat.title);dialog.findChild(QLineEdit).setMaxLength(120)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted;title=dialog.textValue();dialog.deleteLater()
        if not accepted:return
        from app.application.services.chat_history import validate_title
        try:title=validate_title(title)
        except ValueError:
            self.status.setText('Use 1–120 characters without control characters.');return
        def changed(result=None):
            if self.closed:return
            chat.title=title;chat.title_pending=not bool(chat.conversation);index=self.tabs.indexOf(box)
            if index>=0:
                from html import escape
                self.tabs.setTabText(index,title.replace('&','&&'));self.tabs.setTabToolTip(index,'<qt>'+escape(title)+'</qt>')
            self.busy=False;self.tabs.setEnabled(True);self.status.setText('Chat renamed.')
        if not chat.conversation:changed();return
        self.busy=True;self.tabs.setEnabled(False);generation=self.native_generation
        def failed(error):self.busy=False;self.tabs.setEnabled(True);self.status.setText('Rename was not confirmed. Refresh before trying again; nothing was retried automatically.')
        self.manager.submit(lambda:self.manager.transport.rename(chat,title,generation=generation),changed,failed)

    def ask_delete_chat(self):
        if self.busy or self.feeding:return
        box=self.tabs.currentWidget();chat=self.chats.get(box)
        if chat is None:return
        if self.delete_frame is None:
            self.delete_frame=QFrame();self.delete_frame.setObjectName('panel');layout=QVBoxLayout(self.delete_frame)
            self.delete_caption=label('');layout.addWidget(self.delete_caption)
            row=QHBoxLayout();layout.addLayout(row);row.addWidget(button('Confirm delete',self.confirm_delete_chat));row.addWidget(button('Cancel',self.dismiss_delete))
            self.chat_layout.insertWidget(2,self.delete_frame)
        self.pending_delete=box
        self.delete_caption.setText('Delete “'+chat.title+'” and any saved history for it? Separately retained Brain notes and Tasks are kept.')
        self.delete_frame.show()

    def dismiss_delete(self):
        self.pending_delete=None
        if self.delete_frame:self.delete_frame.hide()

    def confirm_delete_chat(self):
        box=self.pending_delete;chat=self.chats.get(box);self.dismiss_delete()
        if chat is None or self.busy or self.feeding:return
        def removed(result=None):
            if self.closed:return
            self.chats.pop(box,None);index=self.tabs.indexOf(box)
            if index>=0:self.tabs.removeTab(index)
            box.deleteLater();self.busy=False;self.tabs.setEnabled(True)
            if not self.tabs.count():self.new_tab()
            self.status.setText('Chat deleted. No request was sent to a model.')
        if not chat.conversation:removed();return
        self.busy=True;self.tabs.setEnabled(False);generation=self.native_generation
        def failed(error):self.busy=False;self.tabs.setEnabled(True);self.status.setText('Deletion was not confirmed. Refresh before retrying; nothing was retried automatically.')
        self.manager.submit(lambda:self.manager.transport.delete(chat,generation=generation),removed,failed)

    def selection_changed(self):
        if not hasattr(self, 'tabs'): return
        if self.busy:return
        chat = self.current()
        if chat is None: return
        selection = (self.model.currentData() or '', self.agent.currentData() or 'local_worker', self.project.currentData() or '')
        if selection == (chat.model, chat.agent, chat.project): return
        if chat.conversation: self.new_tab()
        else: chat.model, chat.agent, chat.project = selection

    def thinking_mode(self, enabled):
        self.thinking.setEnabled(enabled)
        if not enabled:self.thinking.setChecked(False)
        for widget in (self.ask_first,self.step_limit,self.context_size):
            widget.setEnabled(enabled)
            widget.setToolTip('Applies to the bounded Agent tool loop.')

    def trim_activity(self, *args):
        while self.steps.count()>200:self.steps.takeItem(0)

    def tab_changed(self):
        chat = self.current()
        if chat is None: return
        self.send_button.setEnabled(not self.busy and not chat.read_only);self.composer.setEnabled(not chat.read_only)
        if chat.read_only:self.status.setText('Restored history · read-only · open a new chat to send. No action was replayed.')
        for widget, value in [(self.model, chat.model), (self.agent, chat.agent), (self.project, chat.project)]:
            widget.blockSignals(True); index = widget.findData(value)
            if value and index<0:widget.addItem(value+' (unavailable)',value);index=widget.count()-1
            if index >= 0: widget.setCurrentIndex(index)
            widget.blockSignals(False)

    def refresh(self):
        if not self.native_id:
            if self.registering:return
            self.registering=True
            def registered(data):
                self.registering=False;self.native_id=data['id'];self.native_generation=data.get('generation',0)
                if self.closed:
                    self.manager.submit(lambda:self.manager.session.request('DELETE','/api/native/windows/'+self.native_id),lambda result:None,control=True);return
                for chat in self.chats.values():chat.window_id=self.native_id;chat.window_generation=self.native_generation
                self.refresh()
            def failed(error):self.registering=False;self.offline(error)
            hwnd=int(self.winId())
            self.manager.submit(lambda:self.manager.session.request('POST','/api/native/windows',{'client_id':self.client_id,'hwnd':hwnd}),registered,failed,control=True)
            return
        self.status.setText('Checking local models…')
        self.refresh_version+=1;version=self.refresh_version
        self.manager.submit(lambda:self.manager.transport.catalog(self.native_id),
            lambda data:self.loaded(data) if version==self.refresh_version else None,
            lambda error:self.offline(error) if version==self.refresh_version else None)

    def loaded(self, data):
        if self.closed:
            if data.get('window_id'):self.manager.submit(lambda:self.manager.session.request('DELETE','/api/native/windows/'+data['window_id']),lambda result:None,control=True)
            return
        self.native_id=data['window_id']
        if data.get('window_generation') is not None:self.native_generation=data['window_generation']
        for chat in self.chats.values():chat.window_id=self.native_id;chat.window_generation=self.native_generation
        self.manager.catalog = data
        self.available_models={record['name'] for record in data['models']}
        current = self.current()
        if self.pending_restore is not None:
            selected=self.pending_restore['tabs'][self.pending_restore['selected']]
            current.model,current.agent,current.project=(selected[key] for key in ('model','agent','project'))
        for widget, records, key, default in [(self.model, data['models'], 'name', current.model),
                (self.agent, data['agents'], 'id', current.agent), (self.project, data['projects'], 'id', current.project)]:
            widget.blockSignals(True); widget.clear()
            if widget is self.project: widget.addItem('No project', '')
            for record in records: widget.addItem(record.get('name', record[key]), record[key])
            index = widget.findData(default)
            if default and index<0:
                widget.addItem(default+' (unavailable)',default);index=widget.count()-1
            if index >= 0: widget.setCurrentIndex(index)
            widget.blockSignals(False)
        self.selection_changed()
        self.selection_hint.setText('Selections apply to this conversation. Changing an existing conversation starts a new tab.')
        self.status.setText('Ready · local model' if data['models'] else 'No local chat model found. Install one in Ollama, then Refresh.')
        if data.get('model_offline'):self.status.setText('Ollama is offline or its models could not be checked. Retained history is still available; Refresh models after recovery.')
        if self.pending_restore is not None:
            descriptor=self.pending_restore;self.pending_restore=None;self.restore_tabs(descriptor)
        if self.window_stopped:self.stop_window(force=True)

    def show_runtime(self,data):
        self.global_stopped=data.get('global_stopped',False) or self.manager.pending_global_stop
        state=next((w for w in data.get('windows',[]) if w['id']==self.native_id),None)
        if state:
            self.window_stopped=state.get('window_stopped',state['stopped']) or self.pending_stop;self.native_generation=state['generation']
            for chat in self.chats.values():chat.window_generation=self.native_generation
        if self.window_stopped or self.global_stopped:self.capture_controls.stop();self.knowledge_review.stop();self.desktop_controls.stop()
        self.stop_button.setText('Resume' if self.window_stopped else 'Stop')
        self.stop_button.setEnabled(not self.global_stopped)
        self.brain.window_stop.setText(self.stop_button.text());self.brain.window_stop.setEnabled(not self.global_stopped)
        operations=[o for o in data.get('operations',[]) if o['window_id']==self.native_id]
        lines=[]
        if self.manager.pending_global_stop:lines.append('Global stop requested; backend confirmation is pending.')
        elif self.global_stopped:lines.append('All protected work is stopped. Resume new work in Settings.')
        elif self.pending_stop:lines.append('Window stop requested; backend confirmation is pending.')
        elif self.window_stopped:lines.append('This window is stopped. Resume allows new requests only.')
        for item in operations:
            label_text={'waiting':'Queued','running':'Running','stopping':'Stop requested; waiting for release'}.get(item['state'],'Request')
            lines.append(label_text+' · '+item['model'])
        captures=data.get('capture',[])
        if captures:
            ours=[lease['kind'] for lease in captures if lease['window_id']==self.native_id]
            lines.append('Capture here: '+', '.join(ours) if ours else 'Another chat window owns capture.')
        elif data.get('other_capture_active'):lines.append('Another session owns capture.')
        if not lines:lines.append('No model request waiting · capture idle')
        if any(item['provider']!='desktop' for item in operations):lines.append(data['reload_notice'])
        self.queue_status.setText('\n'.join(lines))

    def stop_window(self, *, force=False):
        if self.window_stopped and not force:
            if not self.native_id:return
            self.manager.submit(lambda:self.manager.session.request('POST','/api/native/windows/'+self.native_id+'/resume',{'confirmed':True}),
                lambda result:self.resumed(result),lambda error:self.status.setText('Could not resume this window.'),control=True)
            return
        self.window_stopped=True;self.pending_stop=True;self.stop_event.set();self.feed_stop.set()
        self.capture_controls.stop()
        self.knowledge_review.stop()
        self.desktop_controls.stop()
        if self.pending_tool is not None:self.finish_tool_review(False)
        self.status.setText('Stop requested. Waiting for active work to release; no further action is allowed.')
        if self.native_id:
            def confirmed(result):self.pending_stop=False;self.manager.poll_queue()
            self.manager.submit(lambda:self.manager.session.request('POST','/api/native/windows/'+self.native_id+'/stop'),
                confirmed,lambda error:self.status.setText('Stop could not reach the backend. Close the app if it remains unresponsive.'),control=True)

    def resumed(self,result):
        self.native_generation=result['generation'];self.window_stopped=False;self.pending_stop=False
        for chat in self.chats.values():chat.window_generation=self.native_generation
        self.manager.poll_queue()

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

    def send(self, *, math_tool=None,knowledge=None):
        if self.busy or self.feeding: return
        if self.window_stopped or self.global_stopped:
            self.status.setText('Resume new work before sending. Cancelled requests will not replay.');return
        text = self.composer.toPlainText().strip() if math_tool is None else 'Exact math: '+', '.join(str(v) for k,v in math_tool.items() if k!='kind')
        chat = self.current()
        if chat.read_only:self.status.setText('Restored history is read-only. Open a new chat to send.');return
        if not text: return
        chat.reply_seconds=self.reply_limit.currentData()
        if math_tool is None:
            from app.native_io import url_intent,NativeIOError
            try:destination=url_intent(text)
            except NativeIOError:
                self.status.setText('Only an exact http or https destination can be opened. Nothing was sent.');return
            if destination:
                self.send_url(chat,text,destination);return
        if not chat.model:
            self.status.setText('Choose an installed local model first.'); return
        if chat.model not in self.available_models:
            self.status.setText('This model is unavailable. Refresh or explicitly choose another installed model. Nothing was sent.');return
        if len(text.encode('utf-8')) > 8192:
            self.status.setText('That message is too long. Send a shorter message.'); return
        if math_tool is None and self.use_brain.isChecked() and knowledge is None:
            self.knowledge_review.prepare(chat,text);return
        if math_tool is None and self.agent_loop.isChecked():
            from app.knowledge.shipped_pack import shipped_pack
            if knowledge is not None or shipped_pack().instant(text) is None:
                self.send_agent(chat,text,knowledge=knowledge);return
        self.busy = True; self.response_error = False; self.stop_event.clear()
        if math_tool is None:self.composer.clear()
        if math_tool is None:chat.last_local_prompt=text
        for widget in [self.model, self.agent, self.project, self.tabs]: widget.setEnabled(False)
        self.send_button.setEnabled(False)
        self.append(f'\n\nYou\n{text}\n\nERSELMETZ AI\n')
        self.brain.scene.highlights.clear();self.brain.scene.update()
        from app.knowledge.shipped_pack import shipped_pack
        local_reply=math_tool is not None or (knowledge is None and shipped_pack().instant(text) is not None)
        self.status.setText('Answering locally · no model call' if local_reply else f'Local · {chat.model} · replying…')
        self.steps.addItem('Reviewed local math or exact-match reply; no model call.' if local_reply else 'Sending this message to the selected local model with shipped general guidance.')
        emit = lambda event: self.manager.work.event.emit(self, event)
        self.manager.submit(lambda generation=self.native_generation: self.manager.transport.send_math(chat,text,math_tool,emit,generation=generation) if math_tool is not None else self.manager.transport.send(chat, text, self.stop_event, emit,generation=generation,knowledge=knowledge),
                            lambda result: self.done(cancelled=self.stop_event.is_set()), self.failed,model=True)

    def send_url(self,chat,text,url):
        if not self.native_id:
            self.status.setText('Wait for the local workspace before opening a link.');return
        generation=self.native_generation;self.stop_event.clear();self.busy=True;self.response_error=False
        self.composer.clear()
        for widget in [self.model,self.agent,self.project,self.tabs,self.send_button]:widget.setEnabled(False)
        self.append('\n\nYou\n'+text+'\n\nERSELMETZ AI\n')
        self.status.setText('Preparing the exact browser destination · no model call')
        self.manager.submit(lambda:self.manager.transport.prepare_tool(chat,text,'open_url',{'url':url},generation=generation),
            lambda action:self.show_tool_review(chat,generation,action),self.failed)

    def permit_tool_folder(self):
        if self.busy or self.feeding or self.window_stopped or self.global_stopped:return
        chat=self.current()
        if not chat.model:self.status.setText('Choose an installed local model before choosing its tool folder.');return
        path=QFileDialog.getExistingDirectory(self,'Permit file tools in this folder; writes still need exact diff approval')
        if not path:return
        generation=self.native_generation;self.busy=True;self.send_button.setEnabled(False)
        def permitted(result):
            self.done();self.status.setText('Permitted local folder: '+result['name']+' · writes still need exact diff approval.')
            self.steps.addItem('Owner chose a tool folder; no file was read or written.')
        self.manager.submit(lambda:self.manager.transport.grant_root(chat,path,generation=generation),permitted,self.failed)

    def send_agent(self,chat,text,*,knowledge=None):
        if not self.native_id:return
        generation=self.native_generation;self.stop_event.clear();self.busy=True;self.response_error=False
        self.composer.clear()
        for widget in [self.model,self.agent,self.project,self.tabs,self.send_button]:widget.setEnabled(False)
        self.append('\n\nYou\n'+text+'\n\nERSELMETZ AI\n')
        body={'text':text,'max_steps':self.step_limit.value(),'num_ctx':int(self.context_size.currentText()),
              'thinking':self.thinking.isChecked(),'ask_first':self.ask_first.isChecked()}
        if knowledge is not None:body.update(knowledge)
        def start():
            if not chat.conversation:self.manager.transport.start(chat,generation=generation)
            return self.manager.transport.agent_api(chat,body={**body,'conversation_id':chat.conversation},generation=generation)
        self.status.setText('Running a bounded local Agent step; tool requests still require policy and approval.')
        self.manager.submit(start,lambda result:self.agent_result(chat,generation,result),self.failed,model=True)

    def agent_result(self,chat,generation,result):
        if self.closed:return
        if result.get('retrieval') and result.get('steps',0)>0:
            self.receive({'type':'complete','context_trace':{'retrieval':result['retrieval']}})
        for line in result.get('observed',[]):self.steps.addItem(line)
        if result.get('thinking'):
            self.steps.addItem('Actual model thinking (not a tool result):\n'+result['thinking'])
        if result['state']=='review' and result.get('action'):
            self.pending_run=(chat,generation,result['id']);self.show_tool_review(chat,generation,result['action']);return
        self.pending_run=None
        self.append(result.get('answer','No final answer was confirmed.'))
        if result.get('receipts') and result['state']!='completed':
            self.append('\nObserved tool results:\n'+'\n'.join(receipt['message'] for receipt in result['receipts']))
        if any(receipt.get('brain_changed') for receipt in result.get('receipts',[])):self.manager.refresh_brain()
        self.done(cancelled=self.stop_event.is_set());self.status.setText('Agent turn: '+result['state']+' · '+str(result['steps'])+' bounded steps')

    def show_tool_review(self,chat,generation,action):
        if self.closed:return
        if self.stop_event.is_set() or generation!=self.native_generation:
            if self.pending_run is not None:
                run_id=self.pending_run[2];self.pending_run=None
                self.manager.submit(lambda:self.manager.transport.agent_api(chat,'/'+run_id+'/cancel',generation=self.native_generation),lambda result:None,lambda error:None,control=True)
            else:self.manager.submit(lambda:self.manager.transport.tool_api(chat,'POST','/'+action['id']+'/deny',generation=self.native_generation),lambda result:None,lambda error:None,control=True)
            self.done(cancelled=True);return
        if self.tool_frame is None:
            self.tool_frame=QFrame();self.tool_frame.setObjectName('panel');layout=QVBoxLayout(self.tool_frame)
            self.tool_summary=label('');layout.addWidget(self.tool_summary)
            self.tool_details=QPlainTextEdit();self.tool_details.setReadOnly(True);self.tool_details.setAccessibleName('Exact tool action for approval');self.tool_details.setMaximumHeight(140);layout.addWidget(self.tool_details)
            row=QHBoxLayout();layout.addLayout(row)
            row.addWidget(button('Approve once',lambda:self.finish_tool_review(True)))
            row.addWidget(button('Cancel action',lambda:self.finish_tool_review(False)))
            self.chat_layout.insertWidget(2,self.tool_frame)
        self.pending_tool=(chat,generation,action);self.tool_summary.setText(action['summary']);self.tool_details.setPlainText(action['details']);self.tool_frame.show()
        self.status.setText('Review this exact tool proposal. The proposed action has not run.')
        self.steps.addItem('Tool proposed; waiting for your exact approval.')

    def finish_tool_review(self,approved):
        pending=self.pending_tool
        if pending is None:return
        chat,generation,action=pending;self.pending_tool=None;self.tool_frame.hide()
        current_generation=self.native_generation
        if self.stop_event.is_set() or generation!=current_generation:approved=False
        if self.pending_run is not None:
            _,_,run_id=self.pending_run
            suffix='/'+run_id+('/advance' if approved else '/cancel')
            body={'confirmed_digest':action['approval_digest']} if approved else {}
            self.manager.submit(lambda:self.manager.transport.agent_api(chat,suffix,body,generation=current_generation),
                lambda result:self.agent_result(chat,current_generation,result),self.failed,control=not approved,model=approved)
            return
        suffix='/'+action['id']+('/execute' if approved else '/deny')
        body={'confirmed_digest':action['approval_digest']} if approved else {}
        def finished(result):
            if self.closed:return
            outcome=result.get('result') or {};self.append(outcome.get('message','The tool result was not confirmed.'))
            self.steps.addItem(outcome.get('message','Tool result unverified.'))
            if outcome.get('brain_changed'):self.manager.refresh_brain()
            self.done(cancelled=self.stop_event.is_set())
            self.status.setText('Tool result: '+result['state']+' · no model call')
        self.manager.submit(lambda:self.manager.transport.tool_api(chat,'POST',suffix,body,generation=current_generation),finished,self.failed,control=not approved,model=approved)

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
        if event.get('type')=='complete' and event.get('context_trace'):
            endpoint=event['context_trace'].get('endpoint')
            if endpoint:
                self.steps.addItem('How I answered · Router-reported '+str(endpoint.get('served_provider') or 'unknown provider')+' / '+str(endpoint.get('served_model') or 'unknown model')+' · '+str(endpoint.get('latency_ms'))+' ms · app retries '+str(endpoint.get('retries',0))+'; upstream retries unknown.')
            retrieval=event['context_trace'].get('retrieval',{})
            if retrieval.get('enabled'):
                ids={item['memory_id'] for item in retrieval.get('returned_chunks',[])}
                self.brain.scene.highlights.update(node['id'] for node in self.brain.scene.raw if node.get('record_id') in ids)
                self.brain.scene.update();self.steps.addItem('Used '+str(len(ids))+' actual private Brain records for this message.')

    def done(self, *, cancelled=False):
        if self.closed: return
        self.busy = False
        for widget in [self.model, self.agent, self.project, self.tabs, self.send_button]: widget.setEnabled(True)
        if cancelled:
            self.status.setText('Request ended after Stop. Inspect any results already returned; nothing was replayed.')
            self.steps.addItem('Request ended after Stop; no automatic retry.')
        elif self.window_stopped or self.global_stopped:
            self.status.setText('This window remains stopped. Resume permits new requests only.')
        elif self.response_error:
            self.status.setText('The reply failed. Check your model before trying again.')
            self.steps.addItem('The response failed. No success was assumed.')
        else:
            self.status.setText('Ready · local'); self.steps.addItem('Response finished.')

    def failed(self, error):
        if self.closed: return
        self.response_error=True
        if self.stop_event.is_set():
            self.done(cancelled=True);return
        self.done(); self.status.setText('Could not finish this reply. Check the model and try again. Nothing was retried automatically.')
        if str(error).startswith('Selected knowledge changed after preview'):
            self.status.setText('A selected source changed after review. Review your Brain again before sending; nothing was retried.')
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
        if not self.native_id or self.window_stopped or self.global_stopped:
            self.status.setText('Wait for the workspace, or Resume new work before saving.');return
        if self.busy or self.feeding: return
        self.dismiss_feed(); self.feeding=True; self.feed_stop.clear(); self.cancel_feed_button.setEnabled(True); self.send_button.setEnabled(False)
        window_id=self.native_id
        generation=self.native_generation
        def work():
            sources=files if text is None else [None]; results=[]
            for path in sources:
                if self.feed_stop.is_set(): break
                try:
                    result=self.manager.transport.feed_text(window_id,text,self.feed_stop,generation=generation) if path is None else self.manager.transport.feed_file(window_id,path,self.feed_stop,generation=generation)
                    state=result['state']; name='Note' if path is None else path.name
                    message=f'{name}: unchanged, skipped.' if state=='unchanged' else f"{name}: saved {result['chunks']} chunks"+(' (keyword search; local embeddings unavailable).' if state=='lexical-ready' else '.')
                except Exception:
                    message=('Feed stopped; inspect Brain for any save already completed.' if self.feed_stop.is_set() else (str(path.name) if path else 'Note')+': save not confirmed; refresh Brain before trying again.')
                results.append(message); self.manager.work.event.emit(self,{'type':'brain-progress','text':message})
            return results
        self.manager.submit(work,self.feed_done,lambda error:self.feed_done([]),model=True)

    def feed_done(self,results):
        if self.closed: return
        self.feeding=False; self.cancel_feed_button.setEnabled(False); self.send_button.setEnabled(True)
        self.status.setText('Feed cancelled.' if self.feed_stop.is_set() else 'Feed finished. See the result for each selected source.')
        self.manager.refresh_brain()

    def cancel_feed(self):
        self.feed_stop.set(); self.status.setText('Cancellation requested. No further files will start; results show any files already saved.')
        self.manager.submit(lambda:self.manager.transport.cancel_feed(self.native_id),lambda result:None,lambda error:None,control=True)

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
        generation=self.native_generation
        def found(result):
            if self.closed or self.brain.search.text()!=input_snapshot: return
            self.brain.scene.highlights={hit['id'] for hit in result['hits']}; self.brain.scene.update()
            self.brain.show_hits(result['hits'])
            self.steps.addItem(f"Brain search: {len(result['hits'])} actual matches ({'keyword search' if result['mode']=='lexical' else 'local embeddings'}).")
        self.manager.submit(lambda:self.manager.session.request('POST','/api/memory/owner/native-recall',{'query':query},window=self.native_id,generation=generation),found,
                            lambda error:self.status.setText('Brain search did not complete. Check your local model and try again.'),model=True)

    def toggle_full_brain(self):
        if self.full_brain is not None: self.full_brain.close(); return
        dialog=QDialog(self); dialog.setWindowTitle('Brain · ERSELMETZ AI'); dialog.resize(1200,800)
        self.full_brain=dialog; self.brain_container.removeWidget(self.brain); QVBoxLayout(dialog).addWidget(self.brain)
        self.brain.setProperty('fullWindow',True); self.brain.full.setText('Back')
        self.brain.window_stop.show();self.brain.global_stop.show()
        def restore(result):
            dialog.layout().removeWidget(self.brain); self.brain.setParent(self.brain_container.parentWidget()); self.brain_container.insertWidget(0,self.brain,3)
            self.brain.setProperty('fullWindow',False); self.brain.full.setText('Open Brain'); self.brain.show(); self.full_brain=None; dialog.deleteLater()
            self.brain.window_stop.hide();self.brain.global_stop.hide()
        dialog.finished.connect(restore); dialog.showMaximized(); self.brain.setFocus()

    def closeEvent(self, event):
        if self.busy or self.feeding:
            self.status.setText('Wait for this reply to finish before closing this window.'); event.ignore(); return
        if self.capture_controls.lease is not None:
            self.status.setText('Use Release capture to confirm device ownership release before closing.');event.ignore();return
        self.capture_controls.stop()
        self.knowledge_review.stop()
        self.desktop_controls.stop()
        if self.full_brain: self.full_brain.close()
        self.feed_stop.set()
        self.brain.scene.timer.stop()
        self.closed = True; self.manager.remove(self); event.accept()
        if self.native_id:self.manager.submit(lambda:self.manager.session.request('DELETE','/api/native/windows/'+self.native_id),lambda result:None,control=True)
