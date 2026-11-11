"""Owner-only Android transport: encrypted outbound mailbox, existing local assistant."""
import argparse
import base64
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .durable_json import write
from .phone_remote import PhoneError, PhoneService, UPLOAD_TYPES, request_id, safe_name

CHUNK = 131072
LIMIT = 256 * 1024**2
FRAME_LIMIT = 184320
AAD = b'storylens-personal-v1|'


class RelayError(ValueError):
    pass


def encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def decode(value, limit=FRAME_LIMIT):
    if not isinstance(value,str) or len(value)>limit*2 or not re.fullmatch(r'[A-Za-z0-9_-]*',value):
        raise RelayError('The encrypted connection data is invalid.')
    try:
        result=base64.b64decode(value+'='*((-len(value))%4),altchars=b'-_',validate=True)
    except ValueError:
        raise RelayError('The encrypted connection data is invalid.') from None
    if len(result)>limit:
        raise RelayError('The connection frame is too large.')
    return result


def validate_relay(value):
    parsed=urlsplit(value)
    if parsed.scheme!='https' or not re.fullmatch(r'[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev',parsed.hostname or '') or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise RelayError('Use the exact StoryLens HTTPS relay address, without a path or credentials.')
    return value


class Cipher:
    def __init__(self,key):
        if not isinstance(key,bytes) or len(key)!=32:
            raise RelayError('The phone connection key must contain 32 bytes.')
        self.aes=AESGCM(key)

    def encrypt(self,value,nonce=None):
        identity=request_id(value.get('id'))
        plain=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(plain)>FRAME_LIMIT-16:
            raise RelayError('This result is too large for one phone response. Open the saved result on the laptop.')
        nonce=nonce if nonce is not None else secrets.token_bytes(12)
        if len(nonce)!=12:
            raise RelayError('Invalid encryption nonce.')
        return {'v':1,'id':identity,'nonce':encode(nonce),'data':encode(self.aes.encrypt(nonce,plain,AAD+identity.encode()))}

    def decrypt(self,envelope):
        try:
            if not isinstance(envelope,dict) or set(envelope)!={'v','id','nonce','data'} or type(envelope['v']) is not int or envelope['v']!=1:
                raise RelayError('Invalid encrypted frame.')
            identity=request_id(envelope['id'])
            nonce=decode(envelope['nonce'],12)
            if len(nonce)!=12:
                raise RelayError('Invalid encryption nonce.')
            value=json.loads(self.aes.decrypt(nonce,decode(envelope['data']),AAD+identity.encode()))
            if not isinstance(value,dict) or value.get('id')!=identity:
                raise RelayError('The encrypted result identity does not match.')
            return value
        except Exception:
            raise RelayError('The phone message could not be authenticated. Pair with the correct laptop connection.') from None


def protect(data, decrypt=False):
    if os.name!='nt':
        raise RelayError('This private laptop connection currently supports Windows only.')
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_byte))]
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_byte)))
    target=Blob()
    crypt=ctypes.windll.crypt32
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise RelayError('Windows could not unlock this connection for the signed-in user.')
    try:return ctypes.string_at(target.pbData,target.cbData)
    finally:
        local_free=ctypes.windll.kernel32.LocalFree
        local_free.argtypes=[ctypes.c_void_p];local_free.restype=ctypes.c_void_p
        local_free(target.pbData)


def save_private(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    partial=path.with_suffix('.partial')
    partial.write_bytes(protect(json.dumps(value).encode('utf-8')))
    partial.replace(path)


def read_private(path):
    return json.loads(protect(Path(path).read_bytes(),decrypt=True))


def fields(params, required, optional=()):
    if not isinstance(params,dict) or set(params)-set(required)-set(optional) or set(required)-set(params):
        raise PhoneError('The app sent unsupported or incomplete settings. Update the app and try again.')


class NativeCompanion:
    def __init__(self,root,service=None):
        self.root=Path(root).resolve()
        self.folder=self.root/'cache'/'phone-native'
        self.folder.mkdir(parents=True,exist_ok=True)
        self.uploads=self.folder/'uploads';self.uploads.mkdir(exist_ok=True)
        self.service=service or PhoneService(self.root,'http://127.0.0.1:8797')
        self.lock=threading.RLock()
        private=self.folder/'device.dpapi'
        if private.exists():
            self.token=read_private(private)['token']
            self._renew()
        else:
            self.token,_csrf=self.service.pair(self.service.issue_pairing())
            save_private(private,{'token':self.token})
        self._renew()

    def _renew(self):
        with self.service.db() as db:
            row=db.execute('SELECT revoked FROM devices WHERE hash=?',(hashlib.sha256(self.token.encode()).hexdigest(),)).fetchone()
            if not row or row['revoked']:
                raise RelayError('This native phone connection was revoked. Create a new connection on the laptop.')
            db.execute('UPDATE devices SET expires=? WHERE hash=?',(time.time()+86400,hashlib.sha256(self.token.encode()).hexdigest()))

    def dispatch(self,method,params):
        with self.lock:
            self._renew()
            return self._dispatch(method,params)

    def _dispatch(self,method,params):
        if method=='state':
            fields(params,())
            state=self.service.state(self.token)
            return {k:v for k,v in state.items() if k not in ('csrf','paired')}
        if method=='create_chat':
            fields(params,('request_id',))
            return self.snapshot(self.service.create_chat(self.token,params['request_id']))
        if method in ('chat','stop'):
            fields(params,('chat',))
            operation=self.service.snapshot if method=='chat' else self.service.stop
            return self.snapshot(operation(self.token,params['chat']))
        if method=='send':
            fields(params,('chat','request_id','message'),('attachments','profile'))
            payload={key:value for key,value in params.items() if key!='chat'}
            return self.snapshot(self.service.send(self.token,params['chat'],payload))
        if method=='upload_begin':
            fields(params,('chat','request_id','name','size'))
            owner=self.service.owner(self.token)['hash'];self.service.owned_chat(owner,params['chat'])
            request_id(params['request_id']);safe_name(params['name'])
            if Path(params['name']).suffix.lower() not in UPLOAD_TYPES or type(params['size']) is not int or not 0<params['size']<=LIMIT:
                raise PhoneError('Choose a supported media/text attachment up to 256 MiB.')
            identity=hashlib.sha256((params['chat']+'\0'+params['request_id']).encode()).hexdigest()[:32]
            file=self.uploads/(identity+'.json')
            if file.exists():
                saved=json.loads(file.read_text('utf-8'))
                if saved['request']!=params:raise PhoneError('This upload identity was already used for another file.',409)
            else:
                saved={'request':params,'written':0,'next':0,'chunks':[],'created':time.time()}
                (self.uploads/(identity+'.part')).write_bytes(b'')
                write(file,saved)
            return {'upload':identity,'next_index':saved['next']}
        if method in ('upload_chunk','upload_finish'):
            fields(params,('upload','index','data') if method=='upload_chunk' else ('upload',))
            identity=params['upload']
            if not isinstance(identity,str) or not re.fullmatch(r'[a-f0-9]{32}',identity):raise PhoneError('This upload is unavailable.')
            file=self.uploads/(identity+'.json');part=self.uploads/(identity+'.part')
            if not file.is_file():raise PhoneError('This upload is unavailable. Select the file again.',404)
            saved=json.loads(file.read_text('utf-8'));request=saved['request']
            owner=self.service.owner(self.token)['hash'];self.service.owned_chat(owner,request['chat'])
            if method=='upload_finish':
                if saved.get('result'):return saved['result']
                if saved['written']!=request['size'] or part.stat().st_size!=request['size']:raise PhoneError('The attachment is incomplete. Finish its transfer first.')
                with part.open('rb') as stream:
                    item=self.service.upload(self.token,request['chat'],request['name'],stream,request['size'],request['request_id'])
                saved['result']=item;write(file,saved);part.unlink()
                return item
            index=params['index'];data=decode(params['data'],CHUNK)
            if type(index) is not int or index<0 or not data:raise PhoneError('Invalid upload chunk.')
            checksum=hashlib.sha256(data).hexdigest()
            if index<saved['next']:
                if saved['chunks'][index]!=checksum:raise PhoneError('The repeated upload chunk changed.',409)
                return {'next_index':saved['next']}
            if index!=saved['next'] or saved['written']+len(data)>request['size'] or saved.get('result'):raise PhoneError('Upload chunks arrived out of order or exceed the file size.',409)
            with part.open('r+b') as stream:
                if part.stat().st_size<saved['written']:raise PhoneError('The saved attachment changed. Select it again.')
                stream.seek(saved['written']);stream.truncate();stream.write(data);stream.flush();os.fsync(stream.fileno())
            saved['written']+=len(data);saved['next']+=1;saved['chunks'].append(checksum);write(file,saved)
            return {'next_index':saved['next']}
        if method in ('file_info','file_chunk'):
            fields(params,('file',) if method=='file_info' else ('file','offset','length'))
            item=self.service.file(self.token,params['file']);file=item['path']
            if item['size']>LIMIT:raise PhoneError('This result exceeds the current 256 MiB phone-transfer limit. Open it on the laptop.')
            if method=='file_info':return {'id':params['file'],'name':file.name,'size':item['size'],'mime':item['mime']}
            offset,length=params['offset'],params['length']
            if type(offset) is not int or type(length) is not int or not 0<=offset<=item['size'] or not 1<=length<=CHUNK:raise PhoneError('This result chunk is invalid.')
            with file.open('rb') as stream:
                stat=os.fstat(stream.fileno())
                if stat.st_size!=item['size'] or stat.st_mtime_ns!=item['mtime'] or str(stat.st_ino)!=item['inode']:raise PhoneError('The result changed on the laptop. Refresh the chat.')
                stream.seek(offset);data=stream.read(length)
            return {'data':encode(data),'offset':offset,'next_offset':offset+len(data),'eof':offset+len(data)>=item['size']}
        raise PhoneError('This action is not available through the phone connection.',404)

    def snapshot(self,value):
        result=dict(value)
        result['files']=[{k:v for k,v in file.items() if k not in ('url','download_url')} for file in value.get('files',[])]
        messages=value.get('messages',[])
        kept=[];used=0
        for message in reversed(messages):
            size=len(json.dumps(message,ensure_ascii=False).encode())
            if used+size>110000:break
            kept.append(message);used+=size
        result['messages']=list(reversed(kept))
        if len(kept)<len(messages):result['history_notice']='Older messages remain on the laptop; this response shows the latest messages.'
        return result


class RelayClient:
    def __init__(self,url,token):
        self.url=validate_relay(url)
        self.host=urlsplit(url).hostname
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,100}',token):raise RelayError('Invalid private relay credential.')
        self.token=token

    def request(self,method,route,payload=None):
        conn=http.client.HTTPSConnection(self.host,timeout=30)
        try:
            data=None if payload is None else json.dumps(payload,separators=(',',':')).encode()
            conn.request(method,route,data,{'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'application/json'})
            response=conn.getresponse();body=response.read(2*1024**2+1)
            if response.status!=200 or len(body)>2*1024**2 or not response.getheader('Content-Type','').startswith('application/json'):
                raise RelayError('The private relay is unavailable or rejected this connection. Check its setup on the laptop.')
            return json.loads(body)
        except (OSError,ValueError,http.client.HTTPException):
            raise RelayError('The private relay is unreachable. Check the laptop internet connection.') from None
        finally:conn.close()


def config_path(root):return Path(root)/'cache'/'phone-native'/'connection.dpapi'


def configure(root,url):
    validate_relay(url);file=config_path(root)
    if file.exists():
        existing=read_private(file)
        if existing['url']!=url:raise RelayError('A different native connection is already configured; preserve it and review before replacing.')
        return existing
    value={'v':1,'url':url,'phone_token':secrets.token_urlsafe(32),'laptop_token':secrets.token_urlsafe(32),'key':encode(secrets.token_bytes(32))}
    save_private(file,value);return value


@contextmanager
def receiver_lease(root):
    import msvcrt
    folder=Path(root)/'cache'/'phone-native';folder.mkdir(parents=True,exist_ok=True)
    with (folder/'receiver.lock').open('a+b') as handle:
        handle.seek(0,2)
        if not handle.tell():handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RelayError('The StoryLens Android connection is already running. Open the app on your phone.') from None
        try:yield
        finally:
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)


def serve(root,config):
    with receiver_lease(root):
        _serve(root,config)


def _serve(root,config):
    companion=NativeCompanion(root)
    client=RelayClient(config['url'],config['laptop_token']);cipher=Cipher(decode(config['key'],32))
    folder=Path(root)/'cache'/'phone-native';status=folder/'status.json'
    write(folder/'runtime.json',{'pid':os.getpid(),'root':str(Path(root).resolve()),'relay':config['url']})
    recent={};last_prune=0
    print('StoryLens native phone connection is running. No VPN or browser is required on the phone.',flush=True)
    while True:
        try:
            reply=client.request('GET','/v1/pull?wait=20')
            frames=reply.get('messages')
            if not isinstance(frames,list) or len(frames)>64:raise RelayError('The relay returned an invalid response.')
            write(status,{'state':'connected','checked':time.time(),'relay':config['url'],'pid':os.getpid()})
            for frame in frames:
                try:
                    request=cipher.decrypt(frame)
                    if set(request)!={'id','method','params'} or not isinstance(request['method'],str):raise RelayError('Unsupported encrypted request.')
                    identity=request['id'];fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
                    if identity in recent:
                        old=recent[identity]
                        if old['fingerprint']!=fingerprint:raise RelayError('Request identity conflict.')
                        response=old['response']
                    else:
                        try:
                            result=companion.dispatch(request['method'],request['params'])
                            payload={'id':identity,'ok':True,'result':result}
                        except Exception as error:
                            from .user_messages import problem
                            issue=problem(error)
                            payload={'id':identity,'ok':False,'error':{'message':issue['message'],'code':getattr(error,'code','phone_native')}}
                        try:response=cipher.encrypt(payload)
                        except RelayError:response=cipher.encrypt({'id':identity,'ok':False,'error':{'message':'This result is too large for the phone. Review the full saved result on your laptop.','code':'phone_result_large'}})
                        recent[identity]={'fingerprint':fingerprint,'response':response,'created':time.time()}
                    client.request('POST','/v1/push',response)
                except (RelayError,PhoneError):
                    write(status,{'state':'message_rejected','checked':time.time(),'message':'An invalid or unconfirmed phone frame was not executed. Check the app and saved chat.','pid':os.getpid()})
            if time.time()-last_prune>60:
                recent={key:value for key,value in recent.items() if value['created']>time.time()-300}
                last_prune=time.time()
                for metadata in companion.uploads.glob('*.json'):
                    try:
                        saved=json.loads(metadata.read_text('utf-8'))
                        if saved['created']<time.time()-86400:
                            metadata.with_suffix('.part').unlink(missing_ok=True);metadata.unlink()
                    except (OSError,ValueError,KeyError):pass
        except RelayError:
            write(status,{'state':'offline','checked':time.time(),'message':'Private relay disconnected. Existing laptop jobs are preserved.','pid':os.getpid()})
            time.sleep(3)


def main():
    parser=argparse.ArgumentParser(description='Personal StoryLens native Android connection')
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--url')
    parser.add_argument('--pair',action='store_true')
    parser.add_argument('--relay-hashes',action='store_true')
    parser.add_argument('--init',action='store_true')
    args=parser.parse_args()
    config=configure(args.root,args.url) if args.url else read_private(config_path(args.root))
    if args.relay_hashes:
        print(json.dumps({'PHONE_TOKEN_HASH':hashlib.sha256(config['phone_token'].encode()).hexdigest(),'LAPTOP_TOKEN_HASH':hashlib.sha256(config['laptop_token'].encode()).hexdigest()}));return
    if args.pair:
        pairing={'v':1,'url':config['url'],'token':config['phone_token'],'key':config['key']}
        print('SL1.'+encode(json.dumps(pairing,separators=(',',':')).encode()));return
    if args.init:
        print('Private connection keys saved for the signed-in Windows user.');return
    serve(args.root,config)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except (OSError,ValueError,PhoneError) as error:
        print('Native phone connection needs attention: '+str(error),file=sys.stderr,flush=True)
        raise SystemExit(1) from None
