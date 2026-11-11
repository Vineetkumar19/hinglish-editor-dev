"""Private chat-only companion; the existing editing engine stays loopback-only."""
from contextlib import contextmanager
import argparse
import hashlib
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import tempfile
import time
from urllib.parse import parse_qs, quote, urlsplit

UPLOAD_LIMIT = 256 * 1024**2
JSON_LIMIT = 64 * 1024
COOKIE = 'storylens_phone'
STATIC = Path(__file__).with_name('phone_static')
UPLOAD_TYPES = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.mts', '.m2ts', '.webm', '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.png', '.jpg', '.jpeg', '.webp', '.txt', '.xml'}
OUTPUT_TYPES = {'.mp4', '.mov', '.mkv', '.webm', '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.png', '.jpg', '.jpeg', '.webp', '.pdf', '.txt', '.srt', '.ass', '.xml', '.zip'}
ACTIVE = {'planning', 'running', 'transcribing'}


class PhoneError(Exception):
    def __init__(self, message, status=400, code='phone_request'):
        super().__init__(message)
        self.status, self.code = status, code


class EngineUnavailable(PhoneError):
    def __init__(self, message='StoryLens is not responding on the laptop. Open StoryLens and check this chat before retrying.', *, uncertain=True):
        super().__init__(message, 503, 'phone_engine_unavailable')
        self.uncertain = uncertain


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', value):
        raise PhoneError('The request identity is invalid. Refresh and try again.')
    return value


def safe_name(value):
    if not isinstance(value, str) or not value or len(value) > 200 or any(c in value for c in '\\/:\x00\r\n') or value in {'.', '..'}:
        raise PhoneError('Choose one ordinary media or text file with a valid filename.')
    return value


class EngineClient:
    def __init__(self, root, port=8765):
        self.root = Path(root).resolve()
        self.port = int(port)
        if self.port != 8765:
            raise PhoneError('The companion uses the existing primary StoryLens service on port 8765.')

    def request(self, method, route, payload=None, stream=None, length=None):
        try:
            bridge = json.loads((self.root/'cache'/'app'/'bridge.json').read_text('utf-8'))
            token = bridge['token']
            if not isinstance(token, str) or len(token) < 16:
                raise ValueError('Invalid bridge')
        except (OSError, ValueError, KeyError, TypeError):
            raise EngineUnavailable(uncertain=False) from None
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=120 if stream is not None else 30)
        try:
            headers = {'X-Hinglish-Token': token, 'Accept': 'application/json'}
            if stream is None:
                body = None if payload is None else json.dumps(payload).encode('utf-8')
                headers['Content-Type'] = 'application/json'
                conn.request(method, route, body=body, headers=headers)
            else:
                conn.putrequest(method, route)
                for key, value in {**headers, 'Content-Type':'application/octet-stream', 'Content-Length':str(length)}.items():
                    conn.putheader(key, value)
                conn.endheaders()
                remaining = length
                while remaining:
                    chunk = stream.read(min(1024**2, remaining))
                    if not chunk:
                        raise PhoneError('The attachment was interrupted. Choose the file again.')
                    conn.send(chunk)
                    remaining -= len(chunk)
            response = conn.getresponse()
            body = response.read(8 * 1024**2 + 1)
            if len(body) > 8 * 1024**2 or not response.getheader('Content-Type', '').startswith('application/json'):
                raise EngineUnavailable('StoryLens returned an unexpected result. Check the laptop before retrying.')
            result = json.loads(body)
            if response.status >= 400:
                if response.status in (400, 404, 409, 413):
                    message = result.get('error') if isinstance(result, dict) else None
                    raise PhoneError(message if isinstance(message, str) and len(message) < 500 else 'StoryLens could not accept this request. Check the laptop.', response.status)
                raise EngineUnavailable()
            if not isinstance(result, dict):
                raise EngineUnavailable()
            return result
        except PhoneError:
            raise
        except ConnectionRefusedError:
            raise EngineUnavailable(uncertain=False) from None
        except (OSError, ValueError, http.client.HTTPException):
            raise EngineUnavailable() from None
        finally:
            conn.close()

    def health(self):
        return self.request('GET', '/api/health').get('ok', True) is not False

    def create(self):
        return self.request('POST', '/api/assistant/session', {})

    def snapshot(self, identity):
        return self.request('GET', '/api/assistant/session?id=' + quote(identity))

    def send(self, identity, payload):
        return self.request('POST', '/api/assistant/message', {'session':identity, **payload})

    def stop(self, identity):
        return self.request('POST', '/api/assistant/stop', {'session':identity})

    def upload(self, identity, name, stream, length):
        return self.request('POST', '/api/assistant/upload?session=' + quote(identity) + '&name=' + quote(name), stream=stream, length=length)


class PhoneService:
    def __init__(self, root, origin, engine=None):
        self.root = Path(root).resolve()
        parsed = urlsplit(origin)
        local = parsed.hostname in {'127.0.0.1', 'localhost'} and parsed.scheme == 'http'
        private_https = parsed.scheme == 'https' and bool(re.fullmatch(r'[a-z0-9.-]+\.ts\.net', parsed.hostname or ''))
        if not (local or private_https) or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise PhoneError('Use your private Tailscale HTTPS address, or local loopback for setup.')
        self.origin, self.secure = origin, parsed.scheme == 'https'
        self.host = parsed.netloc
        self.folder = self.root/'cache'/'phone-remote'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.db_path = self.folder/'phone.sqlite3'
        self.engine = engine or EngineClient(self.root)
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS pairing (hash TEXT PRIMARY KEY, expires REAL, used INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS devices (hash TEXT PRIMARY KEY, csrf TEXT, expires REAL, revoked INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS failures (created REAL);
                CREATE TABLE IF NOT EXISTS chats (owner TEXT, id TEXT, title TEXT, status TEXT, stage TEXT, created REAL, PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS requests (owner TEXT, id TEXT, fingerprint TEXT, state TEXT, result TEXT, PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS attachments (owner TEXT, chat TEXT, id TEXT, PRIMARY KEY(owner,chat,id));
                CREATE TABLE IF NOT EXISTS files (owner TEXT, chat TEXT, id TEXT PRIMARY KEY, path TEXT, size INTEGER, mtime INTEGER, inode TEXT);
            ''')

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def issue_pairing(self):
        code = secrets.token_urlsafe(18)
        with self.db() as db:
            db.execute('UPDATE pairing SET used=1 WHERE used=0')
            db.execute('INSERT INTO pairing(hash,expires) VALUES(?,?)', (digest(code), time.time()+600))
        return code

    def pair(self, code):
        if not isinstance(code, str) or not 16 <= len(code) <= 100:
            code = ''
        now = time.time()
        with self.lock, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM failures WHERE created>?', (now-60,)).fetchone()[0] >= 8:
                raise PhoneError('Too many pairing attempts. Wait one minute and request a new code on the laptop.', 429, 'phone_pairing_limited')
            row = db.execute('SELECT * FROM pairing WHERE hash=? AND expires>? AND used=0', (digest(code),now)).fetchone()
            if row:
                db.execute('UPDATE pairing SET used=1 WHERE hash=?', (digest(code),))
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                db.execute('INSERT INTO devices(hash,csrf,expires) VALUES(?,?,?)', (digest(token),csrf,now+24*3600))
            else:
                db.execute('INSERT INTO failures VALUES(?)', (now,))
                token = None
        if token is None:
            raise PhoneError('That code is invalid, expired or already used. Create a new code on the laptop.', 401, 'phone_pairing')
        return token, csrf

    def owner(self, token):
        if not isinstance(token, str) or not 32 <= len(token) <= 100:
            raise PhoneError('Pair this phone with the laptop first.', 401, 'phone_pair_required')
        with self.db() as db:
            row = db.execute('SELECT * FROM devices WHERE hash=? AND revoked=0 AND expires>?', (digest(token),time.time())).fetchone()
        if not row:
            raise PhoneError('Pair this phone with the laptop first.', 401, 'phone_pair_required')
        return dict(row)

    def logout(self, token):
        owner = self.owner(token)
        with self.db() as db:
            db.execute('UPDATE devices SET revoked=1 WHERE hash=?', (owner['hash'],))
        return {'paired':False}

    def revoke_all(self):
        with self.db() as db:
            db.execute('UPDATE devices SET revoked=1')
            db.execute('UPDATE pairing SET used=1')

    def state(self, token):
        owner = self.owner(token)
        with self.db() as db:
            chats = [dict(row) for row in db.execute('SELECT id,title,status,stage,created FROM chats WHERE owner=? ORDER BY created DESC LIMIT 30', (owner['hash'],))]
        try:
            connected = self.engine.health()
        except PhoneError:
            connected = False
        return {'paired':True,'csrf':owner['csrf'],'connected':bool(connected),'assistant':'Configured StoryLens assistant','chats':chats,'active_chat':chats[0]['id'] if chats else None}

    def owned_chat(self, owner, identity):
        if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{16}', identity):
            raise PhoneError('This phone conversation is unavailable.', 404)
        with self.db() as db:
            row = db.execute('SELECT id FROM chats WHERE owner=? AND id=?', (owner,identity)).fetchone()
        if not row:
            raise PhoneError('This phone conversation is unavailable.', 404)

    def reserve(self, owner, identity, payload):
        request_id(identity)
        fingerprint = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM requests WHERE owner=? AND id=?', (owner,identity)).fetchone()
            if row:
                if row['fingerprint'] != fingerprint:
                    raise PhoneError('This request was already used for different content. Start a new request.', 409)
                if row['state'] == 'retryable':
                    db.execute("UPDATE requests SET state='submitted' WHERE owner=? AND id=?",(owner,identity))
                    return None
                if row['state'] != 'complete':
                    raise PhoneError('The laptop did not confirm this request. Check the conversation before sending another command; it will not be sent twice.', 409, 'phone_uncertain_submission')
                return json.loads(row['result'])
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?)', (owner,identity,fingerprint,'submitted',None))
        return None

    def complete(self, owner, identity, result):
        with self.db() as db:
            db.execute('UPDATE requests SET state=\'complete\',result=? WHERE owner=? AND id=?', (json.dumps(result),owner,identity))

    def invoke(self, owner, identity, operation):
        try:
            return operation()
        except EngineUnavailable as error:
            if not error.uncertain:
                with self.db() as db:
                    db.execute("UPDATE requests SET state='retryable' WHERE owner=? AND id=?",(owner,identity))
            raise

    def create_chat(self, token, identity):
        owner = self.owner(token)['hash']
        with self.lock:
            old = self.reserve(owner, identity, {'action':'create_chat'})
            if old:
                return self.snapshot(token, old['id'])
            raw = self.invoke(owner,identity,self.engine.create)
            chat = raw.get('id')
            if not isinstance(chat, str) or not re.fullmatch(r'[a-f0-9]{16}', chat):
                raise EngineUnavailable('StoryLens did not confirm the new chat. Check the laptop before retrying.')
            with self.db() as db:
                db.execute('INSERT INTO chats VALUES(?,?,?,?,?,?)', (owner,chat,'New chat','idle','',time.time()))
            self.complete(owner, identity, {'id':chat})
            return self.present(owner, raw)

    def snapshot(self, token, identity):
        owner = self.owner(token)['hash']
        self.owned_chat(owner, identity)
        return self.present(owner, self.engine.snapshot(identity))

    def send(self, token, identity, payload):
        owner = self.owner(token)['hash']
        self.owned_chat(owner, identity)
        if not isinstance(payload, dict) or set(payload)-{'request_id','message','attachments','profile'}:
            raise PhoneError('Send only your message and its selected attachments.')
        text, items, profile = payload.get('message'), payload.get('attachments',[]), payload.get('profile','general')
        if not isinstance(text, str) or not text.strip() or len(text)>24000:
            raise PhoneError('Enter a message of up to 24,000 characters.')
        if profile not in {'general','cricket','gaming'}:
            raise PhoneError('Choose General, Cricket or Gaming.')
        if not isinstance(items, list) or len(items)>20 or any(not isinstance(item,str) for item in items) or len(set(items)) != len(items):
            raise PhoneError('Choose valid attachments from this phone conversation.')
        with self.db() as db:
            allowed = {row[0] for row in db.execute('SELECT id FROM attachments WHERE owner=? AND chat=?', (owner,identity))}
        if any(item not in allowed for item in items):
            raise PhoneError('An attachment is not part of this phone conversation.')
        args = {'message':text.strip(),'attachments':items,'profile':profile}
        key = payload.get('request_id')
        with self.lock:
            old = self.reserve(owner, key, {'action':'message','chat':identity,**args})
            if old:
                return self.snapshot(token, identity)
            raw = self.invoke(owner,key,lambda:self.engine.send(identity,args))
            self.complete(owner, key, {'id':identity})
        return self.present(owner, raw)

    def stop(self, token, identity):
        owner = self.owner(token)['hash']
        self.owned_chat(owner, identity)
        return self.present(owner, self.engine.stop(identity))

    def upload(self, token, identity, name, stream, length, key):
        owner = self.owner(token)['hash']
        self.owned_chat(owner, identity)
        safe_name(name)
        if Path(name).suffix.lower() not in UPLOAD_TYPES:
            raise PhoneError('Choose a supported video, image, audio, TXT or XML file.')
        if type(length) is not int or not 0 < length <= UPLOAD_LIMIT:
            raise PhoneError('Choose a nonempty file up to 256 MiB.', 413)
        request_id(key)
        with tempfile.TemporaryFile(dir=self.folder) as staged:
            remaining = length
            checksum = hashlib.sha256()
            while remaining:
                chunk = stream.read(min(1024**2, remaining))
                if not chunk:
                    raise PhoneError('The file transfer was interrupted. Select it again.')
                staged.write(chunk);checksum.update(chunk);remaining -= len(chunk)
            staged.seek(0)
            with self.lock:
                old = self.reserve(owner, key, {'action':'attachment','chat':identity,'name':name,'size':length,'sha256':checksum.hexdigest()})
                if old:
                    return old
                raw = self.invoke(owner,key,lambda:self.engine.upload(identity,name,staged,length))
                item = {'id':raw['id'],'name':name,'size':length,'kind':raw.get('kind','file')}
                with self.db() as db:
                    db.execute('INSERT OR IGNORE INTO attachments VALUES(?,?,?)', (owner,identity,item['id']))
                self.complete(owner,key,item)
        return item

    def present(self, owner, raw):
        identity = raw['id']
        self.owned_chat(owner,identity)
        messages=[]
        for message in raw.get('messages', [])[-80:]:
            if not isinstance(message,dict) or message.get('role') not in {'user','assistant'}:
                continue
            messages.append({key:message[key] for key in ('id','role','text','created','error','error_code','error_details') if key in message})
        title = str(raw.get('title') or next((m.get('text','') for m in messages if m['role']=='user'),'New chat'))[:100]
        result = {'id':identity,'title':title,'status':str(raw.get('status','idle'))[:40],'stage':str(raw.get('stage',''))[:1500],
                  'messages':messages,'attachments':[{k:a[k] for k in ('id','name','size','kind') if k in a} for a in raw.get('attachments',[]) if isinstance(a,dict)],
                  'files':self.output_files(owner,identity,raw)}
        with self.db() as db:
            db.execute('UPDATE chats SET title=?,status=?,stage=? WHERE owner=? AND id=?', (title,result['status'],result['stage'],owner,identity))
        progress = raw.get('task_progress')
        if isinstance(progress,dict):
            result['task_progress'] = self.progress(progress)
        return result

    def progress(self, value, depth=0):
        if depth>6:
            return None
        allowed = {'label','title','stage','message','status','progress','percent','completed','total','remaining','count','unit','steps','cards','groups','summary','elapsed_seconds','eta_seconds'}
        if isinstance(value,dict):
            return {k:self.progress(v,depth+1) for k,v in value.items() if k in allowed}
        if isinstance(value,list):
            return [self.progress(item,depth+1) for item in value[:50]]
        if isinstance(value,str):
            return value[:1000]
        return value if type(value) in (int,float,bool) or value is None else None

    def output_files(self, owner, identity, raw):
        candidates=[]
        def walk(value, depth=0):
            if depth>8 or len(candidates)>=100:
                return
            if isinstance(value, str) and len(value)<4096:
                try:
                    path = Path(value)
                    if path.is_absolute() and path.suffix.lower() in OUTPUT_TYPES:
                        candidates.append(path)
                except (OSError,ValueError):
                    pass
            elif isinstance(value,list):
                for item in value[:100]: walk(item,depth+1)
            elif isinstance(value,dict):
                for key,item in list(value.items())[:100]:
                    if not any(word in str(key).lower() for word in ('token','secret','password','credential','prompt','context','request','config')):
                        walk(item,depth+1)
        for message in raw.get('messages',[]):
            if isinstance(message,dict) and message.get('role')=='assistant' and not message.get('error'):
                walk(message.get('videos',[]));walk(message.get('result',{}))
        walk(raw.get('last_paths',[]));walk(raw.get('last_result',{}));walk(raw.get('step_results',[]))
        output=(self.root/'output').resolve()
        found=[];seen=set()
        for candidate in candidates:
            try:
                path=candidate.resolve(strict=True)
                if not path.is_relative_to(output) or not path.is_file() or path.suffix.lower() not in OUTPUT_TYPES or path in seen:
                    continue
                stat=path.stat();seen.add(path)
                key=digest(owner+'\0'+identity+'\0'+str(path))[:32]
                with self.db() as db:
                    existing=db.execute('SELECT * FROM files WHERE id=?',(key,)).fetchone()
                    if not existing:
                        db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?)',(owner,identity,key,str(path),stat.st_size,stat.st_mtime_ns,str(stat.st_ino)))
                    elif existing['size']!=stat.st_size or existing['mtime']!=stat.st_mtime_ns or existing['inode']!=str(stat.st_ino):
                        continue
                mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
                found.append({'id':key,'name':path.name,'size':stat.st_size,'mime':mime,'url':'/phone/files/'+key,'download_url':'/phone/files/'+key+'?download=1'})
            except (OSError,ValueError):
                continue
        return found

    def file(self, token, identity):
        owner=self.owner(token)['hash']
        if not re.fullmatch(r'[a-f0-9]{32}',identity):
            raise PhoneError('This result is unavailable.',404)
        with self.db() as db:
            row=db.execute('SELECT * FROM files WHERE owner=? AND id=?',(owner,identity)).fetchone()
        if not row:
            raise PhoneError('This result is unavailable.',404)
        path=Path(row['path']).resolve()
        try:
            stat=path.stat()
            if not path.is_relative_to((self.root/'output').resolve()) or path.suffix.lower() not in OUTPUT_TYPES or not path.is_file() or stat.st_size!=row['size'] or stat.st_mtime_ns!=row['mtime'] or str(stat.st_ino)!=row['inode']:
                raise OSError('Changed result')
        except OSError:
            raise PhoneError('This result moved or changed on the laptop. Ask the editor for the current result.',409) from None
        return {'path':path,'size':stat.st_size,'mtime':stat.st_mtime_ns,'inode':str(stat.st_ino),'mime':mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}


def create_server(service, port=8796):
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'

        def log_message(self,*_args):
            pass

        def common(self):
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')

        def answer(self,status,value,cookie=None):
            data=json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.common()
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            if cookie:self.send_header('Set-Cookie',cookie)
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(data)

        def check(self, mutation=False, paired=True):
            host=self.headers.get('Host','')
            if host not in {service.host,f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
                raise PhoneError('Open the private StoryLens phone address.',403)
            if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):
                raise PhoneError('Use the private StoryLens phone page.',403)
            if mutation:
                origin=self.headers.get('Origin')
                if origin is not None and origin!=service.origin:
                    raise PhoneError('Use the private StoryLens phone page.',403)
            token=None
            try:
                cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
                token=cookies[COOKIE].value if COOKIE in cookies else None
            except Exception:
                pass
            if paired:
                owner=service.owner(token)
                if mutation and not secrets.compare_digest(self.headers.get('X-Phone-CSRF',''),owner['csrf']):
                    raise PhoneError('Refresh this phone page before trying again.',403)
            return token

        def failure(self, error):
            from .user_messages import problem
            status = error.status if isinstance(error,PhoneError) else 500
            issue = problem(error,status=status if status>=500 else None)
            code = error.code if isinstance(error,PhoneError) else 'phone_internal'
            self.answer(status,{'error':issue['message'],'code':code,'error_code':code,'error_details':issue['details']})

        def do_OPTIONS(self):
            self.answer(405,{'error':'Cross-site access is not enabled.'})

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                parsed=urlsplit(self.path)
                self.check(paired=False)
                static={'/':'index.html','/phone/phone.css':'phone.css','/phone/phone.js':'phone.js'}
                if parsed.path=='/phone/health':
                    return self.answer(200,{'service':'storylens-phone','version':1,'installation':digest(str(service.root))[:16]})
                if parsed.path in static:
                    file=STATIC/static[parsed.path]
                    data=file.read_bytes()
                    self.send_response(200);self.common()
                    self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'text/plain')
                    self.send_header('Content-Length',str(len(data)));self.end_headers()
                    if self.command!='HEAD':self.wfile.write(data)
                    return
                token=self.check()
                if parsed.path=='/phone/state':return self.answer(200,service.state(token))
                if parsed.path=='/phone/chats':return self.answer(200,{'chats':service.state(token)['chats']})
                match=re.fullmatch(r'/phone/chats/([a-f0-9]{16})',parsed.path)
                if match:return self.answer(200,service.snapshot(token,match[1]))
                match=re.fullmatch(r'/phone/files/([a-f0-9]{32})',parsed.path)
                if match:return self.media(token,match[1],parsed)
                raise PhoneError('This phone action is unavailable.',404)
            except PhoneError as error:self.failure(error)
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as error:self.failure(error)

        def media(self,token,identity,parsed):
            item=service.file(token,identity)
            size=item['size'];start=0;end=size-1
            value=self.headers.get('Range')
            if value:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
                if not match or not any(match.groups()):raise PhoneError('This media range is unavailable.',416)
                if not match[1]:start=max(0,size-int(match[2]))
                else:start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
                if start<0 or start>end or start>=size:raise PhoneError('This media range is unavailable.',416)
            with item['path'].open('rb') as file:
                stat=os.fstat(file.fileno())
                if stat.st_size!=size or stat.st_mtime_ns!=item['mtime'] or str(stat.st_ino)!=item['inode']:
                    raise PhoneError('This file changed. Refresh the result on the laptop.',409)
                self.send_response(206 if value else 200);self.common()
                self.send_header('Content-Type',item['mime'])
                self.send_header('Accept-Ranges','bytes')
                self.send_header('Content-Length',str(max(0,end-start+1)))
                if value:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                download=parse_qs(parsed.query).get('download',[''])[0]=='1' or item['mime'] in {'application/xml','text/xml','application/zip'}
                disposition='attachment' if download else 'inline'
                self.send_header('Content-Disposition',disposition+"; filename*=UTF-8''"+quote(item['path'].name,safe=''))
                self.end_headers()
                if self.command=='HEAD':return
                file.seek(start);remaining=end-start+1
                while remaining>0:
                    chunk=file.read(min(1024**2,remaining))
                    if not chunk:break
                    self.wfile.write(chunk);remaining-=len(chunk)

        def do_POST(self):
            try:
                parsed=urlsplit(self.path)
                pair=parsed.path=='/phone/pair'
                token=self.check(mutation=True,paired=not pair)
                if self.headers.get('Transfer-Encoding'):raise PhoneError('Send a fixed-size request.',400)
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:raise PhoneError('Invalid request length.') from None
                match=re.fullmatch(r'/phone/chats/([a-f0-9]{16})/attachments',parsed.path)
                if match:
                    self.close_connection=True
                    if not 0<length<=UPLOAD_LIMIT:raise PhoneError('Choose a nonempty file up to 256 MiB.',413)
                    query=parse_qs(parsed.query)
                    return self.answer(201,service.upload(token,match[1],query.get('name',[''])[0],self.rfile,length,query.get('request_id',[''])[0]))
                if not 0<=length<=JSON_LIMIT:raise PhoneError('This message is too large.',413)
                if not self.headers.get('Content-Type','').startswith('application/json'):raise PhoneError('Send a JSON request.')
                try:payload=json.loads(self.rfile.read(length) or b'{}')
                except (ValueError,UnicodeError):raise PhoneError('The message could not be read. Refresh and try again.') from None
                if not isinstance(payload,dict):raise PhoneError('Send a JSON object.')
                if pair:
                    if set(payload)!={'code'}:raise PhoneError('Enter the pairing code from your laptop.')
                    cookie,csrf=service.pair(payload['code'])
                    value=f'{COOKIE}={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+('; Secure' if service.secure else '')
                    return self.answer(200,{'paired':True,'csrf':csrf},cookie=value)
                if parsed.path=='/phone/logout':return self.answer(200,service.logout(token),cookie=f'{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+('; Secure' if service.secure else ''))
                if parsed.path=='/phone/chats' and set(payload)=={'request_id'}:return self.answer(201,service.create_chat(token,payload['request_id']))
                match=re.fullmatch(r'/phone/chats/([a-f0-9]{16})/(messages|stop)',parsed.path)
                if match:
                    if match[2]=='messages':return self.answer(202,service.send(token,match[1],payload))
                    if payload:raise PhoneError('Stop does not take extra settings.')
                    return self.answer(200,service.stop(token,match[1]))
                raise PhoneError('This phone action is unavailable.',404)
            except PhoneError as error:
                self.close_connection=True
                self.failure(error)
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as error:
                self.close_connection=True
                self.failure(error)

    class Server(ThreadingHTTPServer):
        daemon_threads=True
        allow_reuse_address=False

        def handle_error(self, request, client_address):
            if isinstance(sys.exc_info()[1],(BrokenPipeError,ConnectionResetError,ConnectionAbortedError,TimeoutError)):
                return
            super().handle_error(request,client_address)

    return Server(('127.0.0.1',port),Handler)


def main():
    parser=argparse.ArgumentParser(description='StoryLens private phone Ask the Editor companion')
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--origin',required=True)
    parser.add_argument('--port',type=int,default=8796)
    parser.add_argument('--pair-only',action='store_true')
    parser.add_argument('--revoke-all',action='store_true')
    args=parser.parse_args()
    service=PhoneService(args.root,args.origin)
    if args.revoke_all:
        service.revoke_all();print('All phone sessions and unused pairing codes revoked.',flush=True);return
    code=service.issue_pairing()
    print('StoryLens phone address: '+args.origin,flush=True)
    print('One-use pairing code (expires in 10 minutes): '+code,flush=True)
    if args.pair_only:return
    server=create_server(service,args.port)
    from .durable_json import write
    runtime=service.folder/'runtime.json'
    write(runtime,{'pid':os.getpid(),'root':str(service.root),'origin':service.origin,'port':server.server_port})
    print('Private chat companion listening on loopback only. The main editor is unchanged.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        try:
            if json.loads(runtime.read_text('utf-8')).get('pid')==os.getpid():runtime.unlink()
        except (OSError,ValueError):pass


if __name__=='__main__':
    try:
        main()
    except (PhoneError,OSError) as error:
        print('Phone connection not started: '+str(error),file=sys.stderr,flush=True)
        raise SystemExit(1) from None
