"""Actual local-Qwen scene authoring from saved teacher knowledge.

Only supplied words/asset identities and the reference clock are bound by code.
Every layout/camera/reveal/drift parameter must come from a saved model response.
Missing or invalid choices stop or return to Qwen; never fall back to the teacher.
"""
import copy,hashlib,json,math,re,shutil,os
from datetime import datetime
from pathlib import Path
import uuid

from .reference_composer import obj,arr,number,string,ask,save
from .reference_slots import enum


def schema_for(reference):
    D=reference['end']-reference['start']
    fresh=reference.get('local_reference_version')
    pose=obj({'scale':number(.8,1.8),'x':number(-720,720) if fresh else number(-250,250),'y':number(-1280,1280) if fresh else number(-250,250),'rotation':number(-180,180) if fresh else number(-6,6)})
    camera=obj({'from':pose,'via':pose,'to':pose,'middle_phase':number(.15,.75)})
    layers={}
    for layer in reference['layers']:
        props={'x':number(-360,1000),'y':number(-300,1300),'w':number(8,1200),
          'opacity':number(0,1),'rotation':number(-30,30),'drift':arr(number(-720,720) if reference.get('local_reference_version') else number(-80,80),3,3)}
        if layer['kind']=='text':
            props.update(size=number(14,200),color=string(7),weight=enum([layer.get('weight',700)]),
              delay=number(0,max(0,D-.4)),reveal=enum(['characters','soft']),stagger=number(0,.09))
        else:props['h']=number(8,1600)
        if layer['kind']=='shape':props['color']=string(7)
        for name in ('radius',):
            if name in layer:props[name]=number(0,800)
        if layer.get('orbit_capable'):
            props['orbit']=obj({'center_x':number(0,720),'center_y':number(0,1280),'rotation_delta':number(-360,360)})
        layers[layer['id']]=obj(props)
    world=obj({'camera_z_from':enum([7.,8.,9.,10.,11.,12.]),'camera_z_to':enum([7.,8.,9.,10.,11.,12.]),
      'camera_x_from':enum([-.3,-.1,0.,.1,.3]),'camera_x_to':enum([-.3,-.1,0.,.1,.3]),
      'plate_scale_from':enum([1.,1.05,1.1,1.2]),'plate_scale_to':enum([1.,1.05,1.1,1.2]),
      'debris_speed':enum([.3,.5,.7,1.,1.3]),'pose_scale':enum([.9,1.,1.1])}) if reference.get('mode3d') else obj({})
    fields={'background':string(7),'camera':camera,'entrance':enum(['none','right','up']),
      'exit':enum(['none','left','up']),'layers':obj(layers),'world':world}
    if 'background_style' in reference:fields.update(background_style=enum(['solid','radial']),background_edge=string(7),grid={'type':'boolean'})
    return obj(fields)


def compile_scene(reference,answer):
    import jsonschema
    errors=list(jsonschema.Draft202012Validator(schema_for(reference)).iter_errors(answer))
    if errors:raise ValueError('Local Qwen scene invalid: '+'; '.join('.'.join(map(str,e.absolute_path))+': '+e.message for e in errors[:16]))
    def finite(v):
        if isinstance(v,dict):return all(finite(x) for x in v.values())
        if isinstance(v,list):return all(finite(x) for x in v)
        return not isinstance(v,float) or math.isfinite(v)
    if not finite(answer):raise ValueError('Local Qwen scene invalid: coordinates must be finite.')
    D=reference['end']-reference['start'];cam=answer['camera']
    keys=[{'time':0.,**cam['from']},{'time':D*cam['middle_phase'],**cam['via']},{'time':D,**cam['to']}]
    def color(value):
        if re.fullmatch(r'#[0-9a-fA-F]{3}',value):return '#'+''.join(c*2 for c in value[1:])
        return value
    hexcolor=lambda c:bool(re.fullmatch(r'#[0-9a-fA-F]{6}',c))
    background=color(answer['background'])
    if not hexcolor(background):raise ValueError('Local Qwen scene invalid: use a hex background colour.')
    layers=[]
    for original in reference['layers']:
        choice=copy.deepcopy(answer['layers'][original['id']])
        if 'color' in choice:choice['color']=color(choice['color'])
        if 'color' in choice and not hexcolor(choice['color']):raise ValueError('Local Qwen scene invalid: use #RRGGBB layer colours.')
        # Semantic source bindings are content, not numeric design fallbacks.
        binding={k:original[k] for k in ('id','kind','text','asset','font','align','label','outline','underline','border') if k in original}
        if reference.get('enforce_reveal_deadlines') and original['kind']=='text':
            finish=choice['delay']+.20
            if choice['reveal']=='characters':finish=choice['delay']+.16+max(0,len(original['text'])-1)*choice['stagger']
            if finish>D-.10:
                safe=max(0,(D-.26-choice['delay'])/max(1,len(original['text'])-1))
                raise ValueError(f'Local Qwen scene invalid: {original["id"]} reveal ends at {finish:.3f}s after the {D:.3f}s shot. Reduce delay or choose stagger <= {safe:.4f}; do not drop words.')
        layers.append({**binding,**choice})
    moving=any(abs(keys[-1][k]-keys[0][k])>(.015 if k=='scale' else 2) for k in ('scale','x','y'))
    moving=moving or any(any(abs(x)>2 for x in layer['drift']) for layer in layers)
    if not moving and not reference.get('mode3d'):raise ValueError('Local Qwen scene invalid: include continuous camera or independent layer travel, not only a static poster.')
    result={'id':reference['id'],'start':reference['start'],'end':reference['end'],
      'mode3d':reference.get('mode3d'),'background':background,'camera':copy.deepcopy(keys),
      'entrance':answer['entrance'],'exit':answer['exit'],'world':copy.deepcopy(answer['world']),
      'layers':layers,'authored_parameters':'local_model','content_binding':'exact supplied reference words/assets'}
    if 'background_style' in reference:
        result.update(background_style=answer['background_style'],background_edge=color(answer['background_edge']),grid=answer['grid'])
        if not hexcolor(result['background_edge']):raise ValueError('Local Qwen scene invalid: use a hex gradient edge colour.')
    return result


def knowledge_package(root,source,brief):
    match=re.search(r'^Student knowledge:\s*([^\r\n]+)$',brief,re.M|re.I)
    if not match:return None
    root=Path(root).resolve();folder=Path(match[1].strip().strip('"')).resolve()
    if not folder.is_relative_to(root/'library/motion-teacher'):raise ValueError('Local student knowledge unavailable: choose a saved Motion Graphics lesson.')
    plan=json.loads((folder/'teacher-plan.json').read_text('utf-8'))
    if plan['source_sha256']!=hashlib.sha256(Path(source).read_bytes()).hexdigest():raise ValueError('Local student knowledge unavailable: this lesson belongs to another reference.')
    return folder


def recover_reply(recipe,receipts,model):
    for receipt in reversed(receipts):
        if receipt.get('model')!=model or receipt.get('request',{}).get('reference_recipe')!=recipe:continue
        try:return compile_scene(recipe,receipt['answer'])
        except (ValueError,KeyError):continue
    return None


def author_scene(brain,folder,recipe,index):
    schema=schema_for(recipe);errors=[]
    # Ollama's grammar does not teach the model numeric min/max constraints.
    # State shared ranges once in the actual prompt, without duplicating the
    # potentially large per-layer JSON schema or dropping creator guidance.
    fields={}
    for layer in schema['properties']['layers']['properties'].values():
        fields.update({k:v for k,v in layer['properties'].items() if v.get('type') in ('number','array','object')})
    contract={'camera_pose':schema['properties']['camera']['properties']['from']['properties'],
      'middle_phase':schema['properties']['camera']['properties']['middle_phase'],'layer_fields':fields}
    attempts=[re.search(r'-attempt-(\d+)(?:-error)?$',p.stem) for p in folder.glob(f'qwen-scene-{index:02d}-attempt-*.json')]
    attempt_base=max([int(m[1]) for m in attempts if m],default=0)
    for attempt in range(4 if recipe.get('local_reference_version') else 2):
        try:
            answer=ask(brain,folder,f'qwen-scene-{index:02d}-attempt-{attempt_base+attempt+1}',
          'You are the sole LOCAL author of this Motion Graphics reconstruction. Use the saved teacher example as reference knowledge. '
          'Produce all numeric layout, typography, reveal, parallax and camera settings for ONE scene. No hand-authored fallback will replace your choices. '
          'The supplied reference words and photo/shape identities are fixed content. Match the reference hierarchy and relative arrangement, compact readable spacing, intentional motion and transitions. '
          'Canvas is 720x1280. x/y are TOP-LEFT pixels, w/h are pixel dimensions, size is font pixels, drift is [X,Y,Z] pixels across the shot. '
          'Foreground text must be readable and inside the frame during its resting phase. Photo cutouts may bleed out of frame. Different layers need independent movement. '
          'Camera from/via/to are start/middle/end poses; middle_phase is a fraction .15 to .75 of the shot. The renderer binds these to the known source clock. scale is a multiplier, x/y are pixels, rotation is degrees. '
          'Do not flatten all scenes into a generic stack or use identical static camera endpoints. '
          'world parameters control real Three.js camera Z/X, still-plate scale, debris expansion and pose-plane scale. Use subtle parallax rather than uncontrolled spinning. '
          'Only return the schema JSON; no HTML/JS, commands, external URLs or invented words.',
          {'task':'Reconstruct this scene using the teacher lesson; YOU choose every requested creative parameter.',
           'scene_duration':round(recipe['end']-recipe['start'],3),'reference_recipe':recipe,
           'instructions':'Return from/via/to camera poses and middle_phase .15 to .75. Preserve meaningful reference hierarchy and continuous parallax. Use supplied role font weights. World camera Z is 7 to 12 scene units, never CSS distance 1000. No world values are needed when its schema is empty. Return hex colours. Every requested numeric design choice is yours.',
           'coordinate_rules':'x/y top-left pixels; drift X/Y/Z pixels; text size pixels; camera poses bound to source clock by middle_phase',
           'motion_observations':recipe.get('motion_reading',''),
           'reveal_rules':'Every word must finish revealing by shot end minus 0.10s. The character duration is .16s plus stagger*(character_count-1); choose zero stagger if a long small footer needs an immediate reveal. Never remove words.',
           'required_numeric_contract':contract,'corrections':errors},schema,2000,think=bool(attempt and recipe.get('local_reference_version')))
            scene=compile_scene(recipe,answer);return scene
        except ValueError as error:
            errors=[str(error)]
            save(folder/f'qwen-scene-{index:02d}-attempt-{attempt_base+attempt+1}-error.json',{'model':brain.name,'error':str(error),'reference_id':recipe['id'],'manual_fallback':False})
    else:raise ValueError('Local Qwen could not create a valid scene after its correction: '+str(errors))


def run(root,source,pack,brief,progress=print):
    root,source,pack=Path(root).resolve(),Path(source).resolve(),Path(pack).resolve()
    reference=json.loads((pack/'teacher-plan.json').read_text('utf-8'));manifest=json.loads((pack/'manifest.json').read_text('utf-8'))
    asset_source=Path(manifest['asset_folder']).resolve()
    if not asset_source.is_relative_to(root/'output/motion') or not asset_source.is_dir():raise ValueError('Local student assets unavailable: restore the saved lesson image folder.')
    resume=re.search(r'^Continue student:\s*([^\r\n]+)$',brief,re.M|re.I)
    folder=Path(resume[1].strip()).resolve() if resume else root/'output/motion'/('qwen-student-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:6])
    if not folder.is_relative_to(root/'output/motion'):raise ValueError('Local student resume unavailable: choose its saved output folder.')
    folder.mkdir(parents=True,exist_ok=True)
    shutil.copytree(asset_source,folder/'assets',dirs_exist_ok=True)
    save(folder/'lesson-receipt.json',{'pack':str(pack),'source_sha256':reference['source_sha256'],
      'teacher_plan_sha256':hashlib.sha256((pack/'teacher-plan.json').read_bytes()).hexdigest(),
      'knowledge':str(pack/'retrieved-context.json'),'weight_training':False,
      'content':'supplied reference words/assets; new local-model layout/camera/reveal/drift decisions'})
    os.environ['STORYLENS_REFERENCE_FEATURE']='motion';os.environ['STORYLENS_MOTION_TEACHER_CONTEXT']=str(pack/'retrieved-context.json')
    from hinglish_visuals.brain import open_brain
    brain=open_brain(root,'auto',progress=progress);brain.cache_enabled=False
    completed=[];checkpoint=folder/'student-checkpoint.json'
    if resume and checkpoint.exists():
        prior=json.loads(checkpoint.read_text('utf-8'))
        if prior['source_sha256']!=reference['source_sha256']:raise ValueError('Local student resume unavailable: source reference changed.')
        completed=prior['scenes']
    try:
        for i,recipe in enumerate(reference['scenes']):
            if i<len(completed):continue
            if resume:
                files=sorted((p for p in folder.glob(f'qwen-scene-{i+1:02d}-attempt-*.json') if p.stem.rsplit('-',1)[1].isdigit()),key=lambda p:int(p.stem.rsplit('-',1)[1]))
                recovered=recover_reply(recipe,[json.loads(p.read_text('utf-8')) for p in files],brain.name)
                if recovered:
                    progress(f'Continuing Qwen saved response for scene {i+1}/{len(reference["scenes"])}; no new inference')
                    completed.append(recovered);save(checkpoint,{'source_sha256':reference['source_sha256'],'model':brain.name,'scenes':completed});continue
            progress(f'Local Qwen authoring scene {i+1}/{len(reference["scenes"])}: {recipe["id"]}')
            scene=author_scene(brain,folder,recipe,i+1)
            completed.append(scene);save(checkpoint,{'source_sha256':reference['source_sha256'],'model':brain.name,'scenes':completed})
        model=brain.name
    finally:brain.close()
    plan={k:reference[k] for k in ('width','height','duration','source','source_sha256','uses_reference_photo_crops','uses_reference_audio')}
    plan.update(version=1,authoring_role='local_student',author=model,weight_training=False,approval='owner-review-pending',scenes=completed)
    file=folder/'student-plan.json';save(file,plan)
    save(folder/'authorship.json',{'author':model,'teacher_used_as':'reference knowledge and existing renderer/assets; not the final numeric composition',
      'creative_choices_from':'qwen-scene-*-attempt-*.json raw model answers','manual_design_edits':False,
      'supplied_content':'reference wording, photos/poses and source audio','weight_training':False,'scene_count':len(completed)})
    from .teacher_demo import run as render
    return render(root,source,file,progress,student={'model':model,'raw_model_receipts':str(folder),'manual_design_edits':False})
