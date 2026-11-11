"""Recipe execution with original audio retained and dialogue-timed ducking."""
from pathlib import Path
import json,re,math
from .curation import file_hash
from .render import run_ffmpeg


def mix(plan,original_audio,dialogue_activity,folder,stop):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    duration=float(plan['duration'])
    original_hash=file_hash(original_audio)
    if not 0<duration<=3600:raise ValueError('Choose a mix shorter than one hour.')
    for interval in dialogue_activity:
        if not 0<=interval['start']<interval['end']<=duration:raise ValueError('Dialogue activity must refer to the actual timeline.')
    inputs=['-i',str(original_audio)];filters=[f'[0:a]aresample=48000,asetpts=PTS-STARTPTS,apad,atrim=duration={duration}[original]'];labels=['[original]']
    for i,event in enumerate(plan['events'],1):
        if file_hash(event['path'])!=event['hash']:raise ValueError('A selected sound changed. No substitute was mixed.')
        inputs+=['-ss',str(event['source_in']),'-i',event['path']]
        length=event['end']-event['start'];gain=event['gain_db'];start=event['start']
        # Explicit activity intervals come from reviewed speech timing, not a
        # guessed all-track level. Source voice/music remains present exactly once.
        conditions=[f'between(t,{max(0,a["start"]-start):.6f},{min(length,a["end"]-start):.6f})' for a in dialogue_activity if a['end']>start and a['start']<event['end']]
        duck=('if(gt('+ '+'.join(conditions)+',0),0.25,1)') if conditions else '1'
        label=f'sfx{i}';labels.append('['+label+']')
        filters.append(f'[{i}:a]aresample=48000,atrim=duration={length},asetpts=PTS-STARTPTS,volume={gain}dB,'
                       f"volume='{duck}':eval=frame,afade=t=in:d={event['fade_in']},afade=t=out:st={max(0,length-event['fade_out'])}:d={event['fade_out']},"
                       f'adelay={round(start*1000)}:all=1[{label}]')
    filters.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[mix]')
    graph=folder/'mix-filter.txt';graph.write_text(';\n'.join(filters),encoding='utf-8')
    raw=folder/'mix-raw.wav';out=folder/'mix.partial.wav';final=folder/'mix.wav'
    run_ffmpeg([*inputs,'-filter_complex_script',graph,'-map','[mix]','-t',str(duration),'-ar','48000','-ac','2','-c:a','pcm_s24le',raw],folder,stop)
    target=float(plan['target_lufs']);ceiling=float(plan['true_peak_dbtp'])
    if not -36<=target<=-10 or not -9<=ceiling<=-1:raise ValueError('Use a supported loudness target and a peak ceiling at or below -1 dBTP.')
    run_ffmpeg(['-loglevel','info','-i',raw,'-af',f'loudnorm=I={target}:TP={ceiling}:LRA=11:print_format=json','-f','null','-'],folder,stop)
    log=(folder/'ffmpeg.log').read_text('utf-8',errors='replace')
    blocks=re.findall(r'\{\s*"input_i"[\s\S]*?\}',log)
    if not blocks:raise ValueError('The mixer did not return loudness measurements.')
    metrics=json.loads(blocks[-1])
    lra=max(11,math.ceil(float(metrics['input_lra'])))
    normalizer=f"loudnorm=I={target}:TP={ceiling}:LRA={lra}:measured_I={metrics['input_i']}:measured_TP={metrics['input_tp']}:measured_LRA={metrics['input_lra']}:measured_thresh={metrics['input_thresh']}:offset=0:linear=true"
    run_ffmpeg(['-i',raw,'-af',normalizer+f',aresample=48000,apad,atrim=end_sample={round(duration*48000)},asetpts=PTS-STARTPTS','-ar','48000','-ac','2','-c:a','pcm_s24le',out],folder,stop)
    from .sound_catalog import inspect_audio
    verified=inspect_audio(out,folder,stop)
    loudness = verified['integrated_lufs']
    peak = verified['true_peak_dbtp']
    if loudness is not None and peak is not None and abs(loudness - target) > 1:
        # Short mixes can miss the target after dynamic normalization. Correct
        # the measured result only when the required gain fits the peak budget.
        gain = target - loudness
        if peak + gain <= ceiling:
            corrected = folder/'mix.corrected.wav'
            run_ffmpeg(['-i', out, '-af', f'volume={gain:.6f}dB', '-c:a', 'pcm_s24le', corrected], folder, stop)
            corrected.replace(out)
            verified = inspect_audio(out, folder, stop)
    if verified['true_peak_dbtp'] is None or verified['true_peak_dbtp']>ceiling+.2:raise ValueError('The mixed output did not meet the true-peak ceiling.')
    if abs(verified['duration']-duration)>.05:raise ValueError('The mixed output duration changed.')
    if verified['integrated_lufs'] is None or abs(verified['integrated_lufs']-target)>1:raise ValueError('The mixed output missed its loudness target. Review gain/dynamics instead of accepting it silently.')
    if file_hash(original_audio)!=original_hash:raise ValueError('The original audio changed during mixing.')
    out.replace(final)
    result={'path':str(final),'hash':file_hash(final),'metrics':verified,'recipe_id':plan['recipe_id'],
            'original_audio_hash':original_hash,'dialogue_activity':dialogue_activity,
            'events':plan['events'],'audition_state':'pending','sample_rate':48000}
    (folder/'mix-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
