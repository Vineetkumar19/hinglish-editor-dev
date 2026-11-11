"""Local, hash-bound sound catalog. Imports start quarantined."""
from pathlib import Path
import math,json,re,threading
from .curation import Store,file_hash
from .recipes import CATEGORIES


def inspect_audio(path,folder=None,stop=None):
    import av
    import numpy as np
    path=Path(path).resolve()
    if path.suffix.lower() not in ('.wav','.mp3','.m4a','.flac','.ogg','.aac') or not path.is_file():
        raise ValueError('Choose an existing audio recording.')
    duration=0.;peak=0.;square=0.;samples=0
    with av.open(str(path)) as container:
        if not container.streams.audio:raise ValueError('The selected file has no audio track.')
        stream=container.streams.audio[0];rate=stream.rate;channels=stream.codec_context.channels
        for frame in container.decode(stream):
            data=frame.to_ndarray()
            if np.issubdtype(data.dtype,np.integer):data=data.astype(np.float64)/max(abs(np.iinfo(data.dtype).min),np.iinfo(data.dtype).max)
            else:data=data.astype(np.float64)
            if not np.isfinite(data).all():raise ValueError('The recording contains invalid decoded samples.')
            peak=max(peak,float(np.max(np.abs(data))));square+=float(np.sum(data*data));samples+=data.size
            duration+=frame.samples/frame.sample_rate
    result={'path':str(path),'hash':file_hash(path),'original_filename':path.name,'duration':duration,
            'sample_rate':rate,'channels':channels,'sample_peak_dbfs':20*math.log10(max(peak,1e-12)),
            'rms_dbfs':10*math.log10(max(square/max(samples,1),1e-24)),
            'integrated_lufs':None,'true_peak_dbtp':None,'measurement_note':'Sample peak and RMS only; loudness/true-peak analysis pending.'}
    if folder is not None:
        from .render import run_ffmpeg
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        log=folder/'ffmpeg.log';offset=log.stat().st_size if log.exists() else 0
        run_ffmpeg(['-loglevel','info','-i',path,'-vn','-af','loudnorm=I=-14:TP=-1:LRA=11:print_format=json','-f','null','-'],folder,stop or threading.Event())
        with log.open('rb') as stream:stream.seek(offset);text=stream.read().decode('utf-8',errors='replace')
        blocks=re.findall(r'\{\s*"input_i"[\s\S]*?\}',text)
        if not blocks:raise ValueError('Loudness analysis returned no measurement.')
        data=json.loads(blocks[-1])
        def finite(value):
            number=float(value)
            return number if math.isfinite(number) else None
        result.update(integrated_lufs=finite(data['input_i']),true_peak_dbtp=finite(data['input_tp']),measurement_note='FFmpeg loudnorm integrated loudness and oversampled true peak; silent audio has null loudness.')
    return result


def import_audio(database,value,working_root=None,*,derivation=None):
    from .render import run_ffmpeg
    original_hash=file_hash(value['path'])
    folder=Path(working_root)/original_hash if working_root else None
    measured=inspect_audio(value['path'],folder);id=measured['hash'];alias=value.get('alias','').strip()
    if not alias or len(alias)>120:raise ValueError('Give the recording a short exact alias.')
    if any(r.get('alias')==alias and r['id']!=id for r in database.list('sound')):raise ValueError('That exact alias already identifies another recording.')
    categories=value.get('categories',[])
    if not categories or any(c not in CATEGORIES for c in categories):raise ValueError('Choose a sound-library category.')
    if value['input_hashes']!=[id]:raise ValueError('Confirm the current recording hash before importing.')
    try:
        current=database.get(id)
    except ValueError:
        current=None
    if current and current.get('derivation') and derivation is None:
        raise ValueError('This audio is an existing derived ambience loop. Review its saved provenance.')
    if folder is not None:
        temporary=folder/'working.partial.wav';working=folder/'working.wav'
        run_ffmpeg(['-i',measured['path'],'-vn','-ar','48000','-ac','2','-c:a','pcm_s24le',temporary],folder,threading.Event())
        if file_hash(measured['path'])!=id:raise ValueError('The recording changed during import.')
        temporary.replace(working)
        measured.update(working_path=str(working),working_hash=file_hash(working),working_sample_rate=48000)
    if value.get('expiry'):
        from datetime import date
        date.fromisoformat(value['expiry'])
    return database.mutate(id,'sound',value,lambda old:{**measured,'alias':alias,'categories':categories,
        'tags':value.get('tags',[]),'source_url':value.get('source_url',''),'license_evidence':value.get('license_evidence',''),
        'attribution':value.get('attribution',''),'commercial_scope':value.get('commercial_scope','unknown'),
        'expiry':value.get('expiry'),**({'derivation':derivation} if derivation else {}),'rights_state':'quarantined','audition_approved':False})


def review_audio(database,value):
    def change(old):
        if old is None:raise ValueError('Import the sound before reviewing it.')
        if file_hash(old['path'])!=old['hash'] or value['input_hashes']!=[old['hash']]:raise ValueError('The recording changed; import the new bytes separately.')
        evidence=value.get('license_evidence','').strip()
        if value.get('rights_state') not in ('approved','quarantined'):raise ValueError('Choose a rights review state.')
        if value['rights_state']=='approved' and not evidence:raise ValueError('Record the actual permission or licence evidence first.')
        if value.get('audition_approved') not in (True,False):raise ValueError('Record whether this exact file was auditioned.')
        return {**old,'license_evidence':evidence,'rights_state':value['rights_state'],
                'audition_approved':value['audition_approved'],'reviewer':value.get('reviewer','owner')}
    return database.mutate(value['id'],'sound',value,change)
