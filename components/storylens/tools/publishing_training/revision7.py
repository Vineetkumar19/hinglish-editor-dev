"""Scheduling recovery and weekly batches. Synthetic teaching, no platform actions."""
import hashlib
import json
from tools.publishing_training.curriculum import ROOT, record, plans, LESSONS
from tools.publishing_training.revision6 import SAFE, STATE6

OUT = ROOT / 'output/publishing-training/20261030-v7'
MESSAGES = {d: m for _, _, d, m in LESSONS}
MESSAGES.update(SAFE)
MESSAGES.update(
    retry_saved_release='Reuse the saved private video ID. Retry only the authorized release within its remaining retry budget.',
    report_connector_failure='Scheduling failed and its retry budget is exhausted. Preserve the saved upload and report the connector failure.',
    bind_highlight_transcript='Verify word timings on the finished highlight timeline before selecting Shorts.',
    continue_shorts_only='Keep the long cancelled or deleted. Continue only the currently authorized Shorts.',
    report_local_buffer='The Reels are already queued locally. Publication is not verified.',
    block_identity_mismatch='A supplied file or destination does not match its saved identity. Preserve the saved work and block release.',
    report_capability_gap='The requested action cannot proceed with the supplied inputs. Report the validation failure without silently changing the request.',
)
STATE = STATE6 + '\nUse exactly the approved factual message for the selected decision. Do not append inferred facts. Approved messages: ' + json.dumps(MESSAGES)
PREP = (
    'Route the supplied publishing request into the existing Prepare/Post preparation payload. Return JSON. '
    'Copy exact selected paths and requested count (1 through 7); do not round up to seven or five. '
    'Cricket long is documentary; gaming supports highlights and shorts. Highlights count is one output and minutes is the requested duration. Use minutes=15 outside highlights. '
    'For long/highlights include a supplied valid thumbnail path; an omitted optional thumbnail is empty. '
    'Shorts/Reels use no thumbnail even if an unrelated image was attached. '
    'Prepare/Post validates files and uploads the supplied thumbnail with the matching long/highlight, not the original livestream. '
    'Only shorts use both platforms. Respect draft-only versus schedule or post_now; draft means release=review. '
    'Seven means seven paired clips: seven YouTube deliveries and the SAME seven Instagram deliveries, not fourteen unique clips. '
    'Each clip has its own saved stage and platform receipt. Read only the next stage inputs. '
    'Gaming shorts from a finished highlight use that selected finished file, not the source livestream. '
    'These are routing recommendations, not executed uploads. Return the declared schema only.'
)
SCHEMA = {'type':'object','additionalProperties':False,'properties':{
    'profile':{'type':'string','enum':['cricket','gaming']},
    'mode':{'type':'string','enum':['long','shorts','highlights']},
    'count':{'type':'integer','minimum':1,'maximum':7},
    'minutes':{'type':'integer','minimum':1,'maximum':60},
    'video':{'type':'string'},'thumbnail':{'type':'string'},
    'release':{'type':'string','enum':['review','schedule','post_now']},
    'platforms':{'type':'array','items':{'type':'string','enum':['youtube','instagram']}}
},'required':['profile','mode','count','minutes','video','thumbnail','release','platforms']}

def preparation(n, held=False):
    profile = ['cricket','gaming'][n % 2]
    mode = ['shorts','long' if profile=='cricket' else 'highlights'][n % 3 == 0]
    count = [3,5,7][(n // 3) % 3] if mode=='shorts' else 1
    minutes = [10,15,20][(n // 3) % 3] if mode=='highlights' else 15
    video = f'E:/New exports/{"Unseen" if held else "Practice"} {n}/'+('finished highlight.mp4' if profile=='gaming' and mode=='shorts' else 'final video.mp4')
    selected_thumbnail = f'E:/Covers/{n} '+('cover.png' if n % 2 else 'cover.jpg') if n % 5 else ''
    thumb = selected_thumbnail if mode!='shorts' else ''
    release = ['schedule','post_now','review'][n % 5 % 3]
    request = (f'{profile}: {mode}, '+(f'{count} Shorts and same Reels' if mode=='shorts' else f'{minutes} minutes' if mode=='highlights' else 'one documentary')
               + f'. Video "{video}". '+(f'Thumbnail "{selected_thumbnail}". ' if selected_thumbnail else 'No thumbnail. ')
               + ('Prepare only, let me review.' if release=='review' else 'Schedule it.' if release=='schedule' else 'Post now.'))
    if held:
        request = f'Use this exact file for my {profile} channel: "{video}". '+(
            f'Make {count} paired shorts/reels.' if mode=='shorts' else f'Create {minutes}-minute highlights.' if mode=='highlights' else 'It is a long documentary.') + (
            f' Cover is "{selected_thumbnail}".' if selected_thumbnail else ' Cover omitted.') + (
            ' I will review before posting.' if release=='review' else ' Queue/schedule the result.' if release=='schedule' else ' Publish immediately.')
    row = record(('fresh' if held else 'train')+f'-preparation-{n}', PREP,
        dict(owner_request=request, selected_video=video, selected_thumbnail=selected_thumbnail),
        dict(profile=profile,mode=mode,count=count,minutes=minutes,video=video,thumbnail=thumb,release=release,
             platforms=['youtube','instagram'] if mode=='shorts' else ['youtube']),
        'preparation',['Exact source, cover, count, channel and release; no platform action.'])
    row['response_schema'] = SCHEMA
    return row

CASES = [
 ('private-row','Private upload ID and correct channel verified; processing completed; Studio visibility label timed out before submission. One retry remains.','retry_saved_release'),
 ('private-label','A long video is processed and private. The dropdown opener failed before submit. Two permitted attempts remain.','retry_saved_release'),
 ('empty-budget','Private upload exists; all allowed Studio visibility-control retries failed before submit. Budget is zero.','report_connector_failure'),
 ('uncertain-submit','Schedule Submit may have been clicked. Readback is unavailable; its outcome is unknown. Reuse saved jobs; no second insertion.','reuse_saved_jobs'),
 ('verified','Exact video ID, channel, approved copy and requested future publishAt match independent YouTube readback.','accept_verified_schedule'),
 ('processing','The saved exact video is still being processed by YouTube, so scheduling must wait.','wait_processing'),
 ('wrong-channel','Approved target channel differs from the saved private upload owner. No release submitted.','block_identity_mismatch'),
 ('copy-changed','Approved description was changed after authorization; remote copy is the older revision.','review_changed_copy'),
 ('cancelled','Owner cancelled both branches of this workflow after an upload. No current permission to resume.','keep_cancelled'),
 ('deleted-long','Owner deleted the long and separately authorizes the existing Shorts branch. Do not restore the long.','continue_shorts_only'),
 ('seven-buffer','Seven exact paired clips have authorized future Instagram jobs. No remote Instagram publication is verified.','report_local_buffer'),
 ('highlight-timing','The selected finished highlight lacks verified word timings. No claim about source-stream timings is available.','bind_highlight_transcript'),
 ('changed-cover','Owner supplied a documentary cover. Its file hash changed after the reviewed draft was authorized.','block_identity_mismatch'),
 ('missing-cover','The explicitly supplied highlights thumbnail path does not exist. Do not silently omit a requested cover or invent a replacement.','report_capability_gap'),
 ('invalid-cover','The supplied documentary cover failed image decoding. Video preparation is saved; do not silently publish without the requested image.','report_capability_gap'),
 ('cover-optional','The owner explicitly omitted the optional long-video cover. Source file is valid and preparation has not started.','prepare_without_thumbnail'),
 ('seven-partial','Owner requested seven paired clips. Three have saved verified schedules. Schedule was pressed again on that same preparation; saved per-clip jobs exist.','reuse_saved_jobs'),
 ('copy-one-of-seven','Seven rendered exports are saved. Only clip six has unsupported generated description claims; all other checked copies remain valid.','correct_failed_copy_only'),
 ('weekly-excess','Owner configured a maximum weekly batch of seven and asks for eight in this review. Do not silently reduce or increase the count.','report_capability_gap'),
 ('highlight-parent','User selected the finished ten-minute gaming highlight with verified own word timings for seven Shorts. Original three-hour stream is archived.','use_finished_highlight'),
 ('cover-before-review','Requested documentary cover and metadata were changed after release approval; saved remote copy is the earlier revision.','review_changed_copy'),
 ('thumbnail-receipt-not-schedule','Thumbnail was successfully attached to the processed private long video. Scheduling has not been submitted, one retry remains.','retry_saved_release'),
]

def state_row(identity,evidence,decision):
    return record(identity,STATE,dict(tool_evidence=evidence),dict(decision=decision,message=MESSAGES[decision]),'state',[decision,'Exact factual template; no invented schedule or timing.'])

def build():
    if OUT.exists(): raise RuntimeError('Preserve the frozen run; use a new revision')
    data=OUT/'dataset';data.mkdir(parents=True)
    train=[]
    for n,(_,e,d) in enumerate(CASES):
        for form in ['Latest observation: ','Saved tool evidence: ','Recovery check: ']:
            train.append(state_row(f'train-schedule-{n}-{len(train)}',form+e,d))
    train += [preparation(n) for n in range(48)]
    for row in plans(2100,14): train.append(row)
    previous=ROOT/'output/publishing-training/20261030-v6/dataset'
    for row in map(json.loads,(previous/'train.jsonl').read_text('utf8').splitlines()):
        if row['family']=='paired_copy' and sum(x['family']=='paired_copy' for x in train)<16:train.append(row)
    fresh=[state_row('fresh-'+name,'Independent observation: '+e.replace('One retry remains.','One attempt remains.').replace('Budget is zero.','No retries remain.'),d) for name,e,d in CASES]
    fresh += [preparation(n,True) for n in range(300,324)]
    # Previously inspected failures/regressions are explicitly seen development cases.
    regression=[]
    for split in ['holdout','acceptance']:
        for row in map(json.loads,(previous/(split+'.jsonl')).read_text('utf8').splitlines()):
            if row['family']=='state':
                target=json.loads(row['messages'][-1]['content']);row['messages'][0]['content']=STATE
                row['messages'][-1]['content']=json.dumps(dict(decision=target['decision'],message=MESSAGES[target['decision']]))
                regression.append(row)
    for name,rows in [('train',train),('holdout',fresh),('acceptance',regression)]:
        (data/(name+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    info=dict(train=len(train),fresh_holdout=len(fresh),seen_regression=len(regression),parent='20261030-v6',epochs=1,
        live_actions=False,auto_deploy=False,scope='YouTube scheduling recovery; 1-7 weekly paired clips; supplied/omitted long/highlight covers; no Shorts covers.',
        strict_state_template=True,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.jsonl')})
    (OUT/'curriculum.json').write_text(json.dumps(info,indent=2));print(json.dumps(info))
if __name__=='__main__':build()
