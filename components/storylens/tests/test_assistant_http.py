import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from hinglish_app.server import serve


class AssistantHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server, self.state = serve(self.root, 0)
        self.base = f'http://127.0.0.1:{self.state.port}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def call(self, path, body=None, auth=True):
        data = None if body is None else json.dumps(body).encode()
        headers = {'Content-Type': 'application/json'}
        if auth: headers['X-Hinglish-Token'] = self.state.token
        with urlopen(Request(self.base + path, data=data, headers=headers)) as r:
            return json.load(r)

    def test_chat_creation_and_snapshot_are_protected(self):
        with self.assertRaises(HTTPError) as caught:
            self.call('/api/assistant/session', {}, auth=False)
        self.assertEqual(caught.exception.code, 403)
        s = self.call('/api/assistant/session', {})
        self.assertEqual(self.call('/api/assistant/session?id=' + s['id'])['id'], s['id'])
        with self.assertRaises(HTTPError):
            self.call('/api/assistant/session?id=' + s['id'], auth=False)

    def test_scheduled_posts_require_owner_and_list_does_not_dispatch(self):
        with self.assertRaises(HTTPError):self.call('/api/scheduled',auth=False)
        with self.assertRaises(HTTPError):self.call('/api/scheduled/action',{'action':'publish_now'},auth=False)
        self.assertEqual(self.call('/api/scheduled')['posts'],[])
        self.assertFalse(self.state.local_browser.data['jobs'])
        self.assertFalse(self.state.publisher.store.list())

    def test_history_search_and_transcript_require_owner_and_reopen_original_chat(self):
        chat=self.call('/api/assistant/session',{})
        self.state.assistant._message(chat['id'],'user','Remember my long SEO description preference.')
        with self.assertRaises(HTTPError):self.call('/api/assistant/history',auth=False)
        with self.assertRaises(HTTPError):self.call('/api/assistant/messages?id='+chat['id'],auth=False)
        rows=self.call('/api/assistant/history?q=SEO')['chats']
        self.assertEqual(rows[0]['id'],chat['id'])
        self.assertIn('SEO',rows[0]['title'])
        messages=self.call('/api/assistant/messages?id='+chat['id'])['messages']
        self.assertEqual(messages[0]['text'],'Remember my long SEO description preference.')

    def test_chat_page_is_in_both_workspaces(self):
        for path in ('/', '/publisher.html'):
            with urlopen(self.base + path) as r:
                page = r.read().decode()
            self.assertIn('assistant.js', page)
            self.assertIn('assistant.css', page)
            self.assertNotIn('__APP_TOKEN__', page)

    def test_paired_workflow_status_is_read_only_and_owner_protected(self):
        with self.assertRaises(HTTPError):self.call('/api/distribution',auth=False)
        status=self.call('/api/distribution')
        self.assertEqual(status['workflow']['daily_time'],'19:00')
        self.assertEqual(status['batches'],[])
        with urlopen(self.base+'/workflow.html') as r:page=r.read().decode()
        self.assertNotIn('__APP_TOKEN__',page);self.assertIn('assistant.js',page)
        self.assertFalse(self.state.publisher.store.list());self.assertFalse(self.state.local_browser.data['jobs'])

    def test_private_chat_upload_endpoint_requires_the_owner_token(self):
        s = self.call('/api/assistant/session', {})
        payload = {'session': s['id'], 'review': 'reviewed-batch', 'made_for_kids': False, 'synthetic_media': False}
        with patch('hinglish_app.assistant_publish.start', return_value=s) as publish:
            with self.assertRaises(HTTPError) as caught:
                self.call('/api/assistant/publish', payload, auth=False)
            self.assertEqual(caught.exception.code, 403)
            publish.assert_not_called()
            self.assertEqual(self.call('/api/assistant/publish', payload)['id'], s['id'])
            publish.assert_called_once_with(self.state.assistant, payload)

    def test_attachment_uses_only_its_session(self):
        s = self.call('/api/assistant/session', {})
        data = b'video content'
        with urlopen(Request(self.base + '/api/assistant/upload?session=' + s['id'] + '&name=take.mp4',
                             data=data, headers={'X-Hinglish-Token': self.state.token})) as r:
            a = json.load(r)
        self.assertEqual(Path(a['path']).read_bytes(), data)
        self.assertEqual(self.call('/api/assistant/session?id=' + s['id'])['attachments'][0]['id'], a['id'])
        with self.assertRaises(HTTPError):
            self.call('/api/assistant/message', {'session': '../escape', 'message': 'Clean'})

    def test_dispatch_route_does_not_need_form_submission(self):
        s = self.call('/api/assistant/session', {})
        with patch.object(self.state.assistant, 'send', return_value=s) as send:
            self.call('/api/assistant/message', {'session': s['id'], 'message': 'Make 10 Shorts', 'attachments': ['one']})
        send.assert_called_once_with(s['id'], 'Make 10 Shorts', ['one'], None)

    def test_profile_routes_are_protected_and_publishing_settings_are_isolated(self):
        with self.assertRaises(HTTPError) as caught:
            self.call('/api/niche',auth=False)
        self.assertEqual(caught.exception.code,403)
        data=self.call('/api/niche',{'profile':'gaming','changes':{'feedback':'Keep the setup and payoff.'}})
        self.assertEqual(data['profiles']['gaming']['feedback'],'Keep the setup and payoff.')
        self.call('/api/publisher/settings',{'profile':'gaming','daily_time':'20:15'})
        self.assertEqual(self.call('/api/publisher?profile=gaming')['settings']['daily_time'],'20:15')
        self.assertEqual(self.call('/api/publisher?profile=general')['settings']['daily_time'],'19:00')
        with self.assertRaises(HTTPError): self.call('/api/niche',{'profile':'unknown'})

    def test_explicit_chat_profile_is_forwarded(self):
        s=self.call('/api/assistant/session',{})
        with patch.object(self.state.assistant,'send',return_value=s) as send:
            self.call('/api/assistant/message',{'session':s['id'],'message':'Make highlights','profile':'gaming'})
        send.assert_called_once_with(s['id'],'Make highlights',[],None,profile='gaming')

    def test_video_preview_range_and_access_boundaries(self):
        s = self.state.assistant.create()
        p = self.root / 'output' / 'chat.mp4'
        p.parent.mkdir()
        p.write_bytes(b'0123456789')
        self.state.assistant._message(s['id'], 'assistant', 'Ready', videos=[str(p)])
        url = self.base + f'/api/assistant/media?session={s["id"]}&index=0&token={self.state.token}'
        with urlopen(Request(url, headers={'Range': 'bytes=2-5'})) as r:
            self.assertEqual(r.status, 206)
            self.assertEqual(r.headers['Content-Range'], 'bytes 2-5/10')
            self.assertEqual(r.read(), b'2345')
        with self.assertRaises(HTTPError):
            urlopen(self.base + f'/api/assistant/media?session={s["id"]}&index=0')
        outside = self.root / 'private.mp4'
        outside.write_bytes(b'private')
        self.state.assistant._message(s['id'], 'assistant', 'Bad path', videos=[str(outside)])
        with self.assertRaises(HTTPError):
            urlopen(url.replace('index=0', 'index=1'))


if __name__ == '__main__': unittest.main()
