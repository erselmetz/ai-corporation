import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog,QLineEdit,QComboBox,QPushButton
from tests.test_qt_shell import manager


@pytest.mark.parametrize('operation,value,expected',[
    (0,'0.1+0.2',{'kind':'calculator','expression':'0.1+0.2'}),
    (1,'x*x=4',{'kind':'solve_equation','equation':'x*x=4'}),
    (2,'1',{'kind':'convert_units','value':'1','source_unit':'m','target_unit':'m'})])
def test_math_dialog_requires_exact_run_before_sending(manager,qtbot,operation,value,expected):
    window=manager.new_window();qtbot.waitUntil(lambda:window.model.count()==1)
    sent=[];window.send=lambda *,math_tool:sent.append(math_tool)
    def approve():
        dialog=next(d for d in window.findChildren(QDialog) if d.windowTitle()=='Reviewed local exact math')
        dialog.findChildren(QComboBox)[0].setCurrentIndex(operation)
        dialog.findChild(QLineEdit).setText(value)
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Run locally').click()
    assert sent==[]
    QTimer.singleShot(100,approve);window.open_math()
    assert sent==[expected]
