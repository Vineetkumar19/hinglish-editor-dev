import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from hinglish_publish.signin import start, valid_google_url

URL='https://accounts.google.com/o/oauth2/auth?client_id=fixture&state=test&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A5555%2F'

class SignInTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(self.tmp.cleanup)
        self.publisher=SimpleNamespace(root=Path(self.tmp.name),lock=threading.RLock(),preparing=threading.Lock(),tasks={})
        self.release=threading.Event();self.finished=threading.Event()
        self.addCleanup(self.release.set)
    def connect(self,root,client_file,profile,*,on_authorization):
        on_authorization(URL);self.release.wait(3);self.finished.set()
        return {'channel_id':'same-channel','name':'Saved channel'}
    def test_repeated_clicks_reuse_one_signin_and_do_not_wait_for_media_preparation(self):
        self.publisher.preparing.acquire();self.addCleanup(self.publisher.preparing.release)
        with patch('hinglish_publish.providers.connect_youtube',side_effect=self.connect) as connect:
            one=start(self.publisher,'','cricket');two=start(self.publisher,'','cricket')
            self.assertEqual(one['id'],two['id']);self.assertEqual(one['authorization_url'],URL)
            self.assertEqual(len(self.publisher.tasks),1);self.assertEqual(connect.call_count,1)
            task=self.publisher.tasks[one['id']];self.assertEqual(task['kind'],'youtube_signin');self.assertEqual(task['profile'],'cricket')
            self.release.set();self.finished.wait(1)
    def test_failure_is_retryable_without_claiming_connection_success(self):
        with patch('hinglish_publish.providers.connect_youtube',side_effect=ValueError('Choose the original Google desktop OAuth client JSON file.')):
            result=start(self.publisher,'','gaming');self.assertEqual(self.publisher.tasks[result['id']]['status'],'failed')
            self.assertNotIn('authorization_url',result)
            again=start(self.publisher,'','gaming');self.assertNotEqual(again['id'],result['id'])
    def test_profile_validation_and_google_only_link(self):
        self.assertTrue(valid_google_url(URL))
        for bad in ['javascript:alert(1)',URL.replace('accounts.google.com','accounts.google.com.evil.invalid'),URL.replace('https://','http://'),URL.replace('accounts.google.com','attacker@accounts.google.com')]:
            self.assertFalse(valid_google_url(bad))
        with self.assertRaises(ValueError):start(self.publisher,'','not-a-profile')
