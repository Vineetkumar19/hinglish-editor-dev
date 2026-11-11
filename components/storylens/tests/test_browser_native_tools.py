import tempfile
import unittest
from pathlib import Path

from hinglish_app.native_browser_bridge import BrowserNativeBridge


class BrowserNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.clock=[10.]
        self.bridge=BrowserNativeBridge(self.temp.name,clock=lambda:self.clock[0])
    def tearDown(self):self.temp.cleanup()
    def test_disconnected_has_no_fake_success(self):
        with self.assertRaises(ValueError):self.bridge.submit({'action':'templateAlign','request_id':'one','payload':{}})
    def test_delivers_once_binds_project_and_reuses_request(self):
        identity=self.bridge.register('client','aftereffects','project-a')
        payload={'action':'templateAlign','request_id':'one','payload':{}}
        item=self.bridge.submit(payload)
        self.assertEqual(item['id'],self.bridge.submit(payload)['id'])
        command=self.bridge.poll(**identity)['command']
        self.assertEqual(command['project_id'],'project-a')
        self.assertIsNone(self.bridge.poll(**identity)['command'])
        answer=self.bridge.ack(**identity,id=item['id'],result={'ok':True})
        self.assertEqual(answer['status'],'confirmed')
    def test_unsupported_actions_and_stale_connections_rejected(self):
        self.bridge.register('client','aftereffects','project-a')
        with self.assertRaises(ValueError):self.bridge.submit({'action':'eval','payload':{},'request_id':'x'})
        self.clock[0]+=31
        with self.assertRaises(ValueError):self.bridge.submit({'action':'templateAlign','payload':{},'request_id':'x'})
    def test_uncertain_command_cannot_replay_after_restart(self):
        identity=self.bridge.register('client','aftereffects','project-a')
        item=self.bridge.submit({'action':'templateAlign','payload':{},'request_id':'x'})
        self.bridge.poll(**identity)
        other=BrowserNativeBridge(self.temp.name)
        self.assertEqual(other.status(item['id'])['status'],'unconfirmed')
        other.register('client','aftereffects','project-a')
        retry=other.submit({'action':'templateAlign','payload':{},'request_id':'x'})
        self.assertEqual(retry['id'],item['id'])
        self.assertEqual(retry['status'],'unconfirmed')
    def test_receipts_do_not_accumulate_payloads_in_memory(self):
        identity=self.bridge.register('client','aftereffects','project-a')
        first=None
        for n in range(40):
            item=self.bridge.submit({'action':'templateAlign','payload':{},'request_id':'r'+str(n)})
            if first is None:first=item['id']
            self.bridge.poll(**identity);self.bridge.ack(**identity,id=item['id'],result={'ok':True})
        self.assertLessEqual(len(self.bridge.records),32)
        self.assertEqual(self.bridge.submit({'action':'templateAlign','payload':{},'request_id':'r0'})['id'],first)
