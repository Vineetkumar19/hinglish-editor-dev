"""Place chosen sounds on exact words (peak-synced), add edit sounds, and keep the density musical."""
from dataclasses import dataclass, asdict, field
import math
import re

from .library import exact_peak_time
from .settings import LAYER_WHOOSH_OFFSET, SFX_BEHAVIOUR, TRANSITION_OFFSET, ZOOM_OFFSET


@dataclass
class Cue:
    time: float          # when the file starts on the timeline (s)
    target: float        # the moment it is aimed at (word / cut)
    path: str
    category: str
    length: float        # how much of the file plays (s)
    offset_db: float     # the effect's peak relative to the voice's peak (dB)
    loudness: float
    reason: str
    word: str = ''
    sound: str = ''      # the director's intent
    source: str = 'ai'   # ai | broll | zoom | layer
    strength: int = 2
    emotion: str = ''
    trigger: str = ''    # why a sound is here (punchline, list_item, app_or_device...)
    line: str = ''       # the spoken line
    pull_back: bool = False
    evaluation: dict = None
    source_offset: float = 0.0  # trim pre-roll when a peak would otherwise start before the timeline
    group_id: str = ''
    role: str = ''
    timing_precision: str = 'editor'
    uncertainty: float = 0.0
    anchor_time: float | None = None  # measured speech/editor evidence, before authored sonic offsets
    timing_offset: float = 0.0
    processing: dict = field(default_factory=dict)
    alternatives: list = field(default_factory=list)
    sync: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def _norm(text):
    return re.sub(r'[^\w]+', '', str(text).casefold())


def word_time(phrase, words, target, word_index=None):
    inside = [w for w in words if w.start >= phrase.start - 1e-3 and w.end <= phrase.end + 1e-3]
    if not inside:
        return None
    wanted = _norm(target)
    if type(word_index) is int and 0 <= word_index < len(inside):
        word = inside[word_index]
        if _norm(word.text) == wanted:
            return word.start
    matches = [w for w in inside if wanted and _norm(w.text) == wanted]
    # Ambiguous repeated words need an occurrence id; never silently guess a timestamp.
    return matches[0].start if len(matches) == 1 else None


def place_cue(asset, target, category, reason, word='', sound='', source='ai', offset_db=None, strength=2,
              emotion='', requested_length=None):
    behaviour = SFX_BEHAVIOUR[category]
    if requested_length is not None:
        if type(requested_length) not in (int,float) or not math.isfinite(requested_length) or requested_length<=0:
            raise ValueError('Sound excerpt duration must be a positive finite number')
        # Explicitly authored envelopes may outlast legacy default hit limits.
        # Never stretch the source; unchanged legacy calls keep their old limits.
        length=min(float(asset.duration),30. if category=='ambience' else 8.,requested_length)
        if not math.isfinite(length) or length<.001:
            raise ValueError('Sound excerpt duration must contain at least one millisecond of audio')
        # Search the useful source, not its requested short prefix. The indexed
        # peak is too coarse to use as the local landing of a new excerpt.
        full_peak=exact_peak_time(asset.path,float(asset.duration),hpf=behaviour.get('hpf'))
        if full_peak is None:
            raise ValueError('Sound effect file could not be measured for an audible excerpt')
        source_offset=max(0.,min(full_peak-length/2,max(0.,float(asset.duration)-length)))
        from .library import decode
        import numpy as np
        excerpt=decode(asset.path,48000,mono=True,limit=source_offset+length)[0][int(source_offset*48000):]
        if not len(excerpt) or np.max(np.abs(excerpt))<1e-7:
            raise ValueError('Sound effect file has no audible excerpt')
        local_peak=exact_peak_time(asset.path,length,hpf=behaviour.get('hpf'),source_offset=source_offset)
        if local_peak is None:
            raise ValueError('Sound effect excerpt could not be timed')
        start=target-local_peak if behaviour['align']=='peak' else target
        before_zero=max(0.,-start)
        source_offset+=before_zero
        length=min(length-before_zero,float(asset.duration)-source_offset)
        length=math.floor(length*1000+1e-6)/1000
        if length<=0:
            raise ValueError('Sound effect excerpt falls before the start of the timeline')
        return Cue(round(max(0.,start),3),round(target,3),asset.path,category,length,
                   behaviour['offset'] if offset_db is None else offset_db,asset.loudness,reason,word,sound,
                   source,strength,emotion,source_offset=round(source_offset,6))
    length = min(asset.duration, behaviour['max_len'])
    peak = exact_peak_time(asset.path, length + .05, hpf=behaviour.get('hpf')) if behaviour['align'] == 'peak' else None
    peak = asset.peak_time if peak is None else peak   # the index rounds the peak down to 50 ms
    if behaviour['align'] == 'peak' and peak < length:
        start = target - peak                     # sub-frame sync: the loudest instant hits the word / cut
    else:
        start = target
    trim = max(0.0, -start)
    return Cue(round(max(0.0, start), 3), round(target, 3), asset.path, category, round(length, 3),
               behaviour['offset'] if offset_db is None else offset_db, asset.loudness, reason, word, sound,
               source, strength, emotion, source_offset=round(trim, 6))


def keep_musical(cues, duration, every, gap):
    """Strongest first; never two sounds within `gap` s; about one designed sound per `every` s."""
    budget = max(1, math.ceil(duration / every))
    kept = []
    for cue in sorted(cues, key=lambda c: (-c.strength, c.target)):
        if len(kept) >= budget:
            continue
        if cue.category == 'ambience' and any(c.category == 'ambience' and
                cue.time < c.time + c.length and cue.time + cue.length > c.time for c in kept):
            continue
        if any(abs(cue.target - c.target) < gap for c in kept):
            continue
        kept.append(cue)
    return sorted(kept, key=lambda c: c.time)


EDIT_QUERIES = {
    'broll': {'serious': 'cinematic whoosh transition, smooth and clean',
              'emotional': 'soft airy cinematic whoosh transition',
              'comedic': 'quick cartoon whoosh swipe transition',
              'energetic': 'fast punchy whoosh transition',
              'informational': 'clean fast whoosh transition'},
    'zoom': {'serious': 'deep cinematic boom, low bass hit',
             'emotional': 'soft deep cinematic boom',
             'comedic': 'cartoon pop',
             'energetic': 'punchy bass drop hit',
             'informational': 'clean deep thud hit'},
}
LAYER_QUERY = 'fast cinematic whoosh swoosh leading into a hit'


def edit_cues(index, palette, broll_cuts, zoom_lands, taken, used, limit=None, gap=.8, banned=()):
    """A whoosh on B-roll cut-ins and a boom where a zoom lands on the key word, at most `limit` of them
    (earliest first) and never within `gap` s of another sound."""
    cues = []
    serious = palette != 'comedic'
    for source, times, category, offset in (('broll', broll_cuts, 'whoosh', TRANSITION_OFFSET),
                                            ('zoom', zoom_lands, 'impact', ZOOM_OFFSET)):
        query = EDIT_QUERIES[source].get(palette, EDIT_QUERIES[source]['informational'])
        for t in times:
            if limit is not None and len(cues) >= limit:
                break
            if any(abs(t - c.target) < gap for c in taken + cues):
                continue
            hits = index.search(query, top=4, categories=[category],
                                exclude_genres=('funny',) if serious else (), max_duration=2.0,
                                exclude_paths=used, banned=banned)
            hits = [h for h in hits if h[0].duration <= 3.0] or hits
            if not hits:
                continue
            asset = hits[0][0]
            used.add(asset.path)
            cat = asset.category if asset.category in SFX_BEHAVIOUR else category
            cues.append(place_cue(asset, t, cat, 'B-roll cut-in' if source == 'broll' else 'zoom lands on the key word',
                                  sound=query, source=source, offset_db=offset, strength=1))
    return cues


def layer_hits(cues, index, palette, used, banned=(), evaluate=True):
    """Pro composite: a whoosh whose peak arrives exactly on every hit (impact) of strength 2-3."""
    layers = []
    for cue in cues:
        if cue.category != 'impact' or cue.source != 'ai' or cue.strength < 3:
            continue                        # v4: only the biggest hits get the layered whoosh
        hits = index.search(LAYER_QUERY, top=3, categories=['whoosh'],
                            exclude_genres=('funny',) if palette != 'comedic' else (), max_duration=1.6,
                            exclude_paths=used, banned=banned)
        if evaluate:
            from .evaluator import check_effect
            hits = [h for h in hits if check_effect(index.listener,
                    None if index.audio is None else index.audio[index.assets.index(h[0])],
                    index.facts_for(h[0]), 'whoosh', LAYER_QUERY, palette).passed is not False]
        if not hits:
            continue
        asset = hits[0][0]
        used.add(asset.path)
        layers.append(place_cue(asset, cue.target, 'whoosh', f'layered into the hit on "{cue.word}"',
                                cue.word, LAYER_QUERY, 'layer', LAYER_WHOOSH_OFFSET, 1))
    return layers
