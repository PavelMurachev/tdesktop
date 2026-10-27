# Gift crafting: source-only reproduction

Supporting test source for two independent draft Telegram Desktop changes.
This branch is separate from the proposed production patches. It contains no
local execution logs, account data, credentials, environment snapshots or binaries.
The results below summarize local runs; reviewers should reproduce them.

## Patches and scope

- `fix/gift-craft-response-lifetime`: use the request-owning session for the
  inventory notification after a crafting reply; remove an unused weak reference.
- `fix/gift-craft-exported-entry`: start from an exported owned gift by selecting
  a same-collection primary in owned-only mode. The original gift is secondary.

Each branch is one independent commit on `f985723b552b30fe1c17d377d57f44e61a15a8c4`.
The touched upstream files match the original test base
`dd2a96c356971a0781f142826fcc212273f90098`. Both commits can be applied in either order.

Follow the target repository's AGENTS.md and contribution rules. Review each diff
independently. Preserve ownership, server chance, cooldown, first-slot address
validation, saved gift references and explicit final confirmation. The new entry
step must not request resale, purchase or automatically craft. Server acceptance
of an exported secondary remains unverified; this is not unrestricted NFT crafting.

## Reproduce targeted checks

Run from this directory using Python 3 and a compatible C++20 compiler. Examples
below use the Windows LLVM-MinGW clang++.exe driver with ASan. Replace uppercase
path arguments and use a new output directory for each command. REPO_01 and
REPO_02 are separate checkouts containing only the corresponding patch.

```text
python tests/run_fragments.py --repo REPO_01 --compiler CLANG --work NEW_OUT_01 --sanitizer address --test "heap-lifetime-after-delete"
python tests/run_fragments.py --repo REPO_02 --compiler CLANG --work NEW_OUT_02 --sanitizer address --test "owned picker does not request market"
python tests/run_fragments.py --repo REPO_02 --compiler CLANG --work NEW_OUT_03 --sanitizer address --test "exported entry: explicit owned-only primary"
```

The fragment harness extracts exact production callbacks and substitutes
framework/UI/data/transport adapters. It is not a Telegram build. The three
targeted checks passed separately. For a negative lifetime control repeat the
first command with `--baseline --baseline-ref dd2a96c356971a0781f142826fcc212273f90098`
and a new output directory: the observed baseline compiled, then ASan reported
heap-use-after-free and test exit 86. A compile error or unrelated failure does
not reproduce that control. Runners save build/test output and result.json.

## Real framework component checks

QT_PREFIX is an MSYS2 UCRT Qt prefix including its compatible GCC libstdc++
headers/libraries. SOURCES contains the following pinned public source roots:

| Directory | Public repository | Commit |
| --- | --- | --- |
| base | desktop-app/lib_base | 95a543e426e35938dd632139d0bb828b268c3b4c |
| crl | desktop-app/lib_crl | de724667d7bdfbf906f78fc405af1ee9f7723d49 |
| gsl | microsoft/GSL | 87f9d768866548b5b86e72be66c60c5abd4d9b37 |
| rpl | desktop-app/lib_rpl | c57cccffb01d85570decd7fccb88419c9a682e63 |

Verify these dependencies against the target checkout before reproduction.
Qt/compilers/dependency source archives are not included.

```text
python tests/run_qt_lifetime.py --repo REPO_01 --qt QT_PREFIX --sources SOURCES --work NEW_OUT_04 --test "production reply after controller destruction"
python tests/run_qt_lifetime.py --repo REPO_02 --qt QT_PREFIX --sources SOURCES --work NEW_OUT_05 --test "production picker after base controller deletion"
python tests/run_rpl_loading.py --repo REPO_BOTH --qt QT_PREFIX --sources SOURCES --work NEW_OUT_06 --sequences
```

REPO_BOTH contains both independent commits. Optional `--compiler CLANG
--sanitizer address` enables the compatible Clang ASan/UBSan build. Prebuilt Qt
libraries were not themselves sanitizer-instrumented. Real Qt/base/crl/rpl are
used where indicated; session, transport and UI adapters still are doubles.

## Results and open questions

- Combined mock fragments: 35/35 UBSan and 35/35 ASan+UBSan-trap.
- Real Qt 6.12 component suite: 9/9 GCC and 9/9 ASan. Independent lifetime and
  selection-guard controls passed. Qt 6.11.2: 9/9 GCC and 9/9 Clang without ASan.
- Qt 6.11.2 ASan GUI suite FAILED at teardown with `bad-malloc_usable_size`,
  exit 86; reproduced twice in an empty QApplication. Cause remains open.
  `qt_runtime_control.cpp` and its runner provide that minimal comparison.
- Real-rpl exploratory suite (omit `--sequences`): 9/13 on GCC and ASan,
  exit 1, NOT PASS. Four state-retention assertions fail. Two comparable cases
  also fail on baseline; real RPC reachability of synthetic synchronous/no-value
  conditions is unestablished. These findings have not been fixed or suppressed.
- Separate bounded sequences: 7,812 passed on GCC and ASan, and all 3,906 legacy
  market traces matched baseline. Single-thread event words up to length five;
  fake transport/UI. This does not close the four retention findings. Test-only
  lifetime cleanup occurs after assertions. Legacy comparison preserves existing
  behavior, including error-order asymmetries; it does not prove that behavior ideal.

## Required before treating this as a fully validated application change

Full Telegram Debug compilation, real-window delayed reply, actual gift UI and
server-backed crafting have NOT run. Confirm session ownership in the full app.
For the entry change obtain maintainer agreement on intended behavior, validate
exported secondary eligibility using an authorized disposable fixture, and check
cancellation, empty/error lists, ownership changes and inventory reconciliation.
Report each patch separately with verified source locations, actual commands,
observed results, unresolved findings and unrun gates. No backend change is supplied.
