"""Evidence-first decision diagnostic; no expected answers enter requests."""
from pathlib import Path
import sys,types,shutil
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import runtime_gate,decisions,revision
from diagnose_instruction_scope import FRESH
ROOT=HERE.parents[1]
OUT=ROOT/'output/sound-training/20261030-revision3/evidence-first'
SYSTEM=('Answer the actual question, not an imagined instruction to create audio. '
 'Fill evidence first: summarize only supplied scene facts and explicitly identify missing audio/timing. '
 'For intent, classify whether the question asks to verify evidence, choose a design, or retrieve an asset. '
 'Only then give a decision. A factual question may need no sound design. '
 'Physical scene sound requires a described sound-producing source/action or established environment. '
 'Being indoors alone does not justify footsteps, appliances, voices or music. Emotion and metaphor do not establish physical activity. '
 'When no source action is described, preserve the original room/audio; do not invent replacement ambience. '
 'An optional tonal/comic accent is an editorial proposal, not real environmental activity; say so when proposing one. '
 'Retain useful natural sound decay beyond visual settling; use relative anchors when clock times are absent. '
 'Protect speech and approved source music. Gain values need actual source measurements. '
 'For retrieval verify access, license, local decoding and relevance; never claim unperformed actions. '
 'Return the required JSON with concise evidence and decisions, not a long rationale.')
def main():
    OUT.mkdir(exist_ok=True);shutil.copy2(OUT.parent/'adapter.gguf',OUT/'adapter.gguf')
    selected=[r for r in revision.GATE if r[0] in ('headphone_truth','effect_tail','dry_irony')]
    selected += [r for r in decisions.GATE if r[0] in ('sarcasm_setting','talking_head_emotion')]
    sys.modules['revision']=types.SimpleNamespace(GATE=selected+FRESH,SYSTEM=SYSTEM)
    runtime_gate.OUT=OUT
    runtime_gate.FIELDS=('evidence','intent','decision','timing','mix','uncertainty')
    runtime_gate.SCHEMA=dict(type='object',properties={k:dict(type='string') for k in runtime_gate.FIELDS},
        required=list(runtime_gate.FIELDS),additionalProperties=False)
    runtime_gate.save('protocol.json',dict(kind='evidence-first development diagnosis',heldout_claim=False,
        expected_answers_sent=False,application_changed=False,reasoning_budget=256))
    runtime_gate.main(reasoning_budget=256)
if __name__=='__main__':main()
