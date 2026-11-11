"""Temporary SQLite integration only; no providers, media, models or real queue."""
import copy
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from hinglish_publish.channel_queue_plan import ProposalError, propose_replenishment
from hinglish_publish.store import Store
from tests.test_channel_queue_plan import asset, choose, destination, policy, selection, NOW


def media_for(candidates):
    meta = dict(title='Synthetic finished highlight', description='Synthetic description.',
                instagram_caption='Synthetic highlight. #Gaming', tags=['Gaming'])
    return {a['asset_id']: dict(verified=True, asset=copy.deepcopy(a),
                               content_sha256=a['content_sha256'],
                               video='synthetic-only/' + a['asset_id'] + '.mp4',
                               metadata={'youtube': copy.deepcopy(meta), 'instagram': copy.deepcopy(meta)},
                               visibility='public') for a in candidates}


class ChannelQueueCommitTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).resolve().parents[1] / 'tmp'
        folder.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='queue-commit-', dir=folder)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.bindings = [destination()]

    def plan(self, candidates=None, selected=None, destinations=None, rules=None,
             now=NOW, existing_lineage=None, store=None):
        store = store or self.store
        candidates = candidates if candidates is not None else [asset(0), asset(1), asset(2)]
        selected = selected or selection(*[a['asset_id'] for a in candidates])
        destinations = destinations or [destination()]
        rules = rules or policy(*destinations)
        request = dict(bindings=copy.deepcopy(self.bindings), finished_candidates=candidates,
                       selection=selected, destinations=destinations, policy=rules,
                       now=now, media=media_for(candidates), existing_lineage=existing_lineage)
        snap = store.proposal_snapshot(self.bindings, existing_lineage=existing_lineage)
        proposal = propose_replenishment(snap, candidates, selected, destinations, rules, now, choose)
        return proposal, request

    def raw_rows(self, store=None):
        with (store or self.store).connect() as db:
            return [tuple(r) for r in db.execute('SELECT * FROM jobs ORDER BY rowid')]

    def assert_code(self, code, call):
        with self.assertRaises(ProposalError) as caught:
            call()
        self.assertEqual(code, caught.exception.code)

    def test_apply_only_drafts_not_claimable_and_exact_persisted_times(self):
        proposal, request = self.plan()
        result = self.store.apply_proposal(proposal, **request)
        self.assertFalse(result['replayed'])
        self.assertFalse(result['receipt']['execution_authorized'])
        jobs = self.store.list()
        self.assertEqual(3, len(jobs))
        self.assertTrue(all(j['status'] == 'draft' and j['remote'] == {} and j['attempts'] == 0 for j in jobs))
        self.assertTrue(all(j['execution_authorized'] is False and 'authorized_at' not in j for j in jobs))
        self.assertEqual([e['release_at'] for e in proposal['new_entries']], [j['release_at'] for j in jobs])
        self.assertEqual([datetime.fromisoformat(e['release_at']).timestamp() for e in proposal['new_entries']],
                         [j['due'] for j in jobs])
        self.assertIsNone(self.store.claim(datetime(2030, 1, 1).timestamp()))

    def test_double_submit_and_restart_return_same_receipt_without_writes(self):
        proposal, request = self.plan()
        first = self.store.apply_proposal(proposal, **request)
        before = self.raw_rows()
        revision = self.store.proposal_snapshot(self.bindings)['revision']
        again = Store(self.root)
        result = again.apply_proposal(proposal, **request)
        self.assertTrue(result['replayed'])
        self.assertEqual(first['receipt'], result['receipt'])
        self.assertEqual(before, self.raw_rows(again))
        self.assertEqual(revision, again.proposal_snapshot(self.bindings)['revision'])

    def test_week_two_append_preserves_all_old_bytes_times_and_remote_receipts(self):
        first, first_request = self.plan()
        self.store.apply_proposal(first, **first_request)
        old_id = first['new_entries'][0]['id']
        self.store.change(old_id, status='scheduled', remote={'id': 'synthetic-remote', 'receipt': {'keep': [1, 2]}},
                          attempts=1, metadata={'title': 'Preserve exact old metadata'})
        before = self.raw_rows()
        second, second_request = self.plan([asset(3), asset(4)],
            selection('short-3', 'short-4', request='request-2', batch='week-2'),
            rules=policy(day='2026-11-02'), now=datetime.fromisoformat('2026-11-01T12:00:00+05:30'))
        self.store.apply_proposal(second, **second_request)
        self.assertEqual(before, self.raw_rows()[:3])
        self.assertEqual(['2026-11-02T17:10:00+05:30', '2026-11-03T17:11:00+05:30'],
                         [j['release_at'] for j in self.store.list()[3:]])
        self.assertEqual(5, len(self.store.list()))

    def test_two_connections_same_request_commit_exactly_once(self):
        proposal, request = self.plan()
        stores = [Store(self.root), Store(self.root)]
        barrier, outcomes, errors = threading.Barrier(2), [], []
        def run(store):
            try:
                barrier.wait(timeout=5)
                outcomes.append(store.apply_proposal(proposal, **request))
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=run, args=(store,)) for store in stores]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual([], errors)
        self.assertEqual([False, True], sorted(r['replayed'] for r in outcomes))
        self.assertEqual(3, len(self.store.list()))

    def test_two_connections_competing_requests_reject_stale_without_partial_batch(self):
        first = self.plan([asset(0)], selection('short-0', request='a'))
        second = self.plan([asset(1)], selection('short-1', request='b'))
        barrier, outcomes = threading.Barrier(2), []
        def run(pair):
            try:
                store = Store(self.root)
                barrier.wait(timeout=5)
                store.apply_proposal(pair[0], **pair[1])
                outcomes.append('committed')
            except ProposalError as error:
                outcomes.append(error.code)
        threads = [threading.Thread(target=run, args=(pair,)) for pair in (first, second)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertEqual(['committed', 'stale_snapshot'], sorted(outcomes))
        self.assertEqual(1, len(self.store.list()))

    def test_rebinding_between_plan_and_commit_blocks(self):
        proposal, request = self.plan()
        request['bindings'][0]['connection_ref'] = 'new-connection'
        self.assert_code('stale_snapshot', lambda: self.store.apply_proposal(proposal, **request))
        self.assertEqual([], self.store.list())

    def test_replay_changed_account_or_original_source_never_retargets(self):
        proposal, request = self.plan()
        self.store.apply_proposal(proposal, **request)
        before = self.raw_rows()
        changed = copy.deepcopy(request)
        changed['bindings'][0]['account_id'] = 'wrong-account'
        self.assert_code('account_binding_changed', lambda: self.store.apply_proposal(proposal, **changed))
        changed = copy.deepcopy(request)
        changed['finished_candidates'][0]['content_sha256'] = 'f' * 64
        self.assert_code('request_changed', lambda: self.store.apply_proposal(proposal, **changed))
        self.assertEqual(before, self.raw_rows())

    def test_invalid_second_media_row_rolls_back_entire_batch(self):
        proposal, request = self.plan()
        request['media']['short-1']['content_sha256'] = 'f' * 64
        revision = self.store.proposal_snapshot(self.bindings)['revision']
        self.assert_code('media_identity_changed', lambda: self.store.apply_proposal(proposal, **request))
        self.assertEqual([], self.store.list())
        self.assertEqual(revision, self.store.proposal_snapshot(self.bindings)['revision'])

    def test_sql_failure_after_first_insert_rolls_back_jobs_receipt_and_revision(self):
        proposal, request = self.plan()
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON jobs WHEN json_extract(NEW.data,'$.asset.asset_id')='short-1' BEGIN SELECT RAISE(ABORT,'synthetic insert failure'); END")
        before = self.store.proposal_snapshot(self.bindings)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.apply_proposal(proposal, **request)
        self.assertEqual(before, self.store.proposal_snapshot(self.bindings))
        self.assertEqual([], self.store.list())

    def test_stale_due_change_and_legacy_writes_are_detected(self):
        proposal, request = self.plan()
        self.store.add_batch([dict(kind='long', platform='youtube', fingerprint='c' * 64)], now=NOW.timestamp())
        before = self.raw_rows()
        self.assert_code('stale_snapshot', lambda: self.store.apply_proposal(proposal, **request))
        self.assertEqual(before, self.raw_rows())
        fresh, fresh_request = self.plan()
        self.store.change(self.store.list()[0]['id'], metadata={'manual': 'change'})
        self.assert_code('stale_snapshot', lambda: self.store.apply_proposal(fresh, **fresh_request))

    def test_expired_new_plan_does_not_catch_up_but_saved_receipt_is_readable(self):
        proposal, request = self.plan()
        late = {**request, 'now': datetime.fromisoformat('2026-10-26T17:09:00+05:30')}
        self.assert_code('slot_choice_invalid', lambda: self.store.apply_proposal(proposal, **late))
        self.assertEqual([], self.store.list())
        self.store.apply_proposal(proposal, **request)
        result = self.store.apply_proposal(proposal, **{**request, 'now': datetime.fromisoformat('2026-12-01T12:00:00+05:30')})
        self.assertTrue(result['replayed'])
        self.assertTrue(all(a['action'] == 'missed_slot_review' for a in result['review_actions']))

    def test_unarmed_fields_and_forged_proposal_are_rejected(self):
        proposal, request = self.plan()
        for key, value in [('status', 'ready'), ('authorized_at', NOW.timestamp()), ('remote', {'id': 'bad'})]:
            changed = copy.deepcopy(request)
            changed['media']['short-0'][key] = value
            self.assert_code('draft_fields_required', lambda: self.store.apply_proposal(proposal, **changed))
        changed = copy.deepcopy(proposal)
        changed['new_entries'][0]['status'] = 'ready'
        from hinglish_publish.channel_queue_plan import _hash
        changed['proposal_sha256'] = _hash({k: v for k, v in changed.items() if k != 'proposal_sha256'})
        self.assert_code('proposal_mismatch', lambda: self.store.apply_proposal(changed, **request))
        self.assertEqual([], self.store.list())

    def test_profile_isolation_and_shared_actual_account_day_occupancy(self):
        gaming, cricket, other = destination(), destination(profile='cricket'), destination(profile='general', account='other')
        self.bindings = [gaming, cricket, other]
        first, request = self.plan([asset(0)], selection('short-0'))
        self.store.apply_proposal(first, **request)
        second, request = self.plan([asset(1)], selection('short-1', request='second'), [cricket])
        self.assertEqual('2026-10-27', second['new_entries'][0]['local_date'])
        self.store.apply_proposal(second, **request)
        third, request = self.plan([asset(2)], selection('short-2', request='third'), [other])
        self.assertEqual('2026-10-26', third['new_entries'][0]['local_date'])
        self.store.apply_proposal(third, **request)
        self.assertEqual(['gaming', 'general', 'cricket'], [j['profile'] for j in self.store.list()])

    def test_uncertain_old_submission_is_preserved_no_rearm_or_duplicate(self):
        first, request = self.plan()
        self.store.apply_proposal(first, **request)
        job_id = first['new_entries'][0]['id']
        self.store.change(job_id, status='needs_review', remote={'id': 'synthetic-uncertain'}, attempts=1)
        before = self.raw_rows()
        result = self.store.apply_proposal(first, **request)
        self.assertTrue(result['replayed'])
        self.assertEqual('reconcile_remote', result['review_actions'][0]['action'])
        self.assertEqual(before, self.raw_rows())
        duplicate, duplicate_request = self.plan([asset(0), asset(3)],
            selection('short-0', 'short-3', request='uncertain-duplicate'))
        self.assertFalse(duplicate['commit_ready'])
        self.assert_code('proposal_requires_review', lambda: self.store.apply_proposal(duplicate, **duplicate_request))
        self.assertEqual(before, self.raw_rows())

    def test_existing_duplicates_reference_old_jobs_without_new_upload_rows(self):
        first, request = self.plan()
        self.store.apply_proposal(first, **request)
        duplicate = asset(99, sha=asset(0)['content_sha256'])
        proposal, request = self.plan([duplicate], selection('short-99', request='renamed'))
        self.assertEqual([], proposal['new_entries'])
        before = self.raw_rows()
        result = self.store.apply_proposal(proposal, **request)
        self.assertEqual([], result['receipt']['created_job_ids'])
        self.assertEqual([first['new_entries'][0]['id']], result['receipt']['referenced_job_ids'])
        self.assertEqual(before, self.raw_rows())

    def test_legacy_rows_are_preserved_and_missing_lineage_blocks_instead_of_omitting(self):
        a = asset(0)
        old_id = self.store.add_batch([dict(kind='short', platform='youtube', profile='gaming',
            fingerprint=a['content_sha256'], video='synthetic-old.mp4', metadata={'keep': [1, 2]},
            account_id='channel-a')], now=NOW.timestamp())[0]
        before = self.raw_rows()
        self.assert_code('queue_history_unverified', lambda: self.store.proposal_snapshot(self.bindings))
        lineage = {old_id: dict(verified=True, destination=destination(), asset=a)}
        proposal, request = self.plan([asset(3)], selection('short-3', request='legacy-append'), existing_lineage=lineage)
        self.store.apply_proposal(proposal, **request)
        self.assertEqual(before, self.raw_rows()[:1])
        self.assertEqual(2, len(self.store.list()))

    def test_media_attestation_and_manifest_are_required_no_media_file_reads(self):
        proposal, request = self.plan()
        for mutation in ('unverified', 'lineage', 'missing'):
            changed = copy.deepcopy(request)
            if mutation == 'unverified': changed['media']['short-1']['verified'] = False
            if mutation == 'lineage': changed['media']['short-1']['asset']['highlights']['version'] = 'different'
            if mutation == 'missing': changed['media'].pop('short-1')
            self.assert_code('media_identity_changed', lambda: self.store.apply_proposal(proposal, **changed))
        self.assertEqual([], self.store.list())

    def test_two_accounts_same_profile_and_two_platforms_keep_distinct_persisted_slots(self):
        a, b, instagram = destination(), destination(account='channel-b'), destination(platform='instagram', account='ig-a')
        self.bindings = [a, b, instagram]
        first, request = self.plan([asset(0)], selection('short-0'), [a, instagram])
        result = self.store.apply_proposal(first, **request)
        self.assertEqual(1, result['receipt']['counts']['selected_n'])
        self.assertEqual(2, len(result['receipt']['created_job_ids']))
        second, request = self.plan([asset(1)], selection('short-1', request='other-account'), [b])
        self.assertEqual('2026-10-26', second['new_entries'][0]['local_date'])
        self.store.apply_proposal(second, **request)
        self.assertEqual({'channel-a', 'channel-b', 'ig-a'}, {j['account_id'] for j in self.store.list()})

    def test_cancelled_day_is_held_until_explicit_reconciliation(self):
        first, request = self.plan([asset(0)], selection('short-0'))
        self.store.apply_proposal(first, **request)
        job_id = first['new_entries'][0]['id']
        self.store.change(job_id, status='cancelled')
        held, _ = self.plan([asset(1)], selection('short-1', request='held'))
        self.assertEqual('2026-10-27', held['new_entries'][0]['local_date'])
        self.store.change(job_id, reconciliation=dict(verified=True, reservation_released=True, remote_outcome='cancelled'))
        before = self.raw_rows()
        released, request = self.plan([asset(1)], selection('short-1', request='released'))
        self.assertEqual('2026-10-26', released['new_entries'][0]['local_date'])
        self.store.apply_proposal(released, **request)
        self.assertEqual(before, self.raw_rows()[:1])

    def test_restart_due_edit_is_reported_not_replaced_or_silently_restored(self):
        first, request = self.plan()
        self.store.apply_proposal(first, **request)
        self.store.change(first['new_entries'][0]['id'], due=datetime.fromisoformat('2026-10-26T19:00:00+05:30').timestamp())
        before = self.raw_rows()
        self.assert_code('request_receipt_incomplete', lambda: Store(self.root).apply_proposal(first, **request))
        self.assertEqual(before, self.raw_rows())

    def test_cleared_runtime_binding_cannot_reuse_a_pinned_entry(self):
        first, request = self.plan()
        self.store.apply_proposal(first, **request)
        self.store.change(first['new_entries'][0]['id'], account_id='')
        before = self.raw_rows()
        self.assert_code('queue_history_unverified', lambda: self.store.apply_proposal(first, **request))
        self.assertEqual(before, self.raw_rows())

    def test_incomplete_or_armed_saved_receipt_is_not_reported_as_a_valid_commit(self):
        first, request = self.plan()
        self.store.apply_proposal(first, **request)
        with self.store.connect() as db:
            row = db.execute('SELECT data FROM channel_queue_requests').fetchone()
            body = json.loads(row['data'])
            body['receipt']['execution_authorized'] = True
            db.execute('UPDATE channel_queue_requests SET data=?', (json.dumps(body),))
        before = self.raw_rows()
        self.assert_code('request_receipt_incomplete', lambda: self.store.apply_proposal(first, **request))
        self.assertEqual(before, self.raw_rows())

    def test_refresh_plan_for_committed_request_is_also_idempotent(self):
        first, request = self.plan()
        result = self.store.apply_proposal(first, **request)
        refreshed, request = self.plan()
        self.assertEqual([], refreshed['new_entries'])
        before = self.raw_rows()
        again = self.store.apply_proposal(refreshed, **request)
        self.assertTrue(again['replayed'])
        self.assertEqual(result['receipt'], again['receipt'])
        self.assertEqual(before, self.raw_rows())

    def test_legacy_historical_binding_cannot_override_stored_actual_account(self):
        a = asset(0)
        job_id = self.store.add_batch([dict(kind='short', platform='youtube', profile='gaming',
            fingerprint=a['content_sha256'], account_id='channel-a')], now=NOW.timestamp())[0]
        wrong = {job_id: dict(verified=True, destination=destination(account='wrong'), asset=a)}
        before = self.raw_rows()
        self.assert_code('queue_history_unverified', lambda: self.store.proposal_snapshot(self.bindings, existing_lineage=wrong))
        self.assertEqual(before, self.raw_rows())

    def test_existing_schema_and_legacy_methods_preserve_their_jobs_and_semantics(self):
        root = self.root / 'legacy-schema-fixture'
        path = root / 'cache' / 'publisher' / 'queue.sqlite3'
        path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(path)) as db:
            db.executescript('CREATE TABLE jobs(id TEXT PRIMARY KEY,identity TEXT UNIQUE NOT NULL,status TEXT NOT NULL,due REAL NOT NULL,data TEXT NOT NULL); CREATE TABLE events(id INTEGER PRIMARY KEY,created REAL NOT NULL,job_id TEXT,message TEXT NOT NULL);')
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)', ('old-job', 'old-identity', 'published', NOW.timestamp(),
                json.dumps(dict(kind='long', platform='youtube', fingerprint='d'*64, remote={'id': 'preserve'}, metadata={'old': [1, 2]}))))
            original = db.execute('SELECT * FROM jobs').fetchall()
            columns = db.execute('PRAGMA table_info(jobs)').fetchall()
            db.commit()
        store = Store(root)
        self.assertEqual(original, self.raw_rows(store))
        with store.connect() as db:
            self.assertEqual(columns, [tuple(r) for r in db.execute('PRAGMA table_info(jobs)')])
        item = dict(kind='short', platform='youtube', fingerprint='e'*64)
        ids = store.add_batch([item], now=NOW.timestamp())
        self.assertEqual(ids, store.add_batch([item], now=NOW.timestamp()))
        store.change(ids[0], status='ready')
        self.assertEqual(ids[0], store.claim(NOW.timestamp())['id'])
        store.recover()
        self.assertEqual('needs_review', store.get(ids[0])['status'])
        self.assertEqual(original[0], self.raw_rows(store)[0])

    def test_no_provider_secret_service_worker_network_process_or_implicit_clock(self):
        proposal, request = self.plan()
        import builtins
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if any(part in name for part in ('hinglish_publish.providers', 'hinglish_publish.secrets',
                                            'hinglish_publish.service', 'ollama', 'openai')):
                raise AssertionError('Forbidden runtime dependency: ' + name)
            return original(name, *args, **kwargs)
        with patch('socket.socket', side_effect=AssertionError('network forbidden')), \
             patch('subprocess.Popen', side_effect=AssertionError('process forbidden')), \
             patch('hinglish_publish.store.time.time', side_effect=AssertionError('clock must be injected')), \
             patch('builtins.__import__', side_effect=guarded):
            result = self.store.apply_proposal(proposal, **request)
        self.assertFalse(result['receipt']['execution_authorized'])


if __name__ == '__main__':
    unittest.main()
