"""Versioned publishing lessons; synthetic cases, never platform receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/publishing-training/20261030-v1'
PLAN_SYSTEM = (
    'Plan this explicit cricket uploading request using the existing Prepare and Post tools. Return JSON. '
    'Use only the supplied exact file paths. Empty thumbnail means none. Copy the requested Shorts count. '
    'Default long_release to schedule unless the owner explicitly requests immediate long publication. '
    'Shorts and Reels are scheduled together. The exact steps are prepare_long, release_long, '
    'prepare_shorts, schedule_youtube_shorts, queue_instagram_reels, in that order. '
    'Each stage has saved inputs/results; no previous chat transcript or model conversation is needed.'
)
STEPS = ['prepare_long', 'release_long', 'prepare_shorts', 'schedule_youtube_shorts', 'queue_instagram_reels']
STATE_SYSTEM = (
    'You are the Storylens publishing assistant. Read the supplied tool evidence. '
    'Return JSON with decision and message (strings). decision is a recommendation, NOT a tool invocation. '
    'Never invent an upload or schedule receipt. Preserve exact source/account/job identity and completed work. '
    'Use bounded recovery only for authorized unchanged work. Cancelled work stays cancelled. '
    'Independent preparation can continue while network transfer waits. Report local Instagram buffering separately '
    'from verified publication. Keep messages short. Do not expose secrets or private reasoning.'
)
COPY_SYSTEM = (
    'Write source-grounded YouTube and Instagram text for the same Short. Return JSON with title, description, '
    'tags, caption_words and instagram_hashtags. Use natural English. Instagram caption_words must contain '
    '1-10 single-word strings; instagram_hashtags contains 3-5 relevant strings without #. '
    'End YouTube description with 3-5 hashtags. Do not infer dates, scores, records or current events. '
    'The application adds mandatory YouTube social footers separately; never add them to Instagram.'
)

# Corrected teaching targets from the guide and actual failure classes. These
# contain no live IDs, authentication material or fabricated successful receipts.
LESSONS = [
 ('private', 'YouTube API: processed, private, publishAt absent. Studio visibility dialog failed before submission.', 'retry_saved_release', 'Upload completed privately; scheduling failed. Retry the same saved release after identity checks, without re-uploading.'),
 ('unknown', 'Upload owner exited. No remote video ID and no saved transfer session.', 'reconcile_upload', 'Upload outcome is uncertain. Keep the receipt and reconcile it before any new upload; independent Shorts preparation can continue.'),
 ('session', 'Connection lost after acknowledged bytes; encrypted bound upload session exists.', 'resume_same_session', 'Query the saved transfer session and continue from the server-confirmed offset. Do not create another upload.'),
 ('final_response', 'Final upload response lost, but the encrypted transfer session is saved.', 'query_same_session', 'Query the same session for its completed video ID or confirmed byte offset before continuing.'),
 ('slow', 'Long uploader is alive and acknowledged byte count is increasing slowly. Local Shorts are not prepared yet.', 'continue_independent_preparation', 'The long upload is progressing. Prepare the requested Shorts independently while it continues.'),
 ('processing', 'Exact private video exists; YouTube uploadStatus is uploaded, processingStatus processing.', 'wait_processing', 'YouTube is processing the saved upload. Wait with bounded status checks; do not upload again.'),
 ('scheduled', 'Exact video/channel/copy and requested future publishAt independently verified by YouTube.', 'accept_verified_schedule', 'YouTube confirmed the requested schedule for this video.'),
 ('ig_buffer', 'Three Instagram jobs are authorized and ready locally for future dates. No remote publication receipt.', 'report_local_buffer', 'Three Reels are in the local buffer; Instagram publication is not verified yet.'),
 ('ig_due', 'Instagram job is due, ready, authorized; matching account and source, connector is online.', 'dispatch_due_job', 'The due Reel should be claimed once by the delivery worker and sent through the connected Instagram transport.'),
 ('ig_offline', 'Instagram job is due, but Chrome connector has no current heartbeat.', 'wait_connector', 'The Reel has not posted. Restore the Chrome connector; keep this same authorized queue item.'),
 ('ig_uncertain', 'Instagram Share was clicked, then the response was lost. No permalink verified.', 'reconcile_instagram', 'Instagram publication is uncertain. Check the exact post before retrying Share; do not create a duplicate.'),
 ('ig_verified', 'Exact Instagram account and published permalink independently verified.', 'accept_verified_publication', 'Instagram publication is verified for this Reel.'),
 ('duplicate', 'Owner pressed Schedule twice on the same preparation. Saved queue and remote IDs already exist.', 'reuse_saved_jobs', 'Reuse the existing queue items and receipts. Do not upload another copy.'),
 ('cancel', 'Owner cancelled this workflow. Older instructions had authorized automatic continuation.', 'keep_cancelled', 'Keep this workflow cancelled; previous authorization does not restart it.'),
 ('long_cancel', 'Long stage was verified earlier. Owner later cancelled its schedule; Shorts authorization remains valid.', 'continue_shorts_only', 'Leave the long schedule cancelled and continue only the authorized Shorts from the saved local source.'),
 ('deleted', 'Owner deleted a previously verified long video. Completed local stages and Shorts authorization remain saved.', 'continue_shorts_only', 'Do not restore the deleted long video. Continue the saved Shorts branch only.'),
 ('account', 'Saved target account differs from the currently connected account.', 'block_identity_mismatch', 'The destination account changed. Stop this side effect until the intended account is verified.'),
 ('source', 'The video path matches, but its hash differs from the saved preparation.', 'block_identity_mismatch', 'The source file changed. Revalidate it; do not reuse the old upload binding.'),
 ('copy_changed', 'Metadata revision changed after release authorization; remote description differs.', 'review_changed_copy', 'The publishing text changed. Review the new revision before changing the existing upload.'),
 ('exhausted', 'All bounded release retries failed with the same dialog-loading error.', 'report_connector_failure', 'Scheduling stopped because the Studio dialog still did not open. The private upload is saved; more identical retries are not a fix.'),
 ('short_copy', 'Clip 1 text accepted. Clip 2 text rejected for invented statistics. Clips and transcript saved.', 'correct_failed_copy_only', 'Keep the saved clips and accepted text. Regenerate only Clip 2 text from its evidence and correction.'),
 ('thumbnail', 'Owner supplied a Long video but no optional thumbnail.', 'prepare_without_thumbnail', 'Continue without a thumbnail. The optional thumbnail feature remains available.'),
 ('highlights', 'Gaming livestream is two hours. Finished highlight is ten minutes; owner requests four Shorts from it.', 'use_finished_highlight', 'Use the finished highlight and its own transcript/timebase to create exactly four Shorts.'),
 ('timebase', 'Highlight export exists, but saved word timings still reference the original livestream.', 'bind_highlight_transcript', 'Remap verified timings to the highlight or transcribe the highlight itself before selecting Shorts.'),
 ('buffer_target', 'Owner requested three clips; buffer target is five distinct future days; current queue covers three days.', 'report_buffer_gap', 'Three days are buffered; two more days are needed. Do not generate extra clips without authorization.'),
 ('clear', 'Owner pressed Clear on completed preparation details; scheduled queue items still exist.', 'clear_view_only', 'Clear the displayed preparation without deleting media, schedules or receipts.'),
 ('prep_only', 'Current request says prepare only and let me review. Old conversation once authorized posting.', 'wait_release_authorization', 'Prepare and show the result. Wait for current Post now or Schedule authorization.'),
 ('eta', 'Current model step has no measurable units or total duration.', 'show_unknown_progress', 'Show the current step, elapsed time and last update. Do not invent a percentage or remaining time.'),
 ('steps', 'Two of five measured batches are complete.', 'show_measured_progress', '40% complete: 2 of 5 batches finished, 3 remaining.'),
 ('passed_slot', 'Saved release time passed while uploading; exact video is still private.', 'reconcile_missed_slot', 'The release slot passed. Apply the authorized missed-slot policy or request a new time; never silently publish now.'),
 ('expired', 'Saved resumable session returns 404; remote outcome is not independently known.', 'reconcile_upload', 'The transfer session expired. Reconcile the remote outcome before considering another upload.'),
 ('progress_memory', 'Long text stage completed with an atomic checkpoint. Next step needs only selected speech spans.', 'use_compact_checkpoint', 'Start the next request with saved IDs, relevant evidence and full required creator guidance; release the previous conversation context.'),
 ('wrong_game', 'User asks for one-prompt Gaming workflow, but installed full-workflow route only accepts Cricket.', 'report_capability_gap', 'Gaming preparation tools exist, but this one-prompt route does not support Gaming yet. Do not relabel it as Cricket.'),
 ('future_ig', 'Instagram job has a future due timestamp; worker is online and job is ready.', 'wait_due_time', 'Keep the Reel buffered until its authorized due time; do not post it early.'),
 ('lost_cancel', 'YouTube cancel was clicked, but API still returns the same scheduled publishAt.', 'verify_cancellation', 'Cancellation is not confirmed. Keep checking the exact saved video; do not mark it cancelled yet.'),
 ('cancel_done', 'YouTube confirms exact video private with publishAt absent after requested cancellation.', 'accept_verified_cancellation', 'The schedule is cancelled; the video remains private. Remove it from active scheduled posts.'),
]

def record(identity, system, data, target, family, rubric):
    return dict(id=identity, family=family, synthetic=True, messages=[
        dict(role='system', content=system),
        dict(role='user', content=data if isinstance(data,str) else json.dumps(data,ensure_ascii=False)),
        dict(role='assistant', content=json.dumps(target,ensure_ascii=False))], rubric=rubric)

def plans(start, count, held=False):
    rows=[]
    for n in range(start,start+count):
        video=f'D:\\Documentaries\\{"Unseen" if held else "Practice"} team {n}\\final cut.mp4'
        thumbnail=f'D:\\Covers\\team {n}.jpg' if n%3==0 else ''
        clips=1+n%7
        action='post_now' if n%4==0 else 'schedule'
        phrasing=(f'{"Publish now" if action=="post_now" else "Schedule"} this long documentary on cricket YouTube: "{video}". '
                  f'Extract {clips} Shorts and schedule those on YouTube and Instagram.'
                  +(f' Thumbnail: "{thumbnail}".' if thumbnail else ' No thumbnail.'))
        if held:
            phrasing=f'Cricket channel please: "{video}". Long video {"public now" if action=="post_now" else "later in the evening"}; make {clips} reels/Shorts and queue/schedule both platforms. Thumbnail '+(thumbnail or 'none')+'.'
        rows.append(record(f'{"test" if held else "train"}-plan-{n}',PLAN_SYSTEM,
            dict(owner_request=phrasing,selected_video=video,selected_thumbnail=thumbnail),
            dict(profile='cricket',video=video,thumbnail=thumbnail,count=clips,long_release=action,shorts_release='schedule',steps=STEPS),
            'plan',['Exact source/thumbnail/count/release; exact supported plan schema']))
    return rows

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=plans(0,64)
    for i,(key,observation,decision,message) in enumerate(LESSONS):
        rows.append(record('lesson-'+key,STATE_SYSTEM,dict(observation=observation),dict(decision=decision,message=message),'state',[decision]))
        rows.append(record('case-'+key,STATE_SYSTEM,dict(case_id=f'case-{1000+i}',question='What should happen next? Tell the owner briefly.',tool_evidence=observation),dict(decision=decision,message=message),'state',[decision]))
    teams=['Mumbai Indians','Royal Challengers Bengaluru','Delhi Capitals','Chennai Super Kings','Rajasthan Royals','Punjab Kings']
    for i,team in enumerate(teams):
        for topic,caption in [('teamwork','Teamwork shapes the story'),('batting','Batting shapes the contest'),('bowling','Bowling changes the momentum'),('leadership','Leadership shapes the team')]:
            tags=[team.replace(' ',''),'Cricket',topic.title()]
            rows.append(record(f'copy-{i}-{topic}',COPY_SYSTEM,dict(spoken_content=f'This segment discusses {team} and their {topic}.',profile='cricket'),
                dict(title=f'{team}: A Look at {topic.title()}',description=f'A look at {team} and their {topic}, as discussed in this clip.\n\n'+' '.join('#'+t for t in tags),tags=[team,'Cricket',topic.title()],caption_words=caption.split(),instagram_hashtags=tags),'paired_copy',['Grounded copy; <=10 IG words; separate 3-5 hashtags']))
    for i,game in enumerate(['PUBG Mobile','Minecraft','Valorant','Rocket League']):
        tags=[game.replace(' ',''),'Gaming','Gameplay']
        rows.append(record(f'gaming-copy-{i}',COPY_SYSTEM,dict(spoken_content=f'The player explains their movement strategy in {game}.',profile='gaming'),
            dict(title=f'{game}: Movement Strategy Explained',description=f'The player discusses movement strategy during this {game} gameplay segment.\n\n'+' '.join('#'+t for t in tags),tags=[game,'Gameplay','Movement strategy'],caption_words=['Movement','strategy','makes','the','difference.'],instagram_hashtags=tags),'paired_copy',['Actual game; no Cricket tags; short caption']))
    tests=plans(101,10,True)
    unseen=[
      ('private-late','A clip is READY on the encoding service. YouTube says processed/private and no release date. Our dialog opener timed out.','retry_saved_release'),
      ('uncertain-long','The app crashed midway through upload. It saved neither a platform ID nor a resumable session. Can I safely send the file again?','reconcile_upload'),
      ('buffer-only','There are four local future Reel jobs. No Instagram permalink exists. Did all four publish?','report_local_buffer'),
      ('offline-due','A Reel is past due. Browser connector is disconnected; file and authorization are valid.','wait_connector'),
      ('no-duplicate','The uploader returned a private remote ID. User clicked Schedule again for that preparation.','reuse_saved_jobs'),
      ('owner-cancel','The user cancelled this same workflow after its last retry. Should automatic recovery rearm it?','keep_cancelled'),
      ('highlight-source','The saved gaming highlight export is 12 minutes. Source stream is 180 minutes. Shorts requested from the completed highlight.','use_finished_highlight'),
      ('independent','Long upload is 31% and advancing. Shorts selection has not started. Must local work wait for upload completion?','continue_independent_preparation'),
      ('wrong-account','Remote video owner channel is not the authorized account, despite an identical title.','block_identity_mismatch'),
      ('share-lost','The Instagram Share response was lost after submission. We have no proof that it failed.','reconcile_instagram'),
      ('expired-session','YouTube returned 404 for the encrypted transfer URI. There is no independently verified remote ID.','reconcile_upload'),
      ('verified-date','YouTube API confirms processed private video with the exact requested future publishAt and correct channel/copy.','accept_verified_schedule'),
    ]
    for key,observation,decision in unseen:
        target=next(message for _,_,d,message in LESSONS if d==decision)
        tests.append(record('test-'+key,STATE_SYSTEM,dict(observation=observation),dict(decision=decision,message=target),'state',[decision]))
    # These topics/team identities do not appear in supervised copy targets.
    for i,team in enumerate(['Sunrisers Hyderabad','Kolkata Knight Riders']):
        tags=[team.replace(' ',''),'Cricket','Teamwork']
        tests.append(record(f'test-copy-{i}',COPY_SYSTEM,dict(spoken_content=f'This clip discusses teamwork within {team}.',profile='cricket'),
            dict(title=f'{team}: Teamwork in Focus',description=f'This clip discusses teamwork within {team}.\n\n'+' '.join('#'+t for t in tags),tags=[team,'Cricket','Teamwork'],caption_words=['Teamwork','brings','the','team','together.'],instagram_hashtags=tags),'paired_copy',['Correct unseen team; valid paired schema']))
    dataset=OUT/'dataset';dataset.mkdir(exist_ok=True)
    for name,data in [('train',rows),('holdout',tests)]:
        (dataset/(name+'.jsonl')).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in data)+'\n',encoding='utf8')
    pdf=ROOT/'output/pdf/Storylens-Local-Assistant-Workflow-Training-Guide.pdf'
    manifest=dict(train=len(rows),heldout=len(tests),training_kind='fresh separate Qwen3-14B NF4/LoRA adapter',
       source_pdf=str(pdf),source_pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
       actual_failures=['private Short release dialog timeout','uncertain long upload without remote receipt','local Instagram buffering is not publication'],
       limitations=['Synthetic corrected examples, not successful platform traces','Gaming one-prompt route not implemented by training','Connector and queue liveness require software and live validation'],
       deploy=False,train_families=sorted({r['family'] for r in rows}))
    (OUT/'curriculum.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':build()
