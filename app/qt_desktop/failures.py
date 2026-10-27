"""Local, bounded failure counters. No messages, stacks, paths, secrets or upload."""
import json,os
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

MAX_BYTES=32768
MAX_RECORDS=20


def ui_exception_handler(directory,get_manager):
    handling=[False]
    def handle(error_type,error,traceback):
        if handling[0]:return
        handling[0]=True
        try:
            record_failure(directory,stage='ui',error=error)
            manager=get_manager()
            if manager is not None:
                try:manager.stop_all()
                except Exception:pass
                for window in list(manager.windows):
                    if not window.closed:window.status.setText('The window encountered an error. Stop was requested. Close and reopen the app before continuing.')
        finally:handling[0]=False
    return handle


def record_failure(directory,*,stage,error):
    if stage not in {'startup','shutdown','ui'}:return False
    category=('permission' if isinstance(error,PermissionError) else 'io' if isinstance(error,OSError)
              else 'invalid_state' if isinstance(error,ValueError) else 'internal')
    path=Path(directory)/'native-failures.json';temporary=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.is_symlink() or path.is_junction():return False
        records=[]
        if path.exists():
            if path.stat().st_size>MAX_BYTES:return False
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or set(data)!={'version','records'} or data['version']!=1:return False
            if not isinstance(data['records'],list) or len(data['records'])>MAX_RECORDS:return False
            for item in data['records']:
                if (not isinstance(item,dict) or set(item)!={'at','stage','category'}
                        or item['stage'] not in {'startup','shutdown','ui'}
                        or item['category'] not in {'permission','io','invalid_state','internal'}
                        or not isinstance(item['at'],str) or len(item['at'])>40):return False
            records=data['records']
        records=(records+[{'at':datetime.now(timezone.utc).isoformat(),'stage':stage,'category':category}])[-MAX_RECORDS:]
        payload=json.dumps({'version':1,'records':records},separators=(',',':')).encode('utf-8')
        temporary=path.with_name('.native-failures-'+uuid4().hex+'.tmp')
        with temporary.open('xb') as handle:handle.write(payload);handle.flush();os.fsync(handle.fileno())
        temporary.replace(path);return True
    except (OSError,ValueError,TypeError,RecursionError):return False
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
