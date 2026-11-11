"""Curation commands through the existing authenticated workbench bridge."""
from pathlib import Path
import json
import shutil
from hinglish_cinematic.curation import Store, digest, propose_body, PHASES
from .workbench_jobs import service


def store(state):
    return Store(state.root/'cache/curation/projects.sqlite3')


def snapshot(state, job_id):
    job=service(state).snapshot(job_id)
    if job['kind']!='footage':raise ValueError('Choose a footage dataset.')
    try:return store(state).get(job_id)
    except ValueError:
        return {'id':job_id,'revision':0,'kind':'curation','candidates':job.get('result',{}).get('assets',[]),
                'body':None,'feedback':[],'approval_state':'candidate_review'}


def preselection_gate(state):
    try:
        record = store(state).get('held-out-quality-v1')
    except ValueError:
        return {'passed': False}
    if record.get('kind') != 'quality-review':
        return {'passed': False}
    ids = record.get('candidate_ids', [])
    approved = record.get('approved_ids', [])
    passed = bool(ids and len(set(ids)) == len(ids) and set(approved) <= set(ids)
                  and len(set(approved)) * 5 >= len(ids) * 4 and record.get('reviewer') == 'owner')
    return {'passed': passed, 'reviewed': len(ids), 'approved': len(set(approved))}


def command(state, value):
    job_id=value['id'];job=service(state).snapshot(job_id)
    if job['kind']!='footage' or job['status']!='complete':raise ValueError('Finish collecting this footage first.')
    operation=value.get('operation')
    if operation not in ('review_candidate','propose_body','edit_body','approve_revision','reorder_phases','ban_candidate','pin_candidate','annotate_candidate'):
        raise ValueError('Choose a supported curation command.')
    def change(previous):
        data=previous or snapshot(state,job_id)
        rows={r['id']:r for r in data['candidates']}
        expected=sorted({r['source_sha256'] for r in rows.values()})
        if sorted(value['input_hashes'])!=expected:raise ValueError('Dataset source identities changed. Reload the review.')
        if operation=='annotate_candidate':
            row=rows.get(value.get('clip_id'))
            if row is None:raise ValueError('Choose a known candidate.')
            annotation=value.get('annotation',{})
            if not annotation.get('evidence') or annotation.get('reviewer') not in ('owner','assistant','connected_model'):
                raise ValueError('Record the actual temporal review evidence and reviewer.')
            for field in ('description','location'):
                text=annotation.get(field,'')
                if not isinstance(text,str) or len(text)>2000:raise ValueError('Use bounded source-backed annotations.')
                row[field]=text
            for field in ('tags','camera_moves'):
                values=annotation.get(field,[])
                if not isinstance(values,list) or len(values)>50 or any(not isinstance(t,str) or len(t)>120 for t in values):raise ValueError('Use short annotation tags.')
                row[field]=values
            row.update(semantic_status='reviewed',semantic_evidence=annotation['evidence'],semantic_reviewer=annotation['reviewer'])
            data['feedback'].append({'clip_id':row['id'],'operation':operation,'annotation':annotation})
        elif operation=='review_candidate':
            id=value.get('clip_id');row=rows.get(id)
            if row is None:raise ValueError('Choose a candidate from this dataset.')
            review=value.get('review_state','unreviewed');phases=value.get('phase_tags',row.get('phase_tags',[]))
            if review not in ('unreviewed','approved','rejected'):raise ValueError('Choose a valid candidate review state.')
            if not isinstance(phases,list) or any(p not in set(sum(PHASES.values(),[])) for p in phases):raise ValueError('Choose supported story phases.')
            if not isinstance(value.get('reason',''),str) or len(value.get('reason',''))>2000:raise ValueError('Use a short review reason.')
            old = {k: row.get(k) for k in ('phase_tags', 'review_state', 'rating')}
            if 'rating' in value:
                rating = value['rating']
                if type(rating) is not int or not 0 <= rating <= 5:
                    raise ValueError('Choose an integer rating from 0 to 5.')
                row['rating'] = rating
            row.update(phase_tags=phases,review_state=review,reviewer=value.get('reviewer','owner'),review_reason=value.get('reason',''))
            data['feedback'].append({'clip_id':id,'old':old,'new':{'phase_tags':phases,'review_state':review,'rating':row.get('rating')},
                                     'reason':value.get('reason',''),'reviewer':value.get('reviewer','owner')})
            if data.get('body'):data['body']['approval_state']='plan_review';data['body']['assemblies_valid']=False
        elif operation=='propose_body':
            preselection = value.get('preselection', False) is True
            if preselection and not preselection_gate(state)['passed']:
                raise ValueError('Automatic suggestions need a passing held-out owner review.')
            data['body'] = propose_body(list(rows.values()), value.get('recipe', 'waterfall'), data.get('body'),
                                        preselection=preselection)
        elif operation in ('reorder_phases','ban_candidate','pin_candidate'):
            body=data.get('body')
            if not body:raise ValueError('Propose a body first.')
            if operation=='reorder_phases':
                phases=value.get('phase_order',[])
                if len(phases)!=len(body['phase_order']) or set(phases)!=set(body['phase_order']):raise ValueError('Reorder the existing phases without duplicates.')
                body['phase_order']=phases
                body['slot_assignments'].sort(key=lambda a:phases.index(a['phase']))
            else:
                clip=value.get('clip_id')
                if clip not in rows:raise ValueError('Choose a known candidate.')
                locks=body.setdefault('locked_decisions',{})
                if operation=='ban_candidate':
                    if clip in locks.values():raise ValueError('Unlock the candidate before banning it.')
                    banned=set(body.get('banned',[]))
                    if value.get('enabled',True):banned.add(clip)
                    else:banned.discard(clip)
                    body['banned']=sorted(banned)
                    for slot in body['slot_assignments']:
                        if slot['clip_id'] in banned:slot.update(clip_id=None,gap=True,locked=False)
                else:
                    phase=value.get('phase')
                    if phase not in body['phase_order'] or clip in body.get('banned',[]) or rows[clip]['review_state']=='rejected':raise ValueError('Choose an available candidate and a story phase.')
                    if clip in locks.values() and locks.get(phase)!=clip:raise ValueError('This candidate is already pinned to another phase.')
                    locks[phase]=clip
                    for slot in body['slot_assignments']:
                        if slot['phase']==phase:slot.update(clip_id=clip,gap=False,locked=True)
                        elif slot['clip_id']==clip:slot.update(clip_id=None,gap=True,locked=False)
            body['ordered_clip_ids']=[a['clip_id'] for a in body['slot_assignments'] if a['clip_id']]
            body['missing_phases']=[a['phase'] for a in body['slot_assignments'] if a['gap']]
            body.update(approval_state='plan_review',assemblies_valid=False)
        elif operation=='edit_body':
            body=data.get('body')
            if not body:raise ValueError('Propose a body first.')
            phase=value.get('phase');clip_id=value.get('clip_id')
            if phase not in body['phase_order'] or clip_id not in rows:raise ValueError('Choose a known phase and candidate.')
            if rows[clip_id].get('review_state')=='rejected':raise ValueError('Reapprove this rejected candidate before using it.')
            if clip_id in body.get('banned',[]):raise ValueError('This candidate is banned.')
            locks=body.setdefault('locked_decisions',{})
            if value.get('locked',True):locks[phase]=clip_id
            else:locks.pop(phase,None)
            for a in body['slot_assignments']:
                if a['phase']==phase:a.update(clip_id=clip_id,locked=bool(value.get('locked',True)),gap=False)
            body['ordered_clip_ids']=[a['clip_id'] for a in body['slot_assignments'] if a['clip_id']]
            if len(set(body['ordered_clip_ids']))!=len(body['ordered_clip_ids']):raise ValueError('A body candidate cannot occupy two phases.')
            body['missing_phases']=[a['phase'] for a in body['slot_assignments'] if a['gap']]
            body.update(approval_state='plan_review',assemblies_valid=False)
        else:
            body=data.get('body')
            if not body or not body['ordered_clip_ids']:raise ValueError('Choose at least one body clip before approval.')
            if body['missing_phases'] and value.get('accept_missing_phases') is not True:
                raise ValueError('Review the missing phases before approving the available story.')
            if any(rows[id]['review_state']!='approved' for id in body['ordered_clip_ids']):
                raise ValueError('Review and approve the selected candidates first.')
            body.update(approval_state='approved',plan_hash=digest(body),assemblies_valid=False,reviewer=value.get('reviewer','owner'),accepted_missing_phases=bool(value.get('accept_missing_phases')))
        data['approval_state']='plan_review' if data.get('body') else 'candidate_review'
        return data
    result=store(state).mutate(job_id,'curation',value,change)
    # Materialized selections are recoverable projections of the committed record.
    output=service(state)._file(job_id).parent/'Best Clip'
    selected=set((result.get('body') or {}).get('ordered_clip_ids',[]))
    for bank in ('Selected','Unused'):
        folder=output/bank;folder.mkdir(exist_ok=True)
        wanted = {}
        known = set()
        for row in result['candidates']:
            relative = Path(row.get('orientation', '')) / row['filename']
            known.add(relative)
            if (row['id'] in selected) == (bank == 'Selected') and row['review_state'] != 'rejected':
                wanted[relative] = row
        for relative in known - wanted.keys():
            (folder / relative).unlink(missing_ok=True)
        for relative, row in wanted.items():
            dest = folder / relative
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                import os
                try:os.link(row['best_clip_path'],dest)
                except OSError:shutil.copy2(row['best_clip_path'],dest)
    review=output/'Review'
    temporary=review/'curation.tmp';temporary.write_text(json.dumps(result,indent=2),encoding='utf-8');temporary.replace(review/'curation.json')
    return result
