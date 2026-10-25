"""Three resizable panes with independent chat windows over one backend."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import webbrowser

from PySide6.QtCore import QObject, Signal, Slot, Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QComboBox, QTabWidget, QTextBrowser, QPlainTextEdit,
    QScrollArea, QCheckBox, QInputDialog, QMessageBox, QListWidget, QFrame)

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
        self.work = Work(); self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='qt-api')
        self.work.finished.connect(self.finished)
        self.work.event.connect(self.handle_event)
        self.preferences = QSettings('ERSELMETZ AI', 'Native shell')
        self.reduced_motion = self.preferences.value('reducedMotion', False, type=bool)
        apply_theme(app, self.preferences.value('lightTheme', False, type=bool))

    def submit(self, callback, accepted, failed=None):
        def work():
            try: result, error = callback(), None
            except Exception as exc: result, error = None, exc
            self.work.finished.emit((accepted, failed), result, error)
        self.pool.submit(work)

    @Slot(object, object)
    def handle_event(self, target, event):
        if not target.closed: target.receive(event)

    @Slot(object, object, object)
    def finished(self, callbacks, result, error):
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

    def remove(self, window):
        if window in self.windows: self.windows.remove(window)
        if not self.windows:
            for dialog in self.dialogs.values(): dialog.close()
            self.app.quit()

    def shutdown(self):
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
        self.stop_event = threading.Event(); self.chats = {}; self.sidebar_visible = True
        self.setWindowTitle('ERSELMETZ AI'); self.resize(1360, 820); self.setMinimumSize(800, 580)
        root, layout = column(); self.setCentralWidget(root)
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
        for title in ['Feed file', 'Feed folder']:
            control = button(title, lambda: manager.show_dialog('Advanced'))
            control.setToolTip('Open Brain settings in Advanced to add documents. Native file intake is being connected.')
            side.addWidget(control)
        side.addWidget(button('Add note', self.add_note))
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
        self.brain_empty = label('Brain\n\nYour retained knowledge appears here. Open Brain settings to inspect or remove it.')
        self.brain_empty.setAlignment(Qt.AlignmentFlag.AlignCenter); center_layout.addWidget(self.brain_empty, 3)
        center_layout.addWidget(label('OBSERVED STEPS'))
        self.steps = QListWidget(); self.steps.setAccessibleName('Observed activity'); center_layout.addWidget(self.steps, 2)
        self.steps.addItem('Ready. No action has run.')
        right, chat_layout = column(); self.splitter.addWidget(right)
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

    def current(self): return self.chats.get(self.tabs.currentWidget())

    def new_tab(self):
        if self.busy: return
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
            self.status.setText('Ollama is unavailable. Start Ollama, then Refresh installed models. Your chat stays here.')
            self.selection_hint.setText('Offline · no model was downloaded or substituted.')

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible; self.sidebar.setVisible(self.sidebar_visible)
        if not self.sidebar_visible: self.splitter.setSizes([0, 500, 500])
        else: self.splitter.setSizes([230, 500, 500])

    def append(self, text):
        box = self.tabs.currentWidget(); cursor = box.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text); box.setTextCursor(cursor); box.ensureCursorVisible()

    def send(self):
        if self.busy: return
        text = self.composer.toPlainText().strip(); chat = self.current()
        if not text: return
        if not chat.model:
            self.status.setText('Choose an installed local model first.'); return
        if len(text.encode('utf-8')) > 16000:
            self.status.setText('That message is too long. Send a shorter message.'); return
        self.busy = True; self.response_error = False; self.stop_event.clear(); self.composer.clear()
        for widget in [self.model, self.agent, self.project, self.tabs]: widget.setEnabled(False)
        self.send_button.setEnabled(False)
        self.append(f'\n\nYou\n{text}\n\nERSELMETZ AI\n')
        self.status.setText(f'Local · {chat.model} · replying…'); self.steps.addItem('Sending this message to the selected local model.')
        emit = lambda event: self.manager.work.event.emit(self, event)
        self.manager.submit(lambda: self.manager.transport.send(chat, text, self.stop_event, emit),
                            lambda result: self.done(), self.failed)

    def receive(self, event):
        if event.get('type') == 'chunk': self.append(event.get('text', ''))
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
        if QMessageBox.question(self, 'Save local note', 'Save this note in your owner Brain for 30 days? It can be removed in Brain settings.') != QMessageBox.StandardButton.Yes: return
        body = {'content': content, 'source_name': 'Owner note', 'retention_opt_in': True,
                'expires_at': (datetime.now(timezone.utc)+timedelta(days=30)).isoformat()}
        self.manager.submit(lambda: self.manager.session.request('POST', '/api/memory/owner', body),
            lambda result: self.steps.addItem('Saved your note locally with 30-day retention.'),
            lambda error: self.status.setText('The note was not saved. Open Brain settings to check retention and limits.'))

    def closeEvent(self, event):
        if self.busy:
            self.status.setText('Wait for this reply to finish before closing this window.'); event.ignore(); return
        self.closed = True; self.manager.remove(self); event.accept()
