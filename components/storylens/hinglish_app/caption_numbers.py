"""Comparison-only number forms; displayed script text is never rewritten."""
from functools import lru_cache
import re
from decimal import Decimal


@lru_cache(maxsize=8)
def names(normalizer):
    out={}
    english='zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
    for i,word in enumerate(english):out[normalizer(word)]=str(i)
    for tens,word in enumerate('twenty thirty forty fifty sixty seventy eighty ninety'.split(),2):
        out[normalizer(word)]=str(tens*10)
        for i in range(1,10):out[normalizer(word+' '+english[i])]=str(tens*10+i)
    hindi='शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस'.split()
    for i,word in enumerate(hindi):out[normalizer(word)]=str(i)
    for value,word in [(30,'तीस'),(40,'चालीस'),(50,'पचास'),(60,'साठ'),(70,'सत्तर'),(80,'अस्सी'),(90,'नब्बे'),(100,'सौ'),(100,'hundred'),(1000,'thousand'),(1000,'हजार'),(100000,'lakh'),(1000000,'million')]:out[normalizer(word)]=str(value)
    return out


def numeric_parts(text,normalizer):
    text=str(text)
    if any(c.isdigit() for c in text) and not any(c.isalpha() for c in text):
        return [format(Decimal(n),'f').rstrip('0').rstrip('.') if '.' in n else str(int(n)) for n in re.findall(r'\d+(?:\.\d+)?',text)]
    value=names(normalizer).get(normalizer(text))
    if value is not None:return [value]
    parts=text.split()
    if len(parts)<2:return []
    values=[names(normalizer).get(normalizer(p)) for p in parts]
    if any(v is None for v in values):return []
    result=[];group=0;total=0;present=False
    for value in map(int,values):
        if value>=1000:
            if value>=100000:total=(total+group or 1)*value
            else:total+=(group or 1)*value
            group=0;present=True
        elif value==100:group=(group or 1)*100;present=True
        elif not present or group==0:group=value;present=True
        elif (group>=100 and group%100==0) or (group>=20 and group%10==0 and value<10):group+=value
        else:result.append(total+group);total=0;group=value
    if present:result.append(total+group)
    return [str(v) for v in result]


def number_stream(words,normalizer):
    result=[];i=0
    while i<len(words):
        matched=False
        for size in range(min(6,len(words)-i),0,-1):
            values=numeric_parts(' '.join(words[i:i+size]),normalizer)
            if values:
                result.extend(values);i+=size;matched=True;break
        if not matched:i+=1
    return result


def comparison_key(text,normalizer):
    values=numeric_parts(text,normalizer)
    return ''.join('@n'+n+';' for n in values) if values else normalizer(text)
