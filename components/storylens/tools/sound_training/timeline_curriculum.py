"""Source-qualified timeline teaching; synthetic transfer examples are not transcribed stems."""
from pathlib import Path
import json,copy,hashlib
from tools.sound_training.remediation import SYSTEM

HASHES=['18743eb32bf7598868300400bff69422f624cd5d645584ef5212b673d4aef9d0',
        'e9edb0c1f275e051641bf996dd560730e4b80dab1e37dcff06bcad287e17e0e9',
        '7f35cb73152ae3559a41e543ebfba0be69105817e33343a228e9da3531965315']
# Teacher-authored examples. Supplied times are hypothetical exercise facts, not measured reference events.
CASES=[
('same_scene_bridge','Three camera cuts show the same riverside walk from 0 to 7 seconds; river ambience already fits. Should each cut restart it?',
 'The scene remains one riverside location with an effective existing bed.',
 'Keep one continuous river bed across the cuts. Add footsteps only for evidenced steps and perspective; a cut itself does not require a swoosh.',
 'Bridge 0–7 seconds without restarting the recording at each cut; shape perspective where the camera distance changes.',
 'Preserve continuity and dialogue. Avoid doubling the existing river layer.',
 'Exact gain and source offset need the actual recording; steps are conditional on action evidence.'),
('attack_alignment','The event lands at 10.00 seconds. The selected untrimmed effect peaks 0.45 seconds into its file and has a useful 1.8-second tail after that peak. Where does it go?',
 'Event 10.00, source peak offset 0.45 and tail 1.8 seconds are supplied.',
 'Start the untrimmed clip at 9.55 seconds so its peak lands at 10.00; retain the useful tail to 11.80.',
 'Timeline start = event time minus source peak offset. If trimming the source, recompute using the retained offset.',
 'Fade the tail only if it conflicts with speech or the next event; do not cut at visual settling.',
 'Confirm source bounds and whether its pre-peak lead-in suits the event.'),
('five_not_quota','An editor reference has many staggered tracks. Must every new three-second shot contain five effects?',
 'A dense reference timeline is visible, but no five-sound requirement follows.',
 'Choose distinct functions: location, action body, contact, optional anticipation and tail when justified. Use fewer if roles are already covered; permit richer overlap when it serves the scene.',
 'Give each role its own event anchor and useful duration; do not start or end all clips together.',
 'Audition the ensemble and mute redundant layers. Keep one dominant story cue and room for speech.',
 'Track count does not prove simultaneous audible sources or their gains.'),
('mixed_source_once','An uploaded motorcycle edit already has its approved song and a good transition impact. Add missing engine and gravel sounds only.',
 'Song and impact already exist; engine and gravel are the requested missing physical roles.',
 'Preserve original audio once. Add matched engine activity and tire/gravel texture only where the bike action supports them. Do not add a second song or another impact.',
 'Follow acceleration and tire contact, with natural tails and changing distance rather than 0.1-second slices.',
 'Place Foley around the existing song and voice. A single mixed source cannot independently turn down its song.',
 'Verify engine type, action intervals and source recordings; stationary shots alone do not prove revving.'),
('uncertain_labels','A timeline screenshot shows Page Flip, Clock, Riser, Reverb and several truncated filenames. Can these prove exactly what every audible layer is?',
 'Visible labels support candidate source roles; some names are truncated and no stems are supplied.',
 'Record visible names and overlapping structure, but mark audible identity, mute state and exact gain as unverified. Use the structural lesson, not a fabricated exact reconstruction.',
 'Measure readable ruler positions or use relative anchors; do not invent numeric clip boundaries.',
 'Reverb may be a return or rendered tail; do not automatically treat it as another dry source.',
 'A mixed soundtrack and filename labels cannot reveal every isolated contribution.'),
('voice_masking','A title landing has a low body, bright contact, airy movement and decay. Together they cover the first word of narration. Keep all four loud?',
 'The stack masks a specific spoken word.',
 'Keep only complementary contributions. Reduce or remove the competing bright/contact layer first, shape the body and tail, and keep the word intelligible.',
 'Keep synchronization; use local gain envelopes around the word instead of shifting the whole stack away from the event.',
 'Check the combined bus and headroom, not just solo tracks. Do not add more effects to solve masking.',
 'No absolute dB values are justified without source loudness and listening.'),
('water_context','A swimmer slides down a flume for 2.6 seconds and splashes into a pool; water and pool activity are visibly established. How should layers differ from a UI animation?',
 'Continuous sliding, water movement and a landing splash are established physical actions.',
 'Use water/slide friction during descent, a landing splash and its decay, with compatible continuous pool ambience. A joyful tonal flourish is optional editorial support if allowed; no mouse click substitution.',
 'Sustain descent layers across 2.6 seconds; anchor splash to contact and let droplets decay beyond it.',
 'Match water scale and perspective; preserve speech/music and avoid several identical splash recordings on top of each other.',
 'Exact landing time and clip offsets require the video; do not invent whistles or crowds.'),
('cricket_context','A cricket documentary shows bat-ball contact followed by a visible cheering crowd while a narrator explains the winning shot.',
 'Bat contact and crowd response are established; narration remains important.',
 'Use a matched bat crack, believable stadium bed and a shaped crowd reaction. Add a restrained editorial low emphasis only if it improves the story; do not use a gunshot for bat contact.',
 'Anchor the crack to contact and let the crowd develop across the reaction, not a short click on each cut.',
 'Keep narration foreground; automate crowd/body rather than mute all atmosphere. Retain useful original sports audio once.',
 'Exact frame timing, source distance and levels need inspection. Do not invent commentator words.'),
('garage_perspective','A car visibly accelerates away through a garage from 1 to 5 seconds. What makes its engine layer convincing?',
 'Acceleration, movement away and an enclosed garage are supplied.',
 'Choose a matching acceleration recording with believable mechanical texture. Follow its changing load and distance; use compatible enclosure/reflection rather than unrelated UI clicks.',
 'Cover the 1–5-second motion and useful decay. A pass-by peak should match closest approach if shown, not every edit cut.',
 'Shape distance, brightness and reflections together. Do not sum multiple full-band engine takes merely for track density.',
 'Vehicle type, original audio and source perspective still need checking.'),
('page_pencil','A notebook page turns, then a pencil taps a wooden desk twice while the creator thinks. Explain a sound plan without absolute timestamps.',
 'One page movement and two pencil contacts are supplied.',
 'Choose paper movement for the page and two appropriately light wooden pencil contacts. Thought may use silence or an optional subtle editorial tone; thinking is not a physical ticking clock.',
 'Anchor page movement to its turn, and each tap to its own contact; retain small resonances. Measure absolute times later.',
 'Vary the tap articulation naturally and protect the voice. Do not add a generic click under every caption.',
 'Check actual contact surface and whether good source taps already exist.'),
('riser_role','A calm mountain shot precedes a dramatic destination reveal. The owner permits sound effects but wants the existing music retained.',
 'The reveal has a contrast in scale; existing music is protected.',
 'An editorial swell can anticipate the reveal and resolve into a compatible restrained impact/tail. Keep calm space before it; environmental wind needs actual location evidence.',
 'Build toward the measured reveal and let the decay continue after it. Do not repeat the same swell on every mountain cut.',
 'Fit the swell around the existing song and dialogue; avoid another music track.',
 'No onset time, gain or physical weather source has been supplied.'),
('caption_hierarchy','A talking head has twelve routine caption words, one big heading and one important number. How many clicks?',
 'Captions have unequal narrative importance.',
 'Routine readable words can stay silent. Consider a small movement/contact combination for the heading and a distinct restrained accent for the important number. No click-per-word rule.',
 'Use measured heading/number entrances and useful tails, not uniform 0.1-second cuts.',
 'Match the emotional tone and preserve clear consonants. Separate intentional graphic sound from physical ambience.',
 'The script and motion are needed to choose exact moments and source timbre.'),
('tail_and_cut','A resonant metal contact at 4.0 seconds has a useful 2.2-second decay. The camera cuts at 4.3 to another angle of the same object.',
 'The same object and location continue after the cut.',
 'Retain the contact decay across the cut through about 6.2 seconds if it remains useful. The picture cut is not a mandatory audio endpoint.',
 'Contact at 4.0; natural tail to 6.2. Crossfade only when the perspective/source transition needs it.',
 'Reduce masking with an envelope; avoid restarting the metal hit on the new angle.',
 'Check subsequent speech and source tail rather than assuming full-level sustain.'),
('negative_space','The creator stops joking and says something painful. The timeline currently has a bright click, boing and upbeat riser beneath that phrase.',
 'The emotional intent changes from comedy to vulnerability.',
 'Remove or reduce the comic punctuation and leave room for the phrase. Retain existing room continuity; optional permitted subtle tone must serve the emotion.',
 'Shape the transition around the actual phrase; do not fill the pause just because the timeline looks empty.',
 'Prioritize voice and contrast. A quieter moment makes later emphasis meaningful.',
 'No rain, birds or new physical activity is established by sadness.'),
('source_unavailable','A bicycle gear change needs mechanical detail, but the local library returns only camera clicks. What should you do?',
 'A bicycle gear event needs a matching source; camera clicks are unsuitable.',
 'Search enabled providers for bicycle gear/chain mechanism, verify rights, download and decode a relevant candidate. If unavailable, report the missing layer rather than substitute a random click.',
 'Leave the exact source offset unresolved until inspected; then align the audible gear action to the event.',
 'Compare candidates against existing bicycle sound and preserve it once.',
 'A search result or proposed download is not a delivered audio clip.'),
('five_role_example','A stylized suitcase landing closes a travel montage. The drop and floor contact are visible; a quiet station bed already exists. Suggest a rich but justified ensemble.',
 'Suitcase motion/contact and existing station continuity are established.',
 'Keep the station bed, add suitable air/movement before landing, suitcase body/contact, small latch/rattle if actually supported, and a compatible natural room tail. An editorial low emphasis is optional, not compulsory.',
 'Stagger anticipation, contact and decay around the landing; the station bed bridges the whole scene.',
 'Treat this as one event ensemble: trim redundant lows and preserve speech/music. Do not force every possible layer.',
 'A latch rattle and added bass require justification; exact sources, clock time and gains remain unknown.')
]

GATE=[
('ferry_bridge','A continuous ferry hum covers 0–9 seconds, with picture cuts at 2 and 6. Should the hum restart at both cuts?', 'No; continuity across same scene, only perspective changes, no obligatory whoosh.','same-scene continuity'),
('offset_transfer','A cymbal swell should peak at 7.25 seconds. Its retained source peaks 0.6 seconds after the clip starts and decays for 1.5 seconds after that. Give placement.', 'Start 6.65, peak 7.25, useful tail to 8.75; no visual cutoff.','numeric anchor transfer'),
('raincoat_foley','A raincoat zipper moves for 1.7 seconds in a silent room. The title of the story is Storm Inside. Suggest sound layers.', 'Zipper over action and natural tail, existing room, no invented storm/rain; optional editorial emotional tone labeled as such.','source and metaphor'),
('caption_change','A presenter softly explains a bereavement while ordinary subtitles reveal word by word. Should each word get a pop to fill the timeline?', 'No; preserve voice, restrained continuity and negative space; no pop-per-word or invented weather.','emotional hierarchy'),
('stack_masking','A stone landing ensemble has six effects but three are similar sub booms and the narration is obscured. How do you improve it?', 'Remove/reduce redundant booms, retain complementary contact/body/tail, shape gain and protect speech; six is no quality target.','ensemble mixing'),
('receipt_transfer','A sports crowd recording appears in search, but its license and actual downloaded audio are unknown. Is that layer ready for export?', 'No, verify rights, retrieve/decode and inspect then place; report pending honestly.','source delivery')
]

def build(root):
    root=Path(root); previous=root/'output/sound-training/20261030-remediation/dataset/train.jsonl'
    old=[json.loads(x) for x in previous.read_text(encoding='utf-8').splitlines()]
    rows=[];seen=set()
    # Replay all unique applied/corrective questions plus a distributed original-guide sample.
    for i,row in enumerate(old):
        question=row['messages'][-2]['content']
        if question in seen:continue
        if i<304 and i%8:continue
        seen.add(question); r=copy.deepcopy(row);r['id']='replay-'+r['id'];r['rehearsal']=True;rows.append(r)
    for identity,q,e,d,t,m,u in CASES:
        target=json.dumps(dict(evidence=e,decision=d,timing=t,mix=m,uncertainty=u),ensure_ascii=False)
        for repeat in range(4):
            rows.append(dict(id=f'timeline-{identity}-{repeat}',case_id=identity,source_kind='timeline_teacher_example',
                synthetic=True,audio_quality_verified=False,reference_sha256=HASHES,
                provenance='Teacher-authored transfer scenario informed by visible timeline relationships, owner direction and prior guide; not an isolated-stem transcript.',
                messages=[dict(role='system',content=SYSTEM),dict(role='user',content=q),dict(role='assistant',content=target)]))
    holdout=[dict(id=i,rubric=r,messages=[dict(role='system',content=SYSTEM),dict(role='user',content=q),dict(role='assistant',content=a)]) for i,q,a,r in GATE]
    return rows,holdout

def write(root):
    root=Path(root);out=root/'output/sound-training/20261030-tutorial-timeline/dataset';out.mkdir(parents=True,exist_ok=True)
    rows,holdout=build(root)
    for name,data in [('train',rows),('holdout',holdout)]:
        (out/f'{name}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data),encoding='utf-8')
    receipt=dict(training_rows=len(rows),new_unique_scenarios=len(CASES),fresh_holdouts=len(holdout),
        rehearsal_rows=sum(bool(x.get('rehearsal')) for x in rows),parent='20261030-remediation/adapter',
        source_hashes=HASHES,exact_audio_reconstruction=False,auto_deploy=False,
        sha256=hashlib.sha256((out/'train.jsonl').read_bytes()).hexdigest())
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))

if __name__=='__main__':write(Path(__file__).resolve().parents[2])
