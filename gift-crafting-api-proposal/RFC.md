# Proposal: crafting independent of export history and primary identity

Status: request for maintainer feedback. All method and status names here are illustrative; no new TL identifiers or working server endpoints are claimed.

## Objective and scope

Provide a supported path for every existing, unconsumed instance in a craft-enabled base gift type, regardless of prior export/import history. Include all-TON sets and authorized channel-owned gifts. Keep a single owner per operation initially; multi-owner recipes would require a separate consent design. Temporary cooldowns, ownership, valid recipes and exclusive consumption remain necessary.

The current restrictions and unresolved cases are in [ELIGIBILITY.md](ELIGIBILITY.md). This proposal deliberately does not remove checks from current clients or pretend an external NFT has ceased to exist. Existing Desktop fixes remain independent.

## Result identity and recipes

One possible solution to the primary-identity constraint is a fresh collectible identity for every successful operation. Allocate a new ID, slug and serial; record immutable provenance linking it to consumed canonical inputs. All ingredients are peers: ordering must not change eligibility or odds. Maintainers must decide serial accounting, old-link behavior, metadata representation and whether a different identity design is preferable.

Expose a versioned recipe keyed by base `gift_id`, with enabled state, supported ownership/custody modes, input categories, result model availability and exact success probability. Previously crafted outputs need an explicit policy. Missing chance metadata must produce an explainable status rather than an invented client estimate. Recipe changes before commit require re-preparation; changes after commit cannot alter the recorded outcome.

Candidate enumeration should support owner context and pagination, with statuses such as ready, cooldown with time, wallet authorization required, channel permission required, listed, reserved, consumed and recipe unsupported. Distinguish the asset owner from a profile displaying it. Server-side canonicalization must reject two aliases of the same asset.

## Proposed operation contract

1. **PrepareCraft(owner, inputs, recipe_version, request_key)** validates the request and creates an expiring, exclusive reservation. It returns an operation ID, canonical inputs, odds, owner/result destination and custody requirements. It does not consume assets or draw an outcome. The confirmation view lists all assets that may be irreversibly consumed and any fees.
2. **Obtain TON custody** through a Telegram-supported contract and an owner-authorized transfer. Verify the collection, canonical NFT identity, current ownership, expected contract/network and finality. Any signed authorization must bind the exact operation, inputs, nonce and expiry. Custody must exclude concurrent sale, withdrawal, transfer and reuse. This stage requires actual contract design and review; it is not provided by the model.
3. **CommitCraft(operation_id)** revalidates permissions, ownership, cooldown, listing/reservation status, recipe and verified custody. Only after all checks succeed, persist one irrevocable spend decision and one outcome. Use durable settlement/recovery across the service and TON; do not assume a database transaction can atomically commit on-chain actions. Publish a result only after all inputs have been consumed or irreversibly disabled by the agreed custody contract.
4. **GetCraftOperation(operation_id)** returns the durable status after timeouts or client restarts. Terminal responses identify consumed inputs and the optional fresh result. A completed unsuccessful craft is distinct from a validation rejection or settlement still in progress.
5. **CancelPreparedCraft(operation_id)** releases reservations before commitment and initiates idempotent return of any deposited custody. Expiration uses the same recovery path. After commitment, cancellation must not undo spent inputs or allow a reroll; the recorded operation must finish settlement.

Suggested service states: prepared; returning custody after cancellation; cancelled; committed/settling; succeeded; completed unsuccessful. A settlement incident remains visible and recoverable, not a fabricated terminal failure. Define operational alerts and reconciliation for permanently conflicting receipts. An automated retry alone cannot repair contradictory external ownership records.

## Retries and consistency

- Scope preparation keys to the authenticated actor; bind a key to canonical owner, inputs and recipe version. The same payload returns the original operation, including a cancelled or completed one. A different payload with the same key is rejected. Quote expiry is fixed by the original operation and never extended by retries. Define retention/tombstones before production deployment.
- Commit and recovery use the operation ID as their idempotency identity. Concurrent requests must share one persisted decision and outcome. Every settlement action is bound to an operation and canonical input and has a durable receipt.
- Reservation must cover every transfer, sale and custody exit path. Rechecking only the crafting table is insufficient if an external contract can still release an ingredient.
- Decide the irreversible commitment boundary so no caller can learn the outcome and then cancel, withdraw or request a new draw. Never disclose a stored outcome while settlement is incomplete. Production outcome generation needs an agreed trustworthy mechanism; the model's injected integer is not one.
- Validation failure must spend nothing. A crash after a valid irreversible commitment may leave partial settlement, which must resume from receipts. Never return such an operation to the pool of craftable gifts.
- Resolve aliases and duplicates before reservation. Preserve ownership/provenance mappings across exported and returned states instead of clearing historical identifiers.

## Client integration and rollout

Advertise the new operation and recipe capabilities before showing the flow. Preserve existing API checks for legacy clients/servers. Use explicit candidate explanations and server-provided quotes. Show settlement progress and recover by operation ID after a timeout; do not silently start a second legacy craft when commit status is uncertain.

Return sufficient updates for Desktop, Android, iOS and older clients to reconcile consumed ingredients and the new result. Do not infer success by matching an ingredient slug. Keep any explicit legal or financial consent in the product flow required by the eventual implementation.

Suggested staging: first clarify and test export-return eligibility and explain missing candidates; then agree result identity/operation types; then add verified TON custody and channel support; finally enable per-type recipes after integration tests. No stage should promise universal availability before the required server and contract work exists.

## What the executable model covers

`model.py` uses two separate SQLite ledgers, one for the service and one fake settlement adapter. Tests cover exclusive reservation, one persisted outcome, idempotent receipts, crash recovery, and at most one fresh output. The model uses one local filesystem, SQLite locking and synthetic identifiers. It does not model distributed consensus or network finality.

Important simplifications:

- `verified_ton_inputs` is a **test-only trusted-adapter assertion**, not user-supplied proof or a public API. No signatures, wallet operations, actual escrow or collection verification are implemented.
- `MockSettlement` assumes exclusive custody was already acquired. Its separate ledger provides durable fake receipts for all inputs, including off-chain fixtures. An external conflict intentionally leaves the operation committed with no result; operator reconciliation is out of scope.
- Preparation in this model holds only service reservations. Cancellation/expiry tests release those reservations; they do not test returning deposited NFTs.
- Canonical IDs, recipe data, times and permissions are fixtures. The model has no alias resolver, real channel permission service, candidate pagination or transport authentication.
- Probability is the sum of fixture contributions with values above 1000 rejected. Production aggregation and per-category odds remain maintainer decisions. `draw` defaults to zero for deterministic tests; there is no production randomness or fairness implementation.
- Fresh result IDs are synthetic. There is no serial allocator, slug compatibility, metadata publication, client integration or minted NFT.
- Tests simulate exceptions followed by re-opening both ledgers. They do not simulate power loss, storage corruption, OS process termination, chain reorganizations or arbitrary interleavings.

## Acceptance work requiring Telegram infrastructure

Confirm real export-return and channel behavior; implement versioned recipes and canonicalization; test actual custody/return flows, delayed confirmations and conflicting transfers; validate outcome generation and irreversible commitment; test signed authorizations, nonce expiry and contract/network mismatch; cover service failover and persistence faults; run complete client builds and end-to-end user flows with test gifts. The local model results cannot substitute for these gates.

## Questions for maintainers

1. Which returned gifts and previously crafted outputs are intentionally excluded today, and what policy should apply to them?
2. Is fresh result identity acceptable, including numbering and links to consumed gifts?
3. What supported custody/consumption mechanism can include an all-TON set and safely return pre-commit deposits?
4. Which channel rights authorize preparation, commitment and recovery, and who owns the result?
5. Which team/venue should own protocol and contract review, and which public integration tests can contributors run?
