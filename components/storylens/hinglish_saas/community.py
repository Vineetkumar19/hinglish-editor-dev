"""Account-owned reviews, private owner metrics and signed local usage events."""
import json
import re
import secrets
import time
import uuid
from fastapi import HTTPException,Request
from pydantic import Field
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from hinglish_license.crypto import decode
from .config import EDIT_TOOLS
from .security import digest


def mount_community(app,settings,store,account,body,Input,rate):
    class Review(Input):
        display_name:str=Field(min_length=2,max_length=60)
        rating:int=Field(ge=1,le=5,strict=True)
        title:str=Field(min_length=3,max_length=120)
        body:str=Field(min_length=10,max_length=3000)
    class Moderate(Input):
        status:str=Field(pattern='^(published|hidden)$')
    class Usage(Input):
        id:str=Field(pattern=r'^[a-f0-9]{32}$')
        device_id:str=Field(pattern=r'^[a-f0-9]{32}$')
        credential:str=Field(min_length=32,max_length=100)
        timestamp:int
        tool:str=Field(max_length=30)
        outcome:str=Field(pattern='^(complete|failed|cancelled)$')
        duration:float=Field(ge=0,le=86400,allow_inf_nan=False)
        app_version:str=Field(pattern=r'^[A-Za-z0-9._-]{1,30}$')
        signature:str=Field(min_length=86,max_length=88)

    def text(value):
        value=value.strip()
        if not value or any(ord(c)<32 and c not in '\n\t' for c in value):raise HTTPException(422,'Use plain text without control characters.')
        return value

    def page(request):
        try:offset=max(0,int(request.query_params.get('offset','0')));limit=min(50,max(1,int(request.query_params.get('limit','10'))))
        except ValueError:raise HTTPException(422,'Invalid page.')
        if offset>100000:raise HTTPException(422,'Page is out of range.')
        return offset,limit

    @app.get('/api/reviews')
    def reviews(request:Request):
        offset,limit=page(request)
        summary=store.one("SELECT COUNT(*) AS count,AVG(rating) AS average FROM reviews WHERE status='published'")
        histogram=store.all("SELECT rating,COUNT(*) AS count FROM reviews WHERE status='published' GROUP BY rating")
        rows=store.all("SELECT r.id,r.display_name,r.rating,r.title,r.body,r.updated,CASE WHEN EXISTS(SELECT 1 FROM orders o WHERE o.user_id=r.user_id AND o.state='paid' AND o.payment_id IS NOT NULL) THEN 1 ELSE 0 END AS verified_customer FROM reviews r WHERE r.status='published' ORDER BY r.updated DESC,r.id LIMIT ? OFFSET ?",(limit,offset))
        return {'count':summary['count'],'average':round(float(summary['average']),2) if summary['average'] is not None else None,
            'histogram':histogram,'items':rows,'offset':offset,'limit':limit}

    @app.get('/api/reviews/mine')
    def mine(request:Request):
        user=account(request)
        return {'review':store.one('SELECT id,display_name,rating,title,body,status,updated FROM reviews WHERE user_id=?',(user['user_id'],))}

    @app.post('/api/reviews/mine')
    async def write(request:Request):
        user=account(request,mutation=True)
        if not user['verified']:raise HTTPException(403,'Verify your email before reviewing Storylens.')
        if not store.rate('review-write:'+user['user_id'],6,3600):raise HTTPException(429,'Please wait before editing your review again.')
        data=await body(request,Review);name=text(data.display_name);title=text(data.title);content=text(data.body)
        if '\n' in name or '\n' in title:raise HTTPException(422,'Keep your name and title on one line.')
        if len(name)<2 or len(title)<3 or len(content)<10:raise HTTPException(422,'Please add a little more detail.')
        now=time.time()
        with store.connect(immediate=True) as db:
            old=db.execute('SELECT id FROM reviews WHERE user_id=?',(user['user_id'],)).fetchone()
            review_id=old['id'] if old else uuid.uuid4().hex
            db.execute("INSERT INTO reviews(id,user_id,display_name,rating,title,body,status,created,updated) VALUES(?,?,?,?,?,?,'pending',?,?) ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,rating=excluded.rating,title=excluded.title,body=excluded.body,status='pending',updated=excluded.updated",
                (review_id,user['user_id'],name,data.rating,title,content,now,now))
        return {'id':review_id,'status':'pending','message':'Your review was saved and is awaiting moderation. Both positive and critical reviews follow the same process.'}

    @app.delete('/api/reviews/mine')
    def remove(request:Request):
        user=account(request,mutation=True);store.execute('DELETE FROM reviews WHERE user_id=?',(user['user_id'],));return {'ok':True}

    @app.get('/api/admin/overview')
    def overview(request:Request):
        app.state.support_operator(request);now=time.time()
        counts={}
        for name,query,args in (
            ('users','SELECT COUNT(*) AS n FROM users',()),
            ('verified_users','SELECT COUNT(*) AS n FROM users WHERE verified=1',()),
            ('new_users_30d','SELECT COUNT(*) AS n FROM users WHERE created>?',(now-30*86400,)),
            ('subscribers',"SELECT COUNT(DISTINCT user_id) AS n FROM orders WHERE state='paid' AND starts<=? AND ends>?",(now,now)),
            ('signed_in_accounts','SELECT COUNT(DISTINCT user_id) AS n FROM sessions WHERE expires>?',(now,)),
            ('registered_computers','SELECT COUNT(DISTINCT user_id) AS n FROM devices WHERE revoked=0',()),
            ('open_tickets',"SELECT COUNT(*) AS n FROM support_tickets WHERE status<>'resolved'",()),
            ('pending_reviews',"SELECT COUNT(*) AS n FROM reviews WHERE status='pending'",()),
            ('revenue_paise',"SELECT COALESCE(SUM(amount),0) AS n FROM orders WHERE state='paid'",()),
            ('refunds',"SELECT COUNT(*) AS n FROM orders WHERE state='revoked'",())):
            counts[name]=store.one(query,args)['n']
        usage=store.all('SELECT tool,outcome,COUNT(*) AS count,SUM(duration) AS duration FROM usage_events WHERE created>? GROUP BY tool,outcome ORDER BY count DESC',(now-30*86400,))
        jobs=store.all('SELECT tool,state,COUNT(*) AS count FROM jobs GROUP BY tool,state')
        return {'counts':counts,'usage_30d':usage,'server_jobs':jobs,'database':store.backend,
            'usage_note':'Local tool activity appears only when customers enable usage reporting. No video, script, filenames or captions are collected.',
            'capacity':'Designed and tested for a small account service; AI rendering uses each customer computer.',
            'generated_at':now}

    @app.get('/api/admin/users')
    def users(request:Request):
        app.state.support_operator(request);offset,limit=page(request)
        search=request.query_params.get('search','').strip()[:100]
        where=' WHERE LOWER(u.email) LIKE ?' if search else ''
        args=('%'+search.lower()+'%',) if search else ()
        total=store.one('SELECT COUNT(*) AS n FROM users u'+where,args)['n']
        rows=store.all("SELECT u.id,u.email,u.verified,u.created,(SELECT MAX(o.ends) FROM orders o WHERE o.user_id=u.id AND o.state='paid' AND o.starts<=? AND o.ends>?) AS subscription_expires,(SELECT MAX(e.created) FROM usage_events e WHERE e.user_id=u.id) AS last_usage FROM users u"+where+' ORDER BY u.created DESC,u.id LIMIT ? OFFSET ?',
                       (time.time(),time.time(),*args,limit,offset))
        return {'count':total,'items':rows,'offset':offset,'limit':limit}

    @app.get('/api/admin/reviews')
    def review_queue(request:Request):
        app.state.support_operator(request);offset,limit=page(request)
        return {'items':store.all('SELECT r.*,u.email FROM reviews r JOIN users u ON u.id=r.user_id ORDER BY r.updated DESC,r.id LIMIT ? OFFSET ?',(limit,offset))}

    @app.post('/api/admin/reviews/{review_id}')
    async def moderation(review_id:str,request:Request):
        operator=app.state.support_operator(request,True);data=await body(request,Moderate)
        with store.connect(immediate=True) as db:
            if not db.execute('SELECT id FROM reviews WHERE id=?',(review_id,)).fetchone():raise HTTPException(404,'This review is unavailable.')
            db.execute('UPDATE reviews SET status=? WHERE id=?',(data.status,review_id))
            db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(uuid.uuid4().hex,operator['user_id'],'review.'+data.status,review_id,time.time()))
        return {'ok':True}

    @app.post('/api/usage')
    async def usage(request:Request):
        rate(request,'usage',120);data=await body(request,Usage)
        if data.tool not in EDIT_TOOLS or abs(time.time()-data.timestamp)>300:raise HTTPException(422,'Invalid usage event.')
        device=store.one('SELECT * FROM devices WHERE id=? AND revoked=0',(data.device_id,))
        if not device or not secrets.compare_digest(device['credential'],digest(data.credential)):raise HTTPException(403,'Invalid device.')
        binding=store.one('SELECT * FROM computer_bindings WHERE user_id=?',(device['user_id'],))
        if not binding or (binding['public_key'],binding['hardware_hash'])!=(device['public_key'],device['hardware_hash']):raise HTTPException(403,'This computer is not registered.')
        if not store.entitlement(device['user_id'])['active']:raise HTTPException(402,'An active subscription is required.')
        signed=data.model_dump(exclude={'signature','credential'})
        try:Ed25519PublicKey.from_public_bytes(decode(device['public_key'],32)).verify(decode(data.signature,64),('usage:'+json.dumps(signed,sort_keys=True,separators=(',',':'))).encode())
        except Exception:raise HTTPException(403,'Invalid device proof.')
        store.execute('INSERT OR IGNORE INTO usage_events VALUES(?,?,?,?,?,?,?,?)',(data.id,device['user_id'],device['id'],data.tool,data.outcome,data.duration,data.app_version,time.time()))
        return {'ok':True}
