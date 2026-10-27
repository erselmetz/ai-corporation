import json,sys
from pathlib import Path
import pytest
from app import build_stamp


def test_packaged_entry_propagates_startup_failure_exit_status():
    import subprocess
    entry=Path(__file__).resolve().parents[1]/'native_entry.py'
    script="import runpy,sys,types; module=types.ModuleType('app.native_desktop.__main__'); module.main=lambda:7; sys.modules[module.__name__]=module; runpy.run_path(sys.argv[1],run_name='__main__')"
    result=subprocess.run([sys.executable,'-c',script,str(entry)],capture_output=True,text=True,timeout=10)
    assert result.returncode==7,result.stderr


def stamps(tmp_path,monkeypatch):
    inner=tmp_path/'app';inner.mkdir();executable=tmp_path/'dist'/'app.exe';executable.parent.mkdir()
    monkeypatch.setattr(build_stamp,'__file__',str(inner/'build_stamp.py'))
    monkeypatch.setattr(sys,'executable',str(executable));monkeypatch.setattr(sys,'frozen',True,raising=False)
    stamp={'version':'0.1.0','commit':'a'*40,'source_sha256':'b'*64,'review_build':False}
    paths=[inner/'build_metadata.json',executable.with_name('build-stamp.json')]
    for path in paths:path.write_text(json.dumps(stamp),encoding='utf-8')
    return stamp,paths


def test_frozen_stamp_matches_distribution_and_ignores_environment_override(tmp_path,monkeypatch):
    stamp,_=stamps(tmp_path,monkeypatch);monkeypatch.setenv('ERSELMETZ_BUILD_COMMIT','c'*40)
    assert build_stamp._packaged_stamp()==stamp


def test_health_accepts_and_preserves_the_complete_frozen_build_identity(monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    api=importlib.import_module('app.api.app')
    stamp={'version':'0.1.0','commit':'a'*40,'source_sha256':'b'*64,'review_build':True}
    monkeypatch.setattr(api,'BUILD_STAMP',stamp)
    response=TestClient(api.create_app()).get('/health')
    assert response.status_code==200 and response.json()=={'status':'ok',**stamp}


@pytest.mark.parametrize('failure',['missing','different','invalid','extra','oversize'])
def test_frozen_stamp_fails_closed(tmp_path,monkeypatch,failure):
    stamp,paths=stamps(tmp_path,monkeypatch)
    if failure=='missing':paths[0].unlink()
    elif failure=='different':paths[1].write_text('{}',encoding='utf-8')
    else:
        if failure=='invalid':stamp['commit']='unknown'
        if failure=='extra':stamp['extra']='unexpected'
        if failure=='oversize':stamp['version']='x'*5000
        for path in paths:path.write_text(json.dumps(stamp),encoding='utf-8')
    with pytest.raises(RuntimeError,match='build stamp'):build_stamp._packaged_stamp()
