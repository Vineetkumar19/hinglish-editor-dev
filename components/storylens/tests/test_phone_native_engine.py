import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_app.phone_native import Cipher, NativeCompanion
from hinglish_app.phone_remote import EngineClient, PhoneService
from hinglish_app.server import serve


class NativeEngineContract(unittest.TestCase):
    def test_encrypted_native_command_reaches_real_assistant_route_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            server,state=serve(root,0,publish_bridge=False,restore_pending_jobs=False)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                bridge=root/'cache'/'app'/'bridge.json';bridge.parent.mkdir(parents=True,exist_ok=True)
                bridge.write_text(json.dumps({'token':state.token}),'utf-8')
                engine=EngineClient(root);engine.port=server.server_port
                native=NativeCompanion(root,PhoneService(root,'http://127.0.0.1:8797',engine))
                cipher=Cipher(bytes(range(32)))
                chat=native.dispatch('create_chat',{'request_id':'native-engine-create-001'})
                request={'id':'native-engine-frame-001','method':'send','params':{'chat':chat['id'],'request_id':'native-engine-send-001','message':'Explain the available tools. Do not edit or publish.','attachments':[],'profile':'general'}}
                encrypted=cipher.encrypt(request)
                with patch.object(state.assistant,'_respond') as model:
                    for _ in range(2):
                        decoded=cipher.decrypt(encrypted)
                        reply=native.dispatch(decoded['method'],decoded['params'])
                        self.assertEqual(reply['id'],chat['id'])
                    for _ in range(50):
                        if model.called:break
                        threading.Event().wait(.01)
                self.assertEqual(model.call_count,1)
                saved=state.assistant.snapshot(chat['id'])
                self.assertEqual(len([m for m in saved['messages'] if m['role']=='user']),1)
                self.assertEqual(saved['messages'][0]['text'],request['params']['message'])
                self.assertFalse(state.jobs)
            finally:
                server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
