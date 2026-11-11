"""Functional Smart Visuals question receipts; never infer a subject answer."""
import copy
import json
from pathlib import Path


def read(root, job_id):
    root=Path(root).resolve()
    if not isinstance(job_id,str) or not job_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in job_id):
        return None
    marker=root/'cache/app/jobs'/job_id/'visuals-clarification.json'
    try:
        if marker.stat().st_size>1024*1024:return None
        data=json.loads(marker.read_text('utf-8'))
        if data.get('version')!=1 or data.get('needs_clarification') is not True:return None
        questions=data.get('questions');outcomes=data.get('outcomes')
        if not isinstance(questions,list) or not questions or len(questions)>100:return None
        if any(not isinstance(q,str) or not q.strip() or len(q)>2000 for q in questions):return None
        if not isinstance(outcomes,dict) or not outcomes:return None
        offered=[o.get('clarification_question') for o in outcomes.values()
                 if isinstance(o,dict) and o.get('needs_clarification') is True]
        if any(q not in offered for q in questions):return None
        path=Path(data['resolution_file']).resolve()
        if not path.is_relative_to(root/'output/visuals') or path.name!='visuals-resolution.json':return None
        if path.stat().st_size>1024*1024:return None
        original=json.loads(path.read_text('utf-8'))
        if any(original.get(k)!=data.get(k) for k in ('version','needs_clarification','questions','outcomes')):return None
        return data
    except (OSError,ValueError,KeyError,TypeError,AttributeError):return None


def message(clarification):
    return ' '.join(clarification['questions'][:3])+' Your original video, words and saved context are kept. Reply here to continue.'


def pause(assistant, session_id, job, request, payload):
    if (job.get('error_code')!='visuals_clarification_required' or job.get('needs_input') is not True
            or not isinstance(job.get('clarification'),dict)):return False
    data=copy.deepcopy(job['clarification'])
    assistant._message(session_id,'assistant',message(data),question=True)
    assistant._update(session_id,status='idle',stage='Waiting for a visual subject clarification',job_id=None,
        needs_input=True,visual_clarification={**data,'request':request,'payload':copy.deepcopy(payload),
            'engine_id':job['id']})
    return True
