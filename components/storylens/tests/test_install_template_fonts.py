import json
import tempfile
import unittest
from pathlib import Path
from tools.install_template_fonts import prepare_plan


class InstallTemplateFontsTests(unittest.TestCase):
    def test_changed_source_is_rejected_before_installation(self):
        base = Path(__file__).resolve().parents[1] / 'output/template-fonts/test-temp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            source = Path(temp) / 'font.ttf'
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                prepare_plan({'fonts': [{'source': str(source), 'sha256': 'bad'}]}, Path(temp) / 'target')

    def test_empty_manifest_is_noop(self):
        self.assertEqual(prepare_plan({'fonts': []}, Path('target')), [])
