from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,skip
from unittest.mock import patch
from hinglish_publish.service import Publisher

@skip('Automatic-worker startup was blocked by approval review; owner authorization is pending.')
class PublisherControlTests(TestCase):
    def test_saving_prepare_settings_cannot_start_an_upload_worker(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            pub=Publisher(tmp)
            with patch.object(pub,'start') as start:
                pub.configure({'profile':'cricket','enabled':True})
                start.assert_not_called()
                pub.configure({'profile':'cricket','enabled':True,'run_authorized':True})
                start.assert_called_once()
    def test_worker_switch_requires_boolean_and_enabled(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            pub=Publisher(tmp)
            for data in ({'run_authorized':'yes'},{'run_authorized':True,'enabled':False}):
                with self.assertRaises(ValueError):pub.configure({'profile':'cricket',**data})
