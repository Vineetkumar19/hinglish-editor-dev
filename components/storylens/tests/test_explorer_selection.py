import unittest
from types import SimpleNamespace
from hinglish_app.explorer_selection import selected_paths

class ExplorerSelectionTests(unittest.TestCase):
    def test_reads_only_requested_window_and_single_media(self):
        def window(hwnd, paths):
            return SimpleNamespace(HWND=hwnd, FullName=r'C:\Windows\explorer.exe', Document=SimpleNamespace(SelectedItems=lambda:[SimpleNamespace(IsFileSystem=True,IsFolder=False,Path=p) for p in paths]))
        self.assertEqual(selected_paths([window(1,[r'D:\other.jpg']),window(2,[r'D:\photo.jpg'])],2),[r'D:\photo.jpg'])
    def test_ambiguous_and_non_media_are_rejected(self):
        for paths in [[],[r'D:\one.jpg',r'D:\two.jpg'],[r'D:\script.ps1']]:
            window=SimpleNamespace(HWND=2,FullName=r'C:\Windows\explorer.exe',Document=SimpleNamespace(SelectedItems=lambda: [SimpleNamespace(IsFileSystem=True,IsFolder=False,Path=p) for p in paths]))
            with self.assertRaises(ValueError):selected_paths([window],2)
