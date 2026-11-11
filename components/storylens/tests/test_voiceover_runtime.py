import tempfile
import unittest
from pathlib import Path
from hinglish_voice.runtime import ready, settings


class RuntimeTests(unittest.TestCase):
    def test_partial_model_download_is_not_advertised_as_ready(self):
        Path('work/voiceover-tests').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir='work/voiceover-tests') as folder:
            root=Path(folder);cfg=settings(root)
            python=Path(cfg['python']);python.parent.mkdir(parents=True);python.write_text('test')
            source=Path(cfg['source'])/'omnivoice/models/omnivoice.py';source.parent.mkdir(parents=True);source.write_text('test')
            model=Path(cfg['model']);(model/'audio_tokenizer').mkdir(parents=True)
            for name in ('config.json','model.safetensors','audio_tokenizer/config.json'):(model/name).write_text('test')
            self.assertFalse(ready(root))
            for name in ('tokenizer.json','audio_tokenizer/preprocessor_config.json','audio_tokenizer/model.safetensors'):(model/name).write_text('test')
            self.assertTrue(ready(root))


if __name__=='__main__':unittest.main()
