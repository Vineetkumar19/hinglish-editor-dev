import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_cut import model_storage
from hinglish_cut.model_preferences import resolve_model


class ModelStorageTests(unittest.TestCase):
    def test_staged_models_are_not_used_until_activated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            data={'active':False,'roles':{'planner':{'ollama_model':'staged:9b'}},
                  'aliases':{'old':'new'}}
            (root/'config.model_storage.local.json').write_text(json.dumps(data))
            self.assertEqual(model_storage.role(root,'planner'),{})
            self.assertEqual(model_storage.selected_path(root,'old'),'old')
            self.assertEqual(resolve_model(root,'planning_model','legacy','legacy'),'legacy')
            data['active']=True
            (root/'config.model_storage.local.json').write_text(json.dumps(data))
            self.assertEqual(model_storage.selected_path(root,'old'),'new')
            self.assertEqual(resolve_model(root,'planning_model','legacy','legacy'),'staged:9b')
            self.assertEqual(resolve_model(root,'planning_model','custom','legacy'),'custom')

    def test_validator_override_does_not_rewrite_live_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            live=root/'config.model_storage.local.json'
            live.write_text('{"active":false}')
            staged=root/'pending.json'
            staged.write_text(json.dumps({'active':True,'roles':{'asr':{'path':'new-asr'}}}))
            with patch.dict(os.environ,{'STORYLENS_MODEL_SELECTION':str(staged)}):
                self.assertEqual(model_storage.role(root,'asr')['path'],'new-asr')
            self.assertEqual(model_storage.role(root,'asr'),{})
            self.assertEqual(live.read_text(),'{"active":false}')

    def test_model_identity_changes_transcript_cache_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.model_storage.local.json'
            path.write_text('{"active":true,"roles":{"asr":{"revision":"first"}}}')
            before=model_storage.signature(folder)
            path.write_text('{"active":true,"roles":{"asr":{"revision":"second"}}}')
            self.assertNotEqual(before,model_storage.signature(folder))

    def test_external_destination_requires_explicit_configured_root(self):
        from tools.ranged_download import ranged_get
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as other:
            path=Path(folder)/'model.incomplete'
            stream=Mock(name='stream');stream.name=str(path)
            with self.assertRaisesRegex(ValueError,'configured download roots'):
                ranged_get('https://unused.invalid',stream,0,download_root=Path(other))
            with path.open('w+b') as handle:
                ranged_get('https://unused.invalid',handle,0,download_root=Path(folder))


if __name__=='__main__': unittest.main()
