"""Contract tests for the proposed offline model, not for Telegram servers."""
from concurrent.futures import ThreadPoolExecutor
from itertools import permutations, product
from pathlib import Path
import tempfile
from threading import Barrier
import unittest

from model import Model, MockSettlement, Rejected, SimulatedCrash, transaction


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / 'service.sqlite')
        self.external = str(Path(self.tmp.name) / 'settlement.sqlite')
        self.adapter = MockSettlement(self.external)
        self.m = Model(self.db, self.adapter)

    def seed(self, count=4, **kw):
        ids = [f'g{i}' for i in range(count)]
        for ident in ids:
            self.m.add_gift(ident, **kw)
        return ids

    def prepare(self, ids, **kw):
        return self.m.prepare('alice', 'alice', ids, 'request', **kw)['id']

    def rejects(self, reason, fn, *args, **kw):
        with self.assertRaisesRegex(Rejected, '^' + reason + '$'):
            fn(*args, **kw)

    def restart(self):
        def no_redraw():
            raise AssertionError('Committed operation must never redraw')
        self.adapter = MockSettlement(self.external)
        self.m = Model(self.db, self.adapter, no_redraw)

    def race(self, *jobs):
        barrier = Barrier(len(jobs))
        def run(job):
            barrier.wait(timeout=10)
            try:
                return job()
            except Rejected as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            return list(pool.map(run, jobs))

    def test_fresh_identity_and_consumption(self):
        ids = self.seed()
        out = self.m.commit('alice', self.prepare(ids))
        self.assertEqual(out['state'], 'succeeded')
        self.assertNotIn(out['result'], ids)
        self.assertEqual(self.m.counts(), dict(consumed=4, reserved=0, outputs=1))
        self.assertEqual(self.adapter.count(), 4)

    def test_all_history_and_location_combinations(self):
        for location, exported in product(('telegram', 'ton'), (False, True)):
            with self.subTest(location=location, exported=exported):
                ident = f'{location}-{exported}'
                self.m.add_gift(ident, location=location, exported=exported)
                op = self.m.prepare('alice', 'alice', [ident], ident)['id']
                result = self.m.commit('alice', op, verified_ton_inputs={(op, ident)})
                self.assertEqual(result['state'], 'succeeded')
        self.assertEqual(self.m.counts()['outputs'], 4)

    def test_permutations_have_one_quote_and_operation(self):
        ids = self.seed()
        quotes = [self.m.prepare('alice', 'alice', list(order), 'same') for order in permutations(ids)]
        self.assertEqual(len({q['id'] for q in quotes}), 1)
        self.assertTrue(all(q['chance'] == 1000 for q in quotes))

    def test_request_key_reuse_with_different_payload(self):
        ids = self.seed()
        self.prepare(ids[:1])
        self.rejects('idempotency_conflict', self.prepare, ids[1:2])
        self.rejects('idempotency_conflict', self.prepare, ids[:1], version=2)

    def test_invalid_input_count_duplicates_and_unknown(self):
        ids = self.seed(5)
        for bad in ([], ids, [ids[0], ids[0]]):
            self.rejects('invalid_request', self.prepare, bad)
        self.rejects('unknown_input', self.prepare, ['missing'])
        self.assertEqual(self.m.counts()['reserved'], 0)

    def test_invalid_key_and_ttl(self):
        ids = self.seed(1)
        self.rejects('invalid_request', self.m.prepare, 'alice', 'alice', ids, '')
        self.rejects('invalid_request', self.prepare, ids, ttl=0)

    def test_mixed_types_and_unsupported_recipe(self):
        self.m.add_gift('bell')
        self.m.add_gift('calendar', kind='calendars')
        self.rejects('mixed_types', self.prepare, ['bell', 'calendar'])
        with transaction(self.db) as db:
            db.execute('UPDATE policies SET enabled=0')
        self.rejects('recipe_changed_or_disabled', self.prepare, ['bell'])

    def test_owner_and_operation_access(self):
        ids = self.seed(1)
        self.rejects('owner_authorization_required', self.m.prepare, 'bob', 'alice', ids, 'x')
        self.rejects('wrong_owner', self.m.prepare, 'bob', 'bob', ids, 'x')
        op = self.prepare(ids)
        for method in (self.m.get, self.m.commit, self.m.cancel, self.m.resume):
            self.rejects('operation_not_accessible', method, 'bob', op)

    def test_channel_crafting_preserves_owner(self):
        ids = self.seed(2, owner='channel')
        self.m.permission('alice', 'channel', True)
        op = self.m.prepare('alice', 'channel', ids, 'channel')['id']
        self.m.commit('alice', op)
        with transaction(self.db) as db:
            self.assertEqual(db.execute('SELECT owner FROM outputs').fetchone()[0], 'channel')

    def test_revoked_channel_permission_blocks_commit(self):
        ids = self.seed(1, owner='channel')
        self.m.permission('alice', 'channel', True)
        op = self.m.prepare('alice', 'channel', ids, 'channel')['id']
        self.m.permission('alice', 'channel', False)
        self.rejects('owner_authorization_required', self.m.commit, 'alice', op)
        self.assertEqual(self.adapter.count(), 0)

    def test_cooldown_boundary(self):
        ids = self.seed(1, cooldown=20)
        self.rejects('input_unavailable', self.prepare, ids, now=19)
        self.m.commit('alice', self.prepare(ids, now=20), now=20)

    def test_listed_asset_rejected_and_reservation_locks_mutations(self):
        ids = self.seed(1)
        self.m.change_asset('alice', ids[0], listed=True)
        self.rejects('input_unavailable', self.prepare, ids)
        self.m.change_asset('alice', ids[0], listed=False)
        self.prepare(ids)
        self.rejects('asset_locked', self.m.change_asset, 'alice', ids[0], listed=True)
        self.rejects('asset_locked', self.m.change_asset, 'alice', ids[0], new_owner='bob')

    def test_recipe_or_quote_change_before_commit(self):
        op = self.prepare(self.seed(1))
        with transaction(self.db) as db:
            db.execute('UPDATE policies SET version=2')
        self.rejects('recipe_changed_or_disabled', self.m.commit, 'alice', op)
        with transaction(self.db) as db:
            db.execute('UPDATE policies SET version=1')
            db.execute('UPDATE gifts SET chance=251')
        self.rejects('quote_changed', self.m.commit, 'alice', op)
        self.assertEqual(self.adapter.count(), 0)

    def test_ton_custody_must_match_operation_and_asset(self):
        ids = self.seed(2, location='ton')
        op = self.prepare(ids)
        for receipts in ((), {('other-op', x) for x in ids}, {(op, ids[0])}):
            self.rejects('verified_custody_required', self.m.commit, 'alice', op, verified_ton_inputs=receipts)
        self.assertEqual(self.adapter.count(), 0)
        self.m.commit('alice', op, verified_ton_inputs={(op, x) for x in ids})

    def test_probability_boundaries(self):
        for chance, draw, expected in ((0, 0, 'failed'), (250, 249, 'succeeded'),
                                        (250, 250, 'failed'), (1000, 999, 'succeeded')):
            with self.subTest(chance=chance, draw=draw):
                ident = f'{chance}-{draw}'
                self.m.add_gift(ident, chance=chance)
                self.m.draw = lambda value=draw: value
                op = self.m.prepare('alice', 'alice', [ident], ident)['id']
                self.assertEqual(self.m.commit('alice', op)['state'], expected)
        self.assertEqual(self.m.counts(), dict(consumed=4, reserved=0, outputs=2))

    def test_excess_probability_rejected_not_silently_clamped(self):
        self.rejects('invalid_recipe_probability', self.prepare, self.seed(2, chance=600))
        self.assertEqual(self.m.counts()['reserved'], 0)

    def test_invalid_draw_rolls_back_decision(self):
        op = self.prepare(self.seed(1))
        self.m.draw = lambda: 1000
        with self.assertRaises(ValueError):
            self.m.commit('alice', op)
        self.assertEqual(self.m.get('alice', op)['state'], 'prepared')
        self.assertEqual(self.adapter.count(), 0)

    def test_terminal_retries_do_not_consume_twice_or_redraw(self):
        op = self.prepare(self.seed(2))
        first = self.m.commit('alice', op)
        self.restart()
        self.assertEqual(self.m.commit('alice', op), first)
        self.assertEqual(self.m.resume('alice', op), first)
        self.assertEqual(self.adapter.count(), 2)
        self.assertEqual(self.m.counts()['outputs'], 1)

    def test_failed_craft_consumes_inputs_and_cannot_reroll(self):
        ids = self.seed(1)
        op = self.prepare(ids)
        self.m.draw = lambda: 999
        first = self.m.commit('alice', op)
        self.restart()
        self.assertEqual(self.m.commit('alice', op), first)
        self.assertEqual(first['state'], 'failed')
        self.rejects('input_unavailable', self.m.prepare, 'alice', 'alice', ids, 'retry')
        self.assertEqual(self.m.counts(), dict(consumed=1, reserved=0, outputs=0))

    def test_crash_recovery_all_failpoints_both_outcomes(self):
        for failpoint, draw in product(('after_decision', 'after_first_receipt', 'before_publication'), (0, 999)):
            with self.subTest(failpoint=failpoint, draw=draw):
                ids = [f'{failpoint}-{draw}-{i}' for i in range(2)]
                for ident in ids:
                    self.m.add_gift(ident)
                self.m.draw = lambda value=draw: value
                op = self.m.prepare('alice', 'alice', ids, failpoint + str(draw))['id']
                with self.assertRaises(SimulatedCrash):
                    self.m.commit('alice', op, crash_at=failpoint)
                pending = self.m.get('alice', op)
                self.assertEqual(pending['state'], 'committed')
                self.assertIsNone(pending['result'])
                self.assertNotIn('won', pending)
                self.rejects('already_committed', self.m.cancel, 'alice', op)
                self.assertEqual(self.m.expire(1000), 0)
                self.restart()
                result = self.m.commit('alice', op, now=1000)
                self.assertEqual(result['state'], 'succeeded' if draw == 0 else 'failed')
        self.assertEqual(self.m.counts(), dict(consumed=12, reserved=0, outputs=3))
        self.assertEqual(self.adapter.count(), 12)

    def test_external_conflict_never_publishes_result(self):
        ids = self.seed(2)
        self.adapter.consume(ids[1], 'another-operation')
        op = self.prepare(ids)
        self.rejects('external_conflict', self.m.commit, 'alice', op)
        self.assertEqual(self.m.get('alice', op)['state'], 'committed')
        self.assertEqual(self.m.counts(), dict(consumed=0, reserved=2, outputs=0))
        self.rejects('already_committed', self.m.cancel, 'alice', op)

    def test_cancel_is_idempotent_and_key_does_not_restart(self):
        ids = self.seed(1)
        op = self.prepare(ids)
        cancelled = self.m.cancel('alice', op)
        self.assertEqual(self.m.cancel('alice', op), cancelled)
        self.assertEqual(self.m.prepare('alice', 'alice', ids, 'request'), cancelled)
        self.rejects('cancelled', self.m.commit, 'alice', op)
        self.assertEqual(self.m.counts()['reserved'], 0)
        self.m.prepare('alice', 'alice', ids, 'new-request')

    def test_expiration_boundary_releases_prepared_only(self):
        op = self.prepare(self.seed(1), now=10, ttl=5)
        self.assertEqual(self.m.expire(14), 0)
        self.rejects('expired', self.m.commit, 'alice', op, now=15)
        self.assertEqual(self.m.expire(15), 1)
        self.assertEqual(self.m.expire(16), 0)
        self.assertEqual(self.m.counts()['reserved'], 0)

    def test_concurrent_prepare_same_key(self):
        ids = self.seed(1)
        results = self.race(*[lambda: self.prepare(ids) for _ in range(8)])
        self.assertEqual(len(set(results)), 1)
        self.assertTrue(results[0].startswith('op-'))

    def test_concurrent_prepare_different_keys(self):
        ids = self.seed(1)
        results = self.race(*[lambda k=str(i): self.m.prepare('alice', 'alice', ids, k) for i in range(8)])
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(results.count('already_reserved'), 7)

    def test_concurrent_commit_has_single_outcome(self):
        op = self.prepare(self.seed(4))
        draws = []
        self.m.draw = lambda: draws.append(0) or 0
        results = self.race(*[lambda: self.m.commit('alice', op) for _ in range(8)])
        self.assertTrue(all(isinstance(r, dict) for r in results))
        self.assertEqual(len({r['result'] for r in results}), 1)
        self.assertEqual(len(draws), 1)
        self.assertEqual(self.m.counts(), dict(consumed=4, reserved=0, outputs=1))
        self.assertEqual(self.adapter.count(), 4)

    def test_commit_cancel_race_is_consistent(self):
        op = self.prepare(self.seed(1))
        self.race(lambda: self.m.commit('alice', op), lambda: self.m.cancel('alice', op))
        state = self.m.get('alice', op)['state']
        self.assertIn(state, ('succeeded', 'cancelled'))
        committed = int(state == 'succeeded')
        self.assertEqual(self.m.counts(), dict(consumed=committed, reserved=0, outputs=committed))
        self.assertEqual(self.adapter.count(), committed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
