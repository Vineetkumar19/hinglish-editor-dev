import tempfile
import threading
import unittest
from pathlib import Path


class EditingActivityTests(unittest.TestCase):
    def test_raw_asr_warning_stays_in_logs_without_replacing_plain_activity(self):
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            state=AppState.__new__(AppState);state.root=Path(folder);state.lock=threading.Lock()
            state.jobs={'one':{'id':'one','mode':'broll','logs':[],'stage':'Transcribing speech'}}
            state._persist_visuals_job=lambda job:None;state._persist_broll_job=lambda job:None
            warning='transformers/asr.py:42: FutureWarning: Whisper argument is deprecated'
            state._log('one',warning)
            self.assertEqual(state.jobs['one']['logs'][-1],warning)
            self.assertEqual(state.jobs['one']['stage'],'Transcribing speech')

    def test_asr_progress_has_plain_text_and_real_failure_is_not_hidden(self):
        from hinglish_app.user_messages import editing_activity
        self.assertEqual(editing_activity('Words and timing 1/2 (0.0s)','Preparing'),'Transcribing speech')
        self.assertEqual(editing_activity('Error: video missing','Transcribing speech'),'Error: video missing')
