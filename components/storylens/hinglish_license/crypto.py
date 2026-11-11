import base64
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption


def encode(value): return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decode(value, size=None):
    if not isinstance(value,str) or len(value)>16000: raise ValueError('Invalid encoded key or signature.')
    raw=base64.b64decode(value+'='*((-len(value))%4),altchars=b'-_',validate=True)
    if size is not None and len(raw)!=size: raise ValueError('Invalid key or signature length.')
    if encode(raw)!=value:raise ValueError('Use canonical unpadded base64url encoding.')
    return raw


def private_bytes(key): return key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())
def public_bytes(key): return key.public_bytes(Encoding.Raw,PublicFormat.Raw)


def sign_lease(key,claims):
    payload=encode(json.dumps(claims,sort_keys=True,separators=(',',':')).encode())
    return payload+'.'+encode(key.sign(payload.encode()))


def verify_lease(public_key,lease):
    if not isinstance(lease,str) or len(lease)>12000: raise ValueError('Invalid license.')
    payload,signature=lease.split('.')
    Ed25519PublicKey.from_public_bytes(decode(public_key,32)).verify(decode(signature,64),payload.encode())
    claims=json.loads(decode(payload))
    if not isinstance(claims,dict): raise ValueError('Invalid license claims.')
    return claims
