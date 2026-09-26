"""Score candidate footage against each moment and pick the best clip, never repeating one."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from .stock import cached_name, download

LIBRARY_BONUS = .01          # prefer the creator's own footage when it is equally good
ORIENTATION_PENALTY = .03    # a landscape clip in a vertical reel loses most of the frame


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
    for c in candidates:
        if c.source != 'library' and c not in ready:
            c.score = -1.0


def usage_key(c):
    return f'{c.path}#{int(c.offset // 5)}' if c.source == 'library' else c.id


def adjusted(c, orientation):
    score = c.score + (LIBRARY_BONUS if c.source == 'library' else 0)
    wrong = (orientation == 'portrait' and c.width > c.height) or (orientation == 'landscape' and c.height > c.width)
    return score - (ORIENTATION_PENALTY if wrong else 0)


def choose(pairs, orientation, min_similarity, alternatives=4):
    """pairs: [(slot, [Candidate])] -> {slot_index: (chosen or None, [alternatives])}."""
    used, result = set(), {}
    order = sorted(range(len(pairs)), key=lambda i: (-pairs[i][0].moment.priority, pairs[i][0].start))
    for i in order:
        slot, candidates = pairs[i]
        pool = [c for c in candidates if c.duration + 1e-6 >= slot.duration]
        ranked = sorted(pool, key=lambda c: -adjusted(c, orientation))
        good = [c for c in ranked if adjusted(c, orientation) >= min_similarity]
        chosen = next((c for c in good if usage_key(c) not in used), None)
        if chosen:
            used.add(usage_key(chosen))
        others = [c for c in ranked if c is not chosen and adjusted(c, orientation) >= min_similarity - .03]
        result[i] = (chosen, others[:alternatives])
    return result
