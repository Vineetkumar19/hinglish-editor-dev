"""One local-model review and one render per changed Short."""
import json
from types import SimpleNamespace
from hinglish_cut.model import Word


def repair(root,path,progress=print,*,should_stop=lambda:False):
    from hinglish_visuals.brain import open_brain
    from hinglish_shorts.title_review import review,transcripts,VERSION as title_version
    from .proofread import selected,VERSION as caption_version
    from hinglish_shorts.pipeline import rebuild_project,_load_video
    from hinglish_app.durable_json import write
    project=json.loads(path.read_text('utf-8'))
    previous=project.get('caption_words',project['words'])
    # Review the complete original speech, so an earlier bad merge cannot
    # permanently erase a spoken word from later repair passes.
    words=[Word(t,s,e) for t,s,e in project['words']]
    engine=open_brain(root,'ollama',progress=progress)
    from hinglish_publish.campaign import RecordedBrain
    decisions=path.parent/'caption-decisions';decisions.mkdir(exist_ok=True)
    brain=RecordedBrain(engine,decisions)
    try:
        titles=review(brain,project['shorts'],progress)
        checked,changes=selected(brain,words,[SimpleNamespace(pieces=s['pieces']) for s in project['shorts']],
            progress,root=root,video=_load_video(project['video']))
    finally:engine.close()
    if should_stop():raise ValueError('Stopped after local caption review; existing exports are kept.')
    progress('Local review complete; preparing changed caption layers')
    corrected=[[w.text,round(w.start,3),round(w.end,3)] for w in checked]
    write(path.parent/'caption-review-plan.json',{'model':brain.name,'titles':list(titles.values()),
        'changes':changes,'caption_words':corrected})
    def within(rows,pieces):
        return [row for row in rows if any(a<=(row[1]+row[2])/2<b for a,b in pieces)]
    changed=[s['index'] for s in project['shorts'] if within(previous,s['pieces'])!=within(corrected,s['pieces'])]
    shorts=[{**s,'title':titles[s['index']]['title']} for s in project['shorts']]
    if changed or any(a['title']!=b['title'] for a,b in zip(shorts,project['shorts'])):
        progress('Rendering only the Shorts changed by local title/caption review')
        rebuild_project(path,{'shorts':shorts,'caption_words':corrected,'refresh_captions_indices':changed},progress)
        project=json.loads(path.read_text('utf-8'))
    project['title_review']={'version':title_version,'model':brain.name,'items':list(titles.values())}
    project['caption_review']={'version':caption_version,'model':brain.name,
        'changes':project.get('caption_review',{}).get('changes',[])+changes,'number_format':'digits'}
    write(path,project)
    transcripts(path,project)
