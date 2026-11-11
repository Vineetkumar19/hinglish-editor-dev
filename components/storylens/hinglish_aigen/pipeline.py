"""The run behind both tools. AI Images: script (or video) -> picture moments + prompts (rule-checked) -> pictures on
your GPU (options each) -> vision check (bad ones made again). AI Video: clip moments -> a sharp first frame per
moment (checked, you can pick another) -> animated into a 5 s 720p clip -> checked. Both give a 'chosen' folder,
a timeline with the results on V2 (when you gave a video) and a review page."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
import random
import re
import shutil
import uuid

from hinglish_clean.detection import write_json
from hinglish_eval import guard

from . import engine
from .judge import open_judge
from .plan import plan_moments, script_lines, speech_lines
from .report import write_report
from .settings import NEGATIVE, SIZES, VIDEO_SIZES, GenSettings, style_prompt

TOOLS = {'image': ('aiimage', 'AI Images'), 'video': ('aivideo', 'AI Video')}
LETTERS = 'abcd'
MIN_SHOW, MAX_SHOW = 2.5, 6.0          # seconds a picture stays on screen in the timeline
CLIP_SECONDS = 5.0


def slug(text, limit=40):
    return re.sub(r'[^A-Za-z0-9]+', '-', str(text)).strip('-')[:limit] or 'visual'


def project_name(kind):
    return f'{TOOLS[kind][0]}-project.json'


def _aspect(settings, timeline=None):
    if settings.aspect != 'auto':
        return settings.aspect
    if timeline is not None:
        return {'portrait': '9:16', 'landscape': '16:9', 'square': '1:1'}[timeline.orientation]
    return '16:9'


def _full_prompt(text, style):
    return f'{text.rstrip(". ")}. {style}'


def _good(option):
    return not option.get('error') and (option.get('verdict') is None or option['verdict'].get('passed'))


def _best(options):
    made = [o for o in options if not o.get('error')]
    if not made:
        return ''
    return sorted(made, key=lambda o: (bool(_good(o)), (o.get('verdict') or {}).get('score', 0)), reverse=True)[0]['id']


def make_pictures(root, folder, moments, settings, style, aspect, judge, progress, round_name='a'):
    """settings.options pictures per moment, checked; a moment with no good picture is tried once more.
    Fills m['options'] and m['chosen']. (AI Video: these are the first frames.)"""
    width, height = SIZES[aspect]
    todo = list(moments)
    what = 'picture' if settings.kind == 'image' else 'first frame'
    for attempt in (1, 2):
        items = []
        for m in todo:
            for k in range(settings.options):
                option = f'm{m["index"]:02d}{round_name}{attempt}{LETTERS[k]}'
                items.append({'id': option, 'kind': 'image', 'prompt': _full_prompt(m['prompt'], style),
                              'width': width, 'height': height, 'seed': random.randint(1, 2 ** 31 - 1),
                              'out': str(folder / 'images' / f'{option}.png'),
                              'label': f'{what} {m["index"]} option {k + 1}'})
        if not items:
            break
        progress(f'Making {len(items)} {what}(s) on your GPU' + (' (second try for the failed ones)' if attempt == 2 else ''))
        results = engine.generate(root, items, folder / f'jobs-pictures-{round_name}{attempt}.json', progress)
        for item in items:
            m = next(x for x in todo if item['id'].startswith(f'm{x["index"]:02d}'))
            made = results.get(item['id'], {})
            option = {'id': item['id'], 'file': f'images/{item["id"]}.png', 'seconds': made.get('seconds'),
                      'error': made.get('error', '' if made else 'not made'), 'verdict': None}
            if made.get('event') == 'done' and judge is not None:
                requested=m['prompt']
                if settings.kind=='image' and settings.request_mode=='idea':
                    requested+='\nOriginal user request: '+m['text']+'\nCheck the exact visible subject/object counts, exclusions and requested action as well as anatomy, equipment and composition. Extra opponents or extra balls fail the request.'
                verdict = judge.image(item['out'], requested)
                option['verdict'] = verdict.to_dict()
                progress(f'  {what.capitalize()} {m["index"]}: {"PASS" if verdict.passed else "FAIL"} '
                         f'{"; ".join(verdict.reasons)[:120]}')
            m.setdefault('options', []).append(option)
        todo = [m for m in todo if not any(_good(o) for o in m['options'])]
        if judge is None:
            break
    for m in moments:
        m['chosen'] = _best(m.get('options', []))


def make_clips(root, folder, moments, style, aspect, judge, progress, from_picture=True, quality='full'):
    """AI Video: each moment becomes a 5 s clip, animated from its chosen first frame (or from the text alone)."""
    width, height = VIDEO_SIZES[aspect]
    items = []
    for m in moments:
        still = next((o for o in m.get('options', []) if o['id'] == m.get('chosen')), None)
        if from_picture and still is None:
            continue
        clip = f'm{m["index"]:02d}-{uuid.uuid4().hex[:4]}'
        items.append({'id': clip, 'kind': 'video', 'prompt': _full_prompt(f'{m["prompt"]} {m.get("motion", "")}', style),
                      'negative': NEGATIVE, 'image': str(folder / still['file']) if from_picture else None,
                      'width': width, 'height': height, 'frames': 121, 'fps': 24,
                      'seed': random.randint(1, 2 ** 31 - 1), 'out': str(folder / 'videos' / f'{clip}.mp4'),
                      'label': f'clip {m["index"]}'})
    if not items:
        return
    if quality=='preview':
        for item in items:item.update(width=480 if aspect=='9:16' else 832,height=832 if aspect=='9:16' else 480,frames=49)
        if aspect=='1:1':
            for item in items:item.update(width=480,height=480)
    progress(f'Animating {len(items)} clip(s): '+('2-second quick preview' if quality=='preview' else '5-second full clips'))
    results = engine.generate(root, items, folder / f'jobs-clips-{uuid.uuid4().hex[:4]}.json', progress, **({'mode':'low'} if quality=='preview' else {}))
    for item in items:
        m = next(x for x in moments if item['id'].startswith(f'm{x["index"]:02d}-'))
        made = results.get(item['id'], {})
        video = {'file': f'videos/{item["id"]}.mp4', 'error': made.get('error', '' if made else 'not made'),
                 'seconds': made.get('seconds'), 'verdict': None, 'from': m.get('chosen') if from_picture else ''}
        if made.get('event') == 'done' and judge is not None:
            video['verdict'] = judge.video(item['out'], f'{m["prompt"]} {m.get("motion", "")}').to_dict()
            progress(f'  Clip {m["index"]}: {"PASS" if video["verdict"]["passed"] else "FAIL"} '
                     f'{"; ".join(video["verdict"]["reasons"])[:120]}')
        m['video'] = video


def chosen_file(m):
    """What goes into the video for this moment. AI Images: the chosen picture. AI Video: the clip (if it could not
    be made, its first frame, so the timeline still has something there)."""
    if m.get('removed') or (not m.get('chosen') and m['kind'] == 'image'):
        return ''
    video = m.get('video') or {}
    if m['kind'] == 'video' and video.get('file') and not video.get('error'):
        return video['file']
    option = next((o for o in m.get('options', []) if o['id'] == m.get('chosen')), None)
    return option['file'] if option else ''


def finish(root, folder, project, progress=print):
    """'chosen' folder in story order, the timeline (if any), the review page."""
    chosen = folder / 'chosen'
    if chosen.exists():
        shutil.rmtree(chosen)
    chosen.mkdir()
    for m in project['moments']:
        file = chosen_file(m)
        if file:
            shutil.copyfile(folder / file, chosen / f'{m["index"]:02d} - {slug(m["text"])}{Path(file).suffix}')
    timeline_info = project.get('timeline')
    if timeline_info:
        from hinglish_broll.timeline import parse_xmeml
        from hinglish_broll.xml_export import export_broll_xml
        from hinglish_visuals.render import still_clip, video_clip
        timeline = parse_xmeml(timeline_info['xml'])
        timeline.name = timeline_info['name']
        placements, clips = [], folder / 'clips'
        clips.mkdir(exist_ok=True)
        for m in project['moments']:
            file = chosen_file(m)
            if not file:
                continue
            if file.endswith('.mp4'):
                seconds = min(CLIP_SECONDS, max(MIN_SHOW, m['end'] - m['start'] + .5))
                import av
                with av.open(str(folder/file)) as source:
                    stream=source.streams.video[0]
                    available=float(stream.duration*stream.time_base) if stream.duration is not None else source.duration/av.time_base
                seconds=min(seconds,available)
            else:
                seconds = min(MAX_SHOW, max(MIN_SHOW, m['end'] - m['start'] + .3))
            seconds = min(seconds, max(0, timeline.duration - m['start']))
            if seconds<=0:continue
            target = clips / f'{m["index"]:02d}-{Path(file).stem}.mp4'
            if not target.exists():
                if file.endswith('.mp4'):
                    video_clip(str(folder / file), 0.0, seconds, timeline.width, timeline.height, timeline.fps, target)
                else:
                    still_clip(str(folder / file), seconds, timeline.width, timeline.height, timeline.fps, target)
            start_frame=round(m['start']*timeline.fps);clip_frames=max(1,round(seconds*timeline.fps))
            placements.append({'path': str(target), 'start': float(start_frame/timeline.fps),
                               'end': float((start_frame+clip_frames)/timeline.fps),'source_duration':float(clip_frames/timeline.fps),
                               'name': f'{project["tool"]} {m["index"]}'})
        suffix = '_AI_IMAGES' if project['kind'] == 'image' else '_AI_VIDEO'
        xml = export_broll_xml(timeline, placements, folder / f'{suffix.strip("_")}_SEQUENCE.xml', suffix=suffix)
        project['xml'] = xml.name
        progress(f'  Timeline: {len(placements)} on V2 -> {xml.name}')
    write_json(folder / project_name(project['kind']), project)
    write_report(folder / 'report.html', project)


def run(root, input_path=None, script='', settings=None, progress=print):
    root = Path(root).resolve()
    settings = settings or GenSettings()
    if settings.kind=='video' and settings.video_method=='motion':
        from hinglish_aivideo.studio import run_motion
        return run_motion(root,input_path,script,settings,progress)
    if settings.request_mode=='idea':
        if input_path:raise ValueError('Image ideas do not need a video. Clear the video selection or choose Pictures from a script.')
        if not script.strip():raise ValueError('Describe the image you want, then choose Generate images.')
    kind = settings.kind
    tool_folder, tool = TOOLS[kind]
    status = engine.doctor(root)
    if not status.get('cuda'):
        raise RuntimeError(status.get('problem') or f'{tool} is not set up')
    if kind == 'image' and not status.get('image_model'):
        raise RuntimeError('The picture model is not downloaded: run "Setup AI Images (RTX).bat" once')
    if kind == 'video':
        if not status.get('video_model'):
            raise RuntimeError('The video model is not downloaded: run "Setup AI Video (RTX).bat" once')
        if settings.from_picture and not status.get('image_model'):
            progress('  The picture model is not installed: clips start from the text (run "Setup AI Images (RTX).bat" '
                     'for sharper first frames)')
            settings.from_picture = False
    progress(f'{tool} ready on {status["gpu"]} ({status["vram_gb"]} GB, {status["mode"]} mode)')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / tool_folder / stamp
    output.mkdir(parents=True)
    reference=None
    if kind=='video' and settings.video_method=='reference':
        from hinglish_aivideo.studio import analyse_reference
        reference=analyse_reference(root,settings.reference,output,progress)
    jobs = []
    if input_path:
        from hinglish_broll.pipeline import timelines_for, transcripts_for
        from hinglish_broll.timeline import timeline_words
        for timeline, folder in timelines_for(root, input_path, output, None, progress):
            words, notes = transcripts_for(root, timeline.sources(), 'cpu', progress)
            words = timeline_words(timeline, words)
            if script.strip():
                from hinglish_visuals.script import apply_script
                words, _ = apply_script(words, script)
            jobs.append((folder, speech_lines(words), timeline))
    else:
        if not script.strip():
            raise ValueError('Paste your script (or choose a video)')
        folder = output / '001-script'
        folder.mkdir()
        jobs.append((folder, script_lines(script), None))
    style = style_prompt(root, settings.style, settings.custom_style)
    from hinglish_cut.reelmimic import context as reference_context
    reference = reference or reference_context(root, 'aiimage' if settings.kind == 'image' else 'aivideo')
    if reference and not settings.custom_style.strip():
        reading = reference.get('visual_reading') or {}
        style += '\nReference style: ' + json.dumps(reading, ensure_ascii=False)
    judge = open_judge(root, progress) if settings.check else None
    pages = []
    try:
        for folder, lines, timeline in jobs:
            from hinglish_visuals.brain import open_brain
            brain = open_brain(root, settings.brain, 'qwen3:8b', settings.cpu_threads, progress)
            brain.context_feature = 'thumbnail'
            try:
                progress(f'  AI brain: {brain.name}')
                receipt=None
                if settings.request_mode=='idea':
                    from .direct import plan_idea
                    planned,entities,receipt=plan_idea(brain,script,settings,progress)
                    write_json(folder/'image-direction.json',receipt)
                else:
                    planned, entities = plan_moments(brain, lines, settings, progress, reference=reference) if reference else plan_moments(brain, lines, settings, progress)
            finally:
                brain.close()
            guard.save(folder)
            if not planned:
                progress('  No moment needs one here')
                continue
            moments = [{'index': n, **m.to_dict()} for n, m in enumerate(planned, 1)]
            aspect = _aspect(settings, timeline)
            if kind == 'image' or settings.from_picture:
                make_pictures(root, folder, moments, settings, style, aspect, judge, progress)
            if kind == 'video':
                make_clips(root, folder, moments, style, aspect, judge, progress, settings.from_picture, settings.quality)
            project = {'version': 1, 'kind': kind, 'tool': tool, 'settings': asdict(settings), 'style': style,
                       'aspect': aspect, 'entities': entities, 'evaluator': judge.name if judge else 'off',
                       'moments': moments, 'script': ' '.join(l.text for l in lines)[:20000],
                       'timeline': ({'xml': timeline.xml_path, 'name': timeline.name} if timeline else None)}
            if receipt:project['image_direction']=receipt
            if kind=='video':
                project['production']={'method':settings.video_method,'quality':settings.quality,'reference':reference,'tools':['Qwen planner','Wan 2.2','Qwen Vision' if judge else 'Vision check off']}
                write_json(folder/'production-receipt.json',project['production'])
            finish(root, folder, project, progress)
            pages.append(folder / 'report.html')
            if kind == 'image':
                made = sum(1 for m in moments if chosen_file(m))
                progress(f'Done: {made} of {len(moments)} moments have a picture')
            else:           # a failed clip falls back to its first frame: count real clips only
                made = sum(1 for m in moments if (m.get('video') or {}).get('file') and not m['video'].get('error'))
                progress(f'Done: {made} of {len(moments)} clips made' +
                         ('' if made == len(moments) else ' (the others use their first frame; see the review page)'))
    finally:
        if judge is not None:
            judge.close()
    if not pages:
        raise ValueError('No moment needed one')
    return pages[0]


def rebuild_project(project_file, changes, progress=print):
    """Review page: {choices: {index: option id or ''}, regenerate: {index: new prompt}}.
    AI Images: new pictures only for 'regenerate'. AI Video: new first frames for 'regenerate', and a new clip for
    every moment whose first frame changed. Then the chosen folder, timeline and page are redone."""
    project_file = Path(project_file)
    folder = project_file.parent
    root = folder.parents[3]                      # <root>/output/<tool>/<run>/<job>
    project = json.loads(project_file.read_text(encoding='utf-8'))
    settings = GenSettings(**project['settings'])
    by_index = {m['index']: m for m in project['moments']}
    animate = []
    for index, option in (changes.get('choices') or {}).items():
        m = by_index.get(int(index))
        if m is None or not (option == '' or any(o['id'] == option for o in m.get('options', []))):
            continue
        m['removed'] = option == ''                # "No AI visual here" (also for clips made from text only)
        if option and option != m.get('chosen'):
            m['chosen'] = option
            if m['kind'] == 'video':
                m['video'] = None
                animate.append(m)
    redo = []
    for index, prompt in (changes.get('regenerate') or {}).items():
        m = by_index.get(int(index))
        if m is None:
            continue
        m['prompt'] = ' '.join(str(prompt or m['prompt']).split())[:700]
        m['options'], m['video'], m['removed'] = [], None, False
        redo.append(m)
    judge = open_judge(root, progress) if settings.check and (redo or animate) else None
    try:
        if redo and (project['kind'] == 'image' or settings.from_picture):
            make_pictures(root, folder, redo, settings, project['style'], project['aspect'], judge, progress,
                          'r' + uuid.uuid4().hex[:3])
        if project['kind'] == 'video':
            todo = redo + [m for m in animate if m not in redo]
            make_clips(root, folder, todo, project['style'], project['aspect'], judge, progress, settings.from_picture,settings.quality)
    finally:
        if judge is not None:
            judge.close()
    if (folder / 'clips').exists():
        for clip in (folder / 'clips').glob('*.mp4'):
            clip.unlink()                          # the timeline clips follow the new choices
    finish(root, folder, project, progress)
    return {'moments': len(project['moments']), 'remade': len(redo) + len(animate),
            'with_visual': sum(1 for m in project['moments'] if chosen_file(m))}
