"""Vector index (RAG store) over the sound library.

Two kinds of knowledge per file:
- TEXT: a document of name, tags, folder type, measured shape (embedded with the local text model)
- SOUND: what CLAP heard (audio vector) + "sounds like" labels, cartoonish?, singing?, energy, tempo
Search fuses both rankings (reciprocal rank fusion, the sound counts double), so "deep cinematic boom"
finds files that SOUND like one even when they are called "impact_03.wav"."""
import json

import numpy as np

from .library import audible_span

# The user's library files carry a genre in their names/tags (thriller_..., funny_..., neutral_...).
GENRE_WORDS = {'funny': ['funny', 'cartoon', 'comedy', 'silly', 'goofy', 'meme', 'boing', 'squeak', 'kazoo'],
               'thriller': ['thriller', 'cinematic', 'dark', 'trailer', 'braam', 'horror', 'ominous', 'tension'],
               'neutral': ['neutral', 'clean', 'soft', 'subtle', 'minimal', 'ui']}
RRF_K = 20
SOUND_WEIGHT, TEXT_WEIGHT = 2.0, 1.0


def genre_of(asset, facts=None):
    if facts and facts.get('cartoonish'):
        return 'funny'                       # heard as a cartoon sound, whatever its name says
    text = asset.text.lower() + ' ' + asset.path.lower()
    scores = {g: sum(w in text for w in words) for g, words in GENRE_WORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else 'neutral'


def character(asset):
    """Short plain-English shape of a sound, from its measured envelope."""
    if asset.kind == 'music':
        return 'long music bed' if asset.duration > 60 else 'short music cue'
    length = 'very short' if asset.duration < .6 else 'short' if asset.duration < 1.6 else 'medium' if asset.duration < 4 else 'long'
    shape = 'hits at once' if asset.peak_time < .12 else 'builds up to a peak' if asset.peak_time > .6 * asset.duration else 'swells then fades'
    return f'{length} ({asset.duration:.1f}s), {shape}'


MIN_AUDIBLE = .06   # seconds; shorter clicks vanish next to a voice
PRO_MARK = 'sfx-pro'


def is_pro(asset):
    return PRO_MARK in asset.path.replace('\\', '/').lower()


def heard(facts):
    """What the listener heard, in words for the AI."""
    if not facts:
        return ''
    parts = ['sounds like: ' + ', '.join(facts.get('sounds_like', []))]
    if 'cartoonish' in facts:
        parts.append('cartoonish' if facts['cartoonish'] else 'clean/cinematic')
    if 'vocals' in facts:
        parts.append('HAS SINGING' if facts['vocals'] else 'instrumental')
    if facts.get('energy') is not None and 'energy' in facts:
        parts.append(f"energy {facts['energy']:.1f}" + (f", ~{facts['bpm']:.0f} BPM" if facts.get('bpm') else ''))
    return ' | '.join(parts)


def document(asset, facts=None):
    quality = 'professional studio sound' if is_pro(asset) else 'community recording'
    listened = heard(facts)
    return (f'{asset.name} | {asset.text[:180]} | {asset.kind} | type: {asset.category} | '
            f'genre: {genre_of(asset, facts)} | {character(asset)} | {quality} | {listened}')[:600]


def music_facts(listener, asset):
    """Energy/tempo measured from the audio, cached next to the CLAP vectors."""
    from .listen import _key, music_features
    file = listener.cache / f'{_key(asset.path, "features")}.json'
    if file.exists():
        return json.loads(file.read_text(encoding='utf-8'))
    try:
        facts = music_features(asset.path)
    except Exception:
        facts = {'energy': None, 'bpm': 0.0}
    file.write_text(json.dumps(facts), encoding='utf-8')
    return facts


class SoundIndex:
    def __init__(self, assets, brain, listener=None, progress=print):
        self.assets = assets
        self.brain, self.listener = brain, listener
        self.audio = None
        self.facts = [None] * len(assets)
        if listener is not None and assets:
            self.audio = listener.vectors(assets, progress)
            kind = assets[0].kind
            self.facts = listener.describe(self.audio, kind)
            if kind == 'music':
                for facts, asset in zip(self.facts, assets):
                    facts.update(music_facts(listener, asset))
                mood_text = {
                    'reflective': 'quiet introspective melancholic piano ambient instrumental music',
                    'upbeat': 'bright joyful energetic instrumental music',
                    'tense': 'dark restrained investigative suspense instrumental music',
                    'cinematic': 'dramatic emotional cinematic orchestral instrumental music',
                    'neutral': 'minimal calm factual documentary instrumental underscore',
                    'hopeful': 'warm optimistic gently uplifting instrumental music'}
                mood_vectors = listener.text_vectors(list(mood_text.values()))
                for i, asset in enumerate(assets):
                    if asset.category in ('general', 'auto'):
                        asset.category = list(mood_text)[int(np.argmax(self.audio[i] @ mood_vectors.T))]
                        self.facts[i]['mood_source'] = 'CLAP estimate; not owner-labelled'
        self.docs = [document(a, f) for a, f in zip(assets, self.facts)]
        self.genres = [genre_of(a, f) for a, f in zip(assets, self.facts)]
        self.vectors = brain.embed(self.docs) if assets else np.zeros((0, 1024), np.float32)

    def facts_for(self, asset):
        try:
            return self.facts[self.assets.index(asset)] or {}
        except ValueError:
            return {}

    def scores(self, query):
        """Fused score per file: text match + (double weight) how much it SOUNDS like the query."""
        text = self.vectors @ self.brain.embed([query])[0]
        fused = TEXT_WEIGHT / (RRF_K + np.argsort(np.argsort(-text)))
        if self.audio is not None:
            sound = self.audio @ self.listener.text_vectors([query])[0]
            fused = fused + SOUND_WEIGHT / (RRF_K + np.argsort(np.argsort(-sound)))
        pro = np.array([.004 if is_pro(a) else 0.0 for a in self.assets])   # pro pack wins near-ties
        return fused + pro

    def search(self, query, top=6, categories=None, exclude_genres=(), max_duration=None, exclude_paths=(),
               min_audible=MIN_AUDIBLE, instrumental_only=False, banned=()):
        if not self.assets:
            return []
        scores = self.scores(query)
        ranked = []
        for i in np.argsort(-scores):
            a = self.assets[i]
            facts = self.facts[i] or {}
            if categories and a.category not in categories:
                continue
            if self.genres[i] in exclude_genres or a.path in exclude_paths or a.path in banned:
                continue
            if instrumental_only and facts.get('vocals'):
                continue                            # singing fights the speaker's words
            if max_duration and a.duration > max_duration * 3:
                continue
            if min_audible and a.kind == 'sfx' and audible_span(a.path) < min_audible:
                continue
            ranked.append((a, float(scores[i]), self.genres[i]))
            if len(ranked) >= top:
                break
        return ranked
