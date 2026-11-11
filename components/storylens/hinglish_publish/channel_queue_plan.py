"""Pure append proposals, never a scheduler or an upload authorization.

Contract v1 expects a normalized canonical-store snapshot: revision, verified
bindings, entries and request receipts. entries includes ALL retained short
reservations in the snapshot scope (not long-video jobs); each has kind='short',
id, destination, asset, release_at, local_date, status and optional remote/submission/reconciliation
evidence. Unknown execution states reserve their dates conservatively.

Each completed asset supplies asset_id/content_sha256, completed root_source
{id, sha256, state, duration_frames, timebase}, completed highlights
{id, version, state, source_id,
source_sha256}, mapping_version and ordered source_moments. Each moment has
source_id/source_sha256, integer [start_frame,end_frame) and rational seconds
per frame in timebase [numerator,denominator]. These are upstream attestations;
this module neither verifies files nor chooses highlights or shorts.

now is an injected aware datetime. slot_choices is either an injected callable
receiving explicit offered instants or a saved key->instant mapping. Persist
new_entries AND request_record atomically in the EXISTING canonical store before
execution. Replays use that receipt, not the chooser. No clock/random/I/O/model
or provider calls occur here. Counts other than selected_n count deliveries,
not media: N shorts across two destinations can have 2N deliveries.

Owner handoff: no existing Store/service/worker integration is supplied here.
The adapter must supply secret-free normalized metadata, attest actual account
and lineage verification, persist all new entries plus the request receipt and
exact choices in one transaction, and recheck these preconditions under that
transaction. Snapshot hashes are stale-state guards, not signatures or locks.
Do not commit a blocked/review proposal or infer execution permission from
commit_ready. Old remote receipts/statuses are observations, not verified by
this component. Clock/choice injection must be controlled by that adapter;
uncommitted choices can only be reused if the caller retains them. A committed
retry requires the durable request receipt and cannot reroll its minutes.

Actual local-agent source/highlights/short selection, canonical transactional
append, restart/worker behavior and remote scheduling receipts remain separate
acceptance gaps. In-memory fixtures cannot establish those workflows or an
absence of cloud dependencies elsewhere in Storylens.
Present ProposalError.code through the application's shared error helpers;
retain separate technical diagnostics without exposing credentials. No canonical
execution statuses are introduced here.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json


IST = timezone(timedelta(hours=5, minutes=30), 'Asia/Kolkata')
PROFILES = frozenset(('general', 'gaming', 'cricket'))
PLATFORMS = frozenset(('youtube', 'instagram'))


class ProposalError(ValueError):
    """Stable component code; the application adapter owns error presentation."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _error(code, message):
    raise ProposalError(code, message)


def _hash(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError):
        _error('invalid_snapshot', 'Supply plain, finite JSON metadata only.')
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in '0123456789abcdefABCDEF' for c in value))


def _integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _instant(value, code='invalid_snapshot'):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(IST)
    except (TypeError, ValueError, OverflowError):
        _error(code, 'Supply an exact release instant with its timezone offset.')


def _destination(raw):
    if (not isinstance(raw, dict) or raw.get('profile_id') not in PROFILES
            or raw.get('platform') not in PLATFORMS
            or not _text(raw.get('account_id'))
            or not _text(raw.get('connection_ref')) or raw.get('verified') is not True):
        _error('destination_unverified', 'Supply the explicitly verified profile, platform and stable account binding.')
    return {key: raw[key] for key in
            ('profile_id', 'platform', 'account_id', 'connection_ref', 'verified')}


def _partition(dest):
    return dest['profile_id'], dest['platform'], dest['account_id']


def _account(dest):
    return dest['platform'], dest['account_id']


def _asset(raw):
    code, message = 'lineage_unverified', 'Supply a completed short and completed source/highlights with its validated root-source remap.'
    try:
        root, highlights = raw['root_source'], raw['highlights']
        source_num, source_den = root['timebase']
        if (not _text(raw['asset_id']) or raw['state'] != 'complete'
                or not _sha(raw['content_sha256']) or root['state'] != 'complete'
                or not _text(root['id']) or not _sha(root['sha256'])
                or not _integer(root['duration_frames'], 1)
                or not _integer(source_num, 1) or not _integer(source_den, 1)
                or highlights['state'] != 'complete' or not _text(highlights['id'])
                or not _text(highlights['version'])
                or highlights['source_id'] != root['id']
                or highlights['source_sha256'].lower() != root['sha256'].lower()
                or not _text(raw['mapping_version'])
                or not isinstance(raw['source_moments'], list) or not raw['source_moments']):
            _error(code, message)
        moments = []
        for part in raw['source_moments']:
            numerator, denominator = part['timebase']
            if (part['source_id'] != root['id']
                    or part['source_sha256'].lower() != root['sha256'].lower()
                    or not _integer(part['start_frame'])
                    or not _integer(part['end_frame'], part['start_frame'] + 1)
                    or not _integer(numerator, 1) or not _integer(denominator, 1)):
                _error(code, message)
            if part['end_frame'] * Fraction(numerator, denominator) > root['duration_frames'] * Fraction(source_num, source_den):
                _error(code, message)
            moments.append(dict(source_id=root['id'], source_sha256=root['sha256'].lower(),
                                start_frame=part['start_frame'], end_frame=part['end_frame'],
                                timebase=[numerator, denominator]))
        return dict(asset_id=raw['asset_id'], state='complete',
                    content_sha256=raw['content_sha256'].lower(),
                    root_source=dict(id=root['id'], sha256=root['sha256'].lower(), state='complete',
                                     duration_frames=root['duration_frames'], timebase=[source_num, source_den]),
                    highlights=dict(id=highlights['id'], version=highlights['version'],
                                    state='complete', source_id=root['id'],
                                    source_sha256=root['sha256'].lower()),
                    mapping_version=raw['mapping_version'], source_moments=moments)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        if isinstance(error, ProposalError):
            raise
        _error(code, message)


def _moments(asset):
    result = []
    for part in asset['source_moments']:
        unit = Fraction(*part['timebase'])
        item = (part['source_sha256'], part['start_frame'] * unit, part['end_frame'] * unit)
        if result and result[-1][0] == item[0] and result[-1][2] == item[1]:
            result[-1] = (item[0], result[-1][1], item[2])
        else:
            result.append(item)
    return result


def _duplicate(left, right):
    if left['content_sha256'] == right['content_sha256']:
        return 'content_sha256'
    lm, rm = _moments(left), _moments(right)
    if lm == rm:
        return 'source_moments'
    if any(a[0] == b[0] and max(a[1], b[1]) < min(a[2], b[2]) for a in lm for b in rm):
        return 'potential_duplicate'
    return None


def _released(entry):
    proof = entry.get('reconciliation', {})
    return (entry.get('status') == 'cancelled' and isinstance(proof, dict)
            and proof.get('verified') is True and proof.get('reservation_released') is True
            and proof.get('remote_outcome') in ('absent', 'cancelled'))


def _action(entry, now):
    if entry['status'] in ('scheduled', 'published'):
        return 'preserve_remote'
    if (entry.get('remote') or entry.get('submission_started')
            or entry['status'] in ('submitting', 'uncertain', 'needs_review', 'cancelled')):
        return 'reconcile_remote'
    if _instant(entry['release_at']) <= now:
        return 'missed_slot_review'
    if entry['status'] == 'failed':
        return 'retry_existing_review'
    if entry['status'] not in ('draft', 'queued', 'ready'):
        return 'reconcile_remote'
    return 'preserve_existing'


def _snapshot(snapshot):
    if (not isinstance(snapshot, dict)
            or not (_integer(snapshot.get('revision')) or _text(snapshot.get('revision')))
            or any(not isinstance(snapshot.get(k), list) for k in ('bindings', 'entries', 'requests'))):
        _error('invalid_snapshot', 'Supply an explicit canonical snapshot revision, bindings, entries and request receipts.')
    _hash(snapshot)
    bindings = {}
    for raw in snapshot['bindings']:
        dest = _destination(raw)
        key = _partition(dest)
        if key in bindings:
            _error('invalid_snapshot', 'Resolve ambiguous profile/account bindings before planning.')
        bindings[key] = dest
    entries, ids, occupied = [], set(), set()
    for raw in snapshot['entries']:
        try:
            entry = deepcopy(raw)
            if (entry.get('kind') != 'short' or not _text(entry['id'])
                    or entry['id'] in ids or not _text(entry['status'])):
                raise ValueError()
            entry['destination'] = _destination(entry['destination'])
            entry['asset'] = _asset(entry['asset'])
            instant = _instant(entry['release_at'])
            if instant.date().isoformat() != entry['local_date']:
                raise ValueError()
            if not _released(entry):
                key = (*_account(entry['destination']), entry['local_date'])
                if key in occupied:
                    _error('snapshot_conflict', 'Existing destination-day reservations conflict; reconcile them before appending.')
                occupied.add(key)
            entries.append(entry)
            ids.add(entry['id'])
        except (KeyError, TypeError, ValueError):
            _error('invalid_snapshot', 'Normalize existing entries and their lineage before planning; nothing was replaced.')
    request_ids = [r.get('request_id') for r in snapshot['requests'] if isinstance(r, dict)]
    if (len(request_ids) != len(snapshot['requests']) or any(not _text(r) for r in request_ids)
            or len(set(request_ids)) != len(request_ids)):
        _error('invalid_snapshot', 'Supply unique durable request receipts.')
    return bindings, entries


def _policy(policy, dests):
    supported = dict(timezone='Asia/Kolkata', daily_cap=1, window_start='17:00',
                     window_end='21:00', start_rule='append_after_tail',
                     missed_slot_rule='review', overlap_rule='any_overlap_review', lead_minutes=2)
    if (not isinstance(policy, dict) or any(policy.get(k) != v for k, v in supported.items())
            or isinstance(policy.get('daily_cap'), bool) or isinstance(policy.get('lead_minutes'), bool)
            or set(policy) != set(supported) | {'start_date', 'authorized_destinations'}):
        _error('unsupported_policy', 'This proposal supports only the explicit one-per-day 17:00–21:00 Kolkata append policy with review for missed slots.')
    try:
        day = date.fromisoformat(policy['start_date'])
        allowed = policy['authorized_destinations']
        if not isinstance(allowed, list):
            raise ValueError()
        authorized = {(d['profile_id'], d['platform'], d['account_id']) for d in allowed}
    except (TypeError, KeyError, ValueError):
        _error('unsupported_policy', 'Supply an explicit start date and authorized destinations.')
    if any(_partition(d) not in authorized for d in dests):
        _error('destination_not_authorized', 'This destination is not explicitly authorized by the supplied request policy.')
    return day


def _preconditions(snapshot, dests, selection, intent):
    return dict(revision=snapshot['revision'], snapshot_sha256=_hash(snapshot),
                expected_bindings=deepcopy(dests), request_id=selection['request_id'],
                intent_sha256=intent, atomic_append_required=True,
                recheck=['snapshot_revision_and_hash', 'verified_account_bindings',
                         'source_and_highlights_identity', 'destination_day_occupancy',
                         'content_and_source_moment_duplicates', 'request_receipt'])


def _entry_spec(entry):
    """Immutable scheduling/media evidence; remote progress may change."""
    return _hash({k: entry.get(k) for k in ('id', 'kind', 'destination', 'asset',
                  'release_at', 'release_at_utc', 'local_date', 'timezone',
                  'request_id', 'batch_id')})


def _delivery(asset_id, destination, entry, reason):
    return dict(asset_id=asset_id, destination=deepcopy(destination),
                entry_id=entry['id'], entry_spec_sha256=_entry_spec(entry), reason=reason)


def _finish(proposal, selected_n):
    counts = dict(selected_n=selected_n, delivery_n=0, new_n=len(proposal['new_entries']),
                  already_present_n=len(proposal['existing_matches']), blocked_n=len(proposal['blocked']),
                  per_platform={})
    for collection, label in (('new_entries', 'new_n'), ('existing_matches', 'already_present_n'), ('blocked', 'blocked_n')):
        for item in proposal[collection]:
            platform = item['destination']['platform']
            bucket = counts['per_platform'].setdefault(platform, dict(new_n=0, already_present_n=0, blocked_n=0))
            bucket[label] += 1
            counts['delivery_n'] += 1
    proposal['counts'] = counts
    proposal['commit_ready'] = (not proposal['blocked'] and all(
        item['action'] in ('preserve_existing', 'preserve_remote') for item in proposal['existing_matches']))
    proposal['proposal_sha256'] = _hash(proposal)
    return proposal


def validate_preconditions(proposal, snapshot):
    """A pure stale/tamper check, not a lock, transaction or authorization."""
    unsigned = {k: v for k, v in proposal.items() if k != 'proposal_sha256'}
    if proposal.get('proposal_sha256') != _hash(unsigned):
        _error('invalid_proposal', 'The proposal changed after planning; create a new proposal.')
    expected = proposal.get('preconditions', {})
    if expected.get('revision') != snapshot.get('revision') or expected.get('snapshot_sha256') != _hash(snapshot):
        _error('stale_snapshot', 'The canonical queue changed; replan without overwriting existing entries.')
    return True


def propose_replenishment(snapshot, finished_candidates, selection, destination, policy, now, slot_choices):
    """Return new_entries, matches, blockers, exact choices and commit guards.

    Every result is non-executable. Any blocker/review makes commit_ready false.
    request_record is a proposed receipt, not something this function persists.
    The owning writer must append it atomically with all accepted new_entries.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        _error('clock_unverified', 'Supply the current aware time explicitly; no system clock is read here.')
    now = now.astimezone(IST)
    bindings, existing = _snapshot(snapshot)
    raw_dests = destination if isinstance(destination, list) else [destination]
    dests = [_destination(d) for d in raw_dests]
    if not dests or len({_partition(d) for d in dests}) != len(dests):
        _error('destination_unverified', 'Select each explicit destination only once.')
    # Two editorial profiles for one physical destination are not two deliveries.
    if len({_account(d) for d in dests}) != len(dests):
        _error('destination_unverified', 'Choose one editorial profile per actual destination in a request.')
    for dest in dests:
        if bindings.get(_partition(dest)) != dest:
            _error('account_binding_changed', 'The saved profile/account binding differs; verify it without retargeting old work.')
    first_day = _policy(policy, dests)
    if not isinstance(selection, dict):
        _error('selection_mismatch', 'Supply the exact user-selected short IDs and count.')
    ids, count = selection.get('selected_short_ids'), selection.get('requested_n')
    if (not isinstance(ids, list) or not _integer(count, 1) or count > 1000
            or len(ids) != count or any(not _text(i) for i in ids) or len(set(ids)) != count
            or not _text(selection.get('request_id')) or not _text(selection.get('batch_id'))):
        _error('selection_mismatch', 'Supply 1–1000 unique user-selected short IDs matching requested_n, with durable request and batch IDs.')
    if not isinstance(finished_candidates, list):
        _error('selection_missing', 'Supply the completed candidate manifests for the selected shorts.')
    candidates = {}
    for candidate in finished_candidates:
        if not isinstance(candidate, dict) or not _text(candidate.get('asset_id')) or candidate['asset_id'] in candidates:
            _error('selection_missing', 'Candidate IDs must be explicit and unique.')
        candidates[candidate['asset_id']] = candidate
    if any(i not in candidates for i in ids):
        _error('selection_missing', 'One or more exact user-selected shorts is absent; no replacement was selected.')
    fields = ('asset_id', 'state', 'content_sha256', 'root_source', 'highlights', 'mapping_version', 'source_moments')
    intent = _hash(dict(selection=selection, destinations=dests, policy=policy,
                        assets=[{k: candidates[i].get(k) for k in fields} for i in ids]))
    proposal_id = _hash(['channel-queue-proposal-v1', intent])
    proposal = dict(version=1, proposal_id=proposal_id, execution_authorized=False,
                    preconditions=_preconditions(snapshot, dests, selection, intent),
                    new_entries=[], existing_matches=[], blocked=[], slot_choices={})
    records = [r for r in snapshot['requests'] if r['request_id'] == selection['request_id']]
    if records:
        record = records[0]
        if record.get('intent_sha256') != intent or record.get('proposal_id') != proposal_id:
            _error('request_changed', 'This request ID already refers to different inputs, selections or policy; preserve its receipt.')
        by_id = {e['id']: e for e in existing}
        try:
            deliveries = record['deliveries']
            if not isinstance(deliveries, list):
                raise KeyError()
            for delivery in deliveries:
                entry = by_id[delivery['entry_id']]
                if (_account(entry['destination']) != _account(delivery['destination'])
                        or delivery['entry_spec_sha256'] != _entry_spec(entry)):
                    raise KeyError()
                proposal['existing_matches'].append(dict(
                    asset_id=delivery['asset_id'], destination=deepcopy(delivery['destination']),
                    reason='request_replay', origin='snapshot', entry=deepcopy(entry),
                    action=_action(entry, now)))
            proposal['blocked'] = deepcopy(record['blocked'])
            proposal['slot_choices'] = deepcopy(record['slot_choices'])
            proposal['request_record'] = deepcopy(record)
            if len(deliveries) + len(proposal['blocked']) != count * len(dests):
                raise KeyError()
            pairs = [(d['asset_id'], _partition(d['destination']))
                     for d in deliveries + proposal['blocked']]
            expected = {(i, _partition(d)) for i in ids for d in dests}
            if set(pairs) != expected or len(set(pairs)) != len(pairs):
                raise KeyError()
        except (KeyError, TypeError):
            _error('request_receipt_incomplete', 'The saved request references missing or changed entries; reconcile it rather than creating replacements.')
        return _finish(proposal, count)
    if any(r.get('batch_id') == selection['batch_id'] for r in snapshot['requests']):
        _error('batch_already_present', 'This batch already has a durable request; reuse that request instead of creating another.')
    if first_day < now.date():
        _error('start_date_expired', 'The requested start date has passed. Review a new future start date; no catch-up jobs were proposed.')

    # Preserve evidence across accounts for original-source and parent identity.
    roots, highlights, assets = {}, {}, {}
    for entry in existing:
        a = entry['asset']
        roots.setdefault(a['root_source']['id'], set()).add(a['root_source']['sha256'])
        h = a['highlights']
        highlights.setdefault(h['id'], set()).add((h['version'], h['source_id'], h['source_sha256']))
        assets.setdefault(a['asset_id'], set()).add(_hash(a))
    normalized, errors = {}, {}
    for asset_id in ids:
        try:
            a = _asset(candidates[asset_id])
            root, h = a['root_source'], a['highlights']
            if root['id'] in roots and roots[root['id']] != {root['sha256']}:
                _error('source_changed', 'The original source identity changed; reconcile its lineage before appending.')
            identity = (h['version'], h['source_id'], h['source_sha256'])
            if h['id'] in highlights and highlights[h['id']] != {identity}:
                _error('highlights_changed', 'The completed highlights parent/version changed; review the new lineage first.')
            if asset_id in assets and assets[asset_id] != {_hash(a)}:
                _error('asset_changed', 'This saved short ID now identifies different media or lineage; review it first.')
            roots.setdefault(root['id'], set()).add(root['sha256'])
            highlights.setdefault(h['id'], set()).add(identity)
            normalized[asset_id] = a
        except ProposalError as error:
            errors[asset_id] = dict(code=error.code, message=str(error))

    deliveries = []
    for dest in dests:
        account = _account(dest)
        reserved = [e for e in existing if _account(e['destination']) == account and not _released(e)]
        day = max([first_day] + [date.fromisoformat(e['local_date']) + timedelta(days=1) for e in reserved])
        previous = max(reserved, key=lambda e: _instant(e['release_at']), default=None)
        pool = [(e, 'snapshot') for e in existing if _account(e['destination']) == account]
        index = 0
        for asset_id in ids:
            def block(code, message, **evidence):
                proposal['blocked'].append(dict(asset_id=asset_id, destination=deepcopy(dest),
                                                code=code, message=message, **evidence))
            if asset_id in errors:
                block(**errors[asset_id])
                continue
            a = normalized[asset_id]
            found = [(e, origin, _duplicate(a, e['asset'])) for e, origin in pool]
            exact = next(((e, origin, reason) for e, origin, reason in found
                          if reason in ('content_sha256', 'source_moments')), None)
            if exact:
                e, origin, reason = exact
                if _released(e):
                    block('cancelled_requires_explicit_retry', 'The previous delivery was reconciled as cancelled; an explicit retry authorization is required.', entry_id=e['id'])
                    continue
                action = 'preserve_existing' if origin == 'proposal' else _action(e, now)
                proposal['existing_matches'].append(dict(asset_id=asset_id, destination=deepcopy(dest),
                                                         reason=reason, origin=origin, entry=deepcopy(e), action=action))
                deliveries.append(_delivery(asset_id, dest, e, reason))
                continue
            overlaps = [e['id'] for e, _, reason in found if reason == 'potential_duplicate']
            if overlaps:
                block('potential_duplicate', 'These root-source moments overlap an existing delivery; review them without choosing replacements.', entry_ids=overlaps)
                continue
            while True:
                first = datetime.combine(day, datetime.min.time(), IST).replace(hour=17)
                last = first.replace(hour=21)
                earliest = max(first, now + timedelta(minutes=2))
                if earliest.second or earliest.microsecond:
                    earliest = earliest.replace(second=0, microsecond=0) + timedelta(minutes=1)
                if earliest <= last:
                    break
                day += timedelta(days=1)
            options = [earliest + timedelta(minutes=m) for m in range(int((last-earliest).total_seconds() // 60) + 1)]
            if previous and date.fromisoformat(previous['local_date']) == day - timedelta(days=1):
                clock = _instant(previous['release_at']).time()
                varied = [instant for instant in options if instant.time() != clock]
                options = varied or options
            key = _hash([proposal_id, _partition(dest), asset_id, day.isoformat()])
            offered = tuple(instant.isoformat() for instant in options)
            context = dict(key=key, index=index, destination=deepcopy(dest), local_date=day.isoformat(),
                           options=offered)
            if callable(slot_choices):
                chosen = slot_choices(context)
            elif isinstance(slot_choices, dict) and key in slot_choices:
                chosen = slot_choices[key]
            else:
                _error('slot_choice_required', 'Supply the saved minute or an explicit injected choice for each new destination-day.')
            if chosen not in offered:
                _error('slot_choice_invalid', 'The chosen minute is not an offered future instant in the authorized window.')
            instant = _instant(chosen, 'slot_choice_invalid')
            entry = dict(id=_hash([proposal_id, _partition(dest), asset_id])[:32], kind='short',
                         request_id=selection['request_id'], batch_id=selection['batch_id'],
                         destination=deepcopy(dest), asset=deepcopy(a), timezone='Asia/Kolkata',
                         local_date=day.isoformat(), release_at=chosen,
                         release_at_utc=instant.astimezone(timezone.utc).isoformat())
            proposal['new_entries'].append(entry)
            proposal['slot_choices'][key] = chosen
            deliveries.append(_delivery(asset_id, dest, entry, 'created'))
            pool.append((entry, 'proposal'))
            previous = entry
            day += timedelta(days=1)
            index += 1
    proposal['request_record'] = dict(request_id=selection['request_id'], batch_id=selection['batch_id'],
                                    intent_sha256=intent, proposal_id=proposal_id,
                                    deliveries=deliveries, blocked=deepcopy(proposal['blocked']),
                                    slot_choices=deepcopy(proposal['slot_choices']))
    return _finish(proposal, count)
