"""Separate Qt processes enforce the real Windows DPI scale before QApplication."""
import os,subprocess,sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform!='win32',reason='Baselines record Windows fonts and native DPI behavior')
@pytest.mark.parametrize('scale',['1','1.25','1.5'])
@pytest.mark.parametrize('theme',['dark','light'])
def test_native_screenshot_baselines(scale,theme,tmp_path):
    environment=dict(os.environ);environment.pop('QT_QPA_PLATFORM',None)
    result=subprocess.run([sys.executable,str(ROOT/'tools/qt_screenshot_matrix.py'),'--scale',scale,'--theme',theme,
        '--output',str(tmp_path)],cwd=ROOT,env=environment,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
