import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from hinglish_app.phone_remote import EngineUnavailable, PhoneError, PhoneService, create_server


class FakeEngine:
    def __init__(self, root):
        self.root = root
        self.chats = {}
        self.calls = []
        self.fail_send = False

    def health(self):
        return True

    def create(self):
        identity = f'{len(self.chats) + 1:016x}'
        self.chats[identity] = dict(id=identity, title='', status='idle', stage='', messages=[], attachments=[], last_paths=[], step_results=[])
        return self.snapshot(identity)

    def snapshot(self, identity):
        return json.loads(json.dumps(self.chats[identity]))

    def send(self, identity, payload):
        self.calls.append((identity, payload))
        if self.fail_send:
            raise EngineUnavailable('The result is uncertain.')
        chat = self.chats[identity]
        chat['messages'].append(dict(id='message1', role='user', text=payload['message'], created=1))
        chat.update(status='planning', stage='Understanding your request')
        return self.snapshot(identity)

    def stop(self, identity):
        self.chats[identity]['stage'] = 'Stopping after the current step'
        return self.snapshot(identity)

    def upload(self, identity, name, stream, length):
        stream.read(length)
        row = dict(id='attached1', name=name, size=length, kind='file', path=str(self.root/'input'/name))
        self.chats[identity]['attachments'].append(row)
        return row


class PhoneRemoteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root/'output').mkdir()
        self.engine = FakeEngine(self.root)
        self.service = PhoneService(self.root, origin='http://127.0.0.1:8796', engine=self.engine)
        self.code = self.service.issue_pairing()
        self.token, self.csrf = self.service.pair(self.code)

    def chat(self):
        return self.service.create_chat(self.token, 'create-chat-0001')

    def test_pairing_is_single_use_hashed_and_revocable(self):
        with self.assertRaises(PhoneError):
            self.service.pair(self.code)
        db_bytes = (self.root/'cache'/'phone-remote'/'phone.sqlite3').read_bytes()
        self.assertNotIn(self.code.encode(), db_bytes)
        self.assertNotIn(self.token.encode(), db_bytes)
        self.assertTrue(self.service.state(self.token)['paired'])
        self.service.logout(self.token)
        with self.assertRaises(PhoneError):
            self.service.state(self.token)

    def test_chat_creation_and_message_retries_are_idempotent(self):
        chat = self.chat()
        self.assertEqual(self.chat()['id'], chat['id'])
        payload = dict(request_id='send-message-0001', message='Explain the available editing tools', attachments=[])
        first = self.service.send(self.token, chat['id'], payload)
        second = self.service.send(self.token, chat['id'], payload)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.engine.calls), 1)
        with self.assertRaises(PhoneError):
            self.service.send(self.token, chat['id'], {**payload, 'message':'Different command'})

    def test_another_paired_phone_cannot_access_chat_or_artifacts(self):
        chat = self.chat()
        other, _ = self.service.pair(self.service.issue_pairing())
        with self.assertRaises(PhoneError):
            self.service.snapshot(other, chat['id'])
        with self.assertRaises(PhoneError):
            self.service.stop(other, chat['id'])
        self.assertEqual(self.service.state(other)['chats'], [])

    def test_uncertain_submission_never_replays_the_command(self):
        chat = self.chat()
        self.engine.fail_send = True
        payload = dict(request_id='uncertain-send-0001', message='Make one edit', attachments=[])
        with self.assertRaises(PhoneError):
            self.service.send(self.token, chat['id'], payload)
        with self.assertRaises(PhoneError):
            self.service.send(self.token, chat['id'], payload)
        self.assertEqual(len(self.engine.calls), 1)
        self.assertEqual(self.service.snapshot(self.token, chat['id'])['id'], chat['id'])

    def test_proven_pre_submission_disconnect_can_retry_the_same_request(self):
        chat=self.chat()
        original=self.engine.send
        calls=[]
        def offline_once(identity,payload):
            calls.append(identity)
            if len(calls)==1:
                raise EngineUnavailable('Editor is offline',uncertain=False)
            return original(identity,payload)
        self.engine.send=offline_once
        payload={'request_id':'offline-message-0001','message':'Explain the tools','attachments':[]}
        with self.assertRaises(PhoneError):self.service.send(self.token,chat['id'],payload)
        result=self.service.send(self.token,chat['id'],payload)
        self.assertEqual(result['status'],'planning')
        self.assertEqual(len(self.engine.calls),1)

    def test_uploaded_attachments_are_owned_and_do_not_reveal_paths(self):
        chat = self.chat()
        item = self.service.upload(self.token, chat['id'], 'voice.mp3', io.BytesIO(b'audio'), 5, 'upload-request-0001')
        self.assertEqual(item['name'], 'voice.mp3')
        self.assertNotIn('path', item)
        with self.assertRaises(PhoneError):
            self.service.send(self.token, chat['id'], dict(request_id='wrong-attach-0001', message='Use attachment', attachments=['not-uploaded']))
        with self.assertRaises(PhoneError):
            self.service.upload(self.token, chat['id'], '..\\passwords.txt', io.BytesIO(b'x'), 1, 'upload-request-0002')

    def test_output_discovery_is_chat_bound_and_rejects_active_or_outside_files(self):
        chat = self.chat()
        video = self.root/'output'/'finished.mp4'
        video.write_bytes(b'video-data')
        sound = self.root/'output'/'finished.mp3'
        sound.write_bytes(b'audio-data')
        private = self.root/'settings.txt'
        private.write_text('private')
        html = self.root/'output'/'report.html'
        html.write_text('<script>alert(1)</script>')
        saved = self.engine.chats[chat['id']]
        saved['messages'].append(dict(id='done', role='assistant', text='Done', videos=[str(video)], result={'audio':str(sound), 'report':str(html), 'file':str(private)}))
        snapshot = self.service.snapshot(self.token, chat['id'])
        self.assertEqual({f['name'] for f in snapshot['files']}, {'finished.mp4','finished.mp3'})
        self.assertNotIn(str(self.root), json.dumps(snapshot))
        item = snapshot['files'][0]
        record = self.service.file(self.token, item['id'])
        self.assertEqual(record['path'].parent, (self.root/'output').resolve())
        record['path'].write_bytes(b'changed')
        with self.assertRaises(PhoneError):
            self.service.file(self.token, item['id'])

    def test_upload_identity_binds_actual_bytes_and_state_survives_restart(self):
        chat = self.chat()
        self.service.upload(self.token,chat['id'],'notes.txt',io.BytesIO(b'first'),5,'stable-upload-0001')
        with self.assertRaises(PhoneError):
            self.service.upload(self.token,chat['id'],'notes.txt',io.BytesIO(b'other'),5,'stable-upload-0001')
        recovered = PhoneService(self.root,origin=self.service.origin,engine=self.engine)
        self.assertEqual(recovered.snapshot(self.token,chat['id'])['id'],chat['id'])
        self.assertEqual(recovered.state(self.token)['chats'][0]['id'],chat['id'])

    def test_phone_assets_and_errors_are_in_shared_distribution(self):
        import tomllib
        project = Path(__file__).resolve().parents[1]
        manifest = tomllib.loads((project/'pyproject.toml').read_text('utf-8'))
        self.assertIn('phone_static/*',manifest['tool']['setuptools']['package-data']['hinglish_app'])
        codes = {entry['code'] for entry in json.loads((project/'hinglish_app'/'error_catalog.json').read_text('utf-8'))}
        self.assertTrue({'phone_pair_required','phone_engine_unavailable','phone_uncertain_submission'} <= codes)

    def test_network_disconnect_does_not_print_a_traceback(self):
        from contextlib import redirect_stderr
        server=create_server(self.service,port=0)
        self.addCleanup(server.server_close)
        output=io.StringIO()
        with redirect_stderr(output):
            try:
                raise ConnectionResetError('Phone disconnected')
            except ConnectionResetError:
                server.handle_error(None,('127.0.0.1',12345))
        self.assertEqual(output.getvalue(),'')

    def test_http_requires_allowed_host_origin_cookie_and_csrf(self):
        import http.client
        import threading
        server = create_server(self.service, port=0)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        host = f'127.0.0.1:{server.server_port}'
        def request(method, route, payload=None, **headers):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            data = json.dumps(payload).encode() if payload is not None else None
            conn.request(method, route, data, {'Host':host, 'Content-Type':'application/json', **headers})
            result = conn.getresponse()
            body = result.read()
            status = result.status
            conn.close()
            return status, body
        self.assertEqual(request('GET','/phone/state')[0],401)
        self.assertEqual(request('GET','/phone/phone.js')[0],200)
        self.assertEqual(request('GET','/phone/phone.css')[0],200)
        cookie = f'storylens_phone={self.token}'
        self.assertEqual(request('POST','/phone/chats', {'request_id':'http-create-0001'}, Cookie=cookie)[0],403)
        self.assertEqual(request('POST','/phone/chats', {'request_id':'http-create-0001'}, Cookie=cookie, **{'X-Phone-CSRF':self.csrf,'Origin':'https://untrusted.example'})[0],403)
        self.assertEqual(request('POST','/phone/chats', {'request_id':'http-create-0001'}, Cookie=cookie, **{'X-Phone-CSRF':self.csrf})[0],201)
        self.assertEqual(request('GET','/api/assistant/history',Cookie=cookie)[0],404)
        self.assertEqual(request('GET','/',Host='attacker.example')[0],403)


if __name__ == '__main__':
    unittest.main()
