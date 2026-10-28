"""Bounded metadata-only application log. Never accepts arbitrary messages."""
import json,os,re
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4

def record_event(directory,event,stamp):
    if event not in {'startup','ready','shutdown'}:return False
    version=stamp.get('version','development');commit=stamp.get('commit','development')
    if not isinstance(version,str) or not re.fullmatch(r'[0-9A-Za-z.-]{1,32}',version):return False
    if not isinstance(commit,str) or not re.fullmatch(r'(?:[a-f0-9]{7,40}|development|unknown)',commit):return False
    path=Path(directory)/'native-events.json';temporary=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.is_symlink() or path.is_junction():return False
        rows=[]
        if path.exists():
            if path.stat().st_size>32768:return False
            existing=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(existing,list) or len(existing)>60:return False
            for row in existing:
                if not isinstance(row,dict) or set(row)!={'at','event','version','commit'}:return False
                if row['event'] not in {'startup','ready','shutdown'}:return False
                if not isinstance(row['at'],str) or len(row['at'])>40:return False
                if not re.fullmatch(r'[0-9A-Za-z.-]{1,32}',str(row['version'])):return False
                if not re.fullmatch(r'(?:[a-f0-9]{7,40}|development|unknown)',str(row['commit'])):return False
            rows=existing
        rows=(rows+[{'at':datetime.now(timezone.utc).isoformat(),'event':event,'version':version,'commit':commit}])[-60:]
        temporary=path.with_name('.events-'+uuid4().hex+'.tmp')
        with temporary.open('xb') as handle:
            handle.write(json.dumps(rows,separators=(',',':')).encode('utf-8'));handle.flush();os.fsync(handle.fileno())
        temporary.replace(path);return True
    except (OSError,ValueError,TypeError):return False
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
