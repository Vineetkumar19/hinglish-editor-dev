"""Observed gaming/Shorts provenance, never a selector or rendering substitute.

Exact v1 supports zero-origin CFR H.264 originals at the same frame rate
as the gaming export, with frame-aligned -ss/-t boundaries. Other transformations
remain explicitly unavailable. It does NOT guess FFmpeg resampling provenance.
Prepared-part access-unit hashes are matched in presentation order against the
actual concatenated file, including inserted meme parts and timestamp gaps.
Short composition follows the existing source_frames sampler using its ACTUAL
frame plan and the observed highlights presentation clock, not speech seconds.

Complete means structurally observed provenance, never creative approval or
local-agent acceptance. File observation/hashing adds I/O in future producer
runs; no long-input throughput or constant-memory guarantee is made. Packet
evidence is bounded, no pixel frames/audio arrays are decoded here. Legacy
projects are read-only and receive no invented mapping or approval.
"""
from bisect import bisect_right
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import uuid


class LineageError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise LineageError(code, message)


def unavailable(code, message):
    return dict(schema_version=1, state='unavailable', code=code, message=message,
                approval='not_asserted', queue_manifest=None)


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _int(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _r(value):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        if not _int(value[0]) or not _int(value[1], 1):
            raise ValueError('Invalid rational time')
        return Fraction(*value)
    if isinstance(value, bool) or not isinstance(value, (str, int, Fraction)):
        raise ValueError('Use rational or decimal-string times')
    return Fraction(value)


def _pair(value):
    return [value.numerator, value.denominator]


def _clock(evidence, *, packets=False, cfr=False):
    if evidence.get('codec') != 'h264':
        _fail('unsupported_video_clock', 'Exact lineage v1 requires observed H.264 access-unit timing.')
    fps, unit = _r(evidence['fps']), _r(evidence['timebase'])
    pts = evidence['pts']
    if (fps <= 0 or unit <= 0 or not isinstance(pts, list) or not pts
            or any(not _int(p) for p in pts) or any(a >= b for a,b in zip(pts,pts[1:]))):
        _fail('unsupported_video_clock', 'Video timestamps are absent, repeated or unordered.')
    if cfr and any((b-a)*unit != 1/fps for a,b in zip(pts,pts[1:])):
        _fail('unsupported_video_clock', 'This source has gaps or rate conversion; no exact original-frame map was inferred.')
    if packets and (not isinstance(evidence.get('packets'), list)
                    or len(evidence['packets']) != len(pts)
                    or any(not _sha(p) for p in evidence['packets'])):
        _fail('unsupported_video_clock', 'Missing observed access-unit identities.')
    return fps, unit, pts


def source_record(sha256, evidence):
    try:
        if not _sha(sha256): raise ValueError('Invalid source hash')
        fps, unit, pts = _clock(evidence, cfr=True)
        if pts[0] != 0:
            _fail('source_clock_unrepresentable', 'Exact lineage v1 requires a zero-origin original.')
        return dict(id='sha256:'+sha256, sha256=sha256, state='complete',
                    duration_frames=len(pts), timebase=_pair(1/fps), cfr_proven=True)
    except (KeyError, TypeError, ValueError) as error:
        return unavailable(getattr(error,'code','source_clock_unrepresentable'), str(error))


def _validate_parent(parent):
    if not isinstance(parent, dict) or parent.get('state') != 'complete':
        _fail('parent_lineage_unavailable', 'The completed highlights have no verified original-source lineage.')
    unsigned = {k:v for k,v in parent.items() if k != 'mapping_version'}
    if parent.get('mapping_version') != 'gaming-map-v1:'+_hash(unsigned):
        _fail('parent_lineage_changed', 'The saved highlights mapping changed; it cannot identify the original edit.')
    return parent


def build_highlights(root, parts, output_sha256, output_evidence):
    """Pure observed-part contract. Unsupported evidence returns unavailable."""
    try:
        if root.get('state') != 'complete' or root.get('cfr_proven') is not True:
            _fail('source_clock_unrepresentable', 'Original-source frame timing is not verified.')
        if not _sha(output_sha256) or not parts: raise ValueError('Missing completed highlights evidence')
        fps, unit, pts = _clock(output_evidence, packets=True)
        if _r(root['timebase']) != 1/fps:
            _fail('source_clock_unrepresentable', 'Exact lineage requires the original and highlight frame rates to match.')
        encoded, segments, cursor = [], [], 0
        for item in parts:
            part_fps, _, part_pts = _clock(item['evidence'], packets=True, cfr=True)
            if part_fps != fps: _fail('part_frame_mismatch','Prepared-part rates differ from the completed highlights.')
            frames = len(part_pts)
            start, length = _r(item['source_in']), _r(item['requested_duration'])
            if start < 0 or length <= 0: raise ValueError('Invalid source trim')
            kind = item['kind']
            if kind not in ('root','insert') or not _sha(item['source_sha256']):
                raise ValueError('Unknown part origin')
            segment = dict(start_frame=cursor, end_frame=cursor+frames, kind=kind,
                           source_sha256=item['source_sha256'], source_in=_pair(start),
                           requested_duration=_pair(length), part_packet_sha256=_hash(item['evidence']['packets']))
            if kind == 'root':
                if item['source_sha256'] != root['sha256']: _fail('source_identity_changed','The rendered part refers to another original source.')
                first, count = start*fps, length*fps
                if first.denominator != 1 or count.denominator != 1:
                    _fail('source_trim_unrepresentable','The existing trim is not on original/output frame boundaries; no exact map was guessed.')
                if frames != count: _fail('part_frame_mismatch','Actual prepared frames differ from the requested root interval.')
                if first+frames > root['duration_frames']: _fail('source_bounds','The original-source interval extends beyond its measured frames.')
                segment['source_start_frame'] = int(first)
            encoded.extend(item['evidence']['packets'])
            segments.append(segment)
            cursor += frames
        if encoded != output_evidence['packets']:
            _fail('concat_packet_mismatch','The actual highlights access-unit order/count differs from the prepared parts.')
        record = dict(schema_version=1, state='complete', approval='not_asserted',
                      root_source=deepcopy(root), highlights=dict(id='sha256:'+output_sha256,
                          sha256=output_sha256, state='complete', duration_frames=len(pts), fps=_pair(fps)),
                      clock=dict(fps=_pair(fps),timebase=_pair(unit),pts=list(pts)), segments=segments,
                      evidence_basis='Observed stream-copy access units; same-rate, frame-aligned root trims')
        record['mapping_version'] = 'gaming-map-v1:'+_hash(record)
        return record
    except (KeyError, TypeError, ValueError) as error:
        return unavailable(getattr(error,'code','lineage_unrepresentable'), str(error))


def _sample_indices(clock, frame_plan, out_fps):
    """Same selection/hold decisions as shorts.render.source_frames, no pixels."""
    times = [float(p*_r(clock['timebase'])) for p in clock['pts']]
    half = .5/float(_r(clock['fps']))
    selected = []
    for first, count in frame_plan:
        if not _int(first) or not _int(count,1): raise ValueError('Invalid rendered frame plan')
        start = Fraction(first)/out_fps
        target, k, last = float(start), 0, None
        # Seek backward only affects work, not the latest frame before target.
        begin = max(0, bisect_right(times, float(start)-.5)-1)
        for index in range(begin,len(times)):
            timestamp = times[index]
            if timestamp < target-half:
                last=index
                continue
            while k<count and timestamp >= target-half:
                selected.append(index if timestamp <= target+half or last is None else last)
                k+=1
                target=float(start)+k/float(out_fps)
            last=index
            if k>=count: break
        while k<count and last is not None:
            selected.append(last)
            k+=1
    return selected


def compose_short(parent, frame_plan, fps, short_sha256, output_evidence):
    """Pure composition of measured parent frames into queue-compatible roots."""
    try:
        parent = _validate_parent(parent)
        fps = _r(fps)
        observed_rate, _, pts = _clock(output_evidence,cfr=True)
        if not _sha(short_sha256): raise ValueError('Invalid short hash')
        if fps <= 0 or observed_rate != fps or len(pts) != sum(count for _,count in frame_plan):
            _fail('short_frame_mismatch','Actual output frames/rate differ from the renderer’s saved frame plan.')
        selected = _sample_indices(parent['clock'],frame_plan,fps)
        if len(selected) != len(pts): _fail('short_frame_mismatch','The input cannot supply the renderer’s actual frame plan.')
        ends = [s['end_frame'] for s in parent['segments']]
        moments, inserts = [], []
        root = parent['root_source']
        for output_frame,index in enumerate(selected):
            location=bisect_right(ends,index)
            segment=parent['segments'][location]
            if not segment['start_frame'] <= index < segment['end_frame']: raise ValueError('Unmapped parent frame')
            if segment['kind']=='insert':
                inserts.append(dict(short_frame=output_frame,highlight_frame=index,
                                    source_sha256=segment['source_sha256'],part_frame=index-segment['start_frame']))
                continue
            first=segment['source_start_frame']+index-segment['start_frame']
            if not 0 <= first < root['duration_frames']: _fail('source_bounds','A composed source frame is out of bounds.')
            if moments and moments[-1]['end_frame']==first:
                moments[-1]['end_frame']=first+1
            else:
                moments.append(dict(source_id=root['id'],source_sha256=root['sha256'],
                                    start_frame=first,end_frame=first+1,timebase=list(root['timebase'])))
        if not moments: _fail('no_original_source_frames','This output contains only inserted material, not an original-stream Short.')
        manifest=dict(asset_id='sha256:'+short_sha256,state='complete',content_sha256=short_sha256,
                      root_source={k:root[k] for k in ('id','sha256','state','duration_frames','timebase')},
                      highlights=dict(id=parent['highlights']['id'],version=parent['mapping_version'],state='complete',
                                      source_id=root['id'],source_sha256=root['sha256']),
                      mapping_version=parent['mapping_version'],source_moments=moments)
        result=dict(schema_version=1,state='complete',approval='not_asserted',
                    short_sha256=short_sha256,output_fps=_pair(fps),highlight_frames=selected,
                    insert_frames=inserts,queue_manifest=manifest)
        result['mapping_version']='gaming-short-map-v1:'+_hash(result)
        return result
    except (KeyError, TypeError, ValueError, IndexError) as error:
        return unavailable(getattr(error,'code','lineage_unrepresentable'),str(error))


def _stamp(path):
    stat=Path(path).stat()
    return dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns,ctime_ns=stat.st_ctime_ns)


def media_stamp(path):
    """Capture an insertion's file state before the existing render reads it."""
    return _stamp(path)


def _cancel(cancel):
    if cancel is not None and cancel.is_set(): _fail('lineage_cancelled','Lineage observation was cancelled; no completed mapping was asserted.')


def file_identity(path, cancel=None):
    """Whole-byte identity, streamed and guarded against ordinary file changes."""
    _cancel(cancel)
    before=_stamp(path)
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024*1024):
            _cancel(cancel)
            digest.update(block)
    if _stamp(path)!=before: _fail('media_changed','Media changed during identity measurement.')
    return dict(sha256=digest.hexdigest(),stamp=before)


def observe_video(path, cancel=None, *, payloads=True, max_packets=2000000):
    """Demux H.264 access units/PTS, never decode images or run an encoder."""
    import av
    values=[]
    with av.open(str(path)) as container:
        if len(container.streams.video)!=1: _fail('unsupported_video_clock','Select a single-video-stream completed file.')
        stream=container.streams.video[0]
        fps=stream.base_rate or stream.average_rate
        if not fps or stream.codec_context.name!='h264': _fail('unsupported_video_clock','Exact lineage v1 requires H.264 frame timing.')
        for packet in container.demux(stream):
            _cancel(cancel)
            if not packet.size: continue
            if packet.pts is None: _fail('unsupported_video_clock','A coded access unit has no presentation timestamp.')
            values.append((packet.pts,hashlib.sha256(bytes(packet)).hexdigest() if payloads else None))
            if len(values)>max_packets: _fail('lineage_observation_limit','Lineage packet evidence exceeded its bounded limit; no exact mapping was asserted.')
        values.sort(key=lambda p:p[0])
        result=dict(codec='h264',fps=_pair(Fraction(fps)),timebase=_pair(Fraction(stream.time_base)),
                    pts=[p[0] for p in values])
        if payloads: result['packets']=[p[1] for p in values]
        return result


def _observation_failure(error):
    return unavailable(getattr(error,'code','lineage_observation_failed'),str(error))


def capture_source(path, cancel=None):
    try:
        identity=file_identity(path,cancel)
        record=source_record(identity['sha256'],observe_video(path,cancel,payloads=False))
        if _stamp(path)!=identity['stamp']: _fail('media_changed','Original media changed while observing its clock.')
        return dict(state=record['state'],record=record,path=str(Path(path).resolve()),verification=identity)
    except (OSError,ValueError,RuntimeError) as error:
        return _observation_failure(error)


def capture_highlights(source_context, parts, output_path, cancel=None):
    try:
        if source_context.get('state')!='complete':
            return unavailable('source_clock_unrepresentable','The original source does not have an exact supported frame map.')
        source=Path(source_context['path'])
        if file_identity(source,cancel)!=source_context['verification']:
            _fail('source_identity_changed','The original stream changed during highlights production.')
        prepared=[]
        for item in parts:
            _cancel(cancel)
            origin=Path(item['source_path']).resolve()
            if item['kind']=='root':
                if origin!=source.resolve(): _fail('source_identity_changed','A prepared part refers to another source.')
                sha=source_context['record']['sha256']
            else:
                identity=file_identity(origin,cancel)
                if identity['stamp']!=item.get('source_stamp'):
                    _fail('insert_media_changed','An inserted asset changed while its prepared part was being produced.')
                sha=identity['sha256']
            prepared.append(dict(kind=item['kind'],source_sha256=sha,
                                 source_in=str(item['source_in']),requested_duration=str(item['requested_duration']),
                                 evidence=observe_video(item['rendered_path'],cancel)))
        identity=file_identity(output_path,cancel)
        evidence=observe_video(output_path,cancel)
        if _stamp(output_path)!=identity['stamp']: _fail('media_changed','Highlights changed during observation.')
        return build_highlights(source_context['record'],prepared,identity['sha256'],evidence)
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
        return _observation_failure(error)


def write_new_record(path, record):
    """Atomically create a new sidecar; never replace an earlier project/receipt."""
    path=Path(path)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        with temporary.open('x',encoding='utf-8') as stream:
            json.dump(record,stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            stream.flush()
            os.fsync(stream.fileno())
        if os.name=='nt':
            os.rename(temporary,path)  # Windows rename fails if destination exists
        else:
            os.link(temporary,path)  # exclusive create on POSIX
    finally:
        temporary.unlink(missing_ok=True)


def load_highlights(path, record=None):
    """Verify a fresh completed parent once per run; old projects are not upgraded."""
    try:
        path=Path(path).resolve()
        if record is None:
            sidecar=path.parent/'gaming-lineage.json'
            if not sidecar.is_file(): return unavailable('parent_lineage_unavailable','This source predates verified gaming lineage; no mapping was invented.')
            record=json.loads(sidecar.read_text('utf-8'))
        _validate_parent(record)
        identity=file_identity(path)
        if identity['sha256']!=record['highlights']['sha256']:
            _fail('parent_media_changed','The highlights bytes differ from the completed parent identity.')
        return dict(state='complete',record=deepcopy(record),verification=identity,path=str(path))
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
        return _observation_failure(error)


def capture_short(context, source, target, frame_plan, fps, cancel=None):
    try:
        if not context or context.get('state')!='complete':
            return unavailable('parent_lineage_unavailable','No supported completed highlights mapping was supplied; this Short remains unavailable for provenance-based queueing.')
        if (Path(source).resolve()!=Path(context['path']).resolve()
                or _stamp(source)!=context['verification']['stamp']
                or context['verification']['sha256']!=context['record']['highlights']['sha256']):
            _fail('parent_media_changed','The highlights changed after verification; no child source mapping was asserted.')
        identity=file_identity(target,cancel)
        evidence=observe_video(target,cancel)
        if (_stamp(source)!=context['verification']['stamp'] or _stamp(target)!=identity['stamp']):
            _fail('parent_media_changed','Media changed during Short provenance observation.')
        return compose_short(context['record'],frame_plan,fps,identity['sha256'],evidence)
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
        return _observation_failure(error)
