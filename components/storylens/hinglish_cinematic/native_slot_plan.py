"""Suggest reviewed footage in approved narrative order for inspected native slots."""
def timeline_slots(manifest):
    comps={str(c['id']):c for c in manifest['compositions']}
    result=[]
    for slot in manifest['slots']:
        start=float(slot['in_point']);end=float(slot['out_point'])
        for entry in reversed(slot['comp_path']):
            comp=comps[str(entry['comp_id'])]
            layer=next(l for l in comp['layers'] if str(l['id'])==str(entry['layer_id']))
            if float(layer.get('stretch',100))!=100 or any(p.get('matchName')=='ADBE Time Remapping' and p.get('keys',0)>0 for p in layer.get('properties',[])):
                raise ValueError('Narrative slot suggestions need a reviewed time map for retimed nesting.')
            start=max(start+float(layer['startTime']),float(layer['inPoint']))
            end=min(end+float(layer['startTime']),float(layer['outPoint']))
        if end<=start:raise ValueError('A media slot is not visible in the root timeline.')
        result.append({**slot,'timeline_start':start,'timeline_end':end})
    return sorted(result,key=lambda s:(s['timeline_start'],s['slot_id']))

def propose_slots(manifest,bank):
    body=bank.get('body')
    if not body:raise ValueError('Save the narrative storyboard before proposing native slots.')
    order=body['phase_order'];rows={r['id']:r for r in bank['candidates']}
    banned=set(body.get('banned',[]));pool=[];seen=set()
    for phase in order:
        pinned=body.get('locked_decisions',{}).get(phase)
        eligible=[r for r in rows.values() if r['id'] not in banned and r['review_state']=='approved' and phase in r.get('phase_tags',[])]
        eligible.sort(key=lambda r:(r['id']!=pinned,r['source_id'],r['start']))
        for row in eligible:
            if row['id'] not in seen:pool.append((phase,row));seen.add(row['id'])
    assignments=[];used=[];cursor=0
    for slot in timeline_slots(manifest):
        chosen=None;seconds=slot['duration_frames']/slot['fps']
        for index in range(cursor,len(pool)):
            phase,row=pool[index]
            overlap=any(old['source_id']==row['source_id'] and min(old['end'],row['start']+seconds)-max(old['start'],row['start'])>1/slot['fps'] for old in used)
            if row['duration']+.001>=seconds and not overlap:
                chosen=(index,phase,row);break
        if chosen:
            index,phase,row=chosen;cursor=index+1
            used.append({'source_id':row['source_id'],'start':row['start'],'end':row['start']+seconds})
            assignments.append({'slot_id':slot['slot_id'],'candidate_id':row['id'],'phase':phase,'timeline_start':slot['timeline_start']})
        else:assignments.append({'slot_id':slot['slot_id'],'candidate_id':None,'phase':None,'timeline_start':slot['timeline_start'],'gap':'No remaining distinct reviewed candidate fits this slot in story order.'})
    selected={a['candidate_id'] for a in assignments}
    omitted=[{'phase':p,'candidate_id':id} for p,id in body.get('locked_decisions',{}).items() if id not in selected]
    return {'dataset_id':bank['id'],'expected_revision':bank['revision'],'assignments':assignments,'missing_phases':body.get('missing_phases',[]),'omitted_locked_choices':omitted,'ready_for_review':not omitted and all(a['candidate_id'] for a in assignments),'approval_state':'plan_review'}
