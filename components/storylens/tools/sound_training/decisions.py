"""Applied decision SFT with preserved guide and a new, separate evaluation split.

Synthetic teacher examples are proposed designs, never claims about heard stems.
"""
from pathlib import Path
import sys,json,copy,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import revision,corpus
SYSTEM=("You are Storylens's sound designer. Answer the actual question before proposing a design. "
 "Separate observed action, audible evidence and editorial choices. Missing evidence stays unknown. "
 "Use relative event anchors when timestamps are absent; never invent clock times, durations, source IDs or completed downloads. "
 "Choose sustained physical sound for sustained action. Align attacks to events and retain useful natural decay; "
 "animation duration is not an automatic sound cutoff. Protect speech and existing approved music. "
 "Use selective meaningful accents and complementary layers, never clicks on every word or a fixed layer count. "
 "When retrieval is needed, use only enabled tools and verify license, decoding and relevance before claiming a usable asset. "
 "For a decision request return concise JSON with decision, timing, mix, uncertainty. For a theory question explain briefly. /no_think")

# These scenes teach general errors, not the earlier gate's questions/answers.
EXTRA=[
 ('A waveform spike occurs when a logo appears. Does that prove a gunshot was used?',
  'No. A spike measures energy, not source identity. Record the logo timing and inspect the actual audio before naming the sound.',
  'The logo entrance is a visual anchor; sound onset remains unverified.',
  'No new layer or gain is justified by this evidence alone.',
  'The sound could be many sources or mixed speech/music; do not label it a gunshot.'),
 ('A title uses a 0.4-second spring animation. A soft bell has a 2.3-second ring. How long should the cue last?',
  'Align the bell attack or desired peak to the title landing and retain the useful ring. Do not truncate it to the animation length.',
  'Let the ring decay up to its useful 2.3 seconds if the next beat permits; trim or fade for a specific conflict.',
  'Lower or shape the tail if it masks speech; do not replace its decay with an unrelated ambience.',
  'Actual source loudness and the next spoken beat require listening.'),
 ('A subtitle expands and the editor asks for a timing plan, but supplies no timestamp or video. What times do you give?',
  'Give event-relative timing and request or extract the actual onset before committing timeline clips.',
  'Movement follows expansion; the accent attack aligns with the settle. Absolute times are unknown.',
  'Keep the accent below the spoken phrase and preserve existing music.',
  'Do not invent a starting second or claim placement is complete.'),
 ('The source song and voice are one stereo file. Can you turn only the song down by 4 dB?',
  'Not with simple source gain: that lowers voice too. Preserve the approved source and mix added effects around it, or use explicitly requested stem separation.',
  'Retain original source timing exactly once.',
  'Use effect envelopes and spectral space to protect speech. Do not claim independent music ducking without a separate music stem.',
  'Separation may alter the voice; it needs audition before acceptance.'),
 ('A woman says she loves waiting in endless queues with obvious sarcasm. The frame shows an empty reception.',
  'Use the visible quiet reception as environment evidence, not the word queues. A dry pause or small comic sting can support the contradiction.',
  'Place an optional response after the sarcastic phrase or reaction, using actual word timing.',
  'Retain quiet room continuity and foreground speech; avoid crowd chatter without evidence.',
  'The performance may already carry the joke. Audition before adding a sting.'),
 ('A door latch visibly closes at 2.4 seconds, then the room remains still until 7.0. Available sources are a latch and a room bed.',
  'Use the latch for the closure and the room bed for continuity. These are distinct physical and environmental roles.',
  'Align the latch audible contact at 2.4; retain its natural tail. Continue suitable room tone through the scene to 7.0.',
  'Match perspective and keep background bed subdued; avoid adding repeated latches during stillness.',
  'Source hitpoint, recording length and existing room audio need inspection.'),
 ('A scooter is moving for three seconds, but the only retrieved source is a phone tap. Can you stretch it into an engine?',
  'No. Retrieve a scooter engine/pass-by with compatible action and perspective. A stretched tap is not relevant propulsion sound.',
  'Cover the three-second movement with an appropriate engine section, including approach and recession if visible.',
  'Keep source music and voice; balance engine and evidenced environment separately.',
  'If no suitable source is available, mark the engine layer missing instead of silently substituting a click.'),
 ('A shoe scrapes gravel then stops. The clip includes a 1.4-second scrape and a little settling dust.',
  'Use granular scrape texture for sustained contact, with a small settling grit tail if supported. A low body accent is optional editorial emphasis.',
  'Match the scrape to 1.4 seconds and retain a short plausible settling tail; do not fill the following stillness with scraping.',
  'Give the scrape texture and optional body separate spectral roles. Avoid turning an ordinary step into an explosion.',
  'Footstep surface and source perspective must match.'),
 ('A reaction caption appears while the speaker makes a vulnerable confession. Should it get a funny squeak?',
  'No automatic comic sound. Follow the vulnerable emotional meaning; restraint or a gentle tonal transition may be appropriate if requested.',
  'Leave space around the confession; do not accent every caption reveal.',
  'Keep voice intimate and clear and preserve quiet environment continuity.',
  'A funny effect would change the meaning; use one only if the creator clearly intends irony.'),
 ('A reverse cymbal file has its peak 0.8 seconds after file start. A transition locks at 9.6 seconds. Where does the file begin?',
  'Use the measured peak as the synchronization point.',
  'Start at 8.8 seconds so its peak lands at 9.6. Retain an appropriate release within timeline bounds.',
  'Keep the swell from masking the outgoing words; duck the effect if needed.',
  'Confirm the stated peak belongs to the chosen source excerpt and there is enough pre-roll.'),
 ('One shot has a real water splash already clearly audible. The new plan adds another identical splash over it.',
  'Keep the usable original splash and reject duplicate coverage. Add only a distinct missing perspective or body if the mix needs it.',
  'Preserve original synchronization and natural water decay.',
  'Avoid doubled transients and accidental loudness increase; source audio plays exactly once.',
  'Audition the original before deciding it needs enhancement.'),
 ('A search tool returned a rain result with title and URL but no license or decoded local file. Is the sound ready for export?',
  'No. Inspect individual rights, retrieve through the permitted connector, decode and check relevance before selecting it.',
  'Keep the rain cue planned but unresolved until a valid source and useful duration are available.',
  'Do not add an empty path or unrelated placeholder to the rendered mix.',
  'The result is only a candidate, not a successful download or licensed asset.'),
 ('There are five available effects but only a simple paper-card entrance. Must all five be layered?',
  'No. Choose only complementary functions: for example a short paper movement plus a restrained settle accent if needed.',
  'Follow entrance motion, align the settling attack and retain useful tails.',
  'Judge the combined cue below speech. Remove redundant high-frequency attacks or bass layers.',
  'The number of library files does not determine a good layer count.'),
 ('The on-screen diagram assembles over two seconds while the narrator explains a serious statistic.',
  'Use a restrained assembly texture or sparse accents for key structural arrivals, not a noisy pop on every component.',
  'Follow the two-second assembly and let the final cue decay naturally into the readable hold.',
  'Keep the statistic intelligible and avoid comedy or exaggerated impacts that change its tone.',
  'Exact component arrivals and source choice require the actual edit.'),
 ('A bass impact and a soft airy tail sound quiet alone but overload when combined with the song.',
  'Adjust the combined effect bus and reduce redundant energy rather than trusting individual levels.',
  'Retain meaningful attack alignment and natural tail; use envelopes to resolve conflicts.',
  'Measure combined peaks and loudness, lower or equalize competing low frequencies, and audition speech clarity.',
  'Fixed percentages or arbitrary dB values cannot establish a safe or tasteful mix without source measurements.'),
 ('The creator lists three mistakes, celebrates a success, then turns reflective in one talking-head reel.',
  'Build separate functions within a coherent palette: precise teaching accents, a small celebratory response, then reduced density for reflection.',
  'Anchor changes to actual phrase and visual boundaries. Routine subtitles do not need separate sounds.',
  'Keep narration foreground and existing song; do not paste one identical stack across all three moods.',
  'These are proposed treatments, not claims about sounds already heard.'),
]

GATE=[
 ('sustained_cause','A train wheel squeals through a visible 2.8-second turn beneath a narrator. How should you choose and time its effect?', 'Match a relevant sustained rail squeal through the turn, preserve natural tail and voice; no repeated clicks.','physical duration and perspective'),
 ('resonance','A glassy notification accent rings for 1.2 seconds after its attack; the visual badge is fully revealed after 0.18 seconds. How should the sound end?', 'Keep useful resonance beyond reveal unless masking or next event requires a fade.','natural decay'),
 ('evidence_limit','An amplitude plot shows four peaks beneath a still frame of a desk. Can you identify those peaks as four keyboard clicks?', 'No, energy and still image cannot identify sound sources; inspect audio before teaching identity.','evidence honesty'),
 ('relative_clock','A creator gives no video timestamps but asks you to add a cue to a map pin dropping. What timeline time should you report?', 'Report pin-contact relative anchor with absolute timing unresolved until analysis.','no invented timestamp'),
 ('mixed_source','The uploaded file already mixes voice, a song and a suitable title hit into one track. The user wants only missing Foley. What should stay?', 'Preserve original source once, no second song/title hit, add relevant missing Foley around dialogue; no unsupported independent stem gain.','preservation and actual controls'),
 ('retrieval_receipt','An enabled public audio search returns a fountain page, but no local file or license has been verified. Can the planner mark fountain ambience complete?', 'No, verify license retrieve decode and inspect relevance first; keep layer unresolved.','tool truth and rights'),
 ('talking_head_emotion','A talking-head clip switches from a humorous opening to grief, while animated captions continue throughout. How should the sound palette change?', 'Comic accents only where appropriate, reduce density for grief and protect speech; no per-word clicking.','emotional arc'),
 ('sarcasm_setting','The presenter calls a silent empty gym a wild party with a deadpan expression. Should you add cheering and dance music as environment?', 'No literal keyword interpretation; preserve quiet plausible gym ambience, optional restrained editorial response clearly distinct from physical world.','context and irony'),
]

def build(root):
    old,coverage=corpus.build_corpus(root);rows=[]
    for r in old:
        r=copy.deepcopy(r);r['source_kind']='revision_original';r['messages'][0]['content']=SYSTEM;rows.append(r)
    cases=[]
    for q,evidence,choice,timing,mix,check in revision.SCENARIOS:
        cases.append((q,choice,timing,mix,evidence+' '+check))
    cases.extend(EXTRA)
    for i,(q,*answer) in enumerate(cases):
        for exposure in range(3):
            rows.append(dict(id=f'decision-{i:02d}-exposure-{exposure}',source_kind='decision_curriculum',curriculum_case=i,
                curriculum_exposure=exposure,synthetic=True,audio_quality_verified=False,messages=[
                dict(role='system',content=SYSTEM),dict(role='user',content=q),
                dict(role='assistant',content=json.dumps(dict(zip(('decision','timing','mix','uncertainty'),answer)),ensure_ascii=False))]))
    return rows,coverage

def write(root):
    out=Path(root)/'output/sound-training/20261030-revision3/dataset';out.mkdir(parents=True,exist_ok=True)
    rows,coverage=build(root)
    holdout=[dict(id=i,rubric=r,messages=[dict(role='system',content=SYSTEM),dict(role='user',content=q),dict(role='assistant',content=a)]) for i,q,a,r in GATE]
    for name,data in [('train',rows),('holdout',holdout)]:
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data),encoding='utf-8')
    (out/'coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
    receipt=dict(training_rows=len(rows),unique_original_lessons=304,unique_applied_cases=48,applied_exposures=3,
      fresh_gate_questions=len(GATE),prior_gates_development_only=True,source_guide_pages=40,
      train_sha256=hashlib.sha256((out/'train.jsonl').read_bytes()).hexdigest(),auto_deploy=False)
    (out/'dataset-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
if __name__=='__main__':write(Path(__file__).resolve().parents[2])
