"""Score candidate footage against each moment and pick the best clip, never repeating one."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from .stock import cached_name, download

LIBRARY_BONUS = .01          # prefer the creator's own footage when it is equally good
ORIENTATION_PENALTY = .03    # a landscape clip in a vertical reel loses most of the frame
MIN_SPECIFIC = 0.0           # a clip must fit THIS moment at least as well as clearly different moments
SAME_IDEA = .88              # CLIP text similarity above this = the two moments describe the same idea
STRONG_MATCH = .29           # CLIP score this high is a clear match even if a generic scene scores similarly
DECENT_MATCH = .26           # below STRONG_MATCH a clip must also be specific to its moment
SPECIFIC_WEIGHT = .5
# Shots that look like the talking head itself. A clip that matches these as well as its moment is
# "just a person in a room", not a real cutaway. (Streets, food, phones, offices are real B-roll.)
GENERIC_SCENES = ['a young man talking to the camera', 'a man sitting on a bed in a room',
                  'a selfie video of a person', 'a person standing in a bedroom']


def moment_embedding(vision, slot, context=''):
    texts = [f'a photo of {slot.moment.visual}'] + [f'a photo of {q}' for q in slot.moment.queries[:1]]
    if context:
        texts.append(f'a photo of {slot.moment.visual}, {context}')
    vectors = vision.texts(texts)
    mean = vectors.mean(axis=0)
    return mean / max(np.linalg.norm(mean), 1e-8)


def fetch_thumbs(candidates, folder, session=None, workers=8):
    folder = Path(folder)
    todo = [c for c in candidates if c.source != 'library' and c.thumb.startswith('http')]

    def one(c):
        try:
            c.thumb = str(download(c.thumb, folder / cached_name(c, 'thumb'), session, timeout=30))
        except Exception:
            c.thumb = ''
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))


def score_stock(vision, embedding, candidates):
    ready = [c for c in candidates if c.source != 'library' and c.thumb and Path(c.thumb).is_file()]
    images = []
    for c in ready:
        with Image.open(c.thumb) as im:
            images.append(im.convert('RGB'))
    if images:
        for c, vector in zip(ready, vision.images(images)):
            c.score = float(vector @ embedding)
            c.vector = vector
    for c in candidates:
        if c.source != 'library' and c not in ready:
            c.score = -1.0


def add_specificity(pairs, embeddings, generic):
    """How much better each clip fits its own moment than other moments / generic scenes.

    CLIP gives any photo of a young man a medium score for any text about a young man; a clip is
    only a real match when it prefers THIS description. Sets c.specific (higher is better).
    """
    for i, (slot, candidates) in enumerate(pairs):
        # Only moments that describe something clearly different count as competition
        # ("PG room at night" vs "crowded PG room" are the same idea; a room clip fits both).
        others = [embeddings[j] for j in range(len(pairs))
                  if j != i and float(embeddings[i] @ embeddings[j]) < SAME_IDEA] + list(generic)
        if not others:
            continue
        contrast = np.stack(others)
        for c in candidates:
            vector = getattr(c, 'vector', None)
            if vector is not None:
                c.specific = float(c.score - np.max(contrast @ vector))


def usage_key(c):
    return f'{c.path}#{int(c.offset // 5)}' if c.source == 'library' else c.id


def adjusted(c, orientation):
    score = c.score + (LIBRARY_BONUS if c.source == 'library' else 0) + SPECIFIC_WEIGHT * min(0.0, _specific(c))
    wrong = (orientation == 'portrait' and c.width > c.height) or (orientation == 'landscape' and c.height > c.width)
    return score - (ORIENTATION_PENALTY if wrong else 0)


REUSED_FILE_PENALTY = .015   # prefer a different library file when one is nearly as good


def _specific(c):
    return getattr(c, 'specific', 1.0)   # not measured (e.g. tests) = no penalty


def acceptable(c):
    """Strong matches pass; middling ones only when they fit this moment better than unrelated ideas."""
    if not hasattr(c, 'specific'):
        return True
    return c.score >= STRONG_MATCH or (c.score >= DECENT_MATCH and c.specific >= MIN_SPECIFIC)


def choose(pairs, orientation, min_similarity, alternatives=4):
    """pairs: [(slot, [Candidate])] -> {slot_index: (chosen or None, [alternatives])}."""
    used, used_files, result = set(), set(), {}
    order = sorted(range(len(pairs)), key=lambda i: (-pairs[i][0].moment.priority, pairs[i][0].start))
    for i in order:
        slot, candidates = pairs[i]
        pool = [c for c in candidates if c.duration + 1e-6 >= slot.duration]
        ranked = sorted(pool, key=lambda c: -adjusted(c, orientation))
        good = [c for c in ranked if adjusted(c, orientation) >= min_similarity and usage_key(c) not in used
                and acceptable(c)]
        good.sort(key=lambda c: -(adjusted(c, orientation) - (REUSED_FILE_PENALTY if c.path and c.path in used_files else 0)))
        chosen = good[0] if good else None
        if chosen:
            used.add(usage_key(chosen))
            if chosen.path: used_files.add(chosen.path)
        others = [c for c in ranked if c is not chosen and adjusted(c, orientation) >= min_similarity - .03]
        result[i] = (chosen, others[:alternatives])
    return result
