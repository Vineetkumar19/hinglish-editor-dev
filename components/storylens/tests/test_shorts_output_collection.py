import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_app.assistant_media import outputs


class OutputCollectionTests(unittest.TestCase):
    def test_completed_shorts_are_collected_without_implicit_model_or_render_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'output/shorts/run/video';base.mkdir(parents=True)
            clip=base/'completed.mp4';clip.write_bytes(b'finished-export')
            (base/'shorts-project.json').write_text(json.dumps({'shorts':[{'mp4':clip.name}]}),'utf-8')
            with patch('hinglish_shorts.title_review.ensure_project') as titles,\
                 patch('hinglish_captions.proofread.ensure_project') as captions:
                actual=outputs(root,{'tool':'shorts'},{'folder':str(base)},base,lambda _:None)
            self.assertEqual(actual,[str(clip.resolve())])
            titles.assert_not_called();captions.assert_not_called()
            self.assertEqual(clip.read_bytes(),b'finished-export')


if __name__=='__main__':unittest.main()
