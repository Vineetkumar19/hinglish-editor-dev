import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_app.phone_remote import EngineClient, PhoneError, PhoneService, create_server
from hinglish_app.server import serve


class PhoneEngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.server, self.state = serve(self.root, 0, publish_bridge=False, restore_pending_jobs=False)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        bridge = self.root/'cache'/'app'/'bridge.json'
        bridge.parent.mkdir(parents=True, exist_ok=True)
        bridge.write_text(json.dumps({'token':self.state.token}), encoding='utf-8')
        engine = EngineClient(self.root)
        engine.port = self.server.server_port
        self.phone = PhoneService(self.root, origin='http://127.0.0.1:8796', engine=engine)
        self.token, self.csrf = self.phone.pair(self.phone.issue_pairing())

    def test_real_assistant_http_receives_exact_phone_message_and_attachments(self):
        chat = self.phone.create_chat(self.token,'engine-create-0001')
        item = self.phone.upload(self.token,chat['id'],'instructions.txt',io.BytesIO(b'Keep these exact words'),22,'engine-upload-0001')
        with patch.object(self.state.assistant,'_respond') as respond:
            sent = self.phone.send(self.token,chat['id'],{'request_id':'engine-message-0001','message':'Read my instructions, do not start editing','attachments':[item['id']],'profile':'general'})
            for _ in range(100):
                if respond.called:
                    break
                threading.Event().wait(.01)
        self.assertTrue(respond.called)
        self.assertEqual(sent['status'],'planning')
        saved=self.state.assistant.snapshot(chat['id'])
        self.assertEqual(saved['messages'][-1]['text'],'Read my instructions, do not start editing')
        self.assertEqual(saved['messages'][-1]['attachments'][0]['id'],item['id'])
        self.assertNotIn('path',sent['attachments'][0])
        self.assertFalse(self.state.jobs)

    def test_real_http_result_range_and_download_are_session_protected(self):
        import http.client
        chat=self.phone.create_chat(self.token,'engine-create-0002')
        output=self.root/'output'/'phone-check.mp4'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes(b'0123456789')
        self.state.assistant._message(chat['id'],'assistant','Saved result',videos=[str(output)])
        item=self.phone.snapshot(self.token,chat['id'])['files'][0]
        server=create_server(self.phone,port=0)
        self.addCleanup(server.server_close)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.shutdown)
        def read(cookie=None,range_value=None,download=False):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            headers={}
            if cookie:headers['Cookie']='storylens_phone='+cookie
            if range_value:headers['Range']=range_value
            conn.request('GET',item['url']+('?download=1' if download else ''),headers=headers)
            response=conn.getresponse();body=response.read();result=(response.status,dict(response.headers),body);conn.close();return result
        self.assertEqual(read()[0],401)
        status,headers,body=read(self.token,'bytes=2-5')
        self.assertEqual((status,body),(206,b'2345'))
        self.assertEqual(headers['Content-Range'],'bytes 2-5/10')
        self.assertEqual(read(self.token,'bytes=-3')[2],b'789')
        self.assertEqual(read(self.token,'bytes=99-')[0],416)
        self.assertIn('attachment',read(self.token,download=True)[1]['Content-Disposition'])
        other,_=self.phone.pair(self.phone.issue_pairing())
        self.assertEqual(read(other)[0],404)
        self.phone.logout(self.token)
        self.assertEqual(read(self.token)[0],401)


if __name__=='__main__':
    unittest.main()
