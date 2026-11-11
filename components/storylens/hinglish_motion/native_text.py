"""Bind the official Hyperframes text components; local models select their use."""
import json
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMPONENTS=('bottom-up-letters','text-stagger','soft-blur-in','text-state-swap','tracking-in')


def group_choices(words,cursor):
    """Offer exact-word prefixes and valid emphasis spans, avoiding model arithmetic."""
    remaining=words[cursor:];choices={}
    function={'a','an','the','you','your','it','its','is','are','was','be','to','of','and','or','but','in','on','at','for','with','when','that','this','do','don\'t','we','i','need'}
    limit=next((i+1 for i,w in enumerate(remaining[:5]) if re.search(r'[.!?][\"\u201d\']?$',w)),min(5,len(remaining)))
    has_content=any(w.lower().strip('.,!?;:') not in function for w in remaining[:limit])
    for n in range(limit,0,-1):
        for m in range(n):
            for k in range(1,min(3,n-m)+1):
                phrase=remaining[m:m+k]
                if has_content and (phrase[0].lower().strip('.,!?;:') in function or phrase[-1].lower().strip('.,!?;:') in function):continue
                if m+k<n and remaining[m+k].lower().strip('.,!?;:') in {'up','down','out','off','away','back','forward'}:continue
                label=' '.join(remaining[:m])+(' ' if m else '')+'['+' '.join(phrase)+']'+(' ' if m+k<n else '')+' '.join(remaining[m+k:n])
                choices[label]={'word_start':cursor,'word_count':n,'main_start':m,'main_count':k}
    return choices


def schedule_choices(selected,word_count):
    cursor=0;total=sum(r['hold_weight'] for r in selected);elapsed=0;rows=[]
    for r in selected:
        if r['word_start']!=cursor or r['word_count']<1 or r['hold_weight']<=0:raise ValueError('Motion reference text invalid: incomplete model groups.')
        rows.append({**r,'start_fraction':elapsed/total,'end_fraction':(elapsed+r['hold_weight'])/total})
        elapsed+=r['hold_weight'];cursor+=r['word_count']
    if cursor!=word_count:raise ValueError('Motion reference text invalid: missing model groups.')
    return {'groups':rows}


def bundle(folder):
    folder=Path(folder);source=ROOT/'tools/hyperframes-motion-components/compositions/components'
    vendor=folder/'vendor/hyperframes';vendor.mkdir(parents=True,exist_ok=True)
    scripts=[];styles=[]
    for name in COMPONENTS:
        file=source/(name+'.html');text=file.read_text('utf-8');shutil.copyfile(file,vendor/file.name)
        styles.extend(re.findall(r'<style\b[^>]*>(.*?)</style>',text,re.S))
        body='\n'.join(re.findall(r'<script\b[^>]*>(.*?)</script>',text,re.S))
        scripts.append('configure['+json.dumps(name)+']=function(root,vars){const window={__hyperframes:{getVariables:()=>vars}};const document={querySelectorAll:()=>[root],documentElement:root,createElement:t=>realDocument.createElement(t),createTextNode:t=>realDocument.createTextNode(t)};'+body+'};')
    pre='(function(realDocument){const configure={};\n'+'\n'.join(scripts)+'\nwindow.hfNativeText={configure};})(document);\n'
    helper=(ROOT/'hinglish_motion/web/native-text-binding.js').read_text('utf-8')
    (folder/'native-hyperframes.js').write_text(pre+helper,'utf-8')
    (folder/'native-hyperframes.css').write_text('\n'.join(styles),'utf-8')
    fonts=folder/'fonts';fonts.mkdir(exist_ok=True)
    for src,name in [(Path('C:/Windows/Fonts/BOD_R.TTF'),'NativeBodoni.ttf'),(Path('C:/Windows/Fonts/BOD_B.TTF'),'NativeBodoni-Bold.ttf'),
                     (ROOT/'hinglish_captions/fonts/RobotoCondensed-Bold.ttf','NativeCondensed.ttf')]:
        if not src.is_file():raise ValueError('Motion reference text font unavailable: restore the reference typography fonts.')
        shutil.copyfile(src,fonts/name)
    with (folder/'native-hyperframes.css').open('a',encoding='utf-8') as out:
        out.write('@font-face{font-family:NativeBodoni;src:url(fonts/NativeBodoni.ttf);font-weight:400}@font-face{font-family:NativeBodoni;src:url(fonts/NativeBodoni-Bold.ttf);font-weight:700}@font-face{font-family:NativeCondensed;src:url(fonts/NativeCondensed.ttf);font-weight:700}')


def compile_groups(words,answer,profiles,duration):
    cursor=0;last_end=0.;out=[]
    for row in answer['groups']:
        a,n,m,k=(row.get(x) for x in ('word_start','word_count','main_start','main_count'))
        if any(type(v) is not int for v in (a,n,m,k)) or a!=cursor or not 1<=n<=len(words)-a or not 0<=m<n or not 1<=k<=n-m:
            raise ValueError('Motion reference text invalid: preserve every source word once in consecutive groups.')
        recipe=row.get('recipe')
        if type(recipe) is not int or not 0<=recipe<len(profiles):raise ValueError('Motion reference text invalid: choose an observed typography recipe.')
        start,end=row['start_fraction']*duration,row['end_fraction']*duration
        if start<last_end-.02 or end-start<.6 or end>duration+.01:raise ValueError('Motion reference text invalid: group timing overlaps or is reversed.')
        if not out and start!=0:raise ValueError('Motion reference text invalid: first group starts at zero.')
        selected=words[a:a+n];profile=profiles[recipe]
        out.append({**profile,'header':' '.join(selected[:m]),'main':' '.join(selected[m:m+k]),'footer':' '.join(selected[m+k:]),
                    'start':start,'end':end,'anchor_x':row.get('anchor_x',profile.get('anchor_x',.5)),
                    'anchor_y':row.get('anchor_y',profile.get('anchor_y',.4)),'effect':row['effect']})
        cursor+=n;last_end=end
    if cursor!=len(words) or not out or abs(last_end-duration)>.02:raise ValueError('Motion reference text invalid: missing words or final group hold.')
    return out
