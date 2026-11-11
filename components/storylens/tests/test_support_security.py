import json
import time
import unittest
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from tests.test_licensing import LicensingFixture,ORIGIN
from hinglish_saas.support import totp
from hinglish_saas.support_mailer import run_once
from hinglish_saas.config import Settings

SECRET='JBSWY3DPEHPK3PXP'  # Public test fixture; never an operator's real secret.


class SupportSecurityTests(LicensingFixture):
    def setUp(self):
        super().setUp();self.settings.support_totp_secret=SECRET
        self.owner=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        response=self.owner.post('/api/auth/register',json={'email':'vineetkd418@gmail.com','password':'Test owner fixture password 12345!'})
        self.owner_csrf=response.json()['csrf']
        self.owner_id=self.store.one('SELECT id FROM users WHERE email=?',('vineetkd418@gmail.com',))['id']
        self.store.execute('UPDATE users SET verified=1 WHERE id=?',(self.owner_id,))

    def tearDown(self):self.owner.close();super().tearDown()
    def headers(self):return {'X-CSRF-Token':self.owner_csrf,'X-Support-Code':totp(SECRET)}

    def new_ticket(self,category='editing',message='This test describes an editing problem.'):
        response=self.client.post('/api/support/tickets',json={'subject':'Test support request','category':category,'message':message},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,200,response.text);return response.json()['id']

    def test_customer_ticket_is_private_and_notifications_are_queued(self):
        ticket=self.new_ticket();row=self.client.get('/api/support/tickets/'+ticket).json()
        self.assertEqual(row['messages'][0]['staff'],0)
        self.assertEqual(len(self.store.all('SELECT id FROM support_outbox')),2)
        other=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        r=other.post('/api/auth/register',json={'email':'outsider@example.test','password':'Outsider fixture password 12345!'})
        csrf=r.json()['csrf'];uid=self.store.one('SELECT id FROM users WHERE email=?',('outsider@example.test',))['id']
        self.store.execute('UPDATE users SET verified=1 WHERE id=?',(uid,))
        self.assertEqual(other.get('/api/support/tickets/'+ticket).status_code,404)
        self.assertEqual(other.post('/api/support/tickets/'+ticket+'/messages',json={'message':'Access attempt'},headers={'X-CSRF-Token':csrf}).status_code,404)
        other.close()

    def test_support_requires_auth_verification_and_csrf(self):
        anonymous=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        self.assertEqual(anonymous.get('/api/support/tickets').status_code,401);anonymous.close()
        self.store.execute('UPDATE users SET verified=0 WHERE id=?',(self.uid,))
        response=self.client.post('/api/support/tickets',json={'subject':'Valid title','category':'billing','message':'Billing issue description'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.post('/api/support/tickets',json={}).status_code,403)

    def test_customer_cannot_self_promote_to_staff_or_reset_devices(self):
        ticket=self.new_ticket('activation')
        for path in ('/api/support/admin/tickets','/api/support/admin/tickets/'+ticket):
            self.assertEqual(self.client.get(path,headers={'X-Support-Code':totp(SECRET)}).status_code,403)
        self.assertEqual(self.client.post('/api/support/admin/tickets/'+ticket+'/device-replacement',json={'edition':'plugins','reason':'An unauthorized device replacement attempt.'},headers={'X-CSRF-Token':self.csrf,'X-Support-Code':totp(SECRET)}).status_code,403)

    def test_owner_inbox_requires_two_step_verification(self):
        self.assertEqual(self.owner.get('/api/support/admin/tickets').status_code,403)
        self.assertEqual(self.owner.get('/api/support/admin/tickets',headers=self.headers()).status_code,200)
        self.assertEqual(self.owner.get('/api/support/admin/tickets',headers={'X-Support-Code':'000000'}).status_code,403)

    def test_staff_reply_is_stored_and_delivered_only_to_ticket_owner(self):
        ticket=self.new_ticket()
        response=self.owner.post('/api/support/admin/tickets/'+ticket+'/messages',json={'message':'Please try the updated settings.'},headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        row=self.client.get('/api/support/tickets/'+ticket).json()
        self.assertEqual(row['messages'][-1]['staff'],1)
        self.assertEqual(row['status'],'waiting')
        recipient=self.store.one('SELECT recipient FROM support_outbox WHERE subject LIKE ?',('%Support replied',))['recipient']
        self.assertEqual(recipient,'license@example.com')

    def test_plain_text_cannot_set_staff_status_or_inject_headers(self):
        response=self.client.post('/api/support/tickets',json={'subject':'Hello\r\nBcc: attacker@example.test','category':'billing','message':'Valid long description'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,422)
        response=self.client.post('/api/support/tickets',json={'subject':'Valid title','category':'billing','message':'Valid long description','staff':True},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,422)
        ticket=self.new_ticket(message='<script>alert("not executable")</script>')
        self.assertIn('<script>',self.client.get('/api/support/tickets/'+ticket).json()['messages'][0]['body'])
        # The browser renders this through textContent, never innerHTML.

    def test_device_replacement_requires_owner_review_and_drains_old_lease(self):
        self.paid('plugins');old=self.activate();ticket=self.new_ticket('activation')
        response=self.owner.post('/api/support/admin/tickets/'+ticket+'/device-replacement',json={'edition':'plugins','reason':'Verified signed-in customer replacing a broken computer.'},headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        self.assertGreater(response.json()['activate_after'],time.time())
        self.assertEqual(self.refresh(old).status_code,403)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key=Ed25519PrivateKey.generate();code=self.begin(key=key)
        self.assertEqual(self.approve(code).status_code,409)
        self.store.execute('UPDATE device_bindings SET release_after=0')
        self.store.execute('UPDATE computer_bindings SET release_after=0')
        self.assertEqual(self.approve(code).status_code,200)
        self.assertEqual(self.poll(code,key).status_code,200)
        self.assertEqual(len(self.store.all('SELECT id FROM devices WHERE revoked=0')),1)

    def test_non_activation_ticket_cannot_reset_a_computer(self):
        ticket=self.new_ticket()
        response=self.owner.post('/api/support/admin/tickets/'+ticket+'/device-replacement',json={'edition':'plugins','reason':'Attempted wrong-category device replacement.'},headers=self.headers())
        self.assertEqual(response.status_code,409)

    def test_mail_failure_preserves_ticket_and_retries_without_false_delivery(self):
        ticket=self.new_ticket();self.settings.smtp_host='smtp.test.invalid';self.settings.mail_from='test@example.test'
        sender=Mock(side_effect=RuntimeError('Simulated offline SMTP.'))
        self.assertTrue(run_once(self.settings,sender));sender.assert_called_once()
        self.assertEqual(self.store.one("SELECT COUNT(*) AS n FROM support_outbox WHERE state='sent'")['n'],0)
        self.assertEqual(self.client.get('/api/support/tickets/'+ticket).status_code,200)
        self.store.execute('UPDATE support_outbox SET available=0');sent=[]
        self.assertTrue(run_once(self.settings,lambda settings,row:sent.append(row['id'])))
        self.assertEqual(len(sent),1)
        self.assertEqual(self.store.one("SELECT COUNT(*) AS n FROM support_outbox WHERE state='sent'")['n'],1)

    def test_mail_worker_does_not_send_if_unconfigured(self):
        self.new_ticket();sender=Mock();self.assertFalse(run_once(self.settings,sender));sender.assert_not_called()
        self.settings.smtp_host='smtp.test.invalid'
        self.assertFalse(self.client.get('/api/support/config').json()['email_notifications_connected'])
        self.assertFalse(run_once(self.settings,sender));sender.assert_not_called()

    def test_crash_on_final_mail_attempt_becomes_visible_as_failed(self):
        self.new_ticket();self.settings.smtp_host='smtp.test.invalid';self.settings.mail_from='test@example.test'
        self.store.execute("UPDATE support_outbox SET state='sending',attempts=8,lease_until=0")
        sender=Mock();self.assertFalse(run_once(self.settings,sender,store=self.store));sender.assert_not_called()
        self.assertEqual(self.store.one("SELECT COUNT(*) AS n FROM support_outbox WHERE state='failed'")['n'],2)

    def test_contact_and_phone_policy(self):
        config=self.client.get('/api/support/config').json()
        self.assertEqual(config['email'],'vineetkd418@gmail.com')
        self.assertFalse(config['whatsapp_support']);self.assertFalse(config['phone_support'])
        for path in ('/support','/support/inbox'):
            self.assertEqual(self.client.get(path).status_code,200)

    def test_device_limit_cannot_be_increased_by_configuration(self):
        with self.assertRaisesRegex(ValueError,'exactly one'):Settings(device_limit=2)

    def test_cookie_only_hosted_processing_cannot_start_in_production(self):
        with self.assertRaisesRegex(ValueError,'browser-to-device proof'):
            Settings(production=True,origin='https://editor.example.test',worker_enabled=True,database_url='mysql+pymysql://fixture:test@localhost/storylens_test')

    def test_invalid_operator_authenticator_secret_fails_at_startup(self):
        with self.assertRaisesRegex(ValueError,'Base32'):
            Settings(support_totp_secret='not-a-valid-key')

    def test_minute_requests_do_not_erase_hourly_throttles(self):
        self.assertTrue(self.store.rate('hourly-login',1,3600))
        self.assertTrue(self.store.rate('minute-status',10,60))
        self.assertFalse(self.store.rate('hourly-login',1,3600))

    def test_new_login_invalidates_the_previous_website_session(self):
        other=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        response=other.post('/api/auth/login',json={'email':'license@example.com','password':'unique license test password 123'})
        self.assertEqual(response.status_code,200);self.assertEqual(self.client.get('/api/me').status_code,401)
        self.assertEqual(other.get('/api/me').status_code,200);other.close()
