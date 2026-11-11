"""Bounded public downloads: DNS is pinned to each actual connection/redirect."""
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import urljoin,urlsplit,urlunsplit

def public_ip(value):
    try:
        address=ipaddress.ip_address(value)
        return address.is_global and not (address.is_multicast or address.is_reserved or address.is_unspecified)
    except ValueError:return False

def validate_url(url):
    if not isinstance(url,str) or not 0<len(url)<=4096 or any(ord(c)<=32 for c in url):
        raise ValueError('Photo source invalid: use a public web image source.')
    parsed=urlsplit(url)
    try:port=parsed.port
    except ValueError:raise ValueError('Photo source invalid: use a public web image source.')
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or port not in (None,80,443):
        raise ValueError('Photo source invalid: only public HTTP or HTTPS sources are supported.')
    host=parsed.hostname.encode('idna').decode('ascii')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host.lower()=='localhost' or host.lower().endswith(('.localhost','.local','.internal')):
            raise ValueError('Photo source blocked: only public web sources are supported.')
    else:
        if not public_ip(host):raise ValueError('Photo source blocked: only public web sources are supported.')
    return parsed,host,port or (443 if parsed.scheme=='https' else 80)

def resolve(host,port):
    return list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)))

def connect(url,address,timeout):
    parsed,host,port=validate_url(url)
    raw=socket.create_connection((address,port),timeout=timeout)
    try:
        if parsed.scheme=='https':
            context=ssl.create_default_context()
            raw=context.wrap_socket(raw,server_hostname=host)
            connection=http.client.HTTPSConnection(host,port,timeout=timeout,context=context)
        else:connection=http.client.HTTPConnection(host,port,timeout=timeout)
        connection.sock=raw
        path=urlunsplit(('','',parsed.path or '/',parsed.query,''))
        connection.request('GET',path,headers={'Host':host,'User-Agent':'Mozilla/5.0 Storylens PhotoCollector',
            'Accept':'image/avif,image/webp,image/*,text/html;q=0.5,*/*;q=0.1','Accept-Encoding':'identity'})
        return connection.getresponse(),connection
    except BaseException:
        raw.close();raise

class Fetcher:
    def __init__(self,resolver=resolve,opener=connect,*,max_total=350*1024*1024,cancel=None):
        self.resolver,self.opener=resolver,opener
        self.max_total=max_total;self.total=0;self.lock=threading.Lock();self.cancel=cancel

    def get(self,url,limit=25*1024*1024,kind='image'):
        started=time.monotonic()
        for redirect in range(6):
            if self.cancel and self.cancel.is_set():raise InterruptedError('Photo collection cancelled; saved photos are kept.')
            parsed,host,port=validate_url(url)
            addresses=self.resolver(host,port)
            if not addresses or any(not public_ip(address) for address in addresses):
                raise ValueError('Photo source blocked: only public web sources are supported.')
            response,connection=self.opener(url,addresses[0],15)
            try:
                if response.status in (301,302,303,307,308):
                    location=response.getheader('Location')
                    if not location:raise ValueError('Photo source unavailable: its redirect has no destination.')
                    url=urljoin(url,location);continue
                if response.status!=200:raise ValueError(f'Photo source unavailable: the publisher returned HTTP {response.status}; saved progress is kept.')
                mime=(response.getheader('Content-Type','') or '').split(';')[0].lower()
                if kind=='image' and not mime.startswith('image/'):
                    raise ValueError('Photo source not an image: the publisher returned a page instead of a photo.')
                length=response.getheader('Content-Length')
                if length and int(length)>limit:raise ValueError('Photo source too large: this file exceeds the per-photo limit.')
                chunks=[];size=0
                while True:
                    if self.cancel and self.cancel.is_set():raise InterruptedError('Photo collection cancelled; saved photos are kept.')
                    if time.monotonic()-started>50:raise TimeoutError('Photo source timed out; the remaining collection can continue.')
                    block=response.read(min(65536,limit-size+1))
                    if not block:break
                    size+=len(block)
                    if size>limit:raise ValueError('Photo source too large: the download exceeded its file limit.')
                    with self.lock:
                        self.total+=len(block)
                        if self.total>self.max_total:raise ValueError('Photo collection limit reached: saved photos and sources are kept.')
                    chunks.append(block)
                return {'data':b''.join(chunks),'url':url,'mime':mime}
            finally:
                response.close();connection.close()
        raise ValueError('Photo source unavailable: too many redirects; use the saved source information.')
