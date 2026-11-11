"""One serialized embedding/index job and one local-student adaptation probe.

This builds reference memory, not trained weights. Never silently labels a
teacher artifact or a retrieved example as student-created video.
"""
import json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];KEY='3414a67043b6a4ae102a96bb';PACK=ROOT/'library/motion-teacher'/KEY

def run():
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.ollama_embeddings import OllamaEmbeddings
    from hinglish_motion.teacher_memory import TeacherIndex
    from hinglish_visuals.brain import open_brain
    from hinglish_motion.reference_composer import ask,obj,string,arr,number
    from hinglish_motion.reference_slots import enum
    chunks=json.loads((PACK/'chunks.json').read_text('utf-8'));models=json.loads((ROOT/'config.models.local.json').read_text('utf-8'))
    print('Waiting for the shared GPU queue for one teacher-memory indexing and student probe.',flush=True)
    with gpu_lock(ROOT):
        print('Indexing the saved teacher construction records; no weight training.',flush=True)
        encoder=OllamaEmbeddings(ROOT,models['embedding_model']);index=TeacherIndex(PACK/'vectors.sqlite')
        try:
            vectors=encoder.encode([r['text'] for r in chunks],progress=lambda m:print(m,flush=True))
            index.put(KEY,chunks,vectors)
            query='Ideas editorial typography recipe, exact camera keyframes, complete row character reveal and independent photo parallax. Adapt a new short script without losing motion.'
            q=encoder.encode([query],query=True)[0];retrieved=index.search(q,pack=KEY,limit=4,allow_draft=True)
        finally:encoder.close();index.close()
        context={'kind':'retrieved teacher examples; weights unchanged','approval':'draft, not owner-approved','pack':KEY,'embedding_model':models['embedding_model'],'chunks':retrieved}
        context_file=PACK/'retrieved-context.json';context_file.write_text(json.dumps(context,ensure_ascii=False,indent=2),'utf-8')
        (ROOT/'config.motion-teacher.local.json').write_text(json.dumps({'enabled':True,'selected':KEY,'scope':'Motion Graphics only; draft reference guidance, model weights unchanged'},indent=2),'utf-8')
        os.environ['STORYLENS_REFERENCE_FEATURE']='motion';os.environ['STORYLENS_MOTION_TEACHER_CONTEXT']=str(context_file)
        brain=open_brain(ROOT,'auto',progress=lambda m:print(m,flush=True))
        brain.cache_enabled=False
        plan=json.loads((PACK/'teacher-plan.json').read_text('utf-8'));scene=plan['scenes'][0]
        script='Small ideas can create lasting change.'
        keyframe=obj({'time':number(0,2),'scale':number(.5,2),'x':number(-100,100),'y':number(-100,100)})
        schema=obj({'rows':obj({key:string(80) for key in ('ideas','arent','just','created')}),
          'camera_keys':arr(keyframe,2,4),'text_reveal':enum(['character reveal with full reserved row width']),
          'photo_motion':string(250),'weights_changed':enum([False])})
        try:
            answer=ask(brain,PACK,'student-adaptation-probe',
              'Adapt this teacher motion recipe to the exact new script. Return only the requested JSON. '
              'The reading order is ideas row, arent row, just tag, created row. Split the new words across these four slots in that order; empty slots allowed. '
              'Preserve every script word exactly once, including punctuation. Copy the teacher camera key times/scale/x/y exactly; do not replace them with a static preset. '
              'Retain fixed complete-row character slots and independent photo motion. Describe the existing photo drift. This is a retrieval/few-shot probe, not weight training or a rendered video.',
              {'new_script':script,'teacher_scene':scene,'retrieval_ids':[r['id'] for r in retrieved]},schema,1000)
        finally:brain.close()
        words=' '.join(answer['rows'][key] for key in ('ideas','arent','just','created')).split()
        expected=[{k:v for k,v in key.items() if k in ('time','scale','x','y')} for key in scene['camera']]
        checks={'words_preserved':words==script.split(),'camera_keys_preserved':answer['camera_keys']==expected,'reference_memory_injected':True,'weights_changed':False,'video_rendered':False}
        (PACK/'student-probe-checks.json').write_text(json.dumps({'model':models['planning_model'],'script':script,'checks':checks,'retrieved_ids':[r['id'] for r in retrieved]},indent=2),'utf-8')
        print(json.dumps(checks),flush=True)
    print('Teacher memory and one local student response saved. No trained checkpoint created.',flush=True)

if __name__=='__main__':run()
