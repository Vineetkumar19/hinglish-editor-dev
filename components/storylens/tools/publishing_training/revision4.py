"""Bounded retry contrast correction with replay and a new frozen test split."""
import hashlib
import json
from tools.publishing_training.curriculum import ROOT, record, plans, COPY_SYSTEM
from tools.publishing_training.revision3 import STATE, MESSAGES
from tools.publishing_training.revision2 import PLAN_CONTRACT
OUT=ROOT/'output/publishing-training/20261030-v4'
STATE4=STATE.replace('If release submission never happened, retry_saved_release, never wait_processing.',
    'If release submission never happened AND retry budget remains, retry_saved_release, never wait_processing.')+'''
Retry budget is a hard guard: exhausted or zero remaining attempts means report_connector_failure, even if the upload is processed/private and no release submission occurred. Do not reset the budget or recommend one more identical retry. Cancellation and identity checks still take priority. Unknown remote outcomes require reconciliation, not blind retries.
'''

NEW=[
 ('limit-a','Upload processed/private, no schedule. All 3 of 3 release-panel retries failed. No remaining attempts. No submit took place.', 'report_connector_failure'),
 ('limit-b','Correct private ID and metadata are saved. The schedule panel is still unavailable after the configured retry maximum; budget remaining is zero.', 'report_connector_failure'),
 ('limit-c','Private upload is healthy. Release status failed before submission; supervisor consumed every authorized retry. User wants reliability, not an endless loop.', 'report_connector_failure'),
 ('limit-d','Remote video exists and processing succeeded. A fourth identical release retry is proposed after the maximum three attempts were used.', 'report_connector_failure'),
 ('limit-e','Video upload did succeed. Scheduling failed repeatedly before submit. No retry allowance remains; keep the successful upload.', 'report_connector_failure'),
 ('retry-a','Private processed video is saved. Schedule dialog failed before any submission. Retry budget: 2 remaining.', 'retry_saved_release'),
 ('retry-b','Upload complete, processing succeeded, no publishAt. First release-panel attempt failed; policy allows two more attempts.', 'retry_saved_release'),
 ('retry-c','Exact processed/private ID exists. Unsubmitted release step failed transiently and retry allowance remains.', 'retry_saved_release'),
]
TEST=[
 ('spent','The saved clip finished transcoding and remains private. Release controls failed before submission, and the last permitted retry has already failed. What next?', 'report_connector_failure'),
 ('zero','The only unfinished work is scheduling a processed private upload. Browser still cannot open visibility; remaining retry counter is 0.', 'report_connector_failure'),
 ('maxed','An authorized private video has no publishAt. The scheduling panel timed out on the full allowed retry budget. No additional retry is authorized.', 'report_connector_failure'),
 ('no-extra','After exhausting all release attempts the supervisor proposes one more try because no submit occurred. The upload is complete and private.', 'report_connector_failure'),
 ('last-failed','Attempt 5 was the last allowed scheduling attempt and just failed to open Studio controls. Keep the already processed private upload.', 'report_connector_failure'),
 ('available','The uploaded private video is fully processed. The first unsubmitted release attempt failed; one retry is still available.', 'retry_saved_release'),
 ('two-left','Video ID, owner and approved metadata match. Processing succeeded, schedule absent, release failed BEFORE submit. Two retry attempts remain.', 'retry_saved_release'),
 ('never-processing','Transcoding has finished successfully; waiting cannot create publishAt. The unsent release step failed once and its retry allowance is positive.', 'retry_saved_release'),
 ('schedule-ok','A remote read verifies the exact intended future release timestamp, correct account, approved metadata and existing video ID.', 'accept_verified_schedule'),
 ('processing','Bytes are uploaded but the platform explicitly reports that transcoding is still in progress. No release failure yet.', 'wait_processing'),
 ('cancel-wins','The entire request was cancelled after approval. Private upload is saved and release retries remain, but the owner has not resumed the request.', 'keep_cancelled'),
 ('identity-wins','Private processed video is saved and a release retry is available, but the current account is not the authorized channel.', 'block_identity_mismatch'),
 ('all-stop','Owner said stop BOTH branches. Completed Shorts and old authorizations remain; supervisor must not revive either branch.', 'keep_cancelled'),
 ('limited-stop','Only the long was removed. User currently confirms continuation for the saved three Shorts and says never restore the long.', 'continue_shorts_only'),
 ('no-transfer','Remote upload result is unknown and no usable resumable URI or confirmed ID survived. Local progress previously reached full bytes.', 'reconcile_upload'),
 ('remaining-session','An acknowledged partial offset and valid encrypted source-bound transfer session survive. Connection was lost before completion.', 'resume_same_session'),
 ('share-unknown','The approved Instagram Share request was sent, but its response vanished. No exact permalink or confirmed rejection exists.', 'reconcile_instagram'),
 ('local-only','Six authorized Reels are ready in the future local queue. Their captions are saved, but no Instagram post receipt exists.', 'report_local_buffer'),
 ('future','The Reel is ready with approval and a healthy connector; the authorized release time has not arrived.', 'wait_due_time'),
 ('offline','The Reel is due and approved with exact account and file confirmed. Browser connection is offline; no submission has been attempted.', 'wait_connector'),
 ('parallel','Long upload continues to advance slowly. Independent local Shorts extraction is authorized and ready; neither branch was cancelled.', 'continue_independent_preparation'),
 ('highlight','Use the completed 11-minute gaming highlight with aligned speech to make three Shorts. The original 190-minute stream must not be selected.', 'use_finished_highlight'),
 ('new-copy','The owner altered the description after release approval; remote saved text is the previous version.', 'review_changed_copy'),
 ('cancel-pending','Cancellation request was submitted but readback still contains the scheduled release date for that exact private video.', 'verify_cancellation'),
]

def build():
    if (OUT/'dataset').exists():raise RuntimeError('Do not overwrite frozen splits')
    prev=ROOT/'output/publishing-training/20261030-v3/dataset'
    original=list(map(json.loads,(prev/'train.jsonl').read_text('utf8').splitlines()))
    train=list(map(json.loads,(prev/'holdout.jsonl').read_text('utf8').splitlines()))
    # Balanced replay: previous examples stay in parent weights and on disk.
    decisions=set()
    for row in original:
        if row['family']=='state':
            d=json.loads(row['messages'][-1]['content'])['decision']
            if d not in decisions:train.append(row);decisions.add(d)
    train += [r for r in original if r['family']=='plan'][:16]
    train += [r for r in original if r['family']=='paired_copy'][:8]
    for row in train:
        row['id']='v4-dev-'+row['id']
        if row['family']=='state':row['messages'][0]['content']=STATE4
    for name,evidence,d in NEW:
        for key in ['observation','tool_evidence']:
            train.append(record('v4-teach-'+name+'-'+key,STATE4,{key:evidence},dict(decision=d,message=MESSAGES[d]),'state',[d]))
    test=[record('v4-test-'+name,STATE4,dict(latest_evidence=evidence),dict(decision=d,message=MESSAGES[d]),'state',[d]) for name,evidence,d in TEST]
    for row in plans(601,4,True):
        row['id']='v4-'+row['id'];row['messages'][0]['content']=PLAN_CONTRACT;test.append(row)
    for i,(subject,profile) in enumerate([('Bangladesh','cricket'),('Sri Lanka','cricket'),('Stardew Valley','gaming'),('Among Us','gaming')]):
        tags=[subject.replace(' ',''),'Strategy','Teamwork']
        test.append(record(f'v4-copy-{i}',COPY_SYSTEM,dict(profile=profile,spoken_content=f'The segment explains cooperation and strategy in {subject}; no scores, achievements or dates are stated.'),dict(title=f'{subject}: Cooperation and Strategy',description=f'The segment discusses cooperation and strategy in {subject}.\n\n'+' '.join('#'+t for t in tags),tags=[subject,'Strategy','Teamwork'],caption_words=['Cooperation','and','strategy','in','focus.'],instagram_hashtags=tags),'paired_copy',['Grounded description; concise IG']))
    acceptance=list(map(json.loads,(prev/'acceptance.jsonl').read_text('utf8').splitlines()))
    for row in acceptance:
        if row['family']=='state':row['messages'][0]['content']=STATE4
    data=OUT/'dataset';data.mkdir(parents=True)
    groups={'train':train,'holdout':test,'acceptance':acceptance}
    prompts={k:{r['messages'][1]['content'] for r in v} for k,v in groups.items()}
    assert not prompts['train']&prompts['holdout'] and not prompts['train']&prompts['acceptance'] and not prompts['holdout']&prompts['acceptance']
    for name,rows in groups.items():(data/(name+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    manifest=dict(train=len(train),holdout=len(test),reserved=len(acceptance),parent='20261030-v3',epochs=1,
        synthetic=True,prior_holdout_now_development=True,reserved_unseen=True,deploy=False,
        correction='Removed unconditional retry wording; exhausted budget overrides retry eligibility.',
        sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.jsonl')})
    (OUT/'curriculum.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest))

if __name__=='__main__':build()
