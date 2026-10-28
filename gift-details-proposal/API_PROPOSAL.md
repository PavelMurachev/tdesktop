# Lifecycle-independent removal of original collectible gift details

## Minimal compatible backend change

For a live collectible with an original-details attribute in Telegram custody, evaluate the current owner's authority and the normal product eligibility rules without a permanent exclusion based solely on previous export, mint or return history. When supported, return a current `drop_original_details_stars` quote in the existing owned-gift representations and accept the existing `inputInvoiceStarGiftDropOriginalDetails` payment flow. Keep existing positive-fee clients compatible; do not treat an absent field as a zero-price permission.

This is a proposed policy change, not an identified line of Telegram backend code. First reproduce an affected returned gift and establish whether the field is absent, the invoice is rejected, or metadata mutation is unsupported. If the server already returns a valid quote but a particular client fails to surface it, handle that separately as a reproducible client bug.

Required behavior for a returned gift: removal availability and fee policy match an otherwise equivalent never-exported gift. A previous chain address is not itself a reason for permanent ineligibility. Preserve identity, collectible attributes, ownership and collection membership; do not burn, replace or remint the gift as a shortcut.

## Authorization, payment and consistency

1. Resolve user, channel and slug references to one stable gift identity. A slug is an identifier, not permission. Verify current owner or explicitly authorized channel manager at quote and settlement. A host is not necessarily an owner.
2. Reject missing, consumed/burned and otherwise unavailable gifts. If details are already absent, return the existing result or an explicit no-op without a further debit.
3. Bind a server-side quote to actor, gift identity, ownership/details revision, quoted fee and expiry. Revalidate at settlement. On a price change, require the user to see and confirm a new quote; do not silently raise the debit.
4. Keep the normal Stars payment and explicit destructive-operation confirmation. Explain that sender, recipient, date and greeting will all be removed. No fee guessing, automatic purchase, arbitrary wallet signing or billing bypass.
5. Use the production payment service's durable transaction identity. Retrying a committed operation returns its receipt without another debit. Reusing that identity with different actor/gift/invoice data must fail. Competing operations remove once and charge at most once.
6. Debit and authoritative detail removal must be atomic within a single service transaction, or use a durable coordinated state machine with reconciliation if multiple services are involved. A pending chain mutation is not final success. Do not charge for a permanently failed removal; use the production refund/recovery policy.
7. Publish authoritative gift updates to all active sessions and relevant views. Re-fetch after reconnect; do not rely on a single view's optimistic clearing. Add a durable removal marker so import, resale, transfer, export or old cached representations cannot restore the original details in Telegram's current representation.

These requirements specify new behavior. The SQLite model approximates a single-database transaction only; it does not implement Telegram's payment ledger, authorization system, distributed transactions or account sessions.

## TON-held gifts and persisted metadata

Prefer implementing and validating returned gifts first. For a currently external NFT, either require an official supported return and then use the same flow, or add an explicitly specified wallet-authorized operation. A direct wallet operation requires an authoritative ownership proof bound to gift, intended action, network, nonce and expiry, plus replay prevention and a custody/ownership recheck. No such direct operation is implemented in this package.

Establish what the gift's deployed contract and current metadata authority actually permit before promising external metadata updates. Determine who can update current metadata after minting and after return, and how ownership races and indexer refreshes are handled. If the deployment cannot update the current data, disclose that and propose a supported protocol/contract change. Simply hiding information in one client is not global removal.

Already published blockchain history, downloaded copies and earlier chat messages cannot be assumed erased by removing an attribute from Telegram's current gift record. Tell users which current surfaces change. Do not market the operation as retroactive deletion of all public history.

## Scope boundaries

The target is collectible gifts with `starGiftAttributeOriginalDetails`, including previously exported gifts from every collection. A regular non-collectible gift message uses different data and is not covered by the existing invoice. A message-only removal option would also require an explicit new server contract; do not claim the existing operation preserves the sender/date while removing just text.

## Acceptance and rollout

Validate with maintainers' test gifts: never exported; returned to the same owner; returned to a new owner; returned to an authorized channel; transfer or export between quote and settlement; absent details; consumed gift; insufficient balance; fee/permission change; cancellation; duplicate submission; concurrent submissions; restart and lost response.

Check updated state across supported mobile/Desktop/web clients, gift links, owned-gift lists, service messages and relevant official metadata/indexer surfaces. Confirm the intended historical-data scope in each view rather than erasing user chats implicitly. Verify that details do not reappear after another export/return cycle. Release server eligibility first or behind the established capability mechanism; test old clients and unsupported cases. A full client build and server-backed end-to-end run remain required before calling this implemented.
