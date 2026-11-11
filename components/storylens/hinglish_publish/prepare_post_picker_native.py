"""Modern Windows Open dialog on its own STA thread/process; no GUI toolkit."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import uuid
import json
import os
import time
import threading


def choose(kind='video', start=''):
    if sys.platform != 'win32':raise RuntimeError('The native file chooser requires Windows.')
    log=Path('cache/publisher/picker')/f'{os.getpid()}.json'
    def trace(stage):
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(json.dumps({'pid':os.getpid(),'kind':kind,'stage':stage,'time':time.time()}),encoding='utf-8')
    trace('initializing COM')
    class GUID(ctypes.Structure):
        _fields_ = [('data1',ctypes.c_uint32),('data2',ctypes.c_uint16),('data3',ctypes.c_uint16),('data4',ctypes.c_ubyte*8)]
    def guid(value):return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)
    class Filter(ctypes.Structure):
        _fields_ = [('name',wintypes.LPCWSTR),('pattern',wintypes.LPCWSTR)]
    ole=ctypes.OleDLL('ole32');shell=ctypes.WinDLL('shell32');user=ctypes.WinDLL('user32')
    ole.CoInitializeEx.argtypes=[ctypes.c_void_p,wintypes.DWORD]
    ole.CoInitializeEx.restype=ctypes.c_long
    ole.CoCreateInstance.argtypes=[ctypes.POINTER(GUID),ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype=ctypes.c_long
    ole.CoTaskMemFree.argtypes=[ctypes.c_void_p]
    shell.SHCreateItemFromParsingName.argtypes=[wintypes.LPCWSTR,ctypes.c_void_p,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)]
    shell.SHCreateItemFromParsingName.restype=ctypes.c_long
    user.GetForegroundWindow.restype=wintypes.HWND
    # A hidden console/venv launcher can pass SW_HIDE as its first-window
    # startup setting. Consume that setting on an invisible temporary window,
    # so Windows does not hide the actual first file dialog as well.
    user.CreateWindowExW.argtypes=[wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,
        ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.HWND,wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p]
    user.CreateWindowExW.restype=wintypes.HWND
    user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
    user.DestroyWindow.argtypes=[wintypes.HWND]
    startup_window=user.CreateWindowExW(0,'STATIC','Storylens picker initialization',0x80000000,0,0,1,1,None,None,None,None)
    if startup_window:
        user.ShowWindow(startup_window,1)
        user.DestroyWindow(startup_window)
    def check(result):
        if result<0:raise OSError(f'Windows file dialog failed: 0x{result&0xffffffff:08x}')
    def method(pointer,index,types=(),result=ctypes.c_long):
        table=ctypes.cast(pointer,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(result,ctypes.c_void_p,*types)(table[index])
    def release(pointer):
        if pointer:method(pointer,2,result=ctypes.c_ulong)(pointer)
    dialog=ctypes.c_void_p();item=ctypes.c_void_p();folder=ctypes.c_void_p();name=ctypes.c_void_p()
    check(ole.CoInitializeEx(None,2))
    trace('creating Windows dialog')
    try:
        cls=guid('DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7');interface=guid('D57C7288-D4AD-4768-BE02-9D969532D960')
        check(ole.CoCreateInstance(ctypes.byref(cls),None,1,ctypes.byref(interface),ctypes.byref(dialog)))
        trace('configuring Windows dialog')
        if kind=='video':title='Choose a video - Storylens';filters=(Filter*1)(Filter('Video files','*.mp4;*.mov;*.mkv;*.webm;*.mxf;*.avi'))
        elif kind=='thumbnail':title='Choose a thumbnail - Storylens';filters=(Filter*1)(Filter('Image files','*.png;*.jpg;*.jpeg;*.webp'))
        else:raise ValueError('Choose a video or thumbnail.')
        check(method(dialog,4,(wintypes.UINT,ctypes.POINTER(Filter)))(dialog,1,filters))
        check(method(dialog,17,(wintypes.LPCWSTR,))(dialog,title))
        options=wintypes.DWORD()
        check(method(dialog,10,(ctypes.POINTER(wintypes.DWORD),))(dialog,ctypes.byref(options)))
        check(method(dialog,9,(wintypes.DWORD,))(dialog,options.value|0x40|0x800|0x1000|0x8))
        if start and Path(start).is_dir():
            trace('resolving initial folder')
            iid=guid('43826D1E-E718-42EE-BC55-A1E261C37BFE')
            check(shell.SHCreateItemFromParsingName(str(Path(start).resolve()),None,ctypes.byref(iid),ctypes.byref(folder)))
            check(method(dialog,12,(ctypes.c_void_p,))(dialog,folder))
        trace('showing Windows dialog')
        finished=threading.Event()
        def make_dialog_visible():
            callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
            user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
            user.ShowWindowAsync.argtypes=[wintypes.HWND,ctypes.c_int]
            user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
            user.SetForegroundWindow.argtypes=[wintypes.HWND]
            for _ in range(100):
                found=[]
                @callback_type
                def inspect(hwnd,_):
                    pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                    if pid.value==os.getpid():
                        label=ctypes.create_unicode_buffer(256);user.GetWindowTextW(hwnd,label,256)
                        if label.value==title:found.append(hwnd)
                    return True
                user.EnumWindows(inspect,0)
                if found:
                    user.ShowWindowAsync(found[0],1)
                    user.SetWindowPos(found[0],wintypes.HWND(-1),0,0,0,0,0x1|0x2|0x40)
                    user.SetForegroundWindow(found[0]);trace('native dialog visible');return
                if finished.wait(.1):return
            trace('waiting for Windows to create the dialog')
        threading.Thread(target=make_dialog_visible,daemon=True).start()
        # A browser request can finish launching while Codex/another app has
        # focus. Never attach the modal to that unrelated foreground window.
        result=method(dialog,3,(wintypes.HWND,))(dialog,None)
        finished.set()
        trace('Windows dialog returned')
        if result&0xffffffff==0x800704c7:return ''
        check(result)
        check(method(dialog,20,(ctypes.POINTER(ctypes.c_void_p),))(dialog,ctypes.byref(item)))
        check(method(item,5,(ctypes.c_uint32,ctypes.POINTER(ctypes.c_void_p)))(item,0x80058000,ctypes.byref(name)))
        return ctypes.wstring_at(name)
    finally:
        if name:ole.CoTaskMemFree(name)
        release(item);release(folder);release(dialog);ole.CoUninitialize()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdout.write(choose(*(sys.argv[1:3])))
