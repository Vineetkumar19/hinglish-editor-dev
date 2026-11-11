"""Generate the operator signing key into a private file; output only public key."""
import argparse
import os
import subprocess
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hinglish_license.crypto import encode,private_bytes,public_bytes


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    key=Ed25519PrivateKey.generate()
    with args.output.open('x',encoding='utf-8') as handle:handle.write(encode(private_bytes(key)))
    if os.name!='nt':args.output.chmod(0o600)
    else:
        identity=os.environ['USERDOMAIN']+'\\'+os.environ['USERNAME']
        subprocess.run(['icacls',str(args.output),'/inheritance:r','/grant:r',identity+':F'],check=True,stdout=subprocess.DEVNULL)
    print('Private key saved. Put its value only in the hosting secret HINGLISH_SAAS_LICENSE_PRIVATE_KEY.')
    print('Release public key: '+encode(public_bytes(key.public_key())))


if __name__=='__main__':main()
