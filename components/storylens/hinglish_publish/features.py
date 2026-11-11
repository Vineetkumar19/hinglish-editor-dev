"""Owner-selected optional publishing work, independent of model guesses."""
import json
import re
from pathlib import Path


def features(root):
    path=Path(root)/'config.workflow.local.json'
    data=json.loads(path.read_text('utf-8')) if path.exists() else {}
    selected=data.get('content_features',{})
    policy={'burn_in_captions':False,'instagram_captions':False,'publishing_copy':'full',
            'instagram_text':'title_hashtags',
            **selected}
    # Keep explicit legacy minimal/no-text projects readable; the owner's
    # current full-copy policy has its own independent Instagram text setting.
    if 'instagram_text' not in selected:
        if selected.get('instagram_captions'):policy['instagram_text']='caption'
        elif selected.get('publishing_copy')=='minimal' and selected.get('instagram_captions') is False:policy['instagram_text']='none'
    return policy


def instagram_text_mode(root, request=''):
    """Subtitles and a short post title are separate creator choices."""
    request=re.sub(r'\b(?:hastags?|hashtages?|hash\s+tags?)\b','hashtags',request,flags=re.I)
    for clause in re.split(r'[.!?\n]',request.lower()):
        if re.search(r'\b(?:no|without|omit|remove|don.t (?:add|use))\s+(?:the\s+)?titles?\b',clause):
            continue
        if (re.search(r'\btitles?\b',clause) and
            re.search(r'\b(?:add|put|include|use|keep|preserve|retain|only|just|with|sirf)\b',clause) and
            ('youtube' not in clause or re.search(r'\b(?:instagram|insta|ig)\b',clause))):
            return 'title_hashtags' if (re.search(r'\bhash\s*tags?\b',clause)
                or features(root)['instagram_text']=='title_hashtags') else 'title'
    return features(root)['instagram_text']


def title_hashtags(metadata):
    """Reuse the local writer's topic hashtags, without adding caption prose."""
    tags=re.findall(r'(?<!\w)#([A-Za-z][A-Za-z0-9_]*)',metadata.get('description',''))
    if not tags:tags=metadata.get('tags',[])
    chosen=[];seen=set()
    for tag in tags:
        tag=re.sub(r'[^A-Za-z0-9_]','',tag)
        if tag and tag.casefold() not in seen:
            chosen.append('#'+tag);seen.add(tag.casefold())
    return metadata['title'].strip()+'\n\n'+' '.join(chosen[:5])
