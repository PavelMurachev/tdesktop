# Current evidence and proposed eligibility

Checked 2026-10-27. "Collection" below means the underlying gift type (`gift_id`), not a user's named profile collection. The private server implementation has not been inspected and no live crafting request was made.

| Case | Evidence / current limit | Proposed treatment |
| --- | --- | --- |
| Ordinary owned gift | Existing API requires usable inputs of one base type, 1–4 inputs, and elapsed crafting cooldown [1]. | Preserve these checks; obtain exact odds from a versioned server recipe. |
| Gift currently on TON in the first slot | Explicitly excluded by the documented method; successful crafting reuses that slot's ID [1]. Desktop also checks `giftAddress` [3]. | Use a fresh result identity and verified custody/consumption; remove the designated primary in the new protocol. |
| All inputs currently on TON | No possible first slot under the documented rule [1]; this is an inference from that rule, not a live server test. | Supported only after a Telegram-approved custody path has reserved every NFT. |
| Exported in the past, now returned | The cited method does not establish a blanket ban based on export history. Persistence and interpretation of `gift_address` after return need confirmation. | History alone should not exclude an otherwise eligible instance; keep provenance. |
| Channel-owned gift | Desktop's `CanCraftGift` currently allows the self-owner path and explicitly excludes channels [4]. This is client evidence, not proof of all server behavior. | Explicit owner context and current channel permissions; result remains channel-owned. |
| Hosted/displayed NFT | Display on a profile does not establish the wallet custody needed by this design. Existing hosting and ownership semantics need maintainer confirmation. | Require actual owner authorization; no spending based solely on the host profile. |
| Missing or zero `craftChancePermille` | Desktop's entry check rejects it [4]. Missing metadata does not prove an instance should have a particular chance. | Explicit server eligibility status; assign odds to each supported category. Zero-chance fixtures in the model only exercise outcome boundaries. |
| Previously crafted output | Re-entry eligibility and probability policy are not established by the evidence collected here. | Maintainers must define a recipe for this category to meet the broad goal; never invent a chance client-side. |
| Gift omitted from candidate list | `payments.getCraftStarGifts` returns owned craftable gifts for a type [2]. Omission alone does not explain the cause. | Return candidate status/reason, required next action and availability time. |
| Unsupported type, foreign owner, duplicate or consumed input | Outside the intended scope; server policy and ownership remain authoritative. | Reject before any spend decision. |
| Active listing, reservation or transfer | Full server behavior was not measured. The new design requires exclusive availability across these operations. | Delist or complete the conflicting operation with authorization, then retry preparation. |

## Sources

1. [payments.craftStarGift](https://core.telegram.org/method/payments.craftStarGift): current method contract and parameter description.
2. [payments.getCraftStarGifts](https://core.telegram.org/method/payments.getCraftStarGifts): candidate retrieval and pagination.
3. [Desktop crafting implementation at reviewed baseline](https://github.com/telegramdesktop/tdesktop/blob/dd2a96c356971a0781f142826fcc212273f90098/Telegram/SourceFiles/boxes/star_gift_craft_box.cpp): `ShowSelectGiftBox` and `ShowCraftAddressError`.
4. [Desktop entry eligibility at reviewed baseline, line 1110](https://github.com/telegramdesktop/tdesktop/blob/dd2a96c356971a0781f142826fcc212273f90098/Telegram/SourceFiles/settings/settings_credits_graphics.cpp#L1110): `CanCraftGift`.

The reviewed source baseline is pinned for reproducibility; this matrix is not a claim about every released client version. API pages may change independently. The phrase "Only users can use this method" is not, by itself, evidence that an authorized user cannot act on channel-owned assets.
