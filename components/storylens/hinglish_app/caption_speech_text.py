"""Caption words and formatting remain separate from acoustic comparison keys."""
import re

LETTER_NAMES=('ay bee see dee ee ef jee aitch eye jay kay el em en oh pee cue ar ess tee you vee doubleyou ex why zee').split()


def caption_tokens(script):
    result=[];prefix=[]
    for token in script.split():
        if any(c.isalnum() for c in token):
            result.append({'spoken':token,'text':' '.join(prefix+[token])});prefix=[]
        elif result:result[-1]['text']+=' '+token
        else:prefix.append(token)
    return result


def comparison_variants(text,normalizer):
    variants={normalizer(text)}
    letters=re.sub('[^A-Za-z]','',text)
    if re.fullmatch('[A-Z]{2,6}',letters):
        variants.add(normalizer(' '.join(LETTER_NAMES[ord(c)-65] for c in letters)))
    return {v for v in variants if v}
