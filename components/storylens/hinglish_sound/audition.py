"""Explicit, manifest-bound raw source-window auditions; no winner or full mix.

Suite code owns authentication, job ownership, serving, UI and native import.
This callable accepts a saved output manifest and its independently retained
hash, never a client-supplied candidate object or arbitrary source path.
"""
from contextlib import contextmanager
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import wave

from .recommendation_runtime import CancellationToken, RecommendationCancelled, write_json_atomic
from .recommendations import verify_candidate_source, _candidate_id, _credits

VERSION=1
MAX_SECONDS=30.
MAX_SOURCE_BYTES=256*1024*1024
MAX_MANIFEST_BYTES=16*1024*1024
ENCODER_REVISION='pyav-pcm16-native-mono-stereo-48000-v1'


def _digest(path,token):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        while block:=source.read(1024*1024): token.check();digest.update(block)
    return digest.hexdigest()


def _load_manifest(path,expected,token):
    token.check()
    if path.stat().st_size>MAX_MANIFEST_BYTES: raise ValueError('This saved recommendation is too large. Keep it and create a smaller review job.')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('This recommendation changed. Refresh the sound choices before listening.')
    value=json.loads(raw)
    if (not isinstance(value,dict) or value.get('schema')!='storylens.sound-recommendations' or
        value.get('version')!=1 or value.get('status')!='ready'):
        raise ValueError('Select a completed, verified sound recommendation before listening.')
    return value


def _selection(manifest,candidate_id):
    found=[]
    for group in manifest.get('groups',[]):
        for candidate in group.get('candidates',[]):
            if candidate.get('id')==candidate_id: found.append((group,candidate))
    if len(found)!=1: raise ValueError('Select one unique sound candidate from this saved recommendation.')
    group,candidate=found[0]
    if (group.get('decision')==-1 or group.get('status')!='candidates' or
        group.get('kind') not in ('music','sfx') or candidate.get('kind')!=group['kind'] or
        candidate.get('group_id')!=group.get('id')):
        raise ValueError('This sound is no longer an available choice. Refresh the recommendation.')
    source=candidate['source']; timeline=candidate['timeline']
    if candidate_id!=_candidate_id(manifest['fingerprint'],group['id'],source,timeline):
        raise ValueError('The selected sound identity changed. Refresh this recommendation.')
    a,b=source['in'],source['out'];t,end=timeline['start'],timeline['end']
    seconds=manifest['timeline']['duration']
    if not all(type(x) in (int,float) and math.isfinite(x) for x in (a,b,t,end,seconds)):
        raise ValueError('Check the saved sound window; its times must be finite numbers.')
    if not 0<=t<end<=seconds or not 0<=a<b or abs((b-a)-(end-t))>1e-6:
        raise ValueError('Check this sound window; it must fit the saved timeline and recording.')
    if b-a>MAX_SECONDS:
        raise ValueError('This exact sound window is longer than the 30-second audition limit. Choose a shorter reviewed window first.')
    if not group['timeline']['start']<=t<end<=group['timeline']['end']:
        raise ValueError('The selected sound moved outside its saved group. Refresh this recommendation.')
    return copy.deepcopy(candidate)


def _output_facts(path,duration,token):
    token.check()
    # Header and actual decoded byte count are both checked. A plausible WAV
    # header alone cannot turn a truncated/incomplete prepared file into ready.
    if not path.is_file() or path.is_symlink() or path.stat().st_size>int(MAX_SECONDS*192000)+1048576:
        raise ValueError('The prepared audition is missing or invalid. Keep it for repair; no new preview was substituted.')
    try:
        with wave.open(str(path),'rb') as audio:
            frames=audio.getnframes();rate=audio.getframerate();channels=audio.getnchannels();width=audio.getsampwidth()
            if audio.getcomptype()!='NONE' or width!=2 or channels not in (1,2) or not 8000<=rate<=96000:
                raise ValueError('The audition must be a supported PCM16 audio preview.')
            if not frames or abs(frames/rate-duration)>1/rate+1e-7:
                raise ValueError('The prepared audition duration does not match the selected sound window.')
            count=0
            while block:=audio.readframes(65536): token.check();count+=len(block)
            if count!=frames*channels*width: raise ValueError('The prepared audition audio is incomplete.')
    except (wave.Error,EOFError) as error:
        raise ValueError('The prepared audition is not readable audio. Keep saved progress and retry after the encoder is repaired.') from error
    return dict(path=str(path),sha256=_digest(path,token),bytes=path.stat().st_size,
                frames=frames,sample_rate=rate,channels=channels,duration=frames/rate,format='PCM16 WAV')


def _cached(path,preview,binding,token):
    if not path.exists() and not preview.exists(): return None
    if not path.is_file() or path.is_symlink() or not preview.is_file():
        raise ValueError('A previous audition is incomplete. Keep its files for repair before retrying.')
    if path.stat().st_size>1024*1024: raise ValueError('The saved audition receipt is invalid. Keep it for repair.')
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('binding')!=binding or value.get('status')!='ready':
        raise ValueError('The saved audition no longer matches this sound choice. Refresh the recommendation.')
    expected=dict(schema='storylens.sound-audition',version=VERSION,id=path.stem,
        manifest_sha256=binding['manifest_sha256'],candidate_id=binding['candidate_id'],
        source=binding['source'],credits=binding['credits'],proposed_timeline=binding['timeline'],
        proposed_level_db=binding['proposed_level_db'],proposed_processing=binding['processing'],
        applied_gain_db=0.,applied_processing={},raw_source_audition=True,full_mix_rendered=False,
        native_imported=False,test_encoder_used=binding['test_encoder_used'],local_agent_acceptance=False)
    if any(value.get(key)!=item for key,item in expected.items()):
        raise ValueError('The saved audition receipt changed. Refresh the sound choice before listening.')
    facts=_output_facts(preview,binding['source']['out']-binding['source']['in'],token)
    if value.get('preview')!=facts:
        raise ValueError('The saved audition audio changed. Keep it for repair; it was not silently replaced.')
    return dict(value,cache_hit=True)


@contextmanager
def _owned_work(auditions,key):
    lock=auditions/(key+'.lock')
    try: handle=lock.open('x',encoding='utf-8')
    except FileExistsError:
        raise ValueError('This audition is already being prepared or was interrupted. Check its saved progress before retrying.') from None
    temporary=None
    try:
        with handle: handle.write('Owned audition preparation\n')
        temporary=Path(tempfile.mkdtemp(prefix='.'+key+'-',dir=auditions)).resolve()
        if not temporary.is_relative_to(auditions): raise ValueError('The audition workspace moved outside its job.')
        yield temporary
    finally:
        # Only the directory created by this invocation may be removed. Verify
        # its final absolute location before recursive cleanup on Windows.
        if temporary is not None and temporary.is_relative_to(auditions) and temporary.parent==auditions:
            shutil.rmtree(temporary)
        lock.unlink(missing_ok=True)


def _snapshot(source,destination,expected,token):
    source=Path(source)
    if source.stat().st_size>MAX_SOURCE_BYTES:
        raise ValueError('This library recording exceeds the bounded audition input limit. Prepare a smaller reviewed source first.')
    digest=hashlib.sha256();size=0
    with source.open('rb') as original,destination.open('xb') as snapshot:
        while block:=original.read(1024*1024):
            token.check();size+=len(block)
            if size>MAX_SOURCE_BYTES: raise ValueError('The source recording grew beyond the audition limit. Refresh its recommendation.')
            digest.update(block);snapshot.write(block)
        snapshot.flush();os.fsync(snapshot.fileno())
    if digest.hexdigest()!=expected:
        raise ValueError('The library sound changed during preparation. Refresh this recommendation.')


def _encode_window(source,output,start,end,token):
    """Bounded audio-only PyAV decode/PCM write; never a full score/video render.

    Timestamped samples determine the exact source window. Missing timestamps or
    incomplete sample coverage stop instead of inventing silence or stretching.
    """
    import av
    import numpy as np
    rate=48000;first=round(start*rate);last=round(end*rate);frames=last-first
    if not 0<frames<=round(MAX_SECONDS*rate): raise ValueError('Choose a bounded positive source window.')
    covered=np.zeros(frames,dtype=bool)
    with av.open(str(source)) as container:
        if len(container.streams.audio)!=1: raise ValueError('Select a library recording with exactly one audio stream.')
        stream=container.streams.audio[0]
        channels=stream.codec_context.channels
        if channels not in (1,2): raise ValueError('Choose a mono or stereo recording for an unprocessed source audition.')
        data=np.empty((frames,channels),dtype='<i2')
        origin=float((stream.start_time or 0)*stream.time_base)
        container.seek(max(0,int((origin+start)/float(stream.time_base))),stream=stream,backward=True)
        resampler=av.AudioResampler(format='s16',layout='mono' if channels==1 else 'stereo',rate=rate)
        decoded=0
        def consume(out):
            if out.time is None: raise ValueError('The audition source has missing audio timestamps.')
            samples=out.to_ndarray().reshape(-1,channels)
            offset=round((float(out.time)-origin)*rate)
            left=max(0,first-offset);right=min(len(samples),last-offset)
            if right>left:
                at=offset+left-first;data[at:at+right-left]=samples[left:right];covered[at:at+right-left]=True
        for frame in container.decode(stream):
            token.check();decoded+=frame.samples/frame.sample_rate
            if decoded>(end-start)+15.: raise ValueError('The source could not seek to a bounded audition window.')
            for out in resampler.resample(frame): consume(out)
            if covered.all(): break
        for out in resampler.resample(None): consume(out)
    if not covered.all(): raise ValueError('The selected source window could not be decoded completely. Refresh or relink the recording.')
    token.check()
    with wave.open(str(output),'wb') as audio:
        audio.setparams((channels,2,rate,0,'NONE','not compressed'));audio.writeframes(data.tobytes())


def prepare(root,manifest_path,manifest_sha256,candidate_id,*,allowed_roots=None,
            banned_paths=(),encoder=None,encoder_revision=None,token=None):
    """Return a ready descriptor, a plain failure, or acknowledged cancellation.

    `manifest_sha256` must come from the suite's verified saved job receipt, not
    be trusted simply because a browser supplied it. No auth/route is added here.
    Audition is a raw source excerpt: proposed gain/processing is metadata only.
    """
    token=token or CancellationToken()
    try:
        token.check();root=Path(root).resolve();path=Path(manifest_path).resolve()
        output=(root/'output').resolve()
        if (not output.is_relative_to(root) or not path.is_relative_to(output) or path.parent==output or not path.is_file()):
            raise ValueError('Select a saved recommendation inside its existing Storylens output job.')
        if not isinstance(manifest_sha256,str) or not re.fullmatch('[0-9a-f]{64}',manifest_sha256):
            raise ValueError('Refresh this sound recommendation to obtain its verified manifest identity.')
        if not isinstance(candidate_id,str) or not candidate_id or len(candidate_id)>160:
            raise ValueError('Select an explicit sound candidate before listening.')
        if encoder is not None and (not callable(encoder) or not isinstance(encoder_revision,str) or not encoder_revision.strip() or len(encoder_revision)>120):
            raise ValueError('Supply a versioned audition encoder before preparing audio.')
        manifest=_load_manifest(path,manifest_sha256,token);candidate=_selection(manifest,candidate_id)
        verified=verify_candidate_source(root,candidate,allowed_roots=allowed_roots,banned_paths=banned_paths,token=token)
        if _credits(Path(verified['path']))!=candidate['credits']:
            raise ValueError('The sound licence or credit metadata changed. Refresh the recommendation.')
        binding=dict(version=VERSION,manifest_path=str(path),manifest_sha256=manifest_sha256,candidate_id=candidate_id,
            source=copy.deepcopy(candidate['source']),credits=copy.deepcopy(candidate['credits']),
            timeline=copy.deepcopy(candidate['timeline']),proposed_level_db=candidate['proposed_level_db'],
            processing=copy.deepcopy(candidate.get('processing',{})),
            encoder_revision=encoder_revision if encoder is not None else ENCODER_REVISION,test_encoder_used=encoder is not None)
        key='audition-'+hashlib.sha256(json.dumps(binding,sort_keys=True,allow_nan=False).encode()).hexdigest()[:32]
        auditions=(path.parent/'auditions').resolve()
        if auditions.parent!=path.parent or not auditions.is_relative_to(output):
            raise ValueError('The audition folder is outside this saved job. Keep its files and repair the job path.')
        auditions.mkdir(exist_ok=True)
        preview=auditions/(key+'.wav');receipt=auditions/(key+'.json')
        cached=_cached(receipt,preview,binding,token)
        if cached is not None: return cached
        with _owned_work(auditions,key) as work:
            cached=_cached(receipt,preview,binding,token)
            if cached is not None:return cached
            source=candidate['source'];snapshot=work/('source'+Path(verified['path']).suffix)
            _snapshot(verified['path'],snapshot,verified['sha256'],token)
            temporary=work/'preview.wav';encode=encoder or _encode_window
            encode(snapshot,temporary,verified['source_in'],verified['source_out'],token)
            facts=_output_facts(temporary,verified['source_out']-verified['source_in'],token)
            # Revalidate external inputs after the bounded operation; encode from
            # a hash-verified private snapshot so transient source edits cannot
            # change which input bytes the encoder receives.
            _load_manifest(path,manifest_sha256,token)
            verify_candidate_source(root,candidate,allowed_roots=allowed_roots,banned_paths=banned_paths,token=token)
            token.check();os.replace(temporary,preview);facts['path']=str(preview)
            result=dict(schema='storylens.sound-audition',version=VERSION,status='ready',id=key,
                binding=binding,manifest_sha256=manifest_sha256,candidate_id=candidate_id,
                source=copy.deepcopy(source),credits=copy.deepcopy(candidate['credits']),preview=facts,
                proposed_timeline=copy.deepcopy(candidate['timeline']),proposed_level_db=candidate['proposed_level_db'],
                proposed_processing=copy.deepcopy(candidate.get('processing',{})),applied_gain_db=0.,applied_processing={},
                raw_source_audition=True,full_mix_rendered=False,native_imported=False,cache_hit=False,
                test_encoder_used=encoder is not None,local_agent_acceptance=False,
                notice='Selected source excerpt is ready to listen to. Proposed mix settings are not applied.')
            write_json_atomic(receipt,result)
            return result
    except RecommendationCancelled:
        return dict(status='cancelled',notice='Sound audition stopped. The library and saved recommendation are kept.',native_imported=False)
    except Exception as error:
        from hinglish_app.user_messages import problem
        issue=problem(error,feature='Sound audition')
        return dict(status='failed',notice=issue['message'],error_code=issue['code'],technical_details=issue['details'],native_imported=False)
