"""Create a distinct crossfaded recording that must be auditioned before use."""
import math
import wave
from pathlib import Path

from .curation import Store, file_hash, resolve_sound
from .render import run_ffmpeg
from .sound_catalog import import_audio


def loop_settings(value, asset):
    limits = {'source_in':(0, asset['duration']), 'segment_seconds':(.5, 60),
              'crossfade_seconds':(.02, 5), 'duration':(1, 120)}
    settings = {}
    for key, (low, high) in limits.items():
        number = value.get(key)
        if type(number) not in (int,float) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f'{key} must be between {low:g} and {high:g} seconds.')
        settings[key] = number
    if settings['source_in'] + settings['segment_seconds'] > asset['duration'] + 1e-9:
        raise ValueError('The loop segment extends beyond the approved recording.')
    if settings['crossfade_seconds'] >= settings['segment_seconds']/2:
        raise ValueError('The crossfade must be shorter than half the loop segment.')
    if settings['duration'] <= settings['segment_seconds']:
        raise ValueError('Choose a target longer than one loop segment.')
    return settings


def render_loop(root, request, folder, stop):
    import numpy as np

    root, folder = Path(root), Path(folder)
    database = Store(root/'cache/curation/projects.sqlite3')
    asset = resolve_sound(database.list('sound'), request['asset_id'], request['source_hash'])
    if '03_Ambience' not in asset['categories']:
        raise ValueError('Choose an approved ambience recording.')
    if asset.get('derivation'):
        raise ValueError('Choose the original recording for a new loop.')
    settings = loop_settings(request, asset)
    rate = 48000
    segment = round(settings['segment_seconds']*rate)
    overlap = round(settings['crossfade_seconds']*rate)
    total = round(settings['duration']*rate)
    raw = folder/'segment.f32'
    run_ffmpeg(['-ss', str(settings['source_in']), '-i', asset['path'], '-map','0:a:0',
                '-af',f'aresample={rate},atrim=end_sample={segment}',
                '-ac','2','-c:a','pcm_f32le','-f','f32le',raw], folder, stop)
    source = np.fromfile(raw, dtype='<f4').reshape(-1,2)
    if len(source) != segment or not np.isfinite(source).all():
        raise ValueError('The selected ambience did not decode to the requested segment.')
    result = np.empty((total,2), dtype=np.float32)
    result[:segment] = source
    # Complementary ramps preserve level through identical overlaps and prevent clipping.
    ramp = np.linspace(0, 1, overlap, dtype=np.float32)[:,None]
    end = segment
    while end < total:
        if stop.is_set():
            raise InterruptedError('Ambience loop preparation stopped.')
        start = end - overlap
        result[start:end] = result[start:end]*(1-ramp) + source[:overlap]*ramp
        count = min(total-end, segment-overlap)
        result[end:end+count] = source[overlap:overlap+count]
        end += count
    path = folder/'ambience-loop.wav'
    with wave.open(str(path),'wb') as audio:
        audio.setparams((2,2,rate,0,'NONE','not compressed'))
        audio.writeframes(np.round(np.clip(result,-1,1)*32767).astype('<i2').tobytes())
    resolve_sound(database.list('sound'), asset['id'], asset['hash'])
    if stop.is_set():
        raise InterruptedError('Ambience loop preparation stopped.')
    identity = file_hash(path)
    try:
        current = database.get(identity)
    except ValueError:
        current = None
    if current is not None and (current.get('kind') != 'sound' or
                                current.get('derivation',{}).get('source_hash') != asset['hash']):
        raise ValueError('Identical bytes already exist with different provenance.')
    derivation = {'kind':'crossfaded_ambience','source_id':asset['id'],'source_hash':asset['hash'],
                  'source_revision':asset['revision'],**settings}
    if current is None:
        key = 'ambience-loop:'+folder.name
        current = import_audio(database, {
            'id':identity, 'path':str(path), 'input_hashes':[identity], 'settings_version':1,
            'expected_revision':0, 'command_id':key, 'idempotency_key':key,
            'alias':asset['alias'][:85]+' - Loop '+identity[:12], 'categories':['03_Ambience'],
            'license_evidence':asset['license_evidence'], 'attribution':asset.get('attribution',''),
            'source_url':asset.get('source_url',''), 'commercial_scope':asset.get('commercial_scope','unknown'),
            'expiry':asset.get('expiry'),
        }, root/'cache/curation/sounds', derivation=derivation)
    return {'id':current['id'],'hash':identity,'alias':current['alias'],'derivation':current['derivation'],
            'audition_state':'approved' if current['audition_approved'] else 'pending'}
