"""Effects must be present in real media, bounded to cuts, audible and below dialogue."""
from pathlib import Path
import wave
import numpy as np


def checks(folder,plan,Check):
    settings=plan.get('settings',{})
    if not settings.get('sounds') and not settings.get('overlays'):return []
    fx=plan.get('effects',{})
    events=plan.get('events',[])
    cues=fx.get('cues',[]);overlays=fx.get('overlays',[])
    duration=len(plan['curve'])/plan['fps']
    result=[]
    if settings.get('sounds'):
        timed=fx.get('mix',{}).get('sync_policy')=='movement-duration-v2'
        bounds=all(0<=c['event']<len(events) and c['time']>=events[c['event']]['start']-.001 and
            c['time']+c['length']<=events[c['event']]['end']+.002 and abs(c['heard_peak']-c['target'])<=.041 for c in cues)
        paths=all(Path(c['path']).is_file() and Path(c['stem']).is_file() for c in cues)
        complete=len(cues)==len(events) and {c['event'] for c in cues}==set(range(len(events)))
        if timed:
            from .sound_timing import movements
            from .curve import ZoomEvent
            expected=[(i,a,b) for i,e in enumerate(events) for a,b in movements(ZoomEvent(**e))]
            complete=len(cues)==len(expected)
            bounds=complete and all(c['event']==i and abs(c['time']-a)<=1/48000 and
                abs(c['length']-(b-a))<=2/48000 and c.get('body_db_relative',99)<=-21.95
                for c,(i,a,b) in zip(cues,expected))
        mix=fx.get('mix',{})
        audio_ok=False
        master=Path(folder)/'sound/full-mix.wav'
        if master.is_file():
            with wave.open(str(master),'rb') as w:
                seconds=w.getnframes()/w.getframerate()
                audio=np.frombuffer(w.readframes(w.getnframes()),'<i2')
                audio_ok=bool(len(audio)) and abs(seconds-duration)<.001 and max(abs(audio.astype(np.int32)))<32767
        result += [
            Check('zoom.sfx.sync','Whooshes begin with the zoom and last exactly as long as its movement' if timed else 'One real sound per zoom, with its heard peak synced to the movement',complete and bounds and paths,
                  value=f'{len(cues)} sounds for {len(events)} moves'),
            Check('zoom.sfx.level','Sound effects remain below dialogue and the mix does not clip',
                  audio_ok and ((-45<=mix.get('effects_db_relative',99)<=-18) if timed else (-26<=mix.get('effects_db_relative',99)<=-6)) and mix.get('peak',2)<=.981,
                  value=f"{mix.get('effects_db_relative',99):.1f} dB relative to speech"),
            Check('zoom.sfx.variety','Use varied sounds selected from the listened-to local library',
                  bool(fx.get('listener')) and (len(cues)<4 or len({c['path'] for c in cues})>=min(3,len(fx.get('library',[])) or 3)),
                  value=f"{len({c['path'] for c in cues})} different files"),
        ]
        policy=fx.get('sound_policy')
        if policy:
            result.append(Check('zoom.sfx.owner_collection','Only the owner-approved basic whoosh collection is used',
                                all(c['category']=='whoosh' and c['path'] in policy['allowed_paths'] for c in cues),
                                value=f'{len(cues)} sounds restricted to the approved files'))
    if settings.get('overlays'):
        from .overlays import FOOTAGE_STYLES
        eligible=any(e['start']>0 and any(abs(e['start']-s[0])<=1/plan['fps'] for s in plan.get('shots',[])) for e in events)
        valid=(bool(overlays) or not eligible) and len(overlays)<=4 and all(
            0<=o['event']<len(events) and o['cut']>0 and any(abs(o['cut']-s[0])<=1/plan['fps'] for s in plan.get('shots',[])) and abs(o['cut']-events[o['event']]['start'])<=1/plan['fps'] and
            0<=o['start_frame']<o['end_frame']<=len(plan['curve']) and
            o['end_frame']-o['start_frame']<=max(6,round(.35*plan['fps'])) and
            ((o.get('composition')=='footage_transition' and o['kind'] in FOOTAGE_STYLES and
              o['max_opacity']==1 and Path(o.get('footage_source','')).is_file()) or
             (o.get('composition')!='footage_transition' and o['max_opacity']<=.22)) and Path(o['path']).is_file() for o in overlays)
        result.append(Check('zoom.overlays','Brief transitions align to selected actual cuts',valid,
                            value=f'{len(overlays)} subtle transitions; camera framing is independent'))
        if fx.get('preserved_overlays') is not None:
            actual=[{k:o[k] for k in ('event','kind','cut')} for o in overlays]
            result.append(Check('zoom.overlays.preserved','Existing approved transitions stay unchanged during sound replacement',
                                actual==fx['preserved_overlays'],value=f'{len(actual)} original transitions kept'))
    if fx.get('preserved_sound_choices') is not None:
        result.append(Check('zoom.sfx.preserved','The comparison keeps the same sound choices',
                            [{k:c[k] for k in ('event','path')} for c in cues]==fx['preserved_sound_choices']))
    return result
