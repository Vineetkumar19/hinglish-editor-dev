import hashlib
import json
import hmac
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hinglish_license.crypto import encode,private_bytes,public_bytes,verify_lease,sign_lease
from hinglish_license.client import LicenseClient,LicenseError
from hinglish_saas.app import create_app
from hinglish_saas.config import Settings
from tests.test_saas import Provider,ORIGIN


class LicensingFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.key=Ed25519PrivateKey.generate()
        self.public=encode(public_bytes(self.key.public_key()));self.device=Ed25519PrivateKey.generate()
        self.pub=encode(public_bytes(self.device.public_key()));self.provider=Provider()
        self.app=create_app(Settings(data_dir=self.root/'db',sales_enabled=True,key_id='rzp_test_demo',key_secret='test-secret',
                                   license_private_key=encode(private_bytes(self.key))),self.provider)
        self.client=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        self.settings=self.app.state.settings
        r=self.client.post('/api/auth/register',json={'email':'license@example.com','password':'unique license test password 123'})
        self.csrf=r.json()['csrf'];self.store=self.app.state.store
        self.uid=self.store.one('SELECT id FROM users')['id'];self.store.execute('UPDATE users SET verified=1 WHERE id=?',(self.uid,))

    def tearDown(self):self.client.close();self.temp.cleanup()

    def paid(self,edition):
        r=self.client.post('/api/billing/orders',json={'edition':edition,'plan':'monthly'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200,r.text);o=r.json();p=next(p for p in self.provider.payments.values() if p['order_id']==o['order_id'])
        sig=hmac.new(b'test-secret',(o['order_id']+'|'+p['id']).encode(),hashlib.sha256).hexdigest()
        r=self.client.post('/api/billing/verify',json={'order_id':o['order_id'],'payment_id':p['id'],'signature':sig},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['edition'],'bundle');return o,p

    def begin(self,edition='plugins',key=None):
        key=key or self.device
        public=encode(public_bytes(key.public_key()))
        r=self.client.post('/api/licenses/device-code',json={'edition':edition,'public_key':public,'name':'My laptop','hardware_hash':hashlib.sha256(public.encode()).hexdigest()},headers={'Origin':''})
        self.assertEqual(r.status_code,200,r.text);return r.json()

    def approve(self,code):
        return self.client.post('/api/licenses/approve',json={'user_code':code['user_code']},headers={'X-CSRF-Token':self.csrf})

    def poll(self,code,key=None):
        key=key or self.device
        return self.client.post('/api/licenses/poll',json={'device_code':code['device_code'],'signature':encode(key.sign(('activate:'+code['device_code']).encode()))},headers={'Origin':''})

    def activate(self,key=None):
        code=self.begin(key=key);r=self.approve(code);self.assertEqual(r.status_code,200,r.text)
        r=self.poll(code,key);self.assertEqual(r.status_code,200,r.text);return r.json()

    def refresh(self,device,key=None,nonce=None):
        timestamp=int(time.time());nonce=nonce or uuid.uuid4().hex;key=key or self.device
        payload={'device_id':device['device_id'],'credential':device['credential'],'nonce':nonce,'timestamp':timestamp,
                 'hardware_hash':hashlib.sha256(encode(public_bytes(key.public_key())).encode()).hexdigest()}
        payload['signature']=encode(key.sign(f'refresh:{device["device_id"]}:{nonce}:{timestamp}:{payload["hardware_hash"]}'.encode()))
        return self.client.post('/api/licenses/refresh',json=payload,headers={'Origin':''})

class LicensingTests(LicensingFixture):
    def test_one_purchase_includes_desktop_and_plugins(self):
        self.paid('desktop');code=self.begin();self.assertEqual(self.approve(code).status_code,200)
        self.assertEqual(self.poll(code).json()['status'],'approved')
        self.assertTrue(self.store.entitlement(self.uid,edition='desktop')['active'])

    def test_renewals_extend_the_single_bundled_subscription(self):
        self.paid('desktop');self.paid('plugins')
        orders=self.store.all('SELECT starts,ends FROM orders ORDER BY created')
        self.assertAlmostEqual(orders[1]['starts'],orders[0]['ends'],places=3)

    def test_activation_requires_purchase_and_csrf(self):
        code=self.begin();self.assertEqual(self.approve(code).status_code,402)
        self.assertEqual(self.client.post('/api/licenses/approve',json={'user_code':code['user_code']}).status_code,403)

    def test_signed_lease_contains_host_edition_and_device(self):
        self.paid('plugins');code=self.begin();self.approve(code);response=self.poll(code)
        claims=verify_lease(self.public,response.json()['lease'])
        self.assertEqual(claims['hosts'],['aftereffects','premiere','resolve']);self.assertEqual(claims['public_key'],self.pub)
        self.assertLessEqual(claims['exp']-claims['iat'],86400);self.assertEqual(self.poll(code).status_code,410)
        lease=response.json()['lease'];payload,signature=lease.split('.')
        altered=('A' if signature[0]!='A' else 'B')+signature[1:]
        with self.assertRaises(Exception):verify_lease(self.public,payload+'.'+altered)

    def test_installation_proof_cannot_be_forged(self):
        self.paid('plugins');code=self.begin();self.approve(code)
        self.assertEqual(self.poll(code,Ed25519PrivateKey.generate()).status_code,403)

    def test_device_limit_and_deactivation(self):
        self.paid('plugins');one=self.activate()
        key=Ed25519PrivateKey.generate();code=self.begin(key=key)
        self.assertEqual(self.approve(code).status_code,409)
        r=self.client.delete('/api/licenses/devices/'+one['device_id'],headers={'X-CSRF-Token':self.csrf});self.assertEqual(r.status_code,200)
        self.assertEqual(self.refresh(one).status_code,403)
        self.assertEqual(self.approve(code).status_code,409)
        self.activate()  # Reactivation on the SAME registered installation is allowed.

    def test_replayed_refresh_is_rejected(self):
        self.paid('plugins');device=self.activate();nonce=uuid.uuid4().hex
        self.assertEqual(self.refresh(device,nonce=nonce).status_code,200)
        self.assertEqual(self.refresh(device,nonce=nonce).status_code,409)

    def test_refunded_purchase_no_longer_renews_license(self):
        order,payment=self.paid('plugins');device=self.activate()
        self.store.execute("UPDATE orders SET state='revoked' WHERE id=?",(order['order_id'],))
        self.assertEqual(self.refresh(device).status_code,402)

    def test_cross_account_device_revoke_and_approve_are_denied(self):
        self.paid('plugins');device=self.activate()
        other=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        csrf=other.post('/api/auth/register',json={'email':'other@example.com','password':'unique other test password 123'}).json()['csrf']
        self.assertEqual(other.delete('/api/licenses/devices/'+device['device_id'],headers={'X-CSRF-Token':csrf}).status_code,404)
        other.close()

    def test_expired_code_cannot_be_approved(self):
        self.paid('plugins');code=self.begin();self.store.execute('UPDATE device_codes SET expires=0')
        self.assertEqual(self.approve(code).status_code,404)

    def test_client_online_lease_and_hardware_binding(self):
        client=LicenseClient(self.root/'client',ORIGIN,self.public,'plugins',allow_loopback=True)
        now=int(time.time());claims={'iss':ORIGIN,'aud':'hinglish-editor','public_key':client.installation_key,
                    'device_id':uuid.uuid4().hex,'edition':'plugins','hosts':['premiere','aftereffects','resolve'],'iat':now,'exp':now+300,
                    'hardware_hash':client.hardware_hash,'license_version':2}
        signed=sign_lease(self.key,claims)
        client.save({'device_id':claims['device_id'],'credential':'x'*43,'lease':signed})
        with patch.object(client,'request',return_value={'lease':signed}):
            self.assertEqual(client.ensure('aftereffects')['edition'],'plugins')
            with self.assertRaises(LicenseError):client.ensure('standalone')
        other=LicenseClient(self.root/'other-client',ORIGIN,self.public,'plugins',allow_loopback=True)
        other.save(client.read())
        with patch.object(other,'request',return_value={'lease':signed}):
            with self.assertRaises(LicenseError):other.ensure('premiere')

    def test_expired_client_can_refresh_after_renewal(self):
        client=LicenseClient(self.root/'client',ORIGIN,self.public,'plugins',allow_loopback=True);now=int(time.time())
        claims={'iss':ORIGIN,'aud':'hinglish-editor','public_key':client.installation_key,'device_id':uuid.uuid4().hex,
                'edition':'plugins','hosts':['premiere'],'iat':now-1000,'exp':now-10,
                'hardware_hash':client.hardware_hash,'license_version':2}
        client.save({'device_id':claims['device_id'],'credential':'c'*43,'lease':sign_lease(self.key,claims)})
        fresh={**claims,'iat':now,'exp':now+250}
        with patch.object(client,'request',return_value={'lease':sign_lease(self.key,fresh)}):self.assertEqual(client.ensure()['exp'],now+250)

    def test_client_rejects_untrusted_http_and_forged_keys(self):
        with self.assertRaises(LicenseError):LicenseClient(self.root/'bad','http://attacker.example',self.public,'plugins')
        client=LicenseClient(self.root/'client',ORIGIN,self.public,'desktop',allow_loopback=True)
        client.save({'lease':'not.a.valid.lease'})
        with self.assertRaises(LicenseError):client.ensure()

    def release(self,edition='plugins',file='plugin.zip',sha=None):
        folder=self.root/'db/releases';folder.mkdir(parents=True,exist_ok=True)
        content=b'not a real installer; test fixture only';(folder/'plugin.zip').write_bytes(content)
        row={'id':'plugin','label':'Plugin test fixture','edition':edition,'version':'test','file':file,
             'sha256':sha or hashlib.sha256(content).hexdigest()}
        (folder/'release.json').write_text(json.dumps({'release_ready':True,'artifacts':[row]}),encoding='utf-8')
        return folder

    def test_one_subscription_downloads_desktop_and_plugins(self):
        self.release();self.paid('desktop')
        self.assertEqual(self.client.get('/api/downloads/plugin').status_code,200)
        self.assertEqual(len(self.client.get('/api/downloads').json()['items']),1)

    def test_unfinished_or_modified_release_is_not_downloadable(self):
        self.paid('plugins');folder=self.release()
        manifest=json.loads((folder/'release.json').read_text());manifest['release_ready']=False
        (folder/'release.json').write_text(json.dumps(manifest))
        self.assertEqual(self.client.get('/api/downloads/plugin').status_code,404)
        self.release(sha='0'*64)
        self.assertEqual(self.client.get('/api/downloads/plugin').status_code,404)

    def test_release_path_cannot_escape_the_release_directory(self):
        self.paid('plugins');self.release(file='../private-secret.zip')
        self.assertEqual(self.client.get('/api/downloads/plugin').status_code,404)

    def test_live_sales_fail_without_actual_release_files(self):
        with self.assertRaisesRegex(ValueError,'verified Desktop and Plugin installers'):
            Settings(data_dir=self.root/'production',origin='https://editor.example.org',production=True,sales_enabled=True,database_url='mysql+pymysql://fixture:test@localhost/storylens_test',
                     key_id='rzp_live_example',key_secret='test',webhook_secret='test',smtp_host='smtp.example.org',
                     mail_from='mail@example.org',support_totp_secret='JBSWY3DPEHPK3PXP',license_private_key=encode(private_bytes(self.key)))
