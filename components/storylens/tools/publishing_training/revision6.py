"""Normalize state explanations to the same safe action; preserve old failures."""
import hashlib
import json
from tools.publishing_training.curriculum import ROOT, record, plans
from tools.publishing_training.revision5 import STATE5, COPY5
from tools.publishing_training.revision3 import MESSAGES
from tools.publishing_training.revision2 import PLAN_CONTRACT, CHECKS
OUT=ROOT/'output/publishing-training/20261030-v6'
SAFE={**MESSAGES,
 'retry_saved_release':'Reuse the existing private video ID. Retry its release step only; never create a new upload.',
 'report_local_buffer':'The Reels are already queued locally. Their publication is not verified. Do not create another queue.',
 'bind_highlight_transcript':'The highlight needs verified timings on its own timeline before Shorts selection.',
 'continue_shorts_only':'Keep the long cancelled or deleted. Continue only the currently authorized Shorts.',
 'report_connector_failure':'Scheduling retries are exhausted. Keep the existing upload and report the connector error.',
 'keep_cancelled':'Keep both branches stopped. Old permission does not restart this cancelled workflow.'}
STATE6=STATE5+'''
The explanation must agree with the action. For retry_saved_release, say reuse the existing private video ID and retry only release; NEVER say create a new/identical upload. For report_local_buffer, report the ALREADY saved queue; NEVER instruct creating it again. Explain missing highlight timing without inventing that a particular old transcript was selected. Prefer the short safe action over creative paraphrases.
'''
TEST=[
 ('release-private','A processed private video is verified on the right channel. No release was submitted because the dialog failed once, and one retry remains.', 'retry_saved_release'),
 ('release-same','The existing upload finished. Only scheduling failed before submit; retry allowance is positive. No second upload is permitted.', 'retry_saved_release'),
 ('release-draft-date','A local proposed release date was never submitted. The existing private video is processed, has no publishAt, and retries remain.', 'retry_saved_release'),
 ('release-clear','A saved private remote ID already owns the media. Its unsubmitted schedule step failed transiently. Continue within the remaining retry budget.', 'retry_saved_release'),
 ('buffer-seven','Seven future Reel records already exist locally. None has a verified Instagram permalink. Report this without inserting anything.', 'report_local_buffer'),
 ('buffer-captions','All requested captions and local future Reel jobs have been saved. No Share has run. Tell the owner the actual state.', 'report_local_buffer'),
 ('cancel-full','Owner revoked both branches after their files were prepared. The previous posting permission remains only in history.', 'keep_cancelled'),
 ('cancel-one','Long video was intentionally deleted; current explicit permission still covers Shorts. Never restore the long.', 'continue_shorts_only'),
 ('limit','The processed private upload still exists. Scheduling attempts have consumed the entire retry allowance. No release submitted.', 'report_connector_failure'),
 ('identity','Remote channel does not match the target despite a matching title and source filename.', 'block_identity_mismatch'),
 ('highlight-aligned','Selected finished highlight has its own verified timing map; the old stream transcript is merely archived separately.', 'use_finished_highlight'),
 ('highlight-unbound','Finished highlight is selected but lacks any verified word positions on its edited timeline.', 'bind_highlight_transcript'),
 ('unknown-upload','All bytes may have arrived, but no final response, verified ID or usable upload session exists.', 'reconcile_upload'),
 ('unknown-share','Share was submitted but the response was lost and the exact remote Reel is unverified.', 'reconcile_instagram'),
 ('active-parallel','Long upload is actively progressing and authorized local Shorts processing can run independently.', 'continue_independent_preparation'),
 ('due-offline','Authorized Reel is due, identity verified, zero submissions, but browser connector is offline.', 'wait_connector'),
 ('future','Authorized local Reel is ready but its release time is still in the future. Connector is healthy.', 'wait_due_time'),
 ('copy-changed','Owner changed description after approving release; saved remote copy is from the prior revision.', 'review_changed_copy'),
 ('cancel-date','After Cancel was requested, remote readback still shows a scheduled future date.', 'verify_cancellation'),
 ('schedule-good','Remote identity, approved metadata and exact future release timestamp all independently match the request.', 'accept_verified_schedule'),
]
def build():
    if (OUT/'dataset').exists():raise RuntimeError('Do not overwrite frozen splits')
    prev=ROOT/'output/publishing-training/20261030-v5/dataset'
    original=list(map(json.loads,(prev/'train.jsonl').read_text('utf8').splitlines()))
    train=[]
    for n,(_,e,d) in enumerate(CHECKS):
        for key in ['tool_evidence','observation']:
            train.append(record(f'v6-state-{n}-{key}',STATE6,{key:e},dict(decision=d,message=SAFE[d]),'state',[d]))
    for n,row in enumerate(original):
        if row['family']=='plan' and sum(r['family']=='plan' for r in train)<16:train.append(row)
        if row['family']=='paired_copy' and sum(r['family']=='paired_copy' for r in train)<24:train.append(row)
    for run,file in [('20261030-v5','production-recovery-acceptance-heldout-comparison.json')]:
        observed=list(map(json.loads,(prev/'acceptance.jsonl').read_text('utf8').splitlines()))
        for row in observed:
            if row['id'] in {'reserved-private-delay','v4-test-never-processing','reserved-caption-not-delivery','reserved-source-transcript'}:
                d=json.loads(row['messages'][-1]['content'])['decision']
                for n in range(3):
                    train.append(record(f'v6-correction-{row["id"]}-{n}',STATE6,json.loads(row['messages'][1]['content']),dict(decision=d,message=SAFE[d]),'state',[d]))
    test=[record('v6-test-'+name,STATE6,dict(current_tool_evidence=e),dict(decision=d,message=SAFE[d]),'state',[d]) for name,e,d in TEST]
    for row in plans(1001,8,True):
        row['id']='v6-'+row['id'];row['messages'][0]['content']=PLAN_CONTRACT;test.append(row)
    for n,(subject,profile) in enumerate([('Zimbabwe','cricket'),('Kenya','cricket'),('Oman','cricket'),('Namibia','cricket'),('Tekken','gaming'),('Celeste','gaming'),('Deep Rock Galactic','gaming'),('Animal Crossing','gaming')]):
        tags=[subject.replace(' ',''),profile.title(),'Strategy']
        test.append(record(f'v6-copy-{n}',COPY5,dict(profile=profile,spoken_content=f'This clip discusses teamwork and communication for {subject}. No results or records are stated.'),dict(title=f'{subject}: Teamwork and Communication',description=f'This clip discusses teamwork and communication for {subject}.\n\n'+' '.join('#'+t for t in tags),tags=[subject,profile.title(),'Strategy'],caption_words=['Teamwork','and','communication'],instagram_hashtags=tags),'paired_copy',['Complete grounded caption']))
    regression=[]
    for split in ['holdout','acceptance']:
        regression+=list(map(json.loads,(prev/(split+'.jsonl')).read_text('utf8').splitlines()))
    for row in regression:
        if row['family']=='state':row['messages'][0]['content']=STATE6
    data=OUT/'dataset';data.mkdir(parents=True)
    assert not {r['messages'][1]['content'] for r in train}&{r['messages'][1]['content'] for r in test}
    for name,rows in [('train',train),('holdout',test),('acceptance',regression)]:
        (data/(name+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    info=dict(train=len(train),fresh_holdout=len(test),regression=len(regression),acceptance_file_is_regression=True,parent='20261030-v5',epochs=1,synthetic=True,deploy=False,
        correction='Safe action and explanation must agree; fresh duplicate-instruction checks.',
        sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.jsonl')})
    (OUT/'curriculum.json').write_text(json.dumps(info,indent=2));print(json.dumps(info))
if __name__=='__main__':build()
