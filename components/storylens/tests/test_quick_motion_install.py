import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_quick_motion', ROOT / 'tools/install_quick_motion.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class QuickMotionInstallTests(unittest.TestCase):
    def test_narrow_insert_preserves_every_other_route_and_is_idempotent(self):
        source = "before-owner\n   if(host==='aftereffects'&&message.action==='presetLibrary'){\n    const path=require('path'),root=window.HINGLISH_APP_ROOT;if(!root)throw Error('Reopen the installed Storylens panel to use Presets.');\nOWNER_PRESET_CODE\n   }\nOWNER_OTHER_ROUTES"
        new = module.patched(source)
        self.assertIn('OWNER_PRESET_CODE', new)
        self.assertIn('OWNER_OTHER_ROUTES', new)
        self.assertEqual(new.count("['motionCatalog','applyMotion']"), 1)
        self.assertEqual(module.patched(new), new)
        self.assertEqual(new.replace(module.route_block(), ''), source)

    def test_unexpected_shell_refuses_before_writing(self):
        with self.assertRaises(RuntimeError):
            module.patched('different panel')

if __name__ == '__main__':
    unittest.main()
