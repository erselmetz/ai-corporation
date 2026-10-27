import importlib.util,json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_installer',ROOT/'tools/build_installer.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def package(tmp_path,review=False):
    (tmp_path/'ERSELMETZ-AI.exe').write_bytes(b'fixture only, never executed')
    inner=tmp_path/'_internal'/'app';inner.mkdir(parents=True)
    stamp={'version':'0.1.0','commit':'a'*40,'source_sha256':'b'*64,'review_build':review}
    for path in [inner/'build_metadata.json',tmp_path/'build-stamp.json']:path.write_text(json.dumps(stamp),encoding='utf-8')
    return stamp


def test_installer_accepts_matching_stamp_and_rejects_mismatched_distribution(tmp_path):
    stamp=package(tmp_path);assert builder.validate(tmp_path)[1]==stamp
    (tmp_path/'build-stamp.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='stamps'):builder.validate(tmp_path)


@pytest.mark.parametrize('entry',['node.exe','package.json','_internal/playwright/driver/node.exe'])
def test_final_installer_cannot_hide_a_node_runtime(tmp_path,entry):
    package(tmp_path);path=tmp_path/entry;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
    with pytest.raises(ValueError,match='Node or Playwright'):builder.validate(tmp_path)


def test_review_build_cannot_be_mistaken_for_final_installer(tmp_path):
    package(tmp_path,True)
    with pytest.raises(ValueError,match='Review artifacts'):builder.validate(tmp_path)
    assert builder.validate(tmp_path,review=True)[1]['review_build'] is True
