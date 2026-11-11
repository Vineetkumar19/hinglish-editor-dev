import requests,json
from pathlib import Path
urls={'news':'https://news.google.com/rss/search?q=cricket+when:2d&hl=en-IN&gl=IN&ceid=IN:en','reddit':'https://www.reddit.com/r/CricketShitpost/new/.rss','bing':'https://www.bing.com/search?format=rss&q=cricket+meme+site%3Ax.com%2Fstatus'}
out={}
for k,u in urls.items():
 try:
  r=requests.get(u,headers={'User-Agent':'CricketResearchInbox/1.0 (personal research)'},timeout=20);out[k]={'status':r.status_code,'type':r.headers.get('Content-Type'),'bytes':len(r.content)};Path(__file__).with_name(k+'-sample.txt').write_text(r.text[:100000],encoding='utf8')
 except Exception as e:out[k]={'error':str(e)}
print(json.dumps(out));Path(__file__).with_name('source-probe.json').write_text(json.dumps(out,indent=2))
