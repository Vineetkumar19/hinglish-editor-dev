"""Exact owner-selected finished exports -> editable drafts, never a live post.

This route cannot choose old chat outputs, cut an excerpt, enable a worker or
authorize a post. The ordinary local metadata writer still authors all copy.
"""
from pathlib import Path
import re


def source_paths(text, known=()):
    from .assistant_sources import literal_locations, named_sources, MEDIA
    targets, words = literal_locations(text)
    # The owner typed shorts2 for Shorts 2. Only ignore spaces within that exact
    # name; require word boundaries and refuse multiple matches.
    selected = []
    for target in targets:
        if target.is_file() and target.suffix.lower() in MEDIA:
            selected.append(target)
        elif target.is_dir():
            matches = []
            for p in target.iterdir():
                if not p.is_file() or p.suffix.lower() not in MEDIA or not p.resolve().is_relative_to(target):continue
                pattern = r'\s*'.join(re.escape(part) for part in p.stem.split())
                if re.search(r'(?<!\w)'+pattern+r'(?!\w)', words, re.I):matches.append(p.resolve())
            if len(matches)>1:raise ValueError('More than one video matches that name. Choose the exact file; no old output was substituted.')
            if matches:selected.extend(matches)
            else:selected.extend(named_sources(str(target)+'\n'+words,known))
    return list(dict.fromkeys(selected or named_sources(text,known)))


def prepare(assistant, session_id, text, selected, spec, progress):
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_niche.profiles import account_key
    from hinglish_shorts.source import open_video
    publisher = assistant.state.publisher
    media = [a for a in selected if a.get('kind')!='voice' and Path(a.get('path','')).suffix.lower()=='.mp4']
    if len(media)!=1:
        raise ValueError('Choose one exact finished MP4 export for this upload. Your saved outputs have not been substituted.')
    video = Path(media[0]['path']).resolve(strict=True)
    if not video.is_file():raise ValueError('The selected video is unavailable. Restore that file or attach it again.')
    accounts = {p:publisher.accounts(p).get('youtube',{}) for p in spec['profiles']}
    if any(not a.get('connected') or not a.get('id') for a in accounts.values()):
        raise ValueError('The selected profile has no readable YouTube connection. Open Publishing Studio and check that profile; no upload was started.')
    facts = open_video(video)
    kind = spec['kinds'][0]
    if kind=='auto':kind='short' if facts.height>facts.width and facts.duration<=180 else 'long'
    assistant._update(session_id,status='running',selected='publish',publishing_review=None)
    items = []
    with assistant.state.work_lock,gpu_lock(assistant.root):
        for profile,account in accounts.items():
            if assistant._stopped(session_id):
                assistant._update(session_id,status='stopped',stage='Stopped before saving publishing drafts.');return
            config = {**publisher.settings(profile=profile),'profile':profile}
            prepared = publisher.item(video,kind,'',config,notes=text,progress=progress)
            current = publisher.accounts(profile).get('youtube',{})
            if not current.get('connected') or current.get('id')!=account['id']:
                raise ValueError('The selected YouTube account changed during preparation. Review the profile and try again; nothing was queued.')
            destination = dict(profile_id=profile,platform='youtube',account_id=account['id'],connection_ref=account_key('youtube',profile),verified=True)
            items.extend({**item,'destination':destination,'account_id':account['id'],'connection_ref':destination['connection_ref'],'source_video':str(video)} for item in prepared if item['platform']=='youtube')
        if assistant._stopped(session_id):
            assistant._update(session_id,status='stopped',stage='Stopped before saving publishing drafts.');return
        ids = publisher.store.add_batch(items,publisher.settings(profile=spec['profiles'][0])['daily_time'])
    assistant._message(session_id,'assistant','Your complete video is prepared as an editable YouTube draft for '+', '.join(a['name'] for a in accounts.values())+'. Review it in Publishing Studio. No upload or publication has started.',navigate='publisher',publisher_profile=spec['profiles'][0],publish_ids=ids,command=str(video))
    assistant._update(session_id,status='complete',stage='Publishing drafts ready',pending=None,selected='publish')
    return {'job_ids':ids}
