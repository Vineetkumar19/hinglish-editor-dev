"""Read-only, video-only candidate contract. Never searches, renders or inserts."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Literal, TypedDict, NotRequired
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA = 'storylens.broll.video-candidates'
VERSION = 1
VIDEO_SUFFIXES = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.webm', '.mxf', '.mts', '.m2ts'}
FRAME_CHECKS = ('subject_visible', 'real_clear_footage', 'no_dominant_presenter', 'no_intrusive_overlay')


class Interval(TypedDict):
    start: float
    end: float


class MediaIdentity(TypedDict):
    path: str
    sha256: str
    bytes: int
    duration: float
    fps: str
    time_base: str
    width: int
    height: int
    rotation_degrees: int
    frame_duration: NotRequired[float]
    frame_timing: NotRequired[dict]


class SourceMapping(TypedDict):
    basis: str
    prepared_origin_in_original: float
    prepared_active: Interval
    original_active: Interval
    original_prepared_range: Interval
    original_ticks: dict[str, int]
    prepared_ticks: dict[str, int]


class ReceiptReference(TypedDict):
    project_path: str
    json_pointer: str
    sha256: str


class SourceCrop(TypedDict):
    space: Literal['upright_source_pixels']
    x: int
    y: int
    width: int
    height: int


class WindowCheck(TypedDict):
    state: Literal['bound', 'unbound']
    active_original_seconds: Interval
    crop: SourceCrop | None
    verdict_ref: ReceiptReference
    window_ref: ReceiptReference | None
    judge: str
    frame_checks: list[dict[str, bool]]
    producer_checks: NotRequired[dict[Literal['original','prepared'], ReceiptReference]]


class SourceCredit(TypedDict):
    provider: str
    local_media_scope: Literal['local_video', 'downloaded_excerpt']
    author: str
    title: str
    page_url: str
    license: str
    license_url: str


class OwnerChoice(TypedDict):
    state: Literal['unselected', 'selected', 'no_broll']
    candidate_id: str | None
    candidate_fingerprint: str | None
    slot_fingerprint: str
    source: Literal['none', 'owner']
    revision: int
    status: Literal['ready', 'blocked']
    issue: dict | None


class VideoCandidate(TypedDict):
    id: str
    candidate_id: str
    slot_id: str
    keyword_id: str
    kind: Literal['video']
    original: MediaIdentity
    prepared: MediaIdentity
    mapping: SourceMapping
    handles: dict
    check: WindowCheck
    source: SourceCredit
    fingerprint: str
    selectable: bool
    issues: list[dict]


class TimelineAnchor(TypedDict):
    spoken_seconds: Interval
    frames: dict[str, int]
    sequence_seconds: Interval
    fps: str
    timebase: Literal['sequence_frames']
    rounding: Literal['nearest_even']
    canvas: dict[str, int]
    quote: str


class KeywordSlot(TypedDict):
    id: str
    keyword_id: str
    slot_index: int
    keyword: str
    meaning: str
    anchor: TimelineAnchor
    fingerprint: str
    collection_state: Literal['pending','collecting','no_match','blocked','complete']
    candidates: list[VideoCandidate]
    rejected_candidates: list[dict]
    available_valid_candidates: int
    available_selectable_candidates: int
    omitted_by_cap: int
    choice: OwnerChoice


class CandidateManifest(TypedDict):
    schema: str
    version: int
    bank_id: str
    project_path: str
    content_format: Literal['long', 'short']
    per_keyword_cap: int
    collection_state: Literal['complete', 'saved_incomplete']
    timeline: dict
    slots: list[KeywordSlot]
    orphaned_choices: dict[str, OwnerChoice]


class CandidateContractError(ValueError):
    """Feature code plus shared plain-language presentation/secret redaction."""
    def __init__(self, code: str, message: str, details: str = ''):
        super().__init__(message)
        self.code, self.stderr = code, details

    def as_issue(self) -> dict:
        from hinglish_app.user_messages import problem
        shown = problem(str(self), feature='B-roll')
        return {**shown, 'code': self.code,
                'details': problem(self, feature='B-roll')['details']}


def _fail(code, message, details=''):
    raise CandidateContractError('broll_'+code, message, details)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _rational_text(value):
    return f'{value.numerator}/{value.denominator}'


def _number(value, label, *, minimum=0., positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail('manifest_invalid', f'Check {label}; it must be a finite number.')
    if value < minimum or positive and value <= minimum:
        _fail('manifest_invalid', f'Check {label}; it is outside the usable media range.')
    return float(value)


def _rate(value, label):
    try:
        if isinstance(value, bool): raise ValueError()
        rate = Fraction(str(value))
        if rate <= 0: raise ValueError()
        return rate
    except (ValueError, TypeError, ZeroDivisionError):
        _fail('manifest_invalid', f'Check {label}; a positive rational timebase is required.')


def _dimensions(value, label):
    if type(value) is not int or not 1 <= value <= 16384:
        _fail('manifest_invalid', f'Check {label}; valid video dimensions are required.')
    return value


def _json_file(path):
    try:
        result = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(result, dict): raise ValueError('Expected an object')
        return result
    except (OSError, ValueError) as error:
        _fail('bank_unavailable', 'Reopen a readable saved B-roll bank. Its original files are kept.', str(error))


def _quality_passed(verdict):
    if not isinstance(verdict,dict): return False
    frames=verdict.get('frame_checks')
    return (all(verdict.get(k) is True for k in
                ('passed','related','context_compatible','real_clear_footage','no_intrusive_text','identity_compatible'))
            and isinstance(frames,list) and len(frames)==3
            and all(isinstance(f,dict) and all(f.get(k) is True for k in FRAME_CHECKS) for f in frames))


def _mp4_edit_clock(path):
    """Read the single-track MP4 edit clock, never assume a millisecond epsilon."""
    def atoms(file,start,end):
        count=0
        while start<end:
            if end-start<8: raise ValueError('Incomplete MP4 atom')
            file.seek(start);header=file.read(8)
            size=int.from_bytes(header[:4],'big');width=8
            if size==1:
                extension=file.read(8)
                if len(extension)!=8: raise ValueError('Incomplete MP4 extended size')
                size=int.from_bytes(extension,'big');width=16
            if size==0:size=end-start
            count+=1
            if count>4096 or size<width or start+size>end: raise ValueError('Invalid MP4 atom bounds')
            yield header[4:],start+width,start+size
            start+=size
    def one(rows,kind):
        matches=[(a,b) for k,a,b in rows if k==kind]
        if len(matches)!=1: raise ValueError('Ambiguous MP4 timing')
        return matches[0]
    with Path(path).open('rb') as file:
        moov=one(list(atoms(file,0,Path(path).stat().st_size)),b'moov')
        children=list(atoms(file,*moov));a,b=one(children,b'mvhd')
        file.seek(a);header=file.read(min(40,b-a))
        if len(header)<4 or header[0] not in (0,1):raise ValueError('Unknown movie header')
        offset=20 if header[0]==1 else 12
        if len(header)<offset+4:raise ValueError('Incomplete movie clock')
        scale=int.from_bytes(header[offset:offset+4],'big')
        if not 1000<=scale<=1000000000:raise ValueError('Unsupported movie clock')
        trak=one(children,b'trak');edts=one(list(atoms(file,*trak)),b'edts')
        a,b=one(list(atoms(file,*edts)),b'elst');file.seek(a);edit=file.read(min(32,b-a))
        if len(edit)<8 or edit[0] not in (0,1) or int.from_bytes(edit[4:8],'big')!=1:
            raise ValueError('Unsupported MP4 edit list')
        width=8 if edit[0]==1 else 4;length=8+2*width+4
        if b-a!=length or len(edit)<length:raise ValueError('Incomplete MP4 edit')
        duration=int.from_bytes(edit[8:8+width],'big')
        media_time=int.from_bytes(edit[8+width:8+2*width],'big',signed=True)
        if duration<=0 or media_time<0 or edit[-4:]!=b'\x00\x01\x00\x00':
            raise ValueError('Unsupported MP4 edit rate')
        return Fraction(1,scale),duration


def _frame_extent(proof,fps,timebase,duration):
    """Accept only a complete CFR packet grid and its exact edit-list rounding."""
    if not isinstance(proof,dict) or proof.get('basis')!='mp4_cfr_packet_grid_and_edit_list':
        raise ValueError('No encoded frame timing proof')
    fields=('frame_count','packet_count','ticks_per_frame','first_pts','last_pts',
            'min_pts_step','max_pts_step','edit_duration_ticks','stream_duration_ticks')
    if any(type(proof.get(k)) is not int for k in fields):raise ValueError('Invalid frame timing integers')
    count=proof['frame_count'];ticks=Fraction(1,fps)/timebase
    clock=Fraction(proof['movie_time_base'])
    if (not 2<=count<=100000 or ticks.denominator!=1 or ticks<=0
            or proof['packet_count']!=count or Fraction(proof['base_rate'])!=fps
            or proof['ticks_per_frame']!=ticks or proof['first_pts']!=0
            or proof['last_pts']!=(count-1)*ticks
            or proof['min_pts_step']!=ticks or proof['max_pts_step']!=ticks
            or proof.get('packet_durations_match') is not True
            or clock<=0 or clock>Fraction(1,1000) or clock.numerator!=1):
        raise ValueError('Incomplete or nonconstant encoded frame grid')
    nominal=Fraction(count,fps);edit=proof['edit_duration_ticks'];stream=proof['stream_duration_ticks']
    if (edit!=int(nominal/clock) or stream!=round(edit*clock/timebase)
            or abs(duration-float(stream*timebase))>1e-9
            or not 0<nominal-Fraction(str(duration))<clock+timebase/2):
        raise ValueError('Stream duration is not the encoded edit-clock rounding')
    return float(nominal)


def _encoded_frame_timing(path,fps,timebase,duration,frame_count):
    """Bounded CPU packet inspection only for a shorter muxed duration."""
    try:
        if Path(path).suffix.lower() not in ('.mp4','.mov','.m4v'):return None
        if type(frame_count) is not int or not 2<=frame_count<=100000:return None
        clock,edit=_mp4_edit_clock(path)
        import av
        with av.open(str(path),mode='r') as container:
            if len(container.streams.video)!=1 or container.streams.audio:return None
            stream=container.streams.video[0];packets=[]
            for packet in container.demux(stream):
                if packet.pts is None:
                    if packet.size:raise ValueError('Missing video packet timestamp')
                    continue
                packets.append((packet.pts,packet.duration,packet.time_base))
                if len(packets)>frame_count:raise ValueError('Frame count differs from packet count')
            pts=sorted(p[0] for p in packets);steps=[b-a for a,b in zip(pts,pts[1:])]
            ticks=Fraction(1,fps)/timebase
            proof={'basis':'mp4_cfr_packet_grid_and_edit_list','frame_count':stream.frames,
                'packet_count':len(packets),'base_rate':str(stream.base_rate),'ticks_per_frame':int(ticks),
                'first_pts':pts[0],'last_pts':pts[-1],'min_pts_step':min(steps),'max_pts_step':max(steps),
                'packet_durations_match':all(d==ticks and tb==timebase for _,d,tb in packets),
                'movie_time_base':str(clock),'edit_duration_ticks':edit,'stream_duration_ticks':stream.duration}
            if stream.frames!=frame_count or stream.time_base!=timebase or stream.average_rate!=fps:
                raise ValueError('Video metadata changed during timing inspection')
            _frame_extent(proof,fps,timebase,duration)
            return proof
    except Exception:
        # Missing/ambiguous timing never justifies a longer trim. The ordinary
        # measured duration remains, and the candidate validator rejects excess.
        return None


def local_video_metadata(path: Path) -> dict:
    """CPU inspection only, including one decoded frame to reject bad containers.

    Lazy import: injected metadata fixtures never open a codec. No subprocess,
    network access, encoder, model or GPU context is used by this reader.
    """
    import av
    with av.open(str(path), mode='r') as container:
        if not container.streams.video: raise ValueError('No video stream')
        stream = container.streams.video[0]
        stream.thread_count = 1
        frame = next(container.decode(stream), None)
        if frame is None: raise ValueError('No decodable video frame')
        duration = float(stream.duration * stream.time_base) if stream.duration is not None else 0
        if duration <= 0: raise ValueError('Video-stream duration unavailable')
        rotation = int(stream.metadata.get('rotate', 0)) % 360
        # Unknown display-matrix rotation must be supplied by an upright-aware
        # reader instead of silently claiming the source crop is correct.
        if any('DISPLAYMATRIX' in str(side.type).upper() for side in frame.side_data):
            raise ValueError('Supply upright metadata for display-matrix video')
        width, height = stream.width, stream.height
        if rotation in (90, 270): width, height = height, width
        info={'duration': duration, 'fps': str(stream.average_rate or stream.base_rate),
                'time_base': str(stream.time_base), 'width': width, 'height': height,
                'rotation_degrees': rotation}
        fps=Fraction(info['fps'])
        if stream.frames and 1e-6<float(Fraction(stream.frames,fps))-duration<1/float(fps):
            proof=_encoded_frame_timing(path,fps,stream.time_base,duration,stream.frames)
            if proof is not None:info['frame_timing']=proof
        return info


def _media(path, reader, cache) -> MediaIdentity:
    path = Path(path).resolve()
    if path.suffix.lower() not in VIDEO_SUFFIXES:
        _fail('video_required', 'Choose an actual video file for B-roll; images and text cannot replace it.', str(path))
    if not path.is_file() or not path.stat().st_size:
        _fail('media_missing', 'Relink the missing B-roll video, then review this choice again. Saved decisions are kept.', str(path))
    if str(path) in cache:
        current=path.stat(); saved=cache[str(path)]
        if (current.st_size,current.st_mtime_ns)!=saved['stamp']:
            _fail('media_changed', 'Wait for this changing video to finish, then review its source again.', str(path))
        return dict(saved['identity'])
    before = path.stat()
    try:
        info = reader(path)
        if not isinstance(info, dict): raise ValueError('Metadata reader did not return a video record')
        duration = _number(info['duration'], 'video duration', positive=True)
        fps = _rate(info['fps'], 'video frame rate')
        timebase = _rate(info['time_base'], 'video timebase')
        if fps > 240 or timebase > 1: raise ValueError('Unsupported video rate/timebase')
        width = _dimensions(info['width'], 'video width'); height = _dimensions(info['height'], 'video height')
        rotation = info.get('rotation_degrees', 0)
        if type(rotation) is not int or rotation not in (0, 90, 180, 270): raise ValueError('Unknown upright orientation')
        frame_duration=_frame_extent(info['frame_timing'],fps,timebase,duration) if 'frame_timing' in info else None
        sha = hashlib.sha256()
        with path.open('rb') as file:
            while chunk := file.read(1024*1024): sha.update(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            _fail('media_changed', 'Wait for the B-roll file to finish changing, then review it again. Your choice is kept.', str(path))
    except CandidateContractError: raise
    except Exception as error:
        _fail('media_corrupt', 'Choose a readable video or relink its original. This candidate could not be inspected.', str(path)+'\n'+str(error))
    result = {'path': str(path), 'sha256': sha.hexdigest(), 'bytes': after.st_size,
              'duration': duration, 'fps': _rational_text(fps), 'time_base': _rational_text(timebase),
              'width': width, 'height': height, 'rotation_degrees': rotation}
    if frame_duration is not None:
        result.update(frame_duration=frame_duration,frame_timing=dict(info['frame_timing']))
    cache[str(path)] = {'identity':result,'stamp':(after.st_size,after.st_mtime_ns)}
    return result


def _public_url(value):
    try:
        url = urlsplit(str(value or ''))
        if url.scheme not in ('http', 'https') or not url.hostname: return ''
        sensitive = {'token','access_token','api_key','key','signature','sig','authorization'}
        query = [(key, val) for key, val in parse_qsl(url.query) if key.casefold() not in sensitive]
        return urlunsplit((url.scheme, url.hostname + (':'+str(url.port) if url.port else ''), url.path, urlencode(query), ''))
    except ValueError: return ''


def _validated_crop(crop, original, prepared):
    if not isinstance(crop,dict) or crop.get('space')!='upright_source_pixels':
        _fail('crop_invalid', 'Restore the checked source crop before choosing this video.')
    for key in ('x','y','width','height'):
        if type(crop.get(key)) is not int or crop[key] < (1 if key in ('width','height') else 0):
            _fail('crop_invalid', 'Check the saved B-roll crop; valid source pixel bounds are required.')
    if crop['x']+crop['width']>original['width'] or crop['y']+crop['height']>original['height']:
        _fail('crop_invalid', 'Check the saved B-roll crop; it extends outside the original video.')
    if abs(crop['width']/crop['height']-prepared['width']/prepared['height'])>2/crop['height']:
        _fail('crop_invalid', 'Check the saved crop-to-preview mapping; its aspect ratio does not match the prepared canvas.')
    return {key:crop[key] for key in ('space','x','y','width','height')}


def checked_window_receipt(original_file, prepared_file, *, prepared_origin_in_original,
                           prepared_source_in, active_duration, crop, verdict, media_reader=None):
    """Producer hook ONLY after a fresh actual check and preparation of that shot.

    This binds supplied tool evidence; it never performs a vision check itself.
    Never use it to backfill an interrupted/legacy bank from an old verdict.
    No file is written or rendered. Callers save the returned receipt with the
    new option they are already preparing, after the original check passed.
    """
    if not _quality_passed(verdict) or not isinstance(verdict.get('id'),str) or not verdict['id'].strip():
        _fail('quality_unverified', 'Finish a passing actual footage check before recording its video-window receipt.')
    reader=media_reader or local_video_metadata;cache={}
    original=_media(original_file,reader,cache);prepared=_media(prepared_file,reader,cache)
    origin=_number(prepared_origin_in_original,'prepared origin in original')
    start=_number(prepared_source_in,'prepared source-in')
    length=_number(active_duration,'checked active duration',positive=True)
    if origin+prepared.get('frame_duration',prepared['duration'])>original['duration']+1e-6 or start+length>prepared.get('frame_duration',prepared['duration'])+1e-6:
        _fail('trim_invalid', 'Check the actual original and prepared video bounds before saving this footage receipt.')
    return {'schema':'storylens.broll.checked-window','version':1,
            'candidate_id':verdict['id'],'verdict_sha256':digest(verdict),
            'source_sha256':original['sha256'],'prepared_sha256':prepared['sha256'],
            'start':origin+start,'end':origin+start+length,
            'crop':_validated_crop(crop,original,prepared)}


def _anchor(slot, timeline):
    if not isinstance(slot.get('text'),str):
        _fail('anchor_invalid', 'Restore the exact spoken words for this keyword before choosing B-roll.')
    start = _number(slot.get('start'), 'speech start'); end = _number(slot.get('end'), 'speech end')
    fps = Fraction(timeline['fps']); frames = {'start': round(Fraction(str(start))*fps), 'end': round(Fraction(str(end))*fps)}
    if end <= start or end > timeline['duration']+1e-7 or frames['end'] <= frames['start']:
        _fail('anchor_invalid', 'Check this keyword’s speech timing; it must stay inside the source timeline.')
    return {'spoken_seconds': {'start': start, 'end': end}, 'frames': frames,
            'sequence_seconds': {'start': float(frames['start']/fps), 'end': float(frames['end']/fps)},
            'fps': _rational_text(fps), 'timebase': 'sequence_frames', 'rounding': 'nearest_even',
            'canvas': {'width': timeline['width'], 'height': timeline['height']},
            'quote': str(slot.get('text', ''))}


def _candidate(option, slot, slot_id, keyword_id, position, option_position, anchor, project_file, reader, cache):
    candidate_id = option.get('id')
    if not isinstance(candidate_id,str) or not candidate_id.strip() or len(candidate_id) > 512:
        _fail('candidate_invalid', 'Choose a candidate with a stable saved video identity.')
    if option.get('kind') != 'video':
        _fail('video_required', 'Choose a video candidate for B-roll; no image or text substitution is allowed.')
    if not option.get('path') or not option.get('clip'):
        _fail('mapping_required', 'Relink both the original video and its prepared preview before choosing it.')
    original_path = Path(option['path'])
    if not original_path.is_absolute(): original_path = project_file.parent / original_path
    prepared_path = (project_file.parent / option['clip']).resolve()
    if not prepared_path.is_relative_to(project_file.parent):
        _fail('candidate_invalid', 'Choose a prepared video saved inside this B-roll bank.')
    original = _media(original_path, reader, cache); prepared = _media(prepared_path, reader, cache)
    if Fraction(prepared['fps']) != Fraction(anchor['fps']):
        _fail('mapping_required', 'Check the prepared preview frame rate before using its source trims.')
    if any(prepared[key]!=anchor['canvas'][key] for key in ('width','height')):
        _fail('mapping_required', 'Check the prepared preview dimensions; they differ from the checked timeline canvas.')
    start = _number(option.get('source_in'), 'prepared source-in')
    declared = _number(option.get('source_duration'), 'prepared available duration', positive=True)
    extent=prepared.get('frame_duration',prepared['duration'])
    if declared > prepared['duration']+1e-6 and ('frame_duration' not in prepared or abs(declared-extent)>1e-7):
        _fail('trim_invalid', 'Shorten this B-roll trim or relink its complete preview; its saved duration exceeds the file.')
    need = (anchor['frames']['end']-anchor['frames']['start'])/Fraction(anchor['fps'])
    need = float(need)
    if start+need > min(declared,extent)+1e-6:
        _fail('trim_invalid', 'Shorten this B-roll trim or choose a longer video; the active interval exceeds its preview.')
    if 'original_offset' in option:
        origin = _number(option['original_offset'], 'prepared origin in original')
        basis = 'explicit_original_offset'
    elif 'offset' in option:
        fps = Fraction(anchor['fps'])
        origin = float(round(Fraction(str(_number(option['offset'], 'original active offset')))*fps)/fps)-start
        basis = 'legacy_offset_quantized_to_sequence_rate'
    else:
        _fail('mapping_required', 'Restore the original-to-preview trim mapping before choosing this video.')
    if origin < -1e-7 or origin+declared > original['duration']+1e-6:
        _fail('trim_invalid', 'Check this B-roll mapping; its prepared range falls outside the original video.')
    origin = max(0., origin)
    active = {'start': origin+start, 'end': origin+start+need}
    checks = slot.get('checks', [])
    matches = [(i,c) for i,c in enumerate(checks) if isinstance(c,dict) and c.get('id')==candidate_id]
    if not matches:
        _fail('quality_unverified', 'Run the local footage check before choosing this saved candidate. No substitute will be inserted.')
    check_index, verdict = matches[-1]
    frames = verdict.get('frame_checks', [])
    if not _quality_passed(verdict):
        _fail('quality_rejected', 'Choose another video; the latest saved object, relevance, frame or watermark check did not pass.')
    receipt = option.get('checked_window')
    receipt_present = isinstance(receipt, dict)
    bound = (receipt_present and receipt.get('schema')=='storylens.broll.checked-window'
             and type(receipt.get('version')) is int and receipt['version']==1
             and receipt.get('candidate_id')==candidate_id and receipt.get('verdict_sha256')==digest(verdict)
             and all(receipt.get(key)==media['sha256'] for key,media in
                     (('source_sha256',original),('prepared_sha256',prepared))))
    crop = None
    if receipt_present:
        if 'schema' in receipt and (receipt['schema']!='storylens.broll.checked-window'
                or type(receipt.get('version')) is not int or receipt['version']!=1):
            _fail('check_version', 'Review this video with a supported footage-window receipt before choosing it.')
        if (('candidate_id' in receipt and receipt['candidate_id']!=candidate_id)
                or ('verdict_sha256' in receipt and receipt['verdict_sha256']!=digest(verdict))):
            _fail('check_changed', 'Review this candidate again; its window receipt no longer matches the latest footage check.')
        for key, media in (('source_sha256', original), ('prepared_sha256', prepared)):
            if key in receipt and receipt[key]!=media['sha256']:
                _fail('media_changed', 'Review this source and preview again; their bytes no longer match the checked video. Your saved choice is kept.')
        checked_start = _number(receipt.get('start'), 'checked original start')
        checked_end = _number(receipt.get('end'), 'checked original end')
        tolerance = .5/float(Fraction(anchor['fps']))+1e-7
        if checked_end <= checked_start or checked_end > original['duration']+1e-7 or abs(checked_start-active['start'])>tolerance or abs(checked_end-active['end'])>tolerance:
            _fail('check_window_invalid', 'Review the exact active B-roll interval again; it differs from the saved footage check.')
        crop = _validated_crop(receipt.get('crop'),original,prepared)
    issues = [] if bound else [CandidateContractError('broll_check_unbound',
        'Review this legacy video window before choosing it; its saved check is not bound to source bytes and crop.').as_issue()]
    mapping = {'basis': basis, 'prepared_origin_in_original': origin,
               'prepared_active': {'start': start, 'end': start+need},
               'original_active': active, 'original_prepared_range': {'start': origin, 'end': origin+declared},
               'original_ticks': {k: round(Fraction(str(v))/Fraction(original['time_base'])) for k,v in active.items()},
               'prepared_ticks': {k: round(Fraction(str(v))/Fraction(prepared['time_base'])) for k,v in {'start': start,'end': start+need}.items()}}
    check = {'state': 'bound' if bound else 'unbound', 'active_original_seconds': active,
             'crop': crop, 'verdict_ref': {'project_path': str(project_file),
                 'json_pointer': f'/slots/{position}/checks/{check_index}', 'sha256': digest(verdict)},
             'window_ref': {'project_path': str(project_file),
                 'json_pointer': f'/slots/{position}/options/{option_position}/checked_window',
                 'sha256': digest(receipt)} if receipt_present else None,
             'judge': str(verdict.get('judge','')), 'frame_checks': frames}
    if receipt_present and 'producer_version' in receipt:
        if type(receipt['producer_version']) is not int or receipt['producer_version']!=1:
            _fail('check_version','Review this shot with a supported source-and-preview producer receipt.')
        producer_refs={}
        for stage,media,interval,expected_crop in (
                ('original',original,active,crop),
                ('prepared',prepared,{'start':start,'end':start+need},
                 {'space':'upright_source_pixels','x':0,'y':0,'width':prepared['width'],'height':prepared['height']})):
            expected=receipt.get(stage+'_verdict_sha256')
            matches=[(i,c) for i,c in enumerate(checks) if isinstance(c,dict) and digest(c)==expected]
            if not matches:
                _fail('check_changed','Review this shot again; its actual source or prepared-video check is missing.')
            index,actual=matches[-1]
            if (not _quality_passed(actual) or actual.get('id')!=candidate_id or actual.get('producer_stage')!=stage
                    or actual.get('checked_media_path')!=media['path'] or actual.get('checked_media_sha256')!=media['sha256']
                    or actual.get('checked_crop')!=expected_crop
                    or any(abs(actual.get('checked_interval',{}).get(k,-999)-interval[k])>1e-7 for k in ('start','end'))):
                _fail('check_changed','Review the exact source and preview again; their actual check receipts differ from this shot.')
            producer_refs[stage]={'project_path':str(project_file),'json_pointer':f'/slots/{position}/checks/{index}','sha256':expected}
        if receipt.get('prepared_verdict_sha256')!=digest(verdict):
            _fail('check_changed','Review this shot again; its latest check is not the prepared-video approval.')
        check['producer_checks']=producer_refs
    result = {'id': slot_id+':candidate:'+candidate_id, 'candidate_id': candidate_id,
              'slot_id': slot_id, 'keyword_id': keyword_id, 'kind': 'video', 'original': original, 'prepared': prepared,
              'mapping': mapping, 'handles': {'availability_only': True,
                  'original': {'before': active['start'], 'after': original['duration']-active['end']},
                  'prepared': {'before': start, 'after': declared-start-need}},
              'check': check, 'source': {'provider': str(option.get('source','')),
                  'local_media_scope': 'downloaded_excerpt' if option.get('extraction') else 'local_video',
                  'author': str(option.get('author','')), 'title': str(option.get('title','')),
                  'page_url': _public_url(option.get('page_url')), 'license': str(option.get('license','')),
                  'license_url': _public_url(option.get('license_url'))},
              'selectable': bound, 'issues': issues}
    result['fingerprint'] = digest({'id': result['id'], 'slot_id':slot_id, 'keyword_id':keyword_id, 'original': original['sha256'],
        'prepared': prepared['sha256'], 'anchor': anchor, 'mapping': mapping, 'crop': crop})
    return result


def build_manifest(project_file, *, content_format, bank_id=None, media_reader: Callable | None = None,
                   previous=None, planned_slots=None) -> CandidateManifest:
    """Pure read/inspection. No project rewrites; previous is an owner sidecar.

    Missing check-to-bytes bindings remain visible but unselectable. A caller
    must never synthesize a checked_window to make an old bank appear verified.
    """
    from .candidate_selection import restore_choices
    if content_format not in ('long','short'):
        _fail('format_invalid', 'Choose Long form or Short form for the B-roll choice limit.')
    project_file = Path(project_file).resolve(); project = _json_file(project_file)
    if type(project.get('version')) is not int or project['version'] not in (1,2,3):
        _fail('bank_version', 'Reopen a supported saved B-roll bank; this project version is not understood.')
    if project.get('media_policy') not in (None, 'videos_only'):
        _fail('video_required', 'Choose a videos-only B-roll bank; images cannot be substituted.')
    t = project.get('timeline')
    if not isinstance(t,dict): _fail('manifest_invalid', 'Reopen the saved timeline metadata before choosing B-roll.')
    fps = _rate(t.get('fps'), 'sequence frame rate')
    if fps > 240: _fail('manifest_invalid', 'Check the sequence frame rate; this B-roll contract supports up to 240 fps.')
    timeline = {'name': str(t.get('name','')), 'fps': _rational_text(fps),
                'duration': _number(t.get('duration'), 'sequence duration', positive=True),
                'width': _dimensions(t.get('width'), 'sequence width'),
                'height': _dimensions(t.get('height'), 'sequence height')}
    bank_id = bank_id or digest(str(project_file))[:24]
    if not isinstance(bank_id,str) or not bank_id.strip() or len(bank_id)>256:
        _fail('manifest_invalid', 'Choose a stable B-roll bank identity.')
    saved = project.get('slots', [])
    if not isinstance(saved,list) or any(not isinstance(s,dict) for s in saved):
        _fail('manifest_invalid', 'Reopen a saved B-roll bank with readable keyword slots.')
    planned = planned_slots
    if planned is None:
        journal = project_file.parent.parent/'recovery.json'
        planned = []
        if journal.is_file():
            plans = _json_file(journal).get('plans', [])
            matching = [p for p in plans if p.get('folder')==project_file.parent.name]
            if matching:
                planned = [{**s, 'index': s.get('index',i),
                            'visual': s.get('visual') or s.get('moment',{}).get('visual','')}
                           for i,s in enumerate(matching[0].get('slots',[]))]
    if not isinstance(planned,list) or any(not isinstance(s,dict) for s in planned):
        _fail('manifest_invalid', 'Check the saved B-roll plan; keyword slots must be a list.')
    planned_indices=[s.get('index',i) for i,s in enumerate(planned)]
    if any(type(i) is not int or i<0 for i in planned_indices) or len(set(planned_indices))!=len(planned_indices):
        _fail('manifest_invalid', 'Restore unique planned keyword identities before choosing B-roll.')
    indices = [s.get('index',i) for i,s in enumerate(saved)]
    if any(type(i) is not int or i<0 for i in indices) or len(set(indices))!=len(indices):
        _fail('manifest_invalid', 'Restore unique saved keyword identities before choosing B-roll.')
    source_rows = [(i, s, False) for i,s in enumerate(saved)]
    for i,s in enumerate(planned):
        index=s.get('index',i)
        if type(index) is not int or index<0: _fail('manifest_invalid', 'Check the planned keyword identity.')
        if index not in indices: source_rows.append((None,{**s,'index':index},True));indices.append(index)
    cap=2 if content_format=='long' else 5; cache={}; rows=[]
    for position, slot, pending in source_rows:
        if not isinstance(slot.get('visual'),str) or not slot['visual'].strip():
            _fail('keyword_invalid', 'Restore this keyword’s intended physical subject before choosing B-roll.')
        slot_id = bank_id+':slot:'+str(slot.get('index',position))
        keyword_id = bank_id+':keyword:'+str(slot.get('index',position))
        anchor = _anchor(slot,timeline)
        row = {'id': slot_id, 'keyword_id':keyword_id, 'slot_index': slot.get('index',position),
               'keyword': str(slot.get('visual','')), 'meaning': str(slot.get('meaning','')),
               'anchor': anchor, 'fingerprint': digest({'anchor':anchor,'keyword':slot.get('visual','')}),
               'candidates': [], 'rejected_candidates': [], 'collection_state': 'pending'}
        options = slot.get('options', [])
        if not isinstance(options,list) or len(options)>200: _fail('manifest_invalid', 'Check this saved keyword’s video options; at most 200 saved candidates can be inspected.')
        counts = Counter(str(o.get('id','')) for o in options if isinstance(o,dict))
        for option_position, option in enumerate(options):
            try:
                if not isinstance(option,dict) or counts[str(option.get('id',''))]>1:
                    _fail('candidate_invalid', 'Restore a unique saved video identity before choosing this candidate.')
                row['candidates'].append(_candidate(option,slot,slot_id,keyword_id,position,option_position,anchor,project_file,
                                                     media_reader or local_video_metadata,cache))
            except CandidateContractError as error:
                row['rejected_candidates'].append({'candidate_id': option.get('id') if isinstance(option,dict) else None,
                                                   'issue': error.as_issue()})
            except (OSError,TypeError,ValueError,KeyError,OverflowError) as error:
                issue=CandidateContractError('broll_candidate_invalid',
                    'Review this saved candidate; its video metadata or trim record is unreadable.',str(error)).as_issue()
                row['rejected_candidates'].append({'candidate_id':option.get('id') if isinstance(option,dict) else None,'issue':issue})
        if not pending:
            if not slot.get('collection_complete'): row['collection_state']='collecting'
            elif not options: row['collection_state']='no_match'
            elif not any(c['selectable'] for c in row['candidates']): row['collection_state']='blocked'
            else: row['collection_state']='complete'
        row['available_valid_candidates']=len(row['candidates'])
        row['available_selectable_candidates']=sum(c['selectable'] for c in row['candidates'])
        rows.append(row)
    result = {'schema':SCHEMA, 'version':VERSION, 'bank_id':bank_id,
              'project_path':str(project_file), 'content_format':content_format, 'per_keyword_cap':cap,
              'collection_state':'saved_incomplete' if project.get('collecting') or any(r['collection_state'] in ('pending','collecting') for r in rows) else 'complete',
              'timeline':timeline, 'slots':rows}
    return restore_choices(result, previous)
