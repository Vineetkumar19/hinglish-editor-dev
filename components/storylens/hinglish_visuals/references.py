"""Downloaded, source-linked visual choices. Only the owner's selection becomes a timeline clip."""
import hashlib
import json
import shutil
import time
import re
from pathlib import Path

from PIL import Image

from .evaluator import info_for, open_evaluator
from .gather import gather
from .planner import judge
from .timing import mention_time
from .web import Entity, Media, generic_reference_allowed
from .recovery import checkpoint, context_key, profile_source


def evidence_required(entry):
    import re
    return entry.get('reference_type')=='evidence' or bool(re.search(
        r'\b(?:scorecard|champions? list|rankings?|standings|record|century|runs|not out|law|article\s+\d|section\s+\d)\b',
        entry.get('visual',''),re.I))


def previous_sources(root, entity):
    """Prior internet downloads are retrieval leads, rechecked for the current team/context."""
    if entity.kind!='person' or not entity.qid:return []
    out=[];seen=set()
    files=sorted((Path(root)/'output/visuals').glob('*/*/visuals-project.json'),
        key=lambda p:p.stat().st_mtime,reverse=True)[:30]
    for file in files:
        try:project=json.loads(file.read_text('utf-8'))
        except (OSError,ValueError):continue
        for slot in project.get('slots',[]):
            spec=project.get('entities',{}).get(slot.get('entity'),{})
            if spec.get('qid')!=entity.qid:continue
            for data in slot.get('options',[]):
                if data['id'] in seen or (data.get('evaluation') or {}).get('passed') is not True:continue
                path=file.parent/data.get('asset','')
                if not path.is_file():continue
                seen.add(data['id'])
                out.append(Media(**{k:v for k,v in {**data,'path':str(path.resolve())}.items()
                    if k in Media.__dataclass_fields__}))
    return out[:8]


def reference_method(entry, project):
    """Use only an explicit local generic outcome, never infer an acronym's meaning."""
    entity = Entity(**project['entities'][entry['entity']])
    outcomes = project.get('resolution_outcomes', {})
    if not isinstance(outcomes, dict):
        return {}
    outcome = outcomes.get(entry['entity'], {})
    if (not isinstance(outcome, dict) or outcome.get('status') != 'generic'
            or outcome.get('referent') != 'generic' or outcome.get('needs_clarification') is not False
            or outcome.get('entity_key') != entity.key or outcome.get('original_name') != entity.name
            or outcome.get('candidate_id') not in (None, '') or outcome.get('canonical_name') not in (None, '')
            or entity.qid or evidence_required(entry) or entry.get('evidence_terms')):
        return {}
    meanings, quotes = outcome.get('known_meanings'), outcome.get('quoted_words')
    country = outcome.get('country')
    if (not isinstance(country, str) or not country.strip()
            or not isinstance(meanings, list) or not meanings
            or not all(isinstance(v, str) and v.strip() for v in meanings)
            or not isinstance(quotes, list) or not quotes
            or not all(isinstance(v, str) and v.strip() for v in quotes)):
        return {}
    names = entity.names(min_length=2)
    # A supplied definition is evidence for this mention only, not a global alias.
    for meaning in meanings:
        names += re.findall(r'(?<!\w)' + re.escape(entity.name) + r'\s*\(([^()]{3,80})\)', meaning, re.I)
    evidence=outcome.get('canonical_class_evidence')
    if (isinstance(evidence,dict) and isinstance(evidence.get('qid'),str)
            and re.fullmatch(r'Q[1-9]\d*',evidence['qid'])
            and evidence.get('source')=='https://www.wikidata.org/wiki/'+evidence['qid']
            and isinstance(evidence.get('subclass_of'),list) and evidence['subclass_of']):
        aliases=evidence.get('aliases',[])
        if isinstance(aliases,list):
            names += [n.strip() for n in [evidence.get('label','')]+aliases
                      if isinstance(n,str) and 2<=len(n.strip())<=100]
    category = [w for w in re.findall(r'\w+', entry.get('category', '').casefold()) if len(w) >= 3]
    regions = re.findall(r'\b(?:north|south|east|west|central|northern|southern|eastern|western)\s+'
                         + re.escape(country.strip()) + r'\b', entry.get('visual', ''), re.I)
    method = dict(mode='generic_class', scope='illustration', entity_key=entity.key,
                  name=entity.label or entity.name, kind=entity.kind, show=entry['show'],
                  names=list(dict.fromkeys(names)), category_terms=category,
                  source_constraints=list(dict.fromkeys([country.strip()] + regions)))
    return method if generic_reference_allowed(method, entity.kind, entry['show'], method['name']) else {}


def candidate_info(info, media):
    """Only generic illustrations add source evidence to the pixel-check contract."""
    if 'reference_method' not in info:
        return info
    title, text = ((media.get('title', ''), media.get('text', '')) if isinstance(media, dict)
                   else (media.title, media.text))
    return {**info, 'source_evidence': f'{title} {text}'}


def context_info(entry, project):
    import re
    from .gather import mentions
    info={**info_for(entry,project['entities'][entry['entity']]),'strict_context':True,
        'context':' '.join([project.get('summary',{}).get('topic',''),entry['text'],entry['meaning'],entry['visual']])}
    method = reference_method(entry, project)
    if method:
        info['reference_method'] = method
    if entry['show']=='logo':
        info['visual']='The real '+info['name']+' logo or branded icon'
        info['context']='The speech explicitly names '+info['name']+'. Check this genuine brand/team logo; other teams in the surrounding story do not change this logo request.'
    if info['kind']=='person':
        reference=project.get('identity_references',{}).get(entry['entity'],{})
        if profile_source(reference.get('source')) and reference.get('qid')==project['entities'][entry['entity']].get('qid') and reference.get('path') and Path(reference['path']).is_file():
            info.update(identity_reference=reference['path'],identity_reference_source=reference['source'])
        # Identity-only fallback banks must inherit kit constraints from this
        # person's original locally planned request, not lose them to "photo".
        related = [s for s in project.get('slots', []) if s['entity']==entry['entity']]
        team_context = ' '.join([entry['visual'], *entry.get('queries', [])] +
            [s.get('visual','')+' '+' '.join(s.get('queries',[])) for s in related])
        matching_teams = []
        for spec in project['entities'].values():
            description=spec.get('description','').casefold()
            team_description=any(t in description for t in ('cricket team','cricket franchise','ipl franchise','sports team')) or (
                'franchise' in description and ('premier league' in description or 'cricket' in description))
            if spec['kind']!='brand' and not team_description:continue
            team=Entity(**spec)
            team_names=list(dict.fromkeys(team.names()+list(team.aliases)))
            short_alias=any(2<=len(alias)<=4 and re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',team_context,re.I)
                for alias in team_names)
            if mentions(team_context,team.names()) or short_alias:
                matching_teams.append((team, team_names))
        if len(matching_teams)==1:
                team, team_names = matching_teams[0]
                info.update(required_team=team.label or team.name,team_aliases=team_names)
                logos=[o for s in project['slots'] if s['entity']==team.key and s['show']=='logo'
                    for o in s.get('options',[]) if (o.get('evaluation') or {}).get('passed') is True and Path(o.get('path','')).is_file()]
                logos.sort(key=lambda o:('wikipedia.org' not in o.get('page_url',''),'wikimedia.org' not in o.get('page_url','')))
                if logos:info['team_reference']=logos[0]['path']
        elif len(matching_teams)>1:
            info['team_context_ambiguous'] = True
    if evidence_required(entry):info.update(kind='event',show='photo',category='source document, scorecard or standings table',document_evidence=True,
        context='Spoken words: '+entry['text']+'. Requested evidence: '+entry['visual']+'. Required source terms: '+', '.join(entry.get('evidence_terms',[])))
    elif info['kind']=='thing':
        info['context']='Verify the exact named object '+info['name']+'. This object reference does not prove the surrounding statistical claim.'
    return info


def profile_reference(root, entry, project, candidates, web, finder):
    """Use a named publisher profile headshot as a comparison, never as five options.

    A generic image on a player's article is insufficient. A dedicated named
    publisher profile must identify its headshot through a named image URL or
    the indexed profile image/title (publishers also use numeric CDN filenames).
    """
    from urllib.parse import urlparse, unquote
    from .gather import mentions
    from .pipeline import fetch
    entity=Entity(**project['entities'][entry['entity']])
    if entity.kind!='person' or evidence_required(entry) or not entity.qid or len(entry.get('options',[]))>=5:return
    references=project.setdefault('identity_references',{})
    saved=references.get(entry['entity'],{})
    if profile_source(saved.get('source')) and saved.get('qid')==entity.qid and Path(saved.get('path','')).is_file():return
    if saved:
        project.setdefault('rejected_identity_references',[]).append(saved)
        references.pop(entry['entity'],None)
    candidates=list(candidates)
    if finder and hasattr(finder,'images'):
        # A context-specific action search may have no headshots. Reuse the
        # cached named portrait search to find a comparison reference only.
        # These generic pictures are still NOT offered without the kit check.
        try:
            if hasattr(finder,'begin_subject'):finder.begin_subject(seconds=30)
            candidates+=finder.images(entity.label or entity.name,30)
            candidates+=finder.images((entity.label or entity.name)+' profile',30)
        except Exception:pass
    seen_references=set()
    for media in candidates:
        if media.url in seen_references:continue
        seen_references.add(media.url)
        page=unquote(urlparse(media.page_url).path).replace('-',' ')
        image=unquote(urlparse(media.url).path).replace('-',' ').replace('_',' ')
        if not profile_source(media.page_url):continue
        named_profile=mentions(media.title,entity.names()) and bool(re.search(r'\bprofile\b',media.title,re.I))
        if not mentions(page,entity.names()) or not (mentions(image,entity.names()) or named_profile):continue
        try:
            path=fetch(root,media,web.session,finder)
            with Image.open(path) as picture:
                if min(picture.size)<96:continue
            references[entry['entity']]={'path':str(Path(path).resolve()),'source':media.page_url,
                'asset_url':media.url,'qid':entity.qid}
            return
        except Exception as error:
            project.setdefault('identity_reference_errors',{}).setdefault(entry['entity'],[]).append(str(error)[:800])
            continue


def research_slots(moments, phrases, words, entities, duration):
    """Research every mention, without a B-roll coverage quota hiding named subjects."""
    from dataclasses import replace
    # A scorecard is optional factual evidence; it must not consume the named
    # person's photo bank. These identity requests use only locally planned and
    # resolved subjects. Actual assets still require local ranking/pixel checks.
    moments = list(moments)
    have_identity = {m.entity for m in moments if m.reference_type == 'identity'}
    for key, entity in entities.items():
        if key in have_identity or entity.kind not in ('person', 'brand'):
            continue
        origin = next((m for m in moments if m.entity == key and m.mention), None)
        if origin is None:
            continue
        name = entity.label or entity.name
        requested = ' '.join([origin.visual, *origin.queries])
        teams = [e.label or e.name for e in entities.values() if e.key != key and e.kind == 'brand'
                 and any(n.casefold() in requested.casefold() for n in e.names() if len(n) > 2)]
        visual = name + (' logo' if entity.kind == 'brand' else
            (' in ' + teams[0] + ' kit' if len(teams) == 1 else ' photo'))
        moments.append(replace(origin, visual=visual, queries=[visual, visual + ' png'],
            reference_type='identity', evidence_terms=[], show='logo' if entity.kind == 'brand' else 'photo',
            category='logo' if entity.kind == 'brand' else 'person', display='popup'))
        have_identity.add(key)
    by_id = {p.id: p for p in phrases}
    slots = []
    for m in moments:
        p = by_id.get(m.phrase_id)
        if p is None or m.entity not in entities:
            continue
        entity = entities[m.entity]
        at = mention_time(words, p.start, p.end, m.mention, entity.names())
        start = max(0., at if at is not None else p.start)
        end = min(duration, max(start + .6, min(p.end, start + 3.)))
        if end <= start:
            continue
        slots.append({'index': len(slots), 'start': round(start, 3), 'end': round(end, 3),
            'text': p.text, 'quote': m.quote, 'meaning': m.meaning, 'visual': m.visual,
            'queries': m.queries, 'priority': m.priority, 'entity': m.entity,
            'label': entity.label or entity.name, 'show': m.show, 'display': m.display,
            'category': m.category, 'reference_type': m.reference_type,
            'evidence_terms': m.evidence_terms, 'chosen': None, 'clip': None,
            'evaluation': None, 'rejected': [], 'alternatives': [], 'options': []})
    slots.sort(key=lambda slot:slot['start'])
    for i,slot in enumerate(slots):
        slot['index']=i
        following=next((s['start'] for s in slots[i+1:] if s['start']>slot['start']+.001),None)
        if following is not None and following-slot['start']>=.4:
            slot['end']=min(slot['end'],following)
    return slots


def collect(root, results, brain, web, finder, settings, progress=print, evaluator=None, *, find_more=False, only_entity=None):
    """Rank actual internet files with the local model, then check every offered file's pixels."""
    from .pipeline import fetch, write_outputs
    from .report import write_report
    from hinglish_clean.detection import write_json
    own = evaluator is None
    # Finish text research first, then keep only the vision model busy. Alternating
    # the two large models for every keyword repeatedly reloads them on small GPUs.
    choice_limit=getattr(settings,'options_per_moment',5)
    ranked = {}
    searches = {}
    for timeline, folder, project in results:
        folder = Path(folder)
        project.update(review_options=True, options_per_moment=choice_limit, collecting=True)
        checkpoint(folder, project, 'searching')
        write_report(folder / 'report.html', project)
        progress('Saved the review plan before searching: ' + str(folder / 'report.html'))
        for entry in project['slots']:
            if only_entity and entry['entity']!=only_entity:continue
            entity_spec=project['entities'][entry['entity']]
            if entity_spec['kind']=='thing' and 'trophy' in entry['label'].casefold() and not evidence_required(entry) and 'logo' not in entry['text'].casefold():
                entry['visual']='The real '+entry['label']
                entry['queries']=list(dict.fromkeys([entry['label']+' photo',entry['label']+' png']+entry['queries']))
            if len(entry.get('options',[]))>=choice_limit:
                ranked[id(entry)]=[]
                continue
            if evidence_required(entry):
                import re
                entry['reference_type']='evidence'
                if not entry.get('evidence_terms'):
                    entry['evidence_terms']=[entry['label']]+re.findall(r'\b\d+\b',entry['visual']+' '+entry['meaning'])
                if entry['evidence_terms']==[entry['label']]:
                    from .gather import mentions
                    subjects=[spec.get('label') or spec['name'] for spec in project['entities'].values()
                        if spec['key']!=entry['entity'] and mentions(entry['visual'],Entity(**spec).names())]
                    if subjects:entry['evidence_terms']=subjects+re.findall(r'\b\d+\b',entry['visual']+' '+entry['meaning'])
            entity = Entity(**project['entities'][entry['entity']])
            if entity.kind=='person' and entry['reference_type']!='evidence':
                kit=context_info(entry,project).get('required_team')
                if kit:
                    # Search for the required kit too, rather than collecting a
                    # generic national-team bank and rejecting it afterwards.
                    entry['visual']=(entity.label or entity.name)+' in '+kit+' kit'
                    entry['queries']=list(dict.fromkeys([entry['visual']+' photo',entry['visual']+' png']+entry['queries']))[:4]
            from .planner import VisualMoment
            m = VisualMoment(phrase_id=0, visual=entry['visual'], queries=entry['queries'],
                priority=entry['priority'], quote=entry['quote'], meaning=entry['meaning'],
                entity=entry['entity'], show=entry['show'], display=entry['display'],
                category=entry['category'], reference_type=entry['reference_type'],
                evidence_terms=entry['evidence_terms'])
            method = reference_method(entry, project)
            progress(f'Searching visual choices {entry["index"]+1}/{len(project["slots"])}: {entry["visual"]}')
            signature = hashlib.sha256(json.dumps({'visual': 'identity logo' if m.show=='logo' and m.reference_type!='evidence' else entry['visual'],
                'queries': [] if m.show=='logo' and m.reference_type!='evidence' else entry['queries'],
                'reference_type': entry['reference_type'], 'entity': entity.to_dict(),
                **({'reference_method': method} if method else {})}, sort_keys=True).encode()).hexdigest()
            if signature in searches:
                candidates=searches[signature]
                ranked[id(entry)]=candidates
                entry.update(research_signature=signature,research_candidates=[c.to_dict() for c in candidates])
                checkpoint(folder,project,'searching',entry['label'])
                continue
            if entry.get('research_signature') == signature and 'research_candidates' in entry and not entry.get('search_failed') and not (find_more and len(entry.get('options',[]))<choice_limit):
                ranked[id(entry)] = [Media(**{k:v for k,v in data.items() if k in Media.__dataclass_fields__})
                                    for data in entry['research_candidates']]
                searches[signature]=ranked[id(entry)]
                progress('Reusing the saved search for ' + entry['label'])
                continue
            checkpoint(folder, project, 'searching', entry['label'])
            for provider in (web,finder):
                if hasattr(provider,'begin_subject'):provider.begin_subject()
            try:
                entry['search_failed']=False
                candidates = (finder.evidence_candidates(m, entity, []) if finder else []) if m.reference_type=='evidence' else gather(
                    web, m, entity, entry['end']-entry['start'], timeline.orientation,
                    (timeline.width, timeline.height), (), progress, finder,
                    **({'reference_method': method} if method else {}))
                if method and finder is not None:
                    for issue in getattr(finder,'source_evidence_errors',[]):
                        entry.setdefault('preparation_errors',[]).append(
                            'Source page '+str(issue.get('page_url',''))+': '+str(issue.get('error','')))
                if m.reference_type!='evidence':
                    candidates=list({c.id:c for c in previous_sources(root,entity)+candidates}.values())
            except Exception as error:
                entry['search_failed']=True
                entry.setdefault('preparation_errors', []).append(str(error))
                candidates = []
                from hinglish_app.user_messages import problem
                progress(problem(error, feature='Smart Visuals')['message'])
            try:
                candidates = judge(brain, m, entity, candidates, limit=12)
            except Exception as error:
                progress(f'Candidate ranking unavailable: {error}; source and pixel checks still apply')
            ranked[id(entry)] = candidates
            searches[signature]=candidates
            entry.update(research_signature=signature, research_candidates=[c.to_dict() for c in candidates])
            write_json(folder / 'visuals-project.json', project)
            write_report(folder / 'report.html', project)
    if hasattr(brain, 'close'):
        brain.close()
    # A CLIP type-only fallback cannot verify Kohli/RCB versus Kohli/India.
    evaluator = evaluator or open_evaluator(root, 'vlm', settings.vision_check_model, progress=progress)
    if not getattr(evaluator, 'vlm', None):
        raise ValueError('Smart Visuals needs the local vision model to verify the person, team and scene. Start the configured vision model and retry; your sources are kept.')
    if hasattr(evaluator.vlm, 'request_timeout') or hasattr(evaluator.vlm, 'look'):
        evaluator.vlm.request_timeout = 180
    try:
        for timeline, folder, project in results:
            folder = Path(folder)
            project.update(review_options=True, options_per_moment=choice_limit, collecting=True)
            write_json(folder / 'visuals-project.json', project)
            write_report(folder / 'report.html', project)
            for entry in sorted(project['slots'],key=lambda s:s['show']!='logo'):
                if only_entity and entry['entity']!=only_entity:continue
                bank_started=time.monotonic()
                candidates = ranked[id(entry)]
                seen = {o.get('sha256') for o in entry['options']}
                profile_reference(root,entry,project,candidates,web,finder)
                info = context_info(entry,project)
                key = context_key(info)
                for other in project['slots']:
                    if other is entry:continue
                    for option in other.get('options',[]):
                        if len(entry['options'])>=choice_limit:break
                        if option.get('check_context')==key and option.get('sha256') not in seen and Path(option.get('path','')).is_file():
                            entry['options'].append(dict(option))
                            entry['alternatives'].append(dict(option))
                            seen.add(option['sha256'])
                checkpoint(folder, project, 'checking', entry['label'])
                checks = entry.setdefault('candidate_checks', {})
                for media in candidates[:40 if info.get('required_team') else 20]:
                    if len(entry['options']) >= choice_limit:
                        break
                    if time.monotonic()-bank_started>=240:
                        entry['budget_exhausted']=True
                        progress(entry['label']+': saving partial choices and continuing to the next keyword.')
                        break
                    checked_info = candidate_info(info, media)
                    key = context_key(checked_info)
                    prior = checks.get(media.id, {})
                    # Keep failures too. Restarting must not repeatedly pay for
                    # the same rejected picture. Transient download failures get
                    # at most one retry; explicit context recheck clears this.
                    if prior.get('context') == key and (prior.get('verdict') is not None or prior.get('attempts',0)>=2):
                        continue
                    progress(f'Checking {entry["label"]}: option {len(entry["options"])+1}/{choice_limit}, {media.title[:65]}')
                    try:
                        if media.kind == 'video':
                            path, _ = finder.download_video(media, entry['end']-entry['start'])
                            verdict = evaluator.video(path, 0, entry['end']-entry['start'], info)
                            with Path(path).open('rb') as stream:
                                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                        else:
                            path = fetch(root, media, web.session, finder)
                            with Image.open(path) as im:
                                rgba = im.convert('RGBA')
                                digest = hashlib.sha256(rgba.resize((96, 96)).tobytes()).hexdigest()
                            if digest in seen:
                                continue
                            verdict = evaluator.image(path, checked_info)
                        if verdict.passed is not True:
                            entry['rejected'].append({'id': media.id, 'title': media.title,
                                'source': media.source, **verdict.to_dict()})
                            if verdict.passed is None:
                                # A model outage is not twenty bad photographs.
                                checkpoint(folder, project, 'needs_local_model', entry['label'])
                                write_report(folder / 'report.html', project)
                                raise RuntimeError('The local vision model could not finish its check. Your downloaded sources and finished checks are saved. Resume when the local model is available.')
                            checks[media.id] = {'context': key, 'verdict': False}
                            checkpoint(folder, project, 'checking', entry['label'])
                            continue
                        seen.add(digest)
                        target = folder / 'references' / (digest[:20] + Path(path).suffix)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.copyfile(path, target)
                        data = media.to_dict()
                        data.update(path=str(target.resolve()), asset=target.relative_to(folder).as_posix(),
                            evaluation=verdict.to_dict(), sha256=digest, check_context=key)
                        if 'reference_method' in info:
                            data['reference_method'] = info['reference_method']
                        if media.kind == 'image':
                            thumb = folder / 'thumbs' / (digest[:20]+'.png')
                            thumb.parent.mkdir(parents=True, exist_ok=True)
                            with Image.open(target) as im:
                                im = im.convert('RGBA'); im.thumbnail((480, 480)); im.save(thumb)
                            data['report_thumb'] = thumb.relative_to(folder).as_posix()
                        entry['options'].append(data)
                        entry['alternatives'].append(data)
                        write_json(folder / 'visuals-project.json', project)
                        write_report(folder / 'report.html', project)
                    except Exception as error:
                        if project.get('research_state',{}).get('stage')=='needs_local_model':
                            raise
                        attempts = checks.get(media.id,{}).get('attempts',0)+1
                        checks[media.id] = {'context': key, 'attempts': attempts, 'error': str(error)[:800]}
                        entry.setdefault('preparation_errors', []).append(str(error))
                        progress(f'Could not use this candidate: {error}')
                        checkpoint(folder, project, 'checking', entry['label'])
                entry['shortfall'] = max(0, choice_limit-len(entry['options']))
                if entry['shortfall']:
                    progress(f'{entry["label"]}: {len(entry["options"])}/{choice_limit} passed. Missing choices stay empty; no unrelated substitutions.')
                write_json(folder / 'visuals-project.json', project)
                write_report(folder / 'report.html', project)
            project.pop('collecting', None)
            checkpoint(folder, project, 'ready' if all(len(s.get('options',[]))>=choice_limit for s in project['slots']) else 'partial')
            write_outputs(root, folder, project, progress, preview=False)
    finally:
        if own:
            evaluator.close()


def recheck_project(project_file, progress=print, *, force=False, find_more=False, only_entity=None):
    """Recheck saved pixels with the latest context rules, then refill missing choices."""
    file=Path(project_file)
    saved=json.loads(file.read_text('utf-8'))
    if saved.get('search_method')=='website' and saved.get('review_policy')=='human':
        from .manual_web import resume
        return resume(file.resolve().parents[4],file,progress,find_more=find_more,only_entity=only_entity)
    from .pipeline import write_outputs
    from .settings import load_settings
    from .brain import open_brain
    from .web import Web
    from .websearch import WebSearch
    from hinglish_broll.timeline import parse_xmeml
    file=Path(project_file);root=file.parents[4];project=json.loads(file.read_text('utf-8'))
    settings=load_settings(root,device=project.get('device','cpu'))
    # Revalidate source-name resolution too, not just pixels. A wrong canonical
    # name can make even a perfect face checker approve the wrong subject.
    from .planner import resolve_entity
    from hinglish_eval.model_rules import sounds_like
    suspect = [key for key, spec in project['entities'].items() if (not only_entity or key==only_entity) and spec.get('kind') == 'person'
        and (not spec.get('qid') or (spec.get('label') and not any(
            sounds_like(spec['name'], name, threshold=.58)
            for name in [spec['label']] + spec.get('aliases', []) if name)))]
    if suspect:
        brain = open_brain(root, progress=progress)
        if hasattr(brain,'session'):brain.request_timeout=180;brain.request_attempts=2
        try:
            for key in suspect:
                old = project['entities'][key]
                progress('Rechecking the spoken identity: ' + old['name'])
                for entry in project['slots']:
                    if entry['entity'] != key: continue
                    entry.setdefault('rejected', []).extend({**o, 'passed': False,
                        'reasons': ['The canonical name did not match the spoken name; identity must be resolved again.']}
                        for o in entry.get('options', []))
                    entry.update(options=[], alternatives=[], chosen=None, clip=None, evaluation=None)
                write_outputs(root, file.parent, project, progress, preview=False)
                found = resolve_entity(brain, Web(root), {'key': key, 'name': old['name'],
                    'kind': 'person', 'about': old.get('description', '')},
                    {**project.get('summary',{}),'spoken_context':' '.join(s['text'] for s in project['slots'] if s['entity']==key)},
                    finder=WebSearch(root, progress))
                new = found or Entity(key, old['name'], 'person', label=old['name'],
                    description=old.get('description', ''))
                project['entities'][key] = new.to_dict()
                for entry in project['slots']:
                    if entry['entity'] != key: continue
                    entry['label'] = new.label or new.name
                    for field in ('visual', 'meaning'):
                        entry[field] = entry.get(field, '').replace(old['label'], entry['label'])
                    for field in ('queries', 'evidence_terms'):
                        entry[field] = [s.replace(old['label'], entry['label']) for s in entry.get(field, [])]
                project.setdefault('identity_rechecks', []).append({'spoken_name': old['name'],
                    'previous_label': old['label'], 'label': new.label, 'qid': new.qid})
                write_outputs(root, file.parent, project, progress, preview=False)
        finally:
            brain.close()
    evaluator=open_evaluator(root,'vlm',settings.vision_check_model,progress=progress)
    if hasattr(evaluator.vlm, 'look'):evaluator.vlm.request_timeout=180
    try:
        project['collecting']=True
        for entry in project['slots']:
            if only_entity and entry['entity']!=only_entity:continue
            info=context_info(entry,project);key=context_key(info)
            previous=entry.pop('pending_options',[])+entry.get('options',[])
            kept=[d for d in previous if not force and d.get('check_context')==context_key(candidate_info(info,d))
                  and (file.parent/d['asset']).is_file()]
            pending=[d for d in previous if d not in kept]
            entry.update(options=kept,alternatives=list(kept),pending_options=pending)
            checkpoint(file.parent,project,'rechecking',entry['label'])
            from .report import write_report
            write_report(file.parent/'report.html',project)
            while pending:
                data=pending[0]
                progress('Rechecking '+entry['label']+': '+data['title'][:70])
                path=file.parent/data['asset']
                checked_info=candidate_info(info,data);key=context_key(checked_info)
                verdict=(evaluator.image(path,checked_info) if data['kind']=='image' else
                    evaluator.video(path,0,entry['end']-entry['start'],checked_info))
                if verdict.passed is None:
                    raise RuntimeError('The local vision model is unavailable. Saved choices have been kept; resume after the model is running.')
                if verdict.passed is True:
                    data['evaluation']=verdict.to_dict()
                    data['check_context']=key
                    if data.get('sha256') not in {d.get('sha256') for d in kept}:kept.append(data)
                else:
                    entry['rejected'].append({'id':data['id'],'title':data['title'],'source':data['source'],**verdict.to_dict()})
                pending.pop(0)
                entry['alternatives']=list(kept)
                checkpoint(file.parent,project,'rechecking',entry['label'])
                write_report(file.parent/'report.html',project)
            entry.pop('pending_options',None)
            entry['options']=kept
            if force:entry.pop('candidate_checks',None)
            entry['alternatives']=list(kept)
            if entry.get('chosen') and entry['chosen']['id'] not in {d['id'] for d in kept}:
                entry.update(chosen=None,clip=None,evaluation=None)
        # Persist removals before any further network calls, so a failed refill cannot retain a bad approval.
        write_outputs(root,file.parent,project,progress,preview=False)
    finally:evaluator.close()
    brain=open_brain(root,progress=progress)
    if hasattr(brain,'session'):brain.request_timeout=180;brain.request_attempts=2
    try:
        collect(root,[(parse_xmeml(project['timeline']['xml_path']),file.parent,project)],brain,
            Web(root),WebSearch(root,progress),settings,progress,find_more=find_more,only_entity=only_entity)
    finally:brain.close()
    return {'filled':sum(len(s.get('options',[])) for s in project['slots'])}


def capcut_spec(project_file):
    """Original audio and only saved selected visual clips, at their spoken timestamps."""
    from hinglish_broll.timeline import parse_xmeml
    file = Path(project_file); p = json.loads(file.read_text('utf-8'))
    t = parse_xmeml(p['timeline']['xml_path']); micro = lambda n: round(n*1e6)
    if len(t.clips) != 1:
        return None
    return {'fps': float(t.fps), 'width': t.width, 'height': t.height, 'duration': micro(t.duration),
        'clips': [{'path': c.path, 'start': micro(c.start), 'source_in': micro(c.source_in),
            'duration': micro(c.end-c.start)} for c in t.clips],
        'overlays': [{'path': str((file.parent/s['clip']).resolve()), 'start': micro(s['start']),
            'source_in': 0, 'duration': micro(s['end']-s['start'])} for s in p['slots'] if s.get('clip')],
        'options': [], 'visuals': True, 'selected_only': True}
