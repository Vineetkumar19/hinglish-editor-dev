from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from hinglish_publish.store import Store

class RefreshCopyTests(TestCase):
 def test_refresh_preserves_date_identity_and_original_copy_history(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   store=Store(tmp);old={'title':'Old title','description':'A match.','instagram_caption':'Match.','tags':['Cricket']};new={**old,'title':'New title'}
   item={'profile':'cricket','platform':'youtube','kind':'short','fingerprint':'same-bytes','metadata':old,'brain':'local'}
   key=store.add_batch([item])[0];before=store.get(key)
   store.refresh_draft_copy([key],[{**item,'metadata':new}],{key:old})
   after=store.get(key);self.assertEqual(after['due'],before['due']);self.assertEqual(after['metadata'],new);self.assertEqual(after['metadata_history'][-1]['metadata'],old)
   with self.assertRaises(ValueError):store.refresh_draft_copy([key],[{**item,'metadata':old}],{key:old})
   self.assertEqual(store.get(key)['metadata'],new)
