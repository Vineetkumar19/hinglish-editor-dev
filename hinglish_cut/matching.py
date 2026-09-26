"""Bounded global choice of ordered script matches, across unordered source takes."""
from .model import Selection
from .text import tokens, similarity


def candidates(script, transcript, settings):
    target=tokens(script,settings.aliases)
    raw_observed=[]
    spans=[]
    for i,w in enumerate(transcript.words):
        ts=tokens(w.text)
        raw_observed.extend(ts)
        spans.extend([(i,i+1)]*len(ts))
    # Apply aliases across the whole take, rather than to each individual
    # word. This preserves corrections such as "ka mil" -> "tamil" while
    # retaining the original word span needed for editing.
    replacements=[]
    for source,replacement in settings.aliases.items():
        source_tokens=tokens(source)
        replacement_tokens=tokens(replacement)
        if source_tokens and replacement_tokens:
            replacements.append((source_tokens,replacement_tokens))
    replacements.sort(key=lambda item:len(item[0]),reverse=True)
    observed=[]
    indices=[]
    position=0
    while position<len(raw_observed):
        match=next((item for item in replacements
                    if raw_observed[position:position+len(item[0])]==item[0]),None)
        if match is None:
            observed.append(raw_observed[position])
            indices.append(spans[position])
            position+=1
        else:
            source_span=(spans[position][0],spans[position+len(match[0])-1][1])
            observed.extend(match[1])
            indices.extend([source_span]*len(match[1]))
            position+=len(match[0])
    if not target or not observed:
        return []
    def distance(window):
        """Word edit distance for one possible spoken phrase."""
        previous=list(range(len(window)+1))
        for i,expected in enumerate(target,1):
            current=[i]
            for j,heard in enumerate(window,1):
                current.append(min(
                    previous[j-1]+1-similarity(expected,heard),
                    previous[j]+1,
                    current[j-1]+1,
                ))
            previous=current
        return previous[-1]

    # Test every compact source window.  This is deliberately bounded: a
    # spoken line is short, and choosing the smallest equally good window
    # prevents a cut from swallowing the next script line.
    n=len(observed)
    found=[]
    maximum_window=min(n,max(len(target)+4,len(target)*2))
    for start in range(n):
        for end in range(start+1,min(n,start+maximum_window)+1):
            score=1-distance(observed[start:end])/max(len(target),end-start,1)
            if score<settings.match_threshold:
                continue
            first,last=indices[start][0],indices[end-1][1]
            # Long gaps can indicate abandoned takes. Penalize excessive duration.
            duration=transcript.words[last-1].end-transcript.words[first].start
            score-=max(0,duration-max(12,len(target)*1.8))*.005
            found.append((score,first,last))
    # Nearby alternate endpoints of the same utterance are one candidate.
    distinct=[]
    for c in sorted(found,key=lambda value:(-value[0],value[2]-value[1],value[1])):
        if any(max(c[1],d[1])<min(c[2],d[2]) for d in distinct):
            continue
        distinct.append(c)
        if len(distinct)>=settings.candidates_per_line:
            break
    return distinct


def arrange(lines, transcripts, settings):
    per_line=[]
    for i,line in enumerate(lines):
        pool=[]
        for t in transcripts:
            for score,start,end in candidates(line,t,settings):
                pool.append(Selection(i,line,t.media.id,start,end,score))
        pool.sort(key=lambda c:(-c.score,c.media_id,c.first_word))
        pool=pool[:settings.candidates_per_line]
        for c in pool:
            others=[x for x in pool if x is not c]
            c.ambiguous=any(abs(c.score-x.score)<=settings.ambiguity_margin for x in others)
            c.alternatives=[{'media_id':x.media_id,'first_word':x.first_word,'last_word':x.last_word,'score':round(x.score,4)} for x in others[:3]]
        per_line.append(pool)
    beam=[(0.0,[],{})]
    for i,pool in enumerate(per_line):
        expanded=[]
        for score,chosen,used in beam:
            expanded.append((score-.75,chosen+[Selection(i,lines[i],None)],used))
            for c in pool:
                if any(max(c.first_word,a)<min(c.last_word,b) for a,b in used.get(c.media_id,[])):
                    continue
                next_used={k:list(v) for k,v in used.items()}
                next_used.setdefault(c.media_id,[]).append((c.first_word,c.last_word))
                expanded.append((score+c.score,chosen+[c],next_used))
        beam=sorted(expanded,key=lambda x:x[0],reverse=True)[:settings.beam_width]
    return beam[0][1] if beam else []
