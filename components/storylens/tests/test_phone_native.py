import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from hinglish_app.phone_native import Cipher, NativeCompanion, RelayError, validate_relay
from hinglish_app.phone_remote import PhoneService


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


class NativePhoneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.engine=Mock()
        self.engine.health.return_value=True
        self.chat={'id':'0123456789abcdef','status':'idle','stage':'','messages':[],'attachments':[],'last_paths':[]}
        self.engine.create.return_value=self.chat
        self.engine.snapshot.side_effect=lambda identity:dict(self.chat)
        self.service=PhoneService(self.root,'http://127.0.0.1:8797',engine=self.engine)
        self.native=NativeCompanion(self.root,self.service)
        self.key=bytes(range(32))

    def test_aes_gcm_roundtrip_and_integrity(self):
        cipher=Cipher(self.key)
        plain={'id':'abcdef12-1234-5678-9876-112233445566','method':'state','params':{}}
        envelope=cipher.encrypt(plain)
        self.assertEqual(cipher.decrypt(envelope),plain)
        self.assertNotIn('method',json.dumps(envelope))
        corrupt={**envelope,'id':'otherid1-1234-5678-9876-112233445566'}
        with self.assertRaises(RelayError):cipher.decrypt(corrupt)
        with self.assertRaises(RelayError):Cipher(bytes(32)).decrypt(envelope)

    def test_encrypted_frames_respect_the_actual_relay_ciphertext_cap(self):
        cipher=Cipher(self.key)
        with self.assertRaises(RelayError):
            cipher.encrypt({'id':'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee','result':'x'*185000})

    def test_standard_cross_language_vector(self):
        cipher=Cipher(self.key)
        value={'id':'vector01-1234-5678-9876-112233445566','method':'state','params':{}}
        envelope=cipher.encrypt(value,nonce=bytes(range(12)))
        self.assertEqual(cipher.decrypt(envelope),value)
        self.assertEqual(envelope['nonce'],'AAECAwQFBgcICQoL')
        self.assertEqual(envelope['data'],'PCC_f-ff4G3oIuPkw9lJQLLktADdTmlLAErcvSpfLYMwIpzPnPUmrUGSSc-kpUVdmjEP6XjsgalL9l58Os_XnpFOpxeg8xwaYSkMluIqEGlAkA2wvmhABYRq')

    def test_private_and_plain_http_relays_rejected(self):
        self.assertEqual(validate_relay('https://storylens-personal-link.example.workers.dev'),'https://storylens-personal-link.example.workers.dev')
        for value in ['http://example.workers.dev','https://localhost','https://example.com','https://user:pass@example.workers.dev','https://example.workers.dev/path','https://example.workers.dev?token=x']:
            with self.subTest(value=value),self.assertRaises(RelayError):validate_relay(value)

    def test_native_chats_use_existing_assistant_and_keep_same_ownership_after_restart(self):
        value=self.native.dispatch('create_chat',{'request_id':'native-create-001'})
        self.assertEqual(value['id'],self.chat['id'])
        self.engine.create.assert_called_once()
        again=NativeCompanion(self.root,self.service)
        self.assertEqual(again.dispatch('chat',{'chat':self.chat['id']})['id'],self.chat['id'])
        self.assertTrue(again.dispatch('state',{})['connected'])

    def test_no_generic_paths_or_arbitrary_calls(self):
        for method,params in [('shell',{'command':'whoami'}),('file_info',{'file':'../secret'}),('chat',{'chat':'a'*16}),('state',{'url':'http://localhost:8765/api/bridge'})]:
            with self.subTest(method=method),self.assertRaises(Exception):self.native.dispatch(method,params)

    def test_upload_chunks_and_finish_reuse_existing_attachment_contract(self):
        self.native.dispatch('create_chat',{'request_id':'native-create-002'})
        self.engine.upload.side_effect=lambda chat,name,stream,length: {'id':'attach01','name':name,'size':length,'kind':'file','bytes':stream.read()}
        begin=self.native.dispatch('upload_begin',{'chat':self.chat['id'],'request_id':'native-upload-001','name':'notes.txt','size':6})
        chunk={'upload':begin['upload'],'index':0,'data':b64(b'hello!')}
        self.assertEqual(self.native.dispatch('upload_chunk',chunk)['next_index'],1)
        self.assertEqual(self.native.dispatch('upload_chunk',chunk)['next_index'],1)
        with self.assertRaises(Exception):self.native.dispatch('upload_chunk',{**chunk,'data':b64(b'other!')})
        saved=self.native.dispatch('upload_finish',{'upload':begin['upload']})
        self.assertEqual(saved['id'],'attach01')
        self.assertEqual(self.native.dispatch('upload_finish',{'upload':begin['upload']})['id'],'attach01')
        self.engine.upload.assert_called_once()

    def test_native_transport_launchers_do_not_depend_on_vpn_or_open_ports(self):
        project=Path(__file__).resolve().parents[1]
        start=(project/'tools'/'start_storylens_native_phone.ps1').read_text('utf-8')
        stop=(project/'tools'/'stop_storylens_native_phone.ps1').read_text('utf-8')
        self.assertIn('hinglish_app.phone_native',start)
        self.assertNotIn('tailscale',start.lower())
        self.assertNotIn('netsh',start.lower())
        self.assertIn('Stop-Process -Id',stop)
        self.assertNotIn('Stop-Process -Name',stop)

    def test_only_one_laptop_receiver_owns_a_connection(self):
        from hinglish_app.phone_native import receiver_lease
        with receiver_lease(self.root):
            with self.assertRaises(RelayError):
                with receiver_lease(self.root):pass
        with receiver_lease(self.root):pass

    def test_pairing_keys_are_protected_by_windows_user_storage(self):
        from hinglish_app.phone_native import configure, read_private, config_path
        config=configure(self.root,'https://storylens-personal-link.example.workers.dev')
        raw=config_path(self.root).read_bytes()
        self.assertNotIn(config['key'].encode(),raw)
        self.assertNotIn(config['phone_token'].encode(),raw)
        self.assertEqual(read_private(config_path(self.root)),config)
        self.assertEqual(configure(self.root,config['url']),config)
        with self.assertRaises(RelayError):configure(self.root,'https://other.example.workers.dev')

    def test_result_transfer_only_exposes_saved_chat_files(self):
        self.native.dispatch('create_chat',{'request_id':'native-create-003'})
        folder=self.root/'output';folder.mkdir()
        media=folder/'review.mp3';media.write_bytes(b'1234567890')
        self.chat['messages']=[{'id':'result1','role':'assistant','text':'Ready','result':{'audio':str(media)}}]
        snapshot=self.native.dispatch('chat',{'chat':self.chat['id']})
        identity=snapshot['files'][0]['id']
        info=self.native.dispatch('file_info',{'file':identity})
        self.assertNotIn('path',info)
        result=self.native.dispatch('file_chunk',{'file':identity,'offset':2,'length':4})
        self.assertEqual(result['data'],b64(b'3456'))
        self.assertEqual(result['next_offset'],6)
        self.assertFalse(result['eof'])
        with self.assertRaises(Exception):self.native.dispatch('file_chunk',{'file':identity,'offset':True,'length':4})


if __name__=='__main__':unittest.main()
