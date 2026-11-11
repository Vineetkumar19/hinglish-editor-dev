"""Bind explicit per-account quantities before the local model selects media."""
import re

WORDS={'one':1,'two':2,'both':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12}


def profiles(text,workflow):
    found=[]
    for key,target in workflow['destinations'].items():
        match=re.search(r'(?<!\w)(?:'+re.escape(key)+'|@?'+re.escape(target['instagram'])+'|'+re.escape(target.get('youtube',key))+r')(?!\w)',text,re.I)
        if match:found.append((match.start(),key))
    return [key for _,key in sorted(found)]


def account_order(text,workflow):
    from .assistant_sources import literal_locations
    from .assistant_saved_reels import clip_count
    _,instruction=literal_locations(text)
    named=profiles(instruction,workflow)
    count=clip_count(instruction)
    if re.search(r'\b(?:alternat\w*|round.robin|taking turns)\b',instruction,re.I):
        if len(named)<2:raise ValueError('Name the accounts to alternate between.')
        return [named[i%len(named)] for i in range(count)]
    amount=r'(\d+|'+'|'.join(WORDS)+r')'
    matches=list(re.finditer(r'\b'+amount+r'\s+(?:(?:already.created|already.rendered|saved|existing|old|finished|completed)\s+)*(?:reels?|shorts?|clips?|videos?)\b',instruction,re.I))
    if len(matches)>1:
        order=[]
        for i,match in enumerate(matches):
            clause=instruction[match.end():matches[i+1].start() if i+1<len(matches) else len(instruction)]
            destinations=profiles(clause,workflow)
            if len(destinations)!=1:raise ValueError('Give a count for each destination, for example two Reels on cricket and three on gaming.')
            value=int(match[1]) if match[1].isdigit() else WORDS[match[1].lower()]
            order.extend(destinations*value)
        return order
    if len(named)==1:return named*count
    if len(named)>1 and re.search(r'\beach\b',instruction,re.I):return [p for p in named for _ in range(count)]
    if len(named)>1:raise ValueError('Tell me how many Reels to post on each account.')
    return []


def correction_text(snapshot,text,workflow):
    """A short posting answer keeps the destination of its preceding correction."""
    if profiles(text,workflow) or not re.search(r'\b(?:post|upload|publish)\b.*\b(?:now|immediately)\b',text,re.I):return text
    pending=snapshot.get('distribution_pending') or {}
    if pending.get('request'):return pending['request']+'\n'+text
    prior=[m for m in snapshot.get('messages',[]) if m.get('role')=='user' and m.get('id')!=snapshot.get('active_request_message_id')]
    if prior and re.search(r'\bwhat about\b',prior[-1].get('text',''),re.I) and profiles(prior[-1]['text'],workflow):
        return prior[-1]['text']+'\n'+text
    return text


def destination_text(text):
    match=re.search(r'\bwhat about\b(.*)',text,re.I)
    return match[1].split('\n')[0] if match else text


def remaining_order(expected,previous):
    from collections import Counter
    wanted=Counter(expected);done=Counter(previous)
    if any(done[key]>wanted[key] for key in done):raise ValueError('The earlier attempt used different destinations. Its existing posts are preserved; specify the remaining account and count.')
    remaining=wanted-done
    return [profile for profile in dict.fromkeys(expected) for _ in range(remaining[profile])]
