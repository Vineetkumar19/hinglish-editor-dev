"""Summarize observed training results without claiming platform delivery."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/publishing-training/20261030-v13'
def main():
 status=json.loads((OUT/'native-review-status.json').read_text())
 if status['complete']!=status['total']:raise RuntimeError('Evaluation still running')
 results=json.loads((OUT/'native-review.json').read_text())
 train=json.loads((OUT/'status.json').read_text())
 curriculum=json.loads((OUT/'curriculum.json').read_text())
 splits=status['splits']
 def count(s):return f"{splits[s]['passed']}/{splits[s]['total']}"
 report=dict(run=OUT.name,training_completed=True,optimizer_steps=train['optimizer_steps'],epochs=train['epochs'],elapsed_training_seconds=train['elapsed_seconds'],weight_delta=train['max_weight_delta'],native_evaluation=status,failures=[r['id'] for r in results if not r['passed']],native_checked_cases_passed=status['passed']==status['total'],candidate_activated=False,new_uploads=0,new_schedules=0,new_publications=0,live_platform_validation=False,universal_correctness_claim=False,packaging_blocker='Existing evaluation GGUF differs from training base in all eight sampled unquantized normalization tensors. Matching-base export and verification remain necessary.',scheduling_connector_cause='Previous KKR visibility-control timeout could not be reproduced in authorized read-only inspection; Private dialog opened normally and was cancelled without saving.')
 report['pdf_sections']=[
 dict(heading='Actual weight training',body=f"Candidate {OUT.name} continued the isolated 14B QLoRA adapter from {curriculum['parent']}: {train['optimizer_steps']} optimizer steps across {train['epochs']} epochs, with a measured nonzero adapter-weight change. Training used {curriculum['train']} publishing examples. Original models and all older adapters remain saved."),
 dict(heading='Evaluation results',body=f"On the matching native training base, greedy generation without JSON grammar scored {count('holdout')} reserved synthetic checks, {count('acceptance')} regression checks and {count('production-replay')} original recorded requests. Previously inspected failures are regressions, not unseen examples. These scores cover the stated rubrics, not every possible future prompt."),
 dict(heading='What was corrected',body='The examples teach complete subject/theme retention, individual caption words, concise captions, optional long/highlight covers, exact requested clip count, account/mode routing, saved-job reuse, cancellation and bounded scheduling recovery. An uncertain Schedule result with a saved video ID differs from an upload with no saved remote identity.'),
 dict(heading='Deployment mismatch discovered',body='The earlier exported candidate failed while the same adapter answered correctly in its native runtime. All eight sampled unquantized normalization tensors differ between the training base and the old evaluation GGUF. This is incompatible evidence for blindly transferring LoRA weights; it does not prove the full origin of every base tensor. Publishing evaluation now refuses this mismatch.'),
 dict(heading='Model output versus connector execution',body='The existing private KKR video could be inspected and its visibility dialog opened, but the earlier missing-control timeout was not reproduced. Training a correct recovery decision does not itself repair a browser selector, network failure or lost receipt. No successful scheduling retest is claimed.'),
 dict(heading='Owner constraints and remaining work',body='No new upload, schedule or publication was started. This candidate was not activated. A compatible export must be verified before deployment, followed only by a separately authorized real workflow. Existing Sound Design, uploaded videos, cancelled schedules and owner-deleted trial posts remain untouched.')]
 (OUT/'review-verdict.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 (ROOT/'output/publishing-training/final-training-review.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 work=ROOT/'output/publishing-training/active-work.json';d=json.loads(work.read_text())
 d.update(run=OUT.name,phase='native_training_evaluated_export_unverified',review=str((OUT/'review-verdict.json').relative_to(ROOT)),remaining=['Verify a compatible export before any activation','Real publishing validation remains unperformed and no new posting is authorized'])
 d['checklist'][2]['status']=OUT.name+' actual QLoRA training completed'
 d['checklist'][3]['status']=f"native reserved {count('holdout')}, regression {count('acceptance')}, replay {count('production-replay')}; export mismatch blocked"
 work.write_text(json.dumps(d,indent=2),encoding='utf8')
 print(json.dumps({k:report[k] for k in ('native_checked_cases_passed','failures','candidate_activated','new_publications')}))
if __name__=='__main__':main()
