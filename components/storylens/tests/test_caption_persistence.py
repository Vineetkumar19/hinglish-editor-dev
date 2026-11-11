from pathlib import Path
import tempfile,unittest
from unittest.mock import patch

class CaptionPersistenceTests(unittest.TestCase):
    def test_short_windows_reader_lock_is_retried_and_old_result_is_not_lost(self):
        from hinglish_app.caption_persistence import save
        import os,json
        with tempfile.TemporaryDirectory(dir='tmp') as tmp:
            path=Path(tmp)/'status.json';path.write_text('{"status":"running"}')
            original=os.replace;calls=[]
            def replace(a,b):
                calls.append(1)
                if len(calls)<3:raise PermissionError('Windows reader holds the file')
                original(a,b)
            with patch('hinglish_app.caption_persistence.os.replace',side_effect=replace),patch('hinglish_app.caption_persistence.time.sleep'):
                save(path,{'status':'complete'})
            self.assertEqual(json.loads(path.read_text())['status'],'complete');self.assertEqual(len(calls),3)
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

    def test_permanent_failure_keeps_the_previous_receipt_and_removes_only_own_temp(self):
        from hinglish_app.caption_persistence import save
        with tempfile.TemporaryDirectory(dir='tmp') as tmp:
            path=Path(tmp)/'status.json';path.write_text('old');other=Path(tmp)/'owner.tmp';other.write_text('keep')
            with patch('hinglish_app.caption_persistence.os.replace',side_effect=PermissionError('blocked')),patch('hinglish_app.caption_persistence.time.sleep'):
                with self.assertRaises(PermissionError):save(path,{'status':'complete'})
            self.assertEqual(path.read_text(),'old');self.assertEqual(other.read_text(),'keep')
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[other])
