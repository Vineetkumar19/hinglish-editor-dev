"""Public image/source search; no screenshot upload or authenticated accounts."""
import hashlib
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit,urlunsplit,parse_qsl,urlencode,unquote

from .network import validate_url

def indexed_images(html):
    """Read public image-index data without running page scripts."""
    if re.search(r'unusual traffic|/sorry/index|g-recaptcha|/httpservice/retry/enablejs',html,re.I):raise ValueError('Photo image index unavailable: the search provider requires an interactive browser check; continuing other public sources.')
    found=[];seen=set();thumbnail=None
    for match in re.finditer(r'\[\s*("https?[^"\n]*")\s*,\s*(\d{2,6})\s*,\s*(\d{2,6})\s*\]',html):
        try:
            encoded=re.sub(r'\\x([0-9a-fA-F]{2})',r'\\u00\1',match[1]);url=json.loads(encoded);validate_url(url)
        except (ValueError,TypeError):continue
        width,height=int(match[2]),int(match[3]);host=(urlsplit(url).hostname or '').lower()
        if host.endswith('.gstatic.com') or host.endswith('.googleusercontent.com'):
            if max(width,height)<640:thumbnail=url
            continue
        if max(width,height)<640 or min(width,height)<240 or url in seen:continue
        seen.add(url)
        found.append({'url':url,'thumbnail':thumbnail or url,'page':'','title':'Source photo','publisher':host,
            'width':width,'height':height,'license':'Usage rights unverified; check the image origin.'})
        thumbnail=None
    return sorted(found,key=lambda row:row['width']*row['height'],reverse=True)

def original_urls(url):
    """Try public delivery originals, never construct a larger rendition."""
    try:validate_url(url)
    except ValueError:return []
    parsed=urlsplit(url);host=(parsed.hostname or '').lower();path=parsed.path;query=parse_qsl(parsed.query,keep_blank_values=True)
    if any(re.search(r'token|signature|credential|expires|x-amz',key,re.I) for key,_ in query):return [url]
    variants=[]
    if host.endswith('pinimg.com') and re.match(r'^/(?:\d+x(?:\d+)?|\d+x_M[A-Z])/[^/]+/',path):
        variants.append(urlunsplit((parsed.scheme,parsed.netloc,re.sub(r'^/[^/]+/','/originals/',path),'','')))
    if host in ('images.hindustantimes.com','www.hindustantimes.com') and re.search(r'/rf/image_size_\d+x\d+/',path):
        original=re.sub(r'/rf/image_size_\d+x\d+/', '/rf/',path)
        variants.append(urlunsplit((parsed.scheme,parsed.netloc,original,parsed.query,'')))
    if host in ('img1.hscicdn.com','img2.hscicdn.com','res.cloudinary.com') and '/image/upload/' in path:
        prefix,tail=path.split('/image/upload/',1);parts=tail.split('/')
        while parts and re.match(r'^[a-z]{1,5}_',parts[0]):parts.pop(0)
        if parts:variants.append(urlunsplit((parsed.scheme,parsed.netloc,prefix+'/image/upload/'+'/'.join(parts),'','')))
    if host in ('images.news18.com','images.thequint.com','c.ndtvimg.com','akm-img-a-in.tosshub.com','images.indianexpress.com'):
        transforms={'w','h','width','height','resize','quality','q','fit','fmt','auto','impolicy','size','downsize'}
        clean=[(key,value) for key,value in query if key.lower() not in transforms]
        variants.append(urlunsplit((parsed.scheme,parsed.netloc,path,urlencode(clean),'')))
    if path=='/_next/image':
        target=dict(query).get('url')
        if target:
            direct=urljoin(url,target)
            try:validate_url(direct);variants.append(direct)
            except ValueError:pass
    return list(dict.fromkeys([*variants,url]))

class ImagesInPage(HTMLParser):
    def __init__(self,base):super().__init__(convert_charrefs=True);self.base=base;self.images=[]
    def handle_starttag(self,tag,attributes):
        data=dict(attributes);url=''
        if tag=='meta' and (data.get('property') or data.get('name') or '').lower() in ('og:image','og:image:url','twitter:image','twitter:image:src'):
            url=data.get('content','')
        elif tag=='img':
            url=data.get('data-full-url') or data.get('data-orig-file') or data.get('data-original') or data.get('data-src') or data.get('src','')
            source=data.get('srcset') or data.get('data-srcset')
            if source:
                rows=[part.strip().split() for part in source.split(',') if part.strip()]
                if rows:
                    def resolution(row):
                        try:return float(row[1].rstrip('wx')) if len(row)>1 else 0
                        except ValueError:return 0
                    url=max(rows,key=resolution)[0]
        if url:
            url=urljoin(self.base,url)
            try:validate_url(url)
            except ValueError:return
            for candidate in original_urls(url):
                if candidate not in self.images:self.images.append(candidate)

class Sources:
    def __init__(self,root,progress=print):
        from pathlib import Path
        self.root=Path(root);self.cache=Path(root)/'cache/photo-collector/search';self.cache.mkdir(parents=True,exist_ok=True)
        self.progress=progress
        self.index_unavailable=None

    def _search(self,kind,query,limit):
        key=hashlib.sha256(json.dumps([kind,query,limit]).encode()).hexdigest()
        path=self.cache/(key+'.json')
        if path.exists() and time.time()-path.stat().st_mtime<86400:
            value=json.loads(path.read_text('utf8'))
            if value:return value
        from ddgs import DDGS
        client=DDGS(timeout=18)
        if kind=='images':rows=list(client.images(query,max_results=limit,region='in-en',safesearch='moderate'))
        else:rows=list(client.text(query,max_results=limit,region='in-en',safesearch='moderate'))
        path.write_text(json.dumps(rows,ensure_ascii=False),'utf8')
        return rows

    def images(self,query,limit=40):
        rows=self._search('images',query,limit)
        found=[]
        for row in rows:
            url=row.get('image','');thumb=row.get('thumbnail') or url;page=row.get('url') or ''
            try:validate_url(url);validate_url(thumb)
            except ValueError:continue
            for original in original_urls(url):
                found.append({'url':original,'thumbnail':thumb,'page':page,'title':row.get('title',''),
                    'width':row.get('width',0),'height':row.get('height',0),
                    'publisher':row.get('source',''),'license':'Usage rights unverified; check the source.'})
        return sorted(found,key=lambda row:max(int(row.get('width') or 0),int(row.get('height') or 0)),reverse=True)

    def google_images(self,query,fetcher,limit=30):
        if self.index_unavailable:raise ValueError(self.index_unavailable)
        key=hashlib.sha256(('public-google-images:'+query).encode()).hexdigest();path=self.cache/(key+'.html')
        if path.is_file() and time.time()-path.stat().st_mtime<86400:html=path.read_text('utf8')
        else:
            response=fetcher.get('https://www.google.com/search?'+urlencode({'q':query,'udm':'2'}),limit=6*1024*1024,kind='page')
            html=response['data'].decode('utf8',errors='replace')
            try:indexed_images(html)
            except ValueError as error:self.index_unavailable=str(error);raise
            path.write_text(html,'utf8')
        found=[]
        try:rows=indexed_images(html)
        except ValueError as error:self.index_unavailable=str(error);raise
        for row in rows[:limit]:
            for url in original_urls(row['url']):found.append({**row,'url':url})
        return found

    def page_images(self,query,fetcher,limit=3):
        found=[]
        try:pages=self._search('text',query,limit)
        except Exception:pages=[]
        try:
            from hinglish_visuals.reach import search
            pages=list({row.get('url') or row.get('href'):row for row in pages+search(self.root,query,min(3,limit))}.values())
        except Exception:pass
        for row in pages[:limit+3]:
            page=row.get('href') or row.get('url') or ''
            try:
                response=fetcher.get(page,limit=3*1024*1024,kind='page')
                parser=ImagesInPage(response['url']);parser.feed(response['data'].decode('utf8',errors='replace'))
                for url in parser.images[:12]:
                    found.append({'url':url,'thumbnail':url,'page':response['url'],'title':row.get('title',''),
                        'publisher':'','license':'Usage rights unverified; check the source.'})
            except Exception as error:self.progress('A source page could not be read; checking the remaining results.')
        return found
