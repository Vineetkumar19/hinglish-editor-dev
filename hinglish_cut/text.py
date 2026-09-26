import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache


def _raw_tokens(text):
    text = unicodedata.normalize('NFKC',text).casefold()
    # Keep decimal numbers and negations. Do not strip vowels or collapse words.
    return re.findall(r'\d+(?:[.,]\d+)*|[^\W\d_]+',text,re.UNICODE)


def tokens(text, aliases=None):
    """Return normalized words, including configured ASR spelling and phrase aliases.

    A phrase alias lets a fused Whisper word such as ``managardi`` match the
    three spoken words ``mana kar diya``.  Longest source phrases win so a
    specific correction is not hidden by a shorter one.
    """
    result=_raw_tokens(text)
    if not aliases:
        return result
    replacements=[]
    for source,target in aliases.items():
        source_tokens=_raw_tokens(source)
        target_tokens=_raw_tokens(target)
        if source_tokens and target_tokens:
            replacements.append((source_tokens,target_tokens))
    replacements.sort(key=lambda item:len(item[0]),reverse=True)
    normalized=[]
    index=0
    while index<len(result):
        match=next((item for item in replacements if result[index:index+len(item[0])]==item[0]),None)
        if match is None:
            normalized.append(result[index])
            index+=1
        else:
            normalized.extend(match[1])
            index+=len(match[0])
    return normalized


def split_script(text):
    # Newlines are deliberate edit units; also recognize sentence punctuation.
    return [s.strip() for s in re.split(r'\n+|(?<=[!?।])\s+|(?<=\.)\s+',text) if tokens(s)]


@lru_cache(maxsize=100000)
def similarity(a,b):
    if a==b:
        return 1.0
    # Numbers must match exactly; small spelling differences are allowed in words.
    if any(c.isdigit() for c in a+b):
        return 0.0
    ratio = SequenceMatcher(None,a,b,autojunk=False).ratio()
    return ratio if ratio>=.72 else 0.0
