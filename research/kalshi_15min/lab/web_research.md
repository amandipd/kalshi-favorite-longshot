# Web research: losing trades, the favourite-longshot bias, and what strategies people use

Oct 11, 2026. This is online research plus one simulation. It doesn't touch our data or the bot.
The rule studied: at the end of minute 8, buy the favourite at 90-99.9¢ and hold it to settlement.

## 1. Is a ~5% loss rate expected?

**Yes, if the average price you pay is near 95¢. But at 95¢, 5% is also roughly the break-even point.**
The break-even loss rate is 1 − price − fee:

| price paid | one loss wipes out | break-even loss rate | Kalshi taker fee, as % of stake |
|---|---|---|---|
| 90¢ | 10 wins | 9.4% | 0.70% |
| 93¢ | 14 wins | 6.5% | 0.49% |
| 95¢ | 20 wins | 4.7% | 0.35% |
| 97¢ | 35 wins | 2.8% | 0.21% |
| 99¢ | 106 wins | 0.9% | 0.07% |

- **Inconsistency to check first.** The rule of thumb that each loss costs about 10× a typical win implies fills near 91¢. At 91¢, a 5% loss rate would earn about +4% per bet, which is about 10× the backtest edge.
  - Either the live average fill is nearer 95¢, or "10×" is loose.
  - The test that matters is **realised win rate minus the average (price + fee) actually paid**, not the win rate on its own.
- **Negative skew** means many small wins and rare big losses. "Picking up nickels in front of a steamroller" is the same payoff shape as selling insurance or selling far-out-of-the-money options.
  - Practitioners accept that shape only if the premium pays for the tail.
  - They watch three dangers: the tail being bigger than history shows, losses arriving together, and bet size.
  - Our edge is thin against its noise. Each bet earns +0.45% on average but swings ±21% (standard deviation).

**Simulation.** Assumptions: 95¢ average price, the backtest edge (+4.5¢ per $10 staked, i.e. a 95.76% win rate against 95.33% needed), 3% stakes, and independent bets. A small throwaway simulation, not kept; the numbers are illustrative.
- **Kelly fraction** (the bet size that maximises long-run growth) is 9.2% of bankroll. 3% is about ⅓ Kelly *if* the edge is real. At half that edge, 3% is about ⅔ Kelly. With no edge, any bet size shrinks the bankroll.
- **After 1,000 bets** with the edge intact:
  - 31% chance of still being behind.
  - **Max drawdown** (largest fall from a peak): median 17%; 1-in-20 chance of 32% or worse.
- **After 5,000 bets:** 11% chance of being behind; median drawdown 30%; 1-in-20 chance of 50%.
- **With no edge:** about 56-60% chance of being behind.
- **Losses arrive together.** BTC, ETH and SOL move together within a 15-minute window. Assume 4 bets per window with latent correlation 0.5:
  - 27% of windows that contain a loss contain 2 or more.
  - The 1-in-20 drawdown over 1,000 bets rises to 41%.
  - Variance rises 1.6×, so every test below needs about 1.6× more bets.

**Telling bad luck from a broken edge (rules of thumb).**
1. **Test against price, not against 100%.**
   - Expected losses with no edge = Σ(1 − price − fee) over the bets you took.
   - z = (expected − actual losses) / √Σ p(1−p).
   - Group bets by window, because bets in the same window aren't independent.
2. **Even with the edge intact, you will often see "too many" losses.**
   - Chance of more losses than break-even purely from luck: 42% after 100 bets, 25% after 1,000.
   - Per 100 bets: about 4.2 losses expected; 8 is the 95th percentile and 10 the 99th, so 10 or more is a red flag.
   - Per 1,000 bets: 53 is the 95th percentile and 58 the 99th.
3. **Proving a +0.45% edge takes a long time.**
   - About 9,000 independent bets for 2 standard errors (about 14,000 once window correlation is counted).
   - Live data can't confirm the edge quickly. It can only check that live results match the backtest.
4. **A pre-committed sequential test catches a real break fast.** An **SPRT** (sequential probability ratio test) keeps a running score that stops as soon as the evidence is strong either way; here it allows 5% error each way. Bets needed to decide between "edge as backtested" and:

   | if the true win rate is… | bets to decide |
   |---|---|
   | equal to the price (bias gone; the fee makes it a small loser) | ~4,400 |
   | 1 point below the price | ~900 |
   | 2 points below the price | ~400 |

   A **CUSUM** (a running sum of evidence that resets at zero) does the same job as a monitor.
5. **When the numbers drift, look for a cause.** Likely culprits: worse fills (adverse selection), changes to fees or settlement rules, or new competition.

## 2. Evidence on the favourite-longshot bias (FLB)

The FLB is the pattern where cheap "longshot" contracts are overpriced and expensive favourites are slightly underpriced.

**Bürgi, Deng & Whelan, "Makers and Takers" (UCD; versions Jul 2025 to Feb 2026).**
- Data: Kalshi from 2021 to April 2025; 313,972 prices on 46,282 contracts.
- **It leaves out the hourly crypto and index markets and anything open less than 24 hours, so it says nothing directly about our markets.**
- Contracts under 10¢ lose more than 60% of the money staked.
- Above 70¢ there are small but statistically significant positive returns *after the taker fee*. Example: a 95¢ contract that wins 98% of the time returns +3.1% before fees.
- Average return for makers was −9.6%, against −31.5% for takers. Makers buying at 50¢ or more earned +2.6%.
  - A **maker** posts a resting order; a **taker** accepts one and pays the fee.
- The bias appears in every category; crypto has the steepest slope (0.058, against 0.034 overall).
- **It is shrinking:** the slope for 2025 is 0.021, against 0.048 for 2024, and less significant.
- Their model reproduces the pattern with modest disagreement between traders plus a small overweighting of small probabilities.

**Snowberg & Wolfers (JPE 2010)** studied horse racing. They found the bias comes from bettors misjudging small probabilities, not from a love of risk. A behavioural cause like that tends to persist, but competition erodes it.

**Cardozo & Rivero-Wildemauwe (arXiv 2609.12878, Sep 2026).**
- Data: 588M Polymarket trades.
- Buys at 90¢ or more earn **+0.83¢ per dollar**; buys under 10¢ lose 19.3¢.
- The pattern holds in crypto and politics but not in sports, and it is sensitive to how contracts are grouped.
- The top decile of favourite buyers earns *less* than other accounts.
- How fees are treated could not be checked.

**Smaller GitHub studies of Polymarket:**
- One finds buying 90-99% favourites is *not* significant after costs.
- Another finds no FLB at all.

**15-minute BTC on Kalshi.**
- A blog analysis of about 3,320 KXBTC15M windows (it could not be opened, so this is unverified) found prices close to calibrated. Contracts around 92¢ won about 91.4%, and late 97-98¢ favourites won about 98%.
- So expect little or no raw bias in these markets. Our edge probably comes from the filters (minute 8, spread, late favourites).

**Does it survive fees?**
- At 90-99¢, Kalshi's fee is small: 0.35% of stake at 95¢.
- But that fee is similar in size to our 0.45% net edge, so small fee or fill changes matter.

**Is the bias shrinking?** Probably yes:
- The 2025 slope is half the 2024 slope.
- Institutional market makers have joined, including Susquehanna since April 2024.
- A study reported by *The American Prospect* found takers lose about 1.12% per trade overall, and that the pattern was reversed in Kalshi's early days.

## 3. Strategies people use

| Strategy | How it makes money | What kills it | Fits a small automated account on Kalshi 15-min? |
|---|---|---|---|
| **Market making** (posting resting bids and offers, earning the **spread** = the gap between them) | Spread, plus maker returns, which beat taker returns; plus Kalshi's **Liquidity Incentive Program (LIP)** | **Adverse selection** (informed traders hit your stale quote when spot moves), inventory risk, professional competition | **Partly.** Our 16 series are taker-fee-only, so makers pay **no fee** (Kalshi API, Oct 11). LIP is live today only on palladium, copper, platinum and natural-gas 15-min ($20 per window each, target 300 contracts a side, 0.5× per tick of distance) and on FX 15-min ($50). Nothing on BTC, ETH, gold, silver or WTI. LIP scores your share of resting size near the best price; a snapshot is taken every second; the program runs to Jan 1, 2027. |
| **Arbitrage: YES + NO** | Buying both sides for under $1 | - | **No.** Kalshi has one order book for YES and NO, so it can't happen there. On Polymarket, about $40M was taken April 2024 to April 2025, mostly in multi-outcome markets, by a few bot-like accounts, before fees existed (Saguillo et al.). |
| **Arbitrage: cross-venue** (Kalshi vs Polymarket) | Opposite sides on two venues | **Basis risk** (the two contracts don't settle the same way): Kalshi uses a 60-second index average, Polymarket a single Chainlink price; capital split across venues; US access to Polymarket | **No.** It is a spread bet, not an arbitrage. |
| **Arbitrage: bracket / combinatorial** (related markets that must add up) | Inconsistent prices across linked markets | Thin size, legs that fail to fill | Small. Found mostly in multi-outcome event markets. |
| **High-probability harvesting** ("bonding": buying 95-99¢ and holding) | The small FLB at the favourite end | Tail and resolution risk, crowding, fees and adverse selection. One blog argues that above about 98¢ you are mostly betting on the settlement process working. | **Yes. This is our strategy.** |
| **Fair-value model** (price the contract as a **digital option**, one that pays $1 if the price ends above a level) | Buy when Kalshi's price is below the model value | Latency competition; fees on taker entries | **Best as a filter.** Estimate P(up) ≈ Φ(ln(S/K) / (σ√τ)) from spot S, the price to beat K, short-term volatility σ and time left τ. This matches our Oct 11 finding that a spot-model skip filter helped out of sample. |
| **Latency arbitrage** (trading before the venue catches up with Binance/Coinbase) | Stale quotes | Polymarket added taker fees on 15-min crypto (Jan 5, 2026) and, per one trader, removed its 500 ms taker delay; that trader says pure latency arbitrage died that day. The "$313 → $414k bot" story is unverified. | **No** for a home connection. |
| **News / event trading** | Reacting first to scheduled data or headlines | Speed (firms pay $100k a month for instant news feeds) | **No** as a strategy, but scheduled events (8:30 ET data, 2:00 PM FOMC) are worth **skipping**; see the backtests. |
| **Copy-trading** | Following winning wallets | Whale ≠ skill; slippage and latency; no independent evidence it works | **No.** Kalshi accounts are anonymous. |

## 4. The 15-minute markets themselves

**Kalshi crypto** (KXBTC15M etc.). Taken from the contract text in Kalshi's API, Oct 11, 2026.
- YES if the **simple average of 60 seconds of CF Benchmarks' Real-Time Index before the close** is at least the same 60-second average before the open.
  - The earlier average is the "price to beat" (`floor_strike`).
  - A tie counts as YES. Values are rounded to 2 decimals.
- Fees: `fee_type quadratic` with multiplier 1 on all 16 of our series, meaning takers pay 0.07·P(1−P) and makers pay nothing.

**Kalshi metals and energy** (gold, silver, platinum, palladium, copper, natgas, WTI). These settle differently.
- They compare the **close of the Pyth 1-minute candle** at the close with the one at the open: one price point, with no averaging.
- If Pyth publishes nothing, the last available price is used.

**Kalshi fee rounding** (Kalshi API docs).
- Fees are computed to $0.000001.
- Balances are aligned to $0.01 for FCM-cleared (brokered) customers and $0.0001 for direct members.
- Rounding overpayment builds up per order and is rebated later.
- So "round up to the cent per order" is right for brokered accounts and **overstates fees for direct members**.

**Polymarket 15-minute up/down.**
- "Up" if the Chainlink data-stream price at the end is at least the price at the start: a single point.
- Fees since Jan 5, 2026; now `crypto_fees_v2` = **0.07·p(1−p), taker only, 20% rebated to makers**. That is the same curve as Kalshi.
- A 2026 paper (arXiv 2606.31675) found traders moving the spot price at settlement in Polymarket's **5-minute** BTC markets, with sharp reversals afterwards. It found this largely absent at 15 minutes.

**Who trades them.**
- Bots, HFT firms and market makers, plus retail.
- Up/down contracts reportedly make up more than half of crypto prediction-market volume (~$70M a day combined; unverified).
- Polymarket crypto alone ran $73-100M a day in March 2026.

**What public discussion says** (mostly self-reported):
- Pure taker latency bots died with the fees; maker-side bots survived.
- Fading extreme prices on KXBTC15M lost money in all 100 variants tested (Turbine).
- Late flips happen: in one sample of 200 windows, the loser had been priced at 70¢ or more in 23 of the 31 flips.

## Backtests this suggests (our minute-1-15 bid/ask/last + result data, Dec 2025 to Oct 2026)

1. **Is the edge shrinking?** Compute realised win rate minus average (ask + fee) by month and by 1¢ band, and test for a trend. Whelan's slope halved in 2025.
2. **Loss clustering.** Per window: P(2 or more losses | at least 1 loss), the loss correlation across coins, the effective number of independent bets, and the worst-window loss against the 20% cap. Use this to size the cap and the bets-per-window limit.
3. **Maker entry.** At minute 8, post a bid at ask − 1¢ (or at the bid) instead of taking.
   - Count it filled if a later minute's ask or last price trades through.
   - Measure the fill rate and the **win rate of filled versus unfilled bets** (adverse selection). It saves the fee (0 for makers) and part of the spread.
4. **Scheduled-event skip.** Skip windows that contain 8:30 ET data releases, 10:00 ET, and 2:00 PM FOMC days. This extends the 9:30 ET skip already found.
5. **Point price versus averaging.** Compare late-reversal rates of 90-99¢ minute-8 favourites in metals/energy (Pyth point price) with crypto (60-second average).
6. **Live kill switch.** Replay live fills through an SPRT or CUSUM against "1 point below price" (decision in about 900 bets) and fix the threshold in advance.
7. **Fee check.** Compare the fees actually charged on our fills with the formula, to see whether direct-member rounding applies to us. Rounding matters for 1-3-contract orders.

## Sources

**Favourite-longshot bias**
- Bürgi, Deng & Whelan, Makers and Takers (PDF): https://www.karlwhelan.com/Papers/Kalshi.pdf
- Same paper on CESifo: https://www.ifo.de/en/cesifo/publications/2026/working-paper/makers-and-takers-economics-kalshi-prediction-market
- Same paper on CEPR: https://cepr.org/publications/dp20631
- Cardozo & Rivero-Wildemauwe, FLB on Polymarket: https://arxiv.org/abs/2609.12878
- Snowberg & Wolfers, risk-love or misperceptions: https://www.nber.org/papers/w15923
- Polymarket calibration (GitHub): https://github.com/wcsmars/Polymarket-Calibration-and-Favorite-Longshot-Bias
- Polymarket calibration (GitHub): https://github.com/CH4RL3I/honest-odds
- Polymarket-v1 database: https://arxiv.org/pdf/2606.04217
- Who wins on Kalshi (The American Prospect): https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/

**Kalshi rules, fees and incentives**
- Contract terms and fee settings (Kalshi API): https://api.elections.kalshi.com/trade-api/v2/series/KXBTC15M
- Crypto contract terms: https://assets.kalshi.com/contract_terms/CRYPTO.pdf
- Fee rounding: https://docs.kalshi.com/getting_started/fee_rounding
- Incentive programs API: https://docs.kalshi.com/api-reference/incentive-programs/get-incentives
- Liquidity Incentive Program: https://help.kalshi.com/incentive-programs/liquidity-incentive-program
- Volume Incentive Program ending (The Block): https://www.theblock.co/news/business/2026-09-30-kalshi-ends-trader-incentive-program-417247
- Fee-change history (Allium): https://docs.allium.so/historical-data/predictions/kalshi/series-fee-changes

**Polymarket rules and fees**
- Fees: https://docs.polymarket.com/polymarket-learn/trading/fees
- Fee rollout timeline (Pine Analytics): https://pineanalytics.substack.com/p/polymarket-fee-rollout
- 15-minute fees for liquidity rebates (The Block): https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates
- 15-minute market rules (Polymarket API): https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1783197900

**15-minute market behaviour and bots**
- Settlement manipulation: https://arxiv.org/abs/2606.31675
- Arbitrage on Polymarket (Saguillo et al.): https://arxiv.org/abs/2508.03474
- One trader's bot after the fee change: https://dev.to/lkto1m/february-2026-changed-polymarket-forever-heres-what-happened-to-my-bots-numbers-2fi5
- $313 → $414k bot story (unverified): https://beincrypto.com/arbitrage-bots-polymarket-humans/
- Fading extremes on KXBTC15M (Turbine): https://www.turbinefi.com/research/kalshi-btc-15-minute-markets-mean-revert-more-reliably-under-specif-8e46853f0bad
- 3,320-window calibration check (couldn't open): https://predictionmarketspicks.com/articles/is-kalshi-bitcoin-rigged
- Late flips in 200 windows: https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged

**Bonding and Kelly**
- Bonding at 99¢: https://medium.com/@jacek.jurczynski/picking-up-nickels-at-ninety-nine-cents-d4308907db2c
- Kelly criterion: https://en.wikipedia.org/wiki/Kelly_criterion
