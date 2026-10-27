# Offline model validation

Run date: 2026-10-27. Runtime: CPython 3.12.14 on Windows. Standard-library `unittest` and SQLite; no third-party packages or network services.

Command from this directory:

```sh
python -B -m unittest -v test_model
```

Result: **27 test methods passed**, zero failures/errors. Subcases are included in those methods, not counted as extra tests. The first recorded full run completed in 7.336 seconds; timing depends on the machine.

| Property | Representative evidence |
| --- | --- |
| History/location independence in the proposal | All four synthetic location × export-history combinations complete with required fake custody assertions. |
| Order independence | All 24 permutations of four inputs return one operation and quote for the same key. |
| Validation without spending | Invalid counts, duplicates, unknown gifts, wrong owner, mixed types, disabled/stale recipe, cooldown and listed inputs are rejected. |
| Channel permission | Authorized fixture succeeds with channel-owned output; permission revoked before commit blocks spending. |
| Idempotency | Same-key retries preserve the operation; changed payload conflicts; terminal retries do not redraw or consume again. |
| Probability boundaries | Tests cover zero, one-permille boundary around a 250/1000 quote, and certainty; failed crafts consume once and cannot be rerolled. |
| Crash recovery | Three failpoints × two outcomes: after persisted decision, after first external receipt, before result publication. Both ledgers are re-opened before recovery. |
| Concurrent requests | Eight workers compete on same/different preparation keys and concurrent commits; reservation/output/outcome counts are asserted. |
| Cancellation and expiry | Cancel is idempotent, a cancelled key cannot create a new operation, expiry boundary releases prepared reservations, and commit/cancel race ends consistently. |
| Incomplete external settlement | A conflicting receipt blocks output publication and keeps inputs reserved for reconciliation. |
| Ownership changes and listing | The model prevents transfer/listing of reserved or consumed assets. |

These are contract tests of an authored proposal, not observations of Telegram's server or proof of a production implementation. Concurrent tests exercise schedules selected by the runtime; they are not an exhaustive concurrency proof. An exception/re-open recovery test does not establish power-loss durability. See the explicit model assumptions and remaining integration gates in [RFC.md](RFC.md).

No Telegram Desktop build, actual Qt user flow, wallet signature, TON transaction, real gift consumption or private backend test was performed for this proposal. Earlier client patch validation is separate and is not upgraded by these results.
