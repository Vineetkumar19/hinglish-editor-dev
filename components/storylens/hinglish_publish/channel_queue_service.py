"""Internal finished-output gate for explicit paired-channel DRAFT proposals.

Not an HTTP API, selection/model planner, account grant or publishing worker.
The existing preparation service must supply completed source/highlight remap
attestations; this adapter verifies the actual local short bytes and metadata.
It cannot certify highlight semantics or upstream lineage from metadata alone.
"""
from pathlib import Path

from hinglish_niche.profiles import account_key,valid_profile
from . import channel_queue_plan as qp,metadata
from .store import fingerprint


def destinations(publisher,profile,pair):
    valid_profile(profile)
    if (not isinstance(pair,dict) or set(pair)!= {'youtube','instagram'}
            or any(not isinstance(v,str) or not v.strip() for v in pair.values())):
        qp._error('needs_account_selection','Choose both the YouTube and Instagram account for this profile before preparing its queue.')
    current=publisher.accounts(profile)
    result=[]
    for platform,account in pair.items():
        observed=current.get(platform,{})
        if not observed.get('connected') or not observed.get('id'):
            qp._error('needs_account_selection','Connect and explicitly select both accounts for this profile; no other active account was substituted.')
        if observed['id']!=account:
            qp._error('account_binding_changed','The selected channel account changed. Review the saved pair; existing queue items were kept.')
        result.append(dict(profile_id=profile,platform=platform,account_id=account,
                           connection_ref=account_key(platform,profile),verified=True))
    return result


def checked_media(publisher,candidates,selection,media):
    if not isinstance(media,dict) or not isinstance(candidates,list) or not isinstance(selection,dict):
        qp._error('media_identity_changed','Choose completed, verified local shorts before preparing their queue.')
    by_id={a.get('asset_id'):a for a in candidates if isinstance(a,dict)}
    selected=selection.get('selected_short_ids')
    if not isinstance(selected,list):
        qp._error('selection_missing','Choose the exact finished shorts and count first.')
    for key in selected:
        try:
            asset=qp._asset(by_id[key]);item=media[key];path=Path(item['video']).resolve(strict=True)
            if (not path.is_relative_to(publisher.root/'output') or not path.is_file()
                    or path.suffix.lower()!='.mp4' or item.get('verified') is not True
                    or qp._asset(item['asset'])!=asset
                    or item.get('content_sha256')!=asset['content_sha256']
                    or fingerprint(path)!=asset['content_sha256']):
                raise ValueError()
            for platform in ('youtube','instagram'):metadata.validate(item['metadata'][platform])
        except (KeyError,TypeError,ValueError,OSError):
            qp._error('media_identity_changed','A finished short, its metadata or its source mapping changed. Reopen that exact prepared output; nothing was queued.')


def propose(publisher,*,profile,pair,finished_candidates,selection,policy,media,now,
            slot_choices,existing_lineage=None):
    bindings=destinations(publisher,profile,pair)
    checked_media(publisher,finished_candidates,selection,media)
    snapshot=publisher.store.proposal_snapshot(bindings,existing_lineage=existing_lineage)
    return qp.propose_replenishment(snapshot,finished_candidates,selection,bindings,policy,now,slot_choices)


def commit(publisher,proposal,*,profile,pair,finished_candidates,selection,policy,media,now,
           existing_lineage=None):
    bindings=destinations(publisher,profile,pair)
    checked_media(publisher,finished_candidates,selection,media)
    return publisher.store.apply_proposal(proposal,bindings=bindings,finished_candidates=finished_candidates,
        selection=selection,destinations=bindings,policy=policy,now=now,media=media,existing_lineage=existing_lineage)


def check_authorization_binding(job,accounts):
    """New bound proposals keep their destination; legacy jobs retain their path."""
    if not job.get('queue_proposal_id') and not job.get('destination'):return
    dest=job.get('destination',{})
    profile=job.get('profile','general');platform=job.get('platform')
    current=accounts.get(platform,{})
    if (dest.get('profile_id')!=profile or dest.get('platform')!=platform
            or dest.get('account_id')!=job.get('account_id')
            or dest.get('connection_ref')!=job.get('connection_ref')
            or dest.get('connection_ref')!=account_key(platform,profile)
            or not current.get('connected') or current.get('id')!=dest.get('account_id')):
        qp._error('account_binding_changed','This draft belongs to a different saved channel account. Reconnect that account or prepare a new reviewed pair; it was not retargeted.')

