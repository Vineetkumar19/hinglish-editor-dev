"""Measured shot selection, beat grouping and conservative constant-speed retiming.

Local visual scores are evidence about exposure, detail and motion. They are not
semantic understanding or a guarantee of the editor's preferred creative take.
"""
from pathlib import Path
from fractions import Fraction
from collections import deque
import hashlib
import math
import os
import numpy as np
from hinglish_beats.detect import number

VIDEO_EXTENSIONS = {'.mp4','.mov','.mkv','.mxf','.avi','.webm','.mts','.m2ts','.m4v'}


def _content_fingerprint(path, cancel=None):
    """Exact bytes only; this does not recognize visually similar encodings."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if cancel is not None and cancel.is_set():
                raise RuntimeError('Cinematic reel cancelled')
            block = stream.read(1024*1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _source_groups(shots):
    """Merge path aliases, byte copies and explicitly supplied same-clip IDs."""
    parents, owners = list(range(len(shots))), {}

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for index, shot in enumerate(shots):
        keys = [('path', os.path.normcase(str(Path(shot['path']).resolve())))]
        if shot.get('source_id'):
            keys.append(('source', str(shot['source_id'])))
        content = shot.get('content_sha256') or shot.get('fingerprint')
        if content:
            keys.append(('content', str(content).lower()))
        for key in keys:
            if key in owners:
                parents[find(index)] = find(owners[key])
            else:
                owners[key] = index
    return [find(index) for index in range(len(shots))]


def rate(value):
    fps = number(value, 'Output FPS', 23, 61)
    choices = [Fraction(n) for n in (24,25,30,50,60)] + [Fraction(n*1000,1001) for n in (24,30,60)]
    found = min(choices, key=lambda r: abs(float(r)-fps))
    if abs(float(found)-fps) > .002: raise ValueError('Choose a supported output frame rate')
    return found


def inspect_shot(path, progress=lambda message: None, cancel=None):
    import av
    import cv2
    from hinglish_cut.media import video_rotation, orient_frame
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError('Choose local performance videos')
    rotation = video_rotation(path)
    samples, previous, first_time, next_sample = [], None, None, 0.
    with av.open(str(path)) as container:
        if not container.streams.video: raise ValueError(path.name + ' has no video')
        stream = container.streams.video[0]
        stream.codec_context.thread_count=2
        fps = float(stream.average_rate or stream.guessed_rate or 30)
        duration = float(stream.duration * stream.time_base) if stream.duration is not None else None
        if duration is not None and duration > 600: raise ValueError('Performance shots must each be shorter than 10 minutes')
        last = 0.
        for index, frame in enumerate(container.decode(stream)):
            if cancel is not None and cancel.is_set():raise RuntimeError('Cinematic reel cancelled')
            timestamp = float(frame.time) if frame.time is not None else index/fps
            if first_time is None: first_time = timestamp
            elapsed = timestamp - first_time
            last = elapsed + 1/fps
            if elapsed > 600: raise ValueError('Performance shot is too long; trim it first')
            if elapsed + .001 < next_sample: continue
            next_sample = elapsed + .25
            frame = orient_frame(frame, rotation)
            gray = frame.reformat(width=256, height=144, format='gray').to_ndarray()
            unit = gray.astype(np.float32)/255
            detail = min(1., math.log1p(cv2.Laplacian(gray,cv2.CV_64F).var())/8)
            exposure = max(0., 1-abs(float(unit.mean())-.48)*1.9)
            usable = float(((unit>.025)&(unit<.975)).mean())
            contrast = min(1., float(unit.std())/.18)
            quality = .35*detail + .25*exposure + .25*usable + .15*contrast
            motion = min(1., float(np.mean(np.abs(unit-previous)))*6) if previous is not None else 0.
            samples.append({'time':round(elapsed,6),'quality':quality,'motion':motion})
            previous = unit
    if not samples or last < .15: raise ValueError(path.name + ' is empty or too short')
    if max(s['quality'] for s in samples)<.2:raise ValueError(path.name+' has no clearly usable visible section')
    return {'path':str(path),'name':path.name,'fps':fps,'duration':last,
            'rotation':rotation,'samples':samples,'source_id':str(path),
            'content_sha256':_content_fingerprint(path,cancel)}


def boundaries(beat_plan, fps, budget, minimum, maximum):
    """Find a feasible salient-attack path; never invent an evenly spaced grid.

    A sliding maximum keeps the frame/shot-constrained search O(attacks * budget).
    Salience is measured onset strength, not downbeat or phrase understanding.
    """
    # A fractional last frame must not request music beyond the selected source.
    frames = math.floor(beat_plan['duration'] * fps + 1e-8)
    unique = {}
    for beat in beat_plan['beats']:
        frame = round((beat['timeline_seconds']-beat_plan.get('timeline_start',0))*fps)
        if 0 < frame < frames:
            if frame not in unique or beat['strength'] > unique[frame]['strength']:
                unique[frame] = {**beat,'frame':frame}
    candidates = sorted(unique.values(),key=lambda b:b['frame'])
    if not candidates: raise ValueError('No clear beat points in this range. Choose different music or a denser beat setting.')
    minimum_frames = max(1, math.ceil(minimum*fps-1e-8))
    maximum_frames = math.floor(maximum*fps+1e-8)
    positions = [0]+[b['frame'] for b in candidates]+[frames]
    strengths = [0.]+[float(b['strength']) for b in candidates]+[0.]
    previous = [-math.inf]*len(positions)
    previous[0] = 0.
    parents, feasible = [], None
    for count in range(1,min(budget,len(positions)-1,frames//minimum_frames)+1):
        scores, predecessors = [-math.inf]*len(positions), [-1]*len(positions)
        eligible, best = 0, deque()
        for index in range(1,len(positions)):
            while eligible < index and positions[eligible] <= positions[index]-minimum_frames:
                if math.isfinite(previous[eligible]):
                    # Earlier paths win equal-score ties, retaining deterministic edits.
                    while best and previous[best[-1]] < previous[eligible]:
                        best.pop()
                    best.append(eligible)
                eligible += 1
            while best and positions[best[0]] < positions[index]-maximum_frames:
                best.popleft()
            if best:
                scores[index] = previous[best[0]]+strengths[index]
                predecessors[index] = best[0]
        parents.append(predecessors)
        if math.isfinite(scores[-1]):
            feasible = count
        previous = scores
    if feasible is None:
        raise ValueError('Not enough usable beat points/shots for this music length. Add shots, use Strong density, shorten the music, or increase maximum shot length.')
    index, result = len(positions)-1, [frames]
    for count in range(feasible-1,-1,-1):
        index = parents[count][index]
        result.append(positions[index])
    result.reverse()
    return result


def best_window(shot, duration, target_motion, allow_slow, allow_fast, fps, used=(), minimum_quality=0.):
    samples = shot['samples']
    slow_limit = min(1.,fps/shot['fps'])
    speeds = [1.]
    if allow_slow:speeds += sorted(set(s for s in (max(.25,slow_limit),.5,.75) if slow_limit-.00001<=s<1))
    if allow_fast: speeds += [1.25,1.5,2.]
    best = None
    for speed in speeds:
        needed = duration*speed
        if needed > shot['duration']+.000001: continue
        starts = sorted(set([0.,max(0.,shot['duration']-needed-.002)] +
                            [s['time'] for s in samples if s['time']+needed <= shot['duration']-.001]))
        for start in starts:
            end = start+needed
            if any(start < b-.01 and end > a+.01 for a,b in used): continue
            window = [s for s in samples if start <= s['time'] < end]
            if not window: continue
            quality = float(np.mean([s['quality'] for s in window]))
            if quality < minimum_quality:
                continue
            motion = float(np.mean([s['motion'] for s in window]))
            peak = max(window,key=lambda s:s['motion'])
            # Favour action near a beat cut, then restore natural-speed preference.
            impact = max(0.,1-(peak['time']-start)/max(needed,.01))
            score = quality*.72 + (1-abs(min(1.,motion*speed)-target_motion))*.22 + impact*.06
            score -= abs(math.log(speed))*.045
            value = {'source_in':round(start,6),'source_out':round(end,6),'speed':speed,
                     'score':round(score,6),'quality':round(quality,6),'motion':round(motion,6),
                     'reason':'Best measured window for exposure, detail and movement; matched to this beat interval.'}
            if best is None or score>best['score']: best=value
    return best


def assemble(beat_plan, shots, options):
    fps = float(rate(options.get('fps',beat_plan['fps'])))
    if abs(beat_plan.get('speed',1)-1)>.00001: raise ValueError('Cinematic Reels uses normal-speed music')
    music_duration = number(beat_plan['duration'],'Music range',.2,600)
    music_in = number(beat_plan['source_in'],'Music in point',0,86400)
    music_out = number(beat_plan.get('source_out',music_in+music_duration),'Music out point',music_in,music_in+600)
    if music_in+music_duration > music_out+1e-6:
        raise ValueError('The music range extends beyond its selected out point. Choose a valid music range.')
    pace = options.get('pace','cinematic')
    if pace not in ('cinematic','balanced','action'): raise ValueError('Choose Cinematic, Balanced or Action pace')
    minimum = number(options.get('min_shot',{'cinematic':1.8,'balanced':1.0,'action':.5}[pace]),'Minimum shot length',.25,15)
    maximum = number(options.get('max_shot',6),'Maximum shot length',minimum,30)
    reuse = options.get('allow_reuse',False) is True
    requested = number(options.get('max_shots',len(shots)) or len(shots),'Maximum shots',1,200)
    if requested!=int(requested):raise ValueError('Maximum shots must be a whole number')
    requested=int(requested)
    groups = _source_groups(shots)
    budget = requested if reuse else min(requested,len(set(groups)))
    cuts = boundaries(beat_plan,fps,budget,minimum,maximum)
    minimum_quality = number(options.get('min_quality',.2),'Minimum measured shot quality',0,1)
    chosen, used, used_groups = [], {}, set()
    all_beats = beat_plan['beats']
    # Reserve footage for difficult long intervals before fitting the short ones.
    for start,end in sorted(zip(cuts,cuts[1:]),key=lambda pair:-(pair[1]-pair[0])):
        duration = (end-start)/fps
        local = [b['strength'] for b in all_beats if start/fps <= b['timeline_seconds']-beat_plan.get('timeline_start',0) < end/fps]
        strength = max(local,default=.4)
        target_motion = min(1.,{'cinematic':.2,'balanced':.4,'action':.65}[pace]+strength*.2)
        candidates = []
        for shot,group in zip(shots,groups):
            if not reuse and group in used_groups: continue
            window = best_window(shot,duration,target_motion,options.get('allow_slow',True) is True,
                                 options.get('allow_fast',True) is True,fps,used.get(group,()),minimum_quality)
            if window:
                # Prefer a different clip to repeating the previous source.
                penalty = .12 if chosen and chosen[-1]['path']==shot['path'] else 0.
                candidates.append((window['score']-penalty,shot,window,group))
        if not candidates:
            raise ValueError(f'Cannot fill the {duration:.2f}s beat interval at {start/fps:.2f}s with usable measured-quality footage without repeating or freezing. Add clearer/longer shots, allow retiming/reuse, or shorten the music.')
        _,shot,window,group = max(candidates,key=lambda item:item[0])
        chosen.append({**window,'path':shot['path'],'name':shot['name'],'source_fps':shot['fps'],
                       'source_id':shot.get('source_id',shot['path']),
                       'content_sha256':shot.get('content_sha256') or shot.get('fingerprint'),
                       'start_frame':start,'end_frame':end,'duration_frames':end-start,'beat_strength':strength})
        used_groups.add(group);used.setdefault(group,[]).append((window['source_in'],window['source_out']))
    chosen.sort(key=lambda shot:shot['start_frame'])
    split_music = options.get('split_music',True) is True
    music_ranges = list(zip(cuts,cuts[1:])) if split_music else [(0,cuts[-1])]
    return {'version':1,'kind':'cinematic_reel','fps':str(rate(fps)),'frames':cuts[-1],
            'duration':cuts[-1]/fps,'music':{'path':beat_plan['path'],'source_in':music_in,
                'source_out':music_in+cuts[-1]/fps,'continuous':True,'speed':1.,
                'ranges':[{'start_frame':a,'end_frame':b,'source_in':music_in+a/fps,
                           'source_out':music_in+b/fps} for a,b in music_ranges]},
            'beat_frames':sorted(set(round((b['timeline_seconds']-beat_plan.get('timeline_start',0))*fps) for b in all_beats if 0 <= b['timeline_seconds']-beat_plan.get('timeline_start',0) < cuts[-1]/fps)),
            'cuts':cuts,'shots':chosen,'pace':pace,'split_music':split_music,
            'selection_method':'Local measured visual ranking, not semantic LLM judgement',
            'selection_limits':'Exposure/detail/motion and measured attack salience; not semantic favourites, downbeats or phrase understanding. Content deduplication uses exact bytes or supplied same-clip IDs, not visual similarity.',
            'effects':[],'warnings':[]}
