"""Native searchable records, typed forms and guarded owner actions. No HTML UI."""
import importlib
import hashlib
from pathlib import Path
from urllib.parse import quote
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QLineEdit,QPlainTextEdit,QTextBrowser,QPushButton,QTableWidget,QTableWidgetItem,
    QSplitter,QScrollArea,QWidget,QCheckBox,QComboBox,QSpinBox,QDialogButtonBox,
    QFileDialog,QMessageBox,QAbstractItemView)
from .page_schema import PAGES

def caption(key):return key.replace('_',' ').capitalize()
def text(value,depth=0):
    if depth>8:return 'Further detail omitted.'
    if isinstance(value,dict):return '\n\n'.join(caption(k)+': '+text(v,depth+1) for k,v in value.items() if k not in {'csrf','api_key','password','credential','token'})
    if isinstance(value,list):return '\n'.join('• '+text(v,depth+1) for v in value[:500]) or 'None'
    if isinstance(value,bool):return 'Yes' if value else 'No'
    return 'Unknown' if value is None else str(value)[:64000]

def push(title,callback):
    b=QPushButton(title);b.setAccessibleName(title);b.clicked.connect(callback);return b

class OfflineText(QTextBrowser):
    """Never fetch Markdown images or follow app/document hyperlinks."""
    def __init__(self):
        super().__init__();self.setOpenLinks(False);self.setOpenExternalLinks(False)
    def loadResource(self,kind,url):return None

class Fields(QWidget):
    def __init__(self,schema,defs=None,values=None,depth=0):
        super().__init__();self.schema=schema;self.defs=defs or schema.get('$defs',{});self.entries={};self.required=set(schema.get('required',[]));form=QFormLayout(self)
        for key,s in schema.get('properties',{}).items():
            if '$ref' in s:s=self.defs[s['$ref'].split('/')[-1]]
            if 'anyOf' in s:s=next((x for x in s['anyOf'] if x.get('type')!='null'),s)
            value=(values or {}).get(key,s.get('default'))
            typ=s.get('type','string')
            if s.get('enum'):
                w=QComboBox();w.addItems([str(v) for v in s['enum']]);w.setCurrentText(str(value or s['enum'][0]))
            elif typ=='boolean':w=QCheckBox('Explicitly allow');w.setChecked(value is True)
            elif typ=='integer':
                w=QSpinBox();w.setRange(max(-2147483647,s.get('minimum',0)),min(2147483647,s.get('maximum',1000000)));w.setValue(value if isinstance(value,int) else s.get('minimum',0))
            elif typ=='array' and ('$ref' in s.get('items',{}) or s.get('items',{}).get('type')=='object'):
                child=s['items'];child=self.defs[child['$ref'].split('/')[-1]] if '$ref' in child else child
                w=Fields(child,self.defs,depth=depth+1);typ='object_array'
            elif typ=='array':
                w=QPlainTextEdit();w.setMaximumHeight(100);w.setPlaceholderText('One entry per line');w.setPlainText('\n'.join(value or []))
            else:
                w=QLineEdit();w.setMaxLength(s.get('maxLength',4096));w.setText('' if value is None else str(value))
                if any(part in key for part in ('key','password','passphrase')):w.setEchoMode(QLineEdit.EchoMode.Password)
            w.setAccessibleName(caption(key));form.addRow(caption(key)+(' *' if key in self.required else ''),w);self.entries[key]=(w,typ,s)
    def values(self):
        result={}
        for k,(w,typ,s) in self.entries.items():
            if isinstance(w,QCheckBox):v=w.isChecked()
            elif isinstance(w,QComboBox):v=w.currentText()
            elif isinstance(w,QSpinBox):v=w.value()
            elif isinstance(w,Fields):v=[w.values()]
            elif isinstance(w,QPlainTextEdit):v=[line.strip() for line in w.toPlainText().splitlines() if line.strip()]
            else:v=w.text()
            if v=='' and k not in self.required:continue
            result[k]=v
        return result
    def erase(self):
        for w,typ,s in self.entries.values():
            if isinstance(w,QLineEdit) and w.echoMode()==QLineEdit.EchoMode.Password:w.clear()

class RecordWindow(QDialog):
    def __init__(self,manager,title):
        super().__init__();self.manager=manager;self.page=PAGES[title];self.rows=[];self.selected=None;self.loading=False
        self.setWindowTitle(title+' · ERSELMETZ AI');self.resize(960,700);self.setMinimumSize(600,450)
        layout=QVBoxLayout(self);heading=QLabel(title);heading.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(heading)
        self.search=QLineEdit();self.search.setPlaceholderText('Search records');self.search.setAccessibleName('Search '+title);layout.addWidget(self.search)
        self.search.textChanged.connect(self.filter)
        split=QSplitter();layout.addWidget(split,1)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['Name / title','Status / type','Identifier']);self.table.setAccessibleName(title+' records');self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setWordWrap(True);split.addWidget(self.table)
        self.detail=OfflineText();self.detail.setAccessibleName(title+' detail');split.addWidget(self.detail);split.setSizes([440,500])
        self.table.itemSelectionChanged.connect(self.inspect)
        self.status=QLabel('Loading…');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        actions=QWidget();buttons=QVBoxLayout(actions)
        buttons.addWidget(push('Refresh',lambda:self.refresh()))
        self.action_buttons=[]
        for action in self.page.actions:
            b=push(action.title,lambda checked=False,a=action:self.action(a));buttons.addWidget(b);self.action_buttons.append(b)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMaximumHeight(190);scroll.setWidget(actions);layout.addWidget(scroll)
        layout.addWidget(push('Close',self.close));self.refresh()
    def refresh(self,action_result=None):
        if self.loading:return
        selected_id=(self.selected or {}).get('id')
        self.loading=True;self.status.setText('Loading protected records…')
        def done(data):
            self.loading=False;self.selected=None
            if isinstance(data,list):rows=data
            elif isinstance(data,dict):
                rows=next((data[k] for k in ['items','nodes','packs','entries','workflows','positions'] if isinstance(data.get(k),list)),[data])
            else:rows=[{'value':data}]
            self.rows=[dict(v,id=v.get('id',v.get('approval_id',v.get('pack_id',v.get('document_id',v.get('grant_id',v.get('capability_id',''))))))) if isinstance(v,dict) else {'name':v} for v in rows[:1000]];self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                for j,value in enumerate([row.get('name',row.get('title',row.get('event','Record'))),row.get('state',row.get('status',row.get('kind',''))),row.get('id',row.get('agent_id',''))]):self.table.setItem(i,j,QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents();self.status.setText('No records yet.' if not self.rows else str(len(self.rows))+' records. Select one for details.');self.filter()
            if self.rows:
                index=next((i for i,row in enumerate(self.rows) if row.get('id')==selected_id),0)
                if action_result is None:self.table.selectRow(index)
                else:
                    self.table.blockSignals(True);self.table.selectRow(index);self.table.blockSignals(False)
                    self.selected=self.rows[index]
            if action_result is not None:
                self.show_detail(action_result)
                self.status.setText('Result: '+str(action_result.get('state','returned; review the details')) if isinstance(action_result,dict) else 'Request returned; review the details.')
        self.manager.submit(lambda:self.manager.session.request('GET',self.page.endpoint),done,self.failed)
    def failed(self,error):
        self.loading=False;self.status.setText('Request not completed: '+str(error)[:600]);self.detail.setPlainText('No successful action is claimed. Check permission, provider state and Stop controls, then retry explicitly.')
    def filter(self):
        term=self.search.text().casefold()
        for i,row in enumerate(self.rows):self.table.setRowHidden(i,term not in text(row).casefold())
    def inspect(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):return
        self.selected=self.rows[index];self.detail_data=self.selected;self.show_detail(self.selected)
        if self.page.detail and self.selected.get('id'):
            chosen=self.selected
            self.manager.submit(lambda:self.manager.session.request('GET',self.page.detail.format(id=quote(str(chosen['id']),safe=''))),lambda data:self.show_detail(data) if self.selected is chosen else None,self.failed)
    def show_detail(self,data):
        self.detail_data=data
        if self.windowTitle().startswith('Documentation') and isinstance(data,dict):
            content=data.get('content')
            if isinstance(content,str):self.detail.setMarkdown(content);return
        self.detail.setPlainText(text(data))
    def action(self,action):
        if '{id}' in action.path and not (self.selected or {}).get('id'):
            self.status.setText('Select a record first.');return
        chosen={**(self.selected or {}),**(self.detail_data if isinstance(getattr(self,'detail_data',None),dict) else {})};chosen['confirmed_digest']='';path=action.path.format(id=quote(str(chosen.get('id','')),safe=''))
        dialog=QDialog(self);dialog.setWindowTitle(action.title);dialog.resize(620,620);layout=QVBoxLayout(dialog)
        notice=QLabel(action.notice+'\nSelected record: '+str(chosen.get('name',chosen.get('title',chosen.get('id','New record'))))+'\n'+str(chosen.get('action_summary',''))+'\nNon-loopback endpoints require explicit confirmation and HTTPS. Never paste secrets into prompts.');notice.setWordWrap(True);notice.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(notice)
        if action.dto:
            module,name=action.dto.split('.');model=getattr(importlib.import_module('app.api.'+module),name)
            fields=Fields(model.model_json_schema(),values={**chosen,**dict(action.defaults)})
        else:fields=Fields({'properties':{}})
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(fields);layout.addWidget(scroll)
        confirmed=QCheckBox('I reviewed the exact action and selected record');confirmed.setAccessibleName('Confirm '+action.title);layout.addWidget(confirmed)
        state=QLabel('');state.setWordWrap(True);state.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(state)
        submit=push('Confirm action',lambda:None);submit.setEnabled(False);confirmed.toggled.connect(submit.setEnabled);layout.addWidget(submit);layout.addWidget(push('Cancel',dialog.reject))
        def send():
            body=fields.values();submit.setEnabled(False);confirmed.setEnabled(False);fields.setEnabled(False)
            # Approval digest is never invented or silently substituted.
            self.manager.submit(lambda:self.manager.session.request(action.method,path,body if action.method!='GET' else None),done,fail)
        def done(result):
            fields.erase();dialog.accept();self.refresh(action_result=result)
        def fail(error):
            fields.erase();state.setText('Not completed: '+str(error)[:600]);fields.setEnabled(True);confirmed.setEnabled(True);confirmed.setChecked(False);submit.setEnabled(False)
        submit.clicked.connect(send);dialog.finished.connect(lambda _:fields.erase());dialog.open();self.action_dialog=dialog


class QuickProviderWindow(QDialog):
    """Simple owner setup for auto-detected Ollama and one optional Gemini key."""
    def __init__(self,manager):
        super().__init__();self.manager=manager;self.setWindowTitle('AI providers · ERSELMETZ AI');self.resize(620,540)
        layout=QVBoxLayout(self)
        heading=QLabel('AI providers');heading.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(heading)
        intro=QLabel('Ollama models are detected automatically. Add Gemini only when you choose; its key stays in memory and cloud turns still require consent.')
        intro.setWordWrap(True);intro.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(intro)
        self.local=QPlainTextEdit();self.local.setReadOnly(True);self.local.setAccessibleName('Detected Ollama models');self.local.setMaximumHeight(150);layout.addWidget(self.local)
        layout.addWidget(push('Detect Ollama models',self.refresh))
        layout.addWidget(QLabel('Optional Gemini'))
        self.key=QLineEdit();self.key.setEchoMode(QLineEdit.EchoMode.Password);self.key.setPlaceholderText('Paste Gemini API key');self.key.setAccessibleName('Gemini API key');layout.addWidget(self.key)
        layout.addWidget(push('Connect Gemini',self.connect_gemini))
        self.gemini_model=QComboBox();self.gemini_model.setAccessibleName('Preferred Gemini model for reviewed cloud turns');self.gemini_model.setEnabled(False)
        self.gemini_model.currentTextChanged.connect(lambda model:self.manager.preferences.setValue('cloudModel',model) if model else None)
        layout.addWidget(self.gemini_model)
        self.status=QLabel('Nothing has been sent to a cloud provider.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        layout.addWidget(push('Other provider options',lambda:manager.open_page('Providers',self.status)))
        layout.addWidget(push('Close',self.close));self.refresh()

    def refresh(self):
        self.status.setText('Checking local Ollama and saved provider records…')
        def work():return self.manager.session.models(),self.manager.session.request('GET','/api/local/provider-connections')
        def done(result):
            models,connections=result;lines=[]
            for item in models:
                state='Ready for local chat' if item.get('available') else item.get('reason','Detected; unavailable for chat')
                lines.append(item['name']+' · '+state)
            self.local.setPlainText('\n'.join(lines) if lines else 'No Ollama models detected. Start Ollama, then retry.')
            gemini=next((item for item in connections.get('items',[]) if item.get('provider_type')=='gemini'),None)
            models=gemini.get('models',[]) if gemini else [];saved=self.manager.preferences.value('cloudModel','',type=str)
            self.gemini_model.blockSignals(True);self.gemini_model.clear();self.gemini_model.addItems(models)
            if saved in models:self.gemini_model.setCurrentText(saved)
            self.gemini_model.setEnabled(bool(models));self.gemini_model.blockSignals(False)
            if models:self.manager.preferences.setValue('cloudModel',self.gemini_model.currentText())
            self.status.setText(('Gemini connected · '+str(len(gemini.get('models',[])))+' models found.' if gemini else
                                 'Ollama detection complete. Gemini is optional and not connected.'))
        self.manager.submit(work,done,lambda error:self.status.setText('Could not refresh providers. Start Ollama or check the existing provider record, then retry.'))

    def connect_gemini(self):
        key=self.key.text().strip();self.key.clear()
        if not key:self.status.setText('Paste a Gemini API key first. Nothing was sent.');return
        self.status.setText('Contacting Gemini once to validate the key and discover its model catalog…')
        body={'id':'personal','name':'Gemini','api_key':key,'request_slots':1}
        def work():
            try:return self.manager.session.request('POST','/api/local/provider-connections/gemini',body)
            finally:body['api_key']='';key_bytes=bytearray(key.encode());key_bytes[:]=b'\0'*len(key_bytes)
        def done(result):
            self.status.setText('Gemini connected · '+str(len(result.get('models',[])))+' models found. Cloud use still asks consent per turn.')
            self.refresh()
        self.manager.submit(work,done,lambda error:self.status.setText('Gemini was not connected. Check the key or remove an old Gemini record in Other provider options, then retry.'))

class BackupWindow(QDialog):
    def __init__(self,manager):
        super().__init__();self.manager=manager;self.inspected=None;self.setWindowTitle('Backup & restore · ERSELMETZ AI');self.resize(700,650);layout=QVBoxLayout(self)
        self.detail=OfflineText();self.detail.setAccessibleName('Backup preview');layout.addWidget(self.detail)
        self.private=QCheckBox('Include private data in encrypted backup');self.private.setAccessibleName(self.private.text());layout.addWidget(self.private)
        self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setAccessibleName('Backup passphrase');self.password.setPlaceholderText('Passphrase (12+ characters)');layout.addWidget(self.password)
        self.confirm=QLineEdit();self.confirm.setAccessibleName('Type RESTORE to replace data');self.confirm.setPlaceholderText('Type RESTORE only to replace data after inspecting');layout.addWidget(self.confirm)
        self.status=QLabel('Restore replaces application data and requires restart. No actions are replayed.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        for name,fn in [('Preview backup',self.preview),('Export encrypted backup',self.export),('Inspect backup',lambda:self.upload(False)),('Restore inspected backup',lambda:self.upload(True)),('Close',self.close)]:layout.addWidget(push(name,fn))
    def preview(self):self.manager.submit(lambda:self.manager.session.request('GET','/api/local/backup/preview?include_private_data='+str(self.private.isChecked()).lower()),lambda r:self.detail.setPlainText(text(r)),self.fail)
    def fail(self,error):self.password.clear();self.status.setText('Not completed: '+str(error)[:500])
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Save encrypted backup','','Encrypted backup (*.erselbackup)')
        if not path:return
        secret=self.password.text();private=self.private.isChecked();self.password.clear()
        def work():
            r=self.manager.session.client.post('/api/local/backup/export',json={'passphrase':secret,'include_private_data':private},headers={'X-Local-CSRF':self.manager.session.credentials['csrf']});r.raise_for_status();Path(path).write_bytes(r.content);return 'Encrypted backup saved.'
        self.manager.submit(work,self.status.setText,self.fail)
    def upload(self,restore):
        if restore and (self.confirm.text()!='RESTORE' or self.inspected is None):self.status.setText('Inspect a backup first, then type RESTORE to confirm replacing data.');return
        if restore:path=self.inspected['path']
        else:path,_=QFileDialog.getOpenFileName(self,'Choose encrypted backup','','Encrypted backup (*.erselbackup)')
        if not path:return
        secret=self.password.text();self.password.clear();snapshot=dict(self.inspected or {})
        def work():
            from app.portability.backups import MAX_BACKUP_BYTES
            with Path(path).open('rb') as stream:
                data=stream.read(MAX_BACKUP_BYTES+1)
            if len(data)>MAX_BACKUP_BYTES:raise ValueError('Backup is too large')
            digest=hashlib.sha256(data).hexdigest()
            if restore and digest!=snapshot.get('digest'):raise ValueError('The backup changed after inspection. Inspect it again; nothing was restored.')
            values={'passphrase':secret}
            if restore:values['confirmation']='RESTORE'
            r=self.manager.session.client.post('/api/local/backup/'+('restore' if restore else 'inspect'),files={'file':('backup.erselbackup',data)},data=values,headers={'X-Local-CSRF':self.manager.session.credentials['csrf']});r.raise_for_status();return {'result':r.json(),'path':path,'digest':digest}
        def done(result):
            self.detail.setPlainText(text(result['result']))
            if restore:
                self.inspected=None;self.confirm.clear();self.status.setText('Restore confirmed. Restart ERSELMETZ AI before using protected operations. No work will be replayed.')
            else:
                self.inspected={'path':result['path'],'digest':result['digest']};self.status.setText('Backup inspected. Review the details, re-enter its passphrase and type RESTORE only to replace data.')
        self.manager.submit(work,done,self.fail)

class OwnerWindow(QDialog):
    def __init__(self,manager):
        super().__init__();self.manager=manager;self.setWindowTitle('Owner access · ERSELMETZ AI');self.resize(560,400);layout=QVBoxLayout(self)
        note=QLabel('The owner session stays in this process. Enable a password to protect future launches. Lock stops new protected work before requesting unlock.');note.setWordWrap(True);layout.addWidget(note)
        self.password=QLineEdit();self.confirm=QLineEdit()
        for w,name in [(self.password,'Owner password'),(self.confirm,'Confirm owner password')]:w.setEchoMode(QLineEdit.EchoMode.Password);w.setAccessibleName(name);w.setPlaceholderText(name);layout.addWidget(w)
        self.status=QLabel('');self.status.setWordWrap(True);layout.addWidget(self.status)
        layout.addWidget(push('Enable owner password',lambda:self.configure(True)));layout.addWidget(push('Disable password using current password',lambda:self.configure(False)))
        layout.addWidget(push('Lock now',self.lock));layout.addWidget(push('Close',self.close))
    def configure(self,enabled):
        body={'enabled':enabled,'password':self.password.text(),'confirmation':self.confirm.text()};self.password.clear();self.confirm.clear()
        self.manager.submit(lambda:self.manager.session.request('POST','/api/local/desktop-lock',body),lambda r:self.status.setText('Owner password setting confirmed.'),lambda e:self.status.setText(str(e)[:500]))
    def lock(self):
        self.manager.stop_all()
        # No dismissal grants authority; only a verified password releases the session gate.
        if not hasattr(self.manager.session,'lock_owner'):self.status.setText('Lock requires the in-process owner session.');return
        from app.local_owner_credential import LocalOwnerCredentialStore
        if not LocalOwnerCredentialStore().exists():self.status.setText('Enable an owner password first.');return
        self.manager.session.lock_owner();dialog=QDialog();dialog.setWindowTitle('Unlock ERSELMETZ AI');dialog.setWindowModality(Qt.WindowModality.ApplicationModal);layout=QVBoxLayout(dialog)
        entry=QLineEdit();entry.setEchoMode(QLineEdit.EchoMode.Password);entry.setAccessibleName('Unlock owner password');layout.addWidget(entry);state=QLabel('Protected requests are locked.');layout.addWidget(state)
        def unlock():
            try:self.manager.session.unlock_owner(entry.text())
            except ValueError:entry.clear();state.setText('Password did not match.');return
            entry.clear();dialog.accept()
        layout.addWidget(push('Unlock',unlock));layout.addWidget(push('Quit',self.manager.app.quit));dialog.rejected.connect(self.manager.app.quit);dialog.open();self.lock_dialog=dialog
