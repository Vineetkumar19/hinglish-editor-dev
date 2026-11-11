import hashlib
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from hinglish_motion.reference_policy import ReferenceMediaError, validate_production_asset, withdraw_report


class ReferenceMediaPolicyTests(unittest.TestCase):
    def test_old_renderer_blocks_before_media_extraction_or_model_calls(self):
        from tools.render_one_cricaddict_sample import prepare_media, render
        with patch('subprocess.run') as run:
            for call in (lambda: prepare_media([]), render):
                with self.assertRaises(ReferenceMediaError):
                    call()
            run.assert_not_called()

    def test_cached_completed_sample_cannot_bypass_finisher_guard(self):
        from tools.finish_one_cricaddict_study import main
        with self.assertRaises(ReferenceMediaError):
            main()

    def test_reference_copy_is_rejected_even_with_owned_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            ref = Path(directory) / 'reference.mp4'; ref.write_bytes(b'reference-content')
            copy = Path(directory) / 'renamed.mp4'; copy.write_bytes(ref.read_bytes())
            with self.assertRaises(ReferenceMediaError):
                validate_production_asset(copy, {}, [ref])

    def test_download_or_face_check_does_not_establish_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'person.jpg'; file.write_bytes(b'photo')
            receipt = {'purpose':'production', 'derived_from_reference':False,
                'sha256':hashlib.sha256(file.read_bytes()).hexdigest(), 'source_url':'https://example.com/photo', 'face_checked':True}
            with self.assertRaises(ReferenceMediaError):
                validate_production_asset(file, receipt)
            receipt.update(rights='licensed', permission_evidence='licence file')
            with self.assertRaises(ReferenceMediaError):
                validate_production_asset(file, receipt)

    def test_owned_file_receipt_is_bound_to_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'voice.wav'; file.write_bytes(b'own-voice')
            receipt = {'purpose':'production','derived_from_reference':False,'rights':'owned',
                'permission_evidence':'user supplied own recording', 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
            self.assertEqual(validate_production_asset(file, receipt)['purpose'], 'production')
            file.write_bytes(b'changed')
            with self.assertRaises(ReferenceMediaError):
                validate_production_asset(file, receipt)

    def test_withdrawal_removes_player_and_sample_gallery_but_keeps_study(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'report.html'
            file.write_text('<h1>Study</h1><video src="sample.mp4"></video><p>Sample</p><h2>The local model\'s sample</h2><img src="sample.jpg"><h2>Timestamped local vision review</h2><img src="reference.jpg">', encoding='utf-8')
            withdraw_report(directory); withdraw_report(directory)
            text = file.read_text(encoding='utf-8')
            self.assertNotIn('<video', text); self.assertNotIn('sample.jpg', text)
            self.assertIn('reference.jpg', text)
            self.assertEqual(text.count('id="reference-only-notice"'), 1)

    def test_focused_local_director_receives_rules_even_when_context_is_bounded(self):
        from hinglish_motion.reference_policy import REFERENCE_RULES
        from tools.direct_first_reference_staged import guidance
        with patch('hinglish_niche.documentary_memory.context', return_value={
                'user_requirements': [f'Existing rule {i}' for i in range(16)] + REFERENCE_RULES,
                'brains': []}):
            requirements = guidance()['requirements']
        for rule in REFERENCE_RULES:
            self.assertIn(rule, requirements)
        self.assertIn('Existing rule 7', requirements)

    def test_sourcing_preserves_licence_evidence_in_fresh_and_cached_asset(self):
        from PIL import Image
        from hinglish_motion.assets import Asset, AssetFinder
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); image = root / 'input.jpg'
            Image.new('RGB', (400,400), 'blue').save(image)
            finder = AssetFinder.__new__(AssetFinder)
            finder.root = root; finder.cache = root / 'cache'; finder.cache.mkdir()
            finder.progress = lambda _: None
            finder._wikipedia = lambda _: [SimpleNamespace(url='https://example.org/image', page_url='https://example.org/file',
                source='commons', author='Photographer', license='CC BY 4.0', license_url='https://example.org/licence', nonfree=False)]
            finder._web_pictures = lambda *args: []
            finder._download = lambda _: image
            finder.check = lambda *args, **kwargs: (True, 'Portrait candidate')
            first = finder.picture(Asset('person','portrait','Person'), root / 'job', 'first', False)
            finder._wikipedia = lambda _: self.fail('A cache hit must not search again')
            second = finder.picture(Asset('person','portrait','Person'), root / 'job', 'second', False)
            for asset in (first, second):
                self.assertEqual(asset.license, 'CC BY 4.0')
                self.assertEqual(asset.license_url, 'https://example.org/licence')
                self.assertEqual(asset.credit, 'Photographer')
