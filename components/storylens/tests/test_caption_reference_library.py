import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hinglish_captions.reference_library import discover,prepare,digest
from hinglish_captions.auto_caption import validate

ROOT=Path(__file__).resolve().parents[1]


class ReferenceLibraryTests(unittest.TestCase):
    def setup_library(self,root,folder):
        (root/'hinglish_captions').mkdir()
        (root/'hinglish_captions/auto_caption_references.json').write_text(json.dumps({'reference_folder':str(folder),'styles':[]}))
        (root/'hinglish_captions/reference_catalog.json').write_text(json.dumps({'references':[]}))

    def test_new_renamed_removed_files_and_natural_order(self):
        with TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            root=Path(tmp);folder=root/'videos';folder.mkdir();self.setup_library(root,folder)
            for name in ('Caption 12.mp4','Caption 9.mp4','favorite caption.MOV','notes.txt'):(folder/name).write_bytes(b'video')
            rows=discover(root)
            self.assertEqual([r['name'] for r in rows],['Caption 9','Caption 12','favorite caption'])
            old=rows[0]['style'];(folder/'Caption 9.mp4').rename(folder/'My choice.mp4')
            updated=discover(root);self.assertNotIn(old,[r['style'] for r in updated])
            (folder/'Caption 10.webm').write_bytes(b'video')
            self.assertIn('Caption 10',[r['name'] for r in discover(root)])
            (folder/'Caption 12.mp4').unlink()
            self.assertNotIn('Caption 12',[r['name'] for r in discover(root)])

    def test_new_reference_passes_validation_for_both_methods(self):
        row={'style':'reference_abc','available':True,'base_style':None}
        with patch('hinglish_captions.auto_caption.references',return_value=[row]):
            for method in ('hyperframes','local_llm'):
                settings,_=validate(ROOT,dict(style=row['style'],text='Keep every word readable',duration=10,method=method))
                self.assertEqual(settings['style'],row['style'])

    def test_renamed_known_video_reuses_prepared_style_without_model(self):
        from hinglish_captions.auto_caption import references
        row=next(r for r in references(ROOT) if r['style']=='caption_2')
        ref=dict(row,style='reference_new',base_style=None)
        with patch('hinglish_captions.auto_caption.see',side_effect=AssertionError('Unexpected model call')):
            result=prepare(ROOT,ref,ROOT/'tmp',lambda _:None)
        self.assertEqual(result['base_style'],'caption_2');self.assertFalse(result['approximate'])

    def test_content_change_does_not_reuse_stale_preparation(self):
        with TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            root=Path(tmp);folder=root/'videos';folder.mkdir();self.setup_library(root,folder)
            video=folder/'favorite.mp4';video.write_bytes(b'old video');sha=digest(video)
            cache=root/'cache/captions/reference-library';cache.mkdir(parents=True)
            (cache/(sha+'.json')).write_text(json.dumps({'base_style':'caption_2','sha256':sha}))
            video.write_bytes(b'different video')
            with patch('hinglish_captions.auto_caption.extract_reference',side_effect=RuntimeError('Fresh analysis required')):
                with self.assertRaisesRegex(RuntimeError,'Fresh analysis required'):prepare(root,discover(root)[0],root,lambda _:None)

    def test_missing_folder_has_useful_error(self):
        with TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            root=Path(tmp);self.setup_library(root,root/'missing')
            with self.assertRaisesRegex(FileNotFoundError,'Caption reference folder unavailable'):discover(root)
