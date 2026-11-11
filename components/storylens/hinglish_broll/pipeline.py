"""One-click B-roll: timeline -> speech -> local AI plan -> footage -> conformed clips -> new XML."""
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import json
import math
import re
import shutil
import uuid
from dataclasses import asdict

from hinglish_cut.media import prepare_media
from hinglish_cut.model import Cut
from hinglish_cut.xml_export import export_xml
from hinglish_eval import guard

from .conform import make_clip
from .library import Library, VIDEO_EXTENSIONS, read_frames
from .phrases import build_phrases
from .placement import Moment, Slot, place
from .places import conflicts, is_template, video_country, with_country
from .planner import plan_moments, summarize
from .ranker import GENERIC_SCENES, add_specificity, choose, fetch_thumbs, moment_embedding, score_stock
from .report import write_index, write_report
from .settings import load_settings, profile_for
from .stock import Candidate, PexelsClient, PixabayClient, cached_name, download
from .timeline import Timeline, parse_xmeml, path_key, timeline_words
from .xml_export import export_broll_xml
from .recovery import RunStore, request_key, read_json, restore_choices, retry, transient, valid_clip, write_json
from .producer_contract import (snapshot_file, assert_snapshot, record_check, require_review_check,
                               bind_window, review_option_data as _review_option_data, finalize_candidate_bank)

STOCK_OFFSET = 1.0     # skip the first second of stock clips (often fades / camera settling)


def _videos(path):
    path = Path(path)
    if path.is_file(): return [path]
    return sorted((p for p in path.rglob('*') if p.suffix.lower() in VIDEO_EXTENSIONS),
                  key=lambda p: str(p).casefold())


def timelines_for(root, input_path, output, output_format, progress):
    """An XML sequence is used as-is; each video file becomes a one-clip sequence."""
    input_path = Path(input_path)
    if input_path.suffix.lower() == '.xml':
        folder = output / f'001-{re.sub(r"[^A-Za-z0-9_-]+", "-", input_path.stem)[:40]}'
        folder.mkdir(parents=True, exist_ok=True)
        return [(parse_xmeml(input_path), folder)]
    found = []
    for n, video in enumerate(_videos(input_path), 1):
        media, _ = prepare_media(video, Path(root) / 'cache' / 'conformed', progress)
        folder = output / f'{n:03d}-{re.sub(r"[^A-Za-z0-9_-]+", "-", video.stem)[:40]}'
        folder.mkdir(parents=True, exist_ok=True)
        base = folder / 'source-timeline.xml'
        export_xml(base, [Cut(media.id, 0, math.floor(media.duration * float(media.rate) + 1e-6), 0)],
                   {media.id: media}, output_format)
        timeline = parse_xmeml(base)
        timeline.name = video.stem
        found.append((timeline, folder))
    if not found:
        raise ValueError('No supported videos or XML timeline were found')
    return found


def transcripts_for(root, sources, device, progress):
    from hinglish_semantic.analysis import analyze_sources
    from hinglish_semantic.core import SemanticSettings
    data = json.loads((Path(root) / 'config.phase2.json').read_text(encoding='utf-8-sig'))
    data.update(device=device, speech_backend='swift', matching_backend='word_coverage')
    paths = [Path(p) for p in sources if Path(p).is_file()]
    missing = [str(p) for p in sources if not Path(p).is_file()]
    transcripts, _, errors = analyze_sources(paths, root, SemanticSettings(**data), progress)
    failed = {e['source'] for e in errors}
    mapping = {}
    for path, transcript in zip([p for p in paths if str(p) not in failed], transcripts):
        mapping[path_key(path)] = transcript.words
        mapping[path_key(transcript.media.path)] = transcript.words
    for e in errors:   # duplicate copies share the original's words
        same = re.search(r'same video as (.+)$', e['error'])
        if same and path_key(same.group(1)) in mapping:
            mapping[path_key(e['source'])] = mapping[path_key(same.group(1))]
    notes = [f'Media offline: {m}' for m in missing] + [f"{Path(e['source']).name}: {e['error']}" for e in errors
                                                         if 'same video as' not in e['error']]
    return mapping, notes


def gather_candidates(slot, embedding, library, clients, orientation, timeline, per_query, thumbs, progress,
                      country='',cached_sources=()):
    need = slot.duration
    found = list(library.search(embedding, need)) if library else []
    # Reconsider previously pixel-verified INTERNET sources as retrieval leads.
    # These are not the source video's original edit or creator library. Every
    # new use is ranked again and checked against its new timed clause.
    import copy
    from .subjects import cached_scene_matches
    found += [copy.copy(c) for c in cached_sources if cached_scene_matches(c.verified_description,slot.moment.visual) and
              c.duration>=need+STOCK_OFFSET*.5 and
              not conflicts(c.title+' '+c.page_url,country)]
    for client in list(clients):
        # Web clients are shared across the video, but their limits belong to
        # ONE keyword. Without this reset the first keyword spends the entire
        # video's eight-call allowance and later subjects never search.
        web=getattr(client,'web',None)
        if web is not None and callable(getattr(web,'begin_subject',None)):
            web.begin_subject(seconds=45)
        # A refrigerator or a generic room need not prove its country. Avoid
        # narrowing object searches to country-tagged clips unnecessarily.
        geographic=bool(slot.moment.subject or re.search(r'\b(?:street|city|road|highway|landmark|skyline)\b',slot.moment.visual,re.I))
        queries = with_country(slot.moment.queries, country if geographic else '')
        # A site's first page is not evidence of relevance. Search the planner's
        # narrower alternatives as well before the pixel checker chooses a clip.
        for n, query in enumerate(queries[:2] if client.name in ('web','commons') else queries[:4]):
            if slot.moment.subject and client.name in ('web','commons'):
                # Keep the model's event/action context. Replacing a query like
                # "2009 IPL season" with a bare identity/year loses the subject.
                if slot.moment.subject.casefold() not in query.casefold():
                    query = slot.moment.subject + ' ' + query
            try:
                search=lambda: client.search(query, orientation, timeline.width, timeline.height,
                                        min(per_query,12 if client.name=='pixabay' else 6))
                results = search() if client.name in ('pexels','pixabay') else retry(search, progress, client.name.title()+' search')
            except PermissionError as error:
                # A wrong key must not stop the run: drop that site, keep the other sources.
                progress(f'  {error} Skipping {client.name.title()} for this run.')
                clients.remove(client)
                break
            except Exception as error:
                progress(f'  {client.name.title()} search skipped: {error}')
                results = []
            # Wrong country (Seoul traffic for a Delhi story) is worse than no B-roll.
            found += [c for c in results if c.kind=='video' and (c.duration >= need + STOCK_OFFSET * 0.5 or
                      c.duration<=0 and (c.extraction or c.source=='website'))
                      and not conflicts(f'{c.title} {c.page_url}', country if geographic else '')
                      and not is_template(f'{c.title} {c.page_url}')]
    unique = {}
    for c in found:
        unique.setdefault(c.id, c)
    return [c for c in unique.values() if c.kind=='video']


def verified_internet_sources(root,limit=40):
    """A reusable search bank, never acceptance of a new edit or a manual pick."""
    folders=sorted((Path(root)/'output/broll').glob('*'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]
    found={}
    for folder in folders:
        for file in folder.glob('*/broll-project.json'):
            try:project=json.loads(file.read_text(encoding='utf-8'))
            except (OSError,ValueError):continue
            for slot in project.get('slots',[]):
                data=slot.get('chosen') or {}
                if not data or data.get('source')=='library' or data.get('kind','video')!='video':continue
                if not any(c.get('id')==data.get('id') and c.get('passed') is True for c in slot.get('checks',[])):continue
                if not data.get('path') or not Path(data['path']).is_file():continue
                candidate=Candidate(**{k:v for k,v in data.items() if k in Candidate.__dataclass_fields__})
                passed=[c for c in slot.get('checks',[]) if c.get('id')==data.get('id') and c.get('passed') is True]
                candidate.verified_description=passed[-1].get('seen','') if passed else ''
                found.setdefault(candidate.id,candidate)
                if len(found)>=limit:return list(found.values())
    return list(found.values())


def render_choice(root, folder, timeline, slot_index, slot, candidate, device, handles=3.0, vision=None, embedding=None, checker=None):
    """Download (stock) and conform one chosen candidate; returns the new clip path."""
    if candidate.kind != 'video':
        raise ValueError('Add B-roll uses videos only. Choose a video clip instead of an image.')
    from .internet import acquire
    fps = float(timeline.fps)
    needed_frames=round(slot['end']*fps)-round(slot['start']*fps)
    need = needed_frames/fps
    fresh_review=slot.get('review_options') is True
    if fresh_review:
        slot.pop('checked_window',None)
        if checker is None:raise ValueError('Start the local video checker before preparing review options.')
    source, available, offset = acquire(root, candidate, need)
    available_frames=math.floor(available*fps+1e-7)
    if needed_frames<=0 or available_frames<needed_frames:
        raise ValueError('Choose a video long enough for this B-roll interval.')
    def quantized(value):return max(0,min(round(value*fps),available_frames-needed_frames))/fps
    source_snapshot=None;original_verdict=None;source_crop=None
    if candidate.kind == 'video' and vision is not None and embedding is not None:
        # Search thumbnails can be unrelated to the actual downloaded section.
        # Pick the best of a few decoded shot windows, using the local model.
        times = sorted({min(available-need/2, max(need/2, t))
                        for t in (offset+need/2, available/2, available-need/2)})
        frames = read_frames(source, times)
        if not frames:
            raise ValueError('This B-roll could not be read. Choose another suggested clip.')
        scores = vision.images([im for _, im in frames]) @ embedding
        best = int(scores.argmax())
        if float(scores[best]) < .22:
            raise ValueError('The actual downloaded footage does not match this spoken line. Choose another clip.')
        offset = max(0., min(available-need, frames[best][0]-need/2))
        candidate.offset = offset
    if checker is not None:
        from .verify import readable_window
        slot['canvas_width'],slot['canvas_height']=timeline.width,timeline.height
        if candidate.extraction or candidate.source=='website':
            offset=checker.find_window(source,available,need,slot)
        offset=readable_window(source,available,need,offset,timeline.width,timeline.height)
        offset=quantized(offset);candidate.offset=offset
        if fresh_review:
            from .candidate_manifest import local_video_metadata
            from .conform import crop_box
            source_snapshot=snapshot_file(source);metadata=local_video_metadata(Path(source))
            x,y,w,h=crop_box(metadata['width'],metadata['height'],timeline.width,timeline.height)
            source_crop={'space':'upright_source_pixels','x':x,'y':y,'width':w,'height':h}
            assert_snapshot(source_snapshot)
        verdict=checker.check(source,offset,need,slot,candidate.kind)
        original_verdict=(record_check(verdict,candidate.id,'original',source_snapshot,offset,need,source_crop)
                          if fresh_review else {'id':candidate.id,**verdict})
        slot.setdefault('checks',[]).append(original_verdict)
        if (not verdict['passed'] and not candidate.extraction and candidate.source!='website' and
            verdict.get('real_clear_footage') is False and
            re.search(r'blur|focus|too dark|unreadable',str(verdict.get('reason','')),re.I)):
            # A stock video can rack focus after its blurred opening. Let the
            # local model find a readable shot; verify that exact interval again.
            alternate=checker.find_window(source,available,need,slot)
            if abs(alternate-offset)>.1:
                offset=readable_window(source,available,need,alternate,timeline.width,timeline.height)
                offset=quantized(offset);candidate.offset=offset
                if fresh_review:assert_snapshot(source_snapshot)
                verdict=checker.check(source,offset,need,slot,candidate.kind)
                original_verdict=(record_check(verdict,candidate.id,'original',source_snapshot,offset,need,source_crop)
                                  if fresh_review else {'id':candidate.id,**verdict})
                slot.setdefault('checks',[]).append(original_verdict)
        if not verdict['passed']:
            raise ValueError('B-roll rejected: '+str(verdict.get('reason') or verdict.get('seen') or 'The visible scene does not match the speech.'))
        if fresh_review:
            require_review_check(original_verdict);assert_snapshot(source_snapshot)
    # Quantize both to the target frame rate so handles match the XML exactly.
    offset_frames=max(0,min(round(offset*fps),available_frames-needed_frames))
    first=max(0,offset_frames-round(handles*fps))/fps
    last=min(available_frames,offset_frames+needed_frames+round(handles*fps))/fps
    length = last-first
    safe = re.sub(r'[^A-Za-z0-9]+', '-', candidate.id)[-40:]
    import hashlib
    key=f'{first:.6f}|{length:.6f}|{timeline.width}|{timeline.height}|{timeline.fps}'
    if fresh_review:key+='|checked-v1|'+source_snapshot['sha256']
    signature = hashlib.sha1(key.encode()).hexdigest()[:8]
    clip = Path(folder) / 'media' / f'broll-{slot_index + 1:02d}-{safe}-{signature}.mp4'
    if not valid_clip(folder, clip.relative_to(folder)):
        # The local vision judge occupies most of this laptop's VRAM. NVENC
        # bitstream allocation here caused a real out-of-memory native crash.
        # Review encoding is bounded CPU work; AI inference stays on CUDA.
        encode_device='cpu' if fresh_review else device
        make_clip(source, first, length, timeline.width, timeline.height, timeline.fps, clip, encode_device)
    slot.update(source_in=offset_frames/fps-first, source_duration=length,
                source_path=str(Path(source).resolve()), original_offset=first, scale=slot.get('scale',100))
    if fresh_review:
        assert_snapshot(source_snapshot)
        prepared_snapshot=snapshot_file(clip);prepared_metadata=local_video_metadata(clip)
        if (prepared_metadata['width']!=timeline.width or prepared_metadata['height']!=timeline.height
                or Fraction(str(prepared_metadata['fps']))!=timeline.fps):
            raise ValueError('Check the prepared B-roll canvas and frame rate before saving this option.')
        assert_snapshot(prepared_snapshot)
        prepared_crop={'space':'upright_source_pixels','x':0,'y':0,'width':timeline.width,'height':timeline.height}
        prepared_verdict=record_check(checker.check(clip,slot['source_in'],need,slot,candidate.kind),
            candidate.id,'prepared',prepared_snapshot,slot['source_in'],need,prepared_crop)
        slot['checks'].append(prepared_verdict)
        slot['checked_window']=bind_window(source,clip,first,slot['source_in'],need,source_crop,
            original_verdict,prepared_verdict,source_snapshot,prepared_snapshot)
    return clip


def report_thumb(root, folder, candidate, need):
    """Local jpg for the review page (copied so the page works from its own folder)."""
    target = Path(folder) / 'thumbs' / cached_name(candidate, 'thumb')
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if candidate.source == 'library':
            frames = read_frames(candidate.path, [candidate.offset + need / 2], size=480)
            if frames: frames[0][1].convert('RGB').save(target, quality=85)
        elif candidate.thumb and Path(candidate.thumb).is_file():
            shutil.copyfile(candidate.thumb, target)
    except Exception:
        return None
    return target if target.exists() else None


def timeline_fingerprint(vision, timelines, every=1.5, limit=300):
    """CLIP embeddings of frames from the timelines' own footage (to spot raw takes in the library)."""
    clips = [clip for timeline in timelines for clip in timeline.clips]
    total = sum(max(0.0, c.source_out - c.source_in) for c in clips) or 1.0
    step = max(every, total / limit)          # one frame every 1.5 s, at most ~300 frames per run
    images = []
    for clip in clips:
        span = max(0.0, clip.source_out - clip.source_in)
        count = max(1, round(span / step))
        times = [clip.source_in + span * (k + .5) / count for k in range(count)]
        try:
            images += [im for _, im in read_frames(clip.path, times)]
        except Exception:
            continue
    return vision.images(images) if images else None


def timeline_to_dict(t):
    return {'name': t.name, 'fps': f'{t.fps.numerator}/{t.fps.denominator}', 'width': t.width, 'height': t.height,
            'duration': t.duration, 'xml_path': t.xml_path}


def _unselected_review_source(folder,project):
    """Only defer a new bank when its existing audio-over-black is accessible."""
    folder=Path(folder).resolve()
    if (project.get('review_options') is not True or project.get('audio_only_test') is not True
            or project.get('preview_requested') is True
            or (folder/'BROLL_OWNER_SELECTIONS.v1.json').exists()):return None
    source=(folder.parent/'audio-only-source.mp4').resolve()
    if source.parent!=folder.parent or not source.is_file() or source.stat().st_size<=0:return None
    return '../audio-only-source.mp4'


def write_outputs(root, folder, project, *, defer_review_preview=False, progress=None):
    progress=progress or (lambda _:None)
    _apply_edits(project,{})
    if any((s.get('chosen') or {}).get('kind','video')!='video' for s in project['slots']):
        raise ValueError('This saved B-roll draft contains an image. Remove it or choose a video before rebuilding.')
    timeline = parse_xmeml(project['timeline']['xml_path'])
    timeline.name = project['timeline']['name']
    placements = [{'path': str(Path(folder) / s['clip']), 'start': s['start'], 'end': s['end'],
                   'source_in':s.get('source_in',0), 'source_duration':s.get('source_duration',s['end']-s['start']),
                   'scale':s.get('scale',100),
                   'name': s['chosen']['title'][:60] if s.get('chosen') else 'B-roll'}
                  for s in project['slots'] if s.get('chosen') and s.get('clip')]
    xml = export_broll_xml(timeline, placements, Path(folder) / 'BROLL_SEQUENCE.xml')
    if project.get('review_options'):
        from .options import export_xml as export_options
        export_options(project,folder)
    source=_unselected_review_source(folder,project) if defer_review_preview else None
    project.pop('preview_source',None)
    if source:
        # Source and checked option files already exist. Do not label an older
        # aggregate as current, overwrite it, or claim a render was completed.
        project.update(preview_state='deferred',preview_requested=False,preview_source=source,
            preview_notice='Original audio over black. Preview the options below, then use Save & rebuild to create the combined preview.')
        project.pop('preview_details',None)
        progress('Combined preview deferred until you choose Save & rebuild')
    else:
        project['preview_requested']=True
        progress('Rendering the combined B-roll preview')
        try:
            import numpy as np
            from hinglish_zoom.xml_apply import Sequence
            from hinglish_zoom.preview import render_preview
            seq=Sequence(xml)
            render_preview(seq,np.ones(seq.frames),[None]*seq.frames,Path(folder)/'preview.mp4',max_side=480,
                           progress=lambda _:None)
            project['preview_state']='ready'
            project.pop('preview_notice',None);project.pop('preview_details',None)
            progress('Combined B-roll preview ready')
        except Exception as error:
            (Path(folder)/'preview.mp4').unlink(missing_ok=True)
            project['preview_state']='failed'
            project['preview_notice']='The editable timeline is saved, but its preview could not be rendered. Choose an editor to inspect it, or retry Save & rebuild.'
            project['preview_details']=str(error)
            progress('The combined B-roll preview could not be rendered; saved choices are kept')
    write_json(Path(folder) / 'broll-project.json', project)
    if project.get('review_options'):
        finalize_candidate_bank(Path(folder)/'broll-project.json')
    write_report(Path(folder) / 'report.html', project)
    credits = []
    seen_credits=set()
    for s in project['slots']:
        for c in s.get('options',[]) or [s.get('chosen') or {}]:
            if not c or c.get('id') in seen_credits:continue
            seen_credits.add(c.get('id'))
            credits.append('\n'.join([c.get('title',''), 'Source: '+c.get('source',''),
                c.get('page_url',''), 'Creator: '+c.get('author',''),
                'Licence: '+(c.get('license') or ('Creator footage' if c.get('source')=='library' else 'Check the source page')),
                c.get('license_url','')]))
    (Path(folder)/'CREDITS.txt').write_text('\n\n'.join(credits),encoding='utf-8')
    return xml


def run(root, input_path, output_format=None, density=None, device=None, progress=print, black_background=False,
        target_count=0,brief='',review_options=False,options_per_moment=None,reference_script='',website_review=True,orientation=None):
    if not website_review:raise ValueError('B-roll now uses website search and human review. Reopen Add B-roll; API/Vision mode is disabled.')
    review_options=True
    from .website_catalogs import CATALOGUE_VERSION
    if type(target_count) is not int or not 0<=target_count<=30:
        raise ValueError('Choose a B-roll count between 1 and 30, or leave it blank for automatic coverage.')
    root = Path(root).resolve()
    from .choice_policy import choice_limit as resolve_choice_limit
    options_per_moment=resolve_choice_limit(options_per_moment,orientation,output_format=output_format)
    if orientation not in (None,'vertical','horizontal'):raise ValueError('Choose Vertical or Horizontal.')
    original_input=Path(input_path).resolve()
    if black_background and original_input.is_dir():
        single=_videos(original_input)
        if len(single)!=1:
            raise ValueError('Choose one video for the audio-only black-screen test, then try again.')
        input_path=single[0];original_input=single[0].resolve()
    settings = load_settings(root, density=density, device=device)
    sources = settings.sources()
    if black_background:
        # An audio-only test must not recycle the edited source's existing
        # visuals from the creator library and appear to have discovered them.
        sources=[source for source in sources if source!='library']
    if not sources and not (review_options and website_review):
        raise ValueError('Add a Pexels/Pixabay API key or a footage folder in B-roll settings first')
    store = RunStore(root, request_key(original_input, settings, output_format=output_format,
        black_background=black_background, target_count=target_count, brief=brief,
        review_options=review_options, options_per_moment=options_per_moment, reference_script=reference_script,
        website_review=bool(review_options and website_review),orientation=orientation,catalogue_version=CATALOGUE_VERSION))
    output = store.output
    if output:
        store.save()  # Attach this worker's marker before any expensive work.
        progress('Continuing the saved B-roll job; keeping completed searches, checks and choices')
        if store.data.get('state') == 'complete' and Path(store.data.get('result','')).is_file():
            return Path(store.data['result'])
    else:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
        output = root / 'output' / 'broll' / stamp
        output.mkdir(parents=True)
        store.start(output)
    if black_background:
        from .audio_test import black_video
        if Path(input_path).suffix.lower()=='.xml' or not Path(input_path).is_file():
            raise ValueError('Choose one video for the audio-only black-screen test, then try again.')
        progress('Keeping the original audio and replacing the picture with black for this test')
        target=output/'audio-only-source.mp4'
        input_path=target if valid_clip(output,target.name) else black_video(input_path,target)
    progress('Reading the timeline')
    saved_jobs=store.data.get('jobs',[])
    if saved_jobs and all(Path(j['timeline']['xml_path']).is_file() for j in saved_jobs):
        jobs=[]
        for saved in saved_jobs:
            timeline=parse_xmeml(saved['timeline']['xml_path']);timeline.name=saved['timeline']['name']
            jobs.append((timeline,output/saved['folder']))
    else:
        jobs = timelines_for(root, input_path, output, output_format, progress)
        store.data['jobs']=[{'folder':folder.name,'timeline':timeline_to_dict(timeline)} for timeline,folder in jobs]
        store.save()
    if black_background:
        for timeline,_ in jobs:timeline.name=original_input.stem+' — B-roll audio-only test'
    all_sources = sorted({s for t, _ in jobs for s in t.sources()})
    progress('Understanding your speech (reusing saved transcripts when available)')
    saved_plans={p['folder']:p for p in store.data.get('plans',[])}
    all_planned=all(folder.name in saved_plans for _,folder in jobs)
    words_by_source, notes = ({},store.data.get('notes',[])) if all_planned else transcripts_for(root, [str(original_input)] if black_background else all_sources, settings.device, progress)
    if black_background:
        original_words=words_by_source.get(path_key(original_input))
        if original_words is not None:
            for source in all_sources:words_by_source[path_key(source)]=original_words
    for note in notes: progress('  ' + note)

    plans = []
    from hinglish_visuals.brain import open_brain
    llm = None if all_planned else open_brain(root, threads=settings.cpu_threads, progress=progress)
    if llm is not None: llm.context_feature = 'broll'
    if llm is not None:llm.request_timeout=300
    try:
        for timeline, folder in jobs:
            if folder.name in saved_plans:
                from .settings import Profile
                from .phrases import Phrase
                saved=saved_plans[folder.name]
                slots=[Slot(moment=Moment(**s['moment']),**{k:v for k,v in s.items() if k!='moment'}) for s in saved['slots']]
                plans.append((timeline,folder,saved['summary'],Profile(**saved['profile']),slots,[Phrase(**p) for p in saved['phrases']]))
                continue
            for warning in timeline.warnings: progress('  ' + warning)
            words = timeline_words(timeline, words_by_source)
            phrases = (build_phrases(words,max_words=7,max_seconds=3,merge=False) if target_count
                       else build_phrases(words))
            if not phrases:
                progress(f'  No speech found in {timeline.name}; skipped')
                continue
            profile = profile_for(timeline.duration, settings.density)
            if black_background or review_options:
                # There is no talking-head picture to protect in an audio-only
                # test. Let an establishing cutaway cover the opening words.
                from dataclasses import replace
                profile=replace(profile,hook=0.,tail=0.,min_gap=0.,min_spacing=0.,
                                max_coverage=1. if review_options else profile.max_coverage)
            progress(f'Local AI is reading "{timeline.name}" ({len(phrases)} phrases, {profile.name}-form rules)')
            summary = summarize(llm, phrases)
            if reference_script.strip():
                summary['reference_script']=reference_script.strip()
                summary['reference_script_use']='Context and spelling hints only. Choose keywords and timestamps from the actual spoken words in the video.'
            progress(f'  Topic: {summary["topic"]}')
            if review_options:
                if profile.name == 'long':
                    from .keyword_windows import discover_bounded
                    slots=discover_bounded(llm,phrases,words,summary,target_count,brief,progress,
                                           checkpoint=folder/'keyword-windows.json')
                else:
                    from .keywords import discover
                    slots=discover(llm,phrases,words,summary,target_count or 10,brief,progress)
            else:
                from .clauses import semantic_phrases
                phrases=semantic_phrases(llm,words,summary,brief,progress)
                moments = plan_moments(llm, phrases, summary, profile, timeline.orientation, progress,
                                       requested_count=target_count,brief=brief)
                slots = place(moments, phrases, profile, timeline.duration,phrases)
            if not review_options and (target_count or settings.density=='high' and profile.name=='short'):
                desired=target_count or (10 if review_options else max(1,round(timeline.duration/7)))
                from .placement import cap_diverse_slots
                slots=cap_diverse_slots(slots,desired)
            progress(f'  {len(slots)} B-roll moments chosen')
            plans.append((timeline, folder, summary, profile, slots, phrases))
            store.data['plans'].append({'folder':folder.name,'summary':summary,'profile':asdict(profile),
                'slots':[asdict(s) for s in slots],'phrases':[asdict(p) for p in phrases]})
            store.data['notes']=notes
            store.save()
            guard.save(folder)   # the model checks for this timeline (quality report)
    finally:
        if llm: llm.close()
    if not plans:
        raise ValueError('No speech could be understood in the supplied timeline')

    if review_options and website_review:
        from .website_review import finish_plans
        return finish_plans(root,plans,output,store,options_per_moment,progress,orientation=orientation)

    from .vision import Vision
    vision = None
    # Saved ranked candidates need no embedding model or repeated web searches.
    needs_retrieval=any(not read_json(folder/'ranked-candidates.json') for _,folder,*_ in plans)
    progress('Loading the visual matching model' if needs_retrieval else 'Using saved visual searches; no model reload needed')
    if needs_retrieval:
        vision = Vision(settings.vision_model, root, settings.device, settings.cpu_threads)
    library = None
    if 'library' in sources and needs_retrieval:
        progress('Checking your footage library')
        library = Library(root, settings.library_folders, vision, exclude=all_sources, progress=progress).build()
        removed = library.exclude_lookalikes(timeline_fingerprint(vision, [t for t, _ in jobs]))
        if removed:
            progress(f'  Skipped {removed} of your clips that are takes of this same video')
        progress(f'  {len(library.entries)} of your clips are searchable')
    clients = []
    if 'pexels' in sources: clients.append(PexelsClient(settings.pexels_key, root))
    if 'pixabay' in sources: clients.append(PixabayClient(settings.pixabay_key, root))
    from .internet import CommonsClient, WebClient
    if 'commons' in sources: clients.append(CommonsClient(root))
    if 'web' in sources: clients.append(WebClient(root, progress))
    thumbs = root / 'cache' / 'broll' / 'thumbs'
    cached_sources=verified_internet_sources(root)
    if cached_sources:progress(f'Rechecking {len(cached_sources)} previously verified internet videos as search candidates')

    results = []
    generic = vision.texts([f'a photo of {scene}' for scene in GENERIC_SCENES]) if vision else None
    for timeline, folder, summary, profile, slots, phrases in plans:
        # Long reviews retain many independent keyword groups, each with at
        # most two video choices; this does not lower short-form's five choices.
        choice_limit=min(options_per_moment,2) if profile.name=='long' else options_per_moment
        ranked=read_json(folder/'ranked-candidates.json')
        if not ranked and (vision is None or vision.model is None):
            vision=Vision(settings.vision_model,root,settings.device,settings.cpu_threads)
            if library:library.vision=vision
            generic=vision.texts([f'a photo of {scene}' for scene in GENERIC_SCENES])
        pairs, embeddings = [], []
        retrieval=[]
        country = video_country(summary)
        if country:
            progress(f'  Video is set in {country.title()}: searching local footage, rejecting other countries')
        retrieved=read_json(folder/'retrieved-candidates.json',{})
        for n, slot in enumerate(slots, 1):
            if ranked:
                pairs.append((slot,[Candidate(**c) for c in ranked[str(n)]]))
                continue
            progress(f'Finding footage {n}/{len(slots)}: {slot.moment.visual}')
            # A whole-video setting (closed streets) must not override the
            # requested illustrative interior of this particular venue.
            embedding = moment_embedding(vision, slot, '' if brief else summary.get('visual_world', ''),neutral_venues=bool(brief))
            if str(n) in retrieved:
                candidates=[Candidate(**c) for c in retrieved[str(n)]]
                score_stock(vision,embedding,candidates,progress)
            else:
                candidates = gather_candidates(slot, embedding, library, clients, timeline.orientation, timeline,
                                               settings.results_per_query, thumbs, progress, country,cached_sources)
                fetch_thumbs(candidates, thumbs)
                score_stock(vision, embedding, candidates, progress)
                retrieved[str(n)]=[c.to_dict() for c in candidates]
                write_json(folder/'retrieved-candidates.json',retrieved)
            retrieval.append({'keyword':slot.moment.visual,'subject':slot.moment.subject,
                              'queries':slot.moment.queries,'start':slot.start,
                              'candidates':[{'id':c.id,'source':c.source,'title':c.title,'score':c.score,
                                             'extraction':c.extraction,'has_picture':bool(c.thumb)} for c in candidates]})
            write_json(Path(folder)/'retrieval.json',retrieval)
            progress(f'  Retrieved {len(candidates)} video candidates, including {sum(c.extraction for c in candidates)} web-video leads')
            pairs.append((slot, candidates)); embeddings.append(embedding)
        if not ranked:
            add_specificity(pairs, embeddings, generic)
            write_json(folder/'ranked-candidates.json',{str(n):[c.to_dict() for c in candidates] for n,(_,candidates) in enumerate(pairs,1)})
        picks = choose(pairs, timeline.orientation, settings.min_similarity)
        # Embeddings retrieve a shortlist; the larger reasoning vision model
        # judges actual downloaded frames next. Never keep both on the GPU.
        if vision: vision.close()
        import gc
        gc.collect()
        from .verify import Checker
        checker=None
        project = {'version': 3, 'media_policy':'videos_only', 'timeline': timeline_to_dict(timeline), 'summary': summary,
                   'transcript':[{'start':p.start,'end':p.end,'text':p.text,'meaning':p.meaning} for p in phrases],
                   'profile': profile.name, 'density': settings.density, 'device': settings.device,
                   'requested_count':target_count or (10 if review_options else 0),'brief':brief,'audio_only_test':black_background,
                   'review_options':review_options,'options_per_moment':choice_limit,'slots': []}
        project=read_json(folder/'broll-project.json',project)
        restore_choices(folder,project)
        if review_options:project['collecting']=True
        from .ranker import usage_key
        used_prepared={usage_key(Candidate(**{k:v for k,v in s['chosen'].items() if k in Candidate.__dataclass_fields__}))
                       for s in project['slots'] if s.get('chosen')}
        youtube_blocked=project.get('youtube_blocked',False)
        def save_progress():
            write_json(folder/'broll-project.json',project)
            if review_options:write_report(folder/'report.html',project)
        for i, (slot, _) in enumerate(pairs):
            chosen, others = picks[i]
            entry = {'index': i, 'start': slot.start, 'end': slot.end, 'text': slot.text,
                     'meaning': slot.moment.meaning, 'visual': slot.moment.visual, 'queries': slot.moment.queries,
                     'priority': slot.moment.priority, 'chosen': None, 'clip': None, 'alternatives': []}
            entry['subject'] = slot.moment.subject
            entry['setting'] = summary.get('visual_world','')
            entry['country'] = summary.get('country','')
            entry['direction'] = brief
            entry['translation'] = slot.moment.context
            entry['context'] = speech_context(project['transcript'],slot.start,slot.end)
            entry['source_in'] = 0.0
            entry['scale'] = 100
            entry['review_options']=review_options
            entry['options']=[]
            if i<len(project['slots']):
                entry=project['slots'][i]
                if entry.get('collection_complete'):continue
            else:
                project['slots'].append(entry)
            for c in ([chosen] if chosen else []) + others:
                if any(data['id']==c.id for data in entry['alternatives']):continue
                thumb = report_thumb(root, folder, c, slot.duration)
                data = c.to_dict()
                data['report_thumb'] = thumb.relative_to(folder).as_posix() if thumb else ''
                entry['alternatives'].append(data)
            from .ranker import acceptable,adjusted,usage_key
            pool=sorted((c for c in pairs[i][1] if acceptable(c) and
                         adjusted(c,timeline.orientation)>=settings.min_similarity),
                        key=lambda c:-adjusted(c,timeline.orientation))
            # A web-only top five must not hide viable direct-stock backups.
            # Downloadable sources go first; every choice still needs the same
            # actual-frame approval. Keep the work bounded for this laptop.
            direct_limit=max(6,choice_limit*2) if review_options else 8
            ready=[c for c in pool if not c.extraction][:direct_limit]
            # Thumbnail similarity is retrieval evidence, not a semantic veto.
            # Include strongly named venue metadata as a bounded backup when
            # the thumbnail is blurry or the embedding misses the interior.
            # The independent exact-window pixel check remains mandatory.
            from .ranker import venue_backups
            for candidate in venue_backups(slot.moment.queries,pairs[i][1]):
                if candidate not in ready and len(ready)<direct_limit:ready.append(candidate)
            web=[c for c in pool if c.extraction][:2]
            keyword_leads=[]
            if review_options:
                from .ranker import keyword_backups
                keyword_leads=keyword_backups(slot.moment.visual,pairs[i][1],2)
            if review_options and profile.name!='long' and sum(len(s.get('options',[])) for s in project['slots'])>=200:
                ready=[];web=[];keyword_leads=[]
            # Fast direct videos first. Only two slow web leads may consume
            # this keyword's budget; never spend five download timeouts first.
            web=list({c.id:c for c in keyword_leads+web}.values())[:2]
            candidates_to_check=list({c.id:c for c in ready+web}.values())
            save_progress()
            for selected in candidates_to_check:
                if len(entry['options'])>=choice_limit:break
                attempts=[a for a in entry.get('attempted',[]) if a['id']==selected.id]
                if attempts and (not attempts[-1].get('temporary') or len(attempts)>=2):continue
                if review_options:
                    if any(c['id']==selected.id for c in entry['options']):continue
                elif usage_key(selected) in used_prepared:continue
                is_youtube=bool(re.search(r'(?:youtube\.com|youtu\.be)',selected.page_url+' '+selected.download_url,re.I))
                if youtube_blocked and is_youtube:continue
                # If the top result is unavailable or fails actual-frame checks,
                # try other videos. Never substitute a still or a weak match.
                progress(f'Checking {slot.moment.visual}: {len(entry.get("attempted",[]))+len(entry["options"])+1}/{len(candidates_to_check)} candidates, {len(entry["options"])} choices saved')
                try:
                    if checker is None:checker=Checker(root)
                    import copy
                    candidate_entry=copy.deepcopy(entry) if review_options else entry
                    clip = retry(lambda: render_choice(root, folder, timeline, i, candidate_entry, selected, settings.device,
                                         settings.handle_seconds,checker=checker),progress,'Video preparation',attempts=2)
                    data=next((c for c in entry['alternatives'] if c['id']==selected.id),None)
                    if data is None:
                        data=selected.to_dict()
                        thumb=report_thumb(root,folder,selected,slot.duration)
                        data['report_thumb']=thumb.relative_to(folder).as_posix() if thumb else ''
                        entry['alternatives'].append(data)
                    data.update(selected.to_dict())
                    # Show the checked portion, rather than a stock thumbnail
                    # or the unused trim handles surrounding this window.
                    pictures=read_frames(clip,[candidate_entry.get('source_in',0)+slot.duration/2],size=320)
                    if pictures:
                        thumb=folder/'thumbs'/('checked-'+str(i)+'-'+cached_name(selected,'thumb'))
                        thumb.parent.mkdir(parents=True,exist_ok=True);pictures[0][1].save(thumb,quality=85)
                        data['report_thumb']=thumb.relative_to(folder).as_posix()
                    if review_options:
                        option=_review_option_data(folder,candidate_entry,selected,clip,data)
                        entry['options'].append(option)
                        entry.setdefault('checks',[]).extend(candidate_entry.get('checks',[])[len(entry.get('checks',[])):])
                    if not entry['chosen']:
                        entry['chosen'] = data
                        entry['clip'] = clip.relative_to(folder).as_posix()
                        for field in ('source_in','source_duration','canvas_width','canvas_height'):
                            if field in candidate_entry:entry[field]=candidate_entry[field]
                    used_prepared.add(usage_key(selected))
                    save_progress()
                    if (not review_options or len(entry['options'])>=choice_limit or
                            profile.name!='long' and sum(len(s.get('options',[])) for s in project['slots'])>=200):break
                except Exception as error:
                    from .verify import CheckUnavailable
                    if isinstance(error,CheckUnavailable):
                        save_progress()
                        raise
                    from hinglish_app.user_messages import problem
                    from .candidate_manifest import CandidateContractError
                    issue=error.as_issue() if isinstance(error,CandidateContractError) else problem(error)
                    entry.setdefault('attempted',[]).append({'id':selected.id,'temporary':transient(error),
                        'code':issue['code'],'message':issue['message'],'details':issue['details']})
                    if review_options:
                        entry.setdefault('checks',[]).extend(candidate_entry.get('checks',[])[len(entry.get('checks',[])):])
                    save_progress()
                    if is_youtube and 'not a bot' in str(error).casefold():
                        youtube_blocked=True
                        project['youtube_blocked']=True
                        from hinglish_app.user_messages import problem
                        message=problem('YouTube video download requires sign-in')['message']
                        progress('  '+message)
                        project.setdefault('source_notices',[]).append(message)
                        save_progress()
                        continue
                    progress(f'  Skipped an unsuitable or unavailable candidate; {len(entry["options"])} choices are saved.')
            if youtube_blocked:
                entry['alternatives']=[c for c in entry['alternatives'] if not
                    re.search(r'(?:youtube\.com|youtu\.be)',c.get('page_url','')+' '+c.get('download_url',''),re.I)
                    or c.get('id')==(entry.get('chosen') or {}).get('id')]
            entry['collection_complete']=True
            # Keep completed choices and rejected-candidate explanations even
            # if a later site, model call or render fails.
            save_progress()
        filled = sum(1 for s in project['slots'] if s['clip'])
        project.pop('collecting',None)
        xml = write_outputs(root, folder, project,defer_review_preview=review_options,progress=progress)
        progress(f'  {filled}/{len(project["slots"])} moments received B-roll')
        if review_options:progress(f'Collected {sum(len(s.get("options",[])) for s in project["slots"])} playable video options for human selection')
        results.append({'name': timeline.name, 'folder': folder.name, 'filled': filled,
                        'moments': len(project['slots']), 'xml': str(xml)})
        from hinglish_cut.model_preferences import release_ollama
        if checker is not None:release_ollama(root)
    if vision: vision.close()
    write_index(output / 'index.html', results, notes)
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    result=output / (results[0]['folder'] + '/report.html' if len(results) == 1 else 'index.html')
    store.data.update(state='complete',result=str(result))
    store.save()
    return result


def rebuild_project(project_file, choices, progress=print, edits=None, black_background=None):
    """choices: {slot_index: candidate_id or ''}. '' removes B-roll from that moment."""
    project_file = Path(project_file)
    folder, root = project_file.parent, project_file.parents[4]
    project = json.loads(project_file.read_text(encoding='utf-8'))
    timeline = parse_xmeml(project['timeline']['xml_path'])
    import copy
    project = copy.deepcopy(project)
    # Explicit rebuild resumes the saved bank after a stopped collection. Its
    # available choices are retained even when the final packaging had failed.
    project.pop('collecting',None)
    if black_background is not None and black_background!=project.get('audio_only_test',False):
        if black_background:
            if len(timeline.clips)!=1 or abs(timeline.clips[0].source_in)>.001:
                raise ValueError('Choose one complete source video for an audio-only preview. Your saved choices are kept.')
            from .audio_test import black_video
            from hinglish_cut.media import probe
            original_xml=project['timeline']['xml_path']
            black=black_video(timeline.clips[0].path,folder/'audio-test/source-black.mp4',max_side=None)
            media=probe(black)
            new_xml=folder/'audio-test/source-timeline.xml'
            export_xml(new_xml,[Cut(media.id,0,round(timeline.duration*float(media.rate)),0)],{media.id:media})
            project['original_timeline_path']=original_xml
            project['timeline']['xml_path']=str(new_xml.resolve())
        else:
            original=project.get('original_timeline_path')
            if not original:raise ValueError('The original picture timeline is unavailable. Your saved choices and audio are kept.')
            project['timeline']['xml_path']=original
        project['audio_only_test']=black_background
    _apply_edits(project, edits or {})
    for key, wanted in (choices or {}).items():
        slot = next((s for s in project['slots'] if str(s['index'])==str(key)),None)
        if slot is None:raise ValueError('Choose a B-roll moment in this project and try again.')
        current = (slot.get('chosen') or {}).get('id', '')
        if wanted == current:
            continue
        if not wanted:
            slot['chosen'], slot['clip'] = None, None
            continue
        data = next((c for c in slot['alternatives'] if c['id'] == wanted), None)
        if data is None:
            raise ValueError('That clip is not one of the suggestions for this moment')
        candidate = Candidate(**{k: v for k, v in data.items() if k in Candidate.__dataclass_fields__})
        if candidate.kind!='video':
            raise ValueError('Add B-roll uses videos only. Choose a video clip instead of an image.')
        from .verify import Checker
        slot['context']=speech_context(project.get('transcript',[]),slot['start'],slot['end']) or slot.get('context','')
        slot['direction']=project.get('brief','')
        slot['setting']=project.get('summary',{}).get('visual_world','')
        slot['country']=project.get('summary',{}).get('country','')
        clip = render_choice(root, folder, timeline, slot['index'], slot, candidate, project.get('device', 'cpu'),checker=Checker(root))
        slot['chosen'], slot['clip'] = data, clip.relative_to(folder).as_posix()
    _apply_edits(project,{})
    xml = write_outputs(root, folder, project,progress=progress)
    return {'xml_files': [str(xml.resolve())], 'filled': sum(1 for s in project['slots'] if s.get('clip'))}


def speech_context(transcript,start,end):
    """Keep the complete surrounding thought, with original speech and timing."""
    nearby=[p for p in transcript if p['end']>start-8 and p['start']<end+8]
    return '\n'.join(f"{p['start']:.2f}-{p['end']:.2f}s: {p['text']}" for p in nearby)[:2600]


def _apply_edits(project, edits):
    """Validate the whole edit before writing files: range, source handles and overlap."""
    if not isinstance(edits,dict):
        raise ValueError('Choose valid B-roll timing controls and try again.')
    for key, change in edits.items():
        if not isinstance(change,dict) or str(key) not in {str(s['index']) for s in project['slots']}:
            raise ValueError('Choose a B-roll moment in this project and try again.')
        slot=next(s for s in project['slots'] if str(s['index'])==str(key))
        for name in ('start','end','source_in','scale'):
            if name in change:
                value=change[name]
                if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
                    raise ValueError('B-roll timing and size need finite numbers. Check the selected moment.')
                slot[name]=float(value)
        if not 0<=slot['start']<slot['end']<=project['timeline']['duration']:
            raise ValueError('B-roll timing is outside the video. Keep start before end and inside the timeline.')
        if not 10<=slot.get('scale',100)<=200:
            raise ValueError('B-roll size must be between 10 and 200 percent. Check the selected moment.')
        source_duration=slot.get('source_duration',slot['end']-slot['start'])
        from fractions import Fraction
        fps=float(Fraction(str(project['timeline'].get('fps',30))))
        if slot.get('clip'):_align_frame_trim(slot,slot['start'],slot['end'],fps,source_duration)
    from fractions import Fraction
    fps=float(Fraction(str(project['timeline'].get('fps',30))))
    for slot in project['slots']:
        if slot.get('clip'):_align_frame_trim(slot,slot['start'],slot['end'],fps)
    chosen=sorted((s for s in project['slots'] if s.get('clip')),key=lambda s:s['start'])
    if any(b['start']<a['end']-.001 for a,b in zip(chosen,chosen[1:])):
        raise ValueError('B-roll timings overlap. Shorten or move the neighbouring cutaway, then save again.')


def _align_frame_trim(item,start,end,fps,source_duration=None):
    """Allow only the single-frame difference caused by rounding two endpoints.

    Real over-trims remain errors. A generated choice with handles can start
    one frame earlier so the exact timeline duration fits its available file.
    """
    source=round(item.get('source_in',0)*fps)
    available=round((source_duration if source_duration is not None else item.get('source_duration',end-start))*fps)
    frames=round(end*fps)-round(start*fps)
    excess=source+frames-available
    if excess==1 and source>=1 and available>=frames:
        item['source_in']=(source-1)/fps
        source-=1
    if item.get('source_in',0)<0 or source+frames>available:
        raise ValueError('B-roll trim exceeds its available footage. Shorten the cutaway or choose another clip.')
