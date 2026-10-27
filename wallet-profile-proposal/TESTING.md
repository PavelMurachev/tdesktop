# Validation and reproduction

Base: f985723b552b30fe1c17d377d57f44e61a15a8c4.
Client candidate: 55511e7726fb995556738dce394168f1be44ba63.
Date: 2026-10-27.

## Completed

- Debug-style component compilation with GCC 16.2.0, C++20, -O0, -g3, -D_DEBUG, -Wall, -Wextra and -Werror.
- Real Qt Widgets 6.11.2, offscreen platform, plus the pinned base/crl/rpl/GSL source libraries listed in dependency-provenance.json.
- 600 combinations: self/other, feature available/unavailable, six presence states, five private balances and five card states. Balances include negative, zero, positive, and int64 maximum.
- 3,320 assertions covering value selection, actual QWidget show/hide, callback routing, correct account selection, no private-wallet subscription for other profiles, live balance changes, card arrival/removal at an equal zero, feature disable/re-enable, unavailable state, invisible controls and subscription teardown.
- Original-code negative control compiles and fails the owner-zero expectation: supplied zero card is hidden instead of shown.
- Patch applicability using git apply --check; whitespace check; original gift-crafting working files preserved.

The test runner extracts ProfileBalanceValue, BalancePill::setContent, BalancePill::actionable and the profile click callback from the candidate source at run time. It does not test a separately rewritten copy of those functions.

UserData, session/state producers, configuration events, action targets, styles and amount painting are adapters. QWidget visibility and rpl execution are real. This does not validate the complete widget's layout, paint rendering, generated headers, production API lifetimes, full translation units, linking or Telegram integration.

The negative control extracts the original card stream, original setContent and original callback, adapting the original scalar stream to the optional test interface. It is expected to fail a new requirement. It demonstrates the regression check distinguishes the old behavior; it is not an assertion that the original upstream release is generally broken.

## Reproduce on Windows

Check out the code commit and obtain Qt 6.11.2 with a compatible GCC toolchain. Place pinned dependency sources in separate base, crl, rpl and gsl subdirectories, with gsl/include beneath gsl. See dependency-provenance.json for source revisions. The runner does not download dependencies or install software.

Run from any working directory, substituting paths:

```powershell
python tests/run.py --source C:/path/to/tdesktop --qt C:/path/to/ucrt64 --deps C:/path/to/dependencies --out C:/path/to/results
```

For the negative control, create a separate clean checkout of the base commit and append:

```text
--baseline-control C:/path/to/upstream-base
```

The runner returns success for the negative-control experiment when compilation succeeds and the regression test returns 1. The result.json still records that test failure explicitly. A compilation failure or crash is not accepted as a successful negative control.

The standalone diff is wallet-profile.patch. manifest.json records normalized-LF hashes of the three before/after source files. result.json and baseline-result.json record the tested fragment hashes, compiler and outputs.

## Not performed / required before merge

- Full Telegram Debug build and CI on supported platforms.
- Launching the patched Telegram client with test accounts.
- Visual/accessibility review of zero and small balances, scaling, themes, animation, layer/side/profile contexts and existing card customization.
- End-to-end testing of a genuinely ready zero wallet with an omitted public card, provisioning, wallet-unavailable and rollout-disabled accounts.
- Real backend privacy or cache-invalidation tests; no such privacy implementation is supplied.
- Real transfers, deposits, signing, custody changes, wallet creation or key access.
- Android/iOS changes or builds.

Maintainers should first confirm the intended owner-only profile behavior. The candidate is suitable for source review and component reproduction, not described as fully tested or ready to merge.
