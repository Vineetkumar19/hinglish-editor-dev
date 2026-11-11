"""Private customer tickets, owner inbox and audited device replacement."""
import base64
import hashlib
import hmac
import re
import struct
import time
import uuid
from fastapi import HTTPException,Request
from pydantic import Field


def totp(secret,stamp=None):
    key=base64.b32decode(secret.upper()+'='*((-len(secret))%8),casefold=True)
    message=struct.pack('>Q',int((time.time() if stamp is None else stamp)//30))
    signature=hmac.new(key,message,hashlib.sha1).digest();offset=signature[-1]&15
    return str((struct.unpack('>I',signature[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)


def enqueue(db,recipient,subject,body):
    now=time.time()
    db.execute('INSERT INTO support_outbox(id,recipient,subject,body,available,created) VALUES(?,?,?,?,?,?)',
               (uuid.uuid4().hex,recipient,subject,body,now,now))


def mount_support(app,settings,store,account,body,Input,rate):
    class New(Input):
        subject: str=Field(min_length=5,max_length=140)
        category: str=Field(pattern='^(billing|activation|editing|installation|other)$')
        message: str=Field(min_length=10,max_length=6000)

    class Reply(Input):
        message: str=Field(min_length=1,max_length=6000)

    class Status(Input):
        status: str=Field(pattern='^(open|waiting|resolved)$')

    class Reset(Input):
        edition: str=Field(pattern='^(desktop|plugins)$')
        reason: str=Field(min_length=20,max_length=1000)

    def verified(request,mutation=False):
        user=account(request,mutation=mutation)
        if not user['verified']:raise HTTPException(403,'Verify your email before opening a private support ticket. You can also email '+settings.support_email+'.')
        return user

    def operator(request,mutation=False):
        user=verified(request,mutation);rate(request,'support-operator',30)
        if user['email'] not in settings.support_admin_emails:raise HTTPException(403,'Support operator access required.')
        if not settings.support_totp_secret:raise HTTPException(503,'Configure support operator two-step verification before opening the inbox.')
        code=request.headers.get('x-support-code','')
        if not re.fullmatch(r'\d{6}',code) or not any(hmac.compare_digest(code,totp(settings.support_totp_secret,time.time()+offset)) for offset in (-30,0,30)):
            if not store.rate('support-otp:'+user['user_id'],5,300):raise HTTPException(429,'Too many verification attempts. Wait five minutes.')
            raise HTTPException(403,'Enter the current support authenticator code.')
        return user

    app.state.support_operator=operator

    def ticket(ticket_id,user,staff=False):
        row=store.one('SELECT t.*,u.email FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE t.id=?'+('' if staff else ' AND t.user_id=?'),
                      (ticket_id,) if staff else (ticket_id,user['user_id']))
        if not row:raise HTTPException(404,'This ticket is unavailable.')
        return row

    def messages(ticket_id):
        return store.all('SELECT id,staff,body,created FROM support_messages WHERE ticket_id=? ORDER BY created,id',(ticket_id,))

    def text(value):
        value=value.strip()
        if not value or any(ord(c)<32 and c not in '\n\t' for c in value):raise HTTPException(422,'Use plain text without control characters.')
        return value

    @app.get('/api/support/config')
    def support_config():
        return {'email':settings.support_email,'tickets_enabled':True,'email_notifications_connected':bool(settings.smtp_host and settings.mail_from),
                'one_computer':True,'device_replacement':'Support review required','phone_support':False,'whatsapp_support':False}

    @app.get('/api/support/tickets')
    def list_tickets(request:Request):
        user=account(request)
        return store.all('SELECT id,subject,category,status,created,updated FROM support_tickets WHERE user_id=? ORDER BY updated DESC LIMIT 100',(user['user_id'],))

    @app.post('/api/support/tickets')
    async def create_ticket(request:Request):
        user=verified(request,True);rate(request,'support-create',8,3600);data=await body(request,New)
        subject=text(data.subject);message=text(data.message)
        if '\n' in subject or '\r' in subject:raise HTTPException(422,'Put the subject on one line.')
        if not store.rate('support-create-user:'+user['user_id'],5,3600):raise HTTPException(429,'You have opened several tickets. Reply to an existing ticket instead.')
        now=time.time();ticket_id='HE-'+uuid.uuid4().hex[:16].upper()
        with store.connect(immediate=True) as db:
            count=db.execute("SELECT COUNT(*) FROM support_tickets WHERE user_id=? AND status!='resolved'",(user['user_id'],)).fetchone()[0]
            if count>=5:raise HTTPException(409,'Reply to one of your existing open tickets before opening another.')
            db.execute('INSERT INTO support_tickets(id,user_id,subject,category,created,updated) VALUES(?,?,?,?,?,?)',(ticket_id,user['user_id'],subject,data.category,now,now))
            db.execute('INSERT INTO support_messages VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,ticket_id,user['user_id'],0,message,now))
            enqueue(db,settings.support_email,'['+ticket_id+'] '+subject,'Customer: '+user['email']+'\nCategory: '+data.category+'\n\n'+message+'\n\nOpen the private inbox to reply: '+settings.origin+'/support/inbox\nTicket: '+ticket_id+'\nNever request a password or payment-card details.')
            enqueue(db,user['email'],'['+ticket_id+'] Support request received','We received your request: '+subject+'\n\nYour ticket number is '+ticket_id+'.\nView replies: '+settings.origin+'/support\n\nDo not share passwords, API keys or card details in a ticket.')
        return {'id':ticket_id,'status':'open','message':'Your ticket was saved. You can read replies in Support.'}

    @app.get('/api/support/tickets/{ticket_id}')
    def read_ticket(ticket_id:str,request:Request):
        user=account(request);row=ticket(ticket_id,user)
        return {k:row[k] for k in ('id','subject','category','status','created','updated')}|{'messages':messages(ticket_id)}

    @app.post('/api/support/tickets/{ticket_id}/messages')
    async def customer_reply(ticket_id:str,request:Request):
        user=verified(request,True);rate(request,'support-reply',15);row=ticket(ticket_id,user);data=await body(request,Reply);message=text(data.message)
        if not store.rate('support-reply-user:'+user['user_id'],30,3600):raise HTTPException(429,'Too many support replies. Try again later.')
        now=time.time()
        with store.connect(immediate=True) as db:
            db.execute('INSERT INTO support_messages VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,ticket_id,user['user_id'],0,message,now))
            db.execute("UPDATE support_tickets SET status='open',updated=? WHERE id=?",(now,ticket_id))
            enqueue(db,settings.support_email,'['+ticket_id+'] Customer reply',message+'\n\nReply in the private inbox: '+settings.origin+'/support/inbox\nTicket: '+ticket_id)
        return {'ok':True}

    @app.get('/api/support/admin/tickets')
    def inbox(request:Request):
        operator(request)
        return store.all('SELECT t.*,u.email FROM support_tickets t JOIN users u ON u.id=t.user_id ORDER BY t.updated DESC LIMIT 200')

    @app.get('/api/support/admin/mail-status')
    def mail_status(request:Request):
        operator(request)
        return {'connected':bool(settings.smtp_host and settings.mail_from),
                'queue':store.all('SELECT state,COUNT(*) AS count FROM support_outbox GROUP BY state')}

    @app.post('/api/support/admin/retry-mail')
    def retry_mail(request:Request):
        user=operator(request,True);rate(request,'support-mail-retry',1,60)
        with store.connect(immediate=True) as db:
            db.execute("UPDATE support_outbox SET state='pending',attempts=0,available=?,lease_until=0 WHERE state='failed'",(time.time(),))
            db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(uuid.uuid4().hex,user['user_id'],'support.mail-retry','failed-outbox',time.time()))
        return {'ok':True}

    @app.get('/api/support/admin/tickets/{ticket_id}')
    def staff_read(ticket_id:str,request:Request):
        user=operator(request);row=ticket(ticket_id,user,True)
        return dict(row)|{'messages':messages(ticket_id),'devices':store.all('SELECT id,name,edition,revoked,created FROM devices WHERE user_id=?',(row['user_id'],))}

    @app.post('/api/support/admin/tickets/{ticket_id}/messages')
    async def staff_reply(ticket_id:str,request:Request):
        user=operator(request,True);rate(request,'staff-reply',20);row=ticket(ticket_id,user,True);data=await body(request,Reply);message=text(data.message);now=time.time()
        with store.connect(immediate=True) as db:
            db.execute('INSERT INTO support_messages VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,ticket_id,user['user_id'],1,message,now))
            db.execute("UPDATE support_tickets SET status='waiting',updated=? WHERE id=?",(now,ticket_id))
            db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(uuid.uuid4().hex,user['user_id'],'support.reply',ticket_id,now))
            enqueue(db,row['email'],'['+ticket_id+'] Support replied',message+'\n\nReply securely in your ticket: '+settings.origin+'/support\nTicket: '+ticket_id)
        return {'ok':True}

    @app.post('/api/support/admin/tickets/{ticket_id}/status')
    async def update_status(ticket_id:str,request:Request):
        user=operator(request,True);ticket(ticket_id,user,True);data=await body(request,Status)
        with store.connect(immediate=True) as db:
            db.execute('UPDATE support_tickets SET status=?,updated=? WHERE id=?',(data.status,time.time(),ticket_id))
            db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(uuid.uuid4().hex,user['user_id'],'support.'+data.status,ticket_id,time.time()))
        return {'ok':True}

    @app.post('/api/support/admin/tickets/{ticket_id}/device-replacement')
    async def replacement(ticket_id:str,request:Request):
        user=operator(request,True);row=ticket(ticket_id,user,True);data=await body(request,Reset);reason=text(data.reason)
        if row['category']!='activation':raise HTTPException(409,'Use an activation ticket from the subscription owner for a device replacement.')
        now=time.time()
        with store.connect(immediate=True) as db:
            binding=db.execute('SELECT * FROM device_bindings WHERE user_id=? AND edition=?',(row['user_id'],data.edition)).fetchone()
            if not binding or not binding['device_id']:raise HTTPException(409,'There is no registered computer to replace.')
            device=db.execute('SELECT MAX(last_lease) AS last_lease FROM devices WHERE user_id=?',(row['user_id'],)).fetchone()
            # Older versions issued 24-hour offline grants. Conservatively drain
            # that window for legacy devices before granting a replacement.
            old=db.execute('SELECT hardware_hash FROM devices WHERE id=?',(binding['device_id'],)).fetchone()
            release_after=max(now,(device['last_lease'] if device else now))+5
            if old and not old['hardware_hash']:release_after=max(release_after,now+86400)
            db.execute('UPDATE devices SET revoked=1 WHERE user_id=?',(row['user_id'],))
            db.execute('UPDATE device_bindings SET device_id=NULL,release_after=? WHERE user_id=?',(release_after,row['user_id']))
            db.execute('UPDATE computer_bindings SET public_key=NULL,hardware_hash=NULL,release_after=? WHERE user_id=?',(release_after,row['user_id']))
            db.execute('DELETE FROM device_codes WHERE user_id=?',(row['user_id'],))
            db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(uuid.uuid4().hex,user['user_id'],'device.replacement:'+data.edition+':'+reason,ticket_id,now))
        return {'ok':True,'activate_after':release_after,'message':'The old computer is revoked. The new computer can activate after the previous license window ends.'}
