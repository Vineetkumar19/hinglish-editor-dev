"""Highlight timebase contrast and complete short-caption teaching."""
import hashlib
import json
from tools.publishing_training.curriculum import ROOT, record, plans, COPY_SYSTEM
from tools.publishing_training.revision4 import STATE4
from tools.publishing_training.revision3 import MESSAGES
from tools.publishing_training.revision2 import PLAN_CONTRACT
OUT=ROOT/'output/publishing-training/20261030-v5'
STATE5=STATE4+'''
For highlights, inspect the transcript assigned to the selected highlight. If its own timings are already aligned/remapped, use_finished_highlight. An old stream transcript merely remaining on disk does NOT require retranscription. bind_highlight_transcript applies only when the selected highlight still lacks its own verified timebase. Preserve completed alignment.
'''
COPY5=COPY_SYSTEM+'''
Write a complete short caption or complete noun phrase, at most ten words. Do not leave a dangling word such as "in", "for", "with", "and" or "the" at its end. A shorter complete caption is preferable to a cut-off sentence. Do not copy diagnostic statements like "no dates are mentioned" into public descriptions. State only the supported subject and topic.
'''
CONTRASTS=[
 ('Finished highlight has its own aligned transcript. An obsolete stream transcript is also on disk. Shorts must use the highlight.', 'use_finished_highlight'),
 ('Highlight timings have already been remapped and verified. Archived full-stream speech also exists. No retranscription needed.', 'use_finished_highlight'),
 ('The selected highlight has verified word positions on its own timeline. Do not let unused original-stream timing files override them.', 'use_finished_highlight'),
 ('Highlight exists but ONLY original-stream timing is available. Nothing is aligned to highlight time yet.', 'bind_highlight_transcript'),
 ('Highlight file was rendered. Its assigned transcript still uses stream timestamps; remapping has not been done.', 'bind_highlight_transcript'),
 ('Original stream transcript is preserved as history; selected finished highlight has a separate remapped transcript ready for Shorts.', 'use_finished_highlight'),
 ('New highlight has valid speech text but no verified timing map for the edited export.', 'bind_highlight_transcript'),
 ('Highlight transcript alignment completed successfully. Both original and derived files remain saved. Start Shorts from the finished highlight.', 'use_finished_highlight'),
]
CHECKS=[
 ('aligned-old-archive','Selected finished highlight has verified remapped word timing. The original stream and its older transcript also remain saved as history.', 'use_finished_highlight'),
 ('two-transcripts','Two transcripts exist: archive for the stream and current verified transcript for the finished highlight. Shorts explicitly requested from the highlight.', 'use_finished_highlight'),
 ('own-ready','The highlight export and its own speech alignment have finished. Presence of unused source-stream timing files must not force reprocessing.', 'use_finished_highlight'),
 ('alignment-reused','Shorts use the completed highlight. Its remapped transcript is confirmed correct; original source analysis is still preserved separately.', 'use_finished_highlight'),
 ('stream-only','Finished highlight exists but the sole available word timings belong to the original livestream. No remap has completed.', 'bind_highlight_transcript'),
 ('not-aligned','Highlight text is known, but the export has no verified word positions on its edited timeline.', 'bind_highlight_transcript'),
 ('budget-empty','Processed private video and no publishAt; all allowed attempts to open the schedule controls failed. Retry allowance is exhausted.', 'report_connector_failure'),
 ('budget-left','Exact processed private ID exists; first release-panel attempt failed before submit. There is one retry left.', 'retry_saved_release'),
 ('all-cancel','Latest owner command cancels the entire request including Shorts. Old approval remains in stored history.', 'keep_cancelled'),
 ('part-cancel','Only the long was deleted; current explicit owner permission continues the saved Shorts. Do not restore the long.', 'continue_shorts_only'),
 ('unknown','Video transfer result was lost; neither a usable session nor independently verified remote ID remains.', 'reconcile_upload'),
 ('share','Share may have succeeded, but no exact Instagram permalink is verified after the lost response.', 'reconcile_instagram'),
 ('buffer','Five future local Reel jobs exist, no platform publications independently verified. Report actual delivery status.', 'report_local_buffer'),
 ('parallel','Authorized long upload is advancing and local Shorts generation is independent; neither branch was cancelled.', 'continue_independent_preparation'),
 ('private','YouTube processing succeeded; private ID verified, date absent. Schedule controls failed before submit, with retry budget remaining.', 'retry_saved_release'),
 ('account','Saved video belongs to a different channel from the authorized destination; exact title matches.', 'block_identity_mismatch'),
]

def build():
    if (OUT/'dataset').exists():raise RuntimeError('Do not overwrite frozen splits')
    prev=ROOT/'output/publishing-training/20261030-v4/dataset'
    train=list(map(json.loads,(prev/'train.jsonl').read_text('utf8').splitlines()))
    train+=list(map(json.loads,(prev/'acceptance.jsonl').read_text('utf8').splitlines()))
    for row in train:
        row['id']='v5-dev-'+row['id']
        if row['family']=='state':row['messages'][0]['content']=STATE5
        if row['family']=='paired_copy':row['messages'][0]['content']=COPY5
    for n,(e,d) in enumerate(CONTRASTS):
        for key in ['observation','evidence']:
            train.append(record(f'v5-timebase-{n}-{key}',STATE5,{key:e},dict(decision=d,message=MESSAGES[d]),'state',[d]))
    for subject,profile in [('Bangladesh','cricket'),('Sri Lanka','cricket'),('Mumbai Indians','cricket'),('Delhi Capitals','cricket'),('Minecraft','gaming'),('PUBG Mobile','gaming')]:
        for topic,caption in [('teamwork','Teamwork in focus'),('strategy','A closer look at strategy'),('communication','Communication makes the difference'),('movement','Movement strategy explained')]:
            tags=[subject.replace(' ',''),profile.title(),topic.title()]
            train.append(record('v5-copy-'+subject+'-'+topic,COPY5,dict(profile=profile,spoken_content=f'The segment discusses {topic} in {subject}. No dates or records are stated.'),dict(title=f'{subject}: {topic.title()} Explained',description=f'This segment discusses {topic} in {subject}.\n\n'+' '.join('#'+t for t in tags),tags=[subject,profile.title(),topic.title()],caption_words=caption.split(),instagram_hashtags=tags),'paired_copy',['Complete caption, grounded topic']))
    test=[record('v5-test-'+name,STATE5,dict(current_evidence=e),dict(decision=d,message=MESSAGES[d]),'state',[d]) for name,e,d in CHECKS]
    for row in plans(801,8,True):
        row['id']='v5-'+row['id'];row['messages'][0]['content']=PLAN_CONTRACT;test.append(row)
    for n,(subject,profile) in enumerate([('Nepal','cricket'),('Scotland','cricket'),('Netherlands','cricket'),('West Indies','cricket'),('Dota 2','gaming'),('Hades','gaming'),('Sea of Thieves','gaming'),('Palworld','gaming')]):
        tags=[subject.replace(' ',''),profile.title(),'Strategy']
        test.append(record(f'v5-copy-test-{n}',COPY5,dict(profile=profile,spoken_content=f'This segment covers communication and strategy in {subject}. No statistics or dates are provided.'),dict(title=f'{subject}: Communication and Strategy',description=f'This segment covers communication and strategy in {subject}.\n\n'+' '.join('#'+t for t in tags),tags=[subject,profile.title(),'Strategy'],caption_words=['Communication','and','strategy','in','focus'],instagram_hashtags=tags),'paired_copy',['Grounded; complete caption']))
    # Previously evaluated cases are regression checks, NOT fresh acceptance.
    regression=[]
    for split in ['holdout','acceptance']:
        regression+=list(map(json.loads,(prev/(split+'.jsonl')).read_text('utf8').splitlines()))
    for row in regression:
        if row['family']=='state':row['messages'][0]['content']=STATE5
        if row['family']=='paired_copy':row['messages'][0]['content']=COPY5
    data=OUT/'dataset';data.mkdir(parents=True)
    assert not {r['messages'][1]['content'] for r in train}&{r['messages'][1]['content'] for r in test}
    for name,rows in [('train',train),('holdout',test),('acceptance',regression)]:
        (data/(name+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    manifest=dict(train=len(train),fresh_holdout=len(test),regression_checks=len(regression),acceptance_file_is_regression=True,parent='20261030-v4',epochs=1,synthetic=True,deploy=False,
        corrections=['Already aligned highlight takes precedence over archived stream transcript','Complete captions; omit diagnostic prose'],
        copy_terminal_word_check=True,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.jsonl')})
    (OUT/'curriculum.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest))

if __name__=='__main__':build()
