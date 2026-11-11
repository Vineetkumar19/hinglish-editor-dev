"""Find the audible subject across library folders; do not substitute unrelated audio."""
import math
import re
from .relevance import source_matches, _subjects
from .settings import SFX_BEHAVIOUR


DURATION_GUIDANCE = {
    'principle':'Choose duration from the natural audible envelope and the scene, never from the spoken word length. No universal minimum or forced density.',
    'transients':'A real click/tap can be 0.06–0.3 seconds. Use it only when a click/tap is the intended sound, not as the default for every beat.',
    'developing_sounds':'Stings, joyful tonal reactions, swells, sliding movement and decays can develop for 1–3 seconds, sometimes 3–8 seconds when the event warrants it. Do not cut their body/tail into a 0.1-second tick.',
    'continuous_sources':'Match engines, water flow, surface motion and environment beds to the visible scene span. Quiet layers can overlap foreground accents; do not retrigger them at every word.',
    'music':'Use coherent musical phrases across lines. A short musical sting is a sound-design accent; do not rotate background tracks at each spoken line.',
}

SOUND_FAMILIES = {
    'foley':'Actual physical source: wheels, engine, sliding surface, splashing/pouring water, fabric or footsteps; require observed source evidence.',
    'ambience':'Sustained location/environment: water flow, wind, traffic, crowd or room tone; require scene support.',
    'poke':'An actual short click, pop, tap or UI notification; not a musical chime, environmental bed or default word sound.',
    'cute':'Resonant chime, bright musical tonal reaction, sparkle or joyful descending/ascending sting with its natural decay.',
    'awkward':'Comic tonal sting, humorous reaction, record scratch or comic stop at an actual joke/contradiction.',
    'suspense':'Sustained tonal tension, heartbeat, low drone or ticking with a motivated build/release.',
    'riser':'Growing or reversed swell leading into a motivated event.',
    'whoosh':'Air movement, sweep or swoosh following a movement span.',
    'impact':'Weighty hit, low thump or resonant impact and decay.',
    'vanish':'Disappearing/releasing air or descending decay.',
    'retro':'Game-like musical coin/win accent when the story supports that aesthetic.',
    'glitch':'Digital distortion/stutter only; not a chime, generic air sweep or environmental bed.',
}


def physical_evidence_supported(intent, event):
    """Do not turn copied material examples into invented scene Foley."""
    evidence=str(event.get('label',''))+' '+str(event.get('sound_evidence',''))
    def subjects(text):
        result=_subjects(text)
        for material,pattern in {'wood':r'\bwood(?:en)?\b','plastic':r'\bplastic\b',
                                 'metal':r'\bmetal(?:lic)?\b'}.items():
            if re.search(pattern,text,re.I):result.add(material)
        return result
    wanted,visible=subjects(intent),subjects(evidence)
    return not (wanted-visible)


def effect_candidates(index, query, moment, exclude=(), banned=(), *, folder_options=False):
    family=moment['type']
    duration=moment.get('duration')
    authored=type(duration) in (int,float) and math.isfinite(duration) and duration>0
    physical=family in ('foley','ambience')
    # Owner libraries are folder-labelled, not a reliable physical ontology.
    # A water recording filed as "poke" is still eligible for a water bed.
    hits=index.search(moment['intent'] if physical else query,top=80 if physical else 24,
        categories=None if physical else [family],exclude_genres=exclude,
        max_duration=None if authored or folder_options else SFX_BEHAVIOUR[family]['max_len'],banned=banned)
    if physical:
        wanted=_subjects(moment['intent'])
        def match(asset):return bool(wanted & _subjects(asset.name+' '+asset.text))
        seen={h[0].path for h in hits}
        # Keep exact subject/name matches in the offered slate even if fusion
        # ranks a new recording below many old cinematic/synthetic assets.
        genres=getattr(index,'genres',[])
        for i,asset in enumerate(getattr(index,'assets',[])):
            if exclude:
                from .vectors import genre_of
                genre=genres[i] if i<len(genres) else genre_of(asset)
                if genre in exclude:continue
            if asset.path not in seen and asset.path not in banned and match(asset):
                hits.append((asset,0.,'metadata subject match'));seen.add(asset.path)
        hits.sort(key=lambda h:not match(h[0]))
    accepted,rejected=[],[]
    for hit in hits:
        asset=hit[0]
        ok,why=source_matches(asset,family,moment['intent'])
        if ok and authored and not folder_options and asset.duration+1e-3<duration:
            ok,why=False,'The recording is shorter than the authored sound; do not stretch a click into a sustained sound.'
        if ok:accepted.append(hit)
        else:rejected.append(dict(file=asset.path,intent=moment['intent'],reason=why))
    return accepted,rejected
