"""Acceptance scenarios for a proposed service, using synthetic records only."""
import concurrent.futures
from pathlib import Path
import tempfile
import threading
import unittest

from reference_service import ReferenceService, Rejected


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = ReferenceService(Path(self.tmp.name) / 'model.sqlite')
        self.sql("INSERT INTO balances VALUES('owner',1000)")
        self.sql("INSERT INTO balances VALUES('other',1000)")
        self.sql("INSERT INTO gifts VALUES('gift','owner','telegram',0,1,1,1)")

    def sql(self, query, args=()):
        with self.service.connect() as db:
            return db.execute(query, args).fetchall()

    def assert_untouched(self, balance=1000):
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], balance)
        self.assertEqual(self.sql("SELECT details FROM gifts WHERE id='gift'")[0][0], 1)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM receipts')[0][0], 0)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM removed_details')[0][0], 0)

    def pay(self, quote=None, **options):
        quote = quote or self.service.quote('owner', 'gift')
        return self.service.pay('owner', 'gift', quote, 'operation',
                                confirmed=options.pop('confirmed', True), **options)

    def test_never_exported_gift(self):
        self.assertEqual(self.pay()['paid'], 25)
        self.assertEqual(self.sql("SELECT details FROM gifts")[0][0], 0)
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 975)

    def test_returned_gift_same_fee_and_result(self):
        self.sql('UPDATE gifts SET ever_exported=1')
        self.assertEqual(self.pay()['paid'], 25)
        self.assertEqual(self.sql('SELECT details FROM gifts')[0][0], 0)

    def test_external_wallet_requires_supported_custody_flow(self):
        self.sql("UPDATE gifts SET custody='ton',ever_exported=1")
        with self.assertRaisesRegex(Rejected, 'wallet_flow_required'):
            self.service.quote('owner', 'gift')
        self.assert_untouched()

    def test_hosting_does_not_prove_ownership(self):
        self.sql("UPDATE gifts SET owner='wallet-owner',custody='ton'")
        with self.assertRaisesRegex(Rejected, 'not_owner'):
            self.service.quote('owner', 'gift')
        self.assert_untouched()

    def test_other_user_cannot_quote(self):
        with self.assertRaisesRegex(Rejected, 'not_owner'):
            self.service.quote('other', 'gift')
        self.assert_untouched()

    def test_authorized_channel_manager(self):
        self.sql("UPDATE gifts SET owner='channel',ever_exported=1")
        self.sql("INSERT INTO grants VALUES('owner','channel')")
        self.assertEqual(self.pay()['paid'], 25)

    def test_revoked_channel_permission(self):
        self.sql("UPDATE gifts SET owner='channel'")
        self.sql("INSERT INTO grants VALUES('owner','channel')")
        quote = self.service.quote('owner', 'gift')
        self.sql('DELETE FROM grants')
        with self.assertRaisesRegex(Rejected, 'not_owner'):
            self.pay(quote)
        self.assert_untouched()

    def test_transferred_after_quote(self):
        quote = self.service.quote('owner', 'gift')
        self.sql("UPDATE gifts SET owner='other',revision=revision+1")
        with self.assertRaisesRegex(Rejected, 'not_owner'):
            self.pay(quote)
        self.assert_untouched()

    def test_export_after_quote(self):
        quote = self.service.quote('owner', 'gift')
        self.sql("UPDATE gifts SET custody='ton',revision=revision+1")
        with self.assertRaisesRegex(Rejected, 'wallet_flow_required'):
            self.pay(quote)
        self.assert_untouched()

    def test_gift_revision_changed(self):
        quote = self.service.quote('owner', 'gift')
        self.sql('UPDATE gifts SET revision=revision+1')
        with self.assertRaisesRegex(Rejected, 'gift_changed'):
            self.pay(quote)
        self.assert_untouched()

    def test_requires_confirmation(self):
        with self.assertRaisesRegex(Rejected, 'confirmation_required'):
            self.pay(confirmed=False)
        self.assert_untouched()

    def test_insufficient_balance(self):
        self.sql("UPDATE balances SET stars=24 WHERE actor='owner'")
        with self.assertRaisesRegex(Rejected, 'balance_insufficient'):
            self.pay()
        self.assert_untouched(24)

    def test_changed_fee_requires_new_confirmation(self):
        quote = self.service.quote('owner', 'gift')
        self.sql('UPDATE config SET fee=26,revision=revision+1')
        with self.assertRaisesRegex(Rejected, 'price_changed'):
            self.pay(quote)
        self.assert_untouched()

    def test_expired_quote(self):
        with self.assertRaisesRegex(Rejected, 'quote_expired'):
            self.pay(now=300)
        self.assert_untouched()

    def test_forged_or_foreign_quote(self):
        for quote in ('unknown', self.service.quote('owner', 'gift')):
            with self.assertRaisesRegex(Rejected, 'invalid_quote'):
                self.service.pay('other', 'gift', quote, 'attack', confirmed=True)
        self.assert_untouched()

    def test_missing_gift(self):
        with self.assertRaisesRegex(Rejected, 'not_found'):
            self.service.quote('owner', 'missing')

    def test_burned_gift(self):
        self.sql('UPDATE gifts SET live=0')
        with self.assertRaisesRegex(Rejected, 'gift_unavailable'):
            self.service.quote('owner', 'gift')
        self.assert_untouched()

    def test_already_removed_no_second_charge(self):
        self.pay()
        with self.assertRaisesRegex(Rejected, 'already_removed'):
            self.service.quote('owner', 'gift')
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 975)

    def test_retry_after_lost_reply(self):
        quote = self.service.quote('owner', 'gift')
        first = self.pay(quote)
        self.assertEqual(first, self.pay(quote))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM receipts')[0][0], 1)
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 975)

    def test_operation_bound_to_actor_gift_and_quote(self):
        quote = self.service.quote('owner', 'gift')
        self.pay(quote)
        for actor, gift, quoted in [('other','gift',quote), ('owner','other-gift',quote), ('owner','gift','other-quote')]:
            with self.assertRaisesRegex(Rejected, 'binding_conflict'):
                self.service.pay(actor, gift, quoted, 'operation', confirmed=True)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM receipts')[0][0], 1)

    def test_atomic_failure_and_retry(self):
        for stage in ('after_debit', 'after_removal', 'after_marker', 'after_receipt'):
            with self.subTest(stage=stage):
                quote = self.service.quote('owner', 'gift')
                with self.assertRaises(RuntimeError):
                    self.pay(quote, fail_at=stage)
                self.assert_untouched()
        self.assertEqual(self.pay()['paid'], 25)

    def test_competing_distinct_operations_charge_once(self):
        quotes = [self.service.quote('owner', 'gift') for _ in range(2)]
        ready = threading.Barrier(2)
        def attempt(index):
            ready.wait(timeout=5)
            try:
                return self.service.pay('owner', 'gift', quotes[index], str(index), confirmed=True)['paid']
            except Rejected as error:
                return str(error)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, [25, 'already_removed'])
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 975)

    def test_concurrent_same_operation_reuses_receipt(self):
        quote = self.service.quote('owner', 'gift')
        ready = threading.Barrier(2)
        def attempt(_):
            ready.wait(timeout=5)
            return self.pay(quote)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM receipts')[0][0], 1)

    def test_returned_gift_new_owner_can_remove(self):
        self.sql("UPDATE gifts SET owner='other',ever_exported=1,revision=2")
        quote = self.service.quote('other', 'gift')
        receipt = self.service.pay('other', 'gift', quote, 'new-owner', confirmed=True)
        self.assertEqual(receipt['paid'], 25)
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='other'")[0][0], 975)
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 1000)

    def test_old_quote_invalid_after_export_and_return(self):
        quote = self.service.quote('owner', 'gift')
        for custody in ('ton', 'telegram'):
            self.service.apply_authoritative_snapshot('gift', owner='owner',
                custody=custody, ever_exported=True, details=True)
        with self.assertRaisesRegex(Rejected, 'gift_changed'):
            self.pay(quote)
        self.assert_untouched()
        self.assertEqual(self.pay()['paid'], 25)

    def test_removed_details_stay_removed_after_export_return(self):
        self.pay()
        for custody in ('ton', 'telegram'):
            self.service.apply_authoritative_snapshot('gift', owner='owner',
                custody=custody, ever_exported=True, details=True)
        self.assertEqual(self.sql('SELECT details FROM gifts')[0][0], 0)
        with self.assertRaisesRegex(Rejected, 'already_removed'):
            self.service.quote('owner', 'gift')
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 975)

    def test_removal_survives_restart_and_new_owner(self):
        self.pay()
        self.service = ReferenceService(self.service.path)
        self.service.apply_authoritative_snapshot('gift', owner='other',
            custody='telegram', ever_exported=True, details=True)
        self.assertEqual(self.sql('SELECT details FROM gifts')[0][0], 0)
        with self.assertRaisesRegex(Rejected, 'already_removed'):
            self.service.quote('other', 'gift')
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='other'")[0][0], 1000)

    def test_persisted_marker_blocks_stale_detail_write(self):
        self.pay()
        self.sql('UPDATE gifts SET details=1')
        with self.assertRaisesRegex(Rejected, 'already_removed'):
            self.service.quote('owner', 'gift')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM receipts')[0][0], 1)

    def test_retry_after_service_restart(self):
        quote = self.service.quote('owner', 'gift')
        first = self.pay(quote)
        self.service = ReferenceService(self.service.path)
        self.assertEqual(self.pay(quote), first)
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 975)

    def test_unsettled_quote_survives_restart(self):
        quote = self.service.quote('owner', 'gift')
        self.service = ReferenceService(self.service.path)
        self.assertEqual(self.pay(quote)['paid'], 25)

    def test_committed_retry_after_quote_expiry(self):
        quote = self.service.quote('owner', 'gift')
        first = self.pay(quote)
        self.assertEqual(self.pay(quote, now=1000), first)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM receipts')[0][0], 1)

    def test_invalid_fee_configuration(self):
        for fee in (0, -1, 1.5):
            with self.subTest(fee=fee):
                self.sql('UPDATE config SET fee=?', (fee,))
                with self.assertRaisesRegex(Rejected, 'invalid_fee'):
                    self.service.quote('owner', 'gift')
                self.assert_untouched()

    def test_empty_operation_is_rejected(self):
        quote = self.service.quote('owner', 'gift')
        with self.assertRaisesRegex(Rejected, 'operation_required'):
            self.service.pay('owner', 'gift', quote, '', confirmed=True)
        self.assert_untouched()

    def test_quote_cannot_be_applied_to_another_gift(self):
        quote = self.service.quote('owner', 'gift')
        self.sql("INSERT INTO gifts VALUES('second','owner','telegram',1,1,1,1)")
        with self.assertRaisesRegex(Rejected, 'invalid_quote'):
            self.service.pay('owner', 'second', quote, 'wrong-gift', confirmed=True)
        self.assert_untouched()

    def test_exact_balance_is_sufficient(self):
        self.sql("UPDATE balances SET stars=25 WHERE actor='owner'")
        self.assertEqual(self.pay()['paid'], 25)
        self.assertEqual(self.sql("SELECT stars FROM balances WHERE actor='owner'")[0][0], 0)

    def test_export_history_is_monotonic(self):
        for exported in (True, False):
            self.service.apply_authoritative_snapshot('gift', owner='owner',
                custody='telegram', ever_exported=exported, details=True)
        self.assertEqual(self.sql('SELECT ever_exported FROM gifts')[0][0], 1)
        self.assertEqual(self.pay()['paid'], 25)


if __name__ == '__main__':
    unittest.main(verbosity=2)
