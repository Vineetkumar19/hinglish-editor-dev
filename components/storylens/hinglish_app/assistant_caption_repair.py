"""A normal Storylens chat command repairs editable Shorts, without overlaying old captions."""
from pathlib import Path
import re


def requested(text):
    if re.match(r'^\s*(?:how|why|what|explain)\b',text,re.I):return False
    if re.search(r"\b(?:do not|don.t|never)\s+(?:fix|repair|correct|improve|refresh|regenerate|redo|update)\b",text,re.I):return False
    if re.search(r'\b(?:youtube|yt|metadata|description)\b',text,re.I) and not re.search(r'\b(?:captions?|subtitles?|headings?)\b',text,re.I):return False
    return bool(re.search(r'\b(?:fix|repair|correct|improve|refresh|regenerate|redo|update)\b'
        r'[^.!?;\n]{0,65}\b(?:captions?|subtitles?|headings?|titles?)\b',text,re.I))


def execute(assistant,session_id,text,snapshot,progress):
    if not requested(text) or re.search(r'[A-Za-z]:[\\/]|\b(?:another|different)\s+(?:video|file)\b',text,re.I):return False
    base=(assistant.root/'output/shorts').resolve()
    projects=sorted({Path(p).resolve().parent/'shorts-project.json' for p in snapshot.get('shorts_paths',[])})
    projects=[p for p in projects if p.is_relative_to(base) and p.is_file()]
    if not projects:return False
    from hinglish_captions.repair_project import repair
    from .assistant_media import outputs
    assistant._update(session_id,status='running',stage='Local models are repairing the saved Shorts captions and headings')
    repaired=[]
    with assistant.state.work_lock:
        for project in projects:
            if assistant._stopped(session_id):raise ValueError('Stopped; completed local edits are kept.')
            repair(assistant.root,project,progress,should_stop=lambda:assistant._stopped(session_id))
            repaired+=outputs(assistant.root,{'tool':'shorts'},{'folder':str(project.parent)},project.parent,progress)
    if assistant._stopped(session_id):
        assistant._update(session_id,status='stopped',stage='Stopped after caption repair. No publishing handoff started.')
        return True
    # Old uploaded receipts belong to their old bytes. Keep them as history;
    # this local revision is not a new upload and never replaces a remote video.
    archived=list(snapshot.get('prior_publishing_reviews',[]))
    if snapshot.get('publishing_review'):archived.append(snapshot['publishing_review'])
    assistant._message(session_id,'assistant',f'The local models repaired the saved caption layers and headings for {len(repaired)} Shorts. '
        'The same selected moments were reused. These are revised local exports; existing YouTube uploads have not changed.',videos=repaired)
    assistant._update(session_id,status='complete',stage='Revised local Shorts ready for review',last_paths=repaired,shorts_paths=repaired,
        publishing_review=None,campaign=None,campaign_memory_ref=None,prior_publishing_reviews=archived[-20:],
        caption_repair={'projects':list(map(str,projects)),'needs_new_publishing_review':True})
    # A repair alone never publishes. An explicit continuation may hand the
    # revised exports back to this chat's original workflow without re-extraction.
    pipeline=snapshot.get('pipeline') or {}
    steps=pipeline.get('steps') or []
    continuing=bool(re.search(r'\b(?:resume|continue|complete)\b.{0,35}\b(?:publishing|workflow)\b',text,re.I)
        and not re.search(r"\b(?:do not|don.t|never|no)\s+(?:upload|post|publish|resume|continue)\b",text,re.I))
    if continuing and steps and steps[-1]['tool']=='distribute':
        from .assistant_distribution import from_outputs
        from .assistant_publishing_context import schedule_literals
        options={**steps[-1]['options'],**schedule_literals(text)}
        request=pipeline.get('request','')+'\n'+text
        assistant._update(session_id,status='running',stage='Preparing the repaired Shorts for the requested workflow',
            pipeline={**pipeline,'request':request,'automatic':True,'phase':'preparing','authorized_review':'','next_retry':0})
        from_outputs(assistant,session_id,options,request,progress)
    return True
