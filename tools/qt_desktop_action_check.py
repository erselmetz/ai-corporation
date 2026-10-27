"""Real guarded UIA calls against our disposable fixture only, never user apps."""
from pathlib import Path
import ctypes,json,os,subprocess,sys,tempfile,time
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    profile=Path(tempfile.mkdtemp(prefix='ersel-desktop-action-check-'));os.environ['LOCALAPPDATA']=str(profile);os.chdir(profile)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app.native_desktop.session import NativeSession
    from app.qt_desktop.shell import ShellManager
    from app.integrations.scoped_desktop_automation import WindowsUIAutomationBackend
    original_inspect=WindowsUIAutomationBackend.inspect
    def diagnostic_inspect(*args,**kwargs):
        try:return original_inspect(*args,**kwargs)
        except Exception:
            import traceback;traceback.print_exc();raise
    WindowsUIAutomationBackend.inspect=diagnostic_inspect
    app=QApplication([]);session=NativeSession();manager=ShellManager(app,session)
    fixture=subprocess.Popen([sys.executable,str(ROOT/'tools/native_desktop_fixture.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    record=json.loads(fixture.stdout.readline());evidence={'fixture':record,'kind':'Source Python process, real Windows UI Automation, disposable owned controls only'}
    def wait(predicate):
        end=time.monotonic()+30
        while not predicate():
            app.processEvents();QTest.qWait(20)
            if time.monotonic()>end:raise RuntimeError('Source desktop check timed out')
    try:
        window=manager.new_window();wait(lambda:bool(window.native_id));generation=window.native_generation
        def api(method,path,body=None):return session.request(method,path,body,window=window.native_id,generation=generation)
        prefix='/api/local/automation/desktop'
        process=Path(sys.executable).name.lower()
        api('PUT',prefix+'/process',{'process_name':process,'allowed':True})
        target={'process_id':record['pid'],'window_handle':record['hwnd'],'process_name':process,'window_title':record['title']}
        controls=api('POST',prefix+'/controls',target)['items'];evidence['controls']=controls
        assert {item['action'] for item in controls}=={'fill_text','invoke_button'},evidence
        receipts=[]
        for action in ['fill_text','invoke_button']:
            control=next(item for item in controls if item['action']==action);payload=dict(target,**control)
            if action=='fill_text':payload['value']='Reviewed local fixture — kumusta'
            approval=api('POST',prefix+'/request-approval',payload)['approval']
            api('POST','/api/capabilities/approvals/'+approval['approval_id']+'/approve',{'confirmed_digest':approval['approval_digest']})
            result=api('POST',prefix+'/execute',dict(payload,approval_id=approval['approval_id']))
            receipts.append(result);assert result['status']=='action_dispatched',result
        user=ctypes.WinDLL('user32',use_last_error=True)
        user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int];user.GetWindowTextW.restype=ctypes.c_int
        buffer=ctypes.create_unicode_buffer(128);user.GetWindowTextW(record['button'],buffer,128)
        evidence.update(receipts=receipts,fixture_button_after=buffer.value)
        assert buffer.value=='Invoked 1',evidence
        # Inspect only our controlled test Edit, after the approved replacement.
        from pywinauto import Application
        observed=Application(backend='uia').connect(process=record['pid']).window(handle=record['hwnd']).child_window(auto_id='101',control_type='Edit').wrapper_object().iface_value.CurrentValue
        evidence['fixture_text_after']=observed;assert observed=='Reviewed local fixture — kumusta',evidence
        # Exercise the native Agent-tool broker too, with the same existing UIA
        # service and one approval. This isolated QA owner explicitly resumes
        # Operator; the shipped profile remains paused in normal/new profiles.
        wait(lambda:window.agent.findData('operator')>=0)
        api('PUT','/api/agents/operator/pause',{'paused':False})
        window.model.setCurrentIndex(window.model.findData('qwen3.5:4b'))
        window.agent.setCurrentIndex(window.agent.findData('operator'));chat=window.current()
        arguments=dict(target,**next(item for item in controls if item['action']=='fill_text'))
        arguments.pop('action');arguments['value']='Native broker approved fixture text'
        review=manager.transport.prepare_tool(chat,'Replace the owned QA fixture text only','desktop_type',arguments,generation=generation)
        assert review['approval_required']
        outcome=manager.transport.tool_api(chat,'POST','/'+review['id']+'/execute',{'confirmed_digest':review['approval_digest']},generation=generation)
        assert outcome['state']=='unverified',outcome
        observed=Application(backend='uia').connect(process=record['pid']).window(handle=record['hwnd']).child_window(auto_id='101',control_type='Edit').wrapper_object().iface_value.CurrentValue
        assert observed=='Native broker approved fixture text',observed
        evidence['native_broker']={'receipt':outcome,'observed_text':observed,'model_calls':0}
        window.desktop_controls.show();window.desktop_controls.dialog.grab().save(str(ROOT/'task226-review/desktop-controls.png'));window.desktop_controls.stop()
        print(json.dumps(evidence));(ROOT/'task226-review/source-desktop-action-check.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    finally:
        for window in list(manager.windows):window.close()
        manager.shutdown();session.close()
        if fixture.poll() is None:
            user=ctypes.WinDLL('user32');user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];user.PostMessageW(record['hwnd'],0x10,0,0)
            try:fixture.wait(timeout=5)
            except subprocess.TimeoutExpired:fixture.terminate();fixture.wait(timeout=5)


if __name__=='__main__':main()
