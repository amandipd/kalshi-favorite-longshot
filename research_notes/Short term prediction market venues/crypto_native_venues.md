# Crypto-native and on-chain short-term price prediction venues (excluding Polymarket), as of 13 Oct 2026

Scope: venues offering minute-to-hour crypto (or oracle-priced) up/down or strike binaries, assessed for a US-based bot that buys the heavy favourite (about 90-99c) partway through a short window and holds it to settlement. Research only: no wallets connected, no accounts created. Sources are 2026 unless they're labelled with an older date. "Search summary" means the fact came from a search-engine digest whose underlying page was not opened, so treat it with lower confidence.

## 1. Mechanism (CLOB vs AMM vs parimutuel) and how a favourite-buyer's expected value works on each

### Takeaway
Only two venues run a real central limit order book (CLOB: a book of resting buy and sell limit orders matched by price and time) where you can buy a favourite at a known price partway through a window: Limitless (Base) and Hyperliquid HIP-4. Both bar US persons. PancakeSwap Prediction is a parimutuel pool (everyone's stakes are pooled and the payout ratio is set only when betting closes). It also closes betting before the 5-minute window starts, so a buy partway through the window is impossible. Overtime/Thales Speed Markets set the strike at the current price, so every position is roughly 50:50 and no 95c favourite exists.

### Cited findings
**Limitless Exchange (Base L2)**
- Shares trade between $0.01 and $0.99 USDC, and each YES+NO pair is fully collateralised by $1.00 USDC. Winners get $1.00, losers get 0, and 1 YES + 1 NO can be redeemed for 1 USDC before resolution. Sources: [Limitless docs](https://docs.limitless.exchange/); [What is Limitless](https://docs.limitless.exchange/user-guide/what-is-limitless)
- Most markets use a CLOB with separate Yes and No books. A few use an AMM (automated market maker: a pricing formula that quotes against a liquidity pool), with "AMM Trading (Server Wallets)" documented separately. Sources: [Limitless docs index](https://docs.limitless.exchange/llms.txt); [Limitless fees](https://docs.limitless.exchange/user-guide/fees.md)
- Matching is off-chain and settlement is on-chain. The order-event stream has an "OME" (off-chain matching engine) source and a "SETTLEMENT" source. MATCHED arrives "the moment the engine fills your order (before the on-chain transaction)". MINED is terminal success with a txHash. FAILED means the trade "did not execute and no funds moved". Source: [Limitless WebSocket order events](https://docs.limitless.exchange/developers/websocket/order-events.md)
- Orders are EIP-712 signed messages (EIP-712 is a standard for signing structured off-chain data with your wallet), and the venue's exchange contract is the verifying contract. Order types are GTC, FOK and FAK. Sources: [Limitless developers intro](https://docs.limitless.exchange/developers/introduction); [Limitless API intro](https://docs.limitless.exchange/api-reference/introduction)
- Some markets set `settings.takerDelayMs`, which holds taker orders for a time before filling them (a "speed bump"). Source: [Limitless order events](https://docs.limitless.exchange/developers/websocket/order-events.md)
- The docs include a "Migrate from Polymarket" guide, which suggests a Polymarket-like CTF/CLOB design. Source: [Limitless developers intro](https://docs.limitless.exchange/developers/introduction)

**Hyperliquid HIP-4 outcome markets (HyperCore L1)**
- HIP-4 contracts are fully collateralised and settle within a fixed range. Yes settles to `settleFraction` quote tokens and No to `1 − settleFraction`. The Yes and No books are merged, so a buy of Yes at p equals a sell of No at 1−p, with price-side-time priority. Users can split and merge Yes/No. Source: [HIP-4 spec (Hyperliquid)](https://hyperliquid.gitbook.io/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets)
- Each market opens with a 15-minute single-price auction (it clears at the price that maximises matched volume) and then trades continuously on the CLOB. There is no liquidation engine and no funding. Source: [Blockworks Research, 4 May 2026](https://blockworks-research.beehiiv.com/p/hip4-goes-live)
- Settlement is a single call by a deployer-designated broadcaster that posts 0/1 (or a fraction). Trading halts, open orders are cancelled, and payouts happen in the same block. Source: [Blockworks Research](https://blockworks-research.beehiiv.com/p/hip4-goes-live)

**PancakeSwap Prediction (BNB Chain)**
- Payouts come from a pool. UP payout ratio = (UP pool + DOWN pool) ÷ UP pool, and DOWN works the same way. Winners share the total pot minus a 3% fee. If nobody bets the other side and you win, you get back 97%. Source: [PancakeSwap docs: Prediction](https://docs.pancakeswap.finance/products/prediction)
- Bets lock once placed and can't be changed. UP wins if Closed > Locked, and DOWN wins if Closed < Locked. On a tie (Locked = Closed) "the house wins all bets". Source: [PancakeSwap docs](https://docs.pancakeswap.finance/products/prediction)
- Rounds run in a lock period where positions are taken, then a 5-minute live period, and settle on the Chainlink price at the end compared with the start. Source: [pm.wiki comparison (third party)](https://pm.wiki/compare/pancakeswap-prediction-vs-spend-market)

**Overtime (formerly Thales) Speed Markets (Arbitrum / Optimism / Base)**
- The strike is a snapshot of the current Pyth price at purchase, so "all positions will have 50:50 implied probabilities". A winner gets "a 2x payout (minus the quoted LP fee and a fixed 2% Safebox fee)". Source: [DappRadar Speed Markets (undated; describes the Thales-era product)](https://dappradar.com/dapp/speed-markets)
- "Every position offers 50:50 odds", validated by Pyth Benchmarks pull oracles. Source: [Pyth case study, 21 Sep 2023 (old)](https://pyth.network/blog/innovative-markets-and-community-governance-with-thales-i-pyth-case-study)
- Thales has rebranded to Overtime (OVER). Overtime lists "speed markets" among its market types, next to sports products. Sources: [CoinMarketCap](https://coinmarketcap.com/currencies/overtime); [pm.wiki Overtime](https://pm.wiki/uk/projects/overtime-markets)

**Myriad Markets (Abstract / Linea / BNB Chain)**
- A third-party explainer describes Myriad as EVM contracts "combining … automated market makers (AMMs), and a newly introduced order book system". Source: [FinFeedAPI explainer](https://www.finfeedapi.com/blog/myriad-markets-explained)
- "Candles" are short-timeframe, automatically resolved crypto markets launched with USD1 pools on 14 Jan 2026. The launch article doesn't say whether they use an AMM, a pool or a book. Source: [Decrypt, 14 Jan 2026](https://decrypt.co/353044/world-liberty-financial-stablecoin-usd1-lands-on-prediction-market-myriad)
- Users can't challenge or vote on outcomes; Myriad decides winners from its own data feeds. Source: [HackerNoon commentary](https://sia.hackernoon.com/how-world-liberty-financials-usd1-is-rewriting-settlement-standards-in-prediction-markets)

**Other order-book venues**
- **Opinion (Opinion Labs, BNB Chain):** a community integration describes an on-chain order book with a WebSocket feed and EIP-712 signing. Source: [CloddsBot Opinion skill (third party)](https://tessl.io/registry/skills/github/alsk1992/CloddsBot/opinion)
- **Predict.fun (BNB Chain):** its developer docs include "Understanding the Orderbook". DefiLlama says it charges "taker-only trading fees … finalized at settlement and collected in USDT". Sources: [Predict API](https://dev.predict.fun); [DefiLlama Predict.fun](https://preview.dl.llama.fi/protocol/predict-fun)
- **Drift BET (Solana):** cross-margined with the Drift perps book, with "much thinner liquidity on any given event contract" (third-party 2026 view). Source: [MadeOnSol compare](https://madeonsol.com/compare/drift-bet-vs-metadao)
- **Hedgehog Markets (Solana):** started with match-the-odds or post-your-own-odds peer-to-peer markets, then added escrow and parimutuel pooled formats. Source: [Solana Compass](https://solanacompass.com/projects/hedgehog)

### Inferences
- **CLOB (Limitless, HIP-4, Opinion, Predict.fun):** you can see the ask (say 95c) and lift it partway through the window. Expected value (EV) per $1 share = P(win) − price − fees. Break-even win rate = price adjusted for fees and spread (worked numbers in Section 3). This is the only mechanism that matches the strategy's "buy the favourite mid-window at a known price".
- **Parimutuel (PancakeSwap):** you don't buy at a price. The final payout multiple is (1 − 0.03) × total pool ÷ your side's pool, fixed only when the round locks, and later bettors (often bots in the last block) can move it against you. If the favourite side ends with share s of the pool, break-even P(win) = s ÷ 0.97. For s = 0.95 that's 97.9%, and for s = 0.90 it's 92.8%. The 3% is charged on the whole pot, so for a favourite-backer it costs about 3% of the payout (roughly 2.9 percentage points of probability at s = 0.95). Ties go to the house, which is an extra loss mode. Most important, bets close before the 5-minute price window starts, so "partway through the window" doesn't exist on this venue.
- **Fixed-odds AMM at spot strike (Speed Markets):** the strike always equals the current price, so the bet is a near coin-flip paying about 2x less fees. A 95% favourite can't be bought. Chained or longer variants don't change that.
- **Pool-priced AMMs (Myriad and Limitless AMM markets):** the price comes from a formula. Buying the favourite near 95c moves the price up along the curve, so a $20-$500 ticket can pay well above the quoted mid on thin pools. The 95c price you see is only a marginal quote for the first share.
- **HIP-4's merged book** means No-sellers and Yes-buyers share liquidity, which helps fill quality. Settlement by a designated broadcaster is a single point of trust.

### Gaps
- Limitless does not publish its tick size or minimum order size in the pages fetched.
- No source was found on Myriad Candles' exact mechanism (AMM curve, pool or book) or on Myriad's fee rate.
- The current (2026) Overtime Speed Markets docs and contracts could not be retrieved (the GitHub paths returned 404). Whether payouts are still fixed near 2x, or now skew-priced, is unconfirmed.

## 2. Durations, underlyings, listing cadence and settlement oracle (exact rule)

### Takeaway
Limitless has the closest product: recurring 5-minute and 15-minute crypto up/down markets (Chainlink TWAP; TWAP is a time-weighted average price) plus hourly and daily markets (Pyth). HIP-4 is so far confirmed only for a daily BTC strike binary that settles at 06:00 UTC on Hyperliquid's mark price. PancakeSwap runs 5-minute BNB/BTC/ETH rounds on Chainlink. Probly (TxFlow L1, July 2026) advertises 5m/15m/1h/4h up/down markets but has little documentation.

### Cited findings
**Limitless**
- Market types are hourly, daily, weekly and custom ("nonstop hourly and daily markets" on crypto and stock prices). Sources: [What is Limitless](https://docs.limitless.exchange/user-guide/what-is-limitless); [Limitless docs](https://docs.limitless.exchange/)
- The API has a "Market Timeline" endpoint that looks ahead to "upcoming slots of a recurring market (e.g. 5-minute crypto)". A "Resolve Stable Slug" endpoint maps recurring slugs, such as an hourly BTC market, to the active market. Source: [Limitless docs index](https://docs.limitless.exchange/llms.txt)
- Resolution: **Pyth Network resolves the majority of markets, including crypto prices**, automatically at the deadline, using full feed precision (typically 8 decimals). **Chainlink TWAP is used for short-cadence crypto up/down markets (5-minute and 15-minute).** The "Price to Beat" is the TWAP captured at open, and the closing TWAP is read from the same stream at the deadline. It resolves **Up if close ≥ Price to Beat**, otherwise Down, so a tie goes to Up. If no report exists at the exact time, the first observation inside a tolerance window is used (window length not stated). If there's none, the market isn't auto-resolved. Misresolved markets are refunded under the refund policy. Source: [Limitless market resolution](https://docs.limitless.exchange/user-guide/market-resolution.md)
- There's an "Oracle Candlesticks" endpoint returning "Chainlink candlestick data for markets configured with Chainlink Data Streams". Source: [Limitless docs index](https://docs.limitless.exchange/llms.txt)
- Press coverage (May 2026) mentions 5-minute BTC up/down contracts, 15-minute crypto markets and one-hour commodities markets, plus currencies. Sources: [Public Gaming, 6 May 2026](https://www.publicgaming.com/news-categories-m/legal/15786-limitless-markets-submits-cftc-proposal-for-5-minute-digital-asset-event-contracts); [DeFi Rate, 5 May 2026](https://defirate.com/news/limitless-files-cftc-approval-after-record-1-66b-month/)
- An aggregator lists hourly markets with 30- and 60-minute resolution windows on crypto, stocks and commodities. Source: [pmxt.dev (vendor page, undated)](https://pmxt.dev/limitless-api)
- Planned expansion to 15-, 10- and 1-minute timeframes was reported (aggregator, Feb 2026). Source: [pm.wiki Limitless (search summary)](https://pm.wiki/uk/projects/limitless-exchange)

**Hyperliquid HIP-4**
- The only market described in the spec is a recurring binary that settles daily at 06:00 UTC on the HyperCore BTC mark price. Multi-outcome markets are not in the initial mainnet release, and further markets are to "roll out in stages". Source: [HIP-4 spec](https://hyperliquid.gitbook.io/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets)
- From 2 to 18 May 2026 there were 18 daily BTC binaries, each asking whether BTC closes above a strike at 06:00 UTC the next day. Source: [Arrakis, data to 20 May 2026](https://arrakis.finance/blog/hip-4)
- Recurring configs use an `outcomeMeta` field. One example uses `period:1d`, and a price-bucket example uses `period:15m`. The 15m example is a config string, not evidence of a live 15-minute market. Source: [search summary of HIP-4 developer guides](https://www.dwellir.com/blog/what-is-hyperliquid-hip-4)
- Some sources say the first rollout covered "recurring BTC and HYPE" markets, and some report a 00:00 UTC settlement time and USDC rather than USDH collateral. These conflict with the spec (06:00 UTC). Sources: [GoldRush changelog](https://goldrush.dev/docs/changelog/20260504-hip-4-outcome-markets-now-streaming); [FinFeedAPI](https://www.finfeedapi.com/blog/hyperliquid-hip-4-outcome-markets-prediction-markets)

**PancakeSwap Prediction**
- Rounds are 5 minutes and roll continuously. **Chainlink sets the Lock and Closed prices, updated "up to 20 seconds" apart.** Binance/TradingView feeds are used only for the UI. If the oracle fails, the round is cancelled and bets are refunded. Source: [PancakeSwap docs](https://docs.pancakeswap.finance/products/prediction)
- Live on BNB Chain: BNBUSD, BTCUSD and ETHUSD. CAKEUSD is paused. zkSync Era and Arbitrum are "temporarily paused". The Telegram Mini App offers BNBUSD only. Source: [PancakeSwap docs](https://docs.pancakeswap.finance/products/prediction)

**Overtime / Thales Speed Markets**
- The user picks an asset, a direction and an expiry "as short as 10 minutes into the future". Deployed on Arbitrum, Optimism and Base. Sources: [DappRadar (undated)](https://dappradar.com/dapp/speed-markets); [Arbitrum forum STIP (2023-24)](https://forum.arbitrum.foundation/t/thales-final-stip-round-1/16836)
- The oracle is Pyth Benchmarks (historically queryable prices, "updated every second"). Source: [Pyth case study, Sep 2023 (old)](https://pyth.network/blog/innovative-markets-and-community-governance-with-thales-i-pyth-case-study)

**Myriad Candles**
- "Short timeframes and instant auto-resolved payouts" on crypto prices. Exact durations and the oracle are not published in the coverage. Sources: [Decrypt, 14 Jan 2026](https://decrypt.co/353044/world-liberty-financial-stablecoin-usd1-lands-on-prediction-market-myriad); [MoonPay newsroom](https://www.moonpay.com/newsroom/myriad)

**New 2025-2026 launches of short up/down markets**
- **Probly on TxFlow L1 (July 2026):** "high-frequency Crypto 'Up or Down' rolling markets across BTC, ETH, SOL and XRP" on 5-minute, 15-minute, 1-hour and 4-hour cycles. Price-source markets "can settle immediately", with USDC payouts. 172 live markets were listed on 13 Jul 2026. Sources: [The Block press release](https://www.theblock.co/press-releases/408297/txflow-l1-introduces-probly-marking-the-next-stage-of-its-multi-application-ecosystem-with-prediction-markets); [Crypto Briefing](https://cryptobriefing.com/probly-announces-its-prediction-market-integration-with-txflow-l1/)
- **1win Markets "Crypto Live" (Sept 2026):** BTC, ETH, SOL, BNB, XRP and DOGE up/down rounds across five timeframes. It is a centralised betting operator, not an on-chain venue. Source: [Decrypt / press release](https://decrypt.co/379152/bitcoin-up-or-down-in-5-minutes-1win-markets-launches-crypto-live?amp=1)
- **Hyperliquid HIP-4 (May 2026):** daily BTC binaries, covered above.
- **Context only (excluded venue):** Polymarket's 5-minute crypto markets resolve on Chainlink data streams (Feb 2026 reports). Source: [search summary](https://next.io/prediction-markets/crypto/dogecoin/5-minute/)

**Drift BET, Hedgehog, Azuro, SX Bet**
- Drift BET launched in Aug 2024 with US-election markets. Crypto, sports and economics were planned. No evidence of short-window crypto up/down markets was found. Source: [The Block, Aug 2024 (old)](https://www.theblock.co/post/311888/solana-based-drift-protocol-launches-prediction-market)
- Hedgehog's markets are mostly sports. Source: [Astral Codex Ten, Aug 2022 (old; via search summary)](https://www.astralcodexten.com/p/mantic-monday-81522)
- Azuro is "prediction market infrastructure" mostly used for sports apps. No listing of short-window crypto price markets was found. Source: [DappRadar Azuro report](https://dappradar.com/blog/azuro-protocol-ecosystem-report)

### Inferences
- For the strategy, Limitless's **5-minute and 15-minute Chainlink-TWAP markets** and **hourly Pyth markets** are the closest structural match on any on-chain venue. TWAP settlement smooths the final print, so a favourite late in the window is less exposed to one last-second tick than with a single-print close. That cuts both ways for a favourite-holder.
- HIP-4 currently offers no minutes-to-hour windows. Its only confirmed product is a once-a-day BTC strike binary, which doesn't fit the strategy's horizon even if access weren't barred.
- On PancakeSwap the oracle points are Chainlink rounds "up to 20 s apart", which is coarse relative to a 5-minute window. The lock price may be a stale Chainlink round, not the exact spot price at lock.

### Gaps
- No source confirmed any HIP-4 market shorter than daily, or any non-BTC HIP-4 underlying, as of Oct 2026. Checking the live `outcomeMeta` endpoint would settle it.
- The width of Limitless's Chainlink TWAP window and its "tolerance window" aren't stated. Which assets get 5m/15m markets beyond BTC was not confirmed.
- No 2026 Speed Markets documentation was found for current min/max expiry, assets or buy-in caps.
- No oracle or exact-rule documentation was found for Probly or Myriad Candles.

## 3. Fees and the effective cost of buying a 95% favourite

### Takeaway
Limitless charges takers about 0.53% at a 95c buy (makers pay nothing), so break-even rises from 95.0% to about 95.5% before spread. HIP-4 charged zero protocol fees at launch, and whether a small close/settle fee is now on is disputed. PancakeSwap's 3% cut of the whole pot raises a 95%-share favourite's break-even to about 97.9%, before any adverse late flow. Speed Markets have no favourite to buy.

### Cited findings
- **Limitless CLOB taker buy fee** is price-dependent: **3.00% from $0.01-$0.50, falling to 0.40% at $0.999**, paid in outcome tokens. The table lists **0.53% at $0.95**. The curve "is not published as a closed-form formula", and each fill reports `effectiveFeeBps`. Sell fee: 0.45% at $0.01, peaking at 1.50% at $0.50, 0.42% at $0.999, paid in USDC. **Makers pay no fee.** AMM markets charge a flat 0.40%. Discounts come only from per-profile fee caps. Source: [Limitless fees](https://docs.limitless.exchange/user-guide/fees.md)
- Limitless pays "Daily USDC rewards for providing maker liquidity" (Maker Rebates page). Source: [Limitless docs index](https://docs.limitless.exchange/llms.txt)
- **HIP-4 launch fees:** "Fees are zero for outcome markets during initial testing." Builder codes can add builder fees on top. Source: [HIP-4 spec](https://hyperliquid.gitbook.io/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets)
- HIP-4 fee status after launch is disputed. A Sygnum note (per search summary) reports **7 bps taker / 4 bps maker charged only on close or settlement**. Dwellir says the close-side fee "is not yet published (5-50 bps)". Hypedexer docs say fills are "fee = 0" and that "SetOutcomeFeeScale … has not been activated". Sources: [Sygnum](https://www.sygnum.com/?p=22450); [Dwellir](https://www.dwellir.com/blog/hyperliquid-hip-4-mainnet-outcomes); [Hypedexer docs](https://docs.hypedexer.com/hip-4/overview)
- HIP-4 builder fees observed: Outcome.xyz 0 bps, Hyperbeat 25 bps, Liquidiction 150 bps. Source: [Arrakis, May 2026](https://arrakis.finance/blog/hip-4)
- Blockworks says front ends pay "4 to 7 bps on HyperCore, compared with 50 to 100 bps at external venues". Source: [Blockworks Research](https://blockworks-research.beehiiv.com/p/hip4-goes-live)
- **PancakeSwap: 3% of each round's total prize pool** (part funds CAKE buy-and-burn). Sources: [PancakeSwap docs](https://docs.pancakeswap.finance/products/prediction); [DefiLlama PancakeSwap Prediction (search summary)](https://defillama.com/protocol/pancakeswap-prediction)
- **Speed Markets:** about 2x payout minus the quoted LP fee and a fixed 2% Safebox fee (Thales-era description). Source: [DappRadar](https://dappradar.com/dapp/speed-markets)
- **Predict.fun:** taker-only fees, settled in USDT. Rate not found. Source: [DefiLlama Predict.fun](https://preview.dl.llama.fi/protocol/predict-fun)
- **Myriad:** about $1,319 in 30-day fees across BSC, Abstract and Linea. No rate published. Source: [DefiLlama Myriad fees](https://defillama.com/fees/myriad-markets)
- Base gas is described as "a few cents per transaction" (vendor page). Source: [pmxt.dev](https://pmxt.dev/limitless-api)

### Inferences (worked cost of a 95c favourite)
- **Limitless, taker at 0.95:** $100 buys 105.26 shares, minus 0.53% paid in shares, leaving about 104.70 shares. Break-even P(win) = 100 ÷ 104.70 ≈ **95.5%** (about +0.5 pp), plus half the bid-ask spread. **As a maker** (resting bid at 95c) the fee is 0% and maker rewards may apply, so break-even is 95.0%. Resting bids, though, get filled mostly when the favourite is weakening (adverse selection). The fee is lower near 99c (0.40% at 0.999), so the relative drag is similar across the 90-99c band.
- **HIP-4 at 0.95:** with zero protocol fees and a 0-bps builder, break-even is 95% plus half the spread (median quoted spread 53 bps, so about +0.27 pp). If the reported 7 bps close/settle fee is active, add about 0.07 pp.
- **PancakeSwap:** break-even = s ÷ 0.97, where s is the favourite side's final share of the pool. s = 0.95 gives **97.9%**, and s = 0.90 gives 92.8%. Gas for the bet and the claim comes on top. On the BNB Chain, gas cost per bet is likely small, but no source was found for an exact 2026 figure. Your own stake raises s, which lowers your own payout.
- **Speed Markets:** a coin-flip at about 2x less fees, so break-even is a little above 50% and there's no favourite to buy.
- **AMM markets (Myriad, Limitless AMM markets):** the fee (0.40% on Limitless AMM) plus the price impact of the curve. With pools this small (Myriad's entire fee take is about $1.3k/month), a $100-$500 buy near 95c would likely pay noticeably more than the quote.

### Gaps
- Whether Limitless users pay gas on CLOB fills, or the operator pays it, isn't stated.
- The exact HIP-4 fee schedule in force as of Oct 2026 could not be confirmed.
- Opinion's fee schedule could not be retrieved. Predict.fun's fee rate and the current Speed Markets LP fee are also missing.

## 4. Liquidity: volumes and depth; can a $20-$500 ticket fill?

### Takeaway
Limitless has real volume (about $1.66B notional in Apr 2026), but no per-market depth figures were found for its 5m/15m/hourly crypto markets. HIP-4 BTC dailies carry roughly $3M a day with a median 53 bps spread and deep books near settlement. PancakeSwap pools average roughly a few hundred dollars per round (a rough estimate, not from a source), so $20-$500 stakes would themselves move the odds. Myriad, Speed Markets, Predict.fun, Drift BET and Hedgehog look thin or have no current data.

### Cited findings
- **Limitless monthly notional (Dune):** Aug 2025 $5.7M; Sep $109.4M; Oct $127.5M; Nov $103.8M; Dec $128.6M; Jan 2026 $204.9M; Feb $372.8M; Mar $538.5M; **Apr $1.66B** (5.6% of tracked prediction-market notional); May about $348.2M by 5 May. Cumulative about $3.9-3.97B. Source: [DeFi Rate, 5 May 2026](https://defirate.com/news/limitless-files-cftc-approval-after-record-1-66b-month/)
- DefiLlama calls Limitless the "fastest-growing prediction market at +180% 30D fees ($2.4M)" (undated dashboard). Its cumulative-volume figure (>$600M) conflicts with the Dune figure. Source: [DefiLlama dashboard (search summary)](https://defillama.com/pro/predication-p916z7)
- An undated aggregator lists Limitless at about $4.8M 24h and $22.12M 7d volume. Source: [pm.wiki (search summary)](https://pm.wiki/uk/projects/limitless-exchange)
- **HIP-4 (2-20 May 2026):** $31.7M of BTC prediction volume in 19 days (Polymarket BTC $33.87M; Kalshi $0.5M, preliminary). Daily volume averaged just over $3M. 6,101 wallets; algorithmic wallets were about 6% of wallets but about 49% of dollar volume. **Mean spread 360 bps, median 53 bps.** The book is dense at the top and "thin past 100 bps". On the worst day (13 May), a $1K trade had 2% slippage. **35 minutes before settlement of a 99.2%-Yes outcome, one maker posted $50.3M of bids 0.5-1.0% below mid.** Source: [Arrakis](https://arrakis.finance/blog/hip-4)
- HIP-4 day one: 6.05M contracts across about 4,000 traders. Outcome.xyz carried about 75% of builder volume. Source: [pm.wiki Outcome.xyz](https://pm.wiki/uk/projects/outcomexyz)
- Launch-day volume figures conflict (more than $6M notional vs about $59.5K). Source: [search summary citing Sygnum and others](https://www.sygnum.com/?p=22065)
- **PancakeSwap Prediction:** about $229,909 in fees over 30 days (DefiLlama, date not shown in the snippet). Source: [DefiLlama (search summary)](https://defillama.com/protocol/pancakeswap-prediction)
- **Myriad:** about $1,319 in 30-day fees across all chains, and $167M cumulative volume since launch (as of Jan 2026). Sources: [DefiLlama Myriad](https://defillama.com/fees/myriad-markets); [Decrypt](https://decrypt.co/353044/world-liberty-financial-stablecoin-usd1-lands-on-prediction-market-myriad)
- **Overtime/Thales Speed Markets:** the only volume figure found is about $47.4K average daily volume on Arbitrum in Dec 2023-Jan 2024 (old). OVER token volume was about $5.8K/day in Jul 2026. Sources: [Arbitrum forum update, Jan 2024](https://forum.arbitrum.foundation/t/thales-protocol-first-bi-weekly-update-jan-5th-2024/20444); [Coinranking](https://coinranking.com/coin/px6A1jFbE+overtime-over/historical-data)
- **Opinion:** claimed about a third of global prediction-market volume in early 2026, but was third with 2.8% share by Aug 2026 (CMC summary). Bloomberg (Mar 2026) said its fast start "appears to be running out of steam". Sources: [Bloomberg](https://www.bloomberg.com/news/articles/2026-03-03/prediction-market-boom-finds-a-new-challenger-with-asia-roots); [CMC AI updates](https://coinmarketcap.com/cmc-ai/opinion/latest-updates/)
- **Predict.fun:** an undated report says it had two active markets and about $300K total volume. It acquired Probable (a PancakeSwap/YZi-incubated rival) on 4 Mar 2026. Sources: [MEXC news (secondary)](https://www.mexc.com/news/994586); [Yahoo/CZ teaser](https://finance.yahoo.com/news/cz-teases-bnb-based-prediction-133355253.html)
- **Drift BET:** "much thinner liquidity on any given event contract" (2026 aggregator). Source: [MadeOnSol](https://madeonsol.com/compare/drift-bet-vs-metadao)

### Inferences
- **PancakeSwap pool size (rough):** $229.9K of fees ÷ 3% ≈ $7.7M pooled per 30 days, or about $255K/day. Across about 864 five-minute rounds a day (3 live assets × 288), that's roughly **$300 per round on average** (BNB rounds likely larger). A $20-$500 favourite bet would be a large share of a typical pool and would cut its own payout. This estimate assumes all fees are from BNB Chain rounds and that the snippet is recent; it is a back-of-envelope figure.
- **HIP-4:** $20-$500 tickets would fill near the top of book on the BTC daily (median spread 53 bps), but the product is daily only.
- **Limitless:** platform volume suggests $20-$500 is feasible on active BTC markets, but depth per 5m/15m/hourly market, or for altcoins, could not be verified.

### Gaps
- No per-market order-book depth was found for Limitless short crypto markets, and no Dune dashboard broken down by duration.
- No 2026 volume figures were found for Speed Markets, Probly, Myriad Candles, Drift BET or Hedgehog.
- DefiLlama pages returned 403 when fetched, so the figures above are from search snippets.

## 5. Programmatic access (SDK/API, contract calls, rate limits)

### Takeaway
Limitless (REST, WebSocket, TS/Python/Go/Rust SDKs) and Hyperliquid (documented REST and WebSocket with published limits) have proper bot APIs. Predict.fun has a beta REST API capped at 240 requests per minute. PancakeSwap, Speed Markets and Myriad require direct contract calls or have only lightly documented APIs.

### Cited findings
- **Limitless:** REST `https://api.limitless.exchange` and WebSocket `wss://ws.limitless.exchange` (single global endpoints). Base mainnet (chain ID 8453). **No testnet or sandbox**, so you test with small live orders. Authentication uses HMAC-SHA256 API tokens. Orders are EIP-712 signed. Accounts using 1-click smart wallets must switch to EOA mode for API orders. SDKs exist in TypeScript, Python, Go and Rust, plus a trading MCP server. Source: [Limitless developers intro](https://docs.limitless.exchange/developers/introduction)
- **Limitless rate limits:** no numbers are published. Over-limit returns 429 with `Retry-After`, and higher quotas are available on request. There's an optional `recvWindow` that rejects stale signed orders, and maintenance mode can restrict trading to post-only or cancel-only. Sources: [Limitless API intro](https://docs.limitless.exchange/api-reference/introduction); [Responsible agents](https://docs.limitless.exchange/developers/responsible-agents.md)
- **Limitless agent rules:** no wash trading, spoofing or layering, coordinating fills, or extra wallets to evade limits, and no exploiting bugs. Ordinary cancel/replace quoting is allowed. Source: [Responsible agents](https://docs.limitless.exchange/developers/responsible-agents.md)
- **Hyperliquid REST:** 1,200 weight per minute per IP. Exchange actions weigh 1 + floor(batch/40). `l2Book` and `orderStatus` weigh 2. **Address-based limit: 1 action per 1 USDC traded cumulatively, plus an initial 10,000 buffer**; when exhausted, you get 1 request every 10 seconds. The default open-order limit is 1,000. Source: [Hyperliquid rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- **Hyperliquid WebSocket:** per IP, 10 connections, 1,000 subscriptions, 2,000 messages per minute and 100 inflight posts. "Use websockets for lowest latency realtime data." Source: [Hyperliquid rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- HIP-4 exposes an `outcomeMeta` info endpoint and split/negate actions, and there's a contract-specifications page for recurring outcomes. Source: [HIP-4 spec](https://hyperliquid.gitbook.io/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets)
- Third-party HIP-4 streaming is available (GoldRush, from 4 May 2026). Source: [GoldRush](https://goldrush.dev/docs/changelog/20260504-hip-4-outcome-markets-now-streaming)
- **Predict.fun:** "The REST API is currently in beta". Mainnet needs an API key, with a **default of 240 requests per minute**. SDKs on npm (`@predictdotfun/sdk`) and PyPI (`predict-sdk`). Primary servers are in **ap-northeast-1 (Tokyo)**. No WebSocket is mentioned on the API landing page. Source: [Predict API](https://dev.predict.fun)
- **Opinion:** API key for market data, private key plus EIP-712 for trading, and a WebSocket feed (community integration; no official limits found). Source: [CloddsBot Opinion skill](https://tessl.io/registry/skills/github/alsk1992/CloddsBot/opinion)
- **PancakeSwap Prediction:** the docs describe only app and Telegram usage. Third-party bots interact with the contract directly (2022 GitLab/GitHub projects, unverified). Sources: [PancakeSwap docs](https://docs.pancakeswap.finance/products/prediction); [GitLab "prediction bot" topic](https://gitlab.com/explore/projects/topics/prediction+bot)
- **Myriad** is "positioned … as a developer-friendly platform with APIs, SDKs, and tools for AI agents" (no endpoint details). Source: [FinFeedAPI Myriad](https://www.finfeedapi.com/exchange/myriad)

### Inferences
- Limitless's API is a close functional copy of the Polymarket/Kalshi pattern: a signed-order REST API plus a WebSocket for the book and your own orders. The missing published rate limits and the lack of a testnet are the main frictions.
- Hyperliquid's address-based limit (1 action per $1 traded) is generous for a bot doing $20-$500 tickets, as long as fill rates aren't tiny.

### Gaps
- No official API documentation was found for Opinion, Probly, Myriad Candles, or Overtime Speed Markets in 2026.
- Limitless's numeric REST and WebSocket rate limits are unpublished.

## 6. Latency (hard requirement): PASS / FAIL / UNCLEAR per venue, benchmarked against Kalshi (REST orders plus WebSocket prices and fills, roughly sub-second)

### Takeaway
On latency alone, two venues PASS: **Limitless** (off-chain matching with an instant MATCHED event over WebSocket, then Base settlement; watch for per-market taker delays) and **Hyperliquid HIP-4** (on-chain CLOB with one-block finality and WebSocket streams). Both are off-limits to US persons. PancakeSwap and Speed Markets FAIL: every bet is an on-chain transaction, there's no push stream of fills, and on PancakeSwap betting closes before the window starts. The rest are UNCLEAR because they lack documentation.

### Cited findings (chain and oracle timing)
- **Base:** 2-second blocks, with **Flashblocks: 200 ms sub-blocks streamed inside the 2 s block** (live on mainnet since July 2025). Priority-fee auctions run every 200 ms. If preconfirmations are deemed unsafe, they're disabled network-wide and confirmations fall back to 2 s blocks. Sources: [Base docs: Flashblocks](https://docs.base.org/base-chain/flashblocks); [Base transaction ordering](https://docs.base.org/base-chain/network-information/transaction-ordering.md)
- Measured end-to-end on Base: about 2,000 ms on a standard endpoint vs about 300-500 ms on a Flashblocks-aware endpoint (Chainstack). Source: [Chainstack Flashblocks](https://docs.chainstack.com/docs/flashblocks-on-base)
- **BNB Chain:** the Fermi hard fork (14 Jan 2026) cut blocks from 0.75 s to **0.45 s**, with a target of about 1 s finality (third parties say about 1.1 s). Sources: [BNB Chain blog](https://www.bnbchain.org/en/blog/fermi-hard-fork-accelerates-bsc-to-0-45-second-block-times); [Cointelegraph](https://cointelegraph.com/news/bnb-chain-fermi-upgrade-faster-block-times-finality)
- **Hyperliquid:** HyperCore runs fully on-chain order books. "Every order, cancel, trade … happens … with one-block finality inherited from HyperBFT". It supports 200k orders per second. Source: [Hyperliquid docs](https://hyperliquid.gitbook.io/hyperliquid-docs)
- **Pyth:** price feeds update about every 400 ms (pull model: signed prices are fetched from Hermes and verified on-chain). Source: [Arbitrum docs: Pyth](https://docs.arbitrum.io/for-devs/oracles/pyth)
- **Chainlink on PancakeSwap:** Lock and Close prices are updated "up to 20 seconds" apart. Source: [PancakeSwap docs](https://docs.pancakeswap.finance/products/prediction)
- **Limitless:** MATCHED arrives "the moment the engine fills your order (before the on-chain transaction)", followed by MINED with a txHash. OME and SETTLEMENT events for the same order "can arrive in either order within a few seconds". Sample frames show about 40 ms from occurrence to publication (illustrative only). **Optional `settings.takerDelayMs`: "Some markets hold taker orders before filling them."** The order-event stream is "never coalesced". Source: [Limitless order events](https://docs.limitless.exchange/developers/websocket/order-events.md)
- The Limitless WebSocket also streams prices and order books (`orderbookUpdate`), positions and market lifecycle (`marketResolved`). Source: [Limitless docs index](https://docs.limitless.exchange/llms.txt)
- **Predict.fun:** REST only (beta), 240 requests per minute, servers in Tokyo. Source: [Predict API](https://dev.predict.fun)

### Per-venue latency verdicts

| Venue | Push stream (prices/book, own fills) | Order entry | Typical order-to-confirm | Rate limits | Built-in delays | vs Kalshi | Verdict |
|---|---|---|---|---|---|---|---|
| **Limitless** (Base) | Yes: WS order book, prices, own order events, positions | Off-chain matching engine; on-chain settlement on Base | Match acknowledgement immediate (ms, per docs' design); MINED after Base inclusion (~0.2-2 s per Base docs and Chainstack) | Unpublished; 429 + Retry-After | `takerDelayMs` on some markets; maintenance modes | Similar for match/fill events; settlement finality slightly slower | **PASS** (check `takerDelayMs` on target markets) |
| **Hyperliquid HIP-4** (HyperCore) | Yes: WS (10 conns, 1,000 subs per IP) | On-chain CLOB, one-block finality | Sub-second implied by one-block finality (no official median latency found) | 1,200 weight/min/IP; 1 action per $1 traded + 10k buffer | 15-min opening auction per market | Similar | **PASS** (but daily-only markets) |
| **PancakeSwap Prediction** (BNB Chain) | No official API; read contract events or poll | Every bet is an on-chain tx (0.45 s blocks, ~1 s finality) | ~0.5-1 s+ per bet | None (chain/RPC limits) | Betting closes at lock, before the 5-min window; Chainlink prices up to 20 s apart; payout set only at lock | Slower and structurally incompatible | **FAIL** |
| **Overtime Speed Markets** (Arbitrum/OP/Base) | No documented push API found | Every buy is an on-chain tx with a Pyth pull update | Chain-dependent, multi-hundred ms to seconds | n/a | Strike = Pyth price at purchase | Slower | **FAIL** |
| **Myriad Candles** (Abstract/Linea/BNB) | Unknown | On-chain AMM trades (assumed) | Unknown | Unknown | Unknown | Likely slower | **UNCLEAR** (leaning FAIL) |
| **Opinion** (BNB Chain) | WS reported by third party | EIP-712 signed orders; matching location unverified | Unknown | Unknown | Unknown | Unknown | **UNCLEAR** |
| **Predict.fun** (BNB Chain) | None documented (REST beta only) | Signed orders via REST | Unknown | 240 req/min default | Tokyo servers | Slower (polling) | **UNCLEAR** (leaning FAIL until a WS is confirmed) |
| **Probly** (TxFlow L1) | Unknown | Unknown | Unknown | Unknown | Unknown | Unknown | **UNCLEAR** |
| **Drift BET / Hedgehog / Azuro / SX Bet** | Not checked for short crypto markets (none found) | n/a | n/a | n/a | n/a | n/a | **N/A** (no short crypto product found) |

### Inferences
- **Front-running (MEV, when others see a pending trade and jump ahead of it):** on Limitless, a signed order goes to the off-chain engine, not a public mempool, so entry-time front-running risk is low. The residual risk is in the operator's settlement transaction. On PancakeSwap, bets are public transactions on BNB Chain, so bots can see the pool shift and pile in during the final blocks before lock. That's the main reason the final parimutuel odds are unpredictable for an early bettor. Speed Markets buys are also public transactions.
- **Oracle-update latency:** Pyth (about 400 ms) and Chainlink Data Streams are fast compared with 5- to 60-minute windows. PancakeSwap's Chainlink feed, at up to 20 s between updates, is coarse for a 5-minute round, and lock and close points can sit on stale rounds.
- **Gas or priority fees:** Limitless and HIP-4 entry are signed messages, and HIP-4 actions go straight to the L1. Neither requires the trader to win a gas auction to get matched. PancakeSwap and Speed Markets require paying gas on every bet, and landing a late bet reliably on BNB may need a higher gas price.
- **Overall:** the only venues that pass the latency bar (Limitless, HIP-4) both fail the US-access requirement (Section 7).

### Gaps
- No official median order-to-ack latency was found for Limitless or Hyperliquid. Arbitrum and Optimism block times were not verified in this pass. Opinion's and Myriad's API architectures are unverified.

## 7. US access: terms of service, geo-blocking, CFTC history

### Takeaway
Every venue here with a usable CLOB bars US persons. Limitless's terms (last updated 15 Sep 2026) say the platform "is not available for trading" to US users, and its US arm's CFTC exchange application is still pending. Hyperliquid, Myriad and Opinion also restrict US users. No US bar was found for PancakeSwap Prediction, but it isn't a CFTC-registered venue. The US-legal crypto-company alternative is Gemini Predictions, a CFTC-designated exchange.

### Cited findings
- **Limitless ToS:** "The Platform is not available for trading to users from the following jurisdictions: United States of America, Republic of China", plus Ontario and Alberta. Access is separately blocked from Russia, Belarus, Cuba, Iran, North Korea, Syria and occupied Ukrainian regions. "Last Updated: September 15, 2026." Source: [Limitless Terms of Service](https://docs.limitless.exchange/user-guide/terms-of-service.md)
- **Conflict:** May 2026 press said Limitless "is currently available in the US", and a vendor table lists US access as "Unrestricted". Both predate or contradict the September 2026 terms; treat the terms as authoritative. Sources: [Public Gaming, 6 May 2026](https://www.publicgaming.com/news-categories-m/legal/15786-limitless-markets-submits-cftc-proposal-for-5-minute-digital-asset-event-contracts); [pmxt.dev](https://pmxt.dev/limitless-api)
- **Limitless Markets US, LLC** filed a Form DCM (DCM = designated contract market, a CFTC-licensed exchange) on 1 May 2026. Status is **Pending**. It proposes binary and scalar contracts, fully cash-collateralised, cleared through a CFTC-registered DCO (DCO = clearing house), with its principal office in George Town, Grand Cayman. Sources: [CFTC filing page](https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizations/60686); [DeFi Rate](https://defirate.com/news/limitless-files-cftc-approval-after-record-1-66b-month/)
- A Manifold crowd forecast put approval within 2026 at about 66-69% (snapshot, not a regulatory fact). Source: [Manifold](https://manifold.markets/realTomBayes/limitless-markets-us-approved-as-a)
- **Hyperliquid:** an Aug 2026 report says its terms "still classify US residents as 'Restricted Persons'", enforced by geofencing. Source: [AInvest, Aug 2026](https://www.ainvest.com/news/hyperliquid-28m-washington-push-won-open-2608/)
- Outcome.xyz's HIP-4 front end is "geo-restricted from the US". Source: [pm.wiki Outcome.xyz](https://pm.wiki/uk/projects/outcomexyz)
- Hyperliquid's own terms could not be fetched (403).
- **Myriad:** "available exclusively to customers outside the United States" (Myriad tweet, 14 Jan 2026). Source: [Decrypt](https://decrypt.co/353044/world-liberty-financial-stablecoin-usd1-lands-on-prediction-market-myriad)
- **Opinion:** the United States is on its list of locations where trading is restricted by IP address. Source: [Opinion x Binance Wallet Booster page](https://opinionlabs.notion.site/Introducing-Opinion-x-Binance-Wallet-Booster-Program-2e2b8e9fa797806fbc39f1aa88491887)
- **Jupiter Predict (Solana, routes to Kalshi/Polymarket liquidity):** "US and South Korea IPs are blocked." Source: [Jupiter docs](https://docs.jup.ag/user-docs/trade/predict/how-it-works.md)
- **Drift BET** is "only accessible in countries where the Drift protocol is live" (2024). Source: [The Block, Aug 2024](https://www.theblock.co/post/311888/solana-based-drift-protocol-launches-prediction-market)
- **Hedgehog:** "not open to US citizens" (2022 post; per search summary). Source: [Astral Codex Ten, Aug 2022](https://www.astralcodexten.com/p/mantic-monday-81522)
- **PancakeSwap:** the 2022 geoblock covered 10 sanctioned jurisdictions and did not include the US. The current terms could not be retrieved. Source: [ForkLog, 2022 (old)](https://forklog.com/en/pancakeswap-to-block-users-from-ten-jurisdictions/amp)
- **CFTC history:** in 2022 Polymarket was fined $1.4M and ordered to stop offering markets in the US, after which it geoblocked US users. In 2025 an amended designation let it return via the CFTC-registered QCX LLC (Polymarket US). Sources: [The Block, 2022](https://www.theblock.co/linked/131383/following-cftc-settlement-prediction-platform-polymarket-geoblocks-trades-in-the-us); [search summary of CFTC history](https://www.law.cornell.edu/wex/prediction_market)
- **2026 CFTC stance:** the enforcement director said on 31 Mar 2026 that insider trading on prediction markets will be treated like other CFTC markets. The first prediction-market insider-trading case was filed on 23 Apr 2026. In Apr 2026, House Democrats pressed the CFTC chair on offshore platforms. No 2026 enforcement action against an offshore crypto prediction venue was found. Sources: [Clifford Chance, Apr 2026](https://www.cliffordchance.com/briefings/2026/04/cftc-enforcement-director-outlines-enforcement-priorities-addresses-prediction-market-insider-trading-and-previews-a-forthcoming-cooperation-advisory.html); [Greenberg Traurig, Apr 2026](https://www.gtlaw.com/en/insights/2026/4/prediction-markets-a-cftc-enforcement-update); [The Block](https://www.theblock.co/post/396567/democrats-press-selig-cftc-oversight-offshore-prediction-market-war-bets); [DeFi Rate](https://defirate.com/news/lawmakers-urge-cftc-crackdown-offshore-prediction-markets/)
- **Gemini (US-legal):** Gemini Titan, LLC was designated a DCM in Dec 2025 and launched its predictions marketplace. Gemini Olympus received a DCO licence on 30 Apr 2026. Its products include crypto price-milestone contracts; no confirmation of hourly or minute contracts was found. Sources: [Gemini blog, 1 May 2026](https://www.gemini.com/blog/gemini-receives-dco-license-approval-from-cftc); [Unchained](https://unchainedcrypto.beehiiv.com/p/gemini-wins-cftc-approval-to-launch-prediction-markets)

### Inferences
- **Off-limits to US persons (by the venue's own terms or geoblock):** Limitless (trading), Hyperliquid/HIP-4 and Outcome.xyz, Myriad, Opinion, Jupiter Predict, and probably Hedgehog (2022 evidence).
- **No US bar found but legally gray:** PancakeSwap Prediction, Speed Markets, Predict.fun, Probly. These are binary event contracts on commodities offered off a DCM. The Polymarket 2022 precedent shows the CFTC treats them as within its jurisdiction, so the absence of a geoblock isn't a green light.
- **Watch item:** if Limitless Markets US gets DCM designation and lists its 5-minute crypto contracts, it would become a US-legal on-chain-adjacent venue with a Kalshi-like API. Today it is pending.

### Gaps
- The current terms for PancakeSwap, Overtime, Predict.fun, Probly and Drift could not be retrieved. Hyperliquid's own terms returned 403.
- Whether Gemini lists intraday crypto contracts was not confirmed.

## 8. Calibration, favourite-longshot bias, and known edges/exploits (oracle-latency arbitrage)

### Takeaway
No venue-specific calibration study was found for any of these venues' short crypto markets. The best evidence is that HIP-4 BTC prices sat about 4-5x further from Deribit option-implied probabilities than Polymarket or Kalshi did. That suggests mispricing exists but also that execution is noisy. The favourite-longshot bias (favourites winning more often than their price implies, longshots less) is documented on Kalshi but hasn't been measured on these venues. Venues are closing oracle-latency edges with taker fees, TWAP settlement and taker speed bumps.

### Cited findings
- **HIP-4 vs Deribit:** HIP-4's gap from Deribit implied probability was about 4-5x wider than Polymarket's or Kalshi's (about 4x in a typical hour). All three sat slightly above Deribit at the median (532 hourly rows, excluding the last 5 hours before settlement). Source: [Arrakis, May 2026](https://arrakis.finance/blog/hip-4)
- On HIP-4, 24 stat-arb taker wallets all had win rates above 50% (median 60%). No institutional market makers were identified. Source: [Arrakis](https://arrakis.finance/blog/hip-4)
- **Favourite-longshot bias on Kalshi:** low-priced contracts lose money on average (Bürgi, Deng & Whelan, CESifo working paper; not crypto-specific). Source: [CESifo / ifo](https://www.ifo.de/en/cesifo/publications/2025/working-paper/makers-and-takers-economics-kalshi-prediction-market)
- Polymarket BTC/ETH prices broadly track option-implied benchmarks but deviate most in tail events (Diercks et al., Feb 2026, per a research review). Source: [Capital Spectator review, Apr 2026](https://www.capitalspectator.com/?p=25500)
- **Closing latency arbitrage (excluded venue, context):** Polymarket added taker-only fees to its 15-minute crypto markets on 6 Jan 2026. Under zero fees, bots had exploited small delays between Polymarket prices and spot exchanges. The fees are highest near 50% and fall toward the extremes. Source: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
- **Limitless design choices:** taker fees fall toward the extremes (3% at ≤50c, 0.40% at 0.999). 5- and 15-minute markets settle on a Chainlink TWAP. Some markets apply a per-market `takerDelayMs`. Exploiting bugs is banned. Sources: [Limitless fees](https://docs.limitless.exchange/user-guide/fees.md); [Limitless resolution](https://docs.limitless.exchange/user-guide/market-resolution.md); [Limitless order events](https://docs.limitless.exchange/developers/websocket/order-events.md); [Responsible agents](https://docs.limitless.exchange/developers/responsible-agents.md)
- **PancakeSwap bots:** 2022 open-source projects claim to "win the majority of rounds" or "arbitrage the prediction game". These claims are unverified and old. Source: [GitLab topic](https://gitlab.com/explore/projects/topics/prediction+bot)

### Inferences
- Limitless's fee curve (cheap at 90-99c, expensive near 50c), TWAP settlement and taker delays all target latency snipers trading near 50/50. They impose relatively little cost on a patient favourite-buyer, though a taker delay can matter if the favourite's price is moving.
- Speed Markets' design (strike = the Pyth price at purchase) is vulnerable to stale-oracle sniping in principle, if the on-chain price lags spot. No source was found on how Thales/Overtime handled this.
- On parimutuel PancakeSwap, the "edge" bots target is late-block information, meaning betting just before lock once the pool split is visible. An earlier favourite-backer is structurally the one who gets diluted.

### Gaps
- No calibration or reliability data was found for Limitless, PancakeSwap, Speed Markets, Myriad, Opinion, Predict.fun or Probly.
- No evidence was found on whether favourites at 90-99c on Limitless's 5m/15m/hourly markets win more or less often than their price implies. Measuring this would require pulling Limitless's historical markets and fills through its API.
