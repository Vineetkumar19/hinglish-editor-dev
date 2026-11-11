"""Fit a quiet whoosh to the real camera movement, including its exact onset."""
import numpy as np

RATE=48000
SYNC_POLICY='movement-duration-v2'
UNDER_SPEECH_DB=-22.0
PEAK_UNDER_SPEECH_DB=-20.0


def movements(event):
    if event.kind in ('cut_in','cut_out','smooth','push'):
        spans=[(event.start,event.word)]
        if event.kind in ('smooth','push'):spans.append((event.hold_end,event.end))
    elif event.kind=='reveal':spans=[(event.start,event.end)]
    else:spans=[(event.start,min(event.end,event.start+.12))]
    return [(a,b) for a,b in spans if b-a>=1/RATE]


def fit(audio,seconds):
    """Pitch-preserving duration fit with trimmed silence and click-free edges."""
    import librosa
    audio=np.asarray(audio,np.float32)
    loud=np.flatnonzero(abs(audio)>max(float(np.max(abs(audio)))*.018,1e-8))
    if not len(loud):raise ValueError('An approved SmartZoom sound is silent. Replace that file and retry; your video is kept.')
    audio=audio[max(0,loud[0]-240):min(len(audio),loud[-1]+241)]
    count=max(1,round(seconds*RATE))
    result=librosa.effects.time_stretch(audio,rate=len(audio)/count,n_fft=1024,hop_length=256)
    result=np.pad(result,(0,max(0,count-len(result))))[:count].astype(np.float32)
    fade_in=min(round(.015*RATE),count//6);fade_out=min(round(.035*RATE),count//5)
    if fade_in:result[:fade_in]*=np.sin(np.linspace(0,np.pi/2,fade_in,dtype=np.float32))**2
    if fade_out:result[-fade_out:]*=np.cos(np.linspace(0,np.pi/2,fade_out,dtype=np.float32))**2
    return result


def quiet_gain(sound,voice,start,end,voice_gain):
    from hinglish_sound.mix import body_db,syllable_db
    speech=np.asarray(voice,np.float32)*voice_gain
    def measured(samples,measure):
        # The existing phone-weighting biquads clamp full-scale input. Probe
        # below that limit, then restore dB, so loud source WAVs are not
        # underestimated and subsequently mixed too loudly.
        scale=min(1.0,.05/max(float(np.max(abs(samples))),1e-9))
        return measure(samples*scale)-20*np.log10(scale)
    global_reference=measured(speech,syllable_db)
    window=speech[max(0,round((start-.25)*RATE)):min(len(speech),round((end+.25)*RATE))]
    local_reference=measured(window,syllable_db) if len(window) else global_reference-12
    reference=min(global_reference,max(global_reference-12,local_reference))
    gain=10**((reference+UNDER_SPEECH_DB-measured(sound,body_db))/20)
    speech_peak=max(float(np.max(abs(window))) if len(window) else 0,float(np.max(abs(speech)))*.15)
    ceiling=speech_peak*10**(PEAK_UNDER_SPEECH_DB/20)
    gain=min(gain,ceiling/max(float(np.max(abs(sound))),1e-9))
    return gain,reference,body_db(sound*gain)-reference
