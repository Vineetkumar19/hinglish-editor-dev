"""Acceptance checks for the final small duration correction; no automatic activation."""
from pathlib import Path
import sys,types,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]))
import runtime_gate,remediation,validate_remediation
from tools.sound_training import timeline_curriculum

def main():
    out=HERE.parents[1]/'output/sound-training/20261030-timeline-tail-correction'
    fresh=json.loads((out/'gate.json').read_text())
    duration_rule=json.loads((out/'shared-duration-rule.json').read_text())['rule']
    old=[r for r in timeline_curriculum.GATE if r[0] in {'ferry_bridge','offset_transfer','raincoat_foley','caption_change','stack_masking'}]
    sys.modules['revision']=types.SimpleNamespace(GATE=fresh+old+remediation.GATE,SYSTEM=remediation.SYSTEM+' '+duration_rule)
    runtime_gate.OUT=out;runtime_gate.FIELDS=('evidence','decision','timing','mix','uncertainty')
    runtime_gate.SCHEMA=dict(type='object',properties={k:dict(type='string') for k in runtime_gate.FIELDS},required=list(runtime_gate.FIELDS),additionalProperties=False)
    runtime_gate.save('evaluation-protocol.json',dict(fresh_questions=4,previously_evaluated_regressions=13,
        raincoat_question_explicitly_trained=True,expected_answers_sent=False,reasoning_budget=256,
        shared_duration_rule_included=True,comparison='Candidate acceptance only; no claim of superiority to base',auto_deploy=False))
    runtime_gate.main(reasoning_budget=256,compare_case_ids=set(),after_cases=validate_remediation.production_probe,context_tokens=12288)

if __name__=='__main__':main()
