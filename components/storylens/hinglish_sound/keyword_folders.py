"""Keyword sound bins and a separate draft timeline, bound to saved model evidence."""
import hashlib
import json
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET


def folder_name(value):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', str(value or 'Sound options'))
    name = re.sub(r'\s+', ' ', name.replace('_',' ')).strip(' .')[:72].rstrip(' .') or 'Sound options'
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', name, re.I):
        name = '_' + name
    return name


def label_keywords(brain, events):
    """Migration for saved reviews; reuse their real scene intents, no invented visual analysis."""
    schema = {'type':'object','properties':{'keywords':{'type':'array','minItems':len(events),
        'maxItems':len(events),'items':{'type':'object','properties':{
            'event':{'type':'string','enum':[e['id'] for e in events]},
            'keyword':{'type':'string','maxLength':64}},'required':['event','keyword']}}},'required':['keywords']}
    answer = brain.ask('Organize sound recommendations into human-readable source folders. For EVERY event return its ID and a concise 2-4 word keyword using normal words and spaces. Name the MAIN acoustic source these candidate recordings share, not a checklist of everything mentioned in the intent. For example Rain, Motorcycle riding, Walking in water, Waterfall, Text whooshes are useful names; rain_thunder_mud and waterfall_stream_stone_splash are NOT useful names. Reuse exactly the SAME keyword for repeated equivalent sources. Use the actual candidate names to identify the sound source; distinguish wet steps from flowing water and engines from rain. Preserve a meaningful material/action difference only where the actual recordings support it. Base names ONLY on supplied evidence, not imaginary scenes. These examples are not a fixed taxonomy. Do not choose files or change the timeline.',
        {'events':[{'event':e['id'],'intent':e['intent'],'category':e['category'],
                    'recordings':[c['asset']['name'] for c in e['candidates'] if c.get('recommendation')!='Keyword folder option']}
                   for e in events]},
        schema, think=False, max_tokens=2200, label='Organizing sound keyword folders')
    rows=answer.get('keywords',[])
    if len(rows)!=len(events) or {r.get('event') for r in rows}!={e['id'] for e in events}:
        raise ValueError('The model did not label every sound event. Saved sounds and timeline are unchanged.')
    labels={r['event']:folder_name(r['keyword']) for r in rows}
    for event in events:
        event['keyword']=labels[event['id']]


def curate_folders(brain, review):
    """Same Qwen offers original library options; no second model and no timeline replacement."""
    folders=organize(review)
    for offset in range(0,len(folders),4):
        batch=folders[offset:offset+4]
        schema={'type':'object','properties':{'folders':{'type':'array','minItems':len(batch),'maxItems':len(batch),
            'items':{'type':'object','properties':{'id':{'type':'string','enum':[f['id'] for f in batch]},
            'choices':{'type':'array','items':{'type':'integer'}}},'required':['id','choices']}}},'required':['folders']}
        answer=brain.ask('You are the local sound designer preparing keyword folders for a human. Select ALL genuinely suitable recordings in each supplied folder. Do not fill a quota. Match the real physical source and acoustics: waterfall roar is not an underwater bubble or a fantasy spell; walking in shallow water is not a tap running; motorcycle is not a UI click. Editorial sounds are appropriate only in their editorial folder. Return candidate indices, not file paths. Do not change the draft timeline. No other model will veto these recommendations.',
            {'folders':[{'id':g['id'],'keyword':g['name'],
                'candidates':[{'choice':i,'name':c['asset']['name'],'description':c.get('description','')[:180]}
                              for i,c in enumerate(g['candidates'])]} for g in batch]},
            schema,think=False,max_tokens=1700,label='Choosing keyword folder recordings')
        rows=answer.get('folders',[])
        if len(rows)!=len(batch) or {r.get('id') for r in rows}!={g['id'] for g in batch}:
            raise ValueError('The model did not finish all keyword folders. The original timeline is kept.')
        for group in batch:
            row=next(r for r in rows if r['id']==group['id'])
            indices=row.get('choices',[])
            if any(type(i) is not int or not 0<=i<len(group['candidates']) for i in indices):
                raise ValueError('The model returned an unavailable sound option. The original timeline is kept.')
            chosen={group['candidates'][i]['asset']['path'] for i in indices}
            for event in review['events']:
                if event['id'] not in group['events']:continue
                for candidate in event['candidates']:
                    candidate['folder_approved']=candidate['asset']['path'] in chosen
                    if candidate['folder_approved'] and candidate.get('recommendation')!='Qwen first choice':
                        candidate['recommendation']='Qwen folder option'
    organize(review)


def organize(review):
    """Merge equivalent keywords, deduplicate sources; keep all occurrence timing and selections."""
    groups={}
    for event in review.get('events',[]):
        selected={s['candidate'] for s in (review.get('selections') or []) if s['event']==event['id']}
        event['candidates']=[c for c in event.get('candidates',[]) if c.get('recommendation')!='Keyword folder option' or c['id'] in selected]
        name=folder_name(event.get('keyword') or event.get('intent') or event.get('word'))
        key=name.casefold()
        group=groups.setdefault(key,{'id':'keyword-'+hashlib.sha256(key.encode()).hexdigest()[:12],
            'name':name,'events':[],'candidates':[]})
        group['events'].append(event['id'])
        seen={str(Path(c['asset']['path']).resolve()).casefold() for c in group['candidates']}
        for candidate in event.get('candidates',[]):
            if candidate.get('recommendation')=='Keyword folder option':continue
            if candidate.get('folder_approved') is False:continue
            path=str(Path(candidate['asset']['path']).resolve()).casefold()
            if path not in seen:
                group['candidates'].append({'event':event['id'],**candidate});seen.add(path)
    # Offer the keyword pool at each matching occurrence, preserving old IDs/trim and all owner edits.
    for group in groups.values():
        for event in review['events']:
            if event['id'] not in group['events']:continue
            known={str(Path(c['asset']['path']).resolve()).casefold() for c in event['candidates']}
            for candidate in group['candidates']:
                path=str(Path(candidate['asset']['path']).resolve()).casefold()
                if path in known:continue
                event['candidates'].append({'id':'folder-'+hashlib.sha256(path.encode()).hexdigest()[:16],
                    'asset':dict(candidate['asset']),'description':candidate.get('description',''),
                    'recommendation':'Keyword folder option'})
                known.add(path)
    review.update(version=2,folders=list(groups.values()),workflow='keyword_folders_and_draft')
    return review['folders']


def package(plan_path):
    """Real folders with full source recordings, not short mixed timeline excerpts."""
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text('utf-8'))
    review=plan.get('human_review')
    if not review:return None
    groups=organize(review)
    base=plan_path.parent/'Sound Design'
    old_index=base/'index.json'
    if old_index.exists():
        previous=json.loads(old_index.read_text('utf-8'))
        old_shape={(g['name'],f['source']) for g in previous.get('folders',[]) for f in g['files']}
        new_shape={(g['name'],str(Path(c['asset']['path']).resolve())) for g in groups for c in g['candidates']}
        if old_shape!=new_shape:
            # Preserve prior generated copies outside the current bank; never mix stale options into it.
            import uuid
            archive=plan_path.parent/'keyword-folder-history'/uuid.uuid4().hex[:12]
            parent=plan_path.parent.resolve()
            if not base.resolve().is_relative_to(parent) or not archive.resolve().is_relative_to(parent):
                raise ValueError('The keyword folder location is invalid.')
            archive.mkdir(parents=True);base.rename(archive/'Sound Design')
    base.mkdir(exist_ok=True)
    manifest={'version':1,'name':'Sound Design','folders':[],'timeline':str(plan_path.parent/'SOUND_SEQUENCE.xml')}
    for group in groups:
        dest=base/group['name'];dest.mkdir(exist_ok=True)
        files=[]
        for row in group['candidates']:
            source=Path(row['asset']['path'])
            if not source.is_file():raise ValueError('A recommended recording has moved: '+source.name)
            ident=hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:8]
            target=dest/(folder_name(source.stem)[:65]+'-'+ident+source.suffix.lower())
            if not target.exists() or target.stat().st_size!=source.stat().st_size or target.stat().st_mtime_ns!=source.stat().st_mtime_ns:
                shutil.copy2(source,target)
            files.append({'path':str(target.resolve()),'name':row['asset']['name'],
                'duration':row['asset']['duration'],'source':str(source.resolve()),'recommendation':row['recommendation']})
        occurrences=[{'event':e['id'],'start':e['time'],'duration':e['duration'],'intent':e['intent']}
                     for e in review['events'] if e['id'] in group['events']]
        manifest['folders'].append({'name':group['name'],'files':files,'occurrences':occurrences})
    index=base/'index.json';serialized=json.dumps(manifest,ensure_ascii=False,indent=2)
    if not index.exists() or index.read_text('utf-8')!=serialized:index.write_text(serialized,encoding='utf-8')
    credits=plan_path.parent/'CREDITS.txt'
    if credits.exists() and (not (base/'CREDITS.txt').exists() or (base/'CREDITS.txt').read_bytes()!=credits.read_bytes()):shutil.copy2(credits,base/'CREDITS.txt')
    return manifest


def premiere_project(plan_path, destination=None):
    """XMEML project: Sound Design > keyword bins plus the existing editable sequence."""
    from hinglish_cut.xml_export import add,premiere_pathurl
    plan_path=Path(plan_path);manifest=package(plan_path)
    if not manifest:return str(plan_path.parent/'SOUND_SEQUENCE.xml')
    source=SafeET.parse(plan_path.parent/'SOUND_SEQUENCE.xml').getroot()
    sequence=source if source.tag=='sequence' else source.find('.//sequence')
    if sequence is None:raise ValueError('Save the sound timeline before exporting its keyword folders.')
    root=ET.Element('xmeml',version='4');project=add(root,'project');add(project,'name','Storylens Sound Design')
    children=add(project,'children');children.append(sequence)
    parent=add(children,'bin');add(parent,'name','Sound Design');bins=add(parent,'children')
    fps=int(sequence.findtext('rate/timebase') or 30)
    ntsc=sequence.findtext('rate/ntsc') or 'FALSE'
    n=0
    for group in manifest['folders']:
        bin_=add(bins,'bin');add(bin_,'name',group['name']);items=add(bin_,'children')
        for row in group['files']:
            n+=1;frames=max(1,round(row['duration']*fps/(1.001 if ntsc=='TRUE' else 1)))
            clip=add(items,'clip',id=f'keyword-clip-{n}');add(clip,'name',row['name']);add(clip,'duration',frames)
            rate=add(clip,'rate');add(rate,'timebase',fps);add(rate,'ntsc',ntsc)
            add(clip,'in',0);add(clip,'out',frames)
            file=add(clip,'file',id=f'keyword-file-{n}');add(file,'name',Path(row['path']).name)
            add(file,'pathurl',premiere_pathurl(row['path']));add(file,'duration',frames)
            rate=add(file,'rate');add(rate,'timebase',fps);add(rate,'ntsc',ntsc)
            audio=add(add(file,'media'),'audio')
            # Read actual stream format; originals remain full-length and unprocessed.
            import av
            with av.open(row['path']) as container:
                stream=container.streams.audio[0]
                characteristics=add(audio,'samplecharacteristics')
                add(characteristics,'samplerate',stream.sample_rate);add(audio,'channelcount',stream.channels)
    for group in manifest['folders']:
        for occurrence in group['occurrences']:
            marker=add(sequence,'marker');add(marker,'name',group['name'])
            add(marker,'comment',occurrence['intent'])
            add(marker,'in',round(occurrence['start']*fps/(1.001 if ntsc=='TRUE' else 1)));add(marker,'out',-1)
    destination=Path(destination or plan_path.parent/'SOUND_KEYWORD_PROJECT.xml')
    ET.indent(root,space='  ');ET.ElementTree(root).write(destination,encoding='utf-8',xml_declaration=True)
    # Portable full-source package for CapCut/manual import; preserve attribution with the media.
    import zipfile
    archive=plan_path.parent/'sound-keyword-folders.zip'
    files=[Path(row['path']) for group in manifest['folders'] for row in group['files']]
    files.append(plan_path.parent/'Sound Design/index.json')
    if (plan_path.parent/'Sound Design/CREDITS.txt').exists():files.append(plan_path.parent/'Sound Design/CREDITS.txt')
    if not archive.exists() or any(p.stat().st_mtime>archive.stat().st_mtime for p in files):
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as bundle:
            for file in files:bundle.write(file,file.relative_to(plan_path.parent))
    return str(destination.resolve())
