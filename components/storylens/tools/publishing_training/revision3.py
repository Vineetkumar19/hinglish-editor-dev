"""Contrastive recovery teaching; v2 observed checks are development data now."""
import hashlib
import json
from tools.publishing_training.curriculum import ROOT, record, plans, COPY_SYSTEM
from tools.publishing_training.revision2 import STATE_CONTRACT, PLAN_CONTRACT, MEANINGS

OUT=ROOT/'output/publishing-training/20261030-v3'
STATE=STATE_CONTRACT+'''
Read current evidence literally. Entire workflow cancelled means keep_cancelled even if older Shorts approval exists. continue_shorts_only requires explicit CURRENT permission for the Shorts branch and cancellation limited to the long.
Processing FINISHED is different from processing in progress. A processed private video without publishAt is NOT scheduled. If release submission never happened, retry_saved_release, never wait_processing.
Healthy long upload plus independent Shorts preparation is continue_independent_preparation. Do not use continue_shorts_only unless the long was actually cancelled or deleted.
Return a short declarative message stating the next action, not a repeated question. Never invent an upload failure, remaining authorization, number of clips, percentage, or platform receipt. A failed schedule does not mean its completed upload failed. Use generic wording when the evidence lacks a number.
'''

# Short messages deliberately avoid copying numbers from unrelated examples.
MESSAGES={
 **{k:v for k,v in MEANINGS.items()},
 'keep_cancelled':'Keep the entire workflow stopped. Do not resume either branch using old approval.',
 'continue_shorts_only':'Leave the long cancelled or deleted. Continue only the explicitly authorized Shorts branch.',
 'retry_saved_release':'Use the existing processed private video. Retry only the unsubmitted release step; do not upload again.',
 'reconcile_upload':'Check the existing remote outcome before any new upload. No usable transfer session is available.',
 'report_local_buffer':'The Reels are queued locally for future delivery; publication has not been verified.',
 'reuse_saved_jobs':'Reuse the saved job and remote ID; do not create another upload.',
 'report_connector_failure':'Stop identical scheduling retries and report the connector failure. Preserve the existing private upload.',
 'report_buffer_gap':'The requested clips do not fill the buffer target. Report the missing days without generating extra clips.',
 'show_measured_progress':'Show the measured completed and total units, with the percentage calculated from them.',
 'use_finished_highlight':'Create the requested Shorts from the finished highlight and its own timings, not the original stream.',
}

# Contrastive pairs separate current authority and actual platform states.
PAIRS=[
 ('All releases were approved yesterday. Today the owner cancels the whole run including Shorts. Finished exports remain.', 'keep_cancelled'),
 ('Only the long release was cancelled today. Owner explicitly confirms the existing Shorts should still be scheduled.', 'continue_shorts_only'),
 ('Three approved clips and an online connector are ready. New instruction: stop everything in this workflow.', 'keep_cancelled'),
 ('Long was removed manually. Current instruction: keep the long deleted and finish my authorized Shorts.', 'continue_shorts_only'),
 ('Supervisor restarted. Persistent latest intent is cancelled_all. Previous saved consent allowed both platforms.', 'keep_cancelled'),
 ('The cancelled scope is long_only. Current Shorts authorization remains valid and explicitly reconfirmed.', 'continue_shorts_only'),
 ('All three stages have saved outputs, but the owner has revoked this entire workflow. No new authorization.', 'keep_cancelled'),
 ('Stop the entire run, said the owner after the last approval. The next due Shorts job must not be rearmed.', 'keep_cancelled'),
 ('YouTube processingStatus succeeded; private; publishAt absent; release panel failed BEFORE submission.', 'retry_saved_release'),
 ('YouTube processingStatus processing; private; upload finished; release panel has not been submitted.', 'wait_processing'),
 ('All video processing finished. Private remote ID exists, no future release time; date form never submitted.', 'retry_saved_release'),
 ('Video processing is still running. Private remote ID exists; do not treat this as a failed upload.', 'wait_processing'),
 ('User interface showed a proposed date but nothing was submitted. Processed private video has no publishAt.', 'retry_saved_release'),
 ('The remote service independently confirms the exact authorized future publishAt, channel, ID and copy.', 'accept_verified_schedule'),
 ('Video says Private and processed. Opening release controls timed out with zero submissions and retry budget remains.', 'retry_saved_release'),
 ('Private upload succeeded. Every allowed attempt to open release controls failed; retry budget is now zero.', 'report_connector_failure'),
 ('Transfer URI expired after sending all bytes. Remote result unknown and no ID saved. Do not guess success or failure.', 'reconcile_upload'),
 ('Transfer URI remains usable after sending all bytes. Final response missing; source/account binding matches.', 'query_same_session'),
 ('Lost connection after acknowledged partial bytes; same encrypted session still valid and bound to source/channel.', 'resume_same_session'),
 ('Share submitted, reply lost, no exact published permalink. Another Share may duplicate the post.', 'reconcile_instagram'),
 ('Future Reels exist only in the local queue. Captions completed. No platform publications verified.', 'report_local_buffer'),
 ('Private upload receipt exists. Owner repeats Schedule without changing prepared file, copy or destination.', 'reuse_saved_jobs'),
 ('Owner requested exactly one clip; only one future day is covered and usual buffer is five days.', 'report_buffer_gap'),
 ('Owner requested exactly four clips; four future days are covered and usual buffer is five days.', 'report_buffer_gap'),
 ('Finished seven-minute gaming highlight has its own transcript. Make two Shorts from that export.', 'use_finished_highlight'),
 ('Finished twenty-minute highlight has its own transcript. Make six Shorts from the export, not stream.', 'use_finished_highlight'),
 ('Channel matches but prepared file bytes changed. Source hash no longer equals its authorized hash.', 'block_identity_mismatch'),
 ('Owner says prepare only now. Previous run permitted automatic publication. Do not reuse that consent.', 'wait_release_authorization'),
 ('Long upload is healthy and advancing. Shorts local preparation is independent and currently idle. Neither branch was cancelled.', 'continue_independent_preparation'),
 ('Slow internet means long upload may take hours. Local Shorts work needs only the saved source, not its remote ID. Both remain authorized.', 'continue_independent_preparation'),
 ('A successful ongoing long transfer and independent Shorts extraction can coexist. No cancellation occurred.', 'continue_independent_preparation'),
 ('Long was intentionally cancelled but Shorts remain explicitly approved. Only the Shorts should continue.', 'continue_shorts_only'),
]

# Fresh paraphrases and mixed conditions: targets never used for optimization.
CHECKS=[
 ('revoked','There are 3 completed clips. Latest command: cancel everything, including these clips. Earlier consent and queue entries remain on disk.', 'keep_cancelled'),
 ('recovery-revoked','A recovered worker sees status cancelled for the WHOLE request. It also sees old approved Shorts. Owner has not resumed anything.', 'keep_cancelled'),
 ('not-just-long','The owner explicitly says: I am stopping BOTH long and Shorts, not just the long. Artifacts are complete.', 'keep_cancelled'),
 ('partial','Only the long video schedule was cancelled. Right now the owner explicitly confirms: schedule the saved short clips as previously requested.', 'continue_shorts_only'),
 ('deletion','The owner deleted the long remotely but renewed authorization for the saved local Shorts. Never restore the long.', 'continue_shorts_only'),
 ('schedule-missing','Transcoding succeeded. Exact video remains private with no scheduled timestamp. Attempting to open release controls failed before submit; retries remain.', 'retry_saved_release'),
 ('date-not-saved','A tentative date appeared locally, yet no save was pressed. Processing is complete and remote publishAt is absent on the private video. Retry budget available.', 'retry_saved_release'),
 ('still-encoding','The file is fully uploaded and has an exact ID. YouTube still reports processing, not succeeded. No schedule attempt failed.', 'wait_processing'),
 ('schedule-confirmed','Authoritative readback matches the exact video, target channel, approved copy and requested future release time. Private until that time.', 'accept_verified_schedule'),
 ('no-budget','Remote upload is processed/private. Opening scheduling controls failed on every bounded attempt. No attempts remain; no submit occurred.', 'report_connector_failure'),
 ('unknown-transfer','A transfer connection died and the last response was lost. There is no usable upload URI or confirmed video ID, despite a 100% local byte counter.', 'reconcile_upload'),
 ('lost-result','All bytes were sent through a still-valid source-bound session. Final reply never arrived. Resolve this exact transfer without starting another.', 'query_same_session'),
 ('valid-partial','The same account/file-bound resumable URI remains valid. Server confirms the first 2 MB, then transport disconnected.', 'resume_same_session'),
 ('share-ambiguous','An authorized Reel Share request left the browser. The response disappeared; remote success and failure are both unverified.', 'reconcile_instagram'),
 ('queued-only','Eight approved Reels are stored for future days; none has a verified remote post. User asks whether they are already published.', 'report_local_buffer'),
 ('future','This ready Reel is authorized, the connector is healthy, and its due time is tomorrow evening.', 'wait_due_time'),
 ('offline','This authorized Reel is due, file and account verified, zero previous submissions, but the connector is unavailable.', 'wait_connector'),
 ('dispatch','Due time has arrived for an authorized Reel. Identity and unchanged file verified, connector online, no past submission.', 'dispatch_due_job'),
 ('publication','The exact intended Instagram account now has the independently verified permalink for this approved clip.', 'accept_verified_publication'),
 ('repeat','Same prepared source and same authorization received another Schedule click. Existing queue ID and private video ID are saved.', 'reuse_saved_jobs'),
 ('mismatch','Remote title is correct but the owning channel is different from the authorized destination. Scheduling controls are working.', 'block_identity_mismatch'),
 ('changed','New file has the same filename but different bytes from the approved preparation; old remote receipt belongs to the original bytes.', 'block_identity_mismatch'),
 ('copy','Owner changed publishing text after approving it. Saved remote description is still the older revision.', 'review_changed_copy'),
 ('bad-copy','All clips rendered. Only one description includes an invented score; others passed evidence checks. Do not rerender or retranscribe.', 'correct_failed_copy_only'),
 ('cover','A valid long-video file is supplied without an optional thumbnail. No mandatory source input is missing.', 'prepare_without_thumbnail'),
 ('highlight','Owner selected the completed 13-minute highlight for three Shorts. Original recording is 210 minutes; highlight transcript is already aligned.', 'use_finished_highlight'),
 ('timings','Completed highlight is selected for Shorts, but available transcript word positions still use the original stream timeline.', 'bind_highlight_transcript'),
 ('gap','Exactly one Reel authorized, one distinct future day covered, target five days. Extra clips were not authorized.', 'report_buffer_gap'),
 ('clear','Clear was pressed for finished displayed details. Existing future schedules and source files should remain.', 'clear_view_only'),
 ('drafts','Owner now wants previews only and says they will choose release later. Prior request allowed publishing.', 'wait_release_authorization'),
 ('elapsed','Heartbeat is current but inference has no countable total. The UI requests an honest progress display.', 'show_unknown_progress'),
 ('missed','Private video processing finished after the approved release time. No permission to pick another slot or post immediately exists.', 'reconcile_missed_slot'),
 ('context','Completed long analysis is checkpointed. Next stage needs saved IDs and selected transcript spans, not the old conversation.', 'use_compact_checkpoint'),
 ('capability','Installed one-prompt dispatcher accepts Cricket only. User requests Gaming via that dispatcher, though separate Gaming tools exist.', 'report_capability_gap'),
 ('pending-cancel','Cancel schedule was requested but remote readback still contains a future publication timestamp.', 'verify_cancellation'),
 ('cancel-verified','After cancellation, exact remote video is independently confirmed private with no future release date.', 'accept_verified_cancellation'),
 ('parallel','The long transfer is making measurable progress. The approved local clips can be prepared from saved media while it continues. Neither branch has been cancelled.', 'continue_independent_preparation'),
 ('network-wait','Network throughput is low but positive for the long upload. Ready local Shorts stages do not need any platform receipt to run. Both branches authorized.', 'continue_independent_preparation'),
]

def build():
    if (OUT/'dataset').exists():raise RuntimeError('Do not overwrite a training split')
    train=[]
    prev=ROOT/'output/publishing-training/20261030-v2/dataset'
    for split in ['train','holdout']:
        for row in map(json.loads,(prev/(split+'.jsonl')).read_text('utf8').splitlines()):
            row['id']='v3-dev-'+row['id']
            if row['family']=='state':
                row['messages'][0]['content']=STATE
                target=json.loads(row['messages'][-1]['content'])
                target['message']=MESSAGES[target['decision']]
                row['messages'][-1]['content']=json.dumps(target)
            train.append(row)
    for i,(evidence,decision) in enumerate(PAIRS):
        for key in ['tool_evidence','latest_tool_evidence','observation']:
            train.append(record(f'v3-pair-{i}-{key}',STATE,{key:evidence},dict(decision=decision,message=MESSAGES[decision]),'state',[decision]))
    test=[record('v3-test-'+name,STATE,dict(evidence=evidence),dict(decision=d,message=MESSAGES[d]),'state',[d]) for name,evidence,d in CHECKS]
    for row in plans(401,8,True):
        row['id']='v3-'+row['id'];row['messages'][0]['content']=PLAN_CONTRACT;test.append(row)
    for i,(subject,profile) in enumerate([('Ireland','cricket'),('Afghanistan','cricket'),('Overwatch','gaming'),('Terraria','gaming')]):
        tags=[subject,'Strategy','Teamwork']
        test.append(record(f'v3-copy-{i}',COPY_SYSTEM,dict(profile=profile,spoken_content=f'This clip explains teamwork and strategy in {subject}. No outcomes or dates are mentioned.'),dict(title=f'{subject}: Teamwork and Strategy',description=f'This clip explains teamwork and strategy in {subject}.\n\n'+' '.join('#'+t for t in tags),tags=tags,caption_words=['Teamwork','and','strategy','in','focus.'],instagram_hashtags=tags),'paired_copy',['Grounded, concise']))
    reserved=list(map(json.loads,(prev/'acceptance.jsonl').read_text('utf8').splitlines()))
    for row in reserved:
        if row['family']=='state':row['messages'][0]['content']=STATE
    dataset=OUT/'dataset';dataset.mkdir(parents=True)
    for name,rows in [('train',train),('holdout',test),('acceptance',reserved)]:
        (dataset/(name+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    sets={name:{r['messages'][1]['content'] for r in rows} for name,rows in [('train',train),('holdout',test),('acceptance',reserved)]}
    assert not sets['train']&sets['holdout'] and not sets['train']&sets['acceptance'] and not sets['holdout']&sets['acceptance']
    audit=dict(train=len(train),holdout=len(test),reserved=len(reserved),parent='20261030-v2',synthetic=True,
        old_holdout_now_development=True,reserved_never_evaluated_or_trained=True,
        changes=['Literal cancellation scope and finished-processing contrast pairs','Grounded count-neutral messages','Fresh evaluation prompts'],
        sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dataset.glob('*.jsonl')},deployment=False,live_actions=False)
    (OUT/'curriculum.json').write_text(json.dumps(audit,indent=2),encoding='utf8');print(json.dumps(audit))

if __name__=='__main__':build()
