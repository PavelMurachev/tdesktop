# Proposal: owner access at zero and wallet association privacy

This is a proposed contract for Telegram maintainers, not an implemented backend, a deployable privacy patch, or a declaration that any new RPC already exists. No constructor IDs or invented production API calls are supplied.

## Owner access

For accounts eligible for the native wallet, expose the owner's assigned receiving address and the existing Receive/Add Funds flow independently of balance and public-card visibility.

Distinguish these states in the UI and API:

| State | Owner experience |
| --- | --- |
| Loading | Show loading; do not invent an address or display a false zero. |
| Ready, zero or positive balance | Show the authenticated owner's address, copy/QR and funding entry. |
| Missing | Offer explicit owner-initiated setup if supported; explain availability otherwise. |
| Provisioning | Show progress with bounded retry/recovery, without creating duplicates. |
| Unavailable | Explain availability; do not bypass account/region/service policy. |
| Invalid address/error | Show a recoverable error; do not offer a deposit address. |

If existing RPCs cannot provide owner-initiated setup, provide an authenticated, self-only, idempotent operation or a documented equivalent. Concurrent devices and retries must resolve to the same assigned wallet. Starting setup must not replace an existing wallet, rotate keys, import a wallet, move funds or change custody without the corresponding explicit consent. Availability rules remain server-controlled.

The owner should be able to receive funds without asking another Telegram user to activate the wallet. A private owner view must not implicitly publish their wallet.card to other users.

## Account-wide privacy

Proposed setting: Who can find my wallet from my Telegram account? Everyone / My Contacts / Nobody, with existing Telegram-style exceptions if supported. The authenticated owner retains access in every mode. A privacy-preserving default and migration explanation should be decided by Telegram; do not silently promise retroactive anonymity.

Use server-managed privacy rules, not a local device preference. Only show a saved state after the server confirms it. An unavailable API or failed save must produce an honest error and preserve the last confirmed setting. Older clients must also receive filtered responses.

For a viewer denied by the rule:

- Omit the public wallet.card, including its address, balance and decorations that could expose a wallet association.
- Do not return the user's address through forward wallet.getUserAddresses lookup, including mixed batches and force requests.
- Reverse address lookup must not return the denied user association or put identifying users into auxiliary response vectors. Public cryptographic data may remain available where necessary without Telegram identity metadata.
- Force resolution must not override privacy, provision an unwilling recipient's wallet, or disclose a denied recipient's mapping. Use an agreed privacy-respecting failure/result contract.
- Audit wallet transaction peer metadata, search/autocomplete, notifications, links, gifts/NFT profile associations and other APIs for equivalent Telegram identity mappings. Document legitimate counterparty disclosures and independently public gift associations explicitly.

Ordinary on-chain transfers reveal addresses to counterparties and the public ledger. Sending by Telegram identity may necessarily reveal a destination address to the sender; denied discovery should require an explicitly shared receiving address/payment request, or a separately approved consent flow. Do not claim that ordinary blockchain payments can keep their destination address secret.

Privacy changes must invalidate relevant profile and forward/reverse lookup caches across devices and session-scoped data, including known-empty answers. Version/generation checks must stop older in-flight responses from restoring a mapping after a newer denial. Previously copied data, past transactions and third-party records cannot be recalled.

## Client integration after the server contract is available

Use Telegram's established privacy-settings framework and generated schema. Clearly label the protection as Telegram profile/address association visibility. Retain owner receive access and distinguish zero from absent state. Ensure UI navigation never publishes private wallet state as a public card.

The included Desktop candidate implements only owner profile access with existing APIs. It introduces no privacy setting or provisioning operation.

## Acceptance scenarios for Telegram's backend and integration tests

1. An eligible owner with a ready zero wallet can copy a valid receiving address without receiving a prior transfer.
2. Missing and simultaneous setup requests settle to one wallet; retries do not replace it or change custody.
3. With Nobody selected, a second account receives no wallet.card or forward/reverse mapping through any supported association lookup, including mixed batches and force.
4. Contacts/exceptions are evaluated on the server, with documented precedence and block behavior.
5. The owner still receives their state/address in every privacy mode, including at zero.
6. A failed privacy save leaves the confirmed state visible and does not claim protection.
7. A privacy change on device A updates device B and invalidates stale client/server caches; delayed responses cannot resurrect a denied association.
8. An older or modified client cannot regain associations by omitting UI checks.
9. Gifts/NFTs, transaction peers and auxiliary user vectors honor the documented identity-disclosure policy; necessary counterparty/public-chain disclosure is explained.
10. Network loss, sign-out/account switch and service unavailability cannot mix wallets between accounts or display a fabricated deposit address.
11. Public card customization still works for allowed viewers, and hiding a card does not delete the owner's configuration.
12. Public blockchain address history remains accessible to anyone who already knows that address; the UI does not promise otherwise.

None of these backend scenarios has been executed against Telegram's service in this work.
