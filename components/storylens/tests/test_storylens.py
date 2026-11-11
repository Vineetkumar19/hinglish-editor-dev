import hashlib
import json
import time
import unittest
import uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tests import test_support_security
from tests.test_licensing import LicensingFixture,ORIGIN
from hinglish_license.crypto import encode,public_bytes
from hinglish_saas.config import Settings


class StorylensTests(test_support_security.SupportSecurityTests):
    # Inherit the real security cases too: reviews must not weaken ticket access.
    def review(self,rating=5):
        return self.client.post('/api/reviews/mine',json={'display_name':'Test customer','rating':rating,'title':'Helpful local workflow','body':'The local tools save time. More control over effects would be useful.'},headers={'X-CSRF-Token':self.csrf})

    def test_reviews_are_owned_unique_and_moderated(self):
        result=self.review();self.assertEqual(result.status_code,200,result.text)
        id=result.json()['id'];self.assertEqual(self.client.get('/api/reviews').json()['count'],0)
        self.assertEqual(self.review(4).json()['id'],id)
        self.assertEqual(len(self.store.all('SELECT id FROM reviews')),1)
        self.assertEqual(self.client.post('/api/admin/reviews/'+id,json={'status':'published'},headers={'X-CSRF-Token':self.csrf}).status_code,403)
        published=self.owner.post('/api/admin/reviews/'+id,json={'status':'published'},headers=self.headers())
        self.assertEqual(published.status_code,200,published.text)
        public=self.client.get('/api/reviews').json();self.assertEqual((public['count'],public['average']),(1,4))
        self.assertNotIn('email',public['items'][0]);self.assertNotIn('user_id',public['items'][0])
        self.assertEqual(self.review(2).status_code,200);self.assertEqual(self.client.get('/api/reviews').json()['count'],0)
        self.assertEqual(self.client.delete('/api/reviews/mine',headers={'X-CSRF-Token':self.csrf}).status_code,200)

    def test_invalid_ratings_unverified_accounts_and_csrf_are_denied(self):
        for value in (0,6,3.5,'5'):
            self.assertEqual(self.review(value).status_code,422)
        self.assertEqual(self.client.post('/api/reviews/mine',json={}).status_code,403)
        self.store.execute('UPDATE users SET verified=0 WHERE id=?',(self.uid,))
        self.assertEqual(self.review().status_code,403)

    def test_dashboard_private_and_counts_match_actual_database(self):
        self.assertEqual(self.client.get('/api/admin/overview').status_code,403)
        self.assertEqual(self.owner.get('/api/admin/overview').status_code,403)
        result=self.owner.get('/api/admin/overview',headers=self.headers());self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['counts']['users'],2)
        users=self.owner.get('/api/admin/users',headers=self.headers()).json()['items']
        self.assertEqual(len(users),2)
        for user in users:
            for secret in ('password','csrf','token','credential'):self.assertNotIn(secret,user)
        attack=self.owner.get('/api/admin/users',params={'search':"' OR 1=1 --"},headers=self.headers())
        self.assertEqual(attack.json()['count'],0)

    def test_verified_customer_badge_requires_payment_not_client_claim(self):
        id=self.review().json()['id'];self.owner.post('/api/admin/reviews/'+id,json={'status':'published'},headers=self.headers())
        self.assertFalse(self.client.get('/api/reviews').json()['items'][0]['verified_customer'])
        self.paid('desktop')
        self.assertTrue(self.client.get('/api/reviews').json()['items'][0]['verified_customer'])

    def test_desktop_and_plugins_cannot_be_split_between_computers(self):
        self.paid('desktop');one=self.activate()
        key=Ed25519PrivateKey.generate();code=self.begin('desktop',key)
        self.assertEqual(self.approve(code).status_code,409)
        same=self.begin('desktop');self.assertEqual(self.approve(same).status_code,200)
        self.assertEqual(self.poll(same).status_code,200)
        self.assertEqual(len(self.store.all('SELECT id FROM devices WHERE revoked=0')),2)
        self.assertEqual(len(self.store.all('SELECT user_id FROM computer_bindings WHERE public_key IS NOT NULL')),1)

    def test_signed_usage_events_are_idempotent_and_no_content_is_accepted(self):
        self.paid('desktop');device=self.activate();event={'id':uuid.uuid4().hex,'device_id':device['device_id'],'timestamp':int(time.time()),'tool':'captions','outcome':'complete','duration':12.5,'app_version':'1.0'}
        event['signature']=encode(self.device.sign(('usage:'+json.dumps(event,sort_keys=True,separators=(',',':'))).encode()))
        event['credential']=device['credential']
        for _ in range(2):
            result=self.client.post('/api/usage',json=event,headers={'Origin':''});self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(len(self.store.all('SELECT id FROM usage_events')),1)
        event['tool']='clean';self.assertEqual(self.client.post('/api/usage',json=event,headers={'Origin':''}).status_code,403)
        event['video_path']='private.mp4';self.assertEqual(self.client.post('/api/usage',json=event,headers={'Origin':''}).status_code,422)

    def test_production_requires_mysql_and_remote_tls(self):
        with self.assertRaisesRegex(ValueError,'requires MySQL'):Settings(production=True,origin='https://editor.example.test')
        with self.assertRaisesRegex(ValueError,'TLS'):Settings(production=True,origin='https://editor.example.test',database_url='mysql+pymysql://fixture:test@remote.example/storylens')
