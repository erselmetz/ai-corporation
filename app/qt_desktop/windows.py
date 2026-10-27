"""Bounded window descriptors only: never prompts, drafts, actions or authority."""
import json,os,re
from pathlib import Path
from uuid import uuid4

MAX_WINDOWS=16
MAX_TABS=16
MAX_BYTES=256*1024
_ID=re.compile(r'^[a-zA-Z0-9_-]{1,80}$')


def text(value,limit,*,empty=True):
    if (not isinstance(value,str) or len(value)>limit or (not empty and not value.strip())
            or any(ord(c)<32 or ord(c)==127 or '\u202a'<=c<='\u202e' or '\u2066'<=c<='\u2069' for c in value)):
        raise ValueError('Invalid saved window metadata')
    return value


def tab(record):
    if not isinstance(record,dict) or set(record)!={'model','agent','project','workspace','conversation','title'}:
        raise ValueError('Saved tabs may contain selection identifiers and a title only')
    result={key:text(value,256 if key=='model' else 120 if key=='title' else 80) for key,value in record.items()}
    for key in ['agent','project','workspace','conversation']:
        if result[key] and not _ID.fullmatch(result[key]):raise ValueError('Invalid saved selection identifier')
    if not result['agent']:raise ValueError('A saved Agent identifier is required')
    return result


def window(record):
    if not isinstance(record,dict) or set(record)!={'geometry','maximized','sidebar','selected','tabs'}:
        raise ValueError('Invalid saved window fields')
    geometry=record['geometry'];tabs=record['tabs'];selected=record['selected']
    if (not isinstance(geometry,list) or len(geometry)!=4 or any(type(v) is not int for v in geometry)
            or any(abs(v)>100000 for v in geometry[:2]) or not 100<=geometry[2]<=16384 or not 100<=geometry[3]<=16384
            or type(record['maximized']) is not bool or type(record['sidebar']) is not bool
            or not isinstance(tabs,list) or not 1<=len(tabs)<=MAX_TABS
            or type(selected) is not int or not 0<=selected<len(tabs)):
        raise ValueError('Invalid saved window layout')
    return {**record,'tabs':[tab(item) for item in tabs]}


class WindowStore:
    def __init__(self,path):self.path=Path(path);self.last=None;self.notice=''

    def load(self):
        if not self.path.exists():return []
        try:
            if self.path.is_symlink() or self.path.is_junction():raise ValueError('Linked layout file')
            with self.path.open('rb') as handle:data=handle.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES:raise ValueError('Layout exceeds its size bound')
            record=json.loads(data.decode('utf-8'))
            if (not isinstance(record,dict) or set(record)!={'version','windows'} or type(record['version']) is not int
                    or record['version']!=1 or not isinstance(record['windows'],list) or len(record['windows'])>MAX_WINDOWS):
                raise ValueError('Invalid saved layout version or size')
            return [window(item) for item in record['windows']]
        except (OSError,ValueError,UnicodeError,RecursionError):
            self.notice='The saved layout could not be restored. New empty chat opened; no actions were replayed.'
            # Keep the invalid descriptor file locally for recovery. Renaming a
            # link moves the link itself; it never reads or changes its target.
            try:self.path.replace(self.path.with_name(self.path.name+'.invalid-'+uuid4().hex))
            except OSError:pass
            return []

    def save(self,records):
        if not isinstance(records,list) or not 1<=len(records)<=MAX_WINDOWS:raise ValueError('Invalid window count')
        payload=json.dumps({'version':1,'windows':[window(item) for item in records]},ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(payload)>MAX_BYTES:raise ValueError('Saved layout exceeds its size bound')
        if payload==self.last:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        target=self.path.with_name('.'+self.path.name+'.'+uuid4().hex+'.tmp')
        try:
            with target.open('xb') as handle:handle.write(payload);handle.flush();os.fsync(handle.fileno())
            target.replace(self.path);self.last=payload
        finally:
            if target.exists():target.unlink()
