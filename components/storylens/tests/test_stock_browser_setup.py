import unittest
from pathlib import Path
class StockSetupTests(unittest.TestCase):
    def test_setup_uses_actual_connection_state_and_shared_errors_without_displaying_keys(self):
        base=Path(__file__).resolve().parents[1]/'hinglish_app/static'
        html=(base/'stock-browser.html').read_text('utf-8');script=(base/'stock-browser.js').read_text('utf-8')
        self.assertIn('feedback.js',html);self.assertIn('Connect Chrome',html)
        self.assertIn('storylensResponse',script);self.assertIn('status.connected',script)
        self.assertNotIn('textContent=pair.key',script)
        self.assertIn('chrome.runtime.sendMessage',script)
        self.assertIn('stock-browser.html',(base/'index.html').read_text('utf-8'))

if __name__=='__main__':unittest.main()
