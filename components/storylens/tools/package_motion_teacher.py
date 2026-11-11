"""Export observable construction notes and candidate student supervision."""
import json,hashlib,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/motion/teacher-world-culture-20261024'

def package():
    plan=json.loads((OUT/'teacher-plan.json').read_text('utf-8'));key=plan['source_sha256'][:24];folder=ROOT/'library/motion-teacher'/key;folder.mkdir(parents=True,exist_ok=True)
    chunks=[];pairs=[];notes=[
      'STORYLENS MOTION TEACHER — observable construction record, 24 October 2026',
      'Owner authorized ChatGPT/Codex to create the teacher first, then provide documented examples to the smaller Ollama models. This is expressly teacher-authored, not local-student output.',
      'Approval: DRAFT, awaiting owner visual review. No model weights updated. Reference-derived photo crops, isolated source walking poses and supplied reference audio are reused for this comparison. The 3D camera/debris and editable text are newly constructed. Original meshes, lights and camera cannot be recovered uniquely from this baked 2D video.',
      'Previous pipeline: Qwen3 14.8B Q4_K_M planning; Qwen3.5 9B Q6_K Vision; Qwen3 Embedding 7.6B Q6_K for vector search. Hyperframes 0.8.188 renders HTML/CSS with GSAP 3.15.0. Three.js r128 handles the teacher space/pose planes and 3D debris. FFmpeg mixes audio. The earlier model adapter restricted camera choice to five presets; this teacher preserves arbitrary explicit camera keys instead.',
      'MEASUREMENTS: source-frame-metrics.csv contains all 461 decoded source-frame observations at 30fps. Optical flow is a 2D proxy with cut/occlusion error, not ground-truth 3D camera recovery. teacher-matrices.json records the teacher actual CSS layer matrices, screen rectangles, projection/view matrices and object transforms when available.',
      'UNITS: authoring canvas 720x1280; preview 360x640. Positions, font sizes, offsets and CSS Z values are design pixels. Scene times and key times are seconds; camera keys are local to the scene. Three.js uses separate scene units: 42-degree FOV, 9:16 aspect, near .1, far 100; camera near (0,0,9). Texture plates are 4.25x7.56 world units; pose plane 3.98x7.08 at Z .15.',
      'TEXT: reserve the complete row before revealing letters. Actual loaded font is Inter regular/bold; script accent uses Segoe Script. Measure full DOM row once and fit before reveal. Never center only the revealed prefix. Character reveal uses opacity 0->1, Y 16->0px, scale 1.12->1, blur 4->0px, .16s per-character duration plus saved stagger. Body line breaks use actual BR elements.',
      'TRANSITIONS: horizontal entrance X 760->0px with blur 16->0px in .22s power3.out; exit X 0->-850px with blur 0->20px in .18s power3.in. Vertical equivalents use Y 1250->0 and 0->-1280. Each scene has its own camera key sequence, not one repeated global push.',
      'PARALLAX: each photo/card has an independent drift track and CSS Z offset inside a perspective-1200px scene. The shared camera moves the whole composition; foreground and rear echo drift independently. This is 2.5D photo motion, not generated mesh geometry.',
      'SPACE: reference-derived still plates are projected into the Three.js scene. Perspective camera X changes smoothly as sin(time*.22)*.15. Plate scale changes continuously from each shot onset; no modulo-time resets. Fifty-five independently rotating tetrahedral fragments are actual 3D objects. Their radius expands with elapsed planet-shot time. Source actor poses retain original gait and are transparent image textures on a 3D plane, not a generated humanoid rig.',
      'SOUND: the comparison intentionally reuses supplied reference audio on its original clock. This is not newly authored sound-bank composition. Teacher cut times and source audio stay aligned. New effects/music for another script need a separate timing plan.',
      'LEARNING: structured teacher plans, construction notes, code hashes, visual examples and rejected static-poster counterexamples are candidate supervision. Embeddings plus vector retrieval are reference memory (RAG), not weight training. Real SFT/distillation requires a compatible trainable base and training runtime, and held-out evaluation. Local installed models are GGUF inference files; TRL/PEFT/bitsandbytes/Unsloth are absent in the current application runtime. Do not relabel a Modelfile system prompt as trained weights.',
      'FUTURE ADAPTATION: keep shot identity, support/main hierarchy, masks, depth ordering, transition family and normalized timing. Change exact user words and subject assets independently. Measure new complete text rows. Never let new words recenter existing words. Choose footage/3D assets appropriate to the new script. This one teacher is insufficient evidence for broad generalization.',
    ]
    topics=[('tools',notes[3]),('measurement',notes[4]),('units',notes[5]),('typography',notes[6]),('transitions',notes[7]),('parallax',notes[8]),('three-d',notes[9]),('sound',notes[10]),('training-boundary',notes[11]),('adaptation',notes[12])]
    for id,text in topics:chunks.append({'id':id,'text':text,'status':'draft'})
    for scene in plan['scenes']:
        summary=json.dumps(scene,ensure_ascii=False,separators=(',',':'))
        notes.extend(['',f'SCENE {scene["id"]}: {scene["start"]:.3f}–{scene["end"]:.3f}s',json.dumps(scene,ensure_ascii=False,indent=2)])
        chunks.append({'id':'scene-'+scene['id'],'text':f'Worked motion example {scene["id"]}, {scene["start"]}–{scene["end"]} seconds. Explicit camera keys and independently placed layers: '+summary,'status':'draft'})
        pairs.append({'messages':[{'role':'system','content':'You author exact, inspectable Storylens motion timelines. Preserve explicit tracks, layer hierarchy, exact words and fixed full-row layout. This is candidate teacher data, not proof of approved style.'},{'role':'user','content':f'Reconstruct the {scene["id"]} editorial/cinematic recipe from its reviewed construction notes. Return its declarative scene, including timings, layer positions, movement and reveal settings.'},{'role':'assistant','content':summary}],'approval':'draft','source_sha256':plan['source_sha256']})
    (OUT/'teacher-notes.txt').write_text('\n\n'.join(notes),'utf-8');shutil.copyfile(OUT/'teacher-notes.txt',folder/'teacher-notes.txt');shutil.copyfile(OUT/'teacher-plan.json',folder/'teacher-plan.json')
    (folder/'chunks.json').write_text(json.dumps(chunks,ensure_ascii=False,indent=2),'utf-8')
    (folder/'candidate-planning-sft.jsonl').write_text('\n'.join(json.dumps(p,ensure_ascii=False) for p in pairs)+'\n','utf-8')
    rejected=ROOT/'output/motion/native-text-20261024-165617-a3db94/reference-motion-project.json'
    (folder/'rejected-example.json').write_text(json.dumps({'status':'owner-rejected','project':str(rejected),'reason':'Owner rejected weak, generic motion and text animation; do not use this as a positive target.','replacement_teacher_approval':'draft'},indent=2),'utf-8')
    code={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'hinglish_motion/web/teacher-world.js',ROOT/'hinglish_motion/web/teacher-world.html',ROOT/'tools/build_motion_teacher_world.py']}
    manifest={'id':key,'source_sha256':plan['source_sha256'],'approval':'draft','teacher':'Codex, authorized by latest owner instruction','weight_training':False,'candidate_planning_examples':len(pairs),'knowledge_chunks':len(chunks),'reference_photo_and_audio_reuse':True,'code_sha256':code,'training_blockers':['Owner quality review still pending','No compatible trainable base weights installed here; currently GGUF inference files','TRL/PEFT training runtime not installed','More diverse accepted examples and held-out evaluation are required before claiming generalization']}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8');(OUT/'teacher-package.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    print(folder)
    return folder

if __name__=='__main__':package()
