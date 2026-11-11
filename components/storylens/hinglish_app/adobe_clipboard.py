"""Explorer-file paste shortcut for the open Storylens AE panel.

Only Ctrl+V, only AfterFX, only one copied image/video file. No text clipboard,
other shortcuts, keystroke recording, input injection, or remote communication.
"""
import argparse
import json
import ntpath
import queue
import sys
import threading
import uuid

MEDIA = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif', '.psd', '.exr', '.tga', '.mp4', '.mov', '.avi', '.mxf', '.m4v', '.webm'}


def usable_media(paths):
    return isinstance(paths, list) and len(paths) == 1 and isinstance(paths[0], str) and ntpath.isabs(paths[0]) and ntpath.splitext(paths[0])[1].lower() in MEDIA


class PasteGate:
    def __init__(self, foreground, files, emit):
        self.foreground, self.files, self.emit = foreground, files, emit
        self.pressed, self.suppressed = set(), False

    def key(self, vk, down):
        if vk in {0x11, 0xA2, 0xA3, 0x10, 0xA0, 0xA1, 0x12, 0xA4, 0xA5, 0x5B, 0x5C}:
            (self.pressed.add if down else self.pressed.discard)(vk)
            return False
        if vk != 0x56:
            return False
        if not down:
            handled, self.suppressed = self.suppressed, False
            return handled
        if self.suppressed:
            return True  # Do not repeat a held paste key.
        ctrl = self.pressed.intersection({0x11, 0xA2, 0xA3})
        other = self.pressed.difference({0x11, 0xA2, 0xA3})
        if not ctrl or other or ntpath.basename(self.foreground()).lower() != 'afterfx.exe':
            return False
        paths = self.files()
        if not usable_media(paths):
            return False
        self.emit({'event': 'paste', 'request_id': uuid.uuid4().hex, 'paths': paths})
        self.suppressed = True
        return True


def watch(parent_pid,gate_factory=PasteGate,stop_event=None):
    import ctypes as C
    from ctypes import wintypes as W
    if sys.platform != 'win32':
        raise RuntimeError('File paste shortcuts require Windows.')
    user, kernel, shell = C.WinDLL('user32', use_last_error=True), C.WinDLL('kernel32', use_last_error=True), C.WinDLL('shell32', use_last_error=True)
    result_type = C.c_ssize_t
    callback_type = C.WINFUNCTYPE(result_type, C.c_int, W.WPARAM, W.LPARAM)
    class Keyboard(C.Structure):
        _fields_ = [('vkCode', W.DWORD), ('scanCode', W.DWORD), ('flags', W.DWORD), ('time', W.DWORD), ('extra', C.c_size_t)]
    user.SetWindowsHookExW.argtypes = [C.c_int, callback_type, W.HINSTANCE, W.DWORD]
    user.SetWindowsHookExW.restype = W.HANDLE
    user.CallNextHookEx.argtypes = [W.HANDLE, C.c_int, W.WPARAM, W.LPARAM]
    user.CallNextHookEx.restype = result_type
    user.UnhookWindowsHookEx.argtypes = [W.HANDLE]
    user.GetForegroundWindow.restype = W.HWND
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
    kernel.GetModuleHandleW.restype = W.HMODULE
    user.GetClipboardData.argtypes = [W.UINT]
    user.GetClipboardData.restype = W.HANDLE
    shell.DragQueryFileW.argtypes = [W.HANDLE, W.UINT, W.LPWSTR, W.UINT]
    shell.DragQueryFileW.restype = W.UINT
    user.SetTimer.argtypes = [W.HWND, C.c_size_t, W.UINT, C.c_void_p]
    user.SetTimer.restype = C.c_size_t
    user.KillTimer.argtypes = [W.HWND, C.c_size_t]
    messages = queue.SimpleQueue()
    def writer():
        while True:
            value = messages.get()
            if value is None: return
            try: print(json.dumps(value, ensure_ascii=True), flush=True)
            except (BrokenPipeError, OSError): return
    threading.Thread(target=writer, daemon=True).start()
    def foreground():
        pid = W.DWORD()
        user.GetWindowThreadProcessId(user.GetForegroundWindow(), C.byref(pid))
        process = kernel.OpenProcess(0x1000, False, pid.value)
        if not process: return ''
        try:
            size, name = W.DWORD(32768), C.create_unicode_buffer(32768)
            return name.value if kernel.QueryFullProcessImageNameW(process, 0, name, C.byref(size)) else ''
        finally: kernel.CloseHandle(process)
    def files():
        if not user.IsClipboardFormatAvailable(15) or not user.OpenClipboard(None): return []
        try:
            handle = user.GetClipboardData(15)
            if not handle or shell.DragQueryFileW(handle, 0xFFFFFFFF, None, 0) != 1: return []
            length = shell.DragQueryFileW(handle, 0, None, 0)
            value = C.create_unicode_buffer(length + 1)
            shell.DragQueryFileW(handle, 0, value, length + 1)
            return [value.value]
        finally: user.CloseClipboard()
    gate = gate_factory(foreground, files, messages.put)
    parent = kernel.OpenProcess(0x100000, False, parent_pid)
    if not parent: raise RuntimeError('The Storylens panel is no longer open.')
    @callback_type
    def callback(code, message, pointer):
        if code >= 0:
            key = C.cast(pointer, C.POINTER(Keyboard)).contents.vkCode
            try:
                if gate.key(key, message in (0x100, 0x104)): return 1
            except Exception: pass  # Never break ordinary keyboard input on an error.
        return user.CallNextHookEx(None, code, message, pointer)
    hook = user.SetWindowsHookExW(13, callback, kernel.GetModuleHandleW(None), 0)
    if not hook:
        kernel.CloseHandle(parent)
        raise C.WinError(C.get_last_error())
    timer = user.SetTimer(None, 0, 100 if stop_event is not None else 1000, None)
    if not timer:
        user.UnhookWindowsHookEx(hook);kernel.CloseHandle(parent)
        raise C.WinError(C.get_last_error())
    messages.put({'event': 'ready'})
    try:
        msg = W.MSG()
        while user.GetMessageW(C.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x113 and ((stop_event is not None and stop_event.is_set()) or kernel.WaitForSingleObject(parent, 0) != 0x102): break
            user.TranslateMessage(C.byref(msg));user.DispatchMessageW(C.byref(msg))
    finally:
        user.KillTimer(None, timer);user.UnhookWindowsHookEx(hook);kernel.CloseHandle(parent)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent-pid', required=True, type=int)
    args = parser.parse_args()
    try: watch(args.parent_pid)
    except Exception as error:
        print(json.dumps({'event': 'error', 'message': 'Keyboard paste could not start. Reopen the Storylens panel.', 'details': str(error)}), flush=True)
