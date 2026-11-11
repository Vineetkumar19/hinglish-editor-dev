"""Create a private authenticator setup file; never print its secret or QR URI."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import quote


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
    uri='otpauth://totp/'+quote('Storylens Support:vineetkd418@gmail.com')+'?secret='+secret+'&issuer=Hinglish%20Editor&algorithm=SHA1&digits=6&period=30'
    with args.output.open('x',encoding='utf-8') as handle:json.dump({'environment_key':'HINGLISH_SAAS_SUPPORT_TOTP_SECRET','secret':secret,'authenticator_uri':uri},handle,indent=2)
    if os.name=='nt':
        identity=os.environ.get('USERDOMAIN','')+'\\'+os.environ['USERNAME']
        subprocess.run(['icacls',str(args.output),'/inheritance:r','/grant:r',identity+':F'],check=True,stdout=subprocess.DEVNULL)
    else:args.output.chmod(0o600)
    print('Private authenticator setup file saved. Add it to your authenticator app and hosting secret settings; do not publish it.')


if __name__=='__main__':main()
