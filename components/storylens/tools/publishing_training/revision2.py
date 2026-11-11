"""Corrective continuation. Old holdout becomes development data, never fresh proof."""
import json
from pathlib import Path
from tools.publishing_training.curriculum import ROOT, LESSONS, PLAN_SYSTEM, STATE_SYSTEM, COPY_SYSTEM, record, plans

OUT=ROOT/'output/publishing-training/20261030-v2'
PLAN_CONTRACT=PLAN_SYSTEM+' Exact values: profile="cricket"; long_release="post_now" for immediate publication or "schedule" for later. Never use public_now. Return the exact requested paths and counts.'
MEANINGS={
 'retry_saved_release':'Known processed private YouTube ID, missing schedule, failure before release submission; retry release only.',
 'reconcile_upload':'Unknown YouTube upload result and no usable saved upload session; do not send bytes again.',
 'resume_same_session':'Usable bound resumable session and acknowledged partial bytes; query its offset then continue that session.',
 'query_same_session':'Final upload response lost but usable saved session remains; query that session for completion.',
 'continue_independent_preparation':'Healthy long transfer can run alongside independent local Shorts preparation.',
 'wait_processing':'Saved YouTube ID exists but platform processing is not finished.',
 'accept_verified_schedule':'Exact channel, ID, copy and future release timestamp independently verified.',
 'report_local_buffer':'Local future Reel queue exists; no verified publication yet.',
 'dispatch_due_job':'Due authorized Reel, exact identity and online connector, no previous submission uncertainty.',
 'wait_connector':'Due Reel cannot start because browser connector is offline; retain same job.',
 'reconcile_instagram':'Share may have succeeded; verify exact remote post before any repeat submission.',
 'accept_verified_publication':'Exact Instagram account and post permalink independently verified.',
 'reuse_saved_jobs':'Repeated click with existing queue/remote IDs; reuse those jobs, no duplicate.',
 'keep_cancelled':'Owner cancelled entire current workflow; never auto-rearm.',
 'continue_shorts_only':'Owner cancelled/deleted ONLY the long post; Shorts remain explicitly authorized.',
 'block_identity_mismatch':'Wrong account or changed source hash; no publishing action.',
 'review_changed_copy':'Copy changed after authorization; review revision before release.',
 'report_connector_failure':'Bounded identical release retries exhausted; stop and report connector problem.',
 'correct_failed_copy_only':'Keep finished media and accepted text; regenerate rejected copy only.',
 'prepare_without_thumbnail':'Thumbnail omitted; it is optional for Long/Highlights.',
 'use_finished_highlight':'Shorts requested from completed gaming highlight, not source stream.',
 'bind_highlight_transcript':'Highlight exists but timings still refer to stream; remap or transcribe highlight.',
 'report_buffer_gap':'Requested clip count does not fill five-day buffer; report gap, do not add clips.',
 'clear_view_only':'Clear UI details without deleting schedules, media or receipts.',
 'wait_release_authorization':'Current instruction is prepare/review only; old posting consent is insufficient.',
 'show_unknown_progress':'No measured work total; show elapsed/heartbeat, no invented percent/ETA.',
 'show_measured_progress':'Known completed/total units; report actual fraction.',
 'reconcile_missed_slot':'Release timestamp passed before completion; apply explicit policy or ask, never silently publish now.',
 'use_compact_checkpoint':'Next stage reads saved identity and relevant evidence, not whole previous conversation.',
 'report_capability_gap':'Requested route is not implemented; do not pretend supported.',
 'wait_due_time':'Reel is ready but its scheduled time is still future; do not post early.',
 'verify_cancellation':'Cancel clicked but remote scheduled timestamp still exists; do not claim cancellation.',
 'accept_verified_cancellation':'Remote private and no release date verified after cancel; keep private.'
}
STATE_CONTRACT=STATE_SYSTEM+'\nAllowed decision vocabulary and meanings:\n'+ '\n'.join(k+': '+v for k,v in MEANINGS.items())+'\nPriority: current cancellation and identity checks override previous permission. Recommendations never replace tool validation. A local queue is not a remote receipt. No usable session means no blind resend. Match message to decision; keep counts grounded.'

# New evaluation authored independently of the v1 test wordings; includes mixed
# successful checkpoints with conflicting latest state. Targets are withheld.
CHECKS=[
 ('cancelled-even-ready','Three completed clips and valid release approval exist. Latest owner action cancelled the entire workflow. A supervisor wants to continue it.', 'keep_cancelled'),
 ('deleted-long-only','User removed the completed long post on YouTube but explicitly wants its three locally saved clips scheduled. Do we restore the long?', 'continue_shorts_only'),
 ('timeout-no-session','Network ended before receiving a video ID. No recoverable transfer URI exists. Worker is alive again. Should it initiate another upload?', 'reconcile_upload'),
 ('expired-no-id','Saved upload transfer address expired and remote completion is unknown. The owner requested unattended recovery. Choose next action.', 'reconcile_upload'),
 ('known-offset','The encrypted session is bound to this source/account and still usable. Server acknowledged 1048576 bytes before a connection drop. No completed ID yet.', 'resume_same_session'),
 ('lost-last-response','Final chunk was sent. Its reply disappeared; the same encrypted upload URI is usable. We need the result without creating a second video.', 'query_same_session'),
 ('private-with-good-copy','Clip has a processed private YouTube ID and correct metadata. No publishAt. Opening the schedule panel failed before any submit.', 'retry_saved_release'),
 ('private-is-not-scheduled','Saved private ID, processing finished, exact metadata. UI displayed a proposed date but API publishAt is empty and submit never happened.', 'retry_saved_release'),
 ('transcoding','Remote ID and private privacyStatus verified. processingStatus is processing. No error and the upload transfer is already done.', 'wait_processing'),
 ('verified-future','Readback confirms expected video ID, owner channel, metadata and the exact requested future publishAt. Visibility is private until release.', 'accept_verified_schedule'),
 ('buffer-seven','Seven future Instagram jobs are stored locally. Their authorizations are valid. None has a platform post receipt. Are they published?', 'report_local_buffer'),
 ('future-no-early','This authorized Reel is ready. Connector online. Due time is two hours away. Should dispatch start immediately?', 'wait_due_time'),
 ('due-offline','Reel due time passed ten minutes ago, source/account match and no Share attempted. Chrome connector heartbeat expired.', 'wait_connector'),
 ('due-online','This Reel is due now. Exact account and unchanged file verified; approved copy, live Chrome connector, no prior attempt. Worker can claim the same job once.', 'dispatch_due_job'),
 ('share-uncertain','Share was activated for the authorized account, then the browser stopped. Neither success permalink nor confirmed failure exists.', 'reconcile_instagram'),
 ('real-instagram','Readback verified the published Reel permalink on the exact authorized Instagram account. Local receipt matches this clip.', 'accept_verified_publication'),
 ('double-click','The same preparation received Schedule twice. The first call already saved a queue record and private remote ID. Is another insert needed?', 'reuse_saved_jobs'),
 ('channel-conflict','Source and title match perfectly. Remote owner channel differs from authorized target. Scheduling dialog is currently available.', 'block_identity_mismatch'),
 ('hash-conflict','A file was replaced at the same path. Its current hash differs from the prepared source. Old upload receipt still exists.', 'block_identity_mismatch'),
 ('new-copy','User edited description after approving release. The remote saved text still contains the previous revision.', 'review_changed_copy'),
 ('retry-limit','Every configured retry of the Studio dialog failed identically; release retry budget is exhausted. Private upload still exists.', 'report_connector_failure'),
 ('one-caption-bad','Three exports and transcripts are saved. Copy for clips one and three passed; only clip two invented an unsupported year.', 'correct_failed_copy_only'),
 ('optional-cover','User supplied a valid documentary path and explicitly omitted the optional cover image. Preparation has not started.', 'prepare_without_thumbnail'),
 ('highlight-export','Source gaming stream is 240 minutes. Finished highlight file is 9 minutes with valid own timings. User wants two Shorts from that highlight.', 'use_finished_highlight'),
 ('wrong-timing','A 9-minute highlight export exists. Available speech word positions still belong to the 240-minute stream; they have not been remapped.', 'bind_highlight_transcript'),
 ('buffer-gap','Owner authorized exactly two clips. Those fill two distinct future days, while usual minimum is five days. May we create three more automatically?', 'report_buffer_gap'),
 ('clear-completed','Owner requests Clear for completed preparation details. Its published video and future schedule receipts remain valid.', 'clear_view_only'),
 ('review-first','Old chat approved automatic posting. Latest request says prepare drafts only, I will review before release.', 'wait_release_authorization'),
 ('unknown-duration','Worker heartbeat is fresh but current inference has no measurable total units. What percentage or remaining time can UI truthfully show?', 'show_unknown_progress'),
 ('measured','A measured operation completed 6 of 8 batches. Show progress from those units.', 'show_measured_progress'),
 ('missed-release','Authorized schedule timestamp elapsed before processing finished. Video remains private and no missed-slot permission was given.', 'reconcile_missed_slot'),
 ('next-stage','Long transcription and copy are saved atomically. Next clip stage requires source ID and selected speech spans. Should all old chat be retained?', 'use_compact_checkpoint'),
 ('unsupported-route','Tool capability manifest limits the one-prompt orchestration route to cricket. Owner requests gaming full workflow; separate gaming preparation tools do exist.', 'report_capability_gap'),
 ('cancel-unverified','User clicked Cancel schedule; readback still shows the same future publishAt. No independent private-without-date confirmation yet.', 'verify_cancellation'),
 ('cancel-confirmed','After requested cancellation, exact remote ID now verifies private visibility with no publishAt.', 'accept_verified_cancellation'),
 ('slow-but-active','Long byte transfer advances every check. Shorts local processing has not started and does not require remote ID. Should it wait?', 'continue_independent_preparation'),
]

def messages_for(decision):
    if decision=='report_local_buffer':return 'The Reels are buffered locally. Publication is not verified; keep their authorized future delivery times.'
    if decision=='show_measured_progress':return '75% complete: 6 of 8 batches finished, 2 remain.'
    return next(m for _,_,d,m in LESSONS if d==decision)

def build():
    if (OUT/'dataset/train.jsonl').exists():raise RuntimeError('Versioned curriculum already exists')
    old=ROOT/'output/publishing-training/20261030-v1/dataset'
    train=[]
    for source in ['train','holdout']:
        for row in map(json.loads,(old/(source+'.jsonl')).read_text('utf8').splitlines()):
            row['id']='v2-dev-'+row['id']
            if row['family']=='plan':row['messages'][0]['content']=PLAN_CONTRACT
            if row['family']=='state':
                row['messages'][0]['content']=STATE_CONTRACT
                target=json.loads(row['messages'][-1]['content'])
                if target['decision']=='report_local_buffer':target['message']=messages_for(target['decision'])
                row['messages'][-1]['content']=json.dumps(target)
            train.append(row)
    for i,(_,obs,d,m) in enumerate(LESSONS):
        for j,question in enumerate(['Choose the next allowed action.','Keep completed work and explain only the unfinished step.']):
            train.append(record(f'v2-variation-{i}-{j}',STATE_CONTRACT,dict(request=question,evidence=obs,prior_context='Use the checkpoint; no need to remember the earlier conversation.'),
                dict(decision=d,message=messages_for(d) if d=='report_local_buffer' else m),'state',[d]))
    test=[]
    for name,evidence,decision in CHECKS:
        test.append(record('v2-test-'+name,STATE_CONTRACT,dict(latest_tool_evidence=evidence),dict(decision=decision,message=messages_for(decision)),'state',[decision]))
    for i,row in enumerate(plans(211,12,True)):
        row['id']='v2-'+row['id'];row['messages'][0]['content']=PLAN_CONTRACT
        obj=json.loads(row['messages'][1]['content']);expected=json.loads(row['messages'][-1]['content'])
        obj['owner_request']=f"Use {obj['selected_video']} for cricket. {'Post the long immediately' if expected['long_release']=='post_now' else 'Schedule the long for later'}. Exactly {expected['count']} short clips, scheduled to YouTube and buffered for Instagram. Cover: {obj['selected_thumbnail'] or 'not supplied'}."
        row['messages'][1]['content']=json.dumps(obj);test.append(row)
    for i,(name,profile) in enumerate([('Gujarat Titans','cricket'),('Lucknow Super Giants','cricket'),('Apex Legends','gaming'),('Fortnite','gaming')]):
        tags=[name.replace(' ',''),'Teamwork','Strategy'];caption=['Teamwork','guides','the','next','move.']
        test.append(record(f'v2-copy-{i}',COPY_SYSTEM,dict(profile=profile,spoken_content=f'The segment explains how communication and teamwork guide strategy in {name}.'),
            dict(title=f'{name}: Teamwork and Communication',description=f'This segment discusses teamwork and communication in {name}.\n\n'+' '.join('#'+t for t in tags),tags=[name,'Teamwork','Strategy'],caption_words=caption,instagram_hashtags=tags),'paired_copy',['Grounded named subject; short IG caption']))
    from tools.sound_training.train import validate_split
    validate_split(train,test)
    (OUT/'dataset').mkdir(parents=True)
    for name,rows in [('train',train),('holdout',test)]:
        (OUT/f'dataset/{name}.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf8')
    info=dict(train=len(train),holdout=len(test),parent='20261030-v1',synthetic=True,old_holdout_now_development=True,
        changes=['Explicit exact plan enums','Complete action vocabulary meanings supplied equally to base and adapter','Cancellation/identity/uncertain-result boundaries','New mixed-state holdout'],
        deployment=False,live_actions=False)
    (OUT/'curriculum.json').write_text(json.dumps(info,indent=2),encoding='utf8');print(json.dumps(info))

if __name__=='__main__':build()
