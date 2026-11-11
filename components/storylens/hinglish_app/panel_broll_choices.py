"""Explicit verified B-roll choices, preserved trims and separate native timelines.

This is a deterministic transport/controller. It never invents a semantic choice,
checks pixels with a substitute model or resumes an old collection job.
"""
from fractions import Fraction
from pathlib import Path
import hashlib
import json


def video_codec(path):
    """Inspect local stream metadata without transcoding or changing a source."""
    import av
    try:
        with av.open(str(path)) as container:
            stream=next(iter(container.streams.video),None)
            return stream.codec_context.name if stream is not None else 'unknown'
    except (OSError,ValueError):return 'unknown'


def project_path(root, folder, value):
    base=(Path(root)/'output/broll').resolve();folder=Path(folder).resolve()
    path=Path(value)
    path=(folder/path).resolve() if not path.is_absolute() else path.resolve()
    if (not folder.is_relative_to(base) or not folder.is_dir()
            or not path.is_relative_to(folder) or not path.is_file()
            or path.name!='broll-project.json'):
        raise ValueError('Choose a saved B-roll result from this collection.')
    return path


def saved_results(root):
    base=(Path(root)/'output/broll').resolve();rows=[]
    if not base.is_dir():return rows
    for project in sorted(base.rglob('broll-project.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        if not project.resolve().is_relative_to(base):continue
        try:data=json.loads(project.read_text('utf-8'))
        except (OSError,ValueError):continue
        rows.append({'folder':str(project.parent.resolve()),
                     'name':str(data.get('timeline',{}).get('name') or project.parent.name)[:120],
                     'collecting':bool(data.get('collecting'))})
        if len(rows)>=40:break
    return rows


def load_bank(root, folder, value, content_format, *, media_reader=None):
    from hinglish_broll.candidate_manifest import build_manifest
    from hinglish_broll.candidate_selection import load_selections
    project=project_path(root,folder,value)
    sidecar=project.with_name('BROLL_OWNER_SELECTIONS.v1.json')
    previous=load_selections(sidecar) if sidecar.is_file() else None
    return build_manifest(project,content_format=content_format,
                          previous=previous,media_reader=media_reader)


def cards(root, folder, content_format):
    folder=Path(folder).resolve();rows=[]
    if not folder.is_relative_to((Path(root)/'output/broll').resolve()) or not folder.is_dir():
        raise ValueError('Choose a saved B-roll collection.')
    for project in sorted(folder.rglob('broll-project.json')):
        bank=load_bank(root,folder,project,content_format)
        for slot in bank['slots']:
            shared={'project':str(project.relative_to(folder)),'slot_id':slot['id'],
                    'keyword':slot['keyword'],'start':slot['anchor']['sequence_seconds']['start'],
                    'end':slot['anchor']['sequence_seconds']['end'],'kind':'video',
                    'choice':slot['choice'],'collection_state':slot['collection_state']}
            for candidate in slot['candidates']:
                rows.append({**shared,'id':candidate['id'],'candidate_id':candidate['id'],
                             'path':candidate['prepared']['path'],
                             'selectable':candidate['selectable'],
                             'source_credit':candidate['source'],
                             'issue':next(iter(candidate.get('issues',[])),None)})
            if not slot['candidates']:
                rejected=slot.get('rejected_candidates',[])
                issue=rejected[0].get('issue') if rejected else None
                rows.append({**shared,'id':slot['id'],'path':None,'selectable':False,
                             'issue':issue or {'message':'No checked video is available for this keyword yet.'}})
    return rows


def handoff(root, manifest, host, expected):
    from hinglish_broll.candidate_selection import selected_candidates
    from hinglish_broll.timeline import parse_xmeml
    from hinglish_broll.xml_export import build_track,export_tracks_xml
    from hinglish_broll.candidate_manifest import digest
    selected=selected_candidates(manifest)
    if not selected:raise ValueError('Choose a checked B-roll video first, or keep No B-roll for that keyword.')
    if host=='capcut':return capcut_handoff(root,manifest)
    project=Path(manifest['project_path'])
    saved=json.loads(project.read_text('utf-8'));source=Path(saved['timeline']['xml_path']).resolve()
    if not source.is_relative_to(Path(root).resolve()) or not source.is_file() or source.stat().st_size>20*1024**2:
        raise ValueError('The saved source timeline is unavailable. Your B-roll choices are kept.')
    timeline=parse_xmeml(source);target=manifest['timeline']
    if (Fraction(str(target['fps']))!=timeline.fps or target['width']!=timeline.width
            or target['height']!=timeline.height
            or abs(float(target['duration'])-timeline.duration)>.5/float(timeline.fps)+1e-7):
        raise ValueError('The source timeline changed. Review the keyword timing again before importing.')
    tracks=[]
    for index,candidate in enumerate(selected):
        prepared=candidate['prepared'];anchor=candidate['anchor'];mapping=candidate['mapping']
        if (Fraction(prepared['fps'])!=timeline.fps
                or (prepared['width'],prepared['height'])!=(timeline.width,timeline.height)):
            raise ValueError('This checked preview needs matching canvas and frame rate before native insertion. Your choice is kept.')
        start=anchor['frames']['start']/float(timeline.fps)
        end=anchor['frames']['end']/float(timeline.fps)
        placement={'path':prepared['path'],'start':start,'end':end,
                   'source_in':mapping['prepared_active']['start'],
                   'source_duration':prepared['duration'],'name':candidate['keyword']}
        # One lane per selected interval prevents the generic track builder from
        # silently moving/truncating an overlapping keyword to fit another one.
        tracks.append(build_track([placement],timeline.fps,timeline.width,timeline.height,
                                  'owner-broll-'+str(index)))
    native_originals=[];external=[]
    if host=='premiere':
        for candidate in selected:
            codec=video_codec(candidate['original']['path'])
            if codec in ('av1','libdav1d','unknown'):
                if video_codec(candidate['prepared']['path'])!='h264':
                    raise ValueError('This original cannot be imported automatically and its prepared clip is not a verified H264 handoff. Your sources and choices are kept.')
                external.append({'original':candidate['original'],'source_credit':candidate['source'],
                    'codec':codec,'reason':'Original codec is unsupported or unverified by this native importer; retained as external provenance.'})
            else:native_originals.append(candidate['original']['path'])
    identity={'bank':manifest['bank_id'],'selected':selected,
              'source_xml_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    # New policy identity avoids mistaking an earlier partial import for proof
    # that the repaired handoff works. The failed XML/receipt remain untouched.
    if external:identity['native_media_policy']={'version':2,'external_references':external}
    signature=digest(identity)[:24]
    destination=Path(root)/'output/editor-handoffs/broll-selected';destination.mkdir(parents=True,exist_ok=True)
    xml=destination/(signature+'.xml')
    export_tracks_xml(timeline,tracks,xml,' - Storylens B-roll '+signature)
    notice=('Prepared clips are editable in this timeline. '+str(len(external))+
        ' original source(s) remain external references because their codec is unsupported or unverified; '
        'full-original trimming is unavailable in this handoff. Unchanged sources and credits are kept with the review.') if external else ''
    receipt={'schema':'storylens.panel.broll-selection','version':2 if external else 1,'bank_id':manifest['bank_id'],
             'selection_id':signature,'source_timeline':str(source),'candidates':selected,
             'notice':'Explicit manual choices only; prepared pixels retain checked crop and handles. Original sources and credits remain available.'}
    if external:receipt.update(external_references=external,native_media_notice=notice)
    xml.with_suffix('.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    if host=='aftereffects':
        from .editor_panel import layer_manifest
        result=layer_manifest(xml);result['expected']=expected;result['selection_id']=signature
        return result
    if host!='premiere':raise ValueError('This timed handoff currently supports Premiere Pro and After Effects.')
    return {'type':'files','paths':[str(xml.resolve()),*dict.fromkeys(native_originals)],
            'expected':expected,'activate':True,'name':'Storylens B-roll choices',
            'selection_id':signature,'sequence_name':timeline.name+' - Storylens B-roll '+signature,
            'external_references':external,'notice':notice}


def report_request(root,value,content_format):
    """Map a visible report option to the verified bank, never caller media paths."""
    if type(value.get('slot_index')) is not int:raise ValueError('Choose an offered keyword moment.')
    bank=load_bank(root,value.get('folder',''),value.get('project',''),content_format)
    slot=next((s for s in bank['slots'] if s['slot_index']==value['slot_index']),None)
    if not slot:raise ValueError('Reopen this keyword moment before importing.')
    if value.get('state')=='no_broll':
        return {'folder':value['folder'],'project':bank['project_path'],'slot_id':slot['id'],
                'candidate_id':None,'state':'no_broll'}
    candidate=next((c for c in slot['candidates'] if c['candidate_id']==value.get('source_id')),None)
    if not candidate:raise ValueError('Choose an offered checked video for this keyword.')
    return {'folder':value['folder'],'project':bank['project_path'],'slot_id':slot['id'],
            'candidate_id':candidate['id'],'state':'selected'}


def select(root, folder, value, context, host):
    if value.get('delivery')=='receipt':
        from .timed_choice_delivery import TimedChoiceDelivery
        return {'receipt':TimedChoiceDelivery(root).accept(value.get('operation_id'),value.get('receipt'),context=context)}
    if value.get('delivery')=='active_timeline':
        return select_timed(root,folder,value,context)
    from hinglish_broll.candidate_selection import choose,save_selections
    bank=load_bank(root,folder,value.get('project',''),context['content_format'])
    bank=choose(bank,value.get('slot_id'),value.get('state'),value.get('candidate_id'))
    save_selections(Path(bank['project_path']).with_name('BROLL_OWNER_SELECTIONS.v1.json'),bank)
    if value.get('state')!='selected':return {'choice_saved':True,'manifest':None}
    if host=='capcut' and value.get('defer_project') is True:
        return {'choice_saved':True,'manifest':None,'message':'Choice saved for the new CapCut project.'}
    expected={k:context.get(k) for k in ('project_id','sequence_id')}
    return {'choice_saved':True,'manifest':handoff(root,bank,host,expected)}


def select_timed(root, folder, value, context):
    """An explicit click delivers only its verified slot, never every saved choice."""
    from hinglish_broll.candidate_selection import choose,save_selections,selected_candidates
    from .timed_choice_delivery import TimedChoiceDelivery
    if context.get('host') not in ('premiere','aftereffects'):
        raise ValueError('Use CapCut’s separate editable project handoff. Active-timeline replacement is not connected there.')
    bank=load_bank(root,folder,value.get('project',''),context.get('content_format','short'))
    bank=choose(bank,value.get('slot_id'),value.get('state'),value.get('candidate_id'))
    if value.get('state')!='selected':
        save_selections(Path(bank['project_path']).with_name('BROLL_OWNER_SELECTIONS.v1.json'),bank)
        return {'choice_saved':True,'manifest':None,
                'message':'Choice saved. Existing editor clips are kept; remove them in the editor if needed.'}
    # Validate only the clicked slot; an unrelated old choice cannot turn this
    # into a batch import or silently change its selected video.
    clicked=next(row for row in bank['slots'] if row['id']==value['slot_id'])
    one={**bank,'slots':[clicked],'orphaned_choices':{}}
    selected=selected_candidates(one)
    if len(selected)!=1:raise ValueError('Choose one checked video for this spoken keyword.')
    candidate=selected[0];anchor=candidate['anchor'];prepared=candidate['prepared']
    manifest=TimedChoiceDelivery(root).prepare({
        'feature':'broll','bank_id':bank['bank_id'],'slot_id':clicked['id'],
        'slot_fingerprint':clicked['fingerprint'],'asset_id':candidate['id'],
        'asset_path':prepared['path'],'asset_sha256':prepared['sha256'],
        'source_in':candidate['mapping']['prepared_active']['start'],
        'source_duration':prepared['duration'],'start_frame':anchor['frames']['start'],
        'end_frame':anchor['frames']['end'],'fps':anchor['fps'],
        'width':bank['timeline']['width'],'height':bank['timeline']['height']},context)
    save_selections(Path(bank['project_path']).with_name('BROLL_OWNER_SELECTIONS.v1.json'),bank)
    return {'choice_saved':True,'manifest':manifest}


def capcut_selected_spec(manifest):
    """A NEW editable draft from explicit choices, never a live-draft rewrite."""
    from hinglish_broll.candidate_selection import selected_candidates
    from hinglish_broll.timeline import parse_xmeml
    selected=selected_candidates(manifest)
    if not selected:raise ValueError('Choose a checked video before creating a CapCut project.')
    saved=json.loads(Path(manifest['project_path']).read_text('utf-8'))
    timeline=parse_xmeml(saved['timeline']['xml_path']);target=manifest['timeline']
    if (len(timeline.clips)!=1 or Fraction(str(target['fps']))!=timeline.fps or
        (target['width'],target['height'])!=(timeline.width,timeline.height) or
        abs(target['duration']-timeline.duration)>.5/float(timeline.fps)+1e-7):
        raise ValueError('This CapCut handoff needs the matching single-video source timeline. Your selected B-roll stays saved.')
    micro=lambda value:round(value*1_000_000)
    clips=[{'path':c.path,'start':micro(c.start),'source_in':micro(c.source_in),
            'duration':micro(c.end-c.start)} for c in timeline.clips]
    overlays=[]
    for candidate in selected:
        anchor=candidate['anchor'];prepared=candidate['prepared'];active=candidate['mapping']['prepared_active']
        if (Fraction(prepared['fps'])!=timeline.fps or
                (prepared['width'],prepared['height'])!=(timeline.width,timeline.height)):
            raise ValueError('Check this option against its original timeline canvas and frame rate.')
        overlays.append({'path':prepared['path'],'start':micro(anchor['frames']['start']/timeline.fps),
                         'source_in':micro(active['start']),
                         'duration':micro((anchor['frames']['end']-anchor['frames']['start'])/timeline.fps)})
    return {'fps':float(timeline.fps),'width':timeline.width,'height':timeline.height,
            'duration':micro(timeline.duration),'clips':clips,'overlays':overlays,'options':[],
            'broll':True,'selected_only':True}


def capcut_handoff(root,manifest):
    from .capcut_adapter import create_project
    from . import editor_handoff
    from hinglish_broll.candidate_manifest import digest
    import uuid
    spec=capcut_selected_spec(manifest)
    key=digest({'bank_id':manifest['bank_id'],'spec':spec,
                'choices':[{k:r.get(k) for k in ('id','fingerprint','choice')} for r in manifest['slots']]})[:24]
    project=create_project(root,spec['clips'][0]['path'],'Storylens B-roll choices',key,timeline=spec)
    task_id=uuid.uuid4().hex
    notice='New editable CapCut project prepared from your saved choices at their speech timestamps. Open the named project from CapCut Home. Existing open timeline items are not replaced.'
    with editor_handoff._LOCK:
        editor_handoff._TASKS[task_id]={'id':task_id,'editor':'capcut','status':'complete',
            'stage':'Ready for CapCut','projects':[project],'files':[],'notice':notice}
    return {'type':'capcut','task_id':task_id,'projects':[project],'notice':notice}
