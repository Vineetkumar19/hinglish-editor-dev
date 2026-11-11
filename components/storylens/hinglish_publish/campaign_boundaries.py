"""Transcript boundary options; editorial completeness is judged by the local LLM."""
import re
from hinglish_shorts.find import snap


ENDING_WORDS={
    'है','हैं','था','थी','थे','गया','गई','गए','किया','दिया','हुआ','हुई',
    'जीता','जीती','जीते','आउट','एलबीडब्लू','एलबीडब्ल्यू',
    'hai','hain','tha','thi','the','gaya','gayi','gaye','kiya','diya','hua','hui',
    'jeeta','jeeti','jeete','out','aaut','lbw',
}


def candidates(words,pick,duration,limit,used=(),reserved=(),maximum=24):
    """Offer real word spans, independent of script, team names or source topic.

    Boundary cues are options, never a claim that a sentence is complete. Keep the
    local model's original moment among the options. Reserve later planned moments
    so an early refinement cannot consume another clip's entire source interval.
    """
    s0,e0=pick['pieces'][0]
    indices=[i for i,w in enumerate(words) if max(0,s0-40)<=w.start<w.end<=min(duration,e0+55)]
    if not indices:
        return []
    def ending(i):
        return words[i].text.strip(' ।.,!?;:"\'').casefold() in ENDING_WORDS
    def punctuation(i):
        return bool(re.search(r'[.!?।]["\')\]]?$',words[i].text.strip()))
    starts=[i for i in indices if i==0 or punctuation(i-1) or ending(i-1)
            or words[i].start-words[i-1].end>=.2]
    ends=[i for i in indices if i==len(words)-1 or punctuation(i) or ending(i)
          or words[i+1].start-words[i].end>=.2]
    blocked=[*used,*reserved]
    found={}
    def add(a,b,original=False):
        if b<a:
            return
        s,e=snap(words,words[a],words[b],source_duration=duration)
        if not 10<=e-s<=limit-.4:
            return
        if any(max(s,c)<min(e,d) for p in blocked for c,d in p['pieces']):
            return
        key=f'{a}:{b}'
        found[key]={'id':key,'start':s,'end':e,'seconds':round(e-s,2),
                    'original_moment':original or found.get(key,{}).get('original_moment',False)}
    original=[i for i in indices if s0-1e-6<=words[i].start and words[i].end<=e0+1e-6]
    if original:
        add(original[0],original[-1],True)
        # Also offer sentence-level corrections around the original endpoints.
        starts=sorted(set(starts+[original[0]]))
        ends=sorted(set(ends+[original[-1]]))
    for a in starts:
        for b in ends:
            add(a,b)
    options=list(found.values())
    if len(options)<=maximum:
        return options
    anchor=[c for c in options if c['original_moment']]
    others=[c for c in options if not c['original_moment']]
    # Structural sampling only; the model ranks the actual transcripts.
    room=maximum-len(anchor)
    selected=[others[round(i*(len(others)-1)/max(1,room-1))] for i in range(room)]
    return anchor+selected
