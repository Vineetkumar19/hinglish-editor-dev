import unittest
from hinglish_app.adobe_clipboard import PasteGate, usable_media


class ClipboardPasteTests(unittest.TestCase):
    def test_explorer_file_paste_is_captured_only_in_after_effects(self):
        events = []
        gate = PasteGate(lambda: 'AfterFX.exe', lambda: [r'D:\Photos\owner picture.jpg'], events.append)
        self.assertFalse(gate.key(0xA2, True))
        self.assertTrue(gate.key(0x56, True))
        self.assertEqual(events[0]['paths'], [r'D:\Photos\owner picture.jpg'])
        self.assertTrue(gate.key(0x56, True))
        self.assertEqual(len(events), 1)
        self.assertTrue(gate.key(0x56, False))
        self.assertTrue(gate.key(0x56, True))
        self.assertEqual(len(events), 2)

    def test_other_apps_text_clipboard_and_shift_paste_are_untouched(self):
        events = []
        for app, paths, shift in [('explorer.exe', ['D:/photo.jpg'], False), ('AfterFX.exe', [], False), ('AfterFX.exe', ['D:/photo.jpg'], True)]:
            gate = PasteGate(lambda: app, lambda: paths, events.append)
            gate.key(0xA2, True)
            if shift: gate.key(0xA0, True)
            self.assertFalse(gate.key(0x56, True))
        self.assertEqual(events, [])

    def test_projects_scripts_and_multiple_files_are_not_intercepted(self):
        self.assertTrue(usable_media(['D:/photos/picture.PNG']))
        self.assertFalse(usable_media(['D:/template.aep']))
        self.assertFalse(usable_media(['D:/script.jsx']))
        self.assertFalse(usable_media(['D:/1.jpg', 'D:/2.jpg']))

