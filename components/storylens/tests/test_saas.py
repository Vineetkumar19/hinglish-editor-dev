"""Subscription boundary tests. The provider is simulated; no money is taken."""
import hashlib
import hmac
import json
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
from hinglish_saas.app import create_app, COOKIE
from hinglish_saas.billing import BillingError, add_months
from hinglish_saas.config import Settings
from hinglish_saas.security import digest
from hinglish_saas.worker import claim, process_job, worker_environment

ORIGIN='http://127.0.0.1:8788'


class Provider:
    def __init__(self):self.orders={};self.payments={}
    def create_order(self,amount,receipt):
        oid='order_'+uuid.uuid4().hex;pid='pay_'+uuid.uuid4().hex
        self.orders[oid]={'id':oid,'amount':amount,'currency':'INR'}
        self.payments[pid]={'id':pid,'order_id':oid,'amount':amount,'currency':'INR','status':'captured','amount_refunded':0}
        return self.orders[oid]
    def fetch_payment(self,pid):return self.payments[pid]


class SaaSTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.settings=Settings(data_dir=self.folder,worker_enabled=True,sales_enabled=True,key_id='rzp_test_demo',key_secret='test-secret',webhook_secret='webhook-secret')
        self.provider=Provider();self.app=create_app(self.settings,self.provider);self.store=self.app.state.store
        self.client=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN});self.csrf=self.register(self.client,'one@example.com')
        self.user=self.store.one('SELECT * FROM users WHERE email=?',('one@example.com',))
        self.store.execute('UPDATE users SET verified=1 WHERE id=?',(self.user['id'],))

    def tearDown(self):self.client.close();self.temp.cleanup()

    def register(self,client,email):
        response=client.post('/api/auth/register',json={'email':email,'password':'A unique test password 1234'})
        self.assertEqual(response.status_code,200,response.text);return response.json()['csrf']

    def second(self):
        client=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN});csrf=self.register(client,'two@example.com')
        uid=self.store.one('SELECT id FROM users WHERE email=?',('two@example.com',))['id'];self.store.execute('UPDATE users SET verified=1 WHERE id=?',(uid,));return client,csrf,uid

    def make_order(self,client=None,csrf=None,plan='monthly'):
        client=client or self.client;csrf=csrf or self.csrf
        response=client.post('/api/billing/orders',json={'plan':plan},headers={'X-CSRF-Token':csrf})
        self.assertEqual(response.status_code,200,response.text);order=response.json()
        payment=next(p for p in self.provider.payments.values() if p['order_id']==order['order_id'])
        signature=hmac.new(b'test-secret',(order['order_id']+'|'+payment['id']).encode(),hashlib.sha256).hexdigest()
        return order,{'order_id':order['order_id'],'payment_id':payment['id'],'signature':signature}

    def paid(self,client=None,csrf=None):
        order,payload=self.make_order(client,csrf)
        response=(client or self.client).post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':csrf or self.csrf})
        self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['active']);return order,payload

    def webhook(self,data,signature=None):
        raw=json.dumps(data,separators=(',',':')).encode()
        sig=signature or hmac.new(b'webhook-secret',raw,hashlib.sha256).hexdigest()
        return self.client.post('/api/billing/webhook',content=raw,headers={'Content-Type':'application/json','X-Razorpay-Signature':sig})

    def test_public_website_and_preview_load(self):
        for route in ('/','/tour','/account','/policies','/assets/site.css','/assets/fonts/albert-sans.ttf'):
            self.assertEqual(self.client.get(route).status_code,200,route)
        self.assertIn('Interactive preview',self.client.get('/tour').text)

    def test_password_and_session_not_plaintext(self):
        self.assertTrue(self.user['password'].startswith('$argon2id$'))
        raw=self.client.cookies.get(COOKIE)
        self.assertIsNone(self.store.one('SELECT * FROM sessions WHERE token=?',(raw,)))
        self.assertIsNotNone(self.store.one('SELECT * FROM sessions WHERE token=?',(digest(raw),)))

    def test_anonymous_and_unpaid_accounts_cannot_use_editor(self):
        anonymous=TestClient(self.app,base_url=ORIGIN,headers={'Origin':ORIGIN})
        for path in ('/api/jobs','/api/uploads','/api/exports/anything'):
            self.assertEqual(anonymous.get(path).status_code,401,path)
            self.assertEqual(self.client.get(path).status_code,402,path)
        self.assertEqual(anonymous.get('/app',follow_redirects=False).status_code,303)
        self.assertEqual(self.client.get('/app',follow_redirects=False).headers['location'],'/account?view=billing')
        anonymous.close()

    def test_json_and_storage_flags_do_not_grant_access(self):
        response=self.client.post('/api/jobs',json={'tool':'clean','paid':True,'subscription':'annual'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,402)
        self.assertFalse(self.client.get('/api/me').json()['subscription']['active'])

    def test_origin_host_and_csrf_are_enforced(self):
        self.assertEqual(self.client.post('/api/auth/logout',json={},headers={'Origin':'https://attacker.example','X-CSRF-Token':self.csrf}).status_code,403)
        self.assertEqual(self.client.post('/api/auth/logout',json={}).status_code,403)
        self.assertEqual(self.client.get('/api/me',headers={'Host':'attacker.example'}).status_code,400)
        self.assertEqual(self.client.post('/api/auth/login',json={},headers={'Origin':''}).status_code,403)

    def test_monthly_and_annual_prices_cannot_be_overridden(self):
        self.assertEqual(self.client.post('/api/billing/orders',json={'plan':'monthly','amount':1},headers={'X-CSRF-Token':self.csrf}).status_code,422)
        monthly,_=self.make_order();annual,_=self.make_order(plan='annual')
        self.assertEqual(monthly['amount'],200000);self.assertEqual(annual['amount'],2000000)

    def test_forged_checkout_does_not_activate(self):
        _,payload=self.make_order();payload['signature']='a'*64
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,400)
        self.assertFalse(self.store.entitlement(self.user['id'])['active'])

    def test_authorised_but_not_captured_payment_does_not_activate(self):
        _,payload=self.make_order();self.provider.payments[payload['payment_id']]['status']='authorized'
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,400)

    def test_mismatched_currency_and_amount_do_not_activate(self):
        _,payload=self.make_order();payment=self.provider.payments[payload['payment_id']]
        payment['amount']=1
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,400)
        payment['amount']=200000;payment['currency']='USD'
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,400)

    def test_order_from_other_customer_cannot_be_claimed(self):
        _,payload=self.make_order();other,csrf,uid=self.second()
        self.assertEqual(other.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':csrf}).status_code,400)
        self.assertFalse(self.store.entitlement(uid)['active']);other.close()

    def test_duplicate_callback_and_webhook_do_not_extend_access(self):
        order,payload=self.paid();first=self.store.one('SELECT ends FROM orders WHERE id=?',(order['order_id'],))['ends']
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,200)
        event={'event':'payment.captured','payload':{'payment':{'entity':{'id':payload['payment_id']}}}}
        self.assertEqual(self.webhook(event).status_code,200);self.assertEqual(self.webhook(event).status_code,200)
        self.assertEqual(self.store.one('SELECT ends FROM orders WHERE id=?',(order['order_id'],))['ends'],first)

    def test_refund_revokes_access_and_capture_cannot_reactivate(self):
        _,payload=self.paid();event={'event':'refund.processed','payload':{'refund':{'entity':{'payment_id':payload['payment_id']}}}}
        self.assertEqual(self.webhook(event).status_code,200);self.assertFalse(self.store.entitlement(self.user['id'])['active'])
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,400)

    def test_out_of_order_refund_blocks_future_capture(self):
        _,payload=self.make_order();event={'event':'refund.created','payload':{'refund':{'entity':{'payment_id':payload['payment_id']}}}}
        self.assertEqual(self.webhook(event).status_code,200)
        self.assertEqual(self.client.post('/api/billing/verify',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,400)

    def test_unsigned_webhook_does_not_grant_access(self):
        _,payload=self.make_order();event={'event':'payment.captured','payload':{'payment':{'entity':{'id':payload['payment_id']}}}}
        self.assertEqual(self.webhook(event,'0'*64).status_code,400);self.assertFalse(self.store.entitlement(self.user['id'])['active'])

    def test_expiry_is_checked_on_each_request(self):
        order,_=self.paid();self.store.execute('UPDATE orders SET ends=? WHERE id=?',(time.time()-1,order['order_id']))
        self.assertEqual(self.client.get('/api/jobs').status_code,402)

    def test_disabled_sales_and_unverified_email_block_checkout(self):
        self.settings.sales_enabled=False
        self.assertEqual(self.client.post('/api/billing/orders',json={'plan':'monthly'},headers={'X-CSRF-Token':self.csrf}).status_code,503)
        self.settings.sales_enabled=True;self.store.execute('UPDATE users SET verified=0 WHERE id=?',(self.user['id'],))
        self.assertEqual(self.client.post('/api/billing/orders',json={'plan':'monthly'},headers={'X-CSRF-Token':self.csrf}).status_code,403)

    def test_upload_paths_invalid_video_and_limits(self):
        self.paid();headers={'X-CSRF-Token':self.csrf,'Content-Type':'application/octet-stream'}
        self.assertEqual(self.client.post('/api/uploads?name=../secret.mp4',content=b'fake',headers=headers).status_code,422)
        self.assertEqual(self.client.post('/api/uploads?name=secret.mp4',content=b'fake',headers=headers).status_code,415)
        self.assertEqual(self.store.all('SELECT * FROM uploads'),[])
        self.settings.max_upload_bytes=2
        self.assertEqual(self.client.post('/api/uploads?name=file.mp4',content=b'four',headers=headers).status_code,413)

    def test_oversized_json_rejected(self):
        self.assertEqual(self.client.post('/api/auth/login',content=b'a'*70000,headers={'Content-Type':'application/json'}).status_code,413)

    def test_customer_upload_ids_and_job_ids_are_isolated(self):
        self.paid();other,csrf,uid=self.second();self.paid(other,csrf)
        file=self.folder/'video.mp4';file.write_bytes(b'fixture')
        self.store.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?)',('one-upload',self.user['id'],'test.mp4',str(file),7,time.time()))
        denied=other.post('/api/jobs',json={'tool':'clean','upload_ids':['one-upload']},headers={'X-CSRF-Token':csrf})
        self.assertEqual(denied.status_code,404)
        job=self.client.post('/api/jobs',json={'tool':'clean','upload_ids':['one-upload']},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(job.status_code,200,job.text)
        self.assertEqual(other.get('/api/jobs/'+job.json()['id']).status_code,404)
        self.assertEqual(other.get('/api/jobs').json(),[]);other.close()

    def test_export_ownership_and_path_boundary(self):
        self.paid();other,csrf,uid=self.second();self.paid(other,csrf)
        now=time.time();root=self.folder/'work'/self.user['id'];root.mkdir(parents=True);file=root/'clip.mp4';file.write_bytes(b'owned output')
        self.store.execute('INSERT INTO jobs(id,user_id,tool,payload,created,updated) VALUES(?,?,?,?,?,?)',('job',self.user['id'],'clean','{}',now,now))
        self.store.execute('INSERT INTO exports VALUES(?,?,?,?,?,?)',('export',self.user['id'],'job','clip.mp4',str(file),now))
        self.assertEqual(self.client.get('/api/exports/export').content,b'owned output')
        self.assertEqual(other.get('/api/exports/export').status_code,404)
        self.store.execute('UPDATE exports SET path=? WHERE id=?',(str(self.folder/'subscriptions.sqlite3'),'export'))
        self.assertEqual(self.client.get('/api/exports/export').status_code,404);other.close()

    def test_paths_commands_and_publishing_never_dispatch(self):
        self.paid()
        for payload in ({'tool':'clean','input_path':'C:/private'},{'tool':'clean','options':{'command':'powershell'}},{'tool':'publish'},{'tool':'clean','options':{'profile':'cricket'}}):
            self.assertEqual(self.client.post('/api/jobs',json=payload,headers={'X-CSRF-Token':self.csrf}).status_code,422,payload)

    def test_private_source_is_not_a_public_static_file(self):
        for path in ('/config.cpu.json','/.env','/models/weights','/hinglish_app/server.py','/cache/saas/subscriptions.sqlite3','/api/bridge'):
            self.assertEqual(self.client.get(path).status_code,404,path)

    def test_security_headers_and_secrets_absent_from_config(self):
        r=self.client.get('/');self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy']);self.assertEqual(r.headers['x-content-type-options'],'nosniff')
        config=self.client.get('/api/config').text
        for secret in ('test-secret','webhook-secret','smtp_password'):self.assertNotIn(secret,config)

    def test_logout_invalidates_copied_session(self):
        raw=self.client.cookies.get(COOKIE);self.assertEqual(self.client.post('/api/auth/logout',json={},headers={'X-CSRF-Token':self.csrf}).status_code,200)
        self.assertEqual(self.client.get('/api/me',headers={'Cookie':COOKIE+'='+raw}).status_code,401)

    def test_email_token_is_single_use_and_reset_revokes_sessions(self):
        raw='x'*40;self.store.execute('INSERT INTO tokens VALUES(?,?,?,?)',(digest(raw),self.user['id'],'reset',time.time()+300))
        response=self.client.post('/api/auth/reset',json={'token':raw,'password':'A newer unique test password 7890'})
        self.assertEqual(response.status_code,200);self.assertEqual(self.client.get('/api/me').status_code,401)
        self.assertEqual(self.client.post('/api/auth/reset',json={'token':raw,'password':'A newer unique test password 7890'}).status_code,400)

    def test_rate_limit_cannot_be_bypassed_with_forwarded_header(self):
        # Different email addresses isolate the 60/minute ASGI-peer limit from
        # the independent per-email throttle; forged forwarded IPs cannot reset it.
        # Keep the test inside one rate window even when password hashing spans
        # a wall-clock minute boundary. This does not change production clocks.
        with patch('hinglish_saas.store.time.time',return_value=time.time()):
            for i in range(61):response=self.client.post('/api/auth/login',json={'email':'probe'+str(i)+'@example.test','password':'Wrong unique password 9876'},headers={'X-Forwarded-For':'1.2.3.'+str(i)})
        self.assertEqual(response.status_code,429)

    def test_only_one_render_job_is_claimed(self):
        now=time.time()
        for key in ('a','b'):self.store.execute('INSERT INTO jobs(id,user_id,tool,payload,created,updated) VALUES(?,?,?,?,?,?)',(key,self.user['id'],'clean','{}',now,now))
        self.assertEqual(claim(self.store)['id'],'a');self.assertIsNone(claim(self.store))

    def test_worker_requires_a_real_downloadable_output(self):
        from unittest.mock import patch
        self.paid()
        row={'id':uuid.uuid4().hex,'user_id':self.user['id'],'tool':'clean','payload':json.dumps({'upload_ids':[],'script':'','options':{}})}
        with patch('hinglish_app.server.AppState') as engine:
            engine.return_value.jobs={}
            engine.return_value.snapshot.return_value={'status':'complete'}
            with self.assertRaisesRegex(RuntimeError,'No downloadable output'):
                process_job(self.store,self.settings,row)

    def test_renderer_does_not_inherit_merchant_or_unrelated_host_secrets(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{'HINGLISH_SAAS_RAZORPAY_KEY_SECRET':'merchant-secret','SMTP_PASSWORD':'mail-secret','OPENAI_API_KEY':'unrelated-host-secret','CUDA_VISIBLE_DEVICES':'0'}):
            env=worker_environment()
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'0')
            for key in ('HINGLISH_SAAS_RAZORPAY_KEY_SECRET','SMTP_PASSWORD','OPENAI_API_KEY'):self.assertNotIn(key,env)

    def test_production_requires_https_and_launch_configuration(self):
        with self.assertRaises(ValueError):Settings(production=True,origin=ORIGIN)
        with self.assertRaises(ValueError):Settings(production=True,origin='https://example.com',sales_enabled=True)

    def test_calendar_month_renewal_handles_january_31(self):
        from datetime import datetime,timezone
        start=datetime(2026,1,31,tzinfo=timezone.utc).timestamp()
        end=datetime.fromtimestamp(add_months(start,1),timezone.utc)
        self.assertEqual((end.month,end.day),(2,28))


if __name__=='__main__':unittest.main()
