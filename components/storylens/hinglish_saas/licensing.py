"""Device-code activation, proof-of-possession renewal and signed offline leases."""
import re
import secrets
import time
import uuid
from fastapi import HTTPException, Request
from pydantic import Field
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from hinglish_license.crypto import decode, encode, public_bytes, sign_lease
from .config import EDITIONS
from .security import digest, token


def mount_licenses(app,settings,store,account,body,Input,rate):
    key=Ed25519PrivateKey.from_private_bytes(decode(settings.license_private_key,32)) if settings.license_private_key else None

    class Begin(Input):
        edition: str=Field(pattern='^(desktop|plugins)$')
        public_key: str=Field(min_length=43,max_length=44)
        name: str=Field(min_length=1,max_length=80)
        hardware_hash: str=Field(pattern=r'^[a-f0-9]{64}$')

    class Approve(Input):
        user_code: str=Field(pattern=r'^[A-Z0-9]{4}-[A-Z0-9]{4}$')

    class Poll(Input):
        device_code: str=Field(min_length=32,max_length=100)
        signature: str=Field(min_length=86,max_length=88)

    class Refresh(Input):
        device_id: str=Field(pattern=r'^[a-f0-9]{32}$')
        credential: str=Field(min_length=32,max_length=100)
        nonce: str=Field(pattern=r'^[a-f0-9]{32}$')
        timestamp: int
        signature: str=Field(min_length=86,max_length=88)
        hardware_hash: str=Field(pattern=r'^[a-f0-9]{64}$')

    def ready():
        if not key: raise HTTPException(503,'Device activation is not connected yet.')

    def proof(public_key,signature,message):
        try: Ed25519PublicKey.from_public_bytes(decode(public_key,32)).verify(decode(signature,64),message.encode())
        except Exception: raise HTTPException(403,'This request did not come from the activated installation.')

    def lease(device):
        stamp=time.time();now=int(stamp)
        with store.connect(immediate=True) as db:
            current=db.execute('SELECT d.* FROM devices d JOIN device_bindings b ON b.device_id=d.id AND b.user_id=d.user_id AND b.edition=d.edition WHERE d.id=? AND d.revoked=0',(device['id'],)).fetchone()
            if not current:raise HTTPException(403,'This computer has been deactivated.')
            computer_row=db.execute('SELECT * FROM computer_bindings WHERE user_id=?',(current['user_id'],)).fetchone()
            if not computer_row or (computer_row['public_key'],computer_row['hardware_hash'])!=(current['public_key'],current['hardware_hash']):raise HTTPException(403,'This subscription belongs to a different computer.')
            grant=db.execute("SELECT id,ends FROM orders WHERE user_id=? AND state='paid' AND starts<=? AND ends>? ORDER BY ends DESC LIMIT 1",
                             (current['user_id'],stamp,stamp)).fetchone()
            if not grant:raise HTTPException(402,'This edition does not have an active subscription.')
            expires=min(now+300,int(grant['ends']))
            db.execute('UPDATE devices SET last_lease=MAX(last_lease,?) WHERE id=?',(expires,current['id']))
            result={'lease':sign_lease(key,{'iss':settings.origin,'aud':'hinglish-editor','device_id':current['id'],
                    'public_key':current['public_key'],'edition':current['edition'],'hosts':EDITIONS[current['edition']]['hosts'],
                    'hardware_hash':current['hardware_hash'],'license_version':2,
                    'grant':grant['id'],'iat':now,'exp':expires}),'refresh_after':now+60}
        return result

    def computer(db,user_id,public_key,hardware_hash,claim=False):
        row=db.execute('SELECT * FROM computer_bindings WHERE user_id=?',(user_id,)).fetchone()
        if row and row['release_after']>time.time():raise HTTPException(409,'Wait for the previous computer license to expire before activating.')
        if row and row['public_key'] and (row['public_key'],row['hardware_hash'])!=(public_key,hardware_hash):
            raise HTTPException(409,'One Storylens subscription includes Desktop and Plugins on one computer. Contact Support to replace it.')
        if claim:db.execute('INSERT INTO computer_bindings(user_id,public_key,hardware_hash) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET public_key=excluded.public_key,hardware_hash=excluded.hardware_hash,release_after=0',(user_id,public_key,hardware_hash))

    @app.get('/api/licenses/public-key')
    def public_key():
        ready(); return {'public_key':encode(public_bytes(key.public_key())),'device_limit':1,'offline_hours':0,'online_verification':True}

    @app.post('/api/licenses/device-code')
    async def begin(request:Request):
        ready(); rate(request,'device-code',10,3600); data=await body(request,Begin)
        try: Ed25519PublicKey.from_public_bytes(decode(data.public_key,32))
        except ValueError: raise HTTPException(422,'Invalid installation key.')
        if any(ord(c)<32 for c in data.name):raise HTTPException(422,'Choose a simple device name.')
        raw=token(); alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        user_code=''.join(secrets.choice(alphabet) for _ in range(8));user_code=user_code[:4]+'-'+user_code[4:]
        with store.connect(immediate=True) as db:
            db.execute('DELETE FROM device_codes WHERE expires<=?',(time.time(),))
            db.execute('INSERT INTO device_codes(code,user_code,edition,public_key,name,expires,hardware_hash) VALUES(?,?,?,?,?,?,?)',
                       (digest(raw),user_code,data.edition,data.public_key,data.name,time.time()+600,data.hardware_hash))
        return {'device_code':raw,'user_code':user_code,'verification_uri':settings.origin+'/account?view=activate',
                'expires_in':600,'interval':5,'edition':data.edition}

    @app.get('/api/licenses/pending/{user_code}')
    def pending(user_code:str,request:Request):
        account(request); ready();rate(request,'activation-preview',20)
        if not re.fullmatch(r'[A-Z0-9]{4}-[A-Z0-9]{4}',user_code):raise HTTPException(404,'Invalid activation code.')
        row=store.one('SELECT name,edition,expires FROM device_codes WHERE user_code=? AND expires>? AND consumed=0',(user_code,time.time()))
        if not row:raise HTTPException(404,'This activation code expired or was used.')
        return row

    @app.post('/api/licenses/approve')
    async def approve(request:Request):
        ready();user=account(request,mutation=True);rate(request,'approve',10);data=await body(request,Approve)
        with store.connect(immediate=True) as db:
            row=db.execute('SELECT * FROM device_codes WHERE user_code=? AND expires>? AND consumed=0',(data.user_code,time.time())).fetchone()
            if not row:raise HTTPException(404,'This activation code expired or was used.')
            if row['user_id'] and row['user_id']!=user['user_id']:raise HTTPException(409,'This code has already been approved.')
            if not db.execute("SELECT id FROM orders WHERE user_id=? AND state='paid' AND starts<=? AND ends>? LIMIT 1",(user['user_id'],time.time(),time.time())).fetchone():raise HTTPException(402,'Subscribe to Storylens before activating it.')
            computer(db,user['user_id'],row['public_key'],row['hardware_hash'])
            db.execute('UPDATE device_codes SET user_id=? WHERE code=?',(user['user_id'],row['code']))
        return {'ok':True}

    @app.post('/api/licenses/poll')
    async def poll(request:Request):
        ready();rate(request,'device-poll',60);data=await body(request,Poll)
        with store.connect(immediate=True) as db:
            code=db.execute('SELECT * FROM device_codes WHERE code=? AND expires>? AND consumed=0',(digest(data.device_code),time.time())).fetchone()
            if not code:raise HTTPException(410,'This activation code expired or was used.')
            proof(code['public_key'],data.signature,'activate:'+data.device_code)
            if not code['user_id']:return {'status':'pending'}
            if not db.execute("SELECT id FROM orders WHERE user_id=? AND state='paid' AND starts<=? AND ends>? LIMIT 1",(code['user_id'],time.time(),time.time())).fetchone():raise HTTPException(402,'An active subscription is required.')
            computer(db,code['user_id'],code['public_key'],code['hardware_hash'],True)
            device=db.execute('SELECT * FROM devices WHERE user_id=? AND edition=? AND public_key=?',
                              (code['user_id'],code['edition'],code['public_key'])).fetchone()
            if not device or device['revoked']:
                count=db.execute('SELECT COUNT(*) FROM devices WHERE user_id=? AND edition=? AND revoked=0',(code['user_id'],code['edition'])).fetchone()[0]
                if count>=1:raise HTTPException(409,'This subscription is already registered to one computer.')
            credential=token(); device_id=device['id'] if device else uuid.uuid4().hex
            db.execute('INSERT INTO devices(id,user_id,edition,public_key,name,credential,created,hardware_hash) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET credential=excluded.credential,name=excluded.name,hardware_hash=excluded.hardware_hash,revoked=0',
                       (device_id,code['user_id'],code['edition'],code['public_key'],code['name'],digest(credential),time.time(),code['hardware_hash']))
            db.execute('INSERT INTO device_bindings(user_id,edition,device_id) VALUES(?,?,?) ON CONFLICT(user_id,edition) DO UPDATE SET device_id=excluded.device_id,release_after=0',
                       (code['user_id'],code['edition'],device_id))
            db.execute('UPDATE device_codes SET consumed=1 WHERE code=?',(code['code'],))
        device=store.one('SELECT * FROM devices WHERE id=?',(device_id,))
        return {'status':'approved','device_id':device_id,'credential':credential,**lease(device)}

    @app.post('/api/licenses/refresh')
    async def refresh(request:Request):
        ready();rate(request,'license-refresh',1200);data=await body(request,Refresh)
        if not store.rate('refresh-device:'+data.device_id,12,60):raise HTTPException(429,'Too many license refreshes for this computer.')
        if abs(time.time()-data.timestamp)>300:raise HTTPException(403,'Check your computer clock and retry activation.')
        with store.connect(immediate=True) as db:
            device=db.execute('SELECT * FROM devices WHERE id=? AND revoked=0',(data.device_id,)).fetchone()
            if not device or not secrets.compare_digest(device['credential'],digest(data.credential)):raise HTTPException(403,'This device is deactivated. Sign in to activate it again.')
            binding=db.execute('SELECT device_id FROM device_bindings WHERE user_id=? AND edition=?',(device['user_id'],device['edition'])).fetchone()
            if not binding or binding['device_id']!=device['id'] or device['hardware_hash']!=data.hardware_hash:
                raise HTTPException(403,'This license belongs to a different computer.')
            proof(device['public_key'],data.signature,f'refresh:{data.device_id}:{data.nonce}:{data.timestamp}:{data.hardware_hash}')
            db.execute('DELETE FROM license_nonces WHERE expires<=?',(time.time(),))
            if db.execute('SELECT nonce FROM license_nonces WHERE device_id=? AND nonce=?',(data.device_id,data.nonce)).fetchone():raise HTTPException(409,'This license request was already used.')
            db.execute('INSERT INTO license_nonces VALUES(?,?,?)',(data.device_id,data.nonce,time.time()+600))
        return lease(dict(device))

    @app.get('/api/licenses/devices')
    def devices(request:Request):
        user=account(request)
        return store.all('SELECT id,name,edition,created FROM devices WHERE user_id=? AND revoked=0',(user['user_id'],))

    @app.delete('/api/licenses/devices/{device_id}')
    def revoke(device_id:str,request:Request):
        user=account(request,mutation=True)
        if not store.one('SELECT id FROM devices WHERE id=? AND user_id=?',(device_id,user['user_id'])):raise HTTPException(404,'This device is unavailable.')
        store.execute('UPDATE devices SET revoked=1 WHERE id=? AND user_id=?',(device_id,user['user_id']))
        store.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(uuid.uuid4().hex,user['user_id'],'device.deactivated',device_id,time.time()))
        return {'ok':True,'replacement_requires_support':True,'old_lease_expires_within_seconds':300}
