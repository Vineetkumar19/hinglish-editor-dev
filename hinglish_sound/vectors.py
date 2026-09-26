"""Vector index (RAG store) over the sound library: every file becomes a rich text document, embedded
once with the local embedding model; each sound moment retrieves its best real candidates from it."""
import json
from pathlib import Path

import numpy as np

from .library import audible_span

# The user's library files carry a genre in their names/tags (thriller_..., funny_..., neutral_...).
GENRE_WORDS = {'funny': ['funny', 'cartoon', 'comedy', 'silly', 'goofy', 'meme', 'boing', 'squeak', 'kazoo'],
               'thriller': ['thriller', 'cinematic', 'dark', 'trailer', 'braam', 'horror', 'ominous', 'tension'],
               'neutral': ['neutral', 'clean', 'soft', 'subtle', 'minimal', 'ui']}


def genre_of(asset):
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
PRO_BONUS = .03      # the curated professional pack wins when a match is about as good


def is_pro(asset):
    return PRO_MARK in asset.path.replace('\\', '/').lower()


def document(asset):
    quality = 'professional studio sound' if is_pro(asset) else 'community recording'
    return (f'{asset.kind} | type: {asset.category} | genre: {genre_of(asset)} | {character(asset)} | '
            f'{quality} | {asset.name} | {asset.text}')[:600]


class SoundIndex:
    def __init__(self, assets, brain):
        self.assets = assets
        self.docs = [document(a) for a in assets]
        self.genres = [genre_of(a) for a in assets]
        self.vectors = brain.embed(self.docs) if assets else np.zeros((0, 1024), np.float32)
        self.brain = brain

    def search(self, query, top=6, categories=None, exclude_genres=(), max_duration=None, exclude_paths=(),
               min_audible=MIN_AUDIBLE):
        if not self.assets:
            return []
        q = self.brain.embed([query])[0]
        scores = self.vectors @ q + np.array([PRO_BONUS if is_pro(a) else 0.0 for a in self.assets])
        ranked = []
        for i in np.argsort(-scores):
            a = self.assets[i]
            if categories and a.category not in categories:
                continue
            if self.genres[i] in exclude_genres or a.path in exclude_paths:
                continue
            if max_duration and a.duration > max_duration * 3:
                continue
            if min_audible and a.kind == 'sfx' and audible_span(a.path) < min_audible:
                continue
            ranked.append((a, float(scores[i]), self.genres[i]))
            if len(ranked) >= top:
                break
        return ranked
