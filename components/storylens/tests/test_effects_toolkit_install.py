import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_effects_toolkit', ROOT / 'tools/install_effects_toolkit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ToolkitInstallTests(unittest.TestCase):
    def test_install_is_narrow_and_idempotent(self):
        old = 'OWNER_BEFORE\n' + module.ANCHOR + 'OWNER_AFTER\n'
        new = module.patched(old)
        self.assertEqual(module.patched(new), new)
        self.assertEqual(''.join(line for line in new.splitlines(keepends=True) if not line.startswith(module.MARKER)), old)

    def test_missing_or_duplicate_anchor_is_refused(self):
        for old in ['other', module.ANCHOR * 2]:
            with self.assertRaises(RuntimeError):
                module.patched(old)

if __name__ == '__main__':
    unittest.main()
