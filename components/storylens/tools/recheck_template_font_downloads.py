"""Prepare exact missing font faces from author download pages; never rename faces."""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile
import html
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/template-fonts/library-recheck'
DEST=ROOT/'library/template-fonts/owner-recheck'
SLUGS=['american-captain','anisha','bebas','bebas-neue','bestermind','bignoodle-titling',
 'brittany-signature','butler','coolvetica','corinthiago','darcey-oliver','geometos-rounded',
 'hanoverians','heading','headline-crack','headline-one','headliner-no-45','heavitas',
 'hello-america','hijrnotes','holimount','jersey-m54','manhandle-slab','monument-extended',
 'mung-signature','nexa','old-sport-athletic','rounded-elegance','royalia',
 'rub-this-transfer-sheet','steelfish','steelfish-outline','take-cover','tangosans',
 'type-wrong','uni-sans-heavy-caps','urania-czech','wedding']

def fetch(url,limit=32*1024*1024):
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Storylens font setup'})
    with urllib.request.urlopen(request,timeout=25) as response:
        data=response.read(limit+1)
        if len(data)>limit:raise ValueError('Publisher archive exceeds download limit')
        return data

def prepare(slug,wanted):
    page='https://www.dafont.com/'+slug+'.font'
    url='https://dl.dafont.com/dl/?f='+slug
    result={'family':slug,'page':page,'url':url,'fonts':[]}
    target=DEST/slug
    try:
        page_data=fetch(page,2*1024*1024)
        links=re.findall(r'(?:https?:)?//dl\.dafont\.com/dl/\?[^"\s<>]+',page_data.decode('utf8',errors='replace'))
        if links:
            url=html.unescape(links[0]);url='https:'+url if url.startswith('//') else url
            result['url']=url
        data=fetch(url)
        target.mkdir(parents=True,exist_ok=True)
        archive=zipfile.ZipFile(io.BytesIO(data))
        total=0
        for member in archive.infolist():
            total+=member.file_size
            if total>64*1024*1024:raise ValueError('Expanded publisher archive exceeds limit')
            name=Path(member.filename).name
            if member.is_dir() or name.startswith('._') or '__MACOSX' in member.filename:continue
            suffix=Path(name).suffix.lower()
            if suffix in ('.ttf','.otf'):
                raw=archive.read(member)
                with TTFont(io.BytesIO(raw)) as font:ps=font['name'].getDebugName(6)
                if ps not in wanted:continue
                # Exact identity only. Do not modify internal font naming tables.
                path=target/(hashlib.sha256(raw).hexdigest()[:12]+suffix)
                if path.exists() and path.read_bytes()!=raw:raise ValueError('Font hash collision')
                path.write_bytes(raw)
                result['fonts'].append({'source':str(path),'postscript_name':ps,'url':url,
                    'publisher_page':page,'license':str(target),'sha256':hashlib.sha256(raw).hexdigest()})
            elif suffix in ('.txt','.pdf','.html','.rtf','.md') and member.file_size<2*1024*1024:
                (target/name).write_bytes(archive.read(member))
        if result['fonts']:
            (target/'publisher-page.html').write_bytes(page_data)
        result['notice']='Author-provided download; included notices govern usage, some faces personal-use only.'
    except Exception as error:result['error']=str(error)
    return result

def main():
    wanted=set(json.loads((OUT/'audit-before.json').read_text('utf8'))['missing_candidates'])
    DEST.mkdir(parents=True,exist_ok=True)
    previous=json.loads((OUT/'prepared-fonts.json').read_text('utf8')) if (OUT/'prepared-fonts.json').exists() else {'families':[]}
    cached={row['family']:row for row in previous['families'] if not row.get('error')}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda slug:cached.get(slug) or prepare(slug,wanted),SLUGS))
    fonts={}
    for result in results:
        for row in result['fonts']:fonts.setdefault(row['postscript_name'],row)
    manifest={'fonts':list(fonts.values()),'families':results}
    (OUT/'prepared-fonts.json').write_text(json.dumps(manifest,indent=2),'utf8')
    print(json.dumps({'prepared':len(fonts),'names':sorted(fonts),'unresolved':sorted(wanted-set(fonts)),
                      'unavailable_archives':[r['family'] for r in results if r.get('error')]}))

if __name__=='__main__':main()
