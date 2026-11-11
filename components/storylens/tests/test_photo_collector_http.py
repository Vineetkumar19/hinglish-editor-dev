import io
import unittest
from types import SimpleNamespace
from urllib.parse import urlparse
from unittest.mock import Mock,patch
from hinglish_app import photo_collector_http as api

class PhotoHttpTests(unittest.TestCase):
    def handler(self,connected=True):
        h=Mock();h._authorized.return_value=connected;h._json.side_effect=lambda status,data:(status,data)
        h.wfile=io.BytesIO();return h
    def test_history_requires_connection_and_never_starts_a_job(self):
        with patch.object(api,'service') as factory:
            result=api.get(self.handler(False),SimpleNamespace(token='secret'),urlparse('/api/photos/history'))
        self.assertEqual(result[0],403);factory.assert_not_called()
    def test_actions_dispatch_only_collection_ids_not_arbitrary_paths(self):
        state=SimpleNamespace(root='root',open_path=Mock())
        with patch.object(api,'service') as factory:
            factory.return_value.snapshot.return_value={'status':'done','output_folder':'collection'}
            self.assertEqual(api.post(self.handler(),state,'/api/photos/open-folder',{'id':'saved','path':'C:/private'})[0],200)
            state.open_path.assert_called_once_with('collection')
            with self.assertRaises(ValueError):api.post(self.handler(),state,'/api/photos/delete-all',{})
    def test_zip_requires_token_and_file_resolution(self):
        with patch.object(api,'service') as factory:
            result=api.get(self.handler(False),SimpleNamespace(token='secret'),urlparse('/api/photos/file?token=wrong&kind=zip'))
        self.assertEqual(result[0],403);factory.assert_not_called()

if __name__=='__main__':unittest.main()
