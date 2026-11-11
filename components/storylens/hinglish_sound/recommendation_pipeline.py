"""Fresh local analysis -> timed, source-backed alternatives, without a full mix.

Independent entry point for the suite's normal local-agent dispatch. It does not
register routes, import into an editor, resume semantic checkpoints or call the
automatic rendering pipeline. An injected factory is always labelled test data.
"""
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import time
import uuid

from .recommendation_runtime import CancellationToken, RecommendationCancelled, write_json_atomic
from .recommendations import CachedRankingIndex, recommend


class InsufficientAnalysis(ValueError): pass


def _plain(value):
    if is_dataclass(value): return _plain(asdict(value))
    if isinstance(value, Path): return str(value)
    if isinstance(value, dict): return {str(k): _plain(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [_plain(v) for v in value]
    if hasattr(value, 'tolist'): return value.tolist()
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(_plain(value), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'authorization|password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|cookie',str(k),re.I)
                else _redact(v) for k,v in value.items()}
    if isinstance(value, list): return [_redact(v) for v in value]
    if isinstance(value, str):
        if value.lstrip().startswith(('{','[')):
            try: return json.dumps(_redact(json.loads(value)),ensure_ascii=False)
            except (ValueError,TypeError): pass
        value = re.sub(r'(?i)\bBearer\s+[^\s"\'<>]+', 'Bearer [REDACTED]', value)
        return re.sub(r'(?i)([?&](?:token|api[_-]?key|key|signature)=)[^&\s]+', r'\1[REDACTED]', value)
    return value


class Journal:
    """Own safe receipts; deliberately does not modify the protected Telemetry."""
    def __init__(self, folder, clock=time.monotonic):
        self.folder=Path(folder); self.folder.mkdir(parents=True, exist_ok=True)
        self.clock=clock; self.receipts=[]; self.count=0

    def record(self, label, payload):
        self.count += 1
        name=f'{self.count:04d}-{re.sub("[^a-zA-Z0-9_-]", "-", label)[:70]}.json'
        write_json_atomic(self.folder/name, _redact(_plain(payload)))
        return str(self.folder/name)

    @contextmanager
    def stage(self, name):
        start=self.clock(); row={'stage':name,'cache':'unknown','status':'running'}
        try:
            yield row
            row['status']='finished'
        except RecommendationCancelled:
            row['status']='cancelled'; raise
        except Exception:
            row['status']='failed'; raise
        finally:
            row['elapsed_seconds']=max(0.,self.clock()-start)
            self.receipts.append(row); self.record('stage-'+name,row)


def run(root, input_path, script, creator_context, *, runtime_factory=None,
        execute_local=False, resource_lease=None, expected_models=None,
        token=None, script_role='spoken_reference', limit=5, density='medium', progress=print):
    """Callable by an application worker already holding the suite's GPU lease.

    A release/lease is an execution gate, not a second lock or an authorization
    mechanism. The suite owns queue serialization. No model is started by default.
    Each call is fresh; interrupted evidence is kept but never silently resumed.
    """
    if runtime_factory is None and (execute_local is not True or not isinstance(resource_lease,str) or not resource_lease.strip()):
        raise ValueError('Local analysis needs the suite resource release and a nonempty resource lease.')
    if not isinstance(script,str) or not isinstance(creator_context,dict): raise ValueError('Keep the exact script and full creator context.')
    if script_role not in ('spoken_reference','context_only'): raise ValueError('Choose spoken_reference or context_only for the script.')
    if density not in ('low','medium','high'): raise ValueError('Choose a supported sound density.')
    if type(limit) is not int or not 1<=limit<=20: raise ValueError('Choose 1–20 alternatives per group.')
    root=Path(root).resolve(); source=Path(input_path).resolve()
    if not source.is_file(): raise ValueError('Select an existing video or XML timeline.')
    folder=root/'output/sound-recommendations'/(datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    token=token or CancellationToken(); journal=Journal(folder/'receipts')
    context=dict(root=str(root),input_path=str(source),script=script,creator_context=creator_context,
                 script_role=script_role,density=density,folder=str(folder))
    write_json_atomic(folder/'input.json',context)
    result=dict(schema='storylens.sound-analysis-recommendations',version=1,status='running',
                folder=str(folder),test_factory_used=runtime_factory is not None,
                local_agent_acceptance=False,resource_lease=resource_lease,
                automatic_path_changed=False,rendered=False,native_imported=False)
    runtime=None
    try:
        token.check()
        factory=runtime_factory or LocalRuntime
        runtime=factory(root,folder,journal,progress)
        result['models']=runtime.models
        for role,name in (expected_models or {}).items():
            if runtime.models.get(role,{}).get('name') != name: raise ValueError('The exact requested local model is not selected: '+role)
        for stage in ('prepare','transcribe','observe','prosody','inventory','plan'):
            token.check()
            with journal.stage(stage):
                payload=runtime.invoke(stage,context,journal)
                write_json_atomic(folder/(stage+'.json'),_plain(payload)); context[stage]=payload
            token.check()
            if stage=='prepare':
                seconds=payload.get('duration')
                if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<=0: raise InsufficientAnalysis('The timeline has no measured duration.')
            if stage=='transcribe' and script_role=='spoken_reference' and not payload.get('lines'):
                raise InsufficientAnalysis('Speech timing is unavailable. Check the source audio or choose a context-only script for silent footage.')
            if stage=='observe' and not payload:
                raise InsufficientAnalysis('The video did not produce usable scene evidence. No generic sound fallback was substituted.')
        plan=context['plan']
        if not plan.get('music_sections') and not plan.get('sfx_events'):
            raise InsufficientAnalysis('The local analysis returned no motivated sound groups. No click template was substituted.')
        request=dict(timeline=context['prepare'],script=script,creator_context=creator_context,
                     library_revision=context['inventory']['revision'],passage_revision='measured-energy-v1',
                     music_sections=plan.get('music_sections',[]),sfx_events=plan.get('sfx_events',[]))
        # Validate before a potentially expensive rank/model call.
        from .recommendations import _validate
        _validate(request,limit)
        write_json_atomic(folder/'request.json',request)
        with journal.stage('prepare-rankings'):
            music,sfx,roots=runtime.rankings(request,journal,token,limit)
        token.check()
        with journal.stage('recommendations'):
            manifest=recommend(root,request,music,sfx,limit=limit,allowed_roots=roots,
                               passage_selector=runtime.passage,token=token,checkpoint=None)
            manifest['analysis_provenance']=dict(test_factory_used=runtime_factory is not None,
                models=runtime.models,local_agent_acceptance=False,semantic_checkpoint_resumed=False)
            write_json_atomic(folder/'manifest.json',manifest)
        result.update(status=manifest['status'],manifest=str(folder/'manifest.json'))
        result['notice']='Sound alternatives are ready for review.' if result['status']=='ready' else 'No eligible library matches were found for these sound groups.'
    except RecommendationCancelled as error:
        result.update(status='cancelled',notice='Sound analysis stopped. Saved evidence has been kept.',technical_details=_redact(str(error)))
    except InsufficientAnalysis as error:
        result.update(status='insufficient_analysis',notice=str(error))
    except Exception as error:
        from hinglish_app.user_messages import problem
        issue=problem(error,feature='Sound suggestions')
        result.update(status='failed',notice=issue['message'],error_code=issue['code'],
                      technical_details=_redact(issue['details']))
    finally:
        if runtime is not None:
            try: runtime.close()
            except Exception as error: result['cleanup_details']=_redact(str(error))
        result['stages']=journal.receipts
        write_json_atomic(folder/'result.json',result)
    return result


class _CachePath:
    """Observe this Brain instance's actual cache file reads, not guessed hits."""
    def __init__(self,path,journal): self.path=Path(path);self.journal=journal
    def __fspath__(self): return str(self.path)
    def __truediv__(self,name): return _CachePath(self.path/name,self.journal)
    def __getattr__(self,name): return getattr(self.path,name)
    def read_text(self,*args,**kwargs):
        answer=self.path.read_text(*args,**kwargs)
        self.journal.record('cache-read',dict(tool='cache.read',path=str(self.path),sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()))
        return answer
    def write_text(self,*args,**kwargs):
        result=self.path.write_text(*args,**kwargs)
        self.journal.record('cache-write',dict(tool='cache.write',path=str(self.path),sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()))
        return result


class _BrainReceipt:
    def __init__(self, brain, journal, context):
        self.brain=brain; self.journal=journal; self.context=context
        self.model=brain.model; self.embed_model=brain.embed_model
        brain.cache=_CachePath(brain.cache,journal)

    def ask(self, system, data, schema, **options):
        # Keep the full profile even for general profiles skipped by global inject.
        data=dict(data,creator_profile=self.context,creator_context_json=json.dumps(self.context,ensure_ascii=False,allow_nan=False))
        before=set(self.brain.cache.glob('*.json'))
        calls=self.journal.count
        self.journal.record('planning-tool-request',dict(system=system,data=data,schema=schema,options=options))
        answer=self.brain.ask(system,data,schema,**options)
        changed=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in set(self.brain.cache.glob('*.json'))-before]
        self.journal.record('planning-tool-response',dict(answer=answer,new_cache_artifacts=changed,
            transport_receipts_after=calls,cache='miss' if changed else 'unknown',
            note='No new file does not by itself establish cache identity. See captured HTTP calls.'))
        return answer

    def embed(self, texts, **kwargs):
        self.journal.record('embedding-tool-request',dict(model=self.embed_model,texts=texts))
        answer=self.brain.embed(texts,**kwargs)
        self.journal.record('embedding-tool-response',dict(model=self.embed_model,shape=list(answer.shape),
            transport_cache='unobserved by this adapter; existing encoder owns its session'))
        return answer


def _transport(owner, journal, expected_model, folder, *, embedding_model=None):
    """Capture only this model instance, never global sessions or raw headers."""
    original=owner.session.post
    def post(url, **kwargs):
        models={'http://127.0.0.1:11434/api/chat':expected_model}
        if embedding_model: models['http://127.0.0.1:11434/api/embed']=embedding_model
        if url not in models: raise ValueError('Unexpected local model endpoint')
        body=kwargs.get('json',{})
        if body.get('model')!=models[url]: raise ValueError('The requested local model changed during analysis')
        capture=json.loads(json.dumps(body))
        for message in capture.get('messages',[]):
            if 'images' in message:
                import base64
                refs=[]
                for image in message['images']:
                    raw=base64.b64decode(image,validate=True); digest=hashlib.sha256(raw).hexdigest()
                    path=Path(folder)/'input-blobs'/f'{digest}.bin'; path.parent.mkdir(exist_ok=True); path.write_bytes(raw)
                    refs.append(dict(path=str(path),sha256=digest,encoding='base64 of referenced bytes'))
                message['images']=refs
        journal.record('model-http-request',dict(provider='local Ollama',url=url,body=capture))
        start=time.monotonic(); response=original(url,**kwargs)
        try: payload=response.json()
        except ValueError: payload={'non_json_response':True}
        journal.record('model-http-response',dict(elapsed_seconds=time.monotonic()-start,status=response.status_code,payload=payload))
        return response
    owner.session.post=post


def sound_model_names(root,config):
    """A sound-only trained planner must not change other features or Vision."""
    names={role:config.get(key) for role,key in [('planning','planning_model'),('vision','vision_model'),('embedding','embedding_model')]}
    path=Path(root)/'config.sound.local.json'
    if path.is_file():
        settings=json.loads(path.read_text(encoding='utf-8-sig'))
        if 'think_model' in settings and settings['think_model']!='qwen3:8b':
            names['planning']=settings['think_model']
    if any(not isinstance(n,str) or not n.strip() or ':cloud' in n.lower() or '://' in n for n in names.values()):
        raise ValueError('Choose explicit installed local planning, vision and embedding models.')
    return names


class LocalRuntime:
    """Lazy real adapters. Construction is reached only after the execution gate."""
    def __init__(self,root,folder,journal,progress):
        from hinglish_cut.model_preferences import preferences
        import requests
        self.root=Path(root); self.folder=Path(folder); self.journal=journal; self.progress=progress
        self.config=preferences(root); self.brain=None; self.listener=None
        names=sound_model_names(root,self.config)
        with requests.Session() as session:
            session.trust_env=False
            tags=session.get('http://127.0.0.1:11434/api/tags',timeout=5); tags.raise_for_status()
            version=session.get('http://127.0.0.1:11434/api/version',timeout=5); version.raise_for_status()
        available={m['name']:m for m in tags.json().get('models',[])}
        self.models={}
        for role,name in names.items():
            item=available.get(name) or available.get(name+':latest')
            if not item or not item.get('digest') or item.get('remote_model') or item.get('remote_host'):
                raise ValueError('The exact installed local model could not be verified: '+name)
            self.models[role]=dict(name=name,digest=item['digest'],provider='Ollama loopback',provider_version=version.json().get('version'))
        journal.record('model-identities',self.models)

    def invoke(self,name,c,journal):
        from hinglish_niche.profiles import use
        with use(c['creator_context']): return getattr(self,'_'+name)(c)

    def _prepare(self,c):
        from hinglish_cut.media import probe
        from hinglish_cut.model import Cut
        from hinglish_cut.xml_export import export_xml
        from hinglish_broll.timeline import parse_xmeml
        from hinglish_zoom.xml_apply import Sequence
        path=Path(c['input_path'])
        if path.suffix.lower()=='.xml': xml=path
        else:
            media=probe(path)  # Strict metadata/packet check; never hidden conform/render.
            xml=self.folder/'source-timeline.xml'
            export_xml(xml,[Cut(media.id,0,math.floor(media.duration*float(media.rate)+1e-6),0)],{media.id:media})
        self.timeline=parse_xmeml(xml); self.seq=Sequence(xml)
        seconds=self.seq.frames/float(self.seq.fps)
        identity=[dict(path=p,size=Path(p).stat().st_size,modified_ns=Path(p).stat().st_mtime_ns) for p in self.timeline.sources()]
        return dict(id=_hash([xml.read_text(encoding='utf-8-sig'),identity]),duration=seconds,fps=str(self.seq.fps))

    def _transcribe(self,c):
        from hinglish_broll.pipeline import transcripts_for
        from hinglish_broll.timeline import timeline_words
        from hinglish_broll.phrases import build_phrases
        from hinglish_visuals.script import apply_script
        config=json.loads((self.root/'config.phase2.json').read_text(encoding='utf-8-sig'))
        if config.get('offline') is not True: raise ValueError('Preinstall the speech models and enable offline analysis first.')
        mapping,notes=transcripts_for(self.root,self.timeline.sources(),self.config.get('device','cpu'),self.progress)
        raw=timeline_words(self.timeline,mapping); self.words=raw; corrections=[]
        if c['script_role']=='spoken_reference' and c['script'].strip(): self.words,corrections=apply_script(raw,c['script'])
        self.lines=build_phrases(self.words)
        return dict(raw_words=_plain(raw),words=_plain(self.words),lines=_plain(self.lines),corrections=corrections,notes=notes,
                    cache='managed by existing ASR; per-source lineage unobserved here')

    def _observe(self,c):
        from .events import collect
        from .scenes import inspect
        from hinglish_aigen.judge import Judge
        self.raw_events=collect(self.seq,c['input_path'])
        model=self.models['vision']
        def factory(root):
            judge=Judge(root,model=model['name']); _transport(judge,self.journal,model['name'],self.folder); return judge
        self.observations=inspect(self.root,self.seq,self.folder,self.raw_events,self.progress,temporal=True,
                                  judge_factory=factory,cache_namespace=_hash(model),creator_context=c['creator_context'])
        if not self.lines and c['script_role']=='context_only':
            from hinglish_broll.phrases import Phrase
            self.lines=[Phrase(i,o['time'],o['end'],'Visible scene (not speech): '+o['setting']+'. '+o['action']) for i,o in enumerate(self.observations)]
        return self.observations

    def _prosody(self,c):
        if not self.words: return []
        from hinglish_zoom.preview import _audio_track
        from .prosody import describe_lines
        from scipy.signal import resample_poly
        voice=_audio_track(self.seq.path,c['prepare']['duration'])
        return describe_lines(resample_poly(voice,1,3),self.lines)

    def _inventory(self,c):
        from .settings import load_settings, OLD_SCAN_CACHE, SFX_BEHAVIOUR
        from .library import scan
        from .brain import Brain
        from .listen import Listener
        from .vectors import SoundIndex
        from hinglish_broll.vision import model_folder
        self.settings=load_settings(self.root)
        device=self.config.get('device','cpu')
        folder=model_folder(self.settings.listen_model,self.root,offline=True)
        if folder is None: raise ValueError('The local audio matching model is not installed.')
        if self.config.get('require_cuda_inference'):
            import torch
            if device!='cuda' or not torch.cuda.is_available(): raise ValueError('The configured GPU is unavailable; no CPU/model substitution was made.')
        self.brain=Brain(self.root,self.models['planning']['name'],self.models['embedding']['name'],progress=self.progress)
        self.brain.cache=self.root/'cache/sound/recommendation-brain'/_hash(self.models)
        self.brain.cache.mkdir(parents=True,exist_ok=True)
        _transport(self.brain,self.journal,self.models['planning']['name'],self.folder,embedding_model=self.models['embedding']['name'])
        self.proxy=_BrainReceipt(self.brain,self.journal,c['creator_context'])
        self.listener=Listener(self.root,self.settings.listen_model,device,self.settings.cpu_threads,local_folder=folder)
        self.roots={'music':[Path(self.settings.music_folder),self.root/'library/owner-sound-packs/music',self.root/'library/music-online'],
                    'sfx':[Path(self.settings.sfx_folder),Path(self.settings.pro_folder) if self.settings.pro_folder else self.root/'library/sfx-pro',self.root/'library/sound-online',self.root/'library/owner-sound-packs/sfx']}
        self.indexes={}; inventory=[]
        for kind,roots in self.roots.items():
            assets=[]
            for path in roots: assets+=scan(path,kind,self.root/'cache/sound',OLD_SCAN_CACHE,self.progress)
            assets=list({str(Path(a.path).resolve()):a for a in assets}.values())
            self.indexes[kind]=SoundIndex(assets,self.proxy,self.listener,self.progress)
            inventory.extend([dict(asdict(a),bytes=Path(a.path).stat().st_size,
                                   modified_ns=Path(a.path).stat().st_mtime_ns) for a in assets])
        write_json_atomic(self.folder/'library-inventory.json',inventory)
        return dict(revision=_hash([inventory,self.models['embedding']]),
                    moods=sorted({a.category for a in self.indexes['music'].assets}),
                    families=sorted(set(SFX_BEHAVIOUR)) if self.indexes['sfx'].assets else [])

    def _plan(self,c):
        from .director import analyse
        from .composition import policy,rhetorical_palette,speech_events,ambience_events
        from .layers import augment_moments
        from .events import normalize
        from .spotting import resolve_sections
        from .learning import load,taste
        seconds=c['prepare']['duration']; inv=c['inventory']; composition=policy(self.root,seconds,c['density'])
        raw=list(self.raw_events)
        for o in self.observations:
            for event in ambience_events([o],seconds): raw.append(dict(event,confidence=o['confidence']))
            raw.extend(o.get('action_events',[]))
        measured=normalize(raw,seconds)
        # normalize keeps timing identity; retain the original confidence/mechanism separately.
        for event in measured:
            matches=[r for r in raw if r.get('kind')==event['kind'] and abs(r.get('time',-1)-event['time'])<.002 and r.get('label')==event['label']]
            if matches:
                for key in ('confidence','sound_evidence'): 
                    if key in matches[0]: event[key]=matches[0][key]
        budget=max(2,math.ceil(seconds/{'low':6.,'medium':2.,'high':1.}[c['density']]))
        analysis=analyse(self.proxy,'video',self.lines,c['prosody'],measured,inv['moods'],inv['families'],budget,
                         taste(load(self.root)),self.progress,c['script'],self.observations,composition)
        palette=rhetorical_palette(self.proxy,analysis,'auto',composition,self.observations)
        if palette.get('confirmed') is False: raise InsufficientAnalysis('The local model did not confirm a supported emotional palette.')
        anchors=speech_events(self.lines,self.words,[])
        moments=augment_moments(self.proxy,measured,[],analysis.get('story',''),palette['palette'],budget,inv['families'],
                                speech_events=anchors,composition=composition)
        sections=resolve_sections(analysis.get('music'),self.lines,seconds,inv['moods'])
        write_json_atomic(self.folder/'local-analysis.json',dict(analysis=analysis,palette=palette,moments=moments,measured_events=measured,sections=sections))
        evidence_by_id={e['id']:e for e in measured+anchors}
        music=[]; effects=[]
        for i,s in enumerate(sections):
            if s['mode']!='music': continue
            intent=s.get('query') or s.get('intent') or s.get('why')
            music.append(dict(id=f'music-{s["from_id"]}-{s["to_id"]}',start=s['start'],end=s['end'],mood=s['mood'],intent=intent,
                              role='bed',level_db=-16.,reason=s['why'],evidence=dict(kind='script' if self.words else 'vision',
                              precision='phrase' if self.words else 'sampled',confidence=1.,description=s['why'])))
        for m in moments:
            anchor=evidence_by_id.get(m.get('event_id'))
            if anchor is None: raise InsufficientAnalysis('The local model returned a sound without a measured anchor.')
            a=m.get('target'); length=m.get('duration',m.get('length'))
            if not all(type(v) in (int,float) and math.isfinite(v) for v in (a,length)) or not 0<=a<a+length<=seconds+1e-6:
                raise InsufficientAnalysis('A local sound duration falls outside the measured timeline.')
            span=next((s for s in sections if s['start']<=a<s['end']),None)
            if span is None or span['mode']=='voice_only': continue
            end=min(a+length,span['end'])
            physical=m['type'] in ('foley','ambience'); precision=anchor.get('precision','editor')
            confidence=anchor.get('confidence')
            if physical and (type(confidence) not in (int,float) or confidence<(.8 if m['type']=='foley' else .7)): continue
            if not physical: confidence=1.  # Confidence in the measured anchor, not sound relevance.
            effects.append(dict(id=_hash([anchor['id'],m['role'],m['type'],m['intent']])[:32],start=a,end=end,
                sound_type=m['type'],role=m['role'],intent=m['intent'],level_db=m.get('level_db',-12.),
                reason=m.get('why',''),processing=m.get('processing',{}),evidence=dict(kind='vision' if physical else 'script' if precision=='speech' else 'editor',
                precision=precision,confidence=confidence,description=anchor.get('sound_evidence') or anchor.get('label') or anchor.get('line_text'),
                uncertainty=anchor.get('uncertainty',0))))
        return dict(music_sections=music,sfx_events=effects)

    def rankings(self,request,journal,token,limit):
        from .retrieval import effect_candidates
        from .learning import load,banned
        from .online_sources import Fallback
        online=Fallback(self.root,enabled=self.settings.online_sounds)
        bans=banned(load(self.root)); snapshots={}
        for kind,key in [('music','music_sections'),('sfx','sfx_events')]:
            index=self.indexes[kind]; queries={}
            for slot in request[key]:
                token.check(); query=slot['intent']
                if kind=='music': hits=index.search(query,top=limit*4,categories=[slot['mood']],instrumental_only=True,banned=bans)
                else:
                    hits,rejected=effect_candidates(index,query,dict(type=slot['sound_type'],intent=query,duration=slot['end']-slot['start']),banned=bans)
                    journal.record('retrieval-rejections',rejected)
                if not hits:
                    category=slot['mood'] if kind=='music' else slot['sound_type']
                    index=online.extend(index,query,category,kind,self.proxy,self.listener,self.progress,slot['end']-slot['start'])
                    self.indexes[kind]=index
                    token.check()
                    if kind=='music':hits=index.search(query,top=limit*4,categories=[category],instrumental_only=True,banned=bans)
                    else:
                        hits,rejected=effect_candidates(index,query,dict(type=category,intent=query,duration=slot['end']-slot['start']),banned=bans)
                        journal.record('online-retrieval-rejections',rejected)
                queries.setdefault(query,[])
                seen={p for p,_ in queries[query]}
                queries[query]+=[(a.path,float(score)) for a,score,*_ in hits if a.path not in seen]
            facts={a.path:index.facts_for(a) for a in index.assets}
            snapshots[kind]=CachedRankingIndex(index.assets,queries,facts=facts)
            write_json_atomic(self.folder/(kind+'-ranking-snapshot.json'),dict(queries=queries,facts=facts))
        journal.record('online-audio-search',dict(notices=online.notes,queries_used=3-online.remaining))
        return snapshots['music'],snapshots['sfx'],list({str(p.resolve()) for roots in self.roots.values() for p in roots})

    def passage(self,asset,slot):
        from .music import passage
        from .library import exact_peak_time
        desired=slot['end']-slot['start']
        if asset.kind=='music':
            selected=passage(asset.path,desired); offset=selected['source_offset']
            basis='measured energy passage; semantic suitability requires review'
        else:
            peak=exact_peak_time(asset.path,limit=min(asset.duration,60.))
            if peak is None: raise ValueError('The sound excerpt could not be measured.')
            offset=max(0.,min(asset.duration-desired,peak-desired/3))
            basis='measured energy peak window; exact semantic contact unverified'
        result=dict(source_in=offset,basis=basis)
        self.journal.record('measured-passage',dict(path=asset.path,slot_id=slot['id'],desired_duration=desired,**result))
        return result

    def close(self):
        if self.brain is not None: self.brain.session.close()
        self.listener=None


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True); p.add_argument('--input',required=True)
    p.add_argument('--script-file',required=True); p.add_argument('--creator-context',required=True)
    p.add_argument('--execute-local',action='store_true'); p.add_argument('--resource-lease',required=True)
    p.add_argument('--script-role',choices=['spoken_reference','context_only'],default='spoken_reference')
    a=p.parse_args()
    result=run(a.root,a.input,Path(a.script_file).read_text(encoding='utf-8-sig'),
               json.loads(Path(a.creator_context).read_text(encoding='utf-8-sig')),execute_local=a.execute_local,
               resource_lease=a.resource_lease,script_role=a.script_role)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'] in ('ready','no_match') else 1


if __name__=='__main__': raise SystemExit(main())
