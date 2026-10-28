from pathlib import Path
from types import SimpleNamespace
import pytest
from app.integrations.chromium_startup import wait_for_port


def test_writer_lock_and_partial_file_are_retried_within_original_deadline(tmp_path,monkeypatch):
    (tmp_path/'DevToolsActivePort').write_text('ready',encoding='utf-8')
    attempts=[PermissionError('writer still holds sharing lock'),'','12345\n/devtools/browser/owned\n'];sleeps=[];now=[0.0]
    def read(path,**kwargs):
        value=attempts.pop(0)
        if isinstance(value,Exception):raise value
        return value
    def sleep(seconds):sleeps.append(seconds);now[0]+=seconds
    monkeypatch.setattr(Path,'read_text',read)
    assert wait_for_port(tmp_path,SimpleNamespace(poll=lambda:None),1,clock=lambda:now[0],sleep=sleep)==12345
    assert len(sleeps)==2 and now[0]<1


def test_persistently_locked_file_fails_closed_without_extending_deadline(tmp_path,monkeypatch):
    (tmp_path/'DevToolsActivePort').write_text('ready',encoding='utf-8');now=[0.0]
    def read(path,**kwargs):raise PermissionError('still locked')
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(RuntimeError,match='deadline'):
        wait_for_port(tmp_path,SimpleNamespace(poll=lambda:None),.1,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
    assert now[0]==.1


def test_exited_process_is_never_treated_as_ready(tmp_path):
    (tmp_path/'DevToolsActivePort').write_text('12345\n/devtools/browser/owned\n',encoding='utf-8')
    with pytest.raises(RuntimeError,match='exited'):wait_for_port(tmp_path,SimpleNamespace(poll=lambda:0),1,clock=lambda:0)
