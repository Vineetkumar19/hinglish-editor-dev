"""Independent, source-backed music/SFX alternatives from prepared local rankings.

No Brain/Listener construction, automatic pipeline, audio mix, render, download or
host operation. Supply cached analysis and either CachedRankingIndex or an
explicitly prepared existing SoundIndex. A cache miss never starts a model here.
"""
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

from .recommendation_runtime import CancellationToken,RecommendationCancelled,Telemetry
from .relevance import source_matches
from .retrieval import physical_evidence_supported
from .settings import SFX_BEHAVIOUR

SCHEMA='storylens.sound-recommendations'
VERSION=1


class RankingCacheMiss(Exception):pass


class CachedRankingIndex:
    """In-memory view of already measured assets, ranked query hits and facts.

    Query values are ordered (asset.path, score) pairs. No inference or repair.
    An existing SoundIndex search result can populate this snapshot unchanged.
    """
    cache_status='hit'
    prepared_only=True
    def __init__(self, assets, queries, *, facts=None):
        self.assets=list(assets);self.queries=copy.deepcopy(queries);self.facts=facts or {}
        self.by_path={str(Path(a.path).resolve()):a for a in self.assets}

    def facts_for(self, asset):return copy.deepcopy(self.facts.get(asset.path,{}))

    def search(self, query, *, top=20, categories=None, instrumental_only=False, banned=(), **options):
        if query not in self.queries:raise RankingCacheMiss('This query has no prepared ranking')
        banned={str(Path(p).resolve()) for p in banned};out=[]
        for path,score in self.queries[query]:
            a=self.by_path.get(str(Path(path).resolve()))
            if a is None or str(Path(a.path).resolve()) in banned:continue
            if categories and a.category not in categories:continue
            if instrumental_only and self.facts_for(a).get('vocals') is True:continue
            out.append((a,score,'cached ranking'))
            if len(out)>=top:break
        return out


def _json(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
def _id(value):return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _number(value, label, low, high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Check '+label+'; use a finite number within the source/timeline bounds.')
    return float(value)


def _validate(request, limit):
    request=json.loads(_json(request))
    if type(limit) is not int or not 1<=limit<=20:raise ValueError('Choose 1–20 alternatives per group')
    seconds=_number(request.get('timeline',{}).get('duration'),'timeline duration',.001,86400.)
    timeline=request['timeline']
    if not isinstance(timeline.get('id'),str) or not timeline['id'].strip():raise ValueError('Keep the stable source timeline ID')
    try:fps=Fraction(str(timeline.get('fps')))
    except (ValueError,ZeroDivisionError):raise ValueError('Keep a valid timeline frame rate') from None
    if not 0<fps<=240:raise ValueError('Keep a valid timeline frame rate')
    if not isinstance(request.get('script'),str) or not isinstance(request.get('creator_context'),dict):
        raise ValueError('Keep the exact shared script and full creator context with the request')
    if not isinstance(request.get('library_revision'),str) or not request['library_revision'].strip():
        raise ValueError('Provide the prepared library revision so cached recommendations can be identified')
    for key in ('music_sections','sfx_events'):
        rows=request.get(key,[])
        if not isinstance(rows,list) or len(rows)>5000:raise ValueError('Supply at most 5,000 bounded groups of each kind')
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'].strip() or len(row['id'])>160:
                raise ValueError('Every section/event needs a stable ID')
            if row['id'] in seen:raise ValueError('Section/event IDs must be unique within each kind')
            seen.add(row['id'])
            a=_number(row.get('start'),'group start',0.,seconds)
            b=_number(row.get('end'),'group end',0.,seconds)
            if b<=a:raise ValueError('Every group needs positive duration')
            if not isinstance(row.get('intent'),str) or not row['intent'].strip() or len(row['intent'])>1000:
                raise ValueError('Describe the actual desired sound or music')
            _number(row.get('level_db'),'proposed level',-60.,6.)
            if 'role' in row and (not isinstance(row['role'],str) or not row['role'].strip() or len(row['role'])>80):
                raise ValueError('A sound role must be a short text label')
            rejected=row.get('rejected_source_ids',[])
            if not isinstance(rejected,list) or any(not isinstance(v,str) or not v.strip() for v in rejected):
                raise ValueError('Keep rejected source identities in a list')
            evidence=row.get('evidence')
            if not isinstance(evidence,dict) or not isinstance(evidence.get('description'),str) or not evidence['description'].strip():
                raise ValueError('Keep the actual script/scene evidence for each group')
            _number(evidence.get('confidence'),'evidence confidence',0.,1.)
            if any(not isinstance(evidence.get(k),str) or not evidence[k].strip() for k in ('kind','precision')):
                raise ValueError('Keep the evidence kind and timing precision')
            if row.get('decision') is not None and (type(row['decision']) is not int or row['decision']!=-1):
                raise ValueError('A stored rejection must be explicit -1; recommendations do not auto-select a candidate')
            if row.get('processing'):
                from .processing import validate
                row['processing']=validate(row['processing'])
            elif 'processing' in row and row['processing']!={}:raise ValueError('Sound processing must be a typed object')
            if key=='sfx_events' and row.get('sound_type') not in SFX_BEHAVIOUR:raise ValueError('Choose a supported SFX sound type')
    return request


def _audio_bounds(path):
    import av
    with av.open(str(path)) as media:
        if not media.streams.audio:raise ValueError('The candidate is not playable audio')
        stream=media.streams.audio[0]
        seconds=float(stream.duration*stream.time_base) if stream.duration is not None else float(media.duration or 0)/av.time_base
        return _number(seconds,'available audio duration',.001,86400.)


def _hash(path, token):
    before=path.stat();digest=hashlib.sha256()
    with path.open('rb') as source:
        while data:=source.read(1024*1024):token.check();digest.update(data)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('The source changed while it was being identified')
    return digest.hexdigest(),after


def _credits(path):
    sidecar=Path(str(path)+'.json')
    if not sidecar.is_file():return {'status':'unknown_owner_supplied','license':None,'source_url':None,'metadata_sha256':None}
    if sidecar.stat().st_size>262144:raise ValueError('Source credit metadata is too large')
    raw=sidecar.read_bytes();value=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('Source credit metadata must be an object')
    result=dict(status='provided_not_independently_verified',license=value.get('license') or value.get('licence'),
        source_url=value.get('source_url') or value.get('url'),author=value.get('author') or value.get('username'),
        attribution=value.get('attribution'),license_url=value.get('license_url'),
        metadata_sha256=hashlib.sha256(raw).hexdigest())
    if any(v is not None and not isinstance(v,str) for v in result.values()):raise ValueError('Source credit fields must be text')
    return result


def _source(asset, root, roots, token, audit, memo):
    path=Path(asset.path).resolve()
    if not any(path.is_relative_to(p) for p in roots):raise ValueError('The candidate is outside the prepared library roots')
    if path.is_relative_to(root/'output/sound') or path.name.lower() in ('dialogue.wav','original-audio.wav','full-mix.wav','music-bed.wav'):
        raise ValueError('Original/dialogue/generated soundtrack stems are not recommendation candidates')
    stat=path.stat();key=(str(path),stat.st_size,stat.st_mtime_ns)
    with audit.stage('source.identity',kind='call',cache='hit' if key in memo else 'miss'):
        token.check()
        if key not in memo:
            sha,after=_hash(path,token)
            duration=min(_audio_bounds(path),_number(asset.duration,'cached source duration',.001,86400.))
            memo[key]=dict(path=str(path),sha256=sha,bytes=after.st_size,modified_ns=after.st_mtime_ns,
                available_start=0.,available_end=duration,bounds_basis='minimum of cached index and demux duration',credits=_credits(path))
        return copy.deepcopy(memo[key])


def _evidence_ok(slot):
    family=slot['sound_type'];e=slot['evidence']
    if family not in ('foley','ambience'):return True
    if e.get('kind') not in ('vision','editor','measured'):return False
    if e['confidence']<(.8 if family=='foley' else .7):return False
    if family=='foley' and e.get('precision') not in ('visual_interval','editor','measured'):return False
    return physical_evidence_supported(slot['intent'],{'label':e['description']})


def _candidate_id(fingerprint,gid,source,timeline):
    return 'candidate-'+_id([fingerprint,gid,source['sha256'],source['path'],source['in'],source['out'],
                            source.get('credit_sha256'),timeline])[:24]


def verify_candidate_source(root, candidate, *, allowed_roots=None, banned_paths=(), token=None):
    """Read-only pre-import guard; suite must resolve IDs from its saved manifest.

    Verifies bytes, credits and playable bounds. This is not a native import,
    semantic approval, or permission to use an arbitrary client-supplied path.
    """
    root=Path(root).resolve();token=token or CancellationToken();token.check()
    roots=[Path(p).resolve() for p in (allowed_roots if allowed_roots is not None else [root/'library'])]
    if candidate.get('kind') not in ('music','sfx'):raise ValueError('Choose a music or SFX candidate')
    source=candidate['source'];path=Path(source['path']).resolve()
    from .learning import load,banned as saved_bans
    banned={str(Path(p).resolve()) for p in list(banned_paths)+list(saved_bans(load(root)))}
    if (not any(path.is_relative_to(p) for p in roots) or path.is_relative_to(root/'output/sound') or
        str(path) in banned or path.name.lower() in ('dialogue.wav','original-audio.wav','full-mix.wav','music-bed.wav')):
        raise ValueError('Choose an eligible source from the prepared library')
    try:
        digest,_=_hash(path,token);credits=_credits(path);available=_audio_bounds(path)
        if (digest!=source['sha256'] or credits.get('metadata_sha256')!=candidate['credits'].get('metadata_sha256') or
            credits.get('metadata_sha256')!=source.get('credit_sha256')):
            raise ValueError('The candidate source or credits changed; refresh this recommendation')
    except OSError as error:raise ValueError('The candidate source changed or is unavailable; keep saved progress and relink it') from error
    a=_number(source['in'],'candidate source in',0.,available)
    b=_number(source['out'],'candidate source out',a,available)
    t=_number(candidate['timeline']['start'],'candidate timeline start',0.,86400.)
    end=_number(candidate['timeline']['end'],'candidate timeline end',t,86400.)
    _number(candidate['proposed_level_db'],'candidate level',-60.,6.)
    if b<=a or abs((b-a)-(end-t))>1e-6:raise ValueError('The source excerpt and timeline duration differ')
    return dict(path=str(path),sha256=digest,source_in=a,source_out=b,verified=True,imported=False)


def _verify_saved(group, token, root, roots, fingerprint, slot, kind, limit, banned):
    if group.get('kind')!=kind or group.get('id')!=kind+':'+slot['id'] or len(group.get('candidates',[]))>limit:
        raise ValueError('The checkpoint group changed; keep it and start a new version')
    if slot.get('decision')==-1 and (group.get('candidates') or group.get('decision')!=-1):
        raise ValueError('The checkpoint changed a saved rejection')
    for candidate in group.get('candidates',[]):
        source=candidate['source'];path=Path(source['path']).resolve()
        if not any(path.is_relative_to(p) for p in roots) or path.is_relative_to(root/'output/sound') or str(path) in banned:
            raise ValueError('The checkpoint source is outside the allowed library or is banned')
        timeline=candidate['timeline']
        a=_number(source['in'],'checkpoint source in',0.,source['available_end'])
        b=_number(source['out'],'checkpoint source out',a,source['available_end'])
        t=_number(timeline['start'],'checkpoint start',slot['start'],slot['start'])
        end=_number(timeline['end'],'checkpoint end',t,slot['end'])
        if b<=a or abs((b-a)-(end-t))>1e-6 or candidate.get('proposed_level_db')!=slot['level_db']:
            raise ValueError('The checkpoint timing or level changed')
        if candidate.get('kind')!=kind or candidate.get('id')!=_candidate_id(fingerprint,group['id'],source,timeline):
            raise ValueError('The checkpoint candidate identity changed')
        try:
            digest,_=_hash(path,token)
            same=(digest==source['sha256'] and b<=_audio_bounds(path)+1e-6 and
                  _credits(path).get('metadata_sha256')==candidate['credits'].get('metadata_sha256'))
        except OSError:same=False
        if not same:raise ValueError('A checkpoint source or its credits changed; keep the checkpoint and start a new version.')


def recommend(root, request, music_index, sfx_index, *, limit=5, allowed_roots=None,
              banned_paths=(), passage_selector=None, token=None, telemetry=None,
              checkpoint=None, on_group=None, allow_live_ranking=False):
    """Return a v1 review manifest; never select, import or mix the alternatives.

    Inputs are already timed sections/events and prepared local rankings. Default
    auditions reference the real source head plus an explicit seek/stop window;
    supply a cached passage selector for measured alternative source offsets.
    Existing SoundIndex requires explicit allow_live_ranking release, because its
    search method may run an embedding model on a query cache miss.
    """
    root=Path(root).resolve();request=_validate(request,limit)
    if type(allow_live_ranking) is not bool:raise ValueError('Choose cached or explicitly released live ranking')
    if not allow_live_ranking and any(getattr(i,'prepared_only',False) is not True for i in (music_index,sfx_index)):
        raise ValueError('Use prepared cached ranking snapshots; live ranking needs an explicit resource release')
    token=token or CancellationToken();audit=telemetry or Telemetry()
    roots=[Path(p).resolve() for p in (allowed_roots if allowed_roots is not None else [root/'library'])]
    from .learning import load,banned as saved_bans
    banned={str(Path(p).resolve()) for p in list(banned_paths)+list(saved_bans(load(root)))}
    passage_revision=request.get('passage_revision','source-head-v1' if passage_selector is None else 'unversioned-caller-selector')
    if checkpoint and passage_selector is not None and passage_revision=='unversioned-caller-selector':
        raise ValueError('Version the cached passage selector before checkpointing it')
    fingerprint=_id(dict(version=VERSION,request=request,limit=limit,roots=[str(p) for p in roots],
                         banned=sorted(banned),passage_revision=passage_revision,allow_live_ranking=allow_live_ranking))
    result=dict(schema=SCHEMA,version=VERSION,id='soundrec-'+fingerprint[:24],fingerprint=fingerprint,
        status='running',timeline=copy.deepcopy(request['timeline']),script=request['script'],
        creator_context=copy.deepcopy(request['creator_context']),library_revision=request['library_revision'],
        capabilities={'mixed':False,'rendered_auditions':False,'host_imported':False,'automatic_selection':False},
        groups=[],telemetry=[])
    saved=checkpoint.load(fingerprint) if checkpoint else None
    prior={g['id']:g for g in saved.get('groups',[])} if saved else {}
    memo={}
    try:
        for kind,key,index in (('music','music_sections',music_index),('sfx','sfx_events',sfx_index)):
            for slot in request.get(key,[]):
                token.check();gid=kind+':'+slot['id']
                if gid in prior:
                    with audit.stage('checkpoint.group',cache='hit'):
                        _verify_saved(prior[gid],token,root,roots,fingerprint,slot,kind,limit,banned)
                    group=copy.deepcopy(prior[gid])
                else:
                    with audit.stage('recommendation.group',cache='miss',metadata={'kind':kind,'id':gid}):
                        group=_group(root,roots,index,kind,slot,gid,fingerprint,limit,banned,passage_selector,token,audit,memo)
                result['groups'].append(group)
                if checkpoint:checkpoint.save(fingerprint,result['groups'],'partial')
                if on_group:on_group(copy.deepcopy(group))
        token.check()
        result['status']='ready' if any(g['candidates'] for g in result['groups']) else 'no_match'
        if checkpoint:checkpoint.save(fingerprint,result['groups'],result['status'])
    except RecommendationCancelled as error:
        result.update(status='cancelled',notice=str(error))
        if checkpoint:checkpoint.save(fingerprint,result['groups'],'cancelled')
    result['telemetry']=copy.deepcopy(audit.receipts)
    return result


def _group(root,roots,index,kind,slot,gid,fingerprint,limit,banned,selector,token,audit,memo):
    group=dict(id=gid,kind=kind,timeline={'start':float(slot['start']),'end':float(slot['end'])},
        intent=slot['intent'],role=slot.get('role','bed' if kind=='music' else 'detail'),
        evidence=copy.deepcopy(slot['evidence']),decision=slot.get('decision'),
        status='no_match',reason_code='no_eligible_candidates',candidates=[],rejections=[])
    if slot.get('decision')==-1:
        group.update(status='rejected',reason_code='owner_or_saved_rejection');return group
    if kind=='sfx' and not _evidence_ok(slot):
        group['reason_code']='unsupported_source_evidence';return group
    options=dict(top=max(20,limit*4),banned=banned)
    if kind=='music':options.update(categories=[slot['mood']] if slot.get('mood') else None,instrumental_only=True)
    else:options['categories']=None if slot['sound_type'] in ('foley','ambience') else [slot['sound_type']]
    try:
        with audit.stage('rank.'+kind,kind='call',cache=getattr(index,'cache_status','unknown'),retry=0):
            token.check();hits=index.search(slot['intent'],**options);token.check()
    except RankingCacheMiss:
        group['reason_code']='ranking_cache_missing';return group
    registered={str(Path(a.path).resolve()) for a in index.assets}
    seen=set();rejected_ids=set(slot.get('rejected_source_ids',[]))
    for asset,score,*_ in hits:
        token.check()
        if len(group['candidates'])>=limit:break
        path=str(Path(asset.path).resolve())
        try:
            if path not in registered or path in banned or asset.kind!=kind:raise ValueError('Candidate is unregistered, banned or the wrong media kind')
            score=_number(score,'ranking score',-1e6,1e6)
            facts=index.facts_for(asset) or {}
            _json(facts)
            if kind=='music' and facts.get('vocals') is True:raise ValueError('Singing is excluded from these instrumental alternatives')
            if kind=='sfx':
                ok,reason=source_matches(asset,slot['sound_type'],slot['intent'])
                if not ok:raise ValueError(reason)
            source=_source(asset,root,roots,token,audit,memo)
            if source['sha256'] in seen or source['sha256'] in rejected_ids or 'sha256:'+source['sha256'] in rejected_ids:continue
            selection=selector(asset,copy.deepcopy(slot)) if selector else {'source_in':0.,'basis':'source head; not acoustically auditioned'}
            token.check();available=source['available_end']
            offset=_number(selection.get('source_in'),'source in',0.,available)
            desired=slot['end']-slot['start'];duration=min(desired,available-offset)
            if duration<.001 or kind=='sfx' and duration+1e-6<desired:raise ValueError('The recording cannot cover the requested sound without stretching')
            end=offset+duration
            if selection.get('source_out') is not None:
                end=_number(selection['source_out'],'source out',offset,available);duration=end-offset
                if duration<.001 or duration>desired+1e-6 or kind=='sfx' and duration+1e-6<desired:raise ValueError('The cached excerpt does not fit this section/event')
            source.update({'in':offset,'out':end,'selection_basis':str(selection.get('basis','caller supplied cached window'))})
            credits=source.pop('credits');source['credit_sha256']=credits.get('metadata_sha256')
            timeline={'start':float(slot['start']),'end':float(slot['start']+duration)}
            group['candidates'].append(dict(id=_candidate_id(fingerprint,gid,source,timeline),group_id=gid,kind=kind,
                rank=len(group['candidates'])+1,rank_score=score,name=asset.name,source=source,credits=credits,
                timeline=timeline,role=group['role'],sound_type=slot.get('sound_type'),mood=slot.get('mood'),
                proposed_level_db=float(slot['level_db']),reason=slot.get('reason') or slot['intent'],
                confidence={'value':float(slot['evidence']['confidence']),'basis':'provided evidence; ranking score is not a probability'},
                evidence=copy.deepcopy(slot['evidence']),listening=copy.deepcopy(facts),review_required=True,
                coverage='complete' if duration+1e-6>=desired else 'partial',loop=False,
                audition={'path':source['path'],'in':offset,'out':end,'rendered':False},
                processing=copy.deepcopy(slot.get('processing',{}))))
            seen.add(source['sha256'])
        except (OSError,ValueError) as error:
            group['rejections'].append({'path':path,'reason':str(error),'selected':False})
    if group['candidates']:group.update(status='candidates',reason_code='ranked_local_sources')
    return group
