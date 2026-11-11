"""Bounded continuous GSAP tracks selected by the local reference planner."""
import math


def compile_motion(answer,duration):
    camera=answer['camera'];kind=answer['image_motion'];travel=answer['travel']
    if camera not in ('push-in','pull-out','pan-left','pan-right','punch-in') or kind not in ('parallax-left','parallax-right','rise-drift','slow-turn'):
        raise ValueError('Motion reference movement invalid: select a supported moving camera and layer track.')
    if not math.isfinite(travel) or not .04<=travel<=.12 or not math.isfinite(duration) or duration<1:
        raise ValueError('Motion reference movement invalid: travel and duration must be finite and visible.')
    start={'time':0.,'scale':1.,'x':0.,'y':0.};end={'time':duration,'scale':1.12,'x':0.,'y':-.015}
    if camera=='pull-out':start['scale']=1.16;end['scale']=1.
    elif camera in ('pan-left','pan-right'):
        sign=1 if camera=='pan-left' else -1
        start.update(scale=1.10,x=sign*.04);end.update(scale=1.10,x=-sign*.04,y=0.)
    keys=[start,end]
    if camera=='punch-in':keys=[start,{**end,'time':duration*.8,'scale':1.08},{**end,'scale':1.38}]
    image={'x':-travel if kind=='parallax-left' else travel if kind=='parallax-right' else 0.,
           'y':-travel*.7 if kind=='rise-drift' else -travel*.2,'scale':1.08,'rotation':4. if kind=='slow-turn' else 0.}
    return {'camera':keys,'image':image,'light_sweep':bool(answer['light_sweep']),
            'particles':int(answer['particles']),'transition':answer['transition'],'model_choices':answer}


def plan(brain,folder,index,scene,evidence,profiles,progress):
    from .reference_composer import obj,ask
    from .reference_slots import enum
    progress(f'Local LLM rebuilding continuous camera, parallax and light movement {index+1}')
    schema=obj({'camera':enum(['push-in','pull-out','pan-left','pan-right','punch-in']),
      'image_motion':enum(['parallax-left','parallax-right','rise-drift','slow-turn']),
      'travel':enum([.04,.08,.12]),'light_sweep':{'type':'boolean'},'particles':enum([12,16,24]),
      'transition':enum(['zoom-blur','soft-cut','slide-blur'])})
    answer=ask(brain,folder,f'local-continuous-motion-{index+1}',
      'Rebuild this reference as actual MOTION GRAPHICS, not a poster. Select a continuous camera track and an independent moving photo layer. '
      'Use the timestamped source movement evidence. Track travel is frame-relative displacement over the shot. '
      'Match diagonal moving light/shadows and drifting dust when observed; use an intentional zoom/blur or slide transition. '
      'A locked identical start/end camera and stationary image are not allowed for this owner-requested moving demonstration. '
      'Words, images and soundtrack remain the existing local-model choices. Return supported track IDs, no code.',
      {'scene':scene,'source_motion_evidence':evidence.get('observations',[]),'native_text_profiles':profiles},schema,700)
    return compile_motion(answer,scene['duration'])
