# Favourite-longshot bias and buying heavy favourites in short-dated binary and prediction markets (state as of 13 Oct 2026)

Evidence labels used below:
- **[PR]** peer-reviewed or accepted in a journal
- **[WP]** working paper or preprint (SSRN, arXiv, NBER, university series)
- **[REPL]** third-party replication or data project on GitHub
- **[VENDOR]** practitioner, vendor or bot-seller write-up, with an incentive to overstate
- **[NEWS]** industry or crypto press
- **[ANEC]** social-media or self-reported claim

Terms:
- **FLB (favourite-longshot bias):** heavy favourites win more often than their price implies, and longshots less often.
- **Reverse FLB:** the opposite pattern, where favourites are overpriced.
- **Maker:** a trader who posts a resting limit order.
- **Taker:** a trader who crosses the spread, i.e. hits an existing order.

---

## 1. What the evidence says about FLB by venue, with effect sizes at the 90-99% end

### Takeaway
The evidence finds an FLB at the favourite end on Kalshi and Polymarket, but it is tiny: heavy favourites win roughly 0.3-1 percentage point (pp) more often than their price implies, which is about +0.3% to +2% return before fees. Almost all of the bias's "size" sits on the longshot side, where buyers lose 6-60%. No peer-reviewed study yet measures 15-minute crypto markets: the main Kalshi paper explicitly excluded hourly crypto markets. Betting-exchange in-play evidence is mixed, and some of it shows a reverse FLB late in events.

### Cited findings

**Kalshi: Bürgi, Deng & Whelan, "Makers and Takers" [WP, UCD; Jan 2026 version; SSRN 5502658; not yet published as of Aug 2026 per the replication repo]**
- **Sample.** 2021 to April 2025: 46,282 contracts across 12,403 events, giving 313,972 contract prices.
  - Kept only contracts with at least $1,000 volume and a final spread of 20c or less.
  - **Excluded markets that "re-set every hour", i.e. crypto and index markets.** The sample covers only markets open at least 24 hours. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Where trades happen.** About two-thirds of all observed prices are below 10c or above 90c. The 90-99c band alone holds 106,209 prices (33.8%). Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Returns by price band.**
  - Contracts at 10c or less lose more than 60%.
  - Contracts above 50c earn small positive returns, and those above 70c show "statistically significant, though small, positive post-fee returns."
  - The average pre-fee return across all contracts is about −20%. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
  - The paper's own illustration: "A 95c contract that wins 98% of the time has a pre-fee average return of 3.1%." This is a worked example, not a measured 95c win rate. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Makers vs takers.**
  - Average return is −9.64% for makers and −31.46% for takers.
  - Makers buying at 50c or above earn +2.6% after fees.
  - Makers account for 56.5% of contracts bought in the 90-99c band, against 43.5% in the 1-10c band. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Robustness and trend.** The bias holds across volume quintiles, trade-size quintiles and categories.
  - Crypto (daily or longer) has the steepest slope: ψ = 0.058 against 0.034 for the full sample.
  - The bias may be weakening: ψ fell from 0.048 in 2024 to 0.021 in 2025 (significant only at p < 0.1). Sources: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf); [CEPR VoxEU column](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)
- **Final day.** Maker losses on low-price contracts on the closing day look like taker losses. The authors link this to Page's (2012) "Yogi Berra bias": on InTrade, losing sports teams were priced too high in the final 15 minutes. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)

**Kalshi follow-ups**
- **Becker, "The Microstructure of Wealth Transfer in Prediction Markets"** [WP/blog; SSRN 7217640]
  - Sample: 72.1M Kalshi trades and $18.26B volume, June 2021 to November 2025.
  - Takers earn −1.12% excess return and makers +1.12%. Takers are negative at 80 of 99 price levels.
  - "Contracts at 95¢ win 95.83%" of the time, i.e. +0.83pp. At 1c, takers win 0.43% of the time and makers 1.57%.
  - Crypto category: maker-taker gap of 2.69pp (6.7M trades). Finance: gap of 0.17pp. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- **Vladosyna replication** [REPL; anonymous, 0 stars]
  - All five yearly FLB slopes replicate the original in sign and significance. The maker margin at 50c or above is +2.09% (original: +2.6%).
  - After the 2025 maker-fee boundary, the maker advantage at 50c or above is +2.40% gross. The series-level difference-in-differences estimate of the fee effect is −0.0016 (SE 0.0064), a tight null.
  - 41% of the change in the FLB slope at the fee boundary comes from composition (sports rose from 0.009% to 58.8% of the sample). The repo reports no 90-99c or crypto-series breakdown. Source: [GitHub](https://github.com/Vladosyna/kalshi-makers-takers-persistence)

**Polymarket**
- **Cardozo & Rivero-Wildemauwe** [WP, arXiv 2609.12878, Sep 2026]
  - Sample: 586M purchases totalling $23.7B, Nov 2022 to Mar 2026.
  - Returns are hold-to-resolution, pre-fee, for favourites (90c or above), on three weightings:

    | Weighting | Return | 95% CI |
    |---|---|---|
    | Equal child market | +0.277% | 0.242-0.312 |
    | Pooled dollars | +0.83% | 0.60-1.07 |
    | Equal parent event | +0.392% | n/a |

  - Longshot returns depend on the weighting: −6.3% (equal child market), −19.35% (pooled) and +4.09% (equal parent event). Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **By category (favourites, equal child / pooled).**

  | Category | Equal child | Pooled |
  |---|---|---|
  | Crypto | +0.643% | +0.537% |
  | Politics | +1.044% | +1.419% |
  | Sports | −0.230% | +0.137% (CI includes 0) |

  Sports shows no FLB. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **At the very top of the range.** Probability errors at 95c or above run from +1.14pp down to +0.11pp. Gains peak near 60c and decline toward zero as price approaches $1.
  - Favourites in 90-99c (excluding endpoints) return +0.187% (equal child) and +1.729% (pooled). Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **Short horizon.** Favourite mark-to-market returns are +0.017% after 5 minutes and +0.014% after 1 hour, against +1.939% at resolution (common sample). Almost all of the favourite "edge" is realised at resolution, not from price drift. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **Weather markets (Qiu & Qiu)** [WP, arXiv 2610.13593, 9 Oct 2026]
  - Favourite overpricing (a reverse FLB) is "much stronger in the final 1-12 hours" before resolution, nearly an order of magnitude larger than longshot mispricing.
  - Simple recalibration gave no significant gains.
  - This is direct counter-evidence that late favourites are always cheap. Source: [arXiv abs](https://arxiv.org/abs/2610.13593)
- **GitHub calibration projects** [REPL] disagree with each other:
  - "honest-odds" (2,946 markets) finds no FLB, and a reverse FLB in the 5-20% range.
  - "wcsmars" finds logistic slopes of 1.01-1.13, i.e. favourites resolve YES slightly more often than priced. Sources: [honest-odds](https://github.com/CH4RL3I/honest-odds); [wcsmars](https://github.com/wcsmars/Polymarket-Calibration-and-Favorite-Longshot-Bias)

**Betting exchanges (Betfair)**
- **Gauriot & Page** [WP, NYU Abu Dhabi 0058, Oct 2021; data 2006-2014]
  - Data: Betfair football, with $17B traded across ~7,700 matches.
  - Prices are "very well calibrated with returns being very close [to] zero", with a small longshot bias (negative returns below 50%, positive above).
  - Prices react efficiently to news on average, but **under-react to large shocks "towards the end of the markets' life"**, possibly because of traders' budget constraints. Source: [NYUAD WP](https://nyuad.nyu.edu/content/dam/nyuad/academics/divisions/social-science/working-papers/2021/0058(2).pdf)
- **Angelini, De Angelis & Singleton** [PR, *International Journal of Forecasting*; 1,004 EPL matches, 2009-2014]
  - Finds a **reverse FLB** (favourite bias) pre-match and in-play.
  - After a first goal, markets over-weight a favourite's goal, especially early, and under-weight a longshot's goal scored late.
  - Mispricing peaks 20 seconds after the goal and persists for up to 5 minutes.
  - A simple strategy earned roughly 50% gross ROI in sample and out of sample (2019/20). Source: [paper PDF](https://www.carlsingletoneconomics.com/uploads/4/2/3/0/42306545/information_efficiency_angelini_de_angelis_singleton.pdf)
- **Croxson & Reade (2014)** found Betfair prices update swiftly and fully after goals near half-time (as summarised in Angelini et al.). Source: [paper PDF](https://www.carlsingletoneconomics.com/uploads/4/2/3/0/42306545/information_efficiency_angelini_de_angelis_singleton.pdf)

**Parimutuel (horse racing)**
- **Snowberg & Wolfers** [WP, NBER w15923, 2010; published version in JPE]
  - Data: 5.6M US horse starts, 1992-2001.
  - Rate of return by bet: 100/1 or longer about −61%; random bet −23%; 4/1-9/1 about −18%; **favourite in every race −5.5%**.
  - Even favourites lose after the track take (the operator's cut of the betting pool), so the FLB alone does not make favourites profitable in pari-mutuel pools. Source: [NBER PDF](https://www.nber.org/system/files/working_papers/w15923/w15923.pdf)
- **Green, Lee & Rothschild, "Favorite-Longshot Midas"** [WP, Wharton 2018]: about 63c returned per $1 on 30/1 shots against about 85c on 1/1 favourites. Taken from a search snippet; full text not read. Source: [Wharton PDF](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2018/08/The-Favorite-Longshot-Midas.pdf)
- **Data Golf** [practitioner]: argues the empirical evidence for FLB "is not that strong; some markets show it, but many don't", and that some measured FLB is an artifact of how the bookmaker's margin is spread across odds. Source: [Data Golf](https://datagolf.com/fav-longshot-not-a-bias)

**Fixed-odds / exchange-traded binary options (Nadex/CDNA, retail binaries)**
- No study specific to Nadex/CDNA or retail fixed-odds binaries turned up. Gauriot & Page state that "empirical research has confirmed that binary options prices tend to be well-calibrated." Their "binary options" are exchange betting contracts, not Nadex. Source: [NYUAD WP](https://nyuad.nyu.edu/content/dam/nyuad/academics/divisions/social-science/working-papers/2021/0058(2).pdf)
- Index-option pricing kernels show the inverse-S probability weighting (overweighting small probabilities, underweighting large ones) that would underprice deep in-the-money binaries. This comes from S&P options, not binaries. Source: [Polkovnichenko & Zhao, SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2189482)

### Inferences
- Across venues, the measured favourite-side mispricing is about **0.3-1pp of win probability**. That is the whole raw edge for a 90-99c buyer.
- In return terms, a 1pp gap at 95c is about +1.05%, and a 0.3pp gap at 99c is about +0.3%. The edge is real in aggregate but thin enough that fees, spread and adverse selection decide the outcome (see §2).
- The edge is not uniform:
  - It is absent in Polymarket sports and in some Betfair in-play football settings, where favourites are overpriced.
  - Weather data show *favourite overpricing* in the last hours.
  - "Late in the window means cheap favourites" is therefore not a general law. It holds in some market types and reverses in others.
- The Gauriot & Page under-reaction to large late shocks is the closest academic analogue to a late-window favourite being underpriced after a decisive move. A plausible mechanism is capital/budget limits: buying near-certain contracts ties up a lot of capital for a small payoff.

### Gaps
- **No peer-reviewed or working-paper calibration of 5/15-minute crypto up/down markets on either venue.** Bürgi et al. excluded them, and Cardozo et al. do not split them out of "Crypto".
- No published 90-99c *by-cent* calibration table for Kalshi or Polymarket was retrievable. Becker's 95c figure is the only point estimate found.
- Nadex/CDNA: no FLB study found. Its rebrand to Crypto.com Derivatives North America and its current product set were not verified in this pass.
- No study found of the Betfair in-play FLB specifically in the final minutes for tennis or racing. The Green et al. and Data Golf points come from search snippets or secondary summaries.

---

## 2. Why the bias exists, and how fee formulas change net returns at 90-99c

### Takeaway
The leading explanation is behavioural: traders overweight small probabilities (prospect theory), and disagreeing traders self-select into taking versus making. Risk-love is a weaker explanation. Limits to arbitrage also matter: thin books, huge variance per contract, capital tied up for a tiny payoff, and the anomaly not yet being widely known.

Kalshi and Polymarket crypto both use a 0.07·p·(1−p) taker fee. At 90-99c that requires the favourite to win an extra 0.07-0.63pp just to break even, which is the same order as the measured FLB. Taker edge is therefore about zero or negative, and maker edge is what survives.

### Cited findings
- **Misperceptions over risk-love.** Snowberg & Wolfers test both explanations against exotic-bet prices. They find "misperceptions of probability drive the favorite-longshot bias, as suggested by Prospect Theory" [WP/NBER, 2010]. Source: [NBER PDF](https://www.nber.org/system/files/working_papers/w15923/w15923.pdf)
- **Kalshi model.** Bürgi et al. find that heterogeneous but unbiased beliefs cannot match the data. "Modest levels of disagreement and a small tendency to overstate small probabilities" can.
  - Takers have more extreme beliefs, so they pay up rather than risk not being filled. That is why takers do worse. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Why it hasn't been arbitraged away** (Bürgi et al., §6). They give three reasons:
  1. Small volumes: top-decile Kalshi markets average only $526k total volume, and resting depth is far smaller.
  2. Riskiness: makers' returns on contracts at 50c or above have a standard deviation of 33%. Under "proper risk aversion", a positive mean can be fair compensation.
  3. Lack of information: they expect the anomaly may fade once publicised. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **"Optimism tax".** Takers lean toward affirmative (YES) and longshot outcomes. NO outperforms YES at 69 of 99 price levels, and dollar-weighted returns are −1.02% for YES and +0.83% for NO. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- **Cost of carry / discounting.** Page & Clemen (2013) found InTrade FLB in contracts trading well over 10 days from close and explained it by discounting of the future payout. There were no significant deviations near close (as summarised by Bürgi et al.). Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Kalshi taker fee.** The fee is $0.07·P·(1−P) per contract, **rounded up to the next cent on the order total**. At 50c on 100 contracts the round-up gives a 1.77% fee instead of 1.75%. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Kalshi maker fee.** Introduced after April 2025 on selected series: 0.0175·C·P·(1−P), rounded up. The fee schedule was last updated 5 Feb 2026, per a search snippet; the PDF returned HTTP 429.
  - One vendor says the 15-minute BTC series carries **no maker fee** [VENDOR]. Other sources say Kalshi applies per-series multipliers and that crypto can run higher. Sources: [Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf); [Bot for Kalshi](https://www.botforkalshi.com/blog/kalshi-bitcoin-bot); [startpolymarket review](https://startpolymarket.com/reviews/kalshi-review/)
- **Polymarket fees (docs as fetched Oct 2026).** Taker fee = C·feeRate·p·(1−p); makers pay nothing.
  - Crypto feeRate is 0.07 with a 20% maker rebate. Sports and others are 0.05; finance and politics 0.04; geopolitics 0.
  - Fees are rounded to 5 decimals, so there is **no cent round-up**.
  - Crypto fee per 100 shares: $0.63 at 90c, $0.33 at 95c, $0.07 at 99c. Source: [Polymarket docs](https://docs.polymarket.com/trading/fees.md)
  - History: the earlier January 2026 schedule was feeRate 0.25 with exponent 2 (peak about 1.56%). A March 30 2026 version was 0.072 with exponent 1 (peak 1.80%). These come from cached-doc snippets. Sources: [Polymarket docs](https://docs.polymarket.com/trading/fees); [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- **Does a fee tilt FLB?** On Polymarket, markets with a fee flag show no consistently larger longshot losses. Favourite returns are +0.371% (child) and +0.333% (pooled) with fees, against +0.260% and +0.864% without. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)

### Inferences

Fee drag at 90-99c (the project's own arithmetic from the cited 0.07·p·(1−p) and 0.0175·p·(1−p) formulas):

| Price | Taker fee (c/contract) | Fee as % of cost | Break-even win rate, 100-lot taker (Kalshi, cent round-up) | Break-even win rate, 1-lot taker (Kalshi) | Break-even, maker at 0.0175 |
|---|---|---|---|---|---|
| 90c | 0.63 | 0.70% | 90.63% | 91.0% | 90.16% |
| 92c | 0.52 | 0.56% | 92.52% | 93.0% | 92.13% |
| 95c | 0.33 | 0.35% | 95.34% | 96.0% | 95.09% |
| 97c | 0.20 | 0.21% | 97.21% | 98.0% | 97.06% |
| 98c | 0.14 | 0.14% | 98.14% | 99.0% | 98.04% |
| 99c | 0.07 | 0.07% | 99.07% | **100% (impossible)** | 99.02% |

- The fee shape p(1−p) is small in absolute cents at the extremes. But it is a 0.07·(1−p) share of cost, so cheap contracts pay about 6-7% of price and 95c contracts about 0.35%.
- The bigger hazard at the top is **Kalshi's per-order cent round-up**. A 1-lot at 99c pays 1c, the entire upside. Small orders at 97-99c are structurally unprofitable as a taker, while Polymarket's 5-decimal rounding has no such penalty.
- Measured favourite-side mispricing (0.3-1pp) is about the same size as the taker fee at 90-95c (0.33-0.63pp). Taking liquidity at 90-92c needs a larger-than-average bias to clear fees. Taking at 97-99c clears fees more easily per contract but leaves only 1-3c upside, so a single loss wipes out 30-99 wins.
- Spread is a second cost on top of the fee: one practitioner says 15-minute BTC spreads are often 1-3c. Source: [val.run tracker](https://jacksonfletcher--5d772954845911f1927e1607ee4eb77e.web.val.run/)

### Gaps
- Kalshi's current per-series fee multiplier and maker-fee status for the 15-minute crypto series could not be confirmed from a primary source (the fee PDF was rate-limited). Check kalshi.com/fee-schedule directly.
- Whether Kalshi still rounds fees up per order to the cent in 2026 was not confirmed from a primary 2026 source. The cited formula is from the 2021-Apr 2025 sample period.
- No study isolates the cost-of-capital channel for intraday markets. With a 15-minute hold, discounting is negligible, so this channel should matter far less than for multi-day contracts. This is an inference.

---

## 3. Short-horizon crypto up/down markets: late-window favourites, "last-minute flip" risk, latency arbitrage against spot and oracles

### Takeaway
There is no academic study of late-window favourites in 5/15-minute crypto markets. The best available data is practitioner-grade:
- A vendor study of 6,298 Kalshi 15-minute BTC windows found the leading side settles about 1pp better than its price. That is a +0.67c gross edge per contract, below the ~1.55c average taker fee.
- A 1,600-window study found late flips concentrate almost entirely in windows that finish within about $50 of the strike.

Latency arbitrage against Binance/Coinbase spot was real and lucrative on Polymarket in late 2025. Fees, removal of the taker delay, and later order locks were introduced to curb it.

### Cited findings
- **Bot for Kalshi study [VENDOR, updated 16 Sep 2026; data to 2 Aug 2026].**
  - Sample: 6,298 settled Kalshi 15-minute BTC windows.
  - Across eleven price bands, the leading side settled "roughly one point" better than its price, a gross edge of about **+0.67c per contract**.
  - The average taker fee on those fills was about **1.55c**, so taking was "net negative at every entry time tested, including the last minute."
  - The vendor treats resting limit orders as the only non-negative style, and says the series has no maker fee. No per-band table is published. Source: [Bot for Kalshi](https://www.botforkalshi.com/blog/kalshi-bitcoin-bot)
- **OddsShopper "late flips" study [NEWS/practitioner, updated 11 Oct 2026].**
  - Samples: 200 Kalshi 15-minute BTC windows (4-6 Sep 2026), plus seven reruns of 200 windows each to 11 Oct (1,600 windows in total).
  - A flip is defined as the result going against the side Yes was leaning two minutes before close. The original sample had **31 flips, all in windows finishing within $50 of the line** (28 within $25). None of the 66 windows finishing $50 or more away flipped.
  - Across reruns there were only 7 flips in 821 windows finishing $50 or more from the line.
  - Losing sides priced 70c or better made up 23 of 31 flips in the original sample. One example is a **91c Yes with 2 minutes left that settled No**.
  - Spreads are "widest" in the final two minutes. The author recommends avoiding the last two minutes and using limit orders.
  - There is no calibration-by-price table. Source: [OddsShopper](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged)
- **Kalshi settlement.** Kalshi's 15-minute crypto contracts settle on a **60-second average of the CF Benchmarks Real-Time Index**, sampled once per second in the final minute. The CF index aggregates multiple exchanges. Sources: [Kalshi help](https://help.kalshi.com/en/articles/13823838-crypto-markets); [predictionmarketspicks](https://predictionmarketspicks.com/articles/how-kalshi-settles-bitcoin)
- **Polymarket settlement and manipulation.**
  - Polymarket's 5/15-minute markets resolved on a Chainlink price snapshot at window end, with Up if close ≥ open.
  - Crypto Briefing (11 Jul 2026) reported traders "synchronizing Polymarket positions with spot Bitcoin trades" in the final seconds to move the snapshot. It also said live bot win rates run 25-27% "below breakeven" (no sample given). Source: [Crypto Briefing](https://cryptobriefing.com/polymarket-bitcoin-contracts-price-manipulation/)
  - One bot vendor says that from 7/14 Aug 2026 Polymarket switched to Chainlink TWAP (time-weighted average price) over a 60-second window. **Unverified, single vendor source.** Source: [polymtradebot](https://polymtradebot.com/)
- **Latency arbitrage.**
  - Bots exploited lags between Polymarket prices and Binance/Coinbase spot under zero fees. They entered near 50/50 odds and exited as prices converged.
  - One wallet made "thousands of such trades in one month" with a very high success rate. A post claimed "$313 → $414k in one month" [ANEC].
  - Polymarket's response, on 7 Jan 2026, was a dynamic taker fee (peak about 3.15% at 50c per Finance Magnates) funding maker rebates. Sources: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/); [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
  - Vendor claims of a 1.5-3s Polymarket lag versus spot and sub-200ms bot execution are **unverified**. Source: [polymtradebot](https://polymtradebot.com/blog/how-automated-arbitrage-works-on-polymarket)
- **Polymarket microstructure timeline [NEWS, secondary].**

  | Date | Change |
  |---|---|
  | ~18 Feb 2026 | 500ms taker delay removed on crypto markets (no announcement) |
  | 5 Jun 2026 | Taker orders on crypto and finance up/down markets lock once inside a 250ms window (single source) |

  Sources: [JavaScript in Plain English](https://javascript.plainenglish.io/how-to-build-a-polymarket-trading-bot-in-2026-after-the-new-rules-edition-6dfe61452c85); [cryptonews.net / Protos](https://cryptonews.net/news/market/32461495/); [brainsum mirror](https://san-1510.aid.brainsum.com/news/top-news/polymarket-locks-taker-orders-curb-automated-gaming)
- **Scale.**
  - 5- and 15-minute up/down contracts are over half of crypto trading on both Polymarket and Kalshi, with about $70M combined daily volume (Mar 2026). Source: [Bitget / Crypto.News](https://www.bitget.com/news/detail/12560605263885)
  - Polymarket's 5-minute markets launched 12 Feb 2026, with about $4B cumulative volume by July. Source: [Crypto Briefing](https://cryptobriefing.com/polymarket-bitcoin-contracts-price-manipulation/)
- **Outcome base rate.** A tracker reports 25,902 Polymarket 5-minute BTC windows over 90 days, 50% resolving UP. Source: [updowncharts](https://www.updowncharts.com/markets/bitcoin/5m)

### Inferences
- **Flip risk is about distance to the strike, not time remaining.** A 90c+ price with 2 minutes left can sit on a window within $25 of the line, where flips run around 13-32%.
  - The OddsShopper data imply flip risk is concentrated where the underlying is close to the strike relative to remaining volatility. Price alone hides this, because programs reprice quickly.
  - An averaging settlement (Kalshi's 60-second CF RTI average) partly locks in the last minute's path, which damps final-second manipulation. Polymarket's single snapshot, if still in use, is more exposed.
- **The favourite edge on short crypto windows looks mostly like a maker edge.** The best available (vendor) number of about +1pp calibration, or +0.67c gross, is below average taker cost. That fits the academic pattern on Kalshi generally: makers are positive and takers negative.
- **The latency-arbitrage fight is mostly in mid-priced (around 50c) contracts.** The fees were explicitly targeted at near-50/50 arbitrage. At 90-99c the fee is small, so late favourite buying faces less fee drag but more competition from fast repricers when the underlying is near the strike.

### Gaps
- No independent (non-vendor) calibration of 90-99c prices by minutes-remaining for Kalshi or Polymarket 15-minute markets. The Bot for Kalshi per-band data are unpublished.
- Whether Polymarket now settles on a Chainlink TWAP (Aug 2026) is unconfirmed by a Polymarket primary source.
- No published measurement of Kalshi's reaction lag to CF RTI or spot moves.
- Volatility-regime conditioning (e.g. flip rates on high-volatility days) was not found in any source.

---

## 4. Competition and decay: market makers, bots and cross-venue arbitrage on Polymarket and Kalshi short-term markets (2025-2026)

### Takeaway
Professional liquidity arrived on Kalshi around 2024: Susquehanna was the first dedicated institutional market maker, and Jump took equity-for-liquidity deals with both venues in Feb 2026. Becker shows Kalshi's maker-taker return gap flipped by 5.3pp toward makers after the 2024 election. So the FLB's profits accrue mainly to makers and the edge is being competed into spreads.

There is weak academic evidence the FLB slope shrank in 2025, but a replication finds it persisted after maker fees. On Polymarket short-term crypto, bots dominate the leaderboard. Cross-venue Kalshi/Polymarket 15-minute "arbitrage" repos exist, but there is no verified P&L.

### Cited findings
- **Kalshi regime change [WP/blog].** From launch to 2023, takers earned about +2.0% and makers about −2.0%. After the 2024 election, makers were 2.5pp ahead, a 5.3pp swing; the gap crossed zero in 2024 Q2. Becker attributes this to higher volume attracting professional market makers. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- **Bias trend.** The FLB slope fell from 0.048 (2024) to 0.021 (2025, Jan-Apr only), "some evidence of a weakening". Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Persistence after maker fees** [REPL]. The maker advantage at 50c or above is +2.40% gross after the 2025 fee boundary, against +2.09% before, and the fee difference-in-differences estimate is a tight null. The exploratory event study hints at a "transitory reduction three to four months after treatment". Source: [GitHub](https://github.com/Vladosyna/kalshi-makers-takers-persistence)
- **Market makers.**
  - Susquehanna (SIG) is described as Kalshi's first dedicated institutional market maker (2024), reportedly with reduced fees and higher position limits [NEWS/blog].
  - Bloomberg (via The Block, Feb 2026) reported Jump Trading would make markets on Kalshi and Polymarket in exchange for equity. Jump's Polymarket stake scales with the US capacity it contributes.
  - Jump reportedly doubled its prediction-markets team to about 20 by mid-2026. Sources: [The Block](https://www.theblock.co/post/389086/jump-trading-to-serve-as-polymarket-and-kalshi-market-maker-in-exchange-for-stake-bloomberg); [Navnoor Bawa Substack](https://navnoorbawa.substack.com/p/which-hedge-funds-are-trading-prediction); [Crypto Briefing](https://cryptobriefing.com/jump-trading-prediction-markets-wall-street/)
  - Keyrock is quoted calling growth in 5/15-minute BTC markets "explosive". Source: [Bitget / Crypto.News](https://www.bitget.com/news/detail/12560605263885)
- **Bots on Polymarket.** Finance Magnates reports about $40M extracted by arbitrage traders in a year, and 14 of the 20 most profitable leaderboard wallets are bots. This comes from a search snippet; the article was not read in full. Source: [Finance Magnates "bot playground"](https://www.financemagnates.com/trending/prediction-markets-are-turning-into-a-bot-playground/)
- **Systematic favourite buyers do worse on Polymarket.** Wallets that recurrently buy favourites earn +0.25% against +0.88% for other favourite buyers.
  - They hold about 14-15% of favourite dollars but get 2.9-4.8% of net gains.
  - By decile of past favourite demand, the lowest decile returns 1.39% and the highest 0.25%. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **Skill concentration on Polymarket** [WP, SSRN, Apr 2026, Gómez-Cram, Guo, Kung & Jensen].
  - Sample: 1.72M accounts and $13.76B volume.
  - Only 3.14% of accounts are "skilled winners", meaning their order flow predicts both short-term price moves and final outcomes.
  - Only 12% of top earners overlap with the skilled group, and about 60% of "lucky winners" revert out of sample. Source: [The Block](https://www.theblock.co/post/398902/skilled-polymarket-traders-are-a-3-minority-and-everyone-else-funds-their-gains-study)
- **Cross-venue Kalshi-Polymarket 15-minute arbitrage.** Several open-source bots poll both APIs for YES/UP spreads and "late-resolution gaps". One only evaluates signals after minute 8. None publishes verified P&L, and they behave more like directional spread-chasing than risk-free arbitrage.
  - A DEV post claims about 5 or more opportunities per window, lasting seconds [ANEC].
  - The venues settle on different references: CF RTI 60-second average on Kalshi, Chainlink on Polymarket. So "arbitrage" carries basis risk, meaning the two settlement prices can diverge. Sources: [defi-ape repo](https://github.com/defi-ape/polymarket-kalshi-arbitrage-bot); [DEV Community](https://dev.to/benjamin_martin_749c1d57f/polymarket-x-kalshi-arbitrage-27di)
- **"Bonding" (buying 93-99c near-certain outcomes) is a widely publicised retail strategy.** Practitioner guides frame it as small steady yield with rare large losses. One X thread calls it "a valid strat" but notes under-discussed details. Sources: [predictionnews](https://predictionnews.com/learn/trading-strategy/bonds/); [probabilitygod on X](https://x.com/probabilitygod/status/1996498793026429058)

### Inferences
- **The decay channel is crowding at the favourite end, not elimination of the bias.**
  - Professional makers now sit on the favourite side and capture the mispricing via spread.
  - Retail "bonding" adds buy-side demand at 93-99c.
  - Systematic favourite buyers on Polymarket already earn less than incidental ones.
  - Expect quoted favourite prices to sit closer to true probability, or fills to be rationed, in liquid short-term series.
- **Publicity risk.** Bürgi et al. (SSRN 2025, VoxEU, Jan 2026 revision) and Becker (late 2025) have made the pattern public. Bürgi et al. themselves predict it could fade, as other anomalies do after publication.
- **Market-maker deals change the counterparty mix.** Fee discounts, equity-for-liquidity and rebates let professionals quote tighter at the extremes than an unsubsidised trader can. A non-subsidised trader competing for the same favourite fills is structurally disadvantaged on queue priority and cost.

### Gaps
- No published time series of favourite-end calibration or returns for the 15-minute crypto series specifically, so decay there is not measured.
- No verified P&L for Kalshi-Polymarket cross-venue bots, or for any named latency-arbitrage wallet beyond social-media claims.
- Whether Susquehanna or Jump quote the 15-minute crypto series specifically is not public in the sources found.

---

## 5. Adverse selection: are favourite fills mostly against informed sellers?

### Takeaway
Direct evidence for short-term prediction markets is thin. What exists points the same way:
- Passive (maker) fills earn more than aggressive ones.
- A small skilled minority's flow predicts short-term moves.
- Practitioners report that resting quotes get picked off just before moves.

Adverse selection here means fills arriving disproportionately when the price is about to move against you. For a resting bid on a favourite, the danger is filling when the underlying has just moved toward the strike.

### Cited findings
- **Maker vs taker returns on Kalshi.** Makers beat takers overall: −9.64% against −31.46% (Bürgi et al.), and +1.12% against −1.12% (Becker).
  - Bürgi et al. note makers "must also be willing to cancel those orders if new evidence emerges", so maker returns depend on fast cancellation. Sources: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf); [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
  - Becker says he cannot separate spread capture from exploiting biased flow, because historical spreads are unavailable. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- **Polymarket longshots by fill type.** Longshots bought via posted offers return −3.50% (equal child) and −17.56% (pooled). Those bought by accepting offers return −31.17% and −22.17%.
  - The authors raise, but do not test, the idea that sellers of tail tokens hold better information. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **Informed minority on Polymarket.** The 3.14% "skilled" accounts' order flow predicts short-term price moves. Suspected insider accounts move prices 7-12× more per dollar than skilled traders. Source: [The Block](https://www.theblock.co/post/398902/skilled-polymarket-traders-are-a-3-minority-and-everyone-else-funds-their-gains-study)
- **Practitioner views on 15-minute markets [VENDOR, low credibility].**
  - One says informed traders "take your most aggressive bid or ask right before the market moves against you", and that maker rebates do not remove that risk.
  - Another claims rebates "absorb the adverse selection". The two conflict. Sources: [polyscalping](https://polyscalping.org/leaderboard/maker); [startpolymarket](https://startpolymarket.com/learn/polymarket-rebates-rewards/)
- **Removal of Polymarket's 500ms taker delay.** Removing it took away the window that let makers adjust quotes, which makes latency the main edge and raises makers' pick-off risk. Source: [cryptonews.net / Protos](https://cryptonews.net/news/market/32461495/)
- **Theory.** In limit-order-book models (Glosten-Milgrom, Roşu), the spread reflects the probability of informed trading. Informed traders using limit orders gain about half the spread but suffer decay costs. Source: [Roşu JFQA 2020](https://people.hec.edu/rosu/wp-content/uploads/sites/43/2020/09/info_lob_JFQA_2020.pdf)

### Inferences
- In 15-minute crypto markets, the "informed seller" is usually a faster trader reacting to spot or index moves, not someone with private news.
  - A resting bid at 90-95c is most likely to fill when spot has just ticked toward the strike, which is exactly when the true probability has dropped.
  - This is why measured calibration of *traded prices* can overstate the edge of *a given order's fills*. Conditional-on-fill calibration is the relevant test.
- A trader's own order data can test this directly: compare the win rate of filled orders with unfilled-but-would-have-won orders at the same quoted price. Academic sources do not provide this for short-term markets.

### Gaps
- No academic study of fill-conditional (adverse-selection-adjusted) returns for 5/15-minute crypto prediction markets.
- No public data on Kalshi's maker cancel/replace latency relative to spot, or on who supplies favourite-side liquidity in the last minutes.

---

## 6. Which venue characteristics predict an exploitable favourite bias

### Takeaway
The favourite edge is largest where:
- order flow is retail and "high-engagement";
- fees fall proportionally hardest on cheap contracts (which pushes longshot buyers to overpay);
- tick size and price caps compress the top of the book;
- professional makers are absent or unsubsidised.

The edge is smallest or reversed where:
- flow is professional (finance markets);
- the market is pari-mutuel with a large take;
- sports in-play markets overreact to favourite news.

### Cited findings
- **Retail engagement.** On Kalshi the maker-taker gap is largest in high-engagement categories: Entertainment 4.79pp, Media 7.28pp, World Events 7.32pp, Crypto 2.69pp, Sports 2.23pp. Finance has a gap of only 0.17pp. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
  - On Polymarket, the FLB is strongest in Crypto and Politics and absent in Sports. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **Volume does not kill it.** On Kalshi the bias appears in every volume quintile; only the lowest quintile is notably worse. The highest trade-size quintile has the *largest* slope. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Fee shape.**
  - The p(1−p) fee is about 7% of cost on a 1c contract against 0.07% at 99c. Bürgi et al.'s model shows taker fees shape who becomes a taker versus a maker, and amplify taker losses. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
  - On Polymarket, fee-enabled markets did not show consistently larger longshot losses. Source: [arXiv HTML](https://arxiv.org/html/2609.12878v1)
- **Market structure.**
  - Pari-mutuel US racing shows a strong FLB, but favourites still lose 5.5% after the take. Source: [NBER PDF](https://www.nber.org/system/files/working_papers/w15923/w15923.pdf)
  - Order-driven exchanges show weaker or reverse FLB: Betfair is well calibrated with a small longshot bias, and EPL in-play shows a favourite bias. Sources: [NYUAD WP](https://nyuad.nyu.edu/content/dam/nyuad/academics/divisions/social-science/working-papers/2021/0058(2).pdf); [Angelini et al.](https://www.carlsingletoneconomics.com/uploads/4/2/3/0/42306545/information_efficiency_angelini_de_angelis_singleton.pdf)
  - Angelini et al. suggest exchange bettors may be less risk-loving and better informed than bookmaker customers, which would explain the reverse FLB there. Source: [Angelini et al.](https://www.carlsingletoneconomics.com/uploads/4/2/3/0/42306545/information_efficiency_angelini_de_angelis_singleton.pdf)
  - Bürgi et al. note Kalshi's FLB "mirrors the biases long documented in traditional betting markets where prices are set by bookmakers or via a pari-mutuel system". Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Tick size and price bounds.** Kalshi trades only in whole cents from 1c to 99c, with no 32.5c-type prices. Source: [Kalshi.pdf](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Market-maker incentives.**
  - Polymarket rebates 20% of crypto taker fees to makers. Source: [Polymarket docs](https://docs.polymarket.com/trading/fees.md)
  - Kalshi offered Susquehanna reduced fees and higher position limits [blog]. Source: [Navnoor Bawa Substack](https://navnoorbawa.substack.com/p/which-hedge-funds-are-trading-prediction)
  - Jump has equity-for-liquidity deals with both venues. Source: [The Block](https://www.theblock.co/post/389086/jump-trading-to-serve-as-polymarket-and-kalshi-market-maker-in-exchange-for-stake-bloomberg)

### Inferences
- **A whole-cent tick with a 99c cap mechanically creates apparent FLB at the top.** A contract whose true probability is 99.6% can only print at 99c, and the last cent of upside is the full reward. Venues with finer ticks near the extremes should show less of this artifact. That Polymarket uses sub-cent ticks near 0/1 is from general knowledge, not verified in this pass.
- **Ranking venues by expected favourite edge for a non-subsidised trader** (judgement from the cited evidence):
  1. Retail-heavy order-book venues with cheap-contract-taxing fees and thin professional quoting (newer or smaller series): highest.
  2. Kalshi and Polymarket main crypto up/down series: real but thin maker-side edge, with competition from subsidised makers and latency traders.
  3. Pari-mutuel venues: the take overwhelms the favourite underpricing.
  4. Sports in-play exchanges: can be reversed.
- **Short-dated windows remove the cost-of-capital rationale for the FLB** (relevant to multi-day contracts per Page & Clemen). What is left is behavioural demand for longshots, plus the tick and fee effects. These are exactly the components that professional makers can harvest first.

### Gaps
- No cross-venue study isolating tick size, fee shape or maker incentives as causes of FLB magnitude. The above is pieced together from single-venue studies.
- Polymarket's current tick-size rules near 0/1, and Kalshi's 2026 status on sub-cent pricing, were not verified from primary docs in this pass.
- No data found on other venues' short-dated crypto binaries (Robinhood/Coinbase prediction hubs, Crypto.com/CDNA, offshore binaries) for 2025-2026 favourite-end calibration.
