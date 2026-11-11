"""Use the established isolated runtime for eight fresh and eight regression cases.

Expected answers/rubrics are saved for review, never sent to either model.
"""
from pathlib import Path
import sys,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import decisions,revision,runtime_gate

def main():
    cases=list(decisions.GATE)+list(revision.GATE)
    decisions.GATE=cases
    sys.modules['revision']=decisions
    runtime_gate.OUT=HERE.parents[1]/'output/sound-training/20261030-revision3'
    runtime_gate.save('evaluation-protocol.json',dict(
        fresh_questions=8,regression_questions=8,
        same_prompt_schema_and_sampling_for_base_and_adapter=True,
        expected_answers_sent_to_model=False,cache_disabled=True,
        reasoning_budget_tokens=256,reasoning_mode='Bounded diagnostic; live application remains unchanged',
        semantic_acceptance='Review all answers for the recorded rubric; schema validity alone is insufficient.',
        live_application_test=False,auto_deploy=False))
    runtime_gate.main(reasoning_budget=256)

if __name__=='__main__':main()
