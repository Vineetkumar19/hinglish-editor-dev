"""Narrow, durable Chrome queue for public Pexels/Pixabay VIDEO pages only.

The separate extension receives keywords, never model code, owner files,
cookies, account state or general browser commands. Site verification stays
with the human. This capability cannot publish or access other Storylens tools.
"""
from pathlib import Path
from urllib.parse import urlparse
import json,math,re,secrets,threading,time,uuid
from hinglish_broll.recovery import read_json,write_json

_SERVICES={};_LOCK=threading.RLock()
PROVIDERS=('pexels','pixabay')


def valid_page(provider,url):
    if not isinstance(url,str):return False
    p=urlparse(url)
    return p.scheme=='https' and ((provider=='pexels' and p.netloc=='www.pexels.com' and re.fullmatch(r'/video/[a-z0-9-]+-\d+/',p.path)) or
        (provider=='pixabay' and p.netloc=='pixabay.com' and re.fullmatch(r'/videos/[a-z0-9-]+-\d+/',p.path)))


def public_result(provider,row):
    if not isinstance(row,dict) or set(row)-{'page_url','media_url','title','width','height','duration','thumbnail'}:
        raise ValueError('The stock connector returned unsupported fields.')
    url=row.get('media_url','');p=urlparse(url) if isinstance(url,str) else None
    host='videos.pexels.com' if provider=='pexels' else 'cdn.pixabay.com'
    if not valid_page(provider,row.get('page_url')) or not p or p.scheme!='https' or p.netloc!=host or not p.path.lower().endswith('.mp4') or len(url)>4096:
        raise ValueError('Choose public video pages and advertised media from the requested stock site.')
    dims={}
    for key in ('width','height'):
        n=row.get(key,0)
        if type(n) is not int or not 0<=n<=16384:raise ValueError('The stock video dimensions are unreadable.')
        dims[key]=n
    duration=row.get('duration',0)
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 0<=duration<=1800:raise ValueError('The stock video duration is unreadable.')
    title=row.get('title','')
    if not isinstance(title,str) or len(title)>300:raise ValueError('The stock video title is unreadable.')
    thumbnail=row.get('thumbnail','');tp=urlparse(thumbnail) if isinstance(thumbnail,str) else None
    if thumbnail and (not tp or tp.scheme!='https' or tp.netloc not in ('images.pexels.com','cdn.pixabay.com')):thumbnail=''
    return {'provider':provider,'page_url':row['page_url'],'media_url':url,'title':title,
            **dims,'duration':float(duration),'thumbnail':thumbnail}


class StockBrowser:
    def __init__(self,root,*,clock=time.time,port=8765):
        self.root=Path(root).resolve();self.clock=clock;self.lock=threading.RLock()
        self.folder=self.root/'cache/stock-browser';self.folder.mkdir(parents=True,exist_ok=True)
        self.file=self.folder/'state.json';self.data=read_json(self.file,{})
        self.data.setdefault('key',secrets.token_urlsafe(32));self.data.setdefault('jobs',[])
        self.data.setdefault('seen',0);self.data.setdefault('client','');self.data.setdefault('providers',[])
        self.port=port;self._save()
        write_json(self.folder/'connection.json',{'url':f'http://127.0.0.1:{port}'})

    def _save(self):write_json(self.file,self.data)

    def authorized(self,key):return bool(key) and secrets.compare_digest(str(key),self.data['key'])

    def pairing(self):
        return {'port':self.port,'key':self.data['key'],
            'extension_folder':str(self.root/'editor_plugins/storylens-stock-chrome')}

    def status(self):
        connected=bool(self.data['client']) and self.clock()-self.data['seen']<75
        return {'connected':connected,'providers':self.data['providers'] if connected else [],'parallel_provider_claims':True,
                'version':self.data.get('version',''),'message':'Stock Chrome connected' if connected else 'Connect Stock Chrome to search Pexels and Pixabay in your browser.'}

    def hello(self,client,version,providers):
        if not isinstance(client,str) or not re.fullmatch(r'[a-zA-Z0-9-]{6,80}',client):raise ValueError('Reconnect this stock extension.')
        if not isinstance(providers,list) or any(p not in PROVIDERS for p in providers):raise ValueError('Enable only Pexels/Pixabay video access.')
        with self.lock:
            if self.status()['connected'] and self.data['client']!=client:raise ValueError('Another stock Chrome connection is active. Disconnect it before pairing this profile.')
            self.data.update(client=client,seen=self.clock(),version=str(version)[:30],providers=list(dict.fromkeys(providers)))
            self._save();return self.status()

    def _client(self,client):
        if client!=self.data['client'] or not self.status()['connected']:raise ValueError('Reconnect this stock extension before reading its queue.')
        self.data['seen']=self.clock()

    def _expire(self):
        for job in self.data['jobs']:
            if job['status'] in ('queued','running') and self.clock()>job['deadline']:
                job.update(status='failed',message='The browser search did not finish in time. Other websites continue; your collected clips are kept.')

    def request(self,provider,query,orientation,limit=6):
        if provider not in PROVIDERS or orientation not in (None,'vertical','horizontal') or type(limit) is not int or not 1<=limit<=6:
            raise ValueError('Choose Pexels/Pixabay, a video format and up to six options.')
        if not isinstance(query,str) or not query.strip() or len(query)>120 or any(ord(c)<32 for c in query):raise ValueError('Use a short stock-video keyword.')
        with self.lock:
            self._expire()
            if not self.status()['connected'] or provider not in self.data['providers']:raise ValueError('Connect Stock Chrome and enable this website first.')
            query=query.strip()
            for job in reversed(self.data['jobs']):
                if (job['provider'],job['query'],job['orientation'],job['limit'])==(provider,query,orientation,limit):
                    if job['status'] in ('queued','running') or job['status']=='complete' and job.get('results') and self.clock()-job['created']<86400:return dict(job)
            job={'id':uuid.uuid4().hex,'provider':provider,'query':query,'orientation':orientation,'limit':limit,
                 'status':'queued','created':self.clock(),'deadline':self.clock()+120,'results':[]}
            self.data['jobs']=[j for j in self.data['jobs'] if j['status'] in ('queued','running')]+[j for j in self.data['jobs'] if j['status'] not in ('queued','running')][-60:]
            self.data['jobs'].append(job);self._save();return dict(job)

    def claim(self,client,provider=None):
        with self.lock:
            self._client(client);self._expire()
            if provider is not None and provider not in PROVIDERS:raise ValueError('Choose Pexels or Pixabay video search.')
            if any(j.get('client')==client and j['status']=='running' and (provider is None or j['provider']==provider) for j in self.data['jobs']):self._save();return None
            for job in self.data['jobs']:
                if job['status']=='queued' and job['provider'] in self.data['providers'] and (provider is None or job['provider']==provider):
                    job.update(status='running',client=client,lease=secrets.token_urlsafe(24),deadline=self.clock()+120);self._save()
                    return {k:job[k] for k in ('id','provider','query','orientation','limit','lease')}
            self._save();return None

    def finish(self,client,job_id,lease,results,*,state='complete',message=''):
        with self.lock:
            self._client(client);self._expire()
            job=next((j for j in self.data['jobs'] if j['id']==job_id),None)
            if not job or job.get('client')!=client or not secrets.compare_digest(str(job.get('lease','')),str(lease)) or job['status']!='running':raise ValueError('This browser receipt does not belong to the active search.')
            if state not in ('complete','needs_verification','failed'):raise ValueError('Return a supported stock search status.')
            if not isinstance(results,list) or len(results)>24:raise ValueError('Return a bounded list of public video choices.')
            checked=[public_result(job['provider'],r) for r in results]
            seen=set();unique=[]
            for row in checked:
                if row['media_url'] not in seen:seen.add(row['media_url']);unique.append(row)
            job.update(status=state,results=unique[:job['limit']],message=(
                'Complete the website verification in the Stock Chrome tab yourself; other websites can continue.' if state=='needs_verification' else
                'Browser video search finished.' if state=='complete' else 'Chrome could not finish this source. Other websites continue.'))
            if state=='failed':job['technical_details']=str(message)[:700]
            self._save();return self.snapshot(job_id)

    def snapshot(self,job_id):
        with self.lock:
            self._expire()
            job=next((j for j in self.data['jobs'] if j['id']==job_id),None)
            if not job:raise ValueError('Open a saved stock-browser search.')
            self._save();return {k:v for k,v in job.items() if k not in ('lease','client')}

    def disconnect(self):
        with self.lock:
            for job in self.data['jobs']:
                if job['status'] in ('queued','running'):job.update(status='failed',message='Stock Chrome was disconnected. Collected clips are kept.')
            self.data.update(key=secrets.token_urlsafe(32),client='',seen=0,providers=[]);self._save()
            return self.status()


def service(state):
    root=Path(state.root).resolve()
    with _LOCK:
        if root not in _SERVICES:_SERVICES[root]=StockBrowser(root,port=state.port)
        return _SERVICES[root]


def get(handler,state,parsed):
    from urllib.parse import parse_qs
    if not handler._authorized():return handler._json(403,{'error':'Reopen Stock Chrome from Storylens.'})
    bridge=service(state)
    if parsed.path=='/api/stock-browser':return handler._json(200,bridge.status())
    if parsed.path=='/api/stock-browser/pairing':return handler._json(200,bridge.pairing())
    if parsed.path=='/api/stock-browser/job':return handler._json(200,bridge.snapshot(parse_qs(parsed.query).get('id',[''])[0]))
    raise ValueError('Choose a stock-browser status action.')


def post(handler,state,path,value):
    bridge=service(state)
    if path=='/api/stock-browser/request':
        return handler._json(202,bridge.request(value.get('provider'),value.get('query'),value.get('orientation'),value.get('limit',6)))
    if path=='/api/stock-browser/disconnect':return handler._json(200,bridge.disconnect())
    raise ValueError('Choose a stock-browser connection action.')


def worker(handler,state):
    bridge=service(state);origin=handler.headers.get('Origin','')
    if not re.fullmatch(r'chrome-extension://[a-p]{32}',origin) or not bridge.authorized(handler.headers.get('X-Storylens-Stock','')):
        return handler._json(403,{'error':'Pair the separate Stock Chrome extension first.'})
    try:
        n=int(handler.headers.get('Content-Length','0'))
        if not 0<n<=65536:raise ValueError('Return one bounded stock-browser message.')
        value=json.loads(handler.rfile.read(n));action=handler.path.rsplit('/',1)[-1]
        allowed={'hello':{'client','version','providers'},'claim':{'client','provider'},
                 'finish':{'client','id','lease','results','state','message'}}
        if action not in allowed or not isinstance(value,dict) or set(value)-allowed[action]:raise ValueError('Choose a typed stock-browser operation.')
        if action=='hello':result=bridge.hello(value.get('client'),value.get('version'),value.get('providers'))
        elif action=='claim':result={'task':bridge.claim(value.get('client'),provider=value.get('provider'))}
        else:result=bridge.finish(value.get('client'),value.get('id'),value.get('lease'),value.get('results'),state=value.get('state','complete'),message=value.get('message',''))
        return handler._json(200,result)
    except (ValueError,KeyError,OSError) as error:return handler._json(400,{'error':error})
