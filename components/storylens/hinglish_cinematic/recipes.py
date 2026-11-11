"""Versioned recipe defaults from architecture pages 11–12, not invented assets."""
import math

from .curation import resolve_sound

CATEGORIES=('01_Reveal_Buildup','02_Impacts','03_Ambience','04_Transitions',
            '05_Foley','06_Suspense','07_Music_Beds','08_Stingers')

# Each tuple is role, start, end, nominal gain dB. A user's approved recording is
# required for every populated role. Defaults remain editable and unauditioned.
SOUND_RECIPES={
 'SND_CIN_A_v1':{'duration':5,'events':[('ambience',0,5,-22),('rise',0,3.8,-18),('movement',.6,.9,-12),('movement',2.1,2.4,-12),('impact',3.8,4.2,-10),('bridge',4.2,5,-20)]},
 'SND_CIN_B_v1':{'duration':5,'events':[('foley',0,.5,-12),('pulse',.5,4.2,-22),('movement',1.3,1.6,-12),('movement',3,3.3,-12),('arrival',4.2,5,-15)]},
 'SND_CIN_C_v1':{'duration':5,'preserve_original_reaction':True,'events':[('rise',0,3.4,-24),('accent',3.4,4,-12),('ambience',4,5,-22)]},
 'SND_REVEAL_v1':{'duration':2.5,'anchor':1.5,'events':[('rise',0,1.5,-18),('impact',1.5,2.5,-10),('ambience',1.5,2.5,-22)]},
 'SND_IMPACT_v1':{'duration':1,'anchor':0,'events':[('impact',0,1,-12)]},
 'SND_AMBIENCE_v1':{'duration':5,'events':[('ambience',0,5,-22)]},
 'SND_CRICKET40_v1':{'duration':40,'events':[('cold_open',0,5,-20),('bed',5,12,-26),('tension_a',12,21,-25),('tension_b',21,30,-25),('rise',30,35.5,-22),('landing',36,40,-18)]},
}

EDIT_RECIPES={
 'EDIT_TRIP_ORDER_v1':{'phases':['departure','travel','approach','reveal','experience','closing']},
 'EDIT_PARTY_ORDER_v1':{'phases':['preparation','travel','arrival','atmosphere','highlights','closing']},
 'EDIT_CIN_A_v1':{'premise':'destination_tease','frames':[18,21,24,27,36,24]},
 'EDIT_CIN_B_v1':{'premise':'journey_momentum','frames':[18,21,24,27,36,24]},
 'EDIT_CIN_C_v1':{'premise':'human_reaction','frames':[18,21,24,27,36,24]},
 'EDIT_CRICKET40_v1':{'sections':[0,5,12,21,30,36,40],'protect_payoffs':True,
                      'section_roles':['Cold open','Context and stakes','First story thread','Second story thread','Escalation','Title and handoff']},
}
for recipe in EDIT_RECIPES.values():
    recipe.update(version=1,allowed_transitions=['cut'],fallback='needs_input',
                  qa=['source_traceability','no_unapproved_retiming','human_review'])


def _number(value, label, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be between {low} and {high}.')
    return value


def compile_sound(recipe_id, choices, catalog, duration=None, *, anchor=None,
                  tail=None, target_lufs=-14, true_peak_dbtp=-1):
    recipe=SOUND_RECIPES.get(recipe_id)
    if recipe is None:raise ValueError('Choose a saved sound recipe.')
    flexible = recipe_id in ('SND_AMBIENCE_v1', 'SND_IMPACT_v1', 'SND_REVEAL_v1')
    if anchor is not None and 'anchor' not in recipe:
        raise ValueError('This recipe uses its fixed cue timings.')
    if tail is not None and recipe_id != 'SND_IMPACT_v1':
        raise ValueError('Tail length is configurable for the single-impact recipe.')
    if anchor is None:
        anchor = recipe.get('anchor')
    else:
        _number(anchor, 'Cue anchor', recipe['anchor'], 3600)
    if tail is not None:
        _number(tail, 'Impact tail', .01, 10)
    offset = anchor - recipe['anchor'] if anchor is not None else 0
    required_end = offset + (tail if tail is not None else recipe['duration'])
    if duration is None:
        duration = required_end
    _number(duration, 'Mix duration', .01, 3600)
    if not flexible and duration != recipe['duration']:
        raise ValueError('This recipe uses its declared duration.')
    if recipe_id in ('SND_IMPACT_v1', 'SND_REVEAL_v1') and duration < required_end:
        raise ValueError('The mix is too short for the cue and its tail.')
    _number(target_lufs, 'Loudness target', -36, -10)
    _number(true_peak_dbtp, 'True peak ceiling', -9, -1)
    events=[]
    for index,(role,start,end,gain) in enumerate(recipe['events']):
        start += offset
        end = start + tail if tail is not None else end + offset
        choice=choices.get(role)
        if not choice:raise ValueError('Choose and audition an approved recording for role: '+role)
        asset=resolve_sound(catalog,choice['asset_id'],choice['hash'])
        if recipe_id=='SND_AMBIENCE_v1':end=duration
        source_in=choice.get('source_in',0)
        _number(source_in, 'Recording start', 0, asset['duration'])
        if source_in + end - start > asset['duration'] + 1e-9:
            raise ValueError('The selected sound is too short. Choose another recording or an explicitly auditioned loop.')
        level=choice.get('gain_db',gain)
        if not isinstance(level,(float,int)) or not -60<=level<=6:raise ValueError('Choose a gain between -60 and +6 dB.')
        events.append({'id':recipe_id+':'+str(index),'role':role,'asset_id':asset['id'],'hash':asset['hash'],
                       'path':asset['path'],'source_in':source_in,'start':start,'end':end,'gain_db':level,
                       'fade_in':min(.015,(end-start)/4),'fade_out':min(.06,(end-start)/4),
                       'license_evidence':asset['license_evidence']})
    return {'recipe_id':recipe_id,'version':1,'duration':duration,'events':events,'sample_rate':48000,
            'anchor':anchor,'target_lufs':target_lufs,'true_peak_dbtp':true_peak_dbtp,
            'audition_state':'pending','preserve_original_audio':True}


def bind_edit_recipe(plan):
    """Bind an executable cinematic rhythm to its versioned definition."""
    identifier=plan.get('edit_recipe_id')
    if not identifier:return plan  # Existing source-reviewed plans keep their original contract.
    recipe=EDIT_RECIPES.get(identifier)
    if not recipe or not identifier.startswith('EDIT_CIN_'):
        raise ValueError('Choose a cinematic editing recipe for this montage.')
    if plan.get('edit_recipe_version')!=recipe['version']:
        raise ValueError('The editing recipe version changed; review the current rhythm.')
    if plan['fps']!=30 or [span['frames'] for span in plan['source_spans']]!=recipe['frames']:
        raise ValueError('The source spans do not follow this saved editing rhythm.')
    return {**plan,'edit_recipe':dict(recipe),'edit_recipe_id':identifier}
