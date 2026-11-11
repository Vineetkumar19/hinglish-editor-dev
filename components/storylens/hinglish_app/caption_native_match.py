"""Bounded spoken-span reconciliation; never invent timestamps for missing words."""
from difflib import SequenceMatcher
import re
from .caption_speech_text import comparison_variants


def phonetic(value):
    value=value.replace('gh','').replace('tion','san').replace('sion','san')
    value=re.sub(r'c(?=[eiy])','s',value)
    for a,b in [('ph','f'),('sh','s'),('ch','j'),('bh','b'),('dh','d'),('th','t'),('kh','k'),('ck','k'),('q','k'),('c','k'),('w','v'),('z','s')]:value=value.replace(a,b)
    value=re.sub(r'[mn](?=$|[^aeiou])','n',value)
    value=re.sub(r'h$','',value)
    value=re.sub('[aeiou]','',value)
    return re.sub(r'[yn]$','',value)


def reconcile(script,observed,normalizer,align,*,_round=0):
    from .caption_numbers import comparison_key
    original=normalizer
    normalizer=lambda text:comparison_key(text,original)
    tokens=script.split();indexed=[{**w,'observed_index':i} for i,w in enumerate(observed)]
    anchors=align(script,indexed,normalizer)
    an=[comparison_variants(t,normalizer) for t in tokens];bn=[comparison_variants(w['text'],normalizer) for w in observed]
    def score(a,b):
        if a==b and a:return 30
        if any(c.isdigit() for c in a+b):return 0
        pa,pb=phonetic(a),phonetic(b)
        if pa==pb and pa:return 25
        if min(len(pa),len(pb))>=2 and SequenceMatcher(None,pa,pb,autojunk=False).ratio()>=.72:return 20
        return 0
    result=list(anchors)
    bounds=[{'script_index':-1,'observed_index':-1}]+anchors+[{'script_index':len(tokens),'observed_index':len(observed)}]
    for left,right in zip(bounds,bounds[1:]):
        sa,sb=left['script_index']+1,right['script_index'];oa,ob=left['observed_index']+1,right.get('observed_start',right['observed_index'])
        n,m=sb-sa,ob-oa
        if not n or not m or n>8 or m>16:continue
        dp=[[0]*(m+1) for _ in range(n+1)];back={}
        for i in range(n+1):
            for j in range(m+1):
                if i<n and dp[i][j]>=dp[i+1][j]:dp[i+1][j]=dp[i][j];back[i+1,j]=(i,j,0)
                if j<m and dp[i][j]>=dp[i][j+1]:dp[i][j+1]=dp[i][j];back[i,j+1]=(i,j,0)
                if i>=n:continue
                for count in range(1,min(4,m-j)+1):
                    candidates={''.join(normalizer(v['text']) for v in observed[oa+j:oa+j+count])}
                    candidates.add(normalizer(' '.join(v['text'] for v in observed[oa+j:oa+j+count])))
                    if count==1:candidates|=bn[oa+j]
                    value=max((score(a,b) for a in an[sa+i] for b in candidates),default=0)
                    # Correct one uncertain ASR spelling only between two known
                    # anchors, using an actual word's measured audio interval.
                    context=(count==1 and n==m and n<=2 and left['script_index']>=0 and right['script_index']<len(tokens) and bool(an[sa+i]) and not any(c.isdigit() for c in normalizer(tokens[sa+i])+normalizer(observed[oa+j]['text'])))
                    quality=value if value else (8 if context else 0)
                    if not quality:continue
                    candidate=dp[i][j]+quality-(count-1)*2
                    if candidate>dp[i+1][j+count]:dp[i+1][j+count]=candidate;back[i+1,j+count]=(i,j,count if value else -count)
        added=[];i,j=n,m
        while i or j:
            prev=back.get((i,j))
            if prev is None:break
            pi,pj,count=prev
            if count:
                start=oa+pj;end=oa+j-1
                added.append({**observed[start],'text':tokens[sa+pi],'script_index':sa+pi,'observed_index':end,'observed_start':start,'start':observed[start]['start'],'end':observed[end]['end'],'alignment':'compound' if abs(count)>1 else 'phonetic' if count>0 else 'context-corrected'})
            i,j=pi,pj
        result.extend(reversed(added))
    result=sorted(result,key=lambda w:w['script_index'])
    if not _round and len(result)>len(anchors):return reconcile(script,observed,normalizer,lambda *args:result,_round=1)
    return result
