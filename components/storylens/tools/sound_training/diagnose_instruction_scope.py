"""Separate diagnosis: does an always-design brief distort factual questions?

Both base and adapter receive the identical short brief. No expected answers are
sent. This is development diagnosis, not proof of application acceptance.
"""
from pathlib import Path
import sys,types,shutil
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import runtime_gate,decisions,revision
ROOT=HERE.parents[1]
OUT=ROOT/'output/sound-training/20261030-revision3/instruction-scope'
SYSTEM=('Answer the actual question accurately before offering any action. '
 'A question about whether evidence proves something is not an instruction to create it. '
 'Keep literal scene facts separate from metaphor, emotion and proposed editorial additions. '
 'Do not invent physical activity, source measurements or timing. '
 'Preserve supported useful sound decay rather than equating it to visual animation length. '
 'When asked for a proposal, justify each addition from supplied evidence and distinguish optional editorial choices. '
 'Do not invent a crowd, animal or weather recording to express an emotion. '
 'Use words such as not applicable or unknown for fields unrelated to a factual question, with a brief reason.')
FRESH=[
 ('empty_office','An empty office is shown. The presenter jokes that everyone is hard at work. Should background typing and conversation be added as real office activity?', '', 'No physical workers invented; editorial irony distinguished.'),
 ('shape_not_identity','A spectrogram screenshot has a bright vertical stripe. Is it enough evidence to label the reference sound as a car door slam?', '', 'No unsupported source identity.'),
 ('fading_chord','A title settles in 0.25 seconds. A soft chord underneath fades for 2 seconds. Must its decay be chopped when the title stops moving?', '', 'No automatic truncation; natural decay with speech/next-event checks.'),
 ('quiet_memory','A creator describes missing her grandfather indoors. No outdoor sounds are reported. Choose suitable sound direction without changing the represented location.', '', 'No invented rain or birds; speech and room continuity; optional appropriate tonal treatment.')
]
def main():
    OUT.mkdir(exist_ok=True)
    shutil.copy2(OUT.parent/'adapter.gguf',OUT/'adapter.gguf')
    selected=[r for r in revision.GATE if r[0] in ('headphone_truth','effect_tail','dry_irony')]
    selected += [r for r in decisions.GATE if r[0] in ('sarcasm_setting','talking_head_emotion')]
    sys.modules['revision']=types.SimpleNamespace(GATE=selected+FRESH,SYSTEM=SYSTEM)
    runtime_gate.OUT=OUT
    runtime_gate.save('protocol.json',dict(kind='instruction-scope diagnostic',fresh_questions=4,regressions=5,
        reasoning_budget=512,application_changed=False,expected_answers_sent=False))
    runtime_gate.main(reasoning_budget=512)
if __name__=='__main__':main()
