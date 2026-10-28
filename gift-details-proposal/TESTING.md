# Validation and reproduction

## Offline acceptance model

From this package directory:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

36 tests passed on 2026-10-28. All records, balances, custody flags, permissions and failures are synthetic in temporary SQLite databases. No network requests or real payments are made. Tests cover equivalent fees/results before and after export/return; a new current owner; external-custody and host-only rejection; owner/channel permissions and revocation; ownership/custody/revision changes; confirmation; insufficient and exact balance; invalid and changed fee; expiry; quote/operation binding; absent/consumed gifts; already-removed details; retry after a lost reply and after expiry; service restart; four pre-commit rollback points; two distinct concurrent operations; and a duplicate concurrent operation. A barrier starts both competing workers before they attempt payment. These tests do not stress production concurrency or kill a running process.

The model now persists a removal marker keyed by stable gift identity. Its trusted synthetic import function masks old detail data using that marker, even after restart, transfer and another export/return cycle. A new stale-write test failed against the earlier model, exposing its missing marker. The strengthened model passes it. This was a defect in our offline model, not an independently confirmed Telegram defect.

Six negative controls deliberately change the model to restore a historical export ban, remove ownership or confirmation checks, ignore the removal marker, restore details during import, or ignore gift revisions. Each targeted test detects its broken rule. Reproduce these controls separately:

```text
python tests/run_negative_controls.py --out PATH_TO_RESULTS/negative-controls.json
```

The model demonstrates internally consistent proposed semantics. It is not an implementation or regression test of Telegram's unavailable backend. Its atomicity relies on one SQLite database and `BEGIN IMMEDIATE`; production billing may cross services and requires its own durable transaction protocol. It represents details as a presence flag plus a durable removal marker and does not simulate actual greeting contents, all gift attributes, chain data or cache propagation. The import feed, actor identity, clock and confirmation boolean are trusted test inputs, not network authentication or a public service interface. TLS, MTProto, wallet signatures, production authorization and distributed failure recovery are outside this model.

## Current Desktop source diagnostics

Obtain the seven files in source-manifest.json from the pinned commit, preserving their paths below a source root. A clean checkout of that commit is also suitable. The runner accepts LF or CRLF working-copy files and verifies their normalized Git blob hashes. It extracts the exact unmodified `UniqueGiftCanRemoveDetails()` and `Api::InputSavedStarGiftId()` function definitions, compiling them against small data/TL adapters.

```text
python tests/run_source_diagnostics.py --source PATH_TO_PINNED_SOURCE --compiler PATH_TO_GPP --out PATH_TO_RESULTS
```

Use a C++20-capable GCC compiler. No Qt, Telegram executable or network access is needed by this check. The generated program evaluates 40 combinations of collectible presence, export history, chain-address presence and price, plus the three gift-reference routes. The lifecycle/address fields are synthetic adapter fields; the real eligibility function does not read them. This is evidence about the inspected gate, not a simulation of server responses or proof of post-return invoice acceptance.

The expected current behavior is: a collectible with a positive server-provided quote passes regardless of the supplied export/address adapter values; absent or non-positive quotes fail. A missing quote after return therefore cannot be repaired by claiming the current client already knows a valid price.

Results and source hashes are captured in results/source-diagnostics.json after execution. results/model-tests.txt contains the actual acceptance test output. Neither is evidence of a full Telegram build or a successful removal using real gifts.

## Still required for a release

An affected-account reproduction, authoritative server/contract review, the backend change, real payment/cancellation/refund tests, restart/retry testing against production-equivalent services, cross-client/cache/indexer checks, and a full supported Telegram build. The acceptance matrix is in API_PROPOSAL.md. A universal-removal feature is not complete until those implementation and integration steps are performed by the responsible maintainers.
