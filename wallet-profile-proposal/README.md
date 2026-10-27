# Owner wallet access and profile privacy

Status: Desktop candidate patch plus API/product proposal, prepared 2026-10-27. Submitted as [draft PR #31532](https://github.com/telegramdesktop/tdesktop/pull/31532). The Telegram API/product suggestion is prepared but has not yet been submitted.

[Client change](https://github.com/PavelMurachev/tdesktop/compare/f985723b552b30fe1c17d377d57f44e61a15a8c4...55511e7726fb995556738dce394168f1be44ba63) · [API proposal](API_PROPOSAL.md) · [Evidence](EVIDENCE.md) · [Checks and reproduction](TESTING.md)

The request is to let an owner find and fund their built-in wallet at zero balance, and choose whether Telegram exposes their wallet address and balance to other users.

The report describes an address in a Telegram profile. The reporter cannot see their own wallet and has not supplied an app version or a reproduction with a real account. Source inspection identifies Telegram's native wallet/card feature, but does not establish why that specific account lacks a wallet.

## Implemented client candidate

The existing profile balance control hides zero and conflates an absent card with zero balance. The patch:

- Distinguishes an absent balance from a valid zero balance.
- Shows an existing zero-balance wallet card to its owner.
- If the owner's public card is absent, uses their private wallet state only when the server has returned Ready, the balance is non-negative and wallet_available is enabled.
- Opens the existing wallet window from this fallback control; the existing Add Funds action can show the address without a positive balance.
- Keeps the existing card view when a card exists and keeps other users' profile behavior unchanged.

No new settings, translations, API definitions, wallet keys, signing, transfers or wallet creation are introduced. Three profile source files change. The code branch contains only this change, not this documentation or gift-crafting work. The PR has one consolidated commit, 16ebb5704d27ef4fdbf567471a99bd050bb134a1, with the same tested source tree a3045fdda9605f40c22487f2823f4f7df65b1511 as the original candidate.

## What still needs Telegram

The client cannot provide an assigned address when the server returns walletStateEmpty, nor make a server-disabled wallet available. Owner-initiated provisioning and account-wide address privacy require server/API support or clarification of existing server behavior.

The current public schema contains no wallet-specific privacy key. Removing the address from one screen would leave profile/API association paths available to other clients. The proposal covers profile cards, forward/reverse address lookup, force resolution, response caches and other identity-bearing wallet responses.

Hiding the Telegram association does not hide an already known blockchain address, public balance, transaction graph or previously disclosed information.

## Verification

Extracted production C++ logic compiled and passed 600 state combinations plus event/lifetime checks: 3,320 assertions using Qt Widgets 6.11.2 and the pinned rpl libraries. The unmodified production logic fails the owner-zero regression control. Patch applicability and whitespace checks passed.

These are component checks with synthetic session/data/painting adapters, not a full Telegram build, visual QA, server test, privacy implementation or real wallet transaction. See TESTING.md for exact scope and outstanding work.

## Suggested submission route

The Desktop change is a review candidate for fixing owner access through existing UI. Ask maintainers to confirm that an owner-only profile entry at zero is intended. Full Debug integration and real-account reproduction remain required before calling it ready to merge.

Submit the cross-client product/API request to Telegram's suggestion platform using SUGGESTION.txt. Telegram Desktop's contribution policy excludes new feature/UI implementations; a local privacy toggle would neither meet that policy nor enforce privacy. The API proposal is therefore kept separate from the code patch.
