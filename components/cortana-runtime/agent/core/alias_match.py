"""Shared friendly-name resolution for the app/folder allowlists.

The model does not reliably echo the exact alias string from config. It
says "downloads", "my Downloads", "the downloads folder", "Download".
Exact-key lookup rejected all of those, which is a large part of why
"open my downloads" appeared to do nothing.

This resolves a spoken/typed name against the configured aliases with:
  1. exact match
  2. case-insensitive match
  3. match after stripping filler words ("my", "the", "folder", "open")
  4. substring match either direction
  5. small edit-distance match (handles STT typos: "documnets")

Deliberately conservative: it only ever returns a key that is already in
the allowlist, so this loosens *naming*, never *permissions*.
"""

import re

_FILLER = {
    "my", "the", "a", "an", "please", "open", "folder", "directory",
    "dir", "app", "application", "up", "go", "to", "show", "me",
}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = curr
    return prev[-1]


def _normalize(value: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", (value or "").lower())
    kept = [w for w in words if w not in _FILLER]
    return " ".join(kept or words)


def resolve_alias(name: str, aliases: dict) -> str | None:
    """Returns the matching key from `aliases`, or None."""
    if not aliases:
        return None

    if name in aliases:
        return name

    lookup = {k.lower(): k for k in aliases}
    raw = (name or "").strip()
    if raw.lower() in lookup:
        return lookup[raw.lower()]

    target = _normalize(raw)
    if not target:
        return None

    norm_to_key = {}
    for k in aliases:
        norm_to_key.setdefault(_normalize(k), k)

    if target in norm_to_key:
        return norm_to_key[target]

    # Substring either direction — "downloads folder" vs "Downloads".
    for norm, key in norm_to_key.items():
        if norm and (norm in target or target in norm):
            return key

    # Last resort: closest key within a small edit distance.
    best_key, best_dist = None, None
    for norm, key in norm_to_key.items():
        d = _levenshtein(target, norm)
        if best_dist is None or d < best_dist:
            best_key, best_dist = key, d
    if best_key is not None and best_dist is not None and best_dist <= max(2, len(target) // 3):
        return best_key

    return None
