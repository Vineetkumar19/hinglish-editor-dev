"""Read-only audit: the rendered student plan must equal the local model receipts."""
import argparse,json
from pathlib import Path


def audit(folder,pack):
    from hinglish_motion.student_demo import compile_scene
    folder,pack=Path(folder),Path(pack)
    reference=json.loads((pack/'teacher-plan.json').read_text('utf-8'))
    plan=json.loads((folder/'student-plan.json').read_text('utf-8'))
    rows=[];differences=0
    for i,(recipe,scene) in enumerate(zip(reference['scenes'],plan['scenes'])):
        files=sorted((p for p in folder.glob(f'qwen-scene-{i+1:02d}-attempt-*.json') if p.stem.rsplit('-',1)[1].isdigit()),key=lambda p:int(p.stem.rsplit('-',1)[1]))
        if not files:raise ValueError('Missing local-model authorship receipt for '+recipe['id'])
        receipt=json.loads(files[-1].read_text('utf-8'));compiled=compile_scene(recipe,receipt['answer'])
        match=compiled==scene
        changed=0
        for original,actual in zip(recipe['layers'],scene['layers']):
            for key in ('x','y','w','h','size','rotation','opacity','delay','drift'):
                if key in original and key in actual and original[key]!=actual[key]:changed+=1
        differences+=changed
        rows.append({'scene':recipe['id'],'receipt':files[-1].name,'model':receipt['model'],'exact_compiled_match':match,'changed_layer_parameters':changed,'usage':receipt.get('usage')})
    success=len(rows)==len(reference['scenes'])==len(plan['scenes']) and all(r['exact_compiled_match'] for r in rows)
    result={'all_rendered_scenes_match_local_model_receipts':success,'scenes':rows,'changed_layer_parameters_from_teacher':differences,
      'manual_creative_edits_detected':not success,'known_mechanical_bindings':['reference wording/assets and source scene clock','named camera stage timing','equivalent CSS hex expansion','renderer full-row font fitting'],
      'weights_updated':False,'independent_new_asset_generation':False}
    (folder/'authorship-audit.json').write_text(json.dumps(result,indent=2),'utf-8')
    if not success:raise ValueError('Student scene plan does not match its local-model receipts; do not claim model-only composition.')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('pack');args=p.parse_args()
    r=audit(args.folder,args.pack);print(json.dumps({k:v for k,v in r.items() if k!='scenes'}))
