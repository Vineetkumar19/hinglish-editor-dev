import unittest


class VisualReviewTextTests(unittest.TestCase):
    def test_empty_raw_review_is_honest_and_never_requests_legacy_rebuild(self):
        from hinglish_app.visual_review_text import message
        text=message({'options':0,'subjects':2},raw=True)
        self.assertIn('No verified source images',text);self.assertNotIn('ready',text)
        self.assertIn('No visual',text);self.assertNotIn('rebuild',text)

    def test_raw_sources_are_manual_bin_imports_while_legacy_remains_available(self):
        from hinglish_app.visual_review_text import message
        self.assertIn('project bin',message({'options':3,'subjects':2},raw=True))
        self.assertIn('Save & rebuild',message({'options':3,'subjects':2},raw=False))
