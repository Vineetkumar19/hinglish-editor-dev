"""GSAP easing samples shared with native visual overlays; no extra browser per frame."""
from functools import lru_cache
import json
import math
from pathlib import Path


@lru_cache(maxsize=1)
def library():
    return json.loads(Path(__file__).with_name('gsap_curves.json').read_text('utf-8'))


def ease(name, value):
    curve = library()['curves'][name]
    x = min(1., max(0., float(value))) * (len(curve) - 1)
    left = math.floor(x)
    right = min(left + 1, len(curve) - 1)
    return curve[left] + (curve[right] - curve[left]) * (x - left)
