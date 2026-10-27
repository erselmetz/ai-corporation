"""Owned, disposable Win32 controls for desktop-action verification, no user apps."""
import ctypes,json,os
from ctypes import wintypes as W


def main():
    user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    procedure=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
    user.DefWindowProcW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];user.DefWindowProcW.restype=ctypes.c_ssize_t
    user.PostQuitMessage.argtypes=[ctypes.c_int]
    count=0
    @procedure
    def process(hwnd,message,wp,lp):
        nonlocal count
        if message==0x111 and wp&0xffff==102:
            count+=1;user.SetWindowTextW(button,'Invoked '+str(count));return 0
        if message==2:user.PostQuitMessage(0);return 0
        return user.DefWindowProcW(hwnd,message,wp,lp)
    class WindowClass(ctypes.Structure):
        _fields_=[('style',W.UINT),('procedure',procedure),('class_extra',ctypes.c_int),('window_extra',ctypes.c_int),
                  ('instance',W.HINSTANCE),('icon',W.HICON),('cursor',W.HANDLE),('background',W.HBRUSH),('menu',W.LPCWSTR),('name',W.LPCWSTR)]
    kernel.GetModuleHandleW.argtypes=[W.LPCWSTR];kernel.GetModuleHandleW.restype=W.HMODULE
    instance=kernel.GetModuleHandleW(None);name='ERSELMETZ_QA_Desktop_'+str(os.getpid())
    wc=WindowClass(0,process,0,0,instance,None,None,None,None,name)
    user.RegisterClassW.argtypes=[ctypes.POINTER(WindowClass)];user.RegisterClassW.restype=W.ATOM
    assert user.RegisterClassW(ctypes.byref(wc))
    create=user.CreateWindowExW;create.argtypes=[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,W.LPVOID];create.restype=W.HWND
    title='ERSELMETZ owned desktop QA '+str(os.getpid())
    window=create(0,name,title,0x10cf0000,200,200,540,240,None,None,instance,None)
    assert window
    create(0,'STATIC','Sample input:',0x50000000,20,20,180,24,window,100,instance,None)
    entry=create(0x200,'EDIT','original',0x50000000,20,48,450,30,window,101,instance,None)
    button=create(0,'BUTTON','QA action',0x50000000,20,100,180,34,window,102,instance,None)
    user.SetWindowTextW.argtypes=[W.HWND,W.LPCWSTR];user.SetWindowTextW.restype=W.BOOL
    print(json.dumps({'pid':os.getpid(),'hwnd':int(window),'entry':int(entry),'button':int(button),'title':title}),flush=True)
    msg=W.MSG();user.GetMessageW.argtypes=[ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT]
    while user.GetMessageW(ctypes.byref(msg),None,0,0)>0:
        user.TranslateMessage(ctypes.byref(msg));user.DispatchMessageW(ctypes.byref(msg))


if __name__=='__main__':main()
