import unittest
from pathlib import Path


class PhoneLauncherContracts(unittest.TestCase):
    def test_launchers_keep_only_the_private_companion_exposed(self):
        root=Path(__file__).resolve().parents[1]
        start=(root/'tools'/'start_storylens_phone.ps1').read_text('utf-8')
        stop=(root/'tools'/'stop_storylens_phone.ps1').read_text('utf-8')
        self.assertIn('127.0.0.1:8796',start)
        self.assertIn('phone/health',start)
        self.assertIn('hinglish_app.phone_remote',start)
        self.assertIn('serve --bg --https=443',start)
        self.assertNotIn('funnel --bg',start.lower())
        self.assertNotIn('serve reset',start.lower())
        self.assertIn('Stop-Process -Id',stop)
        self.assertNotIn('Stop-Process -Name',stop)
        self.assertIn('--revoke-all',stop)
        self.assertIn('hinglish_app.phone_remote',stop)
        self.assertTrue((root/'Start Storylens Phone.cmd').is_file())
        self.assertTrue((root/'Stop Storylens Phone.cmd').is_file())


if __name__=='__main__':
    unittest.main()
