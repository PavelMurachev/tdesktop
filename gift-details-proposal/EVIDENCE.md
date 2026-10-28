# Evidence and unknowns

Checked on 2026-10-28. Upstream dev was `f985723b552b30fe1c17d377d57f44e61a15a8c4`. Evidence names functions rather than unstable line numbers.

| Observation | Source | What it establishes |
| --- | --- | --- |
| The removal quote is conditional server data | [savedStarGift](https://core.telegram.org/constructor/savedStarGift) and [gifts API](https://core.telegram.org/api/gifts) | `drop_original_details_stars` enables paid removal of the original-details attribute. No universal post-export policy is documented by this field alone. |
| The invoice already exists | [inputInvoiceStarGiftDropOriginalDetails](https://core.telegram.org/constructor/inputInvoiceStarGiftDropOriginalDetails) | The operation takes an `InputSavedStarGift`; it does not specify a client-selected price or a text-only option. |
| The original attribute includes more than text | [starGiftAttributeOriginalDetails](https://core.telegram.org/constructor/starGiftAttributeOriginalDetails) | Sender, recipient, date and optional message are one attribute. |
| The client requires a collectible and positive quote | [UniqueGiftCanRemoveDetails and UniqueGiftRemoveDetailsHandler](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/settings/settings_credits_graphics.cpp) | The inspected gate contains no address/export test; the handler uses the existing invoice and clears local details after a Paid result. |
| The quote is parsed from owned-gift responses | [FromTL for MTPsavedStarGift](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/api/api_premium.cpp) | An absent quote becomes zero in this client representation. Its absence cannot safely be replaced by an invented price. |
| Three reference forms are already supported | [InputSavedStarGiftId](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/api/api_credits.cpp) | With a usable saved reference it chooses user/channel; without one and with a collectible it falls back to the slug. This does not prove server acceptance for every custody state. |
| Removal has confirmation UI | [MakeUniqueDetails and AddStarGiftTable](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/boxes/gift_premium_box.cpp) | The removal handler is attached to the original-details row and a confirmation box displays the cost. |
| A hosted profile can differ from ownership | [starGiftUnique](https://core.telegram.org/constructor/starGiftUnique) | For hosted gifts the host and TON-wallet owner can differ. A profile entry alone is not authorization to modify NFT metadata. |

The source snapshot and seven Git blob identifiers are recorded in source-manifest.json. Source diagnostics verify those blobs before extracting functions.

## User report, not independently reproduced

A gift's removal action disappears or is unavailable after export to TON, including after return. No affected gift identifier, client version, owned-gift response, invoice error or real-account reproduction was obtained. Do not state that a particular backend predicate has been confirmed or that the failure affects every exported gift.

## Maintainer-only evidence still needed

- Which server condition withholds the quote or rejects the invoice for an affected returned gift?
- Does its authoritative current metadata permit original-detail mutation, and is that different from retained historical metadata?
- Which current representations and external indexers must refresh, and what prevents a later import from restoring removed fields?
- Can the compatible existing invoice support all returned gifts, or is an extended state/result contract required?
- What supported ownership proof or custody route is available for gifts that remain in external wallets?

Public Desktop code cannot answer these backend and deployed-contract questions. No production gate is removed in this package because doing so would assert unsupported availability without changing the actual service.
