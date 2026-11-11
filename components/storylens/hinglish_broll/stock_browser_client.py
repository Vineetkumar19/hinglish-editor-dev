"""Local worker client for the opt-in stock Chrome bridge; no cloud/API/Vision."""
from pathlib import Path
from urllib.parse import urlparse,quote
import hashlib,time
import requests
from .recovery import read_json
from .stock import Candidate

class BrowserSearch:
    def __init__(self,folder):
        folder=Path(folder).resolve();self.root=None;self.url='';self.token='';self.message=''
        for parent in (folder,*folder.parents):
            if folder.is_relative_to(parent/'output/broll') and (parent/'cache/stock-browser/connection.json').is_file():self.root=parent;break
        if self.root is None:return
        value=read_json(self.root/'cache/stock-browser/connection.json',{}).get('url','');p=urlparse(value)
        if p.scheme!='http' or p.hostname!='127.0.0.1' or p.username or p.password or p.path not in ('','/') or p.query or p.fragment or not p.port or not 1024<=p.port<=65535:raise ValueError('Reconnect Stock Chrome from your local Storylens editor.')
        self.url=value.rstrip('/');self.token=read_json(self.root/'cache/app/bridge.json',{}).get('token','')
        self.session=requests.Session();self.session.trust_env=False

    def _api(self,path,body=None):
        r=self.session.request('GET' if body is None else 'POST',self.url+'/api/stock-browser'+path,
            json=body,headers={'X-Hinglish-Token':self.token},timeout=(2,6),allow_redirects=False)
        r.raise_for_status();return r.json()

    def parallel_supported(self):
        if not self.url or not self.token:return False
        try:
            status=self._api('');version=tuple(int(v) for v in status.get('version','').split('.'))
            return bool(status.get('connected') and status.get('parallel_provider_claims') and version>=(0,1,2))
        except (requests.RequestException,ValueError):return False

    def search(self,provider,query,orientation,limit=6):
        if not self.url or not self.token:return None
        status=self._api('')
        if not status.get('connected') or provider not in status.get('providers',[]):return None
        job=self._api('/request',{'provider':provider,'query':query,'orientation':orientation,'limit':limit});deadline=time.monotonic()+125
        while time.monotonic()<deadline:
            result=self._api('/job?id='+quote(job['id'],safe=''))
            if result.get('status') not in ('queued','running'):break
            time.sleep(.6)
        else:raise ValueError('Stock Chrome did not finish this keyword; other websites continue.')
        self.message=result.get('message','')
        if result.get('status') not in ('complete','needs_verification'):raise ValueError(self.message or 'Stock Chrome could not finish this source.')
        from hinglish_app.stock_browser import public_result
        found=[]
        for raw in result.get('results',[])[:limit]:
            row=public_result(provider,{k:v for k,v in raw.items() if k!='provider'})
            if row['width'] and row['height'] and (orientation=='vertical' and row['height']<=row['width'] or orientation=='horizontal' and row['width']<=row['height']):continue
            found.append(Candidate(provider+'_browser',provider+':'+hashlib.sha256(row['page_url'].encode()).hexdigest()[:24],row['title'],row['duration'],row['width'],row['height'],
                thumb=row['thumbnail'],download_url=row['media_url'],page_url=row['page_url'],query=query,
                license=provider.title()+' video · check source licence and third-party rights',
                license_url='https://www.pexels.com/license/' if provider=='pexels' else 'https://pixabay.com/service/license-summary/'))
        return found
