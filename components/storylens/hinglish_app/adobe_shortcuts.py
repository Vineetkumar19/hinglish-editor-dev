"""Three Storylens commands, limited to AE/Explorer; never records typed text.

The listener is opt-in and lives only while the Storylens CEP panel enables it.
It uses the existing local hook runtime; no startup service, remap or injection.
"""
import argparse
import json
import ntpath
import uuid
import sys
import threading

class ShortcutGate:
    def __init__(self,foreground,files,emit,window=None):
        self.foreground,self.emit=foreground,emit
        self.window=window or self._window
        self.pressed,self.suppressed=set(),set()
    @staticmethod
    def _window():
        import ctypes
        user=ctypes.WinDLL('user32');user.GetForegroundWindow.restype=ctypes.c_void_p
        return int(user.GetForegroundWindow() or 0)
    def key(self,vk,down):
        modifiers={0x11,0xA2,0xA3,0x10,0xA0,0xA1,0x12,0xA4,0xA5,0x5B,0x5C}
        if vk in modifiers:
            (self.pressed.add if down else self.pressed.discard)(vk);return False
        if vk not in (0x32,0x33,0x34):return False
        if not down:
            handled=vk in self.suppressed;self.suppressed.discard(vk);return handled
        if vk in self.suppressed:return True
        held=self.pressed
        if (not held.intersection({0x11,0xA2,0xA3}) or not held.intersection({0x10,0xA0,0xA1})
                or not held.intersection({0x12,0xA4,0xA5}) or held.intersection({0x5B,0x5C})):return False
        app=ntpath.basename(self.foreground()).lower()
        if app not in ('afterfx.exe','explorer.exe') or app=='explorer.exe' and vk!=0x32:return False
        self.emit({'event':'shortcut','request_id':uuid.uuid4().hex,
                   'command':{0x32:'copy',0x33:'paste',0x34:'undo'}[vk],
                   'source':'explorer' if app=='explorer.exe' else 'project','window_handle':self.window()})
        self.suppressed.add(vk);return True

if __name__=='__main__':
    from hinglish_app.adobe_clipboard import watch
    parser=argparse.ArgumentParser();parser.add_argument('--parent-pid',required=True,type=int)
    stop=threading.Event()
    def stop_reader():
        try:
            for line in sys.stdin:
                if line.strip()=='stop':break
        finally:stop.set()
    threading.Thread(target=stop_reader,daemon=True).start()
    try:watch(parser.parse_args().parent_pid,gate_factory=ShortcutGate,stop_event=stop)
    except Exception as error:print(json.dumps({'event':'error','message':'Storylens shortcuts could not start. The buttons remain available.','details':str(error)}),flush=True)
