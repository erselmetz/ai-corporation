"""Capture a native test window to PNG using Windows GDI and Python stdlib."""
import ctypes
from ctypes import wintypes as w
import struct
import zlib
from pathlib import Path


def capture(root, destination):
    root.update()
    user=ctypes.windll.user32; gdi=ctypes.windll.gdi32
    user.GetAncestor.argtypes=[w.HWND,w.UINT]; user.GetAncestor.restype=w.HWND
    user.GetWindowDC.argtypes=[w.HWND]; user.GetWindowDC.restype=w.HDC
    gdi.CreateCompatibleDC.argtypes=[w.HDC]; gdi.CreateCompatibleDC.restype=w.HDC
    gdi.CreateCompatibleBitmap.argtypes=[w.HDC,ctypes.c_int,ctypes.c_int]; gdi.CreateCompatibleBitmap.restype=w.HBITMAP
    gdi.SelectObject.argtypes=[w.HDC,w.HGDIOBJ]; gdi.SelectObject.restype=w.HGDIOBJ
    gdi.DeleteObject.argtypes=[w.HGDIOBJ]; gdi.DeleteDC.argtypes=[w.HDC]
    user.ReleaseDC.argtypes=[w.HWND,w.HDC]
    user.PrintWindow.argtypes=[w.HWND,w.HDC,w.UINT]
    hwnd=user.GetAncestor(root.winfo_id(),2); rect=w.RECT(); user.GetWindowRect(hwnd,ctypes.byref(rect))
    width,height=rect.right-rect.left,rect.bottom-rect.top
    source=user.GetWindowDC(hwnd); dc=gdi.CreateCompatibleDC(source); bitmap=gdi.CreateCompatibleBitmap(source,width,height)
    old=gdi.SelectObject(dc,bitmap)
    class Header(ctypes.Structure):
        _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
    header=Header(ctypes.sizeof(Header),width,-height,1,32,0,0,0,0,0,0)
    pixels=ctypes.create_string_buffer(width*height*4)
    gdi.GetDIBits.argtypes=[w.HDC,w.HBITMAP,w.UINT,w.UINT,ctypes.c_void_p,ctypes.c_void_p,w.UINT]
    try:
        if not user.PrintWindow(hwnd,dc,2): raise RuntimeError("Native window capture failed")
        gdi.SelectObject(dc,old)
        if not gdi.GetDIBits(dc,bitmap,0,height,pixels,ctypes.byref(header),0): raise RuntimeError("Native pixels unavailable")
        raw=bytearray()
        data=pixels.raw
        for y in range(height):
            raw.append(0)
            row=data[y*width*4:(y+1)*width*4]
            for x in range(0,len(row),4): raw.extend((row[x+2],row[x+1],row[x]))
        def chunk(kind,payload): return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
        target=Path(destination); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(png)
    finally:
        gdi.DeleteObject(bitmap); gdi.DeleteDC(dc); user.ReleaseDC(hwnd,source)
