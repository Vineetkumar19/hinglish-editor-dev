import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from hinglish_broll.model_trace import ModelTrace


class ModelTraceTests(unittest.TestCase):
    def test_transport_metrics_are_recorded_without_changing_model_verdict(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-model-trace';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            file=Path(folder)/'calls.jsonl'
            model=SimpleNamespace(name='local-test-model',session=SimpleNamespace(hooks={'response':[]}))
            trace=ModelTrace(model,file)
            negative={'passed':False,'reason':'wrong subject'}
            response=Mock(status_code=200);response.json.return_value={'model':'local-test-model','total_duration':123,
                'load_duration':11,'prompt_eval_count':200,'eval_count':30}
            def look(*args):
                for hook in model.session.hooks['response']:hook(response)
                return negative
            model.look=look
            self.assertIs(trace.look([], 'private input', {}),negative)
            event=json.loads(file.read_text('utf-8'))
            self.assertEqual(event['http_requests_observed'],1)
            self.assertEqual(event['responses'][0]['prompt_eval_count'],200)
            self.assertNotIn('private input',file.read_text('utf-8'))
            self.assertEqual(negative,{'passed':False,'reason':'wrong subject'})

    def test_model_failure_is_preserved_and_logged_as_failure(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-model-trace';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            file=Path(folder)/'calls.jsonl';model=SimpleNamespace(name='local',look=Mock(side_effect=TimeoutError('fixture timeout')))
            trace=ModelTrace(model,file)
            with self.assertRaises(TimeoutError):trace.look([],'input',{})
            event=json.loads(file.read_text('utf-8'));self.assertEqual(event['status'],'failed')
            self.assertEqual(event['http_requests_observed'],0)


if __name__=='__main__':unittest.main()
