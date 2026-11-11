"""Capture the real file-selection request using saved approved bike-score assets.

This replays source selection only. It does not claim fresh video analysis or a
rendered mix. No model call, application mutation or external request occurs here.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
def main():
    from hinglish_sound.director import pick
    import soundfile as sf
    src=ROOT/'output/sound/20261024-chatgpt-bike-foley-take2/001-bike-foley'
    plan=json.loads((src/'sound-plan.json').read_text(encoding='utf-8'))
    cues=plan['cues'][:3]
    candidates=[]
    for c in cues:
        p=Path(c['path']);info=sf.info(str(p))
        candidates.append(dict(doc=f"{c['sound']}. Available prepared recording: {info.duration:.3f} seconds. Source role: {c['role']}.",path=str(p)))
    # A different ordering per moment detects copying the moment number into choice.
    orders=[[2,0,1],[1,2,0],[0,1,2]]
    moments=[dict(line_text=c['reason'],word='',type=c['category'],intent=c['sound'],
                  emotion='motorcycle travel',duration=c['length'],duration_reason='Saved reviewed shot bounds, not a new source analysis.',
                  role=c['role'],group_id=c['group_id']) for c in cues]
    evidence={}
    class Captured(Exception):pass
    class CaptureBrain:
        def ask(self,system,data,schema,**kwargs):
            from hinglish_niche.profiles import inject
            from hinglish_sound.reference_memory import inject as reference
            system,data=inject(system,data,root=ROOT)
            system=reference(system,data,ROOT,feature='sound')
            evidence.update(system=system,data=data,schema=schema,call_options=kwargs)
            raise Captured()
    try:pick(CaptureBrain(),plan['story'],plan['palette'],moments,[[candidates[j] for j in order] for order in orders],[],[])
    except Captured:pass
    evidence.update(kind='Saved project file-selection replay',source_plan=str(src/'sound-plan.json'),
        expected_choices=[order.index(i) for i,order in enumerate(orders)],candidates=candidates,
        fresh_video_analysis=False,rendered=False,full_creator_context_preserved=True)
    out=ROOT/'output/sound-training/20261030-remediation/production-probe.json'
    out.write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(captured=bool(evidence.get('schema')),candidates=len(candidates),prompt_characters=len(evidence['system'])+len(json.dumps(evidence['data'])))))
if __name__=='__main__':main()
