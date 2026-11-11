"""Synthetic, in-memory proposal checks; not local-agent/publishing acceptance."""
import copy
from datetime import datetime
import unittest
from unittest.mock import patch

from hinglish_publish.channel_queue_plan import (
    ProposalError, propose_replenishment, validate_preconditions,
)


def destination(profile='gaming', account='channel-a', platform='youtube'):
    return dict(profile_id=profile, platform=platform, account_id=account,
                connection_ref='synthetic-connection-' + account, verified=True)


def asset(index, *, source='root-a', sha=None, start=None):
    root_hash = ('a' if source == 'root-a' else 'b') * 64
    start = index * 100 if start is None else start
    return dict(asset_id='short-' + str(index), state='complete',
                content_sha256=sha or format(index + 1, '064x'),
                root_source=dict(id=source, sha256=root_hash, state='complete',
                                 duration_frames=270000, timebase=[1, 25]),
                highlights=dict(id='highlights-' + source, version='v1',
                                state='complete', source_id=source,
                                source_sha256=root_hash), mapping_version='map-v1',
                source_moments=[dict(source_id=source, source_sha256=root_hash,
                                     start_frame=start, end_frame=start + 50,
                                     timebase=[1, 25])])


def snapshot(*destinations):
    return dict(revision=0, bindings=list(destinations or (destination(),)),
                entries=[], requests=[])


def policy(*destinations, day='2026-10-26'):
    return dict(timezone='Asia/Kolkata', daily_cap=1, window_start='17:00',
                window_end='21:00', start_date=day, start_rule='append_after_tail',
                missed_slot_rule='review', overlap_rule='any_overlap_review',
                lead_minutes=2, authorized_destinations=[
                    {k: d[k] for k in ('profile_id', 'platform', 'account_id')}
                    for d in (destinations or (destination(),))])


def selection(*ids, request='request-1', batch=None):
    return dict(request_id=request, batch_id=batch or ('week-1' if request == 'request-1' else 'batch-' + request),
                requested_n=len(ids), selected_short_ids=list(ids))


NOW = datetime.fromisoformat('2026-10-25T12:00:00+05:30')


def choose(context):
    clock = '17:' + str(10 + context['index']).zfill(2)
    return next((instant for instant in context['options'] if instant[11:16] == clock),
                context['options'][0])


def propose(snap=None, candidates=None, selected=None, destinations=None,
            rules=None, now=NOW, chooser=choose):
    dests = destinations or [destination()]
    return propose_replenishment(
        snap if snap is not None else snapshot(*dests),
        candidates if candidates is not None else [asset(0), asset(1), asset(2)],
        selected if selected is not None else selection('short-0', 'short-1', 'short-2'),
        dests, rules if rules is not None else policy(*dests), now, chooser)


def committed(snap, proposal):
    """Test-only canonical-writer simulation, never Store or a real queue."""
    result = copy.deepcopy(snap)
    result['revision'] += 1
    for entry in proposal['new_entries']:
        result['entries'].append({**copy.deepcopy(entry), 'status': 'draft', 'remote': {}})
    result['requests'].append(copy.deepcopy(proposal['request_record']))
    return result


def golden_week_proposals():
    """Reconstruct both full synthetic golden proposals without disk or services."""
    first = propose()
    old = committed(snapshot(), first)
    old['entries'][0].update(status='scheduled', remote={'id': 'synthetic-remote-1',
                                                       'receipt': 'preserve-exactly'})
    unchanged = copy.deepcopy(old)
    second = propose(old, [asset(3), asset(4)],
                     selection('short-3', 'short-4', request='request-2', batch='week-2'),
                     rules=policy(day='2026-11-02'),
                     now=datetime.fromisoformat('2026-11-01T12:00:00+05:30'))
    if old != unchanged:
        raise AssertionError('Weekly append changed the earlier canonical snapshot')
    return first, old, second


class QueueProposalTests(unittest.TestCase):
    def assert_code(self, code, action):
        with self.assertRaises(ProposalError) as caught:
            action()
        self.assertEqual(code, caught.exception.code)

    def test_golden_week_one_then_week_two_preserves_receipts(self):
        first, old, second = golden_week_proposals()
        self.assertEqual('a63548fdc10800ca7da3ccdb3641dcf12853da2ee4193c7aab21271d94c7fe66',
                         first['proposal_sha256'])
        self.assertEqual('92cb0989db7c187a8bb09844d6c1254c24cd05d68b5c9d071805ffa75a3f9a4a',
                         second['proposal_sha256'])
        self.assertEqual(['2026-10-26T17:10:00+05:30',
                          '2026-10-27T17:11:00+05:30',
                          '2026-10-28T17:12:00+05:30'],
                         [e['release_at'] for e in first['new_entries']])
        self.assertEqual('2026-10-26T11:40:00+00:00', first['new_entries'][0]['release_at_utc'])
        frozen = copy.deepcopy(old)
        self.assertEqual(['2026-11-02T17:10:00+05:30', '2026-11-03T17:11:00+05:30'],
                         [e['release_at'] for e in second['new_entries']])
        self.assertEqual(frozen, old)
        combined = committed(old, second)
        self.assertEqual(frozen['entries'], combined['entries'][:3])
        self.assertEqual(5, len(combined['entries']))
        self.assertFalse(second['execution_authorized'])
        self.assertTrue(second['commit_ready'])

    def test_replay_uses_saved_ids_minutes_without_chooser_even_when_expired(self):
        first = propose()
        saved = committed(snapshot(), first)
        result = propose(saved, now=datetime.fromisoformat('2026-12-01T10:00:00+05:30'),
                         chooser=lambda _: self.fail('Replay must not reroll'))
        self.assertEqual([], result['new_entries'])
        self.assertEqual(3, result['counts']['already_present_n'])
        self.assertEqual(first['proposal_id'], result['proposal_id'])
        self.assertEqual([e['id'] for e in first['new_entries']],
                         [e['entry']['id'] for e in result['existing_matches']])
        self.assertTrue(all(a['action'] == 'missed_slot_review' for a in result['existing_matches']))

    def test_changed_request_source_selection_policy_or_binding_is_blocked(self):
        saved = committed(snapshot(), propose())
        altered = [asset(0), asset(1), asset(2)]
        altered[0]['content_sha256'] = 'f' * 64
        self.assert_code('request_changed', lambda: propose(saved, altered))
        self.assert_code('request_changed', lambda: propose(saved, selected=selection('short-2', 'short-1', 'short-0')))
        self.assert_code('request_changed', lambda: propose(saved, rules=policy(day='2026-10-27')))
        changed = destination(account='channel-b')
        self.assert_code('account_binding_changed', lambda: propose(saved, destinations=[changed]))

    def test_exact_n_and_explicit_user_order(self):
        s = selection('short-2', 'short-0')
        result = propose(selected=s)
        self.assertEqual(['short-2', 'short-0'], [e['asset']['asset_id'] for e in result['new_entries']])
        self.assertEqual(2, result['counts']['selected_n'])
        s['requested_n'] = 3
        self.assert_code('selection_mismatch', lambda: propose(selected=s))
        self.assert_code('selection_mismatch', lambda: propose(selected=selection('short-0', 'short-0')))
        self.assert_code('selection_missing', lambda: propose(selected=selection('unknown')))

    def test_two_platforms_do_not_double_selected_media_count(self):
        ds = [destination(), destination(platform='instagram', account='ig-a')]
        result = propose(destinations=ds)
        self.assertEqual(3, result['counts']['selected_n'])
        self.assertEqual(6, result['counts']['new_n'])
        self.assertEqual(3, result['counts']['per_platform']['instagram']['new_n'])
        self.assertEqual(6, len({e['id'] for e in result['new_entries']}))

    def test_other_actual_accounts_have_independent_tails(self):
        a, b = destination(), destination(account='channel-b')
        saved = committed(snapshot(a, b), propose(snapshot(a, b)))
        result = propose(saved, [asset(3)], selection('short-3', request='b'), [b])
        self.assertEqual('2026-10-26', result['new_entries'][0]['local_date'])

    def test_two_profiles_same_actual_account_share_occupancy_and_dedup(self):
        a, b = destination(), destination(profile='cricket')
        saved = committed(snapshot(a, b), propose(snapshot(a, b)))
        result = propose(saved, [asset(3)], selection('short-3', request='b'), [b])
        self.assertEqual('2026-10-29', result['new_entries'][0]['local_date'])
        duplicate = propose(saved, [asset(0)], selection('short-0', request='c'), [b])
        self.assertEqual([], duplicate['new_entries'])
        self.assertEqual('content_sha256', duplicate['existing_matches'][0]['reason'])

    def test_hash_dedup_ignores_asset_filename_and_path(self):
        saved = committed(snapshot(), propose())
        renamed = asset(99, sha=asset(0)['content_sha256'])
        renamed['path'] = 'never-open-this-file.mp4'
        result = propose(saved, [renamed], selection('short-99', request='new'))
        self.assertEqual(1, result['counts']['already_present_n'])
        self.assertEqual([], result['new_entries'])

    def test_root_moment_dedup_after_reencode_and_equivalent_timebase(self):
        saved = committed(snapshot(), propose())
        recoded = asset(99, start=0)
        recoded['source_moments'][0].update(end_frame=100, timebase=[1, 50])
        result = propose(saved, [recoded], selection('short-99', request='recoded'))
        self.assertEqual('source_moments', result['existing_matches'][0]['reason'])

    def test_split_contiguous_remap_is_exact_same_moment(self):
        saved = committed(snapshot(), propose())
        recoded = asset(99, start=0)
        moment = recoded['source_moments'][0]
        recoded['source_moments'] = [{**moment, 'end_frame': 20}, {**moment, 'start_frame': 20}]
        result = propose(saved, [recoded], selection('short-99', request='split'))
        self.assertEqual(1, result['counts']['already_present_n'])

    def test_overlap_requires_review_and_never_selects_replacement(self):
        saved = committed(snapshot(), propose())
        result = propose(saved, [asset(99, start=25)], selection('short-99', request='overlap'))
        self.assertEqual('potential_duplicate', result['blocked'][0]['code'])
        self.assertEqual([], result['new_entries'])
        self.assertFalse(result['commit_ready'])
        different_root = propose(saved, [asset(99, source='root-b', start=25)],
                                 selection('short-99', request='other-root'))
        self.assertEqual(1, len(different_root['new_entries']))

    def test_duplicate_inside_current_selection_matches_proposal_not_second_entry(self):
        duplicate = asset(99, sha=asset(0)['content_sha256'])
        result = propose(candidates=[asset(0), duplicate], selected=selection('short-0', 'short-99'))
        self.assertEqual(1, len(result['new_entries']))
        self.assertEqual(1, len(result['existing_matches']))
        self.assertEqual('proposal', result['existing_matches'][0]['origin'])

    def test_changed_original_source_or_highlights_identity_is_not_silently_retargeted(self):
        saved = committed(snapshot(), propose())
        changed = asset(3)
        changed['root_source']['sha256'] = 'c' * 64
        changed['highlights']['source_sha256'] = 'c' * 64
        changed['source_moments'][0]['source_sha256'] = 'c' * 64
        result = propose(saved, [changed], selection('short-3', request='source-change'))
        self.assertEqual('source_changed', result['blocked'][0]['code'])
        changed = asset(3)
        changed['highlights']['version'] = 'v2'
        result = propose(saved, [changed], selection('short-3', request='highlight-change'))
        self.assertEqual('highlights_changed', result['blocked'][0]['code'])

    def test_unfinished_source_highlights_missing_or_invalid_lineage_blocks(self):
        for mutation in ('source', 'highlight', 'map', 'moment', 'root'):
            candidate = asset(0)
            if mutation == 'source': candidate['root_source']['state'] = 'running'
            if mutation == 'highlight': candidate['highlights']['state'] = 'running'
            if mutation == 'map': candidate.pop('mapping_version')
            if mutation == 'moment': candidate['source_moments'][0]['end_frame'] = 0
            if mutation == 'root': candidate['source_moments'][0]['source_id'] = 'wrong'
            result = propose(candidates=[candidate], selected=selection('short-0'))
            self.assertEqual('lineage_unverified', result['blocked'][0]['code'], mutation)
            self.assertEqual([], result['new_entries'])

    def test_stable_verified_explicit_authorized_binding_required(self):
        for field, value in [('account_id', ''), ('verified', False), ('connection_ref', '')]:
            d = destination(); d[field] = value
            self.assert_code('destination_unverified', lambda: propose(destinations=[d]))
        p = policy(); p['authorized_destinations'] = []
        self.assert_code('destination_not_authorized', lambda: propose(rules=p))
        self.assert_code('account_binding_changed', lambda: propose(snapshot(destination()), destinations=[destination(account='b')]))

    def test_one_per_day_window_endpoints_and_ceil_lead(self):
        one = [asset(0)]; selected = selection('short-0')
        p = policy(day='2026-10-25')
        exact = propose(candidates=one, selected=selected, rules=p,
                        now=datetime.fromisoformat('2026-10-25T16:58:00+05:30'),
                        chooser=lambda c: c['options'][0])
        self.assertEqual('2026-10-25T17:00:00+05:30', exact['new_entries'][0]['release_at'])
        seconds = propose(candidates=one, selected=selected, rules=p,
                          now=datetime.fromisoformat('2026-10-25T20:58:00.000001+05:30'),
                          chooser=lambda c: c['options'][0])
        self.assertEqual('2026-10-26T17:00:00+05:30', seconds['new_entries'][0]['release_at'])
        last = propose(candidates=one, selected=selected, rules=p,
                       now=datetime.fromisoformat('2026-10-25T20:58:00+05:30'),
                       chooser=lambda c: c['options'][-1])
        self.assertEqual('2026-10-25T21:00:00+05:30', last['new_entries'][0]['release_at'])

    def test_choice_must_be_offered_no_naive_clock_or_expired_new_policy(self):
        self.assert_code('slot_choice_invalid', lambda: propose(chooser=lambda _: '2026-10-26T16:00:00+05:30'))
        self.assert_code('clock_unverified', lambda: propose(now=datetime(2026, 10, 25)))
        self.assert_code('start_date_expired', lambda: propose(rules=policy(day='2026-10-24')))
        self.assert_code('slot_choice_required', lambda: propose(chooser={}))

    def test_adjacent_minutes_vary_and_choices_are_explicitly_recorded(self):
        result = propose(chooser=lambda c: c['options'][0])
        self.assertEqual(['17:00', '17:01', '17:00'],
                         [e['release_at'][11:16] for e in result['new_entries']])
        choices = result['slot_choices']
        self.assertEqual(3, len(choices))
        again = propose(chooser=choices)
        self.assertEqual(result, again)

    def test_unknown_submissions_and_cancelled_unreconciled_never_resubmit(self):
        first = propose()
        for status in ('submitting', 'uncertain', 'needs_review', 'cancelled', 'failed'):
            saved = committed(snapshot(), first)
            saved['entries'][0].update(status=status, submission_started=True)
            result = propose(saved, [asset(0), asset(3)],
                             selection('short-0', 'short-3', request=status))
            match = result['existing_matches'][0]
            self.assertEqual('reconcile_remote', match['action'])
            self.assertEqual('2026-10-29', result['new_entries'][0]['local_date'])
            self.assertEqual(1, len(result['new_entries']))

    def test_reconciled_cancel_releases_occupancy_but_not_retry_authorization(self):
        saved = committed(snapshot(), propose(candidates=[asset(0)], selected=selection('short-0')))
        saved['entries'][0].update(status='cancelled', reconciliation=dict(
            verified=True, reservation_released=True, remote_outcome='cancelled'))
        result = propose(saved, [asset(0), asset(3)],
                         selection('short-0', 'short-3', request='cancel'))
        self.assertEqual('cancelled_requires_explicit_retry', result['blocked'][0]['code'])
        self.assertEqual('2026-10-26', result['new_entries'][0]['local_date'])
        self.assertFalse(result['commit_ready'])

    def test_remote_receipt_preserved_and_reconciled_before_any_retry(self):
        saved = committed(snapshot(), propose())
        saved['entries'][0].update(status='failed', remote={'id': 'synthetic-remote'})
        result = propose(saved, [asset(0)], selection('short-0', request='receipt'))
        self.assertEqual('reconcile_remote', result['existing_matches'][0]['action'])
        self.assertEqual({'id': 'synthetic-remote'}, result['existing_matches'][0]['entry']['remote'])

    def test_snapshot_precondition_detects_same_revision_mutation_and_competitors(self):
        snap = snapshot()
        first = propose(snap)
        second = propose(snap, [asset(3)], selection('short-3', request='competing'))
        self.assertNotEqual(first['proposal_id'], second['proposal_id'])
        self.assertTrue(validate_preconditions(first, snap))
        self.assert_code('stale_snapshot', lambda: validate_preconditions(second, committed(snap, first)))
        changed = copy.deepcopy(snap); changed['bindings'][0]['connection_ref'] = 'different'
        self.assert_code('stale_snapshot', lambda: validate_preconditions(first, changed))

    def test_replay_missing_saved_entry_is_not_replaced(self):
        saved = committed(snapshot(), propose())
        saved['entries'].pop()
        self.assert_code('request_receipt_incomplete', lambda: propose(saved))

    def test_replay_detects_changed_entry_media_schedule_or_editorial_binding(self):
        first = propose()
        for mutation in ('media', 'schedule', 'binding'):
            saved = committed(snapshot(), first)
            entry = saved['entries'][0]
            if mutation == 'media': entry['asset']['content_sha256'] = 'f' * 64
            if mutation == 'schedule': entry['release_at'] = '2026-10-26T18:00:00+05:30'
            if mutation == 'binding': entry['destination']['connection_ref'] = 'reconnected'
            self.assert_code('request_receipt_incomplete', lambda: propose(saved))

    def test_receipt_delivery_count_cannot_hide_repeated_or_missing_selection(self):
        saved = committed(snapshot(), propose())
        saved['requests'][0]['deliveries'][1] = copy.deepcopy(saved['requests'][0]['deliveries'][0])
        self.assert_code('request_receipt_incomplete', lambda: propose(saved))

    def test_late_day_no_catchup_and_utc_clock_uses_kolkata_calendar(self):
        result = propose(candidates=[asset(0)], selected=selection('short-0'),
                         rules=policy(day='2026-10-26'),
                         now=datetime.fromisoformat('2026-10-25T23:00:00+00:00'))
        self.assertEqual('2026-10-26', result['new_entries'][0]['local_date'])
        result = propose(candidates=[asset(0)], selected=selection('short-0'),
                         rules=policy(day='2026-10-25'),
                         now=datetime.fromisoformat('2026-10-25T23:59:00+05:30'))
        self.assertEqual('2026-10-26', result['new_entries'][0]['local_date'])

    def test_missed_known_unsubmitted_differs_from_uncertain_no_new_upload(self):
        saved = committed(snapshot(), propose())
        saved['entries'][0].update(status='failed', submission_started=False)
        result = propose(saved, now=datetime.fromisoformat('2026-12-01T12:00:00+05:30'))
        self.assertEqual('missed_slot_review', result['existing_matches'][0]['action'])
        self.assertFalse(result['commit_ready'])
        self.assertEqual([], result['new_entries'])

    def test_unreconciled_cancel_and_unknown_state_reserve_last_day(self):
        first = propose(candidates=[asset(0)], selected=selection('short-0'))
        for status in ('cancelled', 'future-state-not-yet-mapped'):
            saved = committed(snapshot(), first)
            saved['entries'][0]['status'] = status
            result = propose(saved, [asset(3)], selection('short-3', request=status))
            self.assertEqual('2026-10-27', result['new_entries'][0]['local_date'])

    def test_proposal_tamper_and_duplicate_snapshot_day_are_rejected(self):
        result = propose()
        result['new_entries'][0]['release_at'] = '2026-10-26T19:00:00+05:30'
        self.assert_code('invalid_proposal', lambda: validate_preconditions(result, snapshot()))
        saved = committed(snapshot(), propose())
        saved['entries'][1]['release_at'] = saved['entries'][0]['release_at']
        saved['entries'][1]['local_date'] = saved['entries'][0]['local_date']
        self.assert_code('invalid_snapshot', lambda: propose(saved))

    def test_an_existing_batch_requires_its_original_request(self):
        saved = committed(snapshot(), propose())
        self.assert_code('batch_already_present', lambda: propose(
            saved, [asset(3)], selection('short-3', request='new-key', batch='week-1')))

    def test_no_io_network_store_workers_clock_or_input_mutation(self):
        snap, candidates, selected, ds, rules = snapshot(), [asset(0)], selection('short-0'), [destination()], policy()
        before = copy.deepcopy((snap, candidates, selected, ds, rules))
        with patch('builtins.open', side_effect=AssertionError('file I/O forbidden')), \
             patch('sqlite3.connect', side_effect=AssertionError('DB forbidden')), \
             patch('socket.socket', side_effect=AssertionError('network forbidden')), \
             patch('subprocess.Popen', side_effect=AssertionError('process forbidden')):
            result = propose(snap, candidates, selected, ds, rules)
        self.assertEqual(before, (snap, candidates, selected, ds, rules))
        self.assertTrue(result['preconditions']['atomic_append_required'])

    def test_unsupported_policies_fail_instead_of_discarding_user_instructions(self):
        for key, value in [('window_start', '16:00'), ('daily_cap', 2),
                           ('missed_slot_rule', 'publish_now'), ('timezone', 'UTC')]:
            rules = policy(); rules[key] = value
            self.assert_code('unsupported_policy', lambda: propose(rules=rules))

    def test_root_bounds_and_source_clock_are_required_not_just_positive_intervals(self):
        for mutation in ('past_end', 'missing_clock', 'zero_clock'):
            candidate = asset(0)
            if mutation == 'past_end': candidate['source_moments'][0]['end_frame'] = 270001
            if mutation == 'missing_clock': candidate['root_source'].pop('timebase')
            if mutation == 'zero_clock': candidate['root_source']['timebase'] = [1, 0]
            result = propose(candidates=[candidate], selected=selection('short-0'))
            self.assertEqual('lineage_unverified', result['blocked'][0]['code'])

    def test_injected_choice_cannot_expand_its_authorized_options(self):
        def mutate(context):
            context['options'] = ('2026-10-26T16:00:00+05:30',)
            return context['options'][0]
        self.assert_code('slot_choice_invalid', lambda: propose(chooser=mutate))


if __name__ == '__main__':
    unittest.main()
