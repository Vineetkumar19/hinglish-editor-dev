"""Controller fixtures, not evidence of genuine model subject resolution."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


def receipt(root, job='one'):
    output=root/'output/visuals/example';output.mkdir(parents=True,exist_ok=True)
    state={'version':1,'needs_clarification':True,'questions':['What does "PG" refer to in this line?'],
        'outcomes':{'pg':{'original_name':'PG','quoted_words':['PG'], 'known_meanings':[],
            'needs_clarification':True,'clarification_question':'What does "PG" refer to in this line?'}}}
    target=output/'visuals-resolution.json';target.write_text(json.dumps(state))
    work=root/'cache/app/jobs'/job;work.mkdir(parents=True,exist_ok=True)
    (work/'visuals-clarification.json').write_text(json.dumps({**state,'resolution_file':str(target)}))
    return state


class VisualClarificationBridgeTests(unittest.TestCase):
    def test_bound_question_keeps_original_quotes_and_known_meanings(self):
        from hinglish_app.visual_clarification import read
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();expected=receipt(root)
            actual=read(root,'one')
            self.assertEqual(actual['outcomes'],expected['outcomes'])
            self.assertEqual(actual['questions'],expected['questions'])

    def test_missing_false_or_foreign_receipts_are_not_questions(self):
        from hinglish_app.visual_clarification import read
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();self.assertIsNone(read(root,'one'));receipt(root)
            marker=root/'cache/app/jobs/one/visuals-clarification.json'
            data=json.loads(marker.read_text());data['needs_clarification']='true'
            marker.write_text(json.dumps(data));self.assertIsNone(read(root,'one'))
            data['needs_clarification']=True;data['resolution_file']=str(root/'foreign.json')
            marker.write_text(json.dumps(data));self.assertIsNone(read(root,'one'))

    def test_normal_worker_question_stops_before_saved_media_recovery(self):
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();receipt(root)
            source=root/'source.mp4';source.write_bytes(b'controller fixture only')
            state=AppState.__new__(AppState);state.root=root;state.engine_root=root
            state.python_executable=Path(sys.executable);state.license_client=None;state.lock=threading.Lock()
            state.jobs={'one':{'id':'one','mode':'visuals','status':'running','logs':[]}}
            state._stage_sources=Mock(return_value=None)
            process=Mock();process.stdout=iter(['Error: Please clarify the subject\n']);process.wait.return_value=1
            payload={'mode':'visuals','profile':'gaming','_creator_context':{'profile':'gaming','all':'retained'}}
            with patch('hinglish_app.server.subprocess.Popen',return_value=process), \
                 patch('hinglish_visuals.recovery.resumable_projects') as recovery:
                state._execute_job('one',payload,[],source,'')
            job=state.jobs['one'];self.assertEqual(job['error_code'],'visuals_clarification_required')
            self.assertTrue(job['needs_input']);self.assertIn('What does "PG"',job['stage'])
            recovery.assert_not_called();self.assertNotIn('result',job)

    def test_chat_asks_without_importing_or_discarding_original_source(self):
        from hinglish_app.server import AppState
        from hinglish_app.visual_clarification import pause
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();state=AppState(root);assistant=state.assistant
            session=assistant.create()['id'];source=root/'source.mp4';source.write_bytes(b'fixture')
            assistant._update(session,profile='gaming',original_paths=[str(source)])
            typed=receipt(root)
            job={'id':'one','status':'failed','error_code':'visuals_clarification_required',
                'needs_input':True,'clarification':typed}
            with patch('hinglish_app.assistant_media.outputs') as outputs:
                self.assertTrue(pause(assistant,session,job,'Run Smart Visuals',{'mode':'visuals'}))
            saved=assistant.snapshot(session)
            self.assertEqual(saved['status'],'idle');self.assertTrue(saved['needs_input'])
            self.assertTrue(saved['messages'][-1]['question']);self.assertEqual(saved['profile'],'gaming')
            self.assertEqual(saved['original_paths'],[str(source)])
            self.assertEqual(saved['visual_clarification']['outcomes'],typed['outcomes'])
            outputs.assert_not_called()


if __name__=='__main__':unittest.main()
