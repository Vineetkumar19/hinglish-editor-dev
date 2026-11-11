import unittest
from hinglish_app.adobe_shortcuts import ShortcutGate

class ShortcutTests(unittest.TestCase):
    def gate(self,app='AfterFX.exe'):
        self.events=[]
        gate=ShortcutGate(lambda:app,lambda:[],self.events.append,window=lambda:42)
        for key in (0xA2,0xA0,0xA4):gate.key(key,True)
        return gate
    def test_ae_and_explorer_have_distinct_capture_sources(self):
        for app,source in [('AfterFX.exe','project'),('explorer.exe','explorer')]:
            gate=self.gate(app);self.assertTrue(gate.key(0x32,True));self.assertEqual(self.events[0]['source'],source)
            self.assertTrue(gate.key(0x32,True));self.assertEqual(len(self.events),1)
            gate.key(0x32,False);self.assertTrue(gate.key(0x32,True));self.assertEqual(len(self.events),2)
    def test_paste_and_undo_are_only_active_in_ae(self):
        for key,command in [(0x33,'paste'),(0x34,'undo')]:
            gate=self.gate();self.assertTrue(gate.key(key,True));self.assertEqual(self.events[0]['command'],command)
            gate=self.gate('explorer.exe');self.assertFalse(gate.key(key,True));self.assertEqual(self.events,[])
    def test_other_apps_and_native_shortcuts_are_untouched(self):
        gate=self.gate('chrome.exe');self.assertFalse(gate.key(0x32,True));self.assertEqual(self.events,[])
        gate=self.gate()
        for key in (0x43,0x56,0x5A,0x53,0x31,0x35):self.assertFalse(gate.key(key,True))
        self.assertEqual(self.events,[])
        gate.key(0xA0,False);self.assertFalse(gate.key(0x32,True))
    def test_windows_modifier_and_injected_app_names_do_not_match(self):
        gate=self.gate();gate.key(0x5B,True);self.assertFalse(gate.key(0x32,True))
        gate=self.gate('NotAfterFX.exe');self.assertFalse(gate.key(0x32,True))
