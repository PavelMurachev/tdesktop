# Remove original gift details after export and return

Prepared on 2026-10-28 against Telegram Desktop dev `f985723b552b30fe1c17d377d57f44e61a15a8c4`.

This is a server/API change proposal with an executable offline acceptance model and diagnostics of unchanged Desktop functions. It is not a working Telegram server patch or a TON contract implementation. No production source changes, live requests, real gifts or payments are included.

## Requested behavior

Let the current authorized owner remove original details from any existing collectible gift that still has them, at the server's quoted fee, regardless of whether that gift was ever exported. In particular, returning a gift from TON to Telegram must not permanently exclude it from the supported removal flow merely because it has an export history. Cover collection types uniformly.

For gifts still held in TON, provide an official owner-authorized path, or a clear supported return-to-Telegram prerequisite. Hosting a gift on a Telegram profile does not establish ownership of the NFT. An unimplemented direct wallet path must not be presented as working.

The existing operation removes the whole original-details attribute: sender, recipient, date and message. Removing only the greeting text is a separate proposed product option, not an ability of the existing invoice.

## Finding

The checked Desktop gate is `UniqueGiftCanRemoveDetails()` in `settings/settings_credits_graphics.cpp`: a collectible and a positive `starsForDetailsRemove` are required. The fee comes from the server's `drop_original_details_stars`. This gate does not inspect an NFT address or export history. The client already creates `inputInvoiceStarGiftDropOriginalDetails`, and the gift-reference helper supports user, channel and slug references.

Consequently, deleting a client gate or inventing a fee cannot implement the requested feature. The exact reason a particular returned gift lacks a removal quote remains unconfirmed: no affected account, current API response or live reproduction was used. The server policy and TON metadata/custody implementation are not present in the inspected Desktop repository.

## Review package

- [API_PROPOSAL.md](API_PROPOSAL.md): minimal compatible backend change, custody and payment requirements, acceptance criteria.
- [EVIDENCE.md](EVIDENCE.md): pinned source references, facts and unknowns.
- [TESTING.md](TESTING.md): reproducible commands and precise test limits.
- [SUGGESTION.txt](SUGGESTION.txt): ready English text for Bugs and Suggestions, category General / all apps.
- `tests/reference_service.py`: SQLite model of the proposed in-Telegram service behavior, entirely synthetic.
- `tests/test_reference_service.py`: 36 acceptance tests, including return to a new owner, restart, stale data, concurrency and rollback.
- `tests/run_negative_controls.py`: six deliberate model mutations that the acceptance tests must detect.
- `tests/run_source_diagnostics.py` and `tests/source_harness.cpp.in`: extract and compile the unchanged client gate and reference helper with adapters.
- `source-manifest.json`: seven upstream Git blobs pinned to the authoring commit.

## Validation

36 offline acceptance tests passed. Six deliberately broken model rules were detected by their targeted tests. Unmodified extracted Desktop functions also compiled with GCC 16.2.0 and passed 40 diagnostic combinations plus three gift-reference routes; all seven pinned source blobs matched. Results and commands are in TESTING.md. None of these checks verifies a real server, actual billing, a full Telegram build or TON metadata mutation. This package should be submitted as a platform proposal, not as a claim that a client PR enables universal removal.

The existing crafting and wallet PRs are unrelated and unchanged.
