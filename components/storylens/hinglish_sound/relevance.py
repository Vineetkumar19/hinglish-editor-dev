"""Conservative source-subject checks from titles/tags, independent of CLAP.

This guard rejects obvious physical mismatches. It does not identify unknown
audio, replace listening evaluation, or restrict abstract designed accents.
"""
import re


_PATTERNS = {
    'birds':r'\b(?:birds?|birdsong|avian|sparrows?|crows?|ravens?|doves?|pigeons?|seagulls?|gulls?|owls?|ducks?|roosters?|nightingales?)\b',
    'insects':r'\b(?:insects?|crickets?|cicadas?|mosquito(?:es)?|bees?|grasshoppers?|locusts?)\b',
    'horse':r'\b(?:horses?|pon(?:y|ies)|stallions?|equine|hooves|hoof|hoofbeats?|gallop(?:ing)?|canter(?:ing)?|neigh(?:ing)?|whinn(?:y|ying)|clip\s*clop(?:ping)?)\b',
    'foliage':r'\b(?:leaves|leaf|foliage|underbrush)\b|\b(?:grass|bushes|trees|branches|twigs)\s+(?:rustl\w*|sway\w*|crackl\w*)\b',
    'footsteps':r'\b(?:footsteps?|footfalls?|heels?|shoes?|boots?|barefoot|walking|stepping|treading|stomp(?:ing)?)\b|\brunning\s+on\s+(?:gravel|pavement|concrete|stairs|floor|wood|grass)\b',
    'keyboard':r'\b(?:typing|keyboards?|typewriters?|mouse\s+clicks?)\b',
    'combat':r'\b(?:punch(?:ing|es)?|boxing|punching\s+bag|body\s+cutting|fighting)\b',
    'heartbeat':r'\b(?:heartbeats?|heart\s+beating)\b',
    'cloth':r'\b(?:cloth|clothes|clothing|fabric|textiles?|denim|cotton|linen|jackets?|jeans|shirts?|sleeves?)\b',
    'door':r'\b(?:doors?|doorknobs?|doorbells?|gates?|doorways?)\b',
    'water':r'\b(?:water|waterfalls?|rivers?|creeks?|oceans?|sea|faucets?|splashes|splash(?:ing)?|drips?|dripping|streamflow)\b|\b(?:ocean|sea|water)\s+waves?\b',
    'rain':r'\b(?:rain|raining|rainfall|rainwater|raindrops?|downpours?|drizzle|drizzling)\b',
    'wind':r'\b(?:winds?|windy|gusts?|breezes?)\b(?!\s+(?:up|down)\b)',
    'traffic':r'\b(?:traffic|cars?|trucks?|buses|motorcycles?|motorbikes?|vehicles?|lorr(?:y|ies)|engines?)\b',
    'room-hum':r'\broom\s+(?:tone|hum|ambience)\b|\bindoor\s+(?:hum|ambience|room\s+tone)\b|\bfluorescent\b|\b(?:electrical|electric|light|lamp|mains|transformer)\s+(?:light\s+)?(?:hum|buzz|noise)\b|\b(?:refrigerator|fridge|ventilation|air\s+conditioning|ac\s+unit|ceiling\s+fan|extractor\s+fan)\b|\bfan\s+(?:hum|noise|whirr\w*)\b',
    'electronic-static':r'\bstatic\b|\b(?:radio|television|tv|digital|electronic)\s+(?:interference|hiss|noise)\b',
    'crowd':r'\b(?:crowds?|audience|applause|clapping|cheering)\b|\b(?:people|human|human\s+voices)\s+(?:talking|chatter|murmur\w*)\b',
}
_SUBJECTS={name:re.compile(pattern,re.I) for name,pattern in _PATTERNS.items()}
_NEGATED=re.compile(r'\b(?:no|not|without|excluding|lacking)\s+(?:[a-z]+\s+){0,2}$',re.I)
_HUMAN_FEET=re.compile(r'\b(?:heels?|shoes?|boots?|barefoot|human|person|woman|man)\b',re.I)


def _subjects(text):
    text=re.sub(r'[_\-]+',' ',str(text or '').casefold())
    result=set()
    for subject,pattern in _SUBJECTS.items():
        for match in pattern.finditer(text):
            before=text[max(0,match.start()-45):match.start()]
            after=text[match.end():match.end()+12]
            if _NEGATED.search(before) or re.match(r'\s+free\b',after):continue
            result.add(subject)
            break
    # A horse walking is not evidence of human footsteps. Surface/action words
    # must not hide an explicitly named animal behind a generic locomotion tag.
    if 'horse' in result and not _HUMAN_FEET.search(text):result.discard('footsteps')
    return result


def source_matches(asset, sound_type, intent):
    """Return ``(allowed, reason)`` using only authoritative source name/tags.

    A recognized physical source needs overlap with an explicitly requested
    subject. Unknown metadata remains eligible for the separate audio listener.
    Synthetic categories are exempt: an air/wind swoosh can score movement.
    """
    if str(sound_type).casefold() not in ('foley','ambience'):
        return True,'Abstract designed sound category; physical source-subject guard is not applied'
    title=re.sub(r'[_\-]+',' ',str(getattr(asset,'name','') or '')+' '+str(getattr(asset,'path','') or '').replace('\\','/').rsplit('/',1)[-1]).casefold()
    if re.search(r'\b(?:riser|drone|swoosh|whoosh|trailer|interface|notification|spy\s+hit)\b',title):
        return False,'Named designed/synthetic effect is not a verified recording of this physical source'
    if re.search(r'\b(?:cascad\w*|waterfall\w*|river\w*|stream\w*|ocean\w*|waves?)\b',intent,re.I) and re.search(r'\b(?:soda|drink\w*|glass|bottle|faucet|sink|toilet)\b',title):
        return False,'Domestic/drinking water recording does not match the requested natural flowing-water source'
    source=_subjects(str(getattr(asset,'name','') or '')+' '+str(getattr(asset,'text','') or ''))
    requested=_subjects(intent)
    if not source:
        return True,'Source subject unknown in title/tags; listening evaluation is still required'
    common=source & requested
    if common:
        return True,'Source title/tags match requested physical subject(s): '+', '.join(sorted(common))
    return False,('Source title/tags identify '+', '.join(sorted(source))+
                  '; requested physical subject(s): '+(', '.join(sorted(requested)) or 'unknown')+
                  '. No matching source subject; reject this recording')


def delivery_label_only(intent, emotion):
    """A copied delivery label names no audible source or designed sound."""
    normalize=lambda value:' '.join(re.findall(r'\w+',str(value or '').casefold()))
    label=normalize(emotion)
    return bool(label and normalize(intent)==label)
