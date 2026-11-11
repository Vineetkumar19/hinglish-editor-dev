import json
from pathlib import Path
import tempfile
import threading
import unittest


class EditorProgressEventTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='cache');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_actual_event_clock_and_only_whitelisted_fields_are_written(self):
        from hinglish_app.progress_events import record
        record(self.root,'job','one',status='queued',stage='Starting',headers={'secret':'never'},payload='never')
        record(self.root,'job','one',status='running',stage='Checking https://source.example/a?token=private')
        rows=[json.loads(line) for line in (self.root/'cache/app/progress-events/job-one.jsonl').read_text('utf-8').splitlines()]
        self.assertGreaterEqual(rows[1]['monotonic_ns'],rows[0]['monotonic_ns'])
        self.assertEqual(rows[0]['status'],'queued');self.assertNotIn('headers',rows[0]);self.assertNotIn('payload',rows[0])
        self.assertNotIn('private',rows[1]['stage'])

    def test_progress_hook_records_real_controller_boundary_without_model_or_job_dispatch(self):
        from hinglish_app.server import AppState
        state=AppState.__new__(AppState);state.root=self.root;state.lock=threading.Lock()
        state.jobs={'one':{'id':'one','mode':'visuals','status':'running'}}
        state._persist_visuals_job=lambda job:None;state._persist_broll_job=lambda job:None
        state._update('one',stage='Checking physical source',progress=28)
        event=json.loads((self.root/'cache/app/progress-events/job-one.jsonl').read_text('utf-8').splitlines()[-1])
        self.assertEqual(event['stage'],'Checking physical source');self.assertEqual(event['progress'],28)

    def test_diagnostic_write_failure_does_not_change_original_workflow(self):
        from hinglish_app.progress_events import record
        self.assertFalse(record(self.root,'job','../outside',stage='Keep source'))

    def test_actual_assistant_stage_hook_keeps_request_payload_out_of_diagnostics(self):
        from hinglish_app.assistant import Assistant
        assistant=Assistant.__new__(Assistant);assistant.root=self.root;assistant.lock=threading.RLock()
        session={};assistant._get=lambda key:session;assistant._save=lambda value:None
        assistant._update('chat-one',status='working',stage='Understanding your request',payload={'never':'record'},kind='not-a-diagnostic-kind')
        event=json.loads((self.root/'cache/app/progress-events/assistant-chat-one.jsonl').read_text('utf-8'))
        self.assertEqual(event['stage'],'Understanding your request');self.assertNotIn('payload',event)

