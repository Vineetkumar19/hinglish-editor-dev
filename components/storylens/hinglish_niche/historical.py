"""Verified local player imagery for historical cricket scenes. Identity never proves season/match."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def normalize(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value).casefold()).strip()


def select_player_asset(root,name,year,team='',match_id=''):
    if type(year) is not int or not 1850 <= year <= 2100:
        raise ValueError('Historical player visuals need an explicit season year.')
    base=(Path(root)/'library/cricket-assets').resolve();manifest=base/'manifest.json'
    if not manifest.exists():return None
    candidates=[]
    for entry in json.loads(manifest.read_text(encoding='utf-8')).get('assets',[]):
        if not isinstance(entry,dict):continue
        names=[entry.get('player',''),*entry.get('aliases',[])]
        if not normalize(name) or normalize(name) not in [normalize(n) for n in names]:continue
        if entry.get('approved') is not True or entry.get('verified') is not True or entry.get('rights') not in ('owned','licensed'):continue
        if type(entry.get('year')) is not int or entry['year']!=year:continue
        if team and normalize(entry.get('team',''))!=normalize(team):continue
        if match_id and entry.get('match_id')!=match_id:continue
        evidence=entry.get('evidence_url','')
        if urlparse(evidence).scheme!='https' or not urlparse(evidence).hostname:continue
        path=(base/str(entry.get('file',''))).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):continue
        candidates.append({**entry,'path':str(path)})
    # A generic year portrait cannot replace an explicitly requested match photo.
    if len({normalize(e['player']) for e in candidates}) > 1: return None
    return sorted(candidates,key=lambda e:(not bool(e.get('match_id')),e['path']))[0] if candidates else None


def mentioned_years(text):
    """Explicit years only, including common spoken Hindi/English season forms."""
    text=str(text).casefold().translate({0x0966+i:ord('0')+i for i in range(10)})
    years={int(y) for y in re.findall(r'\b(?:18|19|20)\d{2}\b',text)}
    endings={'bees':20,'bis':20,'biis':20,'ikkiis':21,'ikkis':21,'baais':22,'baiis':22,
             'baees':22,'teees':23,'teis':23,'chaubees':24,'chaubiis':24,'chaubis':24,
             'pachchis':25,'pachchiis':25,'paccis':25,'pachis':25,'chhabbis':26,
             'chhabbiis':26,'sattais':27,'atthais':28,'untees':29,'tees':30,
             'aath':8,'nau':9,'das':10,'gyarah':11,'gyaarah':11,'barah':12,'baarah':12,
             'terah':13,'chaudah':14,'pandrah':15,'solah':16,'satrah':17,'atharah':18,'unnees':19}
    for suffix in re.findall(r'\bdo\s+hazaar\s+([a-z]+)\b',text):
        if suffix in endings:years.add(2000+endings[suffix])
    for suffix in re.findall(r'\btwo\s+thousand\s+(?:and\s+)?(twenty(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|thirty)\b',text):
        parts=suffix.replace('-',' ').split();units={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9}
        years.add(2000+(30 if parts[0]=='thirty' else 20+units.get(parts[-1],0)))
    return years


def attach_context(scenes,lines):
    """Retain model year context only when supported by the narrated season chapter."""
    from .profiles import current_profile
    if current_profile()!='cricket':return
    # A future year elsewhere in the script cannot validate this chapter's image.
    # Multiple years in a comparison suspend automatic inheritance.
    scopes={};inherited=set()
    for line in sorted(lines,key=lambda line:line.start):
        explicit=mentioned_years(line.text)
        if explicit:inherited=explicit if len(explicit)==1 else set()
        scopes[line.id]=explicit or inherited
    for scene in scenes:
        years=scopes.get(scene.line,set())
        for asset in scene.assets:
            if asset.get('kind')!='person':continue
            raw=asset.get('historical') or {}
            year=raw.get('year')
            if type(year) is not int or year not in years:
                query_years=mentioned_years(asset.get('query',''))
                year=next(iter(query_years)) if len(query_years)==1 and query_years<=years else (next(iter(years)) if len(years)==1 and not query_years else None)
            asset['historical']={'year':year,'team':str(raw.get('team',''))[:100],'match_id':str(raw.get('match_id',''))[:150]}


def anchor_player_scenes(scenes,lines,words,move_scene=True):
    from .profiles import current_profile
    if current_profile()!='cricket':return
    from hinglish_visuals.timing import mention_time
    by_id={line.id:line for line in lines}
    for scene in scenes:
        people=[a for a in scene.get('assets',[]) if a.get('kind')=='person']
        line=by_id.get(scene['line'])
        if not people or line is None:continue
        aligned=[w for w in words if getattr(w,'aligned',False)]
        entries=[]
        for person in people:
            at=mention_time(aligned,line.start,line.end,person.get('name',''))
            if at is not None:entries.append({'name':person['name'],'seconds':round(at,3),'source':'aligned spoken word'})
        if not entries:continue
        scene.setdefault('data',{})['player_entries']=entries
        if move_scene and len(people)==1:
            at=entries[0]['seconds']
            scene['start']=round(at,3)
            scene['name_anchor']=entries[0]
