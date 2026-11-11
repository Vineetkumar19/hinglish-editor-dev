"""Fresh-question comparison, explicitly trained regressions and real selection schema."""
from pathlib import Path
import sys,types,json
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import runtime_gate,remediation,revision,decisions
from diagnose_instruction_scope import FRESH
OUT=HERE.parents[1]/'output/sound-training/20261030-remediation'

def production_probe(session,endpoint,identity):
    import jsonschema
    fixture=json.loads((OUT/'production-probe.json').read_text(encoding='utf-8'))
    results={}
    for label,scale in [('base',0.0),('adapter',1.0)]:
        body=runtime_gate.request_body(fixture['system'],json.dumps(fixture['data'],ensure_ascii=False),identity,scale)
        body['response_format']['json_schema']['schema']=fixture['schema'];body['max_tokens']=1024
        response=session.post(endpoint+'/v1/chat/completions',json=body,timeout=180);response.raise_for_status()
        result=response.json();choice=result['choices'][0]
        text=choice['message'].get('content','');error=None;parsed=None
        try:
            parsed=json.loads(text);jsonschema.validate(parsed,fixture['schema'])
        except (ValueError,jsonschema.ValidationError) as exc:error=str(exc)[:500]
        expected=fixture['expected_choices'];selected={}
        if isinstance(parsed,dict):selected={r.get('moment'):r.get('choice') for r in parsed.get('effects',[]) if isinstance(r,dict)}
        results[label]=dict(finish_reason=choice.get('finish_reason'),schema_error=error,parsed=parsed,
            correct_role_choices=error is None and choice.get('finish_reason')=='stop' and all(selected.get(i)==v for i,v in enumerate(expected)),
            usage=result.get('usage'),timings=result.get('timings'))
    runtime_gate.save('production-probe-result.json',dict(kind=fixture['kind'],results=results,
        original_source=str(fixture['source_plan']),rendered=False,application_end_to_end=False))

def main():
    fresh=list(remediation.GATE)
    old=list(revision.GATE)+list(decisions.GATE)+list(FRESH)
    sys.modules['revision']=types.SimpleNamespace(GATE=fresh+old,SYSTEM=remediation.SYSTEM)
    runtime_gate.OUT=OUT;runtime_gate.FIELDS=('evidence','decision','timing','mix','uncertainty')
    runtime_gate.SCHEMA=dict(type='object',properties={k:dict(type='string') for k in runtime_gate.FIELDS},
        required=list(runtime_gate.FIELDS),additionalProperties=False)
    runtime_gate.save('evaluation-protocol.json',dict(fresh_questions=8,trained_regressions=20,
        compare_base_only_on_fresh_questions=True,regressions_are_not_unseen_evidence=True,
        same_request_for_base_and_adapter=True,expected_answers_sent=False,reasoning_budget=256,
        production_probe='Existing file-selection prompt/schema with full creator memory and real saved recordings; no render',
        auto_deploy=False))
    runtime_gate.main(reasoning_budget=256,compare_case_ids={r[0] for r in fresh},after_cases=production_probe,context_tokens=12288)
if __name__=='__main__':main()
