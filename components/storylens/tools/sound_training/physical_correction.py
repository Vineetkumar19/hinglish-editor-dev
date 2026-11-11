"""Corrective supervised examples; never used as a pre-authored inference timeline."""
import json, random
from pathlib import Path
from tools.sound_training.remediation import SYSTEM
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-physical-sources'

def record(identity,question,answer,kind='corrective_supervision'):
    return dict(id=identity,source_kind=kind,audio_quality_verified=False,
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':question},
                  {'role':'assistant','content':json.dumps(answer)}],
        rubric=['Answer the supplied evidence, not a memorized timeline.','Choose physical source, useful duration and audibility without invented actions.'])

def build():
    folder=OUT/'dataset';folder.mkdir(parents=True,exist_ok=True)
    replay=[json.loads(x) for x in (ROOT/'output/sound-training/20261030-timeline-tail-correction/dataset/train.jsonl').read_text().splitlines()]
    cases=[
      ('motorcycle','Rear view from a moving motorcycle: a handlebar mirror and rider are visible. No foot contacts are shown.','motorcycle engine under riding load','pavement heels','engine','Keep engine activity for the observed ride; stop or transition when the vehicle shot ends.','Wind/road texture may complement the engine; never stack walking recordings over a ride.'),
      ('puddle','Shoes visibly displace shallow puddle water at each step.','wet footsteps with small splashes','dry forest footsteps','wet contacts','Anchor separate contacts to observed footfalls; retain the water decay.','Use real wet-surface articulation; a dry click cannot be converted into splashing by volume.'),
      ('waterfall','Close view of a broad waterfall continuously crashing onto rocks.','close waterfall roar and turbulent water','water from a kitchen tap','waterfall','Cover the entire waterfall scene, including the end, with natural continuous water.','A faucet is a different scale, source and texture; reject it even though both tags say water.'),
      ('rain','Rain is visibly falling on outdoor vegetation and wet clothing.','forest rain pattering on leaves','birds chirping','rain','Keep one continuous rain bed through the rainy location, with perspective changes.','Thunder and birds require their own evidence; rain is not a reason to invent them.'),
      ('stream','A person crosses a shallow rocky stream; water moves around their shoes.','small river flow plus wet footsteps','toilet flushing','stream','Keep flowing water continuous and sync wet contacts separately.','Do not replace an outdoor stream with indoor plumbing recordings.'),
      ('mud','Shoes sink and lift in soft muddy ground.','mud squelching footfalls','high heels on tile','mud contacts','Match the cadence and retain each soft suction/release tail.','Surface material matters as much as the general footsteps category.'),
      ('parked','A stationary bicycle leans on a wall; no person or moving machinery is visible.','no additional physical action cue','motorcycle revving','none','No moving-source event has been established.','A vehicle noun alone does not prove that an engine is running.'),
      ('tap','A hand opens a kitchen faucet into a steel sink.','water from a kitchen tap','large waterfall roar','faucet','Follow the tap opening and water duration.','Select the actual small indoor source rather than a spectacular unrelated waterfall.'),
      ('cricket','A bat visibly strikes the ball, followed by a stadium crowd reaction.','cricket bat contact and stadium reaction','gunshot and UI click','bat contact','Align the crack to contact; let the crowd swell develop across reaction shots.','Preserve commentary and avoid duplicate full-volume crowd beds.'),
      ('caption','A quiet talking-head clip has ordinary subtitles; no physical action or emphasized graphic occurs.','no automatic caption ticks','mouse click for every word','none','Routine subtitle words do not establish acoustic events.','Leave room for speech; use designed accents only for meaningful editorial emphasis.'),
    ]
    new=[]
    for i,(key,evidence,good,bad,role,timing,mix) in enumerate(cases):
      for variant in range(3):
        items=[{'id':'asset-A','description':good},{'id':'asset-B','description':bad}]
        random.Random(i*13+variant).shuffle(items)
        q=json.dumps({'task':'Choose a source and explain timing and mixing. Candidate order is arbitrary.','evidence':evidence,'candidates':items,'source_audio':'Existing voice and song must remain once.','observed_seconds':2+variant})
        answer=dict(evidence=evidence,decision='Choose asset-A: '+good+'. Reject asset-B: '+bad+'.',timing=timing,mix=mix+' Keep existing audio once and make the main action audible without covering speech.',uncertainty='Precise source offsets and final gain require the actual recording and mix measurements.')
        new.append(record(f'physical-{key}-{variant}',q,answer))
    for i,(base,duck,desired) in enumerate([(-10,2,-10),(-18,2,-14),(-10,1,-8),(-18,1,-12),(-10,2,-12),(-18,2,-18),(-4,2,-9),(-2,2,-8)]):
        # Existing production schema only allows attenuation; explicitly report an impossible boost.
        extra=desired-base+duck
        q=f'Production mixer: final approximate offset = category_base + level_db - duck_db. category_base={base}, duck_db={duck}, desired final offset={desired} dB. level_db is currently limited to -24 through 0. What should the planner return and why?'
        decision=(f'Use level_db={extra} dB.' if extra<=0 else f'The requested target requires level_db=+{extra} dB, which this schema cannot express. Use 0 as the loudest allowed value and report the capability mismatch; do not claim the desired level was achieved.')
        new.append(record(f'gain-domain-{i}',q,dict(evidence=f'Base {base}, duck {duck}, target {desired}, adjustment range [-24,0].',decision=decision,timing='No timing change is required.',mix='level_db is an ADDITIONAL adjustment, not the final voice-relative level. Never apply the target negative value a second time. Confirm exported effect against the concurrent original soundtrack.',uncertainty='Measured body loudness, masking and peak limiting can change the resulting loudness.')))
    specifics=[
      ('duplicate','Three descriptions walking, stepping and walking away refer to the SAME person, surface and interval. Should all three become full footstep beds?','Treat them as one physical source. Choose one footstep performance plus distinct justified water/ground detail; do not stack three different walking loops.'),
      ('coverage','A waterfall is visible from 18 seconds to the video end at 27 seconds. The current plan ends all effects at 21 seconds.','The ending is uncovered. Extend or continue a compatible waterfall recording through the observed end, with a natural final fade; do not invent a click at every second.'),
      ('seen','A twelve-frame montage contains a bike in frames 0–4, a bridge walk in 5–8, and wading in 9–11. One observation labels frames 0–11 walking.','Reject the blanket action interval. Request or use shot-specific visual evidence; bike riding, bridge walking and wading require distinct event ranges and sources.'),
      ('quiet','Effects measure 29 dB below the concurrent song. They are technically nonzero, but the owner cannot hear the physical action.','Do not call nonzero audio audible success. Raise the primary effect or reduce masking within permissions, check the actual combined mix, preserve the song and avoid clipping.'),
      ('same','The same river remains audible across three shots. The matching river asset was already used and a novelty rule offers a faucet instead.','Reuse the fitting river asset with the same explicit reuse_key and a continuity reason, vary its excerpt/perspective if useful. Source relevance wins over novelty; reject the faucet.'),
      ('library','A needed waterfall recording is missing locally. The library offers UI clicks and faucet water; a licensed public sound provider is enabled.','Search for a waterfall field recording with the correct scale and perspective. Verify access, license, decode and acoustic relevance before placing it. Do not substitute unrelated local sounds just to fill the timeline.'),
      ('song','An uploaded video already contains the desired song mixed with voice. The user requests sound effects only.','Retain the original stereo once and add only independently controlled effects. Do not generate another song or claim independent control of music embedded in the source.'),
      ('numbers','A quality report says 51 checks passed, but source matching and listening were not reviewed.','Report technical checks only. Do not claim natural, relevant or accepted sound design from valid JSON, track count or absence of clipping.')]
    for key,q,a in specifics:
        new.append(record('physical-rule-'+key,q,dict(evidence=q,decision=a,timing='Use supplied event intervals; missing exact contact times remain unknown.',mix='Protect voice, maintain purposeful audible physical sources and check the complete ensemble.',uncertainty='No independent listening acceptance has been supplied.')))
    held=[]
    for key,q,a in [
      ('kayak','A paddle visibly enters a lake and pushes water. Available sources: keyboard typing, paddle dip and pull, fountain pump. Which source?','Paddle dip and pull; sync water entry/pull and retain wet decay, not keyboard or fountain.'),
      ('snow','A person walks over crunchy snow, not water. Available: wet puddle steps, crunchy snow footfalls, horse hooves. Which source?','Crunchy snow footfalls at visible contacts, not splashes or hooves.'),
      ('gain','Base offset -8 dB, duck 1 dB, requested final -11 dB. Additional level_db is constrained -24..0. What value?','Use -2 dB additional: -8 -2 -1 = -11. Do not set -11 again.'),
      ('coverage','A visible electric fan runs continuously from 3 to 11 seconds across two camera angles. The first clip ends at 6 seconds. What now?','Continue a matching fan recording through 11 seconds; preserve continuity across the angle change rather than stop at 6 or invent multiple fans.')]:
        held.append(record('physical-heldout-'+key,q,dict(evidence=q,decision=a,timing='Use the supplied interval or measured contact.',mix='Keep relevant sources audible and preserve original audio.',uncertainty='Final sound quality needs actual audio review.'),'unseen_holdout'))
    train=replay+new
    for name,rows in [('train',train),('holdout',held)]:
        (folder/(name+'.jsonl')).write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n',encoding='utf8')
    (OUT/'curriculum.json').write_text(json.dumps({'replayed_prior_examples':len(replay),'new_examples':len(new),'unseen_holdouts':len(held),'prior_adapter':'20261030-timeline-tail-correction','owner_video_is_training_material':True,'manual_timeline_used_as_inference_answer':False},indent=2),encoding='utf8')
    print(len(train),'training examples;',len(held),'unseen holdouts')
if __name__=='__main__':build()
