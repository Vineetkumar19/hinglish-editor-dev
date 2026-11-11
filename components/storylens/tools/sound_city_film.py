"""Bespoke sound edit for the owner's ChatGPT comparison film; no model inference."""
from pathlib import Path
import json, wave
import numpy as np
from hinglish_sound.library import decode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/motion/chatgpt-madurai-after-ten-20261024'
RATE = 48000
N = RATE * 50
T = np.arange(N) / RATE
timings = json.loads((OUT / 'timings.json').read_text(encoding='utf-8'))
starts = [x['start']/30 for x in timings]
music = ROOT / 'library/music/funny/kevin-macleod-local-forecast-elevator.mp3'
bed = decode(music, limit=58)[:,8*RATE:58*RATE]
envelope = np.minimum(T/.6, 1) * np.minimum((50-T)/1.3, 1)
# The dry pause is motivated by the city switching off; the final camera shot returns the groove.
off = starts[1]+1.85
duck = np.ones(N)
duck[(T>=off)&(T<off+1.1)] = .04
duck[(T>=off+1.1)&(T<starts[5])] = .42
mix = bed[:,:N] * envelope[None,:] * duck[None,:] * .26
events = []
credits = [{'file': str(music.relative_to(ROOT)), **json.loads(Path(str(music)+'.json').read_text()), 'changes':'50-second excerpt, level changes, fades and effects mixed.'}]

def cue(relative, when, gain=.3, length=2, peak_anchor=False):
    global mix
    path = ROOT/'library/sfx-pro'/relative
    data = decode(path, limit=length)
    # Trim only source leading silence; preserve the audible attack and natural tail.
    env = np.max(np.abs(data), axis=0)
    audible = np.flatnonzero(env > max(.002, float(env.max())*.025))
    if len(audible): data = data[:,max(0,int(audible[0]) - 240):]
    if not data.shape[1]: return
    data *= gain/max(.1,float(np.max(np.abs(data))))
    fade=min(240,data.shape[1]//3)
    data[:,:fade] *= np.linspace(0,1,fade)
    data[:,-fade:] *= np.linspace(1,0,fade)
    start=int(when*RATE); end=min(N,start+data.shape[1])
    mix[:,start:end] += data[:,:end-start]
    events.append({'time':round(when,3),'source':str(path.relative_to(ROOT)),'gain':gain,'purpose':relative.split('/')[-1]})
    sidecar=Path(str(path)+'.json')
    if not any(x['file']==str(path.relative_to(ROOT)) for x in credits):
        credits.append({'file':str(path.relative_to(ROOT)), **(json.loads(sidecar.read_text()) if sidecar.exists() else {})})

cue('whoosh/short_wind_swoosh_mixkit1461.mp3',.45,.18,1.2)
cue('suspense/clock_ticker_single_mixkit1061.mp3',starts[1]+.6,.19,.7)
cue('poke/on_or_off_light_switch_tap_mixkit2585.mp3',off,.45,.5)
cue('poke/on_or_off_light_switch_tap_mixkit2585.mp3',off+.35,.27,.5)
cue('whoosh/lightweight_sliding_door_close_mixkit182.mp3',starts[2]+.4,.22,1.3)
cue('whoosh/wooden_sliding_door_mixkit188.mp3',starts[2]+1.65,.18,1.4)
cue('whoosh/short_transition_sweep_mixkit175.mp3',starts[3]+1.05,.14,.8)
cue('whoosh/lightweight_sliding_door_close_mixkit182.mp3',starts[3]+2.0,.24,1.1)
cue('whoosh/short_transition_sweep_mixkit175.mp3',starts[3]+4.4,.13,.8)
cue('whoosh/wooden_long_sliding_door_mixkit191.mp3',starts[3]+7.2,.29,1.6)
cue('whoosh/vinyl_record_swipe_mixkit707.mp3',starts[4]+3,.15,.65)
cue('whoosh/short_wind_swoosh_mixkit1461.mp3',starts[5]+.05,.22,1.3)
cue('poke/camera_shutter_click_mixkit1133.mp3',starts[5]+1.1,.38,.5)
cue('poke/positive_interface_beep_mixkit221.mp3',starts[5]+1.14,.12,.5)
cue('whoosh/short_transition_sweep_mixkit175.mp3',starts[5]+4.3,.18,.7)
peak = float(np.max(np.abs(mix)))
mix *= min(1, .92/max(peak, 1e-6))
with wave.open(str(OUT/'soundtrack.wav'),'wb') as f:
    f.setnchannels(2); f.setsampwidth(2); f.setframerate(RATE)
    f.writeframes((mix.T.clip(-1,1)*32767).astype('<i2').tobytes())
(OUT/'sound-edit.json').write_text(json.dumps({'authorship':'ChatGPT sound edit, existing credited local audio assets','duration':50,'music_level':.26,'events':events,'peak_before_limiter':peak},indent=2),encoding='utf-8')
(OUT/'credits.json').write_text(json.dumps(credits,indent=2),encoding='utf-8')
(OUT/'CREDITS.txt').write_text('MADURAI / AFTER TEN\nCreative direction, vector artwork, animation and sound edit: ChatGPT, requested by owner.\nScript: owner. No voice narration.\n\n'+credits[0]['attribution']+'\nChanges: excerpted, faded and mixed.\n\nSound effects: Mixkit, Sound Effects Free License. Full source metadata: credits.json.\n',encoding='utf-8')
print('Soundtrack ready: 50 seconds, stereo, 15 motivated sound cues.')
