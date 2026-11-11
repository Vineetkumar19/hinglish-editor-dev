"""Saved, event-bound choices. Auditions/remixes never call a judging model."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import math
import shutil

from .library import Asset, decode
from .cues import place_cue
from .settings import SFX_BEHAVIOUR


def build(moments, candidates, picks):
    choices = {p.get('moment'): p for p in picks.get('effects', [])}
    events = []
    for i, (moment, slate) in enumerate(zip(moments, candidates)):
        pick = choices.get(i, {})
        best = pick.get('choice', -1)
        recommended = [n for n in pick.get('alternatives', [])
                       if type(n) is int and 0 <= n < len(slate) and n != best]
        order = list(dict.fromkeys(([best] if type(best) is int and 0 <= best < len(slate) else [])
                                  + recommended + ([] if 'keyword' in pick else list(range(len(slate))))))
        events.append({'id': f'event-{i}', 'intent': moment.get('intent', ''),
                       'keyword': pick.get('keyword', moment.get('keyword', moment.get('intent', 'Sound options'))),
                       'word': moment.get('word', ''), 'category': moment['type'],
                       'time': moment['target'], 'duration': moment.get('duration', SFX_BEHAVIOUR[moment['type']]['max_len']),
                       'level_db': SFX_BEHAVIOUR[moment['type']]['offset'] + moment.get('level_db', 0),
                       'reason': pick.get('why', moment.get('why', '')),
                       'best': f'choice-{best}' if type(best) is int and 0 <= best < len(slate) else None,
                       'candidates': [{'id': f'choice-{n}', 'asset': asdict(slate[n]['asset']),
                                       'recommendation': 'Qwen first choice' if n == best else
                                       'Qwen alternative' if n in recommended else 'Library match',
                                       'description': slate[n].get('doc', '')} for n in order]})
    review={'version': 2, 'events': events, 'selections': None,
            'policy': 'Qwen first choice; human approval; no second-model veto'}
    from .keyword_folders import organize
    organize(review)
    return review


def bind_timeline(review, cues):
    """Initial selections mirror the real rendered timeline, including any numeric limits."""
    if review.get('selections') is not None:
        return
    used = set()
    rows = []
    for event in review['events']:
        for candidate in event['candidates']:
            for i, cue in enumerate(cues):
                if i in used or cue['path'] != candidate['asset']['path']:
                    continue
                if abs(cue['target'] - event['time']) > .02:
                    continue
                rows.append({'event': event['id'], 'candidate': candidate['id'],
                             'start': cue['time'], 'duration': cue['length'], 'level_db': cue['offset_db']})
                candidate['initial_cue'] = deepcopy(cue)
                used.add(i)
                break
    review['selections'] = rows


def _candidate(plan, event_id, candidate_id):
    event = next((e for e in plan.get('human_review', {}).get('events', []) if e['id'] == event_id), None)
    row = next((c for c in event['candidates'] if c['id'] == candidate_id), None) if event else None
    if row is None:
        raise ValueError('This sound option is unavailable. Reopen the saved sound review.')
    path = Path(row['asset']['path']).resolve()
    if not path.is_file():
        raise ValueError('This sound file has moved. Restore it to its library folder and try again.')
    return event, row


def audition(plan_file, event_id, candidate_id):
    """Copy only an option already bound to the saved project, never an arbitrary request path."""
    import soundfile as sf
    from urllib.parse import quote
    plan_file = Path(plan_file)
    plan = json.loads(plan_file.read_text('utf-8'))
    event, row = _candidate(plan, event_id, candidate_id)
    source = Path(row['asset']['path'])
    key = hashlib.sha256((str(source.resolve()) + str(source.stat().st_mtime_ns)).encode()).hexdigest()[:20]
    folder = plan_file.parent / 'review-audio'
    folder.mkdir(exist_ok=True)
    preview = folder / (key + '.wav')
    if not preview.exists():
        audio = decode(source, limit=12)
        sf.write(preview, audio.T, 48000, subtype='PCM_16')
    original = folder / (key + '-original' + source.suffix.lower())
    if not original.exists():
        shutil.copy2(source, original)
    output_root = plan_file.parents[2]  # output/sound
    url = lambda p: '/sound-output/' + quote(p.relative_to(output_root).as_posix())
    return {'preview': url(preview), 'download': url(original), 'name': source.name,
            'notice': 'Original recording; first 12 seconds for audition. Timeline trim and level are applied when saved.'}


def apply(plan, selections):
    """Validate owner choices and build literal timeline cues; no model, novelty or taste veto."""
    if not isinstance(selections, list) or len(selections) > 500:
        raise ValueError('Choose up to 500 sound layers for this review.')
    cues, seen, saved = [], set(), []
    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError('Choose sounds from this review before saving.')
        event, row = _candidate(plan, selection.get('event'), selection.get('candidate'))
        key = (event['id'], row['id'])
        if key in seen:
            raise ValueError('The same option was added twice to one event.')
        seen.add(key)
        values = [selection.get(k) for k in ('start', 'duration', 'level_db')]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Enter valid numbers for start, duration and volume.')
        start, duration, level = values
        maximum = min(float(row['asset']['duration']), plan['seconds'] - start)
        if start < 0 or duration <= 0 or duration > maximum + .001 or not -60 <= level <= 6:
            raise ValueError('Keep the sound inside the video and source duration, with volume between -60 and +6 dB.')
        asset = Asset(**row['asset'])
        cue = place_cue(asset, start, event['category'], 'Owner selected from Qwen review',
                        event.get('word', ''), event['intent'], requested_length=duration)
        # Explicit owner start is literal, not an automatic peak-alignment request.
        cue.time, cue.target, cue.length, cue.offset_db = start, start, duration, level
        initial = row.get('initial_cue', {})
        cue.source_offset = min(float(initial.get('source_offset', 0)), max(0, asset.duration - duration))
        cue.group_id, cue.source = event['id'], 'human_review'
        cue.evaluation = {'passed': None, 'review': 'Owner choice; no model cross-check'}
        cue.alternatives = [{'path': c['asset']['path'], 'name': c['asset']['name']} for c in event['candidates']]
        cues.append(cue.to_dict())
        saved.append(dict(event=event['id'], candidate=row['id'], start=start, duration=duration, level_db=level))
    plan['human_review']['selections'] = saved
    plan['cues'] = plan['all_cues'] = cues
    plan['kept'] = list(range(len(cues)))
    plan['settings']['human_review'] = True
    plan['settings']['listen'] = plan['settings']['evaluate'] = False
    plan['listener'] = ''
    return plan


def register(plan_file):
    """Register actual saved reviews for the Adobe/CapCut companion result picker."""
    plan_file=Path(plan_file).resolve()
    root=plan_file.parents[4]
    if not plan_file.is_relative_to(root/'output/sound'):return
    key='mix-'+hashlib.sha256(str(plan_file).encode()).hexdigest()[:24]
    folder=root/'cache/app/human-sound-reviews';folder.mkdir(parents=True,exist_ok=True)
    (folder/(key+'.json')).write_text(json.dumps({'id':key,'plan':str(plan_file)}),encoding='utf-8')
    return key


def registered(root, key):
    import re
    if not isinstance(key,str) or not re.fullmatch(r'mix-[a-f0-9]{24}',key):
        raise ValueError('Choose a saved sound review.')
    root=Path(root).resolve();entry=root/'cache/app/human-sound-reviews'/(key+'.json')
    data=json.loads(entry.read_text('utf-8'));p=Path(data['plan']).resolve()
    if not p.is_relative_to(root/'output/sound') or p.name!='sound-plan.json':
        raise ValueError('This sound review is unavailable.')
    plan=json.loads(p.read_text('utf-8'))
    if not plan.get('human_review'):raise ValueError('This result has no saved alternatives.')
    return p,plan
