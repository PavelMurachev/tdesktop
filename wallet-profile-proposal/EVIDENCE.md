# Source evidence and limits

Inspected upstream revision: [f985723b552b30fe1c17d377d57f44e61a15a8c4](https://github.com/telegramdesktop/tdesktop/commit/f985723b552b30fe1c17d377d57f44e61a15a8c4), schema layer 232. Findings describe that source revision, not verified production backend behavior.

| Observation | Source and symbol | Implication |
| --- | --- | --- |
| A missing card becomes numeric zero; setContent hides balances at or below zero. | [info_profile_balance_pill.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/info/profile/info_profile_balance_pill.cpp), BalancePill constructor and setContent | A valid zero is not distinguished from absence in this UI. |
| Card view refuses to open without a wallet card. | [wallet_card_view.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/wallet/wallet_card_view.cpp), ShowCardView | Showing an empty control alone is insufficient; a fallback route is needed. |
| Address access requires Presence::Ready, not positive balance. applyState accepts a parseable walletState at zero. | [wallet_session.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/wallet/wallet_session.cpp), addressFriendly and applyState | Existing ready zero wallets can use existing receiving UI. |
| Receive checks address length; Add Funds opens it and follows readiness. | [wallet_content.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/wallet/wallet_content.cpp), ShowWalletReceiveBox and Content::setupPinned | No balance-gated transfer or new deposit API is needed for this client case. |
| The wallet menu follows walletAvailable, which reads wallet_available. | [window_main_menu.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/window/window_main_menu.cpp) and [main_app_config.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/main/main_app_config.cpp), AppConfig::walletAvailable | The reporter's missing entry cannot be attributed solely to a zero-balance client condition. |
| walletStateEmpty contains no address and may indicate creating. | [api.tl](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/mtproto/scheme/api.tl), WalletState | Missing/provisioning is different from ready with zero. No address should be fabricated. |
| userFull may include wallet.card with address and balance. | Same api.tl, userFull and wallet.card | Profile disclosure requires server filtering for denied viewers. |
| wallet.getUserAddresses supports user IDs, addresses and force. The client supports forward lookup, reverse ownership lookup and funded-sender forced resolution. | Same api.tl and [wallet_user_addresses.cpp](https://github.com/telegramdesktop/tdesktop/blob/f985723b552b30fe1c17d377d57f44e61a15a8c4/Telegram/SourceFiles/wallet/wallet_user_addresses.cpp), forceResolve, resolveOwner and sendChunk | Privacy must cover every association path; hiding the profile control alone is insufficient. |
| No wallet-specific inputPrivacyKey, privacyKey or globalPrivacySettings flag appears. | Same api.tl | This revision does not expose the requested privacy setting. It does not prove there is no unpublished server support. |

The separate settings currency entry is based on credits().tonBalanceValue(). It is not the native wallet profile feature and is not modified.

The code uses card balance when a valid card exists, retaining existing presentation behavior. The private balance is a fallback only for the owner's missing card. It does not create or publish a wallet.card object.

## Unknowns requiring maintainers

- Whether every supported account already has a provisioned native wallet; what triggers provisioning.
- Whether wallet.getState can initiate provisioning or only reports it, and whether a supported owner-initiated creation flow already exists.
- Whether production users.getFullUser supplies a zero-balance card, omits it, or applies another threshold.
- Rollout/region/account eligibility and the reporter's exact client/version.
- Intended owner profile visibility and any unpublished wallet privacy contract.
- How identity metadata in transaction peers, gifts/NFTs and cached profile cards should behave under a new privacy rule.

No authenticated Telegram API requests, balance queries for real users, key access, forced resolution or transfers were performed in this investigation.
