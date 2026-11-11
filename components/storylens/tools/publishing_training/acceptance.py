"""Reserved boundary checks, written before v2 inference results are inspected."""
import json
from tools.publishing_training.revision2 import OUT, STATE_CONTRACT, PLAN_CONTRACT, COPY_SYSTEM, messages_for
from tools.publishing_training.curriculum import record, STEPS

def build():
    p=OUT/'dataset/acceptance.jsonl'
    if p.exists():raise RuntimeError('Do not overwrite reserved acceptance cases')
    rows=[]
    cases=[
      ('partial-cancel','Long has been manually cancelled, but only that long schedule. User explicitly says continue three previously authorized Shorts. Do not cancel the Shorts.', 'continue_shorts_only'),
      ('whole-cancel','User says cancel the whole workflow including Shorts. A previous checkpoint has completed Long and permission for Shorts. Which instruction wins?', 'keep_cancelled'),
      ('private-delay','YouTube upload completed and processing completed. It is private with no publishAt. Local UI says Scheduled, but Studio failed before submitting. Which action follows the remote evidence?', 'retry_saved_release'),
      ('caption-not-delivery','Three Instagram captions finished. Three future local Reel jobs are ready. No Share call happened. Report delivery truthfully.', 'report_local_buffer'),
      ('source-transcript','Requested Shorts from finished gaming highlight export with own remapped transcript. The original stream transcript also remains on disk. Which source is used?', 'use_finished_highlight'),
      ('same-name-other-channel','Two channels contain a video with identical title. Receipt ID points to the wrong owner channel. Browser is signed in and ready to schedule.', 'block_identity_mismatch'),
      ('expired-but-no-proof','Old upload session expired. No platform ID. Prior progress was 100% bytes sent, but no final success receipt. Do not infer failure from expiry alone.', 'reconcile_upload'),
      ('fresh-session-no-insert','Upload URI is still usable and tied to source/account. A partial byte offset was acknowledged, then connection dropped. Continue without a new insert.', 'resume_same_session'),
      ('share-double-risk','Instagram may already show this Reel. Share returned a connection error after submission and exact permalink has not been verified. User wants no duplicates.', 'reconcile_instagram'),
      ('schedule-double-risk','Two identical Schedule requests arrived. Same prepared media, same authorization and an existing saved private video ID. No new revision requested.', 'reuse_saved_jobs'),
      ('full-context','Next step has an atomic checkpoint and exact input IDs. Prior long context is huge. It only needs selected source spans, required creator guidance and the saved result.', 'use_compact_checkpoint'),
      ('healthy-network','Long bytes keep advancing. CPU/GPU local Shorts stages are available. Upload may take hours but preparation does not depend on completion.', 'continue_independent_preparation'),
    ]
    for name,evidence,d in cases:
        rows.append(record('reserved-'+name,STATE_CONTRACT,dict(tool_evidence=evidence),dict(decision=d,message=messages_for(d)),'state',[d]))
    for n,(count,now,thumb) in enumerate([(3,False,False),(1,True,False),(4,False,True),(7,True,True),(2,False,False),(6,False,True),(5,True,False),(8,False,True)]):
        path=f'D:\\Editing\\Documentaries\\clip {701+n}.mp4';cover=f'D:\\Covers\\poster {701+n}.png' if thumb else ''
        request=f'Bro this is my video: "{path}". Cricket YouTube long {"post now" if now else "schedule"}; make {count} Shorts from it, schedule YouTube and keep same Reels in Instagram buffer. '+(f'Thumbnail "{cover}".' if cover else 'Skip thumbnail.')
        rows.append(record(f'reserved-plan-{n}',PLAN_CONTRACT,dict(owner_request=request,selected_video=path,selected_thumbnail=cover),
            dict(profile='cricket',video=path,thumbnail=cover,count=count,long_release='post_now' if now else 'schedule',shorts_release='schedule',steps=STEPS),'plan',['Exact values']))
    for n,(subject,profile) in enumerate([('Australia','cricket'),('New Zealand','cricket'),('Counter-Strike 2','gaming'),('Fall Guys','gaming')]):
        tags=[subject.replace(' ','').replace('-',''),'Teamwork','Strategy']
        rows.append(record(f'reserved-copy-{n}',COPY_SYSTEM,dict(profile=profile,spoken_content=f'The clip discusses communication and strategy for {subject}. No score, record, winner or year is stated.'),
            dict(title=f'{subject}: Communication and Strategy',description=f'This clip discusses communication and strategy for {subject}.\n\n'+' '.join('#'+t for t in tags),tags=[subject,'Teamwork','Strategy'],caption_words=['Communication','shapes','the','strategy.'],instagram_hashtags=tags),'paired_copy',['Grounded topic; concise caption']))
    known={r['messages'][-2]['content'] for file in ['train','holdout'] for r in map(json.loads,(OUT/f'dataset/{file}.jsonl').read_text('utf8').splitlines())}
    assert not any(r['messages'][-2]['content'] in known for r in rows)
    p.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    print('Saved 24 reserved acceptance cases; not used in training.')

if __name__=='__main__':build()
