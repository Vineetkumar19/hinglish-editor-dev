"""The fresh native worker must own the GPU slot, never its waiting parent."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hinglish_cut.gpu_lock import gpu_lock, _held


class WorkerGpuOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_parent_dispatch_keeps_work_serialized_without_owning_child_gpu_slot(self):
        from hinglish_app.prepare_post_http import dispatch
        engine=Mock();engine.get.return_value={'status':'failed'};engine._submitted=set()
        def execute(*args):
            self.assertEqual(_held.get(),())
            return {'status':'prepared'}
        engine.run.side_effect=execute
        publisher=Mock();publisher.task.side_effect=lambda work:work()
        state=SimpleNamespace(root=self.root,publisher=publisher,work_lock=threading.RLock())
        with patch('hinglish_app.prepare_post_http.service',return_value=engine):
            dispatch(state,{'action':'start','profile':'cricket','id':'same-job'})
        engine.run.assert_called_once()

    def test_worker_owns_slot_and_nested_model_guard_is_reentrant(self):
        from hinglish_publish.prepare_post_worker import main
        request=self.root/'request.json'
        request.write_text(json.dumps({'root':str(self.root),'stage':'selection','draft':{}}))
        runtime=Mock()
        def stage(*args):
            self.assertEqual(len(_held.get()),1)
            with gpu_lock(self.root):
                self.assertEqual(len(_held.get()),1)
            return {'model_result':'fixture; no inference'}
        runtime.stage.side_effect=stage
        with patch('hinglish_publish.prepare_post_runtime.LocalRuntime',return_value=runtime):
            self.assertEqual(main(['--request',str(request)]),0)
        self.assertEqual(_held.get(),())
        self.assertTrue((self.root/'result.json').is_file())
