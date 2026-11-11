"""Explicit owner-only read-only encrypted link check; never starts a model or edit."""
import argparse
import json
from pathlib import Path
import time
import uuid

from hinglish_app.phone_native import Cipher, RelayClient, config_path, decode, read_private


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    config=read_private(config_path(args.root))
    client=RelayClient(config['url'],config['phone_token'])
    cipher=Cipher(decode(config['key'],32))
    identity=str(uuid.uuid4())
    client.request('POST','/v1/push',cipher.encrypt({'id':identity,'method':'state','params':{}}))
    deadline=time.monotonic()+65
    while time.monotonic()<deadline:
        for envelope in client.request('GET','/v1/pull?wait=20').get('messages',[]):
            result=cipher.decrypt(envelope)
            if result['id']!=identity:continue
            if not result.get('ok'):raise RuntimeError(result.get('error',{}).get('message','Encrypted link failed'))
            state=result['result']
            receipt={'checked_at':time.time(),'relay':config['url'],'encrypted_roundtrip':True,'laptop_editor_connected':state.get('connected') is True,'model_or_edit_started':False,'physical_android_test':False}
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(receipt,indent=2),'utf-8')
            print(json.dumps(receipt));return
    raise SystemExit('The laptop did not answer. Keep the receiver running and check its saved status.')


if __name__=='__main__':main()
