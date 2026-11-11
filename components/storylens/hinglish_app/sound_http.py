"""Sound library endpoints inside the authenticated Storylens workbench."""
from pathlib import Path
from hinglish_cinematic.curation import file_hash,resolve_sound
from hinglish_cinematic.recipes import CATEGORIES,SOUND_RECIPES,EDIT_RECIPES,compile_sound
from hinglish_cinematic.sound_catalog import inspect_audio,import_audio,review_audio
from .curation_http import store
from .workbench_jobs import service

def get(handler,state,path,query):
    database=store(state)
    if path.endswith('/sounds'):
        return handler._json(200,{'sounds':database.list('sound'),'categories':CATEGORIES,'recipes':SOUND_RECIPES,'edit_recipes':EDIT_RECIPES})
    if path.endswith('/sound-media'):
        from .workbench_http import _media
        row=database.get(query.get('asset',[''])[0])
        if row['kind']!='sound':raise ValueError('Choose a saved sound.')
        if file_hash(row['path'])!=row['hash']:raise ValueError('This recording changed. Reimport it before auditioning.')
        return _media(handler,Path(row['path']),False)
    if path.endswith('/mix-media'):
        from .workbench_http import _media
        row=service(state).snapshot(query.get('id',[''])[0])
        if row['kind']!='sound-mix' or row['status']!='complete':raise ValueError('Choose a completed mix.')
        return _media(handler,Path(row['result']['path']),False)
    raise ValueError('Choose a supported sound result.')

def post(handler,state,path,value):
    database=store(state)
    if path.endswith('/sound-inspect'):
        result=inspect_audio(value['path']);result['id']=result['hash'];result['revision']=0
        try:result['revision']=database.get(result['id'])['revision']
        except ValueError:pass
        return handler._json(200,result)
    if path.endswith('/sound-import'):
        result=import_audio(database,value,state.root/'cache/curation/sounds')
    elif path.endswith('/sound-review'):result=review_audio(database,value)
    elif path.endswith('/sound-plan'):
        choices=value['choices'];catalog=database.list('sound')
        plan = compile_sound(value['recipe_id'], choices, catalog, value.get('duration'),
                             anchor=value.get('anchor'), tail=value.get('tail'),
                             target_lufs=value.get('target_lufs', -14), true_peak_dbtp=value.get('true_peak_dbtp', -1))
        hashes=sorted(set(event['hash'] for event in plan['events']))
        if sorted(value['input_hashes'])!=hashes:raise ValueError('Sound choices changed. Refresh the recipe.')
        plan.update(original_audio=str(Path(value['original_audio']).resolve()),original_audio_hash=file_hash(value['original_audio']),dialogue_activity=value.get('dialogue_activity',[]))
        result=database.mutate(value['id'],'sound-plan',value,lambda old:plan)
    elif path.endswith('/sound-render'):
        plan=database.get(value['id'])
        if plan['kind']!='sound-plan' or plan['revision']!=value['expected_revision']:raise ValueError('Reload the current mix plan before rendering.')
        for event in plan['events']:resolve_sound(database.list('sound'),event['asset_id'],event['hash'])
        if file_hash(plan['original_audio'])!=plan['original_audio_hash']:raise ValueError('Original audio changed; revise this mix plan.')
        result=service(state).start('sound-mix',{'plan_id':plan['id'],'plan_revision':plan['revision'],'idempotency_key':value['idempotency_key']})
        return handler._json(202,result)
    else:raise ValueError('Choose a supported sound command.')
    return handler._json(200,result)
