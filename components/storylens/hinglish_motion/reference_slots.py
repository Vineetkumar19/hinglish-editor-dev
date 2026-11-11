"""Required role slots keep an image choice from replacing the model's text."""
import re
from .reference_composer import obj,arr,string,ask,compile_layer,validate_scene,LAYER,number


def enum(values):
    return {'type':'string' if isinstance(values[0],str) else 'boolean' if isinstance(values[0],bool) else 'number','enum':values}


def compile_slots(answer,parts,asset_ids,duration):
    slots=answer['slots'];out=[]
    def make(key,kind,text='',asset='',opacity=1.):
        if key not in slots:raise ValueError('Motion reference layout invalid: missing required slot '+key)
        row=dict(slots[key]);row.update(kind=kind,text=text,asset=asset,opacity=opacity)
        return compile_layer(row)
    for i,d in enumerate(answer.get('decorations',[])):
        out.append(compile_layer({**d,'text':'','asset':'','size':.04,'font':'sans','align':'center','weight':400}))
    if answer.get('backdrop_word'):out.append(make('backdrop','text',answer['backdrop_word'],opacity=.12))
    for key in asset_ids:out.append(make('asset_'+key,'image',asset=key))
    for i,text in enumerate(parts):out.append(make('copy_'+str(i),'text',text))
    return {'duration':duration,'background':answer['background'],'camera_start':answer['camera_start'],
            'camera_end':answer['camera_end'],'layers':out,'sound_intents':answer['sound_intents']}


def plan(brain,folder,index,beat,evidence,assets,progress):
    progress(f'Local LLM assigning required text/image slots for scene {index+1}')
    # This small first call chooses the typography's actual phrase divisions.
    partition=obj({'parts':arr(string(180),1,5)})
    errors=[]
    for attempt in range(3):
        answer=ask(brain,folder,f'local-parts-{index+1}-{attempt+1}',
          'Divide this exact copy into 1–5 consecutive phrases for typographic emphasis. Preserve every word exactly once in reading order; no rewriting. Return only the parts JSON.',
          {'copy':beat['copy'],'corrections':errors},partition,300)
        parts=answer.get('parts',[])
        if re.findall(r'\w+',' '.join(parts).lower())==re.findall(r'\w+',beat['copy'].lower()):break
        errors=['Keep every word exactly once; do not add, remove or duplicate words.']
    else:raise ValueError('Motion reference layout invalid: the model did not preserve its copy.')
    D=beat['duration']
    colors=list(dict.fromkeys([v for v in evidence['measurements'].get('palette',{}).values() if isinstance(v,str) and re.fullmatch('#[0-9a-fA-F]{6}',v)]+['#ffffff','#111111','#f1ede4','#88847e']))
    style=obj({'cx':enum([.15,.25,.35,.5,.65,.75,.85]),'cy':enum([.1,.2,.3,.4,.5,.6,.7,.8,.9]),
      'w':enum([.2,.3,.45,.6,.75,.85,.9,1.]),'h':enum([.05,.1,.15,.2,.3,.4,.5,.65,.8,1.]),
      'size':enum([.035,.045,.06,.08,.1,.12,.16,.2,.26]),'font':enum(['sans','serif','italic','condensed']),
      'color':enum(colors),'align':enum(['left','center','right']),'weight':enum([400,700]),
      'rotation':enum([-30,-15,0,15,30]),'delay':enum([0.,.15,.3,.6,.9,round(D*.5,3)]),
      'end':enum([round(D*.45,3),round(D*.7,3),D]),
      'motion':enum(['rise','from-left','from-right','zoom-out','float','none']),'shadow':enum([0.,.2,.4,.6])})
    slots={**{'copy_'+str(i):style for i in range(len(parts))},**{'asset_'+key:style for key in assets},'backdrop':style}
    deco=obj({'kind':enum(['rect','ellipse','star','line']),'cx':style['properties']['cx'],'cy':style['properties']['cy'],
              'w':enum([.02,.04,.08,.2,.4,.6,1.]),'h':enum([.005,.012,.025,.05,.1,.3,.6]),
              'color':enum(colors),'opacity':enum([.12,.25,.45,1.]),'rotation':enum([-45,-30,0,30,45,90]),
              'delay':enum([0.,.3,.6]),'motion':enum(['none','float','from-left','from-right']), 'shadow':enum([0.,.2,.4])})
    sound=obj({'time':enum([t for t in [.15,.3,.6,.9,1.2,1.8,2.4,3.,3.6,4.2,5.,6.,7.] if t<D-.1]),
               'query':enum(['soft whoosh','low impact','clock tick','soft click','chime','riser','swish','short hit','subtle pop','glitch']),
               'gain_db':enum([-20.,-16.,-12.,-9.])})
    schema=obj({'background':enum(colors),'camera_start':enum([1.,1.03,1.06,1.1]),'camera_end':enum([1.,1.03,1.06,1.1]),
      'slots':obj(slots),'backdrop_word':enum(['',*list(dict.fromkeys(w.strip('.,!?') for w in beat['copy'].split() if len(w)>3))]),
      'decorations':arr(deco,0,5),'sound_intents':arr(sound,2,5)})
    system=('You are Storylens LOCAL motion designer. Fill EVERY named slot with its own type style, position and motion. '
      'Slot copy_N contains the exact supplied phrase; asset_ID contains the corresponding cutout. Roles and words are already fixed; you choose their art direction. '
      'cx/cy are box CENTRES in fractions of the frame, w/h are box fractions, size is font size divided by frame WIDTH. '
      'Make the reference-inspired photo/cutout composition: large photos, different serif/sans/condensed hierarchy, compact typography, offset rows, large faint backdrop word, shadows and accent marks. '
      'Do not put every slot at the same place or use the same size. Foreground text must remain readable, and avoid overlapping text blocks while they are visible. '
      'delay is entrance onset; end can replace one phrase with another before the scene ends. end must be later than delay+.65. '
      'Use scene duration for the image end, and use its size/position fields (font fields are ignored for images). '
      'The measured --paper token describes the reference light paper background; --bg describes the dark shade. Follow the observed light/dark sequence rather than turning everything black. '
      'backdrop_word may be empty; its backdrop slot is rendered faintly behind the image. Use decorations for lines, stars and broad shadow shapes. '
      'Choose 2–5 appropriate sound intents at actual entrance/landing/transition times. Clock ticks need a clock, and impacts need a motivated landing. '
      'All choices must use offered values. No source video pixels/audio/branding, no arbitrary code.')
    data={'scene':beat,'copy_slots':{'copy_'+str(i):text for i,text in enumerate(parts)},
      'assets':[{k:v for k,v in a.items() if k in ('id','query','seen','cutout')} for a in assets.values()],
      'reference_observations':evidence['observations'],'frame':'9:16' if evidence['height']>evidence['width'] else '16:9'}
    errors=[]
    for attempt in range(3):
        answer=ask(brain,folder,f'local-role-layout-{index+1}-{attempt+1}',system,{**data,'corrections':errors},schema,3000)
        try:
            scene=compile_slots(answer,parts,list(assets),D)
            validate_scene(scene,assets)
            return scene
        except (ValueError,KeyError) as error:errors=[str(error)]
    raise ValueError('Motion reference layout invalid: '+str(errors))
