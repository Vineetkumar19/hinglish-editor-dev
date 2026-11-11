import json
import os
import platform
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse
import requests
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .crypto import decode, encode, private_bytes, public_bytes, verify_lease
from .device import DeviceVault


class LicenseError(ValueError): pass


class LicenseClient:
    def __init__(self,folder,origin,public_key,edition,*,allow_loopback=False):
        parsed=urlparse(origin)
        if edition not in ('desktop','plugins') or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise LicenseError('The release license configuration is invalid.')
        if parsed.scheme!='https' and not (allow_loopback and parsed.scheme=='http' and parsed.hostname=='127.0.0.1'):
            raise LicenseError('Activation requires the release HTTPS server.')
        if allow_loopback and (getattr(sys,'frozen',False) or parsed.scheme!='http' or parsed.hostname!='127.0.0.1'):
            raise LicenseError('Test-mode storage is restricted to unfrozen loopback tests.')
        decode(public_key,32)
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.origin=origin;self.public_key=public_key;self.edition=edition;self.lock=threading.RLock()
        self.file=self.folder/(edition+'.json');self.pending=None;self.checked=0
        self.vault=DeviceVault(self.folder,test_mode=allow_loopback)
        self.hardware_hash=self.vault.hardware_hash
        key_file=self.folder/'installation.key'
        if not key_file.exists():
            key=Ed25519PrivateKey.generate()
            try:
                self.vault.write('installation.key',private_bytes(key),exclusive=True)
            except FileExistsError:pass
        self.key=Ed25519PrivateKey.from_private_bytes(self.vault.read('installation.key'))
        self.installation_key=encode(public_bytes(self.key.public_key()))

    def read(self):
        try:
            value=json.loads(self.vault.read(self.file.name))
            return value if isinstance(value,dict) else {}
        except (OSError,ValueError):return {}

    def save(self,data):
        self.vault.write(self.file.name,json.dumps(data).encode())

    def request(self,path,data):
        response=requests.post(self.origin+path,json=data,timeout=(4,8),allow_redirects=False)
        if not response.ok:
            if response.status_code in (401,402,403): self.file.unlink(missing_ok=True)
            try:detail=response.json().get('detail','Activation could not complete.')
            except ValueError:detail='Activation could not complete.'
            raise LicenseError(detail)
        return response.json()

    def claims(self,data,host):
        try:
            c=verify_lease(self.public_key,data.get('lease',''));now=time.time()
            if (c.get('iss')!=self.origin or c.get('aud')!='hinglish-editor' or c.get('edition')!=self.edition
                    or c.get('public_key')!=self.installation_key or c.get('device_id')!=data.get('device_id')
                    or c.get('hardware_hash')!=self.hardware_hash or c.get('license_version')!=2
                    or not isinstance(c.get('exp'),(int,float)) or not isinstance(c.get('iat'),(int,float))
                    or not c['iat']-60<=now<c['exp'] or c['exp']-c['iat']>300
                    or host not in c.get('hosts',[]) or now+300<data.get('last_seen',0)):
                raise ValueError('Invalid license claims.')
            return c
        except Exception as error:raise LicenseError('Sign in to activate this edition, or renew your subscription.') from error

    def ensure(self,host=None):
        host=host or ('standalone' if self.edition=='desktop' else 'premiere')
        with self.lock:
            data=self.read()
            now=time.time()
            if not data.get('device_id') or not data.get('credential'):
                raise LicenseError('Sign in to activate this computer.')
            if data.get('device_id') and data.get('credential'):
                nonce=uuid.uuid4().hex;timestamp=int(now);device=data['device_id']
                signature=encode(self.key.sign(f'refresh:{device}:{nonce}:{timestamp}:{self.hardware_hash}'.encode()))
                try:
                    fresh=self.request('/api/licenses/refresh',{'device_id':device,'credential':data['credential'],
                        'nonce':nonce,'timestamp':timestamp,'signature':signature,'hardware_hash':self.hardware_hash})
                    data.update(fresh)
                except requests.RequestException as error:
                    raise LicenseError('Connect this computer to the internet to verify its subscription. No offline editing access is enabled.') from error
                self.checked=now
            claims=self.claims(data,host);data['last_seen']=now;self.save(data);return claims

    def status(self):
        try:
            data=self.read();c=self.claims(data,'standalone' if self.edition=='desktop' else 'premiere')
            return {'active':True,'edition':self.edition,'expires':c['exp'],'pending':False}
        except LicenseError:
            return {'active':False,'edition':self.edition,'pending':bool(self.pending and self.pending['deadline']>time.time()),
                    'error':self.pending.get('error','') if self.pending else ''}

    def usage_preference(self,enabled=None):
        with self.lock:
            if enabled is not None:self.vault.write('usage-privacy.json',json.dumps({'enabled':bool(enabled)}).encode())
            try:return bool(json.loads(self.vault.read('usage-privacy.json')).get('enabled',False))
            except (ValueError,OSError):return False

    def report_usage(self,tool,outcome,duration):
        # Optional aggregate operational metadata only. Never send input paths,
        # scripts, transcripts, captions, source footage or exception details.
        if not self.usage_preference():return
        data=self.read()
        if not data.get('credential'):return
        event={'id':uuid.uuid4().hex,'device_id':data['device_id'],'timestamp':int(time.time()),
            'tool':tool,'outcome':outcome,'duration':round(min(86400,max(0,duration)),3),'app_version':'1.0'}
        signature=encode(self.key.sign(('usage:'+json.dumps(event,sort_keys=True,separators=(',',':'))).encode()))
        try:self.request('/api/usage',{**event,'credential':data['credential'],'signature':signature})
        except (requests.RequestException,LicenseError,ValueError):pass

    def begin(self):
        with self.lock:
            if self.pending and self.pending['deadline']>time.time():return self.public_pending()
            value=self.request('/api/licenses/device-code',{'edition':self.edition,'public_key':self.installation_key,
                       'name':platform.node()[:80] or 'My computer','hardware_hash':self.hardware_hash})
            if value.get('verification_uri')!=self.origin+'/account?view=activate':raise LicenseError('Unexpected activation address.')
            self.pending={**value,'deadline':time.time()+min(int(value['expires_in']),600),'error':''}
            threading.Thread(target=self._poll,name='license-activation',daemon=True).start()
            return self.public_pending()

    def public_pending(self):
        return {k:self.pending[k] for k in ('user_code','verification_uri','expires_in','edition','error')} if self.pending else {}

    def _poll(self):
        pending=self.pending
        while time.time()<pending['deadline']:
            time.sleep(5)
            try:
                value=self.request('/api/licenses/poll',{'device_code':pending['device_code'],
                    'signature':encode(self.key.sign(('activate:'+pending['device_code']).encode()))})
                if value.get('status')=='approved':
                    self.claims(value,'standalone' if self.edition=='desktop' else 'premiere')
                    with self.lock:self.save(value);self.pending=None;self.checked=time.time()
                    return
            except requests.RequestException:continue
            except (LicenseError,ValueError,KeyError) as error:
                pending['error']=str(error);break
        pending['error']=pending['error'] or 'Activation code expired. Try again.'
        pending['deadline']=0
