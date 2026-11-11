import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from hinglish_cut.local_runtime import ensure


class LocalRuntimeTests(unittest.TestCase):
    def test_never_starts_for_a_remote_endpoint_or_unconfigured_store(self):
        session = Mock()
        with tempfile.TemporaryDirectory() as folder, patch('hinglish_cut.local_runtime.subprocess.Popen') as launch:
            self.assertFalse(ensure(folder, session, 'https://remote.example'))
            self.assertFalse(ensure(folder, session, 'http://127.0.0.1:11434'))
            launch.assert_not_called()
            session.get.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows runtime startup')
    def test_starts_only_installed_runtime_with_selected_store_and_loopback_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root / 'local/Programs/Ollama/ollama.exe'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'fixture-not-executed')
            (root / 'models/ollama').mkdir(parents=True)
            (root / 'config.model_storage.local.json').write_text(json.dumps({'active': True, 'root': str(root/'models')}))
            session = Mock()
            session.get.side_effect = [ConnectionError('not running'), SimpleNamespace(ok=True)]
            with patch.dict(os.environ, {'LOCALAPPDATA': str(root/'local')}), \
                 patch('hinglish_cut.local_runtime.subprocess.Popen') as launch:
                self.assertTrue(ensure(root, session, 'http://127.0.0.1:11434'))
            args, kwargs = launch.call_args
            self.assertEqual(args[0], [str(binary), 'serve'])
            self.assertEqual(kwargs['env']['OLLAMA_HOST'], '127.0.0.1:11434')
            self.assertEqual(kwargs['env']['OLLAMA_MODELS'], str(root/'models/ollama'))
            self.assertEqual(kwargs['env']['OLLAMA_NO_CLOUD'], '1')


if __name__ == '__main__':
    unittest.main()
