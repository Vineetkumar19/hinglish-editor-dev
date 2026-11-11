import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import requests
from tests.test_licensing import LicensingFixture,ORIGIN
from hinglish_license.crypto import encode,private_bytes,public_bytes,sign_lease
from hinglish_license.client import LicenseClient,LicenseError
from hinglish_license.device import DeviceVault
from hinglish_app.aftereffects_adapter import cut_manifest
from defusedxml.common import DefusedXmlException


class DeviceSecurityTests(LicensingFixture):
    def test_same_key_with_a_different_machine_identity_cannot_reactivate(self):
        self.paid('plugins');self.activate()
        response=self.client.post('/api/licenses/device-code',json={'edition':'plugins','public_key':self.pub,'name':'Another computer','hardware_hash':'a'*64},headers={'Origin':''})
        code=response.json();self.assertEqual(self.approve(code).status_code,409)

    def test_signed_refresh_for_a_different_machine_is_denied(self):
        self.paid('plugins');device=self.activate();nonce='b'*32;stamp=int(time.time());hardware='c'*64
        response=self.client.post('/api/licenses/refresh',json={'device_id':device['device_id'],'credential':device['credential'],
            'nonce':nonce,'timestamp':stamp,'hardware_hash':hardware,
            'signature':encode(self.device.sign(f'refresh:{device["device_id"]}:{nonce}:{stamp}:{hardware}'.encode()))},headers={'Origin':''})
        self.assertEqual(response.status_code,403)

    def test_offline_network_failure_does_not_grant_editing_access(self):
        client=LicenseClient(self.root/'client',ORIGIN,self.public,'plugins',allow_loopback=True)
        now=int(time.time());device='a'*32
        claims={'iss':ORIGIN,'aud':'hinglish-editor','public_key':client.installation_key,'device_id':device,'edition':'plugins',
                'hosts':['premiere'],'iat':now,'exp':now+300,'hardware_hash':client.hardware_hash,'license_version':2}
        client.save({'device_id':device,'credential':'x'*43,'lease':sign_lease(self.key,claims)})
        with patch.object(client,'request',side_effect=requests.ConnectionError('Offline test.')):
            with self.assertRaisesRegex(LicenseError,'internet'):client.ensure()

    def test_long_lived_legacy_license_is_rejected(self):
        client=LicenseClient(self.root/'client',ORIGIN,self.public,'plugins',allow_loopback=True);now=int(time.time());device='a'*32
        claims={'iss':ORIGIN,'aud':'hinglish-editor','public_key':client.installation_key,'device_id':device,'edition':'plugins',
                'hosts':['premiere'],'iat':now,'exp':now+86400,'hardware_hash':client.hardware_hash,'license_version':2}
        with self.assertRaises(LicenseError):client.claims({'device_id':device,'lease':sign_lease(self.key,claims)},'premiere')

    def test_simultaneously_approved_codes_cannot_create_two_devices(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self.paid('plugins');one=self.begin();key=Ed25519PrivateKey.generate();two=self.begin(key=key)
        self.assertEqual(self.approve(one).status_code,200);self.assertEqual(self.approve(two).status_code,200)
        self.assertEqual(self.poll(one).status_code,200);self.assertEqual(self.poll(two,key).status_code,409)
        self.assertEqual(len(self.store.all('SELECT id FROM devices WHERE revoked=0')),1)


class LocalDataSecurityTests(unittest.TestCase):
    def test_xml_entities_are_rejected_before_expansion(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'malicious.xml'
            file.write_text('<!DOCTYPE xmeml [<!ENTITY payload "untrusted">]><xmeml><sequence><name>&payload;</name></sequence></xmeml>',encoding='utf-8')
            with self.assertRaises(DefusedXmlException):cut_manifest(file)

    @unittest.skipUnless(os.name=='nt','Windows data protection is platform-specific.')
    def test_windows_vault_ciphertext_is_bound_to_its_machine_context(self):
        with tempfile.TemporaryDirectory() as folder:
            vault=DeviceVault(Path(folder)/'license')
            secret=b'test secret, not an actual key';encrypted=vault.encode(secret)
            self.assertNotIn(secret,encrypted);self.assertEqual(vault.decode(encrypted),secret)
            vault.hardware_hash='0'*64
            with self.assertRaises(ValueError):vault.decode(encrypted)
