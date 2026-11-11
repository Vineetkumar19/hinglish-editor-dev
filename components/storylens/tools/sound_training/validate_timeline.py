"""Bounded fresh timeline transfer checks plus prior evidence/duration regressions."""
from pathlib import Path
import sys,types,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]))
import runtime_gate,remediation
from tools.sound_training import timeline_curriculum
import validate_remediation

def main():
    fresh=timeline_curriculum.GATE
    sys.modules['revision']=types.SimpleNamespace(GATE=fresh+remediation.GATE,SYSTEM=remediation.SYSTEM)
    out=HERE.parents[1]/'output/sound-training/20261030-tutorial-timeline'
    runtime_gate.OUT=out;runtime_gate.FIELDS=('evidence','decision','timing','mix','uncertainty')
    runtime_gate.SCHEMA=dict(type='object',properties={k:dict(type='string') for k in runtime_gate.FIELDS},required=list(runtime_gate.FIELDS),additionalProperties=False)
    runtime_gate.save('evaluation-protocol.json',dict(fresh_questions=6,previously_evaluated_regressions=8,
        trained_regressions_not_counted_as_unseen=True,expected_answers_sent=False,reasoning_budget=256,
        auto_deploy=False,production_probe='Actual saved source files and production file-choice schema; not a render'))
    runtime_gate.main(reasoning_budget=256,compare_case_ids={r[0] for r in fresh},
                      after_cases=validate_remediation.production_probe,context_tokens=12288)

if __name__=='__main__':main()
