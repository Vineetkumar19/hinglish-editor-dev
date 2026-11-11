"""Explicit correction SFT: former evaluation cases now become training data.

New holdouts below are separate. Never report memorized regressions as unseen
generalization. All sources/guide examples remain preserved.
"""
from pathlib import Path
import sys,json,copy,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import decisions,revision
from diagnose_instruction_scope import FRESH
SYSTEM=("You are Storylens's sound designer. Answer the actual question. Before selecting sounds, "
 "state a concise evidence summary containing only supplied facts. Separate physical source activity "
 "from rhetorical meaning and optional editorial effects. Missing source activity stays unknown; "
 "do not fill it with assumed voices, appliances, weather, birds or footsteps. "
 "A proof question is not an instruction to create the hypothetical sounds. "
 "Use only supplied times, otherwise relative event anchors. Preserve useful natural decay beyond "
 "visual settling, approved source audio and intelligible dialogue. Choose purposeful complementary "
 "layers, not a fixed count or repeated click template. Verify retrieval access, license, decoding "
 "and relevance before claiming a usable source. For decisions return JSON with evidence, decision, "
 "timing, mix and uncertainty. Theory questions may use concise prose. /no_think")

# evidence, timing, mix, uncertainty for the previously tested questions.
DETAILS={
 'cafe_title':('Narration, small labels, one major heading and an existing song are supplied; no individual cafe actions or clock times are given.', 'Use the heading landing and relevant label entrances as relative anchors; extract actual times first.', 'Preserve the existing song and speech. Do not invent separate music control if they are one file. Judge effect loudness from sources.', 'Cafe chatter, cup clinks and source levels are not confirmed. Do not assume them.'),
 'tram_world':('A tram visibly passes for 4.2 seconds beneath an interview; existing tram audio is weak.', 'Sustain the appropriate pass-by over the 4.2-second movement, with a useful natural tail and changing perspective.', 'Match the original tram and keep dialogue foreground; avoid arbitrary percentages and duplicate layers.', 'Exact source offsets and level depend on the selected recording; a horn or other city activity is not established.'),
 'dry_irony':('The arcade is nearly deserted; packed is a sarcastic contrast, not crowd evidence.', 'Use the reaction or phrase ending as a relative anchor for an optional editorial cue; no clock times supplied.', 'Retain quiet location continuity and clear voice. A dry comic sting is optional editorial punctuation.', 'No vending machine, voices, footsteps or neon buzz are established; do not invent them as ambience.'),
 'leather_action':('A leather bag zip moves for 1.9 seconds; a three-second zipper and generic click are available.', 'Select a matching zipper movement across 1.9 seconds; align its audible onset and keep a useful tail within bounds.', 'Use the zipper at believable proximity below narration. Do not add the click merely because it is available.', 'Inspect source offsets, usable duration and whether any terminal contact is actually visible/audible.'),
 'headphone_truth':('Only a screenshot and energy curve are available, with no confirmed audio-source identities.', 'Timing of particular chimes or bass hits is unverified. Do not invent timestamps.', 'No verified chime/bass mix can be reconstructed from these inputs.', 'Actual audio or trustworthy source annotation is required. Energy peaks do not establish instruments or layer counts.'),
 'overlay_preserve':('An effective swoosh and a song already exist in the source; the proposal duplicates both.', 'Keep their original timing; no new cue is needed at that moment.', 'Play source audio exactly once; add only a justified missing function after audition.', 'No timestamps, gains or new-source need are supplied. Do not invent a five-second interval.'),
 'unavailable_site':('Local rain is unsuitable; Freesound access is unavailable; Commons is enabled.', 'Retrieve first; align a verified rain recording to actual scene bounds later.', 'No sound has been downloaded or mixed yet. Preserve voice/music and do not assume thunder.', 'Check the individual license and decode/audition the result; a search result is not a completed source.'),
 'effect_tail':('The sound has a 1.6-second decay; the title settles in 0.3 seconds.', 'Align the intended attack/peak to the title event and retain the useful 1.6-second decay; visual settling is not a cutoff.', 'Shape or lower the tail only for an actual masking/next-event conflict; avoid hard truncation.', 'The surrounding speech and next event require listening, but the supplied decay is known.'),
 'sustained_cause':('Wheel squeal accompanies a visible 2.8-second train turn beneath narration.', 'Cover the 2.8-second turn with matching sustained rail friction and a useful tail.', 'Keep voice foreground, compatible train perspective and no random click stack.', 'The source recording, gain and exact onset offset must be checked.'),
 'resonance':('The notification rings for 1.2 seconds; the badge reveals in 0.18 seconds.', 'Keep the useful 1.2-second resonance beyond visual reveal; synchronize its attack to the intended event.', 'Reduce/fade only for actual masking or the next beat; do not chop at 0.18 seconds.', 'Exact source level and neighboring audio are unknown; the ring duration is supplied.'),
 'evidence_limit':('Only four amplitude peaks and a still desk image are provided.', 'No verified keyboard onset times can be assigned.', 'Do not construct or train a four-click reference mix as fact.', 'Energy peaks cannot identify keyboard clicks. Inspect actual audio and relevant action before assigning a source.'),
 'relative_clock':('A map pin drops, but no timestamps or video are supplied.', 'Use pin landing as the relative anchor; leave absolute placement unresolved until measured.', 'An optional graphic accent is editorial, not proof of a physical pin impact. Protect speech.', 'Clock time, source and gain are unknown. Do not invent them.'),
 'mixed_source':('Voice, song and a useful title hit are already one mixed source; only missing Foley is requested.', 'Keep original synchronization; add Foley only at supported action anchors.', 'Preserve source once, no duplicate song/hit. One stereo mix does not permit independent song gain without separation.', 'Identify actual missing actions and suitable recordings before adding anything.'),
 'retrieval_receipt':('Search returned a fountain page, but no license or decoded local file is verified.', 'Leave the planned layer unresolved until a valid source is retrieved.', 'No completed ambience clip exists yet; do not add a placeholder or claim export readiness.', 'Verify per-file rights, download through enabled access, decode, inspect and select a relevant section.'),
 'talking_head_emotion':('A humorous talking-head opening turns to grief while captions continue; no weather or other activity is supplied.', 'Follow the measured emotional transition; use relative anchors until times are known.', 'Reduce comic/graphic density and protect speech. Preserve room/source continuity; a restrained tonal treatment is optional editorial support if music changes are permitted.', 'Do not invent rain, wind, birds, footsteps or new music permissions from grief.'),
 'sarcasm_setting':('The gym is explicitly empty and silent; wild party is deadpan metaphor.', 'An optional dry editorial response can follow the line; no absolute times are given.', 'Keep quiet location sound and clear speech. Do not label cheering/dance music as real environment.', 'Intentional ironic sound contrast would be an explicit editorial choice, not evidence of crowd activity.'),
 'empty_office':('The office is empty; the presenter jokes about everyone working.', 'No real worker action has a supported cue time.', 'Preserve quiet office/source continuity. An optional comic accent must be identified as editorial.', 'No typing or conversations are established. The verbal joke does not create workers.'),
 'shape_not_identity':('A spectrogram has a vertical stripe but no confirmed source identity.', 'Do not assign a door-slam timestamp from this alone.', 'No verified door-slam layer exists to mix.', 'Many abrupt sounds produce stripes; actual audio or trustworthy annotation is required.'),
 'fading_chord':('The title settles in 0.25 seconds; the underlying chord decays for two seconds.', 'Keep the useful two-second fade beyond the settle; synchronize the intended attack separately.', 'Reduce or fade for a real overlap conflict, not merely because the graphic stopped.', 'Speech/next-event context and source level are unspecified.'),
 'quiet_memory':('An indoor creator misses her grandfather; no movement, appliances or outdoor activity is described.', 'Leave space for the reflective phrase; no absolute cue times are supplied.', 'Preserve voice and existing room tone. A sparse gentle tonal layer is optional editorial support only if compatible with existing music and permissions.', 'Do not invent footsteps, appliances, weather or birds. Indoor location alone is not source-action evidence.'),
}
FRESH_ANSWERS={
 'empty_office':'No. Preserve the empty-office reality; typing and conversation would invent real activity. A clearly editorial comic accent may be considered separately.',
 'shape_not_identity':'No. A spectrogram stripe cannot establish a car-door identity. Keep it unknown until actual audio or trustworthy source evidence is available.',
 'fading_chord':'No. Retain the useful two-second musical decay; the title stopping after 0.25 seconds does not require an audio cutoff.',
 'quiet_memory':'Preserve the voice and existing indoor room continuity; use space for reflection, with optional restrained tonal support if allowed. Do not invent physical activity or outdoor sound.',
}

GATE=[
 ('museum_irony','A silent gallery has no visitors in the shot. The guide jokes that the crowd is deafening. Should a crowd bed be added as real location audio?', 'No. Keep the observed quiet location; the statement is ironic. Any comic accent must be editorial, not invented crowd activity.','literal versus rhetoric'),
 ('grief_no_action','A seated narrator remembers a loss in a quiet room. Nothing moves and no other sound source is described. Give an appropriate sound direction.', 'Keep speech and existing room continuity, space for emotion, optional permitted subtle tonal support; no invented appliances, walking or weather.','no invented physical sound'),
 ('tail_new_numbers','A graphic finishes moving in 0.12 seconds. Its selected soft metallic accent has a useful 2.4-second resonance. Must the resonance be cut at 0.12?', 'No. Align attack to the event and retain useful resonance; shorten only for a real mixing conflict.','natural decay transfer'),
 ('watermark_waveform','A waveform contains six sharp peaks under a photo of a bicycle. Does this prove six gear shifts occurred?', 'No. Energy and a still bicycle photo do not prove gear-shift source identity or count. Inspect actual audio/action.','evidence identity transfer'),
 ('fabric_movement','A sleeve brushes a rough wall continuously for 2.1 seconds. Available sources are fabric scrape and mouse click. What should be chosen?', 'Use relevant fabric scrape through the observed movement and useful tail; no mouse-click substitution.','physical action and duration'),
 ('unknown_video_clock','Only a written description says a chapter card folds open. No timecodes exist. What exact timeline start can you promise?', 'None. Use the card-opening/settle as relative anchors, measure actual timing before committing absolute placement.','unknown timing'),
 ('source_control','The owner supplied one stereo track containing speech and music and asks for a paper-fold effect only. Can you independently lower the existing music with that source gain?', 'No, whole-source gain lowers speech too. Preserve source once and mix the supported paper Foley around it; separate music control requires stems/separation.','actual mix controls'),
 ('pending_download','The enabled search connector found an eligible-looking wind recording. The file has not downloaded or decoded. Can you mark the wind layer delivered?', 'No. Verify per-file rights, retrieve and decode, inspect relevance, then place/mix. Keep status pending until actual completion.','tool receipt truth'),
]

def build(root):
    rows,coverage=decisions.build(root)
    for r in rows:
        r['messages'][0]['content']=SYSTEM
        if r['source_kind']=='decision_curriculum':
            i=r['curriculum_case'];a=json.loads(r['messages'][-1]['content'])
            evidence=revision.SCENARIOS[i][1] if i<len(revision.SCENARIOS) else 'Supplied scenario: '+r['messages'][-2]['content']
            r['messages'][-1]['content']=json.dumps(dict(evidence=evidence,**a),ensure_ascii=False)
    correction_cases=list(revision.GATE)+list(decisions.GATE)+[(i,q,FRESH_ANSWERS[i],rubric) for i,q,_,rubric in FRESH]
    for identity,q,answer,rubric in correction_cases:
        evidence,timing,mix,uncertainty=DETAILS[identity]
        target=json.dumps(dict(evidence=evidence,decision=answer,timing=timing,mix=mix,uncertainty=uncertainty),ensure_ascii=False)
        for exposure in range(8):
            rows.append(dict(id=f'correct-{identity}-{exposure}',source_kind='supervised_correction',
                correction_id=identity,curriculum_exposure=exposure,previously_evaluated=True,synthetic=True,
                audio_quality_verified=False,messages=[dict(role='system',content=SYSTEM),dict(role='user',content=q),dict(role='assistant',content=target)]))
    return rows,coverage

def write(root):
    out=Path(root)/'output/sound-training/20261030-remediation/dataset';out.mkdir(parents=True,exist_ok=True)
    rows,coverage=build(root)
    holdout=[dict(id=i,rubric=r,messages=[dict(role='system',content=SYSTEM),dict(role='user',content=q),dict(role='assistant',content=a)]) for i,q,a,r in GATE]
    for name,data in [('train',rows),('holdout',holdout)]:
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data),encoding='utf-8')
    (out/'coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
    receipt=dict(training_rows=len(rows),original_lessons=304,applied_cases=48,previously_evaluated_correction_cases=20,
       correction_exposures=8,fresh_gate_questions=8,former_evaluation_cases_now_training=True,
       train_sha256=hashlib.sha256((out/'train.jsonl').read_bytes()).hexdigest(),auto_deploy=False)
    (out/'dataset-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
if __name__=='__main__':write(Path(__file__).resolve().parents[2])
