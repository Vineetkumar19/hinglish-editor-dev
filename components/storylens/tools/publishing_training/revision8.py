"""Correct observed v7 routing failures; retain its failed checks as development."""
import hashlib,json
from tools.publishing_training.curriculum import ROOT,plans,record
from tools.publishing_training import revision7 as v7
OUT=ROOT/'output/publishing-training/20261030-v8'
PREP=v7.PREP+'\nCritical routing rule: when mode=shorts, thumbnail MUST be the empty string, even when selected_thumbnail contains a valid path. Copy selected_thumbnail only for long or highlights. The application does not attach a thumbnail to Shorts or Reels. For long AND highlights, platforms MUST be ["youtube"]. Only shorts has ["youtube","instagram"]. Infer mode from the requested operation, never from the filename; final video.mp4 can be the source for requested Shorts.'
STATE=v7.STATE+'\nClassify the actual failure before considering clip count. One invalid caption in seven saved clips means correct_failed_copy_only, NOT report_buffer_gap. A request above the owner maximum is report_capability_gap, NOT report_buffer_gap. A supplied image that does not decode is report_capability_gap; a file changed after approval is block_identity_mismatch.'

def prep(n,held):
    row=v7.preparation(n,held);row['messages'][0]['content']=PREP;row['id']='v8-'+row['id'];return row

def build():
    if OUT.exists():raise RuntimeError('Preserve frozen datasets')
    data=OUT/'dataset';data.mkdir(parents=True)
    previous=ROOT/'output/publishing-training/20261030-v7/dataset'
    train=[]
    for split in ['train','holdout']:
        for row in map(json.loads,(previous/(split+'.jsonl')).read_text('utf8').splitlines()):
            if row['family']=='state':row['messages'][0]['content']=STATE
            if row['family']=='preparation':row['messages'][0]['content']=PREP
            row['id']='v8-development-'+row['id'];train.append(row)
    train.extend(prep(n,False) for n in range(500,536))
    fresh=[]
    evidence=[
      ('one-copy','Exactly seven clips and their timings are saved. Only the sixth caption failed factual grounding; six other copies passed.','correct_failed_copy_only'),
      ('weekly-limit','This owner permits at most seven paired weekly clips; current instruction asks eight. Do not silently cap or add clips.','report_capability_gap'),
      ('corrupt-image','The explicitly requested documentary JPEG is present but cannot be decoded as an image. Its original fingerprint is unchanged.','report_capability_gap'),
      ('cover-replaced','The owner-selected highlights cover was replaced after approval and now has a different fingerprint.','block_identity_mismatch'),
      ('private-no-date','Upload is processed/private with exact channel and ID. Studio control loading failed before submit; one bounded attempt remains.','retry_saved_release'),
      ('no-budget','Processed private video exists. All permitted visibility-dialog retries failed. Zero attempts remain.','report_connector_failure'),
      ('schedule-verified','Independent readback matches video, channel, approved text and intended future publishAt.','accept_verified_schedule'),
      ('same-job','Schedule was clicked repeatedly for the same seven clips; their original queue entries and remote IDs remain saved.','reuse_saved_jobs'),
      ('cancelled','Owner cancelled the entire long-plus-seven-Shorts request; previous approval is historical.','keep_cancelled'),
      ('partial-cancel','The owner deleted the long but currently authorizes the seven existing Shorts separately.','continue_shorts_only'),
      ('seven-buffer','Seven Reels are ready in the local authorized future queue; no Instagram share receipt has been returned.','report_local_buffer'),
      ('missing-timing','The selected finished highlight has no verified edited-timeline speech positions.','bind_highlight_transcript'),
    ]
    for name,e,d in evidence:
        row=v7.state_row('v8-fresh-'+name,e,d);row['messages'][0]['content']=STATE;fresh.append(row)
    fresh.extend(prep(n,True) for n in range(700,724))
    regression=list(map(json.loads,(previous/'holdout.jsonl').read_text('utf8').splitlines()))
    for row in regression:
        if row['family']=='state':row['messages'][0]['content']=STATE
        if row['family']=='preparation':row['messages'][0]['content']=PREP
    for name,rows in [('train',train),('holdout',fresh),('acceptance',regression)]:
        (data/(name+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf8')
    info=dict(train=len(train),reserved_checks=len(fresh),seen_regression=len(regression),parent='20261030-v7',epochs=1,
      live_actions=False,auto_deploy=False,previous_holdout_now_development=True,strict_state_template=True,
      sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.jsonl')})
    (OUT/'curriculum.json').write_text(json.dumps(info,indent=2));print(json.dumps(info))
if __name__=='__main__':build()
