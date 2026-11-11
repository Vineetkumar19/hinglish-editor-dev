"""Producer bookkeeping around actual checks. No model decisions are invented."""
import copy
import hashlib
from pathlib import Path

from .candidate_manifest import CandidateContractError, _quality_passed, checked_window_receipt, digest


def snapshot_file(path):
    path=Path(path).resolve()
    try:
        before=path.stat();sha=hashlib.sha256()
        with path.open('rb') as stream:
            while chunk:=stream.read(1024*1024):sha.update(chunk)
        after=path.stat()
        stamp=(after.st_size,after.st_mtime_ns,after.st_ino)
        if stamp!=(before.st_size,before.st_mtime_ns,before.st_ino):raise ValueError('File changed during hashing')
        return {'path':str(path),'sha256':sha.hexdigest(),'stamp':stamp}
    except (OSError,ValueError) as error:
        raise CandidateContractError('broll_media_changed',
            'Wait for this video to finish changing, then check it again. Saved choices are kept.',str(error)) from error


def assert_snapshot(snapshot):
    try:
        stat=Path(snapshot['path']).stat()
        if (stat.st_size,stat.st_mtime_ns,stat.st_ino)!=snapshot['stamp']:raise ValueError('File changed after its actual check began')
    except (OSError,ValueError) as error:
        raise CandidateContractError('broll_media_changed',
            'Review this changing video again before preparing B-roll. No new choice was approved.',str(error)) from error


def record_check(verdict,candidate_id,stage,snapshot,start,duration,crop):
    """Add deterministic provenance; leave every model verdict flag untouched."""
    return {**copy.deepcopy(verdict),'id':candidate_id,'producer_stage':stage,
            'checked_media_path':snapshot['path'],'checked_media_sha256':snapshot['sha256'],
            'checked_interval':{'start':start,'end':start+duration},'checked_crop':copy.deepcopy(crop)}


def require_review_check(verdict):
    if not _quality_passed(verdict):
        raise CandidateContractError('broll_quality_rejected',
            'Choose another video; the actual three-frame footage check did not pass.')


def bind_window(source,prepared,origin,source_in,duration,crop,original_verdict,prepared_verdict,
                original_snapshot,prepared_snapshot,*,media_reader=None):
    require_review_check(original_verdict);require_review_check(prepared_verdict)
    assert_snapshot(original_snapshot);assert_snapshot(prepared_snapshot)
    for verdict,snapshot,stage,start in ((original_verdict,original_snapshot,'original',origin+source_in),
                                         (prepared_verdict,prepared_snapshot,'prepared',source_in)):
        if (verdict.get('producer_stage')!=stage or verdict.get('checked_media_path')!=snapshot['path']
                or verdict.get('checked_media_sha256')!=snapshot['sha256']
                or abs(verdict.get('checked_interval',{}).get('start',-999)-start)>1e-7
                or abs(verdict.get('checked_interval',{}).get('end',-999)-(start+duration))>1e-7):
            raise CandidateContractError('broll_check_changed','Review this exact video interval again; its producer evidence does not match.')
    receipt=checked_window_receipt(source,prepared,prepared_origin_in_original=origin,
        prepared_source_in=source_in,active_duration=duration,crop=crop,
        verdict=prepared_verdict,media_reader=media_reader)
    assert_snapshot(original_snapshot);assert_snapshot(prepared_snapshot)
    if receipt['source_sha256']!=original_snapshot['sha256'] or receipt['prepared_sha256']!=prepared_snapshot['sha256']:
        raise CandidateContractError('broll_media_changed','Review this video again; its bytes changed during actual footage checking.')
    receipt.update(producer_version=1,original_verdict_sha256=digest(original_verdict),
                   prepared_verdict_sha256=digest(prepared_verdict))
    return receipt


def review_option_data(folder,slot,candidate,clip,data):
    receipt=slot.get('checked_window')
    if not isinstance(receipt,dict) or receipt.get('producer_version')!=1:
        raise CandidateContractError('broll_quality_unverified',
            'Finish the actual source and prepared-video checks before saving this option.')
    if receipt.get('candidate_id')!=candidate.id or data.get('id')!=candidate.id:
        raise CandidateContractError('broll_check_changed',
            'Keep this actual footage receipt attached to its own video candidate before saving it.')
    result=copy.deepcopy(data)
    result.update({key:copy.deepcopy(slot[key]) for key in
        ('source_in','source_duration','canvas_width','canvas_height','source_path','original_offset','checked_window')})
    result.update(path=slot['source_path'],clip=Path(clip).relative_to(folder).as_posix(),
                  review_note=slot['checks'][-1].get('reason','Locally checked video option'))
    return result


def finalize_candidate_bank(project_file,*,content_format=None,media_reader=None):
    """Write only the new typed manifest; never bless or rewrite old options."""
    from .candidate_manifest import _json_file,build_manifest
    from .candidate_selection import load_selections
    from .recovery import write_json
    from .settings import SHORT_FORM_LIMIT
    project_file=Path(project_file).resolve();project=_json_file(project_file)
    if content_format is None:
        profile=project.get('profile')
        profile_name=profile.get('name') if isinstance(profile,dict) else profile if isinstance(profile,str) else None
        content_format=project.get('content_format') or profile_name
    if content_format is None:
        content_format='short' if project['timeline']['duration']<=SHORT_FORM_LIMIT else 'long'
    owner_file=project_file.parent/'BROLL_OWNER_SELECTIONS.v1.json'
    manifest=build_manifest(project_file,content_format=content_format,media_reader=media_reader,
                            previous=load_selections(owner_file) if owner_file.is_file() else None)
    write_json(project_file.parent/'BROLL_CANDIDATES.v1.json',manifest)
    return manifest
