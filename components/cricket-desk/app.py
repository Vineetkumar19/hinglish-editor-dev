from pathlib import Path
import sqlite3,json,hashlib,time,threading,datetime as dt,re,html,urllib.parse as U,xml.etree.ElementTree as ET,secrets,sys,os,zipfile,io
from html.parser import HTMLParser
from contextlib import contextmanager
import requests
import research
import social
import selected_assets
from flask import Flask,request,jsonify,send_from_directory,abort,render_template_string
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data';DATA.mkdir(exist_ok=True);(DATA/'media').mkdir(exist_ok=True);(DATA/'exports').mkdir(exist_ok=True)
DB=DATA/'inbox.sqlite3';TOKEN=secrets.token_urlsafe(28);LOCK=threading.Lock();SCAN=threading.Lock();SESSION=requests.Session();SESSION.headers['User-Agent']='CricketResearchInbox/1.0 (personal owner research)'
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=2*1024*1024
N={'a':'http://www.w3.org/2005/Atom'}
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
@contextmanager
def db():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
 try:
  yield c;c.commit()
 except Exception:
  c.rollback();raise
 finally:c.close()
def init():
 with db() as c:
  c.executescript('CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,url TEXT UNIQUE,title TEXT,platform TEXT,event TEXT,kind TEXT,published TEXT,discovered TEXT,thumbnail TEXT,media_url TEXT,media_path TEXT,author TEXT,summary TEXT,review TEXT DEFAULT "new",decision_author TEXT,source TEXT,metadata TEXT);CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,started TEXT,finished TEXT,result TEXT);')
  c.execute('INSERT OR IGNORE INTO state VALUES(?,?)',('config',json.dumps({'mode':'auto','event':'','interval_minutes':30,'enabled':True})))
def get(k,default=None):
 with db() as c:r=c.execute('SELECT value FROM state WHERE key=?',(k,)).fetchone()
 return json.loads(r[0]) if r else default
def put(k,v):
 with db() as c:c.execute('INSERT OR REPLACE INTO state VALUES(?,?)',(k,json.dumps(v)))
def platform(url):
 try:
  p=U.urlsplit(url);h=(p.hostname or '').lower()
  if p.scheme!='https' or p.username or p.password:return None
  direct=social.direct_url(url)
  if direct:return direct[0]
  if h.removeprefix('www.').removeprefix('mobile.') in ['x.com','twitter.com','instagram.com']:return None
  if (h=='reddit.com' or h.endswith('.reddit.com')) and '/comments/' in p.path:return 'Reddit'
  if h in ['news.google.com','www.espncricinfo.com','www.icc-cricket.com','www.bcci.tv','www.iplt20.com','www.cricbuzz.com']:return 'News'
  domains=get('config',{}).get('domains',[])
  if any(h==d or h.endswith('.'+d)for d in domains):return 'News'
 except ValueError:pass
 return None
def canonical(url):
 direct=social.direct_url(url)
 if direct:return direct[1].replace('www.','').rstrip('/')
 p=U.urlsplit(url);h=(p.hostname or '').lower().replace('www.','').replace('twitter.com','x.com');path=p.path.rstrip('/')
 if '/status/' in path:path=path.split('/status/')[0]+'/status/'+path.split('/status/')[1].split('/')[0]
 if 'instagram.com' in h:path='/'.join(path.split('/')[:3])
 return 'https://'+h+path

def ingest(rows,source='feed',author='collector'):
 count=0
 with db() as c:
  for x in rows[:200]:
   url=x.get('url','');plat=platform(url)
   if not plat:continue
   url=canonical(url);ident=hashlib.sha256(url.encode()).hexdigest()[:20]
   thumb=x.get('thumbnail','');media=x.get('media_url','');pub=x.get('published','')
   if not media_allowed(thumb):thumb=''
   if not media_allowed(media):media=''
   # Preserve publication evidence. Discovery time is never substituted for unknown publication time.
   c.execute('INSERT OR IGNORE INTO items(id,url,title,platform,event,kind,published,discovered,thumbnail,media_url,media_path,author,summary,decision_author,source,metadata) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,url,str(x.get('title','Untitled source post'))[:500],plat,str(x.get('event',''))[:300],x.get('kind','meme' if plat=='Reddit' else 'unclassified'),str(pub)[:80],now(),str(thumb)[:2000],str(media)[:2000],'',str(x.get('author',''))[:200],str(x.get('summary',''))[:2000],author,source,json.dumps(x,ensure_ascii=False)))
   count+=c.execute('SELECT changes()').fetchone()[0]
   if media:c.execute('UPDATE items SET media_url=?,thumbnail=CASE WHEN ?!="" THEN ? ELSE thumbnail END WHERE id=?',(media,thumb,thumb,ident))
 return count
class Extract(HTMLParser):
 def __init__(self):super().__init__();self.images=[];self.links=[];self.text=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img' and a.get('src'):self.images.append(html.unescape(a['src']))
  if tag=='a' and a.get('href'):self.links.append(html.unescape(a['href']))
 def handle_data(self,data):self.text.append(data)
def fetch(url):
 r=SESSION.get(url,timeout=18);r.raise_for_status()
 if len(r.content)>3*1024*1024:raise ValueError('Feed exceeds3MB bound')
 return ET.fromstring(r.content)
def rss_rows(root,event='',source=''):
 out=[]
 for x in root.findall('.//item')[:30]:
  url=x.findtext('link','');title=x.findtext('title','');pub=x.findtext('pubDate','')
  out.append({'url':url,'title':title,'published':pub,'event':event,'kind':'news' if source=='news'else'unclassified'})
 return out
def reddit_rows(root,event=''):
 out=[]
 for x in root.findall('a:entry',N)[:40]:
  title=x.findtext('a:title','',N);link=x.find('a:link',N);parser=Extract();parser.feed(x.findtext('a:content','',N));url=link.get('href','')if link is not None else''
  if event and not any(w in (' '.join([title,*parser.text])).lower() for w in event.lower().split() if len(w)>3):continue
  images=[i for i in parser.images if media_allowed(i)];originals=[i for i in parser.links if media_allowed(i) and 'i.redd.it' in U.urlsplit(i).netloc]
  out.append({'url':url,'title':title,'published':x.findtext('a:published','',N) or x.findtext('a:updated','',N),'event':event,'thumbnail':images[0]if images else'','media_url':originals[0]if originals else(images[0]if images else''),'author':x.findtext('a:author/a:name','',N),'kind':'meme','summary':'Public subreddit candidate; humour/claims need owner review.'})
 return out
def media_allowed(url):
 try:
  p=U.urlsplit(url);h=(p.hostname or '').lower();return p.scheme=='https' and not p.username and not p.password and any(h==d or h.endswith('.'+d)for d in ['redd.it','redditmedia.com','twimg.com','cdninstagram.com','fbcdn.net'])
 except ValueError:return False
def collect():
 if not SCAN.acquire(False):return {'status':'already_running'}
 started=now();status=[];total=0;cfg=get('config');event=cfg['event'].strip()if cfg['mode']=='manual'else''
 try:
  domains=cfg.get('domains',research.DEFAULTS['domains']);q=(event or 'cricket')+' when:2d';news=[]
  authorities=[d for d in domains if d not in ['instagram.com','x.com','twitter.com','reddit.com']]
  if authorities:q+=' ('+' OR '.join('site:'+d for d in authorities)+')'
  try:
   if not authorities:raise ValueError('News domains disabled by owner')
   news=rss_rows(fetch('https://news.google.com/rss/search?'+U.urlencode({'q':q,'hl':'en-IN','gl':'IN','ceid':'IN:en'})),event,'news');total+=ingest(news,'Google News RSS');status.append({'source':'News','ok':True,'found':len(news)})
  except Exception as e:status.append({'source':'News','ok':False,'error':str(e)})
  for sub in (['CricketShitpost','Cricket']if 'reddit.com' in domains else[]):
   try:
    url='https://www.reddit.com/r/'+sub+('/search.rss?'+U.urlencode({'q':event,'restrict_sr':'on','sort':'new','t':'week'})if event else'/new/.rss')
    rows=reddit_rows(fetch(url),event);total+=ingest(rows,'Reddit public Atom');status.append({'source':'r/'+sub,'ok':True,'found':len(rows)})
   except Exception as e:status.append({'source':'r/'+sub,'ok':False,'error':str(e)})
  rows,social_status=social.collect(cfg,'cricket',ROOT,media_allowed)
  total+=ingest(rows,'Public browser discovery')
  status.extend(social_status)
  put('social_receipt',{'finished':now(),'sources':social_status})
  result={'status':'complete','new_items':total,'sources':status,'mode':cfg['mode'],'event':event,'finished':now()};put('last_scan',result);put('discovery_hints',news[:8])
  with db() as c:c.execute('INSERT INTO runs(started,finished,result)VALUES(?,?,?)',(started,now(),json.dumps(result)))
  return result
 finally:SCAN.release()
def download(ident):
 with db() as c:x=c.execute('SELECT * FROM items WHERE id=?',(ident,)).fetchone()
 if not x:raise ValueError('Missing item')
 url=x['media_url']
 if not media_allowed(url):raise ValueError('No accessible direct image yet. Open source or use a GPT/browser research pass; login/private posts are not bypassed.')
 r=SESSION.get(url,timeout=25,stream=True,allow_redirects=False)
 if r.status_code in [301,302,303,307,308]:raise ValueError('Media redirected; needs a fresh source URL')
 r.raise_for_status();buf=io.BytesIO()
 for chunk in r.iter_content(65536):
  buf.write(chunk)
  if buf.tell()>25*1024*1024:raise ValueError('Image exceeds25MB limit')
 from PIL import Image
 im=Image.open(io.BytesIO(buf.getvalue()));im.verify();im=Image.open(io.BytesIO(buf.getvalue()));im.thumbnail((4096,4096));p=DATA/'media'/(ident+'.png');im.convert('RGB').save(p)
 with db() as c:c.execute('UPDATE items SET media_path=? WHERE id=?',(str(p),ident))
 return str(p)
def export():
 stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S');folder=DATA/'exports'/stamp;folder.mkdir()
 with db() as c:rows=[dict(x)for x in c.execute('SELECT * FROM items WHERE review="keep" ORDER BY discovered DESC')]
 import shutil
 for x in rows:
  if x['media_path'] and Path(x['media_path']).is_file():shutil.copy2(x['media_path'],folder/Path(x['media_path']).name)
 (folder/'sources.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf8')
 (folder/'README.txt').write_text('Owner-selected research material. Source links and attribution preserved. Memes/rumours are not verified news. Unavailable media remains a source link. No posting performed.',encoding='utf8')
 return {'folder':str(folder),'items':len(rows),'images':len(list(folder.glob('*.png')))}
@app.before_request
def protect():
 if request.host.split(':')[0] not in ['127.0.0.1','localhost']:abort(403)
 if request.method=='POST' and request.headers.get('X-Inbox-Token')!=TOKEN:abort(403)
@app.get('/')
def index():return render_template_string((ROOT/'index.html').read_text(encoding='utf8'),token=TOKEN)
@app.get('/api/state')
def state():
 with db() as c:rows=[dict(x)for x in c.execute('SELECT * FROM items ORDER BY discovered DESC LIMIT 1000')]
 return jsonify(config=get('config'),items=rows,last_scan=get('last_scan'),hints=get('discovery_hints',[]),gpt_request=get('gpt_request'),gpt_receipt=get('gpt_receipt'),scanning=SCAN.locked(),gpt_usage=get('gpt_usage'),gpt_running=research.LOCK.locked(),social_receipt=get('social_receipt'),collection_browser=social.browser_state())
@app.get('/api/selected')
def selected():return jsonify(selected_assets.manifest(db,ROOT,request.args.get('q','')[:300]))
@app.post('/api/selected/prepare')
def prepare_selected():
 try:return jsonify(selected_assets.prepare(db,ROOT,download,(request.get_json(silent=True)or{}).get('ids')))
 except Exception as e:return jsonify(error=str(e)),400
@app.get('/health')
def health():return jsonify(app='cricket-meme-inbox',ok=True)
@app.post('/api/config')
def config():
 try:
  x=request.get_json();c=research.validate(x,get('config'));c.update(mode='manual'if x.get('mode')=='manual'else'auto',event=str(x.get('event',''))[:300],enabled=bool(x.get('enabled',False)),interval_minutes=max(15,min(1440,int(x.get('interval_minutes',30)))))
  put('config',c)
  if not c['gpt_enabled']:research.cancel()
  return jsonify(c)
 except Exception as e:return jsonify(error='Invalid settings: '+str(e)),400
@app.post('/api/scan')
def scan():threading.Thread(target=collect,daemon=True).start();return jsonify(started=True)
@app.post('/api/browser/connect')
def browser_connect():
 threading.Thread(target=social.connect_browser,daemon=True).start()
 return jsonify(started=True)
@app.post('/api/browser/finish')
def browser_finish():
 social.SETUP_FINISH.set()
 return jsonify(requested=True)
@app.post('/api/social')
def social_scan():
 def run():
  if not SCAN.acquire(False):return
  try:
   rows,status=social.collect(get('config'),'cricket',ROOT,media_allowed)
   added=ingest(rows,'Public browser discovery')
   receipt={'finished':now(),'new_items':added,'sources':status}
   put('social_receipt',receipt)
   last=get('last_scan',{})
   last['sources']=[s for s in last.get('sources',[]) if s.get('source') not in ['X','Instagram']]+status
   put('last_scan',last)
  finally:SCAN.release()
 threading.Thread(target=run,daemon=True).start()
 return jsonify(started=True)
@app.post('/api/add')
def add():
 x=request.get_json()
 if not platform(x.get('url','')):return jsonify(error='Use a direct Instagram / X / Reddit post URL.'),400
 return jsonify(added=ingest([dict(x,event=get('config')['event'])],'Owner added link','owner'))
@app.post('/api/gpt')
def gpt():
 if not get('config').get('gpt_enabled'):return jsonify(error='GPT research is OFF. Enable it and save settings first.'),400
 threading.Thread(target=research.run,args=(put,get,ingest,True),daemon=True).start();return jsonify(started=True)
@app.post('/api/review')
def review():
 x=request.get_json();v=x.get('review');assert v in ['new','keep','reject']
 with db() as c:c.execute('UPDATE items SET review=? WHERE id=?',(v,x['id']))
 selected_assets.sync(db,ROOT)
 return jsonify(ok=True)
@app.post('/api/download')
def media():
 try:return jsonify(path=download(request.get_json()['id']))
 except Exception as e:return jsonify(error=str(e)),400
@app.post('/api/export')
def exports():return jsonify(export())
@app.get('/media/<name>')
def mediafile(name):return send_from_directory(DATA/'media',name)
def worker():
 while True:
  cfg=get('config');last=get('last_scan',{}).get('finished');due=not last or (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(last)).total_seconds()>cfg['interval_minutes']*60
  if cfg['enabled'] and due:
   try:collect()
   except Exception as e:put('worker_error',{'at':now(),'error':str(e)})
  if cfg.get('gpt_enabled') and research.slot(cfg) and research.slot(cfg)!=get('gpt_last_slot') and not research.LOCK.locked():
   threading.Thread(target=research.run,args=(put,get,ingest),daemon=True).start()
  time.sleep(30)
if __name__=='__main__':
 init()
 selected_assets.sync(db,ROOT)
 cfg={**research.DEFAULTS,**get('config',{})}
 if cfg.get('consent_revision')!='20261104-owner-controls':cfg.update(enabled=False,gpt_enabled=False,consent_revision='20261104-owner-controls')
 put('config',cfg)
 if '--collect' in sys.argv:print(json.dumps(collect(),indent=2))
 elif '--import' in sys.argv:
  p=Path(sys.argv[sys.argv.index('--import')+1]);print('New candidates:',ingest(json.loads(p.read_text(encoding='utf-8-sig')),'GPT/browser research','GPT'))
 elif '--export' in sys.argv:print(json.dumps(export()))
 else:
  try:
   if requests.get('http://127.0.0.1:8879/health',timeout=1).json().get('app')=='cricket-meme-inbox':sys.exit(0)
  except requests.RequestException:pass
  threading.Thread(target=worker,daemon=True).start();app.run('127.0.0.1',8879,threaded=True,use_reloader=False)
