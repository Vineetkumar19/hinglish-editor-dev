import unittest
from hinglish_app.adobe_folder_cleanup import collapse_search, title_matches, ensure_search_focus, read_live_search


class Search:
    def __init__(self, value='', interfere=False):
        self.value = value
        self.writes = []
        self.interfere = interfere
    def read(self):
        return self.value
    def write(self, value):
        self.writes.append(value)
        self.value = 'owner typed a filter' if self.interfere else value


class AdobeFolderCleanupTests(unittest.TestCase):
    def test_blank_search_is_reset_without_touching_project_content(self):
        search = Search()
        result = collapse_search(search, lambda: True)
        self.assertTrue(result['ok'])
        self.assertEqual(len(search.writes), 2)
        self.assertTrue(search.writes[0])
        self.assertEqual(search.writes[-1], '')
    def test_search_changes_are_committed_before_reset(self):
        class Committed(Search):
            def __init__(self):
                super().__init__()
                self.commits = []
            def commit(self):
                self.commits.append(self.value)
        search = Committed()
        self.assertTrue(collapse_search(search, lambda: True)['ok'])
        self.assertEqual(len(search.commits), 2)
        self.assertTrue(search.commits[0])
        self.assertEqual(search.commits[1], '')

    def test_user_filter_is_preserved(self):
        search = Search('photos')
        result = collapse_search(search, lambda: True)
        self.assertFalse(result['ok'])
        self.assertIn('search', result['message'])
        self.assertEqual(search.writes, [])
    def test_project_switch_stops_before_mutation(self):
        search = Search()
        self.assertFalse(collapse_search(search, lambda: False)['ok'])
        self.assertEqual(search.writes, [])
    def test_user_typing_during_cleanup_is_not_erased(self):
        search = Search(interfere=True)
        self.assertFalse(collapse_search(search, lambda: True)['ok'])
        self.assertEqual(search.value, 'owner typed a filter')
        self.assertEqual(len(search.writes), 1)
    def test_title_must_match_full_saved_project_path(self):
        self.assertTrue(title_matches('Adobe After Effects 2026 - D:\\Edits\\2.aep *', 'd:/edits/2.aep'))
        self.assertFalse(title_matches('Adobe After Effects 2026 - B:\\Other\\2.aep', 'D:/Edits/2.aep'))
        self.assertFalse(title_matches('Premiere Pro - D:\\Edits\\2.aep', 'D:/Edits/2.aep'))


class SearchFocusTests(unittest.TestCase):
    def test_verified_focus_needs_no_click(self):
        calls=[]
        ensure_search_focus(lambda:calls.append('focus'),lambda:True,lambda:True,lambda:calls.append('click'))
        self.assertEqual(calls,['focus'])
    def test_native_focus_failure_uses_one_checked_click(self):
        state={'focused':False};calls=[]
        def click():
            calls.append('click');state['focused']=True
        ensure_search_focus(lambda:None,lambda:state['focused'],lambda:True,click)
        self.assertEqual(calls,['click'])
    def test_focus_change_prevents_fallback_click(self):
        calls=[]
        with self.assertRaises(RuntimeError):ensure_search_focus(lambda:None,lambda:False,lambda:False,lambda:calls.append('click'))
        self.assertEqual(calls,[])
    def test_click_without_verified_search_focus_never_allows_typing(self):
        with self.assertRaises(RuntimeError):ensure_search_focus(lambda:None,lambda:False,lambda:True,lambda:None)

class LiveSearchTests(unittest.TestCase):
    def test_invalidated_native_search_is_reacquired_once(self):
        state={'fresh':False};calls=[]
        def read():
            if not state['fresh']:raise RuntimeError('Element unavailable')
            return 'query'
        def refresh():
            state['fresh']=True;calls.append('refresh')
        self.assertEqual(read_live_search(read,refresh),'query');self.assertEqual(calls,['refresh'])
    def test_second_native_failure_is_not_silenced(self):
        def fail():raise RuntimeError('unavailable')
        with self.assertRaises(RuntimeError):read_live_search(fail,lambda:None)

class UnsavedProjectCleanupTests(unittest.TestCase):
    def test_known_unsaved_session_matches_only_default_untitled_project(self):
        self.assertTrue(title_matches('Adobe After Effects 2026 - Untitled Project.aep *','unsaved-123456'))
        self.assertFalse(title_matches('Adobe After Effects 2026 - D:\\Owner.aep','unsaved-123456'))
        self.assertFalse(title_matches('Adobe After Effects 2026 - Other.aep','unsaved-123456'))
        self.assertFalse(title_matches('Adobe After Effects 2026 - Untitled Project.aep *','unsaved-bad'))
