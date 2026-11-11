"""Explicit owner choices, separate from legacy machine-suggested chosen/clip."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from .candidate_manifest import CandidateContractError, OwnerChoice, SCHEMA, VERSION, VIDEO_SUFFIXES, digest, _json_file, _quality_passed

SELECTION_SCHEMA = 'storylens.broll.owner-selections'


def _error(code, message, details=''):
    raise CandidateContractError('broll_'+code, message, details)


def _manifest(value, *, require_choices=True):
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA or type(value.get('version')) is not int or value.get('version')!=VERSION or not isinstance(value.get('slots'),list):
        _error('manifest_version', 'Rebuild a supported video-candidate manifest before choosing B-roll.')
    if (value.get('content_format') not in ('long','short') or type(value.get('per_keyword_cap')) is not int
            or value['per_keyword_cap']!={'long':2,'short':5}[value['content_format']]):
        _error('manifest_version', 'Rebuild the Long form or Short form choice limits before choosing B-roll.')
    ids=[]
    for row in value['slots']:
        if (not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('keyword_id'),str) or not isinstance(row.get('anchor'),dict)
                or not isinstance(row.get('fingerprint'),str) or not isinstance(row.get('candidates'),list)
                or require_choices and not isinstance(row.get('choice'),dict)):
            _error('manifest_invalid','Rebuild this bank’s readable keyword and owner-choice records.')
        ids.append(row['id'])
    if len(set(ids))!=len(ids):_error('manifest_invalid','Restore unique keyword identities before preparing choices.')


def _previous(value, bank_id):
    if (not isinstance(value,dict) or value.get('schema')!=SELECTION_SCHEMA or type(value.get('version')) is not int or value.get('version')!=1
            or not isinstance(bank_id,str) or not bank_id.strip() or len(bank_id)>256
            or value.get('bank_id')!=bank_id or not isinstance(value.get('choices'),dict)):
        _error('selection_version', 'Load this bank’s own supported choice file. Saved choices from another bank are kept.')
    for slot, choice in value['choices'].items():
        if (not isinstance(slot,str) or not isinstance(choice,dict)
                or choice.get('state') not in ('unselected','selected','no_broll')
                or choice.get('source') not in ('none','owner')
                or type(choice.get('revision')) is not int or choice['revision']<0
                or not isinstance(choice.get('slot_fingerprint'),str)):
            _error('selection_invalid', 'Reopen a readable owner-choice file; no saved decision will be guessed.')
        if choice['state']!='unselected' and choice['source']!='owner':
            _error('selection_invalid', 'Confirm this B-roll decision yourself; machine suggestions are not owner choices.')
        if choice['state']=='selected':
            if not isinstance(choice.get('candidate_id'),str) or not isinstance(choice.get('candidate_fingerprint'),str):
                _error('selection_invalid', 'Restore the exact selected video identity before continuing.')
        elif choice.get('candidate_id') is not None or choice.get('candidate_fingerprint') is not None:
            _error('selection_invalid', 'Check the saved no-B-roll or unselected decision; it must not select a video.')
    return value['choices']


def restore_choices(manifest, previous=None):
    """Restore by stable identities, pin a selected choice within the format cap.

    The previous fingerprint is deliberately kept when something changes. A
    blocked choice is not silently cleared, rebound or replaced with option one.
    """
    _manifest(manifest, require_choices=False)
    choices = _previous(previous,manifest['bank_id']) if previous is not None else {}
    cap = manifest['per_keyword_cap']; known=set()
    for row in manifest['slots']:
        known.add(row['id']); all_candidates=row['candidates']
        old=choices.get(row['id'])
        if old is None or old['state']=='unselected':
            choice={'state':'unselected','candidate_id':None,'candidate_fingerprint':None,
                    'slot_fingerprint':row['fingerprint'],'source':'none','revision':0,'status':'ready','issue':None}
            if old is not None: choice={**copy.deepcopy(old),'slot_fingerprint':row['fingerprint'],'status':'ready','issue':None}
        else:
            choice=copy.deepcopy(old); message=None
            if old['slot_fingerprint']!=row['fingerprint']:
                message='Review this saved choice again; its spoken keyword or timeline anchor changed.'
            if old['state']=='selected':
                found=next((c for c in all_candidates if c['id']==old['candidate_id']),None)
                if found is None: message='Relink or review the selected video; it is no longer an available verified candidate. Your exact choice is kept.'
                elif not found['selectable']: message='Review the selected video’s source-window evidence before insertion. Your exact choice is kept.'
                elif found['fingerprint']!=old['candidate_fingerprint']: message='Review this saved choice again; its video bytes, crop or trim mapping changed.'
            choice.update(status='blocked' if message else 'ready',
                          issue=CandidateContractError('broll_choice_changed',message).as_issue() if message else None)
        # Ready videos get the limited display slots before visible-but-unbound
        # legacy previews. An owner's blocked selection is still pinned below.
        ordered=sorted(all_candidates,key=lambda c:not c['selectable'])
        visible=ordered[:cap]
        if choice['state']=='selected':
            selected=next((c for c in all_candidates if c['id']==choice['candidate_id']),None)
            if selected is not None and selected not in visible: visible=visible[:cap-1]+[selected]
        row['candidates']=visible; row['omitted_by_cap']=len(all_candidates)-len(visible); row['choice']=choice
    manifest['orphaned_choices']={slot:{**copy.deepcopy(c),'status':'blocked',
        'issue':CandidateContractError('broll_slot_missing','Review this saved choice; its keyword slot is no longer in the bank. The decision is kept.').as_issue()}
        for slot,c in choices.items() if slot not in known and c['state']!='unselected'}
    return manifest


def _fingerprint(candidate, anchor):
    try:
        return digest({'id':candidate['id'],'slot_id':candidate['slot_id'],'keyword_id':candidate['keyword_id'],'original':candidate['original']['sha256'],
            'prepared':candidate['prepared']['sha256'],'anchor':anchor,
            'mapping':candidate['mapping'],'crop':candidate['check']['crop']})
    except (KeyError,TypeError,ValueError) as error:
        _error('manifest_invalid','Rebuild this candidate’s video identity and source mapping.',str(error))


def _video_candidate(candidate, row):
    if (candidate.get('kind')!='video' or candidate.get('check',{}).get('state')!='bound'
            or not candidate.get('selectable')
            or any(Path(candidate.get(k,{}).get('path','')).suffix.lower() not in VIDEO_SUFFIXES
                   for k in ('original','prepared'))):
        _error('video_required', 'Choose a checked video candidate; images, text and unbound previews cannot be inserted as B-roll.')
    if candidate.get('slot_id')!=row['id'] or candidate.get('keyword_id')!=row['keyword_id']:
        _error('choice_changed','Review this video identity; it belongs to a different keyword or timeline slot.')


def _current_receipts(manifest,row,candidate):
    """A later rejection or edited bank must not hide behind an old receipt ref."""
    refs=candidate['check']; project_path=Path(manifest['project_path']).resolve()
    try:
        project=_json_file(project_path)
        source_slot=None
        for kind,field in (('verdict','verdict_ref'),('window','window_ref')):
            ref=refs[field]
            if Path(ref['project_path']).resolve()!=project_path: raise ValueError('Receipt belongs to a different project')
            parts=ref['json_pointer'].strip('/').split('/')
            if len(parts) not in (4,5) or parts[0]!='slots': raise ValueError('Invalid receipt pointer')
            if (not parts[1].isdigit() or not parts[3].isdigit()
                    or kind=='verdict' and (len(parts)!=4 or parts[2]!='checks')
                    or kind=='window' and (len(parts)!=5 or parts[2]!='options' or parts[4]!='checked_window')):
                raise ValueError('Receipt pointer has the wrong type')
            source_slot=project['slots'][int(parts[1])]
            if source_slot.get('index',int(parts[1]))!=row['slot_index']: raise ValueError('Receipt belongs to another keyword slot')
            value=project
            for part in parts: value=value[int(part)] if isinstance(value,list) else value[part]
            if digest(value)!=ref['sha256']: raise ValueError(kind+' receipt changed')
            if kind=='verdict':
                last=[c for c in source_slot['checks'] if c.get('id')==candidate['candidate_id']][-1]
                if digest(last)!=ref['sha256'] or not _quality_passed(last): raise ValueError('Latest saved check is not the selected approval')
            else:
                from fractions import Fraction
                if (value.get('schema')!='storylens.broll.checked-window' or type(value.get('version')) is not int or value['version']!=1
                        or value.get('candidate_id')!=candidate['candidate_id']
                        or value.get('verdict_sha256')!=refs['verdict_ref']['sha256']
                        or value.get('source_sha256')!=candidate['original']['sha256']
                        or value.get('prepared_sha256')!=candidate['prepared']['sha256']
                        or value.get('crop')!=refs['crop']):
                    raise ValueError('Window receipt does not bind this candidate and its actual files')
                tolerance=.5/float(Fraction(row['anchor']['fps']))+1e-7
                if any(abs(value[key]-candidate['mapping']['original_active'][key])>tolerance for key in ('start','end')):
                    raise ValueError('Window receipt belongs to a different active interval')
        from .candidate_manifest import _anchor
        for stage,ref in refs.get('producer_checks',{}).items():
            parts=ref['json_pointer'].strip('/').split('/')
            if (stage not in ('original','prepared') or Path(ref['project_path']).resolve()!=project_path
                    or len(parts)!=4 or parts[0]!='slots' or parts[2]!='checks'
                    or not parts[1].isdigit() or not parts[3].isdigit()):
                raise ValueError('Invalid source/prepared check reference')
            saved_slot=project['slots'][int(parts[1])]
            actual=saved_slot['checks'][int(parts[3])]
            media=candidate[stage if stage=='original' else 'prepared']
            if (saved_slot.get('index',int(parts[1]))!=row['slot_index'] or digest(actual)!=ref['sha256']
                    or not _quality_passed(actual) or actual.get('id')!=candidate['candidate_id']
                    or actual.get('producer_stage')!=stage or actual.get('checked_media_sha256')!=media['sha256']):
                raise ValueError('Actual source/prepared check changed')
        if _anchor(source_slot,manifest['timeline'])!=row['anchor'] or source_slot.get('visual','')!=row['keyword']:
            raise ValueError('Saved keyword/anchor changed')
        from fractions import Fraction
        if any(project['timeline'][key]!=manifest['timeline'][key] for key in ('width','height','duration')) or Fraction(str(project['timeline']['fps']))!=Fraction(manifest['timeline']['fps']):
            raise ValueError('Saved timeline metadata changed')
    except CandidateContractError: raise
    except (KeyError,TypeError,ValueError,IndexError,ZeroDivisionError) as error:
        _error('check_changed','Review this selected video again; its saved footage check or source anchor changed.',str(error))


def choose(manifest, slot_id, state, candidate_id=None):
    """Call only after an explicit UI choice. Returns a copy, never inserts."""
    _manifest(manifest)
    result=copy.deepcopy(manifest)
    row=next((r for r in result['slots'] if r['id']==slot_id),None)
    if row is None: _error('slot_missing', 'Choose an existing keyword slot from this B-roll bank.')
    if state not in ('unselected','selected','no_broll'):
        _error('selection_invalid', 'Choose a video, No B-roll, or clear your choice.')
    candidate=None
    if state=='selected':
        candidate=next((c for c in row['candidates'] if c['id']==candidate_id),None)
        if candidate is None or not candidate.get('selectable'):
            _error('selection_unavailable', 'Choose a checked video from this keyword’s available choices. Nothing was inserted.')
        _video_candidate(candidate,row)
        if _fingerprint(candidate,row['anchor'])!=candidate['fingerprint']:
            _error('choice_changed', 'Rebuild this candidate manifest; its saved video mapping changed.')
    elif candidate_id is not None:
        _error('selection_invalid', 'Clear the video identity when choosing No B-roll or unselected.')
    old=row['choice']
    new={'state':state,'candidate_id':candidate_id if candidate else None,
         'candidate_fingerprint':candidate['fingerprint'] if candidate else None,
         'slot_fingerprint':row['fingerprint'],'source':'owner',
         'revision':old.get('revision',0)+1,'status':'ready','issue':None}
    if all(old.get(k)==new[k] for k in new if k!='revision'): new['revision']=old['revision']
    row['choice']=new
    return result


def selection_state(manifest):
    _manifest(manifest)
    choices={r['id']:copy.deepcopy(r['choice']) for r in manifest['slots']}
    choices.update(copy.deepcopy(manifest.get('orphaned_choices',{})))
    result={'schema':SELECTION_SCHEMA,'version':1,'bank_id':manifest['bank_id'],'choices':choices}
    _previous(result,manifest['bank_id'])
    return result


def save_selections(path, manifest):
    """Explicit sidecar write only; never overwrite a project or arbitrary JSON."""
    path=Path(path); state=selection_state(manifest)
    if path.suffix.casefold()!='.json': _error('selection_invalid', 'Choose a separate JSON file for owner choices.')
    if path.exists(): _previous(_json_file(path),manifest['bank_id'])
    from .recovery import write_json
    try: write_json(path,state)
    except OSError as error:
        _error('choice_save_failed','Choose a writable separate file for owner choices, then save again. Existing choices are kept.',str(error))
    return state


def load_selections(path):
    state=_json_file(path)
    _previous(state,state.get('bank_id'))
    return state


def selected_candidates(manifest):
    """Return only explicit, still-valid decisions. No host/queue side effects.

    Hash selected original and preview files again at the handoff boundary.
    Native hosts must still validate bounds/target identity and return a receipt.
    """
    _manifest(manifest)
    if manifest.get('orphaned_choices'):
        _error('slot_missing', 'Review saved choices for removed keywords before preparing an insertion.')
    result=[]
    for row in manifest['slots']:
        choice=row['choice']
        if choice['status']=='blocked':
            _error('choice_changed', 'Review the blocked saved B-roll choice before preparing an insertion.')
        if choice['state']!='selected': continue
        candidate=next((c for c in row['candidates'] if c['id']==choice['candidate_id']),None)
        if (choice.get('source')!='owner' or candidate is None or not candidate.get('selectable')
                or _fingerprint(candidate,row['anchor'])!=choice['candidate_fingerprint']
                or digest({'anchor':row['anchor'],'keyword':row['keyword']})!=choice['slot_fingerprint']):
            _error('choice_changed', 'Review this B-roll decision again; its identity, anchor or source mapping changed.')
        _video_candidate(candidate,row)
        _current_receipts(manifest,row,candidate)
        for media in (candidate['original'],candidate['prepared']):
            file=Path(media['path'])
            try:
                sha=hashlib.sha256()
                with file.open('rb') as stream:
                    while chunk:=stream.read(1024*1024):sha.update(chunk)
                if sha.hexdigest()!=media['sha256']:raise ValueError('Content fingerprint changed')
            except (OSError,ValueError) as error:
                _error('media_changed','Relink or review the selected video before insertion; its bytes changed or disappeared.',str(error))
        result.append({**copy.deepcopy(candidate),'anchor':copy.deepcopy(row['anchor']),
                       'keyword':row['keyword'],'owner_choice':copy.deepcopy(choice)})
    return result
