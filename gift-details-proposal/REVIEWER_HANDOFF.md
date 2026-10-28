# Maintainer handoff

Request: remove original details from collectible gifts independently of historical mint/export status, especially after return from TON. Retain the normal fee, current-owner checks and explicit confirmation. The user's original report is not independently reproduced.

Start with EVIDENCE.md and the pinned `UniqueGiftCanRemoveDetails`, `UniqueGiftRemoveDetailsHandler`, `FromTL(MTPsavedStarGift)` and `InputSavedStarGiftId` functions. There is no identified Desktop export-history condition to delete for this operation. Do not submit a client PR that invents a quote or clears details without accepted payment.

Backend owners should identify the quote/settlement policy for one affected returned gift, review whether the current metadata authority permits the change, and implement the smallest compatible change described in API_PROPOSAL.md. Public client code is insufficient to provide a mergeable backend diff. No new public TL constructor, method name or error string in this package is claimed to be a Telegram API. Model error strings are illustrative.

Run the existing pinned-source diagnostics and offline acceptance suite as documented in TESTING.md. Extend backend integration tests with actual returned gifts, different current owners, authorized channels and import/export races. The model's `ever_exported` flag is deliberately irrelevant to eligibility, and its external-custody rejection is a missing supported-flow boundary, not completion of a direct TON removal feature.

The SQLite model is a disposable behavioral reference, not code to deploy into Telegram or a payment system. In production, map its transaction identity and atomicity requirements onto the existing payment ledger and authorization/custody architecture. Confirm distributed failure handling, balance currency, quote/UI consistency and update propagation before release. Current deployed contracts and indexers are untested here.

This is a standalone platform proposal. Existing crafting and wallet PRs should not be expanded to contain it.
