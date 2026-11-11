"""Server-owned prices, provider capture checks, atomic grants and revocation."""
import calendar
from datetime import datetime, timezone
import hashlib
import hmac
import re
import time
import requests
from .config import PLANS, EDITIONS


class BillingError(ValueError): pass


def add_months(stamp, months):
    d=datetime.fromtimestamp(stamp,timezone.utc)
    year=d.year+(d.month-1+months)//12;month=(d.month-1+months)%12+1
    return d.replace(year=year,month=month,day=min(d.day,calendar.monthrange(year,month)[1])).timestamp()


class Razorpay:
    def __init__(self, settings): self.settings=settings
    def request(self, method, path, body=None):
        if not self.settings.key_id or not self.settings.key_secret:raise BillingError('Payments are not connected yet.')
        try:
            response=requests.request(method,'https://api.razorpay.com/v1/'+path,
                auth=(self.settings.key_id,self.settings.key_secret),json=body,timeout=(5,20))
            response.raise_for_status();return response.json()
        except (requests.RequestException,ValueError) as exc:
            raise BillingError('The payment provider could not verify this payment. Retry shortly.') from exc
    def create_order(self, amount, receipt):
        return self.request('POST','orders',{'amount':amount,'currency':'INR','receipt':receipt})
    def fetch_payment(self, payment_id):
        if not re.fullmatch(r'pay_[A-Za-z0-9]{1,80}',payment_id):raise BillingError('Invalid payment reference.')
        return self.request('GET','payments/'+payment_id)


class Billing:
    def __init__(self,store,settings,provider=None):
        self.store=store;self.settings=settings;self.provider=provider or Razorpay(settings)

    def create(self,user_id,plan,receipt,edition='bundle'):
        if plan not in PLANS:raise BillingError('Choose monthly or annual.')
        if edition not in (*EDITIONS,'bundle'):raise BillingError('Choose the Storylens subscription.')
        edition='bundle'
        p=PLANS[plan];order=self.provider.create_order(p['amount'],receipt)
        if order.get('amount')!=p['amount'] or order.get('currency')!='INR' or not re.fullmatch(r'order_[A-Za-z0-9]{1,80}',str(order.get('id',''))):
            raise BillingError('Payment provider returned an invalid order.')
        self.store.execute('INSERT INTO orders(id,user_id,plan,amount,created,edition) VALUES(?,?,?,?,?,?)',(order['id'],user_id,plan,p['amount'],time.time(),edition))
        return {'order_id':order['id'],'amount':p['amount'],'currency':'INR','key_id':self.settings.key_id,'plan':plan,'edition':edition}

    def verify_checkout(self,user_id,order_id,payment_id,signature):
        order=self.store.one('SELECT * FROM orders WHERE id=? AND user_id=?',(order_id,user_id))
        if not order:raise BillingError('This order does not belong to this account.')
        expected=hmac.new(self.settings.key_secret.encode(),f'{order["id"]}|{payment_id}'.encode(),hashlib.sha256).hexdigest()
        if not self.settings.key_secret or not hmac.compare_digest(expected,signature):raise BillingError('Payment signature is invalid.')
        self.grant(self.provider.fetch_payment(payment_id))
        return self.store.entitlement(user_id,edition=order['edition'])

    def grant(self,payment):
        now=time.time()
        with self.store.connect(immediate=True) as db:
            order=db.execute('SELECT * FROM orders WHERE id=?',(payment.get('order_id'),)).fetchone()
            if not order:raise BillingError('Payment has no matching server order.')
            if payment.get('status')!='captured' or payment.get('amount')!=order['amount'] or payment.get('currency')!=order['currency'] or payment.get('amount_refunded',0)!=0:
                raise BillingError('Payment has not been captured for the correct amount.')
            if not re.fullmatch(r'pay_[A-Za-z0-9]{1,80}',str(payment.get('id',''))):raise BillingError('Invalid payment reference.')
            if db.execute('SELECT payment_id FROM revocations WHERE payment_id=?',(payment['id'],)).fetchone():raise BillingError('This payment has been revoked.')
            if order['state']=='paid':
                if order['payment_id']!=payment['id']:raise BillingError('Order is already settled.')
                return
            if order['state']=='revoked':raise BillingError('This payment has been revoked.')
            latest=db.execute("SELECT MAX(ends) AS ends FROM orders WHERE user_id=? AND state='paid'",(order['user_id'],)).fetchone()['ends']
            starts=max(now,latest or now);ends=add_months(starts,PLANS[order['plan']]['months'])
            db.execute("UPDATE orders SET state='paid',payment_id=?,starts=?,ends=? WHERE id=?",(payment['id'],starts,ends,order['id']))

    def webhook(self,raw,signature,event_id):
        import json
        if not self.settings.webhook_secret:raise BillingError('Webhooks are not configured.')
        expected=hmac.new(self.settings.webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,signature):raise BillingError('Webhook signature is invalid.')
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get('payload',{}),dict):raise BillingError('Invalid webhook payload.')
        event=data.get('event');payload=data.get('payload',{})
        # Signed bodies are deduplicated independently of the unsigned header.
        event_id=hashlib.sha256(raw).hexdigest()
        if self.store.one('SELECT id FROM webhook_events WHERE id=?',(event_id,)):return
        if event=='payment.captured':
            entity=payload.get('payment',{}).get('entity',{})
            self.grant(self.provider.fetch_payment(str(entity.get('id',''))))
        elif event in ('refund.created','refund.processed','payment.dispute.created'):
            entity=payload.get('refund',payload.get('dispute',{})).get('entity',{})
            payment_id=entity.get('payment_id')
            if not re.fullmatch(r'pay_[A-Za-z0-9]{1,80}',str(payment_id or '')):raise BillingError('Invalid revocation reference.')
            with self.store.connect(immediate=True) as db:
                db.execute('INSERT OR IGNORE INTO revocations VALUES(?,?)',(payment_id,time.time()))
                db.execute("UPDATE orders SET state='revoked' WHERE payment_id=?",(payment_id,))
        self.store.execute('INSERT OR IGNORE INTO webhook_events VALUES(?,?)',(event_id,time.time()))
