"""Small subscription API. Rendering is performed by a separate private worker."""
import asyncio
import json
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager,suppress
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .billing import Billing, BillingError
from .config import EDIT_TOOLS, EDITIONS, PLANS, Settings
from .mail import send_link
from .security import PASSWORDS, digest, token, verify_password
from .store import Store
from sqlalchemy.exc import TimeoutError as PoolTimeout
from pymysql.err import OperationalError as MySQLOperationalError

SITE=Path(__file__).resolve().parents[1]/'saas_site'/'dist'
COOKIE='he_session'


class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Credentials(Input):
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=12,max_length=128)


class Order(Input):
    plan: str=Field(pattern='^(monthly|annual)$')
    edition: str=Field(default='bundle',pattern='^(bundle|desktop|plugins)$')


class Payment(Input):
    order_id: str=Field(pattern=r'^order_[A-Za-z0-9]{1,80}$')
    payment_id: str=Field(pattern=r'^pay_[A-Za-z0-9]{1,80}$')
    signature: str=Field(pattern=r'^[a-f0-9]{64}$')


class Email(Input):
    email: str=Field(min_length=3,max_length=254)


class Link(Input):
    token: str=Field(min_length=32,max_length=100)
    password: str=Field(default='',max_length=128)


class Edit(Input):
    tool: str
    upload_ids: list[str]=Field(default_factory=list,max_length=10)
    script: str=Field(default='',max_length=20000)
    options: dict=Field(default_factory=dict)


def email_address(value):
    value=value.strip().lower()
    if not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+',value):raise HTTPException(422,'Enter a valid email address.')
    return value


async def body(request, model):
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>65536:raise HTTPException(413,'This request is too large.')
    try:return model.model_validate_json(data)
    except (ValueError,ValidationError):raise HTTPException(422,'Check the supplied fields and try again.')


def create_app(settings=None,provider=None):
    settings=settings or Settings.from_env();store=Store(settings.data_dir,settings.database_url);billing=Billing(store,settings,provider)
    @asynccontextmanager
    async def lifespan(application):
        async def deliver():
            from .support_mailer import run_once
            while True:
                try:worked=await asyncio.to_thread(run_once,settings,store=store)
                except Exception:worked=False
                await asyncio.sleep(1 if worked else 10)
        task=asyncio.create_task(deliver()) if settings.smtp_host and settings.mail_from else None
        try:yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):await task
    app=FastAPI(title='Storylens subscription gateway',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.settings=settings;app.state.store=store;app.state.billing=billing
    def site_page(name):
        if settings.qa_mode:
            html=(SITE/name).read_text(encoding='utf-8').replace('<body>','<body><div class="qa-notice">ISOLATED TEST DATA · Accounts, subscriptions, payments and reviews on this page are fixtures, not real customers or transactions.</div>',1)
            return HTMLResponse(html)
        return FileResponse(SITE/name)
    auth_slots=asyncio.Semaphore(2)
    async def password_work(function,*args):
        async with auth_slots:return await asyncio.to_thread(function,*args)

    @app.middleware('http')
    async def boundary(request,call_next):
        host=urlparse(settings.origin).netloc.lower()
        if request.headers.get('host','').lower()!=host:
            return JSONResponse({'detail':'This host is not allowed.'},status_code=400)
        machine_routes=('/api/billing/webhook','/api/licenses/device-code','/api/licenses/poll','/api/licenses/refresh','/api/usage')
        if request.method in ('POST','PUT','PATCH','DELETE') and request.url.path not in machine_routes:
            if request.headers.get('origin')!=settings.origin:
                return JSONResponse({'detail':'This request did not come from your editor.'},status_code=403)
        try:
            length=int(request.headers.get('content-length','0'))
        except ValueError:return JSONResponse({'detail':'Invalid request size.'},status_code=400)
        limit=settings.max_upload_bytes if request.url.path=='/api/uploads' else 65536
        if length<0 or (request.method!='GET' and length>limit):return JSONResponse({'detail':'This request is too large.'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' https://checkout.razorpay.com; style-src 'self'; img-src 'self' data: https://*.razorpay.com; font-src 'self'; media-src 'self'; connect-src 'self' https://*.razorpay.com; frame-src https://*.razorpay.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        response.headers['Cache-Control']='public,max-age=3600' if settings.production and request.url.path.startswith('/assets/') else 'no-store'
        if settings.production:response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response

    @app.exception_handler(BillingError)
    async def billing_error(request,error):return JSONResponse({'detail':str(error)},status_code=400)

    @app.exception_handler(PoolTimeout)
    @app.exception_handler(MySQLOperationalError)
    async def database_busy(request,error):
        return JSONResponse({'detail':'The account service is temporarily busy. Please retry shortly.'},status_code=503,headers={'Retry-After':'5'})

    def rate(request,kind,limit=10,seconds=60):
        # Client IP is the ASGI peer. Never trust arbitrary X-Forwarded-For.
        ip=request.client.host if request.client else 'unknown'
        if not store.rate(kind+':'+ip,limit,seconds):raise HTTPException(429,'Too many attempts. Wait a moment and retry.')

    def account(request,paid=False,mutation=False):
        raw=request.cookies.get(COOKIE,'')
        session=store.one('SELECT s.*,u.email,u.verified FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(digest(raw),time.time())) if raw else None
        if not session:raise HTTPException(401,'Sign in to continue.')
        if mutation and not secrets.compare_digest(request.headers.get('x-csrf-token','').encode(),session['csrf'].encode()):raise HTTPException(403,'Your session changed. Refresh the page and retry.')
        if paid and not store.entitlement(session['user_id'])['active']:raise HTTPException(402,'An active subscription is required.')
        return session

    def session_response(user_id):
        raw=token();csrf=token();now=time.time()
        with store.connect(immediate=True) as db:
            db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(raw),user_id,csrf,now+settings.session_seconds))
            # One active website login. Device activation is independently bound
            # to the desktop; sharing an account password does not move it.
            db.execute('DELETE FROM sessions WHERE user_id=? AND token<>?',(user_id,digest(raw)))
        response=JSONResponse({'csrf':csrf,'subscription':store.entitlement(user_id)})
        response.set_cookie(COOKIE,raw,max_age=settings.session_seconds,httponly=True,secure=settings.production,samesite='strict',path='/')
        return response

    def mail_token(user,kind):
        raw=token();now=time.time()
        with store.connect(immediate=True) as db:
            db.execute('DELETE FROM tokens WHERE user_id=? AND kind=?',(user['id'],kind))
            db.execute('INSERT INTO tokens VALUES(?,?,?,?)',(digest(raw),user['id'],kind,now+1800))
        try:return send_link(settings,user['email'],kind,raw)
        except Exception:
            store.execute('DELETE FROM tokens WHERE hash=?',(digest(raw),))
            return False

    @app.get('/api/config')
    def configuration():
        return {'brand':'Storylens','plans':PLANS,'editions':EDITIONS,'activation_enabled':bool(settings.license_private_key),
                'device_limit':settings.device_limit,'checkout_enabled':bool(settings.sales_enabled and settings.key_id and settings.key_secret),
                'test_payments':settings.key_id.startswith('rzp_test_'),'worker_enabled':settings.worker_enabled,
                'enabled_tools':list(settings.enabled_tools),'email_enabled':bool(settings.smtp_host),
                'support_email':settings.support_email,'limits':{'upload_bytes':settings.max_upload_bytes,'storage_bytes':settings.storage_bytes,'jobs_month':settings.max_jobs_month},
                'billing_type':'fixed-term; manual renewal','publishing_connected':False}

    @app.get('/api/health')
    def health():return {'status':'ok'}

    @app.post('/api/auth/register')
    async def register(request:Request):
        rate(request,'register',5,3600);data=await body(request,Credentials);email=email_address(data.email)
        if store.one('SELECT id FROM users WHERE email=?',(email,)):
            raise HTTPException(400,'Account could not be created. Sign in or reset your password.')
        user_id=uuid.uuid4().hex
        encoded=await password_work(PASSWORDS.hash,data.password)
        try:store.execute('INSERT INTO users VALUES(?,?,?,?,?)',(user_id,email,encoded,0,time.time()))
        except sqlite3.IntegrityError:raise HTTPException(400,'Account could not be created. Sign in or reset your password.')
        if settings.smtp_host:await asyncio.to_thread(mail_token,{'id':user_id,'email':email},'verify')
        return session_response(user_id)

    @app.post('/api/auth/login')
    async def login(request:Request):
        rate(request,'login',60);data=await body(request,Credentials);email=email_address(data.email)
        if not store.rate('login-email:'+digest(email),20,3600):raise HTTPException(429,'Too many attempts. Try again later.')
        user=store.one('SELECT * FROM users WHERE email=?',(email,))
        matched=await password_work(verify_password,user['password'] if user else None,data.password)
        if not matched or not user:raise HTTPException(401,'Email or password is incorrect.')
        return session_response(user['id'])

    @app.get('/api/me')
    def me(request:Request):
        user=account(request)
        return {'email':user['email'],'verified':bool(user['verified']),'csrf':user['csrf'],'subscription':store.entitlement(user['user_id']),
                'is_operator':bool(user['verified'] and user['email'] in settings.support_admin_emails),
                'editions':{e:store.entitlement(user['user_id'],edition=e) for e in EDITIONS}}

    @app.post('/api/auth/logout')
    def logout(request:Request):
        user=account(request,mutation=True);store.execute('DELETE FROM sessions WHERE token=?',(user['token'],))
        response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/',secure=settings.production,samesite='strict');return response

    @app.post('/api/auth/email')
    async def email_link(request:Request):
        rate(request,'email',4,3600);user=account(request,mutation=True)
        if not settings.smtp_host:raise HTTPException(503,'Email delivery is not connected yet.')
        await asyncio.to_thread(mail_token,{'id':user['user_id'],'email':user['email']},'verify')
        return {'message':'Check your inbox for the verification link.'}

    @app.post('/api/auth/forgot')
    async def forgot(request:Request):
        rate(request,'forgot',4,3600);data=await body(request,Email);email=email_address(data.email)
        if not settings.smtp_host:raise HTTPException(503,'Password recovery is not connected yet.')
        user=store.one('SELECT id,email FROM users WHERE email=?',(email,))
        if user:await asyncio.to_thread(mail_token,user,'reset')
        return {'message':'If this email has an account, a reset link will arrive shortly.'}

    async def consume_link(request,kind):
        rate(request,'link',10);data=await body(request,Link)
        if kind=='reset' and len(data.password)<12:raise HTTPException(422,'Use at least 12 characters for your password.')
        encoded=await password_work(PASSWORDS.hash,data.password) if kind=='reset' else None
        with store.connect(immediate=True) as db:
            link=db.execute('SELECT * FROM tokens WHERE hash=? AND kind=? AND expires>?',(digest(data.token),kind,time.time())).fetchone()
            if not link:raise HTTPException(400,'This link expired or has already been used.')
            if kind=='verify':db.execute('UPDATE users SET verified=1 WHERE id=?',(link['user_id'],))
            else:
                db.execute('UPDATE users SET password=? WHERE id=?',(encoded,link['user_id']))
                db.execute('DELETE FROM sessions WHERE user_id=?',(link['user_id'],))
            db.execute('DELETE FROM tokens WHERE hash=?',(digest(data.token),))
        return {'ok':True}

    @app.post('/api/auth/verify')
    async def verify(request:Request):return await consume_link(request,'verify')

    @app.post('/api/auth/reset')
    async def reset(request:Request):return await consume_link(request,'reset')

    @app.post('/api/billing/orders')
    async def order(request:Request):
        user=account(request,mutation=True);rate(request,'checkout',5);data=await body(request,Order)
        if not settings.sales_enabled:raise HTTPException(503,'Purchases open after payment, email and device activation are connected.')
        if not user['verified']:raise HTTPException(403,'Verify your email before purchasing.')
        return await asyncio.to_thread(billing.create,user['user_id'],data.plan,uuid.uuid4().hex,data.edition)

    @app.post('/api/billing/verify')
    async def verify_payment(request:Request):
        user=account(request,mutation=True);rate(request,'verify-payment',10);data=await body(request,Payment)
        return await asyncio.to_thread(billing.verify_checkout,user['user_id'],data.order_id,data.payment_id,data.signature)

    @app.post('/api/billing/webhook')
    async def webhook(request:Request):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>65536:raise HTTPException(413,'Webhook is too large.')
        try:await asyncio.to_thread(billing.webhook,bytes(raw),request.headers.get('x-razorpay-signature',''),request.headers.get('x-razorpay-event-id',''))
        except (ValueError,KeyError):raise HTTPException(400,'Webhook could not be verified.')
        return {'ok':True}

    @app.post('/api/uploads')
    async def upload(request:Request):
        user=account(request,paid=True,mutation=True);rate(request,'upload',10)
        if not settings.worker_enabled:raise HTTPException(503,'The rendering worker is not connected yet.')
        name=request.query_params.get('name','')
        if not name or len(name)>100 or any(c in name for c in '\\/:\x00\r\n') or Path(name).suffix.lower() not in ('.mp4','.mov','.mkv','.webm'):
            raise HTTPException(422,'Upload an MP4, MOV, MKV or WebM video with a simple filename.')
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:raise HTTPException(411,'A file size is required.')
        if not 0<length<=settings.max_upload_bytes:raise HTTPException(413,'The video exceeds the upload limit.')
        upload_id=uuid.uuid4().hex;folder=settings.data_dir/'uploads'/user['user_id'];folder.mkdir(parents=True,exist_ok=True)
        path=folder/(upload_id+Path(name).suffix.lower());partial=path.with_suffix('.partial')
        with store.connect(immediate=True) as db:
            used=db.execute('SELECT COALESCE(SUM(bytes),0) AS total FROM uploads WHERE user_id=?',(user['user_id'],)).fetchone()['total']
            if used+length>settings.storage_bytes:raise HTTPException(413,'Your upload storage is full. Delete an old upload first.')
            db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?)',(upload_id,user['user_id'],name,str(path),length,time.time()))
        try:
            total=0
            with partial.open('xb') as output:
                async for chunk in request.stream():
                    total+=len(chunk)
                    if total>length:raise HTTPException(413,'File size did not match the upload.')
                    output.write(chunk)
            if total!=length:raise HTTPException(400,'The upload ended early.')
            # Only inspect container magic at the public boundary. Untrusted
            # decoding belongs in the time-limited private media worker.
            with partial.open('rb') as probe:header=probe.read(64)
            iso=len(header)>=12 and header[4:8] in (b'ftyp',b'moov',b'mdat',b'wide',b'free')
            ebml=header.startswith(b'\x1aE\xdf\xa3')
            extension=Path(name).suffix.lower()
            if not ((iso and extension in ('.mp4','.mov')) or (ebml and extension in ('.mkv','.webm'))):
                raise HTTPException(415,'This file is not a supported video container.')
            partial.replace(path)
        except BaseException:
            partial.unlink(missing_ok=True);path.unlink(missing_ok=True);store.execute('DELETE FROM uploads WHERE id=?',(upload_id,));raise
        return {'id':upload_id,'name':name,'bytes':length}

    @app.get('/api/uploads')
    def list_uploads(request:Request):
        user=account(request,paid=True)
        return store.all('SELECT id,name,bytes,created FROM uploads WHERE user_id=? ORDER BY created DESC',(user['user_id'],))

    @app.delete('/api/uploads/{upload_id}')
    def delete_upload(upload_id:str,request:Request):
        user=account(request,paid=True,mutation=True)
        row=store.one('SELECT * FROM uploads WHERE id=? AND user_id=?',(upload_id,user['user_id']))
        if not row:raise HTTPException(404,'This upload is unavailable.')
        if store.one("SELECT id FROM jobs WHERE user_id=? AND state IN ('queued','running')",(user['user_id'],)):
            raise HTTPException(409,'Wait for your current edit before deleting uploads.')
        path=Path(row['path']).resolve()
        if not path.is_relative_to((settings.data_dir/'uploads'/user['user_id']).resolve()):raise HTTPException(404,'This upload is unavailable.')
        path.unlink(missing_ok=True);store.execute('DELETE FROM uploads WHERE id=?',(upload_id,));return {'ok':True}

    @app.post('/api/jobs')
    async def submit_job(request:Request):
        user=account(request,paid=True,mutation=True);rate(request,'edit',10);data=await body(request,Edit)
        if data.tool not in EDIT_TOOLS:raise HTTPException(422,'Choose a supported editing tool.')
        if not settings.worker_enabled or data.tool not in settings.enabled_tools:raise HTTPException(503,'This tool needs a configured rendering worker before it can run online.')
        allowed={'format':('source','instagram_vertical','youtube_horizontal'),'caption_style':('typography_1','typography_2','typography_3','typography_4','typography_5','flash_cut'),
                 'density':('low','medium','high'),'pacing':('natural','tight','relaxed'), 'zoom_style':('smooth','mixed','punch'),
                 'zoom_strength':('subtle','medium','strong'),'sound_style':('auto','cinematic','funny','chill','emotional')}
        if any(k not in allowed or v not in allowed[k] for k,v in data.options.items()):raise HTTPException(422,'One of the edit settings is unavailable.')
        if len(set(data.upload_ids))!=len(data.upload_ids):raise HTTPException(422,'Choose each upload once.')
        for upload_id in data.upload_ids:
            row=store.one('SELECT path FROM uploads WHERE id=? AND user_id=?',(upload_id,user['user_id']))
            if not row or not Path(row['path']).is_file():raise HTTPException(404,'One of your uploads is unavailable.')
        if not data.upload_ids and not (data.tool in ('motion','aiimage','aivideo') and data.script.strip()):raise HTTPException(422,'Upload your video first.')
        if data.tool=='script' and not data.script.strip():raise HTTPException(422,'Paste the script to arrange your clips.')
        now=time.time();job_id=uuid.uuid4().hex
        with store.connect(immediate=True) as db:
            if db.execute("SELECT id FROM jobs WHERE user_id=? AND state IN ('queued','running')",(user['user_id'],)).fetchone():raise HTTPException(409,'You already have an edit in progress.')
            count=db.execute('SELECT COUNT(*) FROM jobs WHERE user_id=? AND created>?',(user['user_id'],now-30*86400)).fetchone()[0]
            if count>=settings.max_jobs_month:raise HTTPException(429,'Your monthly processing allowance is used. Contact support for more capacity.')
            db.execute('INSERT INTO jobs(id,user_id,tool,payload,message,created,updated) VALUES(?,?,?,?,?,?,?)',(job_id,user['user_id'],data.tool,data.model_dump_json(),'Waiting for the rendering worker',now,now))
        return {'id':job_id,'state':'queued'}

    @app.get('/api/jobs')
    def jobs(request:Request):
        user=account(request,paid=True)
        rows=store.all('SELECT id,tool,state,message,created FROM jobs WHERE user_id=? ORDER BY created DESC LIMIT 50',(user['user_id'],))
        for row in rows:row['exports']=store.all('SELECT id,name FROM exports WHERE job_id=? AND user_id=?',(row['id'],user['user_id']))
        return rows

    @app.get('/api/jobs/{job_id}')
    def job(job_id:str,request:Request):
        user=account(request,paid=True)
        row=store.one('SELECT id,tool,state,message,created FROM jobs WHERE id=? AND user_id=?',(job_id,user['user_id']))
        if not row:raise HTTPException(404,'This edit is unavailable.')
        row['exports']=store.all('SELECT id,name FROM exports WHERE job_id=? AND user_id=?',(job_id,user['user_id']));return row

    @app.get('/api/exports/{export_id}')
    def download(export_id:str,request:Request):
        user=account(request,paid=True)
        row=store.one('SELECT * FROM exports WHERE id=? AND user_id=?',(export_id,user['user_id']))
        if not row:raise HTTPException(404,'This export is unavailable.')
        path=Path(row['path']).resolve()
        if not path.is_relative_to((settings.data_dir/'work'/user['user_id']).resolve()) or not path.is_file():raise HTTPException(404,'This export is unavailable.')
        return FileResponse(path,filename=row['name'],media_type='application/octet-stream')

    @app.get('/')
    def landing():return site_page('index.html')

    @app.get('/account')
    def account_page():return site_page('account.html')

    @app.get('/app')
    def editor(request:Request):
        try:account(request,paid=True)
        except HTTPException as e:return RedirectResponse('/account?view='+('billing' if e.status_code==402 else 'login'),status_code=303)
        return FileResponse(SITE/'workspace.html')

    @app.get('/tour')
    def tour():return FileResponse(SITE/'tour.html')

    @app.get('/policies')
    def policies():return FileResponse(SITE/'policies.html')

    from .licensing import mount_licenses
    mount_licenses(app,settings,store,account,body,Input,rate)
    from .downloads import mount_downloads
    mount_downloads(app,settings,store,account)
    from .support import mount_support
    mount_support(app,settings,store,account,body,Input,rate)
    from .community import mount_community
    mount_community(app,settings,store,account,body,Input,rate)
    @app.get('/reviews')
    def reviews_page():return site_page('reviews.html')
    @app.get('/dashboard')
    def dashboard_page():return site_page('dashboard.html')
    @app.get('/support')
    def support_page():return FileResponse(SITE/'support.html')
    @app.get('/support/inbox')
    def support_inbox():return FileResponse(SITE/'support-inbox.html')
    app.mount('/assets',StaticFiles(directory=SITE/'assets'),name='assets')
    return app
