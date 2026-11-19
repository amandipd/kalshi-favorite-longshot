# The favorite-longshot bias: literature on its size, causes, persistence and tradability, and what it means for buying 90-99.9c favorites late in Kalshi 15-minute markets

Scope note: "favorite-longshot bias" (FLB) = cheap contracts (longshots) win less often than their price implies and expensive ones (favorites) win more often. Buying a favorite at 95c is economically the same as selling a 5c longshot, so every finding that longshots are overpriced is also a finding that favorites are underpriced. "Maker" = posts a resting limit order; "taker" = hits an existing quote and (on Kalshi) pays the taker fee. Our bot is a taker. Research date 2026-10-09. Items marked UNVERIFIED come from snippets, secondary write-ups or non-peer-reviewed repos.

## 1. Causes: which explanations predict a larger bias, and under what conditions (time to expiry, liquidity, trader mix, price level, volatility)?

### Takeaway
The best-supported mechanism in modern exchange-style markets is "modest disagreement + a small tendency to overweight small probabilities + taker self-selection and fees". Pure risk-love has lost ground. A separate late-event effect (the "Yogi Berra" bias: losing sides stay overpriced near the finish) makes the bias larger close to expiry. That is the condition our minute-8-of-15 entry is exposed to. Long-horizon bias is mostly a discounting/capital-lockup effect, which does not apply to 15-minute contracts.

### Cited findings
**Classic explanations**
- Snowberg & Wolfers (JPE 2010, vol. 118(4), 723-746): using a large horse-racing dataset, they test whether a model fitted to win bets also prices exotic bets (exacta, quinella, trifecta). The evidence favors misperception of probabilities (prospect-theory-style probability weighting) over risk-love. Source: [NBER w15923](https://www.nber.org/papers/w15923)
- Ottaviani & Sørensen: the FLB can come from privately informed bettors who bet at the same time (often late) without seeing each other's bets. "The direction and the extent of the bias depend on the amount of private information relative to noise." More information relative to noise gives a larger standard FLB; a noise-dominated market can show the reverse. Sources: [Ottaviani & Sørensen 2006 WP "Noise, Information, and the FLB"](https://www.economics.ku.dk/research/workingpapers/centerpapers/fru-wp/archive/2006_04.pdf); [Ottaviani & Sørensen, "Surprised by the Parimutuel Odds?" (AER 2009)](https://web.econ.ku.dk/sorensen/papers/SBO.pdf)
- Whelan (Economica 2024): in a competitive fixed-odds market, an FLB can come from bettors' disagreement plus bookmaker risk aversion, even when bettors are right on average. Sources: [Whelan, Economica final version](https://www.karlwhelan.com/Papers/EconomicaFinal.pdf); [MPRA 116923](https://mpra.ub.uni-muenchen.de/116923/)

**Exchange / quote-driven microstructure (the Kalshi-relevant model)**
- Bürgi, Deng & Whelan (BDW; GWU CER WP 2026-001, Feb 2026, paper dated Jan 2026). In their model, traders with the most extreme beliefs choose to be takers, so takers do worse. A model with disagreement only (β=0) cannot fit the data: it predicts makers profit most on cheap contracts, the opposite of what is observed. Fitting the data needs a belief bias toward 0.5 of β≈0.06-0.12 (calibrated β=0.09), disagreement σ=0.107 and match rate θ=0.6. "Behavioral bias is necessary... but the level of bias required... is modest." Source: [BDW 2026-001 (GWU)](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- BDW: takers lose more on cheap contracts for two reasons. Kalshi's fee 0.07·P·(1−P), rounded up, is a larger fraction of a low price, and the bid-ask spread is a larger fraction of a cheap contract's price. Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Whelan, "Agreeing to Disagree: The Economics of Betting Exchanges" (CEPR DP20633, Jan 2026), studies a maker/taker model on more than 200,000 Betfair soccer matches (2022-24). Pre-match and early in-play returns fit the model: takers' losses grow as their bet's win probability falls, and makers sit near break-even. Sources: [Whelan, Betfair paper PDF](https://www.karlwhelan.com/Papers/Betfair.pdf); [CEPR DP20633](https://cepr.org/publications/dp20633)
- Becker (Kalshi, 72.1M trades, $18.26B, 2021 to Nov 2025) calls it an "optimism tax": takers lean toward affirmative (YES) outcomes. NO outperforms YES at 69 of 99 price levels. At 1c, YES has an expected value of −41% versus +23% for NO. Dollar-weighted, YES returns −1.02% and NO +0.83%. Makers profit "by accommodating biased flow" rather than by forecasting better. Practitioner research (also listed as SSRN WP 7217640); not peer-reviewed. Source: [Becker, "The Microstructure of Wealth Transfer in Prediction Markets"](https://www.jbecker.dev/research/prediction-market-microstructure)

**Late-event / near-expiry effects**
- Page (2012), "Yogi Berra bias" on InTrade: across 1,100 US sports markets, prices for losing teams in the final 15 minutes were too high relative to how often they won. Page suggests "higher emotional tension" near the end distorts probability judgment. As summarized in [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf) and [Whelan Betfair paper](https://www.karlwhelan.com/Papers/Betfair.pdf) (original: Applied Economics 44, 81-92; not fetched)
- Whelan argues that if risk-seeking or small-probability misperception were fixed traits of bettors, longshots would do badly pre-match too. Instead the bias appears late, and he suggests late bettors switch from "slow" to "fast" thinking while watching live. Source: [Whelan Betfair paper](https://www.karlwhelan.com/Papers/Betfair.pdf)
- Moshrefi (Princeton, arXiv July 2026; about 23M Kalshi NBA/MLB/NHL moneyline trades, Mar-May 2026): calibration is close to perfect 30-240 minutes before settlement. In the final 10 minutes the price-to-outcome curve turns step-like, with Platt slopes of 1.62 (NBA), 2.05 (MLB) and 4.56 (NHL). A Platt slope above 1 means true probabilities are more extreme than prices: favorites underpriced, longshots overpriced. The author calls this "consistent with insurance-demand behavior by traders holding losing positions" but cannot rule out other explanations. Source: [arXiv 2607.14430](https://arxiv.org/html/2607.14430)

**Horizon, liquidity, trade size and category conditions**
- Page & Clemen (Economic Journal 2013): InTrade longshots were too expensive and favorites too cheap mainly in contracts traded well over 10 days before close, which they attribute to discounting of the future payout. Near close they found no significant miscalibration. As summarized in [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Domain-specific calibration study (arXiv 2602.19520, Kalshi: 64.7M trades and 210,608 contracts through Dec 2025): underconfidence (prices compressed toward 50, i.e. an FLB in the 5-95c interior) grows with horizon, from a slope of 0.99 at 0-1h to 1.32 beyond one month. **Kalshi crypto is calibrated at short horizons: slope 0.99 at 0-1h and 1.01 at 1-3h**, rising to 1.36 beyond one month. Finance is 0.96 at 0-1h. Weather is overconfident at short horizons (0.69). The study filters to 5-95c, so it says nothing about our 90-99.9c tail. Source: [arXiv 2602.19520v2](https://arxiv.org/html/2602.19520v2)
- BDW, final volume quintiles: the lowest-volume quintile has the largest bias coefficient (ψ=0.045). Otherwise more volume does not mean less bias (top quintile ψ=0.032). By mean trade size, the largest-trade quintile has the largest ψ (0.043). Source: [BDW Tables 6-7](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- BDW, by category (ψ = the slope of pre-fee profit on price; larger means a stronger FLB): **Crypto 0.058 (the largest of any category)**, Other 0.053, Economics 0.034, Financials 0.032, Climate/Weather 0.031, Politics 0.022 (not significant), Entertainment 0.020 (not significant). BDW excluded Kalshi's hourly crypto and index markets, so this is crypto markets open at least 24 hours. Source: [BDW Table 8](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Polymarket (Cardozo & Rivero-Wildemauwe, arXiv Sep 2026; about 588M trades): the FLB is stronger in more heavily traded markets. Pooled favorite returns by previous-trading quartile are +0.491%, +0.384%, +0.323% and +1.265%. The authors link this to Ottaviani-Sørensen. Misperception fits the interior of the price curve better than the tails. Recurrent longshot buyers earn about what other wallets earn (−21.96% vs −20.33%), so there is no evidence of a distinct risk-loving group bearing the losses. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Becker, Kalshi maker-taker gap by category: Finance 0.17pp, Politics 1.02pp, Sports 2.23pp, Weather 2.57pp, **Crypto 2.69pp**, Entertainment 4.79pp, Media 7.28pp, World Events 7.32pp. He attributes the differences to participant selection: "dry" quantitative markets filter out emotional bettors. Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)

**Why it is not competed away (limits to arbitrage)**
- BDW give three reasons. Volumes are small: the top-decile market averages $526,245 and order books are thin. Risk is high: the standard deviation of return on maker purchases at 50c or more is 33%, and under Samuelson/Pratt-Zeckhauser "proper risk aversion" a rational investor may decline even many independent bets. And traders may not know about it. Source: [BDW §6](https://www2.gwu.edu/~forcpgm/2026-001.pdf)

### Inferences
- For a 15-minute contract, the capital-lockup/discounting explanation (Page & Clemen) is irrelevant. What is left is probability weighting, late-event "fast" or emotional trading, taker optimism and lottery demand on the cheap side, and fee/spread wedges. All of these predict the bias is **largest at extreme prices and close to expiry**, which fits the minute-8 design and the bias we measured.
- Interior crypto prices on Kalshi are calibrated at under an hour, so any short-horizon crypto edge should sit only in the tails (roughly 1-10c and 90-99c). That matches our finding and suggests not widening the entry band below 90c.
- Becker's YES-preference finding suggests a test: in up/down markets, is a favorite on the NO/"Down" side (so the longshot is a YES) more underpriced than a favorite on the YES/"Up" side? This is a hypothesis; no study tests it on 15-minute markets.
- Ottaviani-Sørensen and the Polymarket trading-activity result predict a larger bias in the busiest markets (e.g. BTC versus thin metals or energy series). BDW's lowest-volume quintile also shows a large bias, so the volume relationship may be U-shaped or noisy. Worth testing on our data rather than assuming either direction.

### Gaps
- No study was found that conditions the FLB on the underlying asset's volatility (realized or implied) in short-dated binaries. Whether favorites are more underpriced in calm or volatile 15-minute windows is untested in the literature.
- The full texts of Snowberg & Wolfers and Ottaviani & Sørensen could not be read (abstracts only), so effect sizes from the classic horse-racing literature are not reported here.

## 2. Kalshi and Polymarket evidence, and how the bias has changed over 2023-2026

### Takeaway
Both platforms show an FLB in which favorites at 90c and above earn small positive returns: about +0.2% to +1% before fees on Polymarket, and "small positive" on Kalshi. The gain to favorites mostly goes to makers. Takers buying favorites on Kalshi lost money on average after fees in 2021 to April 2025. There are early signs of weakening: BDW's 2025 coefficient is smaller, the 91-99c share of Kalshi taker volume has collapsed, and on Polymarket dedicated favorite-buying wallets earn less. But no study shows the bias has gone.

### Cited findings
**Kalshi: Bürgi, Deng & Whelan (2021 to Apr 2025)**
- Sample: 46,282 contracts from 12,403 events, each open at least 24 hours, with at least $1,000 volume and a final spread of 20c or less. That gives 313,972 Yes+No prices from closing day back to 10 days before close. 33.8% of prices are in 90-99c and 33.8% in 1-10c. Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Contracts at 10c or less lose more than 60%. Contracts above 50c earn small positive returns, and above 70c those returns are "statistically significant, though small," after taker fees. The average pre-fee return across all contracts is about −20% because of the asymmetry. Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Average return is −9.64% for makers and −31.46% for takers. Makers buying at 50c or more earn +2.6%. **For takers, "loss rates... decline [as prices rise] but they still lose money on average"**, so after fees, takers buying high-priced contracts were slightly negative on average. Makers account for 56.5% of 90-99c purchases. Source: [BDW §4-5, Table 10](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Fees in the sample: takers paid $0.07·P·(1−P) per contract, rounded up to the next cent per order; makers paid nothing. Kalshi began charging some makers after April 2025. Source: [BDW §2.2](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- **Over time:** ψ by year was 0.041 (2021), 0.023 (2022), 0.036 (2023), 0.048 (2024) and 0.021 (2025, January to April, significant only at 10%). The authors call this "some evidence of a weakening". Source: [BDW Table 9](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- The bias holds on every horizon from closing day (ψ=0.036) to 10 days out (0.038), ranging 0.017-0.041. Accuracy (mean absolute error) improves toward close, with a steep drop on the last day. Source: [BDW Table 5, Fig. 4](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- On closing-day prices, makers' losses on cheap contracts look like takers', which the authors read as a possible Kalshi "Yogi Berra effect" late in a market's life. Source: [BDW §4](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Coverage: [VoxEU column](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market); [SSRN 5502658](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5502658).

**Kalshi: Becker (2021 to Nov 2025, practitioner)**
- 5c contracts win 4.18% (mispricing −16.36%). **95c contracts win 95.83%.** Every price below 20c underperforms and every price above 80c outperforms. Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)
- Overall, takers earn −1.12% and makers +1.12%. Takers are negative at 80 of 99 price levels. Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)
- **The sign changed over time.** In 2021-2023, takers averaged +2.0% and makers −2.0%. The gap crossed zero in 2024 Q2 and widened after the November 2024 election, from −2.9pp to +2.5pp, a 5.3pp swing, while volume went from $30M (2024 Q3) to $820M (2024 Q4). **The 91-99c share of taker volume fell from 40-50% (2021-23) to under 20% (2025).** Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)

**Kalshi: independent replication after maker fees (UNVERIFIED, GitHub)**
- Reproduces BDW's by-year signs through April 2025. The maker margin at 50c or more is +2.09% (BDW: +2.6%) and +2.40% gross after the 2025 fee boundary. A difference-in-differences test of the maker-fee "treatment" gives −0.0016 (SE 0.0064), a tight null; an event study hints at a "transitory reduction three to four months after treatment". 41% of the change in the aggregate FLB slope at the 2025 boundary is composition: sports went from 0.009% of the 2024 sample to 58.8% after May 2025. Source: [Vladosyna/kalshi-makers-takers-persistence](https://github.com/Vladosyna/kalshi-makers-takers-persistence)

**Kalshi: other**
- A Kalshi unemployment-market FLB study exists, but it was not read. Source: [ResearchGate](https://www.researchgate.net/publication/409238145_Market_Efficiency_and_the_Favorite-Longshot_Bias_in_Unemployment_Prediction_Markets)
- Kalshi's own calibration publication reportedly finds prices "extremely well calibrated as markets approach resolution" (per a search-engine summary; the page returned HTTP 429 twice, UNVERIFIED). Source: [Kalshi Research: Calibration](https://kalshi.com/research/publications/calibration)

**Polymarket: Cardozo & Rivero-Wildemauwe (Nov 2022 to Mar 2026; about 588M trades, 2.48M wallets)**
- **Favorites (90c and above): +0.277% (equal weight per market), +0.83% (dollar-pooled), +0.392% (equal weight per parent event).** Longshots (below 10c): −6.30%, −19.35% (confidence interval includes 0) and +4.09% under the same three weightings, so the sign of the longshot result depends on how you weight. Favorites are positive under all three. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- **Crypto: favorites +0.643% equal-weight and +0.537% pooled; longshots −14.84% and −12.63%.** Politics favorites +1.044% and +1.419%. Sports is the exception: favorites −0.230% equal-weight and +0.137% pooled. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- **Buyer action (posted versus accepted offers): favorites bought by accepting a seller's offer (taker-like) return −0.460% equal-weight and +0.877% pooled. Favorites bought by posting an offer (maker-like) return +0.641% and +0.816%.** Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- **Crowding among favorite buyers:** wallets in the top decile of favorite buying, who persistently buy favorites, earn +0.25% versus +0.88% for other wallets and capture only 4.8% of the net favorite gain. Persistence falls from 64.5% after one month to 15.8% after six months. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Fees: no consistent pattern of larger longshot losses in markets that report fees. Favorites return +0.371% equal-weight in fee markets versus +0.260% without fees. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Experience: every experience group loses on longshots. Favorite returns rise slightly with experience, from +0.60% to +0.84% pooled. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- The quarterly trend over time is in the paper's Figure 6, but the values are not in the readable text. Q1 2026 estimates are provisional. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)

**Polymarket: other**
- Not every sample shows the bias. One analysis of 2,946 resolved markets finds no classic FLB (calibration slope 0.999, SE 0.040, 30 days before resolution) and a slight reverse in the 5-20% range. Practitioner repo, UNVERIFIED. Source: [CH4RL3I/honest-odds](https://github.com/CH4RL3I/honest-odds)
- In the domain-calibration study, political underconfidence (an FLB) replicates on Polymarket. Polymarket's sub-3-hour timestamps are too noisy for short-horizon cells. Source: [arXiv 2602.19520v2](https://arxiv.org/html/2602.19520v2)
- In Polymarket's 15-minute crypto markets, taker fees were added to fund maker rebates and blunt latency arbitrage. The peak fee is at 50% and smaller in the tails; reported peak levels vary from about 1.56% to 3% between sources (UNVERIFIED levels). Sources: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates); [Unchained](https://unchainedcrypto.com/polymarket-introduces-taker-fees-in-15-minute-markets/)

**Crypto-linked binaries versus options**
- Polymarket Bitcoin threshold contracts priced "Yes" an average of 5.6pp above Binance option-implied risk-neutral probabilities (t=6.46; pooled 6.3pp; 11pp versus Deribit). The gap is largest for low-probability, long-maturity contracts and has a half-life of about 4.2 hours. A delta-hedged arbitrage proxy made 16 trades with a 69% net win rate. The sample is small (214-287 hourly observations, 2023). Source: [Portnaya, arXiv 2606.19517](https://www.alphaxiv.org/abs/2606.19517)

### Inferences
- **Taker versus maker matters more than anything else in the literature for our bot.** On both platforms, most of the favorite premium goes to whoever posts the order. Kalshi takers buying favorites were about break-even to slightly negative after fees in BDW's data, and equal-weighted taker-like favorite purchases on Polymarket are −0.46%. Our measured edge of a few tenths of a cent as a taker is consistent with this. Posting a resting bid one tick under the ask at minute 7-8 could capture more of the edge, but fill rates and adverse selection (fills arrive when price moves against you) must be measured. Kalshi's post-2025 maker fees on 15-minute crypto markets need checking.
- Our data match Becker's closely: 95.8% wins in a bucket averaging about 94.4c, versus Becker's 95c contracts winning 95.83%. That suggests the 15-minute markets carry roughly the same size of tail bias as Kalshi overall, about 1-1.5pp in win rate, before fees and slippage.
- The two Kalshi time series point the same way. The share of taker flow at 91-99c fell sharply and the 2025 coefficient is smaller. On Polymarket, dedicated favorite buyers already earn less than incidental ones. **Expect the favorite edge to be competed down as more bots run the same "buy 90c+ late" strategy.**

### Gaps
- No study measures the FLB in Kalshi's 15-minute (or hourly) crypto, metals or energy markets. BDW excluded markets open under 24 hours, and the domain study excludes prices outside 5-95c.
- No published Kalshi FLB estimates for May 2025 to Oct 2026 except the unverified GitHub replication.
- Kalshi's own calibration page could not be retrieved (HTTP 429).

## 3. High-frequency, in-play and near-expiry evidence: are heavy favorites late in an event under- or over-priced, and do markets overreact to surprising moves?

### Takeaway
The best recent evidence (Whelan 2026 on more than 200,000 Betfair matches; Moshrefi 2026 on Kalshi sports) finds **favorites become underpriced late in events**. Takers can earn small, statistically significant profits backing strong favorites in the second half. This echoes Page's "Yogi Berra" bias. An older Betfair Premier League study found the reverse (favorites overpriced in-play), and the evidence on reactions to surprises conflicts (overreaction in one study, underreaction in another). In short-dated options, buyers of cheap out-of-the-money lottery tickets lose, mostly to transaction costs.

### Cited findings
**Betfair in-play**
- Whelan (2026), more than 200,000 soccer matches, 2022-24, with maker and taker sides identified from one-second order-book data. Returns 15 minutes in match pre-play. "As matches progress, losses for Takers get larger, particularly for longshot bets," and makers on longshots also lose. "By 105 minutes [about 87 on the match clock], loss rates for Takers in the bottom decile of probability reach about 70% and loss rates for Makers taking longshot bets are almost as bad. Small but statistically significant profits for Takers emerge during the second half for bets with a reasonably high chance of success... it may be possible to earn money on Betfair just by accepting offers on strong favorites in the second half!" Betfair commission is typically 2%. Whelan also asks whether the effect will survive now that it is published. Source: [Whelan, Betfair paper](https://www.karlwhelan.com/Papers/Betfair.pdf)
- Angelini, De Angelis & Singleton (IJF 2022; Reading DP 2019-20): 1,004 Premier League matches (2009/10 to 2013/14), Betfair prices every 10 seconds. They find a **reverse** FLB (favorites overpriced) both pre-match and in-play. Mispricing grows after surprises: when a longshot scores the first goal late, "the market underestimat[es] their chances of going on to win". Markets overstate how decisive an early favorite goal is. Mispricing is strongest 20 seconds after the goal and still significant 5 minutes later. Backing longshots gave gross returns of about 40% (home) to 56% (away) in-sample and about 52% out-of-sample, before commission. Sources: [Angelini et al., Reading DP](https://www.reading.ac.uk/web/files/economics/emdp201920.pdf); [IJF version](https://www.sciencedirect.com/science/article/abs/pii/S0169207021000996)
- Choi & Hui (2014): in in-play soccer betting, participants underreact to anticipated events and overreact to very surprising ones; a secondary summary says the effects fade within minutes. (Abstract and snippets only.) Source: [Choi & Hui, ResearchGate](https://www.researchgate.net/publication/256013000_The_Role_of_Surprise_Understanding_Overreaction_and_Underreaction_to_Unanticipated_Events_using_In-Play_Soccer_Betting_Market)
- Croxson & Reade (2014): Betfair prices adjust quickly and fully to goals just before half-time (semi-strong efficient). As summarized in [Angelini et al.](https://www.reading.ac.uk/web/files/economics/emdp201920.pdf) and [Whelan](https://www.karlwhelan.com/Papers/Betfair.pdf)

**Kalshi sports near expiry (2026)**
- Final 10 minutes: Platt slopes 1.62-4.56 and a step-shaped calibration curve. In NHL games with 0-10 minutes left, "the empirical outcome rate sits at essentially zero across prices below 0.40", meaning cheap trailing-team contracts are heavily overpriced and leaders underpriced. 30-240 minutes out, calibration is about perfect. Source: [Moshrefi, arXiv 2607.14430](https://arxiv.org/html/2607.14430)

**InTrade**
- Page (2012): losing teams overpriced in the final 15 minutes across 1,100 sports markets. As reported in [Whelan](https://www.karlwhelan.com/Papers/Betfair.pdf) and [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)

**Options analogues (buying a 95c favorite is like selling a deep out-of-the-money digital option)**
- S&P 500 and FTSE 100 index futures options (Hodges, Tompkins & Ziemba; 1985-2002): an FLB appears in S&P 500 calls. In FTSE calls, only the deepest out-of-the-money options show a significant longshot bias. Put buyers overpaid in both markets ("cost of insurance"). (Abstract/snippet only.) Sources: [ResearchGate](https://www.researchgate.net/publication/280858937_The_Favorite-Longshot_Bias_in_sp_500_and_FTSE_100_Index_Futures_Options_The_Return_to_Bets_and_the_Cost_Of_Insurance); [ScienceDirect chapter](https://www.sciencedirect.com/science/chapter/edited-volume/abs/pii/B9780444507440500123)
- 0DTE (zero-days-to-expiry) SPX options (Beckmeyer, Branger & Gayda 2023): retail traders lost about $358,000 a day, **more than 60% of it transaction costs (spreads)** rather than option overpricing as such. Narrower spreads did not offset the risk of the positions retail favors. Sources: [Bloomberg](https://www.bloomberg.com/news/articles/2023-04-21/day-traders-lose-358-000-per-day-gambling-on-zero-day-options); [Neudata summary](https://neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders)
- One backtest of SPXW options with 0-5 days to expiry claims far out-of-the-money ultra-short options had good risk-adjusted returns, against the lottery-overpricing story (single study, UNVERIFIED). Source: [ResearchGate](https://www.researchgate.net/publication/370012499_Retail_Traders_Love_0DTE_Options_But_Should_They)

### Inferences
- Minute 8 of a 15-minute contract is structurally like "the second half": a decisive, fast-moving finish watched in real time. The 2026 evidence (Whelan, Moshrefi) supports the idea that favorites are underpriced at this stage and that the effect grows toward the end. That suggests testing **later entries (minutes 10-13)**, with the caveat that in the very last minutes the favorite's price rises, so the absolute cents of edge per contract shrink even if win rates keep beating prices.
- The 0DTE finding is a warning that matters for us: in very short-dated products, **spreads and fees, not mispricing, decide who wins**. Our edge of a few tenths of a cent is the same order as one tick of spread or slippage.
- On surprises the evidence conflicts: Choi & Hui find overreaction, while Angelini et al. find underreaction to a late longshot goal. Neither tells us cleanly whether a favorite created by a sudden spot jump in the last 1-2 minutes is over- or under-priced versus one created by steady drift. This should be tested on our own data (condition on the price path in minutes 6-8).

### Gaps
- The Betfair and Kalshi-sports late-game results do not give win rates or returns specifically for 90-99c favorites (Whelan reports deciles in figures, not text; Moshrefi gives no favorite-bucket numbers).
- No peer-reviewed study was found of near-expiry FLB in exchange-traded binary options (Nadex, CME event contracts) or in crypto options under an hour to expiry.

## 4. Does the bias depend on price within 90-100c, and are extreme favorites (98-99.9c) mispriced differently?

### Takeaway
The literature almost never splits the 90-99c band. Where it looks, favorites stay underpriced up to the top of the range, but the gap in probability points shrinks toward 99c. Kalshi's fee formula and per-order rounding then decide whether 98-99.9c is tradable at all. No study isolates 98-99.9c.

### Cited findings
- Polymarket: at 95c and above, the probability error (win rate minus price) ranges from +1.14 to +0.11pp and "is positive throughout the favorite range". Favorites at 90-99c excluding endpoint prices return +0.187% equal-weight and +1.729% pooled. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Polymarket full price curve: in percentage-return terms, gains peak near 60c and fall toward $1. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Kalshi (Becker): 95c contracts win 95.83% (+0.83pp). Every level above 80c outperforms its implied odds. No 90c or 99c figures are given in the text. Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)
- BDW reports only a single 90-99c band. Their illustration ("A 95c contract that wins 98% of the time has a pre-fee average return of 3.1%") is arithmetic, not data. Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Kalshi taker fee during BDW's sample: $0.07·P·(1−P) per contract, rounded up to the next cent per order. On 100 contracts at 50c, rounding lifts the effective fee from 1.75% to 1.77% of price. Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Kalshi prices traded only in whole cents (1-99c) during BDW's sample. Our bot's 99.9c ceiling implies the 15-minute markets now quote finer ticks, which no study covers. Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)

### Inferences
- **Break-even win rates for a taker, using the 0.07·P·(1−P) formula before rounding** (own arithmetic, not from a source; check against Kalshi's current fee schedule for 15-minute crypto, metals and energy series):

| Ask | Fee/contract | Break-even win rate | Required excess over price |
|---|---|---|---|
| 90c | 0.63c | 90.63% | +0.63pp |
| 92c | 0.52c | 92.52% | +0.52pp |
| 94c | 0.39c | 94.39% | +0.39pp |
| 95c | 0.33c | 95.33% | +0.33pp |
| 96c | 0.27c | 96.27% | +0.27pp |
| 97c | 0.20c | 97.20% | +0.20pp |
| 98c | 0.14c | 98.14% | +0.14pp |
| 99c | 0.07c | 99.07% | +0.07pp |
| 99.5c | 0.035c | 99.53% | +0.03pp |
| 99.9c | 0.007c | 99.907% | +0.007pp |

- Per-order rounding up to a whole cent dominates at the top. One contract at 99c pays a 1c fee, which is the entire possible profit. Ten contracts at 99c pay 1c in total (0.1c each, break-even 99.10%). Order size must be large enough to dilute the round-up, or the 98-99.9c band is untradable regardless of the bias.
- The fee falls toward the extremes, but so does the most you can win (100 − ask). The Polymarket error band (+1.14 to +0.11pp at 95c+) suggests the probability excess shrinks toward 99c. Whether the excess shrinks faster than the fee does is an empirical question for our data. The literature cannot answer it.
- Tail risk grows at the top of the band: at 99c one loss wipes out about 99 wins. A settlement or data error (index glitch, last-second spike) can matter more than the bias. This is outside the FLB literature but matters for sizing.

### Gaps
- No academic or practitioner source gives win rates or returns for 96-97c, 98c, 99c or sub-cent prices on Kalshi or Polymarket.
- Kalshi's current fee schedule (taker and maker) for the 15-minute series was not verified in this research.

## 5. Profitability of betting favorites after transaction costs, and bias decay as markets mature and sophisticated traders arrive

### Takeaway
After fees, the favorite side of the FLB is a thin edge of tenths of a percent to about 1% before fees, captured mostly by makers. Takers often net zero or less. Evidence on decay is suggestive rather than conclusive. Kalshi's 2025 coefficient is smaller. Kalshi's maker/taker returns flipped sign in 2024 as volume exploded. Taker flow into 91-99c collapsed. Polymarket's persistent favorite buyers already earn less. Academics expect publicized anomalies to fade. A Kalshi maker-fee "treatment" showed no lasting effect, and the bias has survived 100x volume growth.

### Cited findings
- Kalshi takers buying high-priced contracts: "loss rates for Takers decline but they still lose money on average." Makers buying at 50c or more: +2.6% after commission (SD 33%). Source: [BDW](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Polymarket favorites: +0.28% to +0.83% depending on weighting; accepted-offer (taker-like) favorites −0.46% equal-weight. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Becker: the Kalshi maker edge (+1.12%) comes from biased flow, and he cannot separate it from spread capture because historical spreads are unavailable. Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)
- Betfair late favorites: "small but statistically significant profits" for takers after 2% commission. Whelan notes the caveat that maker profits depend on getting matched. Source: [Whelan](https://www.karlwhelan.com/Papers/Betfair.pdf)
- 0DTE options: more than 60% of retail losses were spreads. Source: [Bloomberg](https://www.bloomberg.com/news/articles/2023-04-21/day-traders-lose-358-000-per-day-gambling-on-zero-day-options)
- Polymarket 15-minute crypto: taker fees were introduced specifically to neutralize latency arbitrage, and developer reports say taker-fee strategies on thin margins were wiped out while maker-side bots were favored (anecdotal, UNVERIFIED). Sources: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates); [Unchained](https://unchainedcrypto.com/polymarket-introduces-taker-fees-in-15-minute-markets/)
- Decay signals:
  - BDW ψ fell from 0.048 (2024) to 0.021 (Jan-Apr 2025). Source: [BDW Table 9](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
  - Kalshi maker/taker returns swung 5.3pp from the 2024 election onward, and the 91-99c taker share went from 40-50% to under 20%. Source: [Becker](https://www.jbecker.dev/research/prediction-market-microstructure)
  - The maker-fee DiD is null with a possible transitory dip, and composition explains 41% of the slope change (UNVERIFIED). Source: [Vladosyna replication](https://github.com/Vladosyna/kalshi-makers-takers-persistence)
  - Polymarket favorite-decile wallets earn +0.25% versus +0.88% for others. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Persistence signals:
  - BDW reject unbiasedness in every year 2021-2025, every volume quintile and every category. They ask whether the pattern will "disappear once [it has] been publicized," citing evidence that published anomalies decay (Shanaev & Ghimire 2021; Zaremba et al. 2020). Source: [BDW §6](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
  - Whelan raises the same question for the Betfair late-game effect. Source: [Whelan](https://www.karlwhelan.com/Papers/Betfair.pdf)
  - Polymarket: the FLB holds across experience levels and is stronger, not weaker, in the busiest markets. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)

### Inferences
- Our sign change (negative Jul 18 to Aug 23 2026, positive after) looks like the early-life instability Becker found on Kalshi as a whole, where takers won in early, thin periods and the sign flipped as volume and retail flow arrived. It also fits the composition effects in the replication. Both point to **watching who is on the other side** (retail longshot flow versus fast bots) rather than calendar time. It does not prove the edge is getting stronger: about two months of positive results is a short window given the variance of a 1-1.5pp win-rate edge.
- Practical levers suggested by the literature, ranked by expected impact:
  1. Capture the maker share by posting rather than hitting the ask, after checking Kalshi's maker fee and measuring adverse selection.
  2. Concentrate where late-event and tail effects are strongest: later minutes, and the deepest tail at which the fee table and rounding still leave positive expected value.
  3. Prefer series and conditions with more retail longshot flow. Crypto has the largest Kalshi FLB coefficient and a large maker-taker gap; "dry" finance-type series show little.
  4. Build in a monitor that pauses the strategy when the realized win-rate excess over price falls below the fee break-even for a rolling window, since decay from bot competition is the expected direction.
- Variance matters as much as the mean. BDW's Samuelson argument (rational investors may decline many small positive-expected-value bets with fat left tails) applies directly to a strategy that, buying at 96c, loses about 96c roughly once every 25 trades.

### Gaps
- No study measures post-cost returns from systematically buying late favorites in short-duration crypto binaries on either platform.
- No study directly measures how quickly the FLB decays after bots arrive in a specific market type. Evidence on decay is indirect (yearly coefficients, volume shares, wallet-level returns).
- Polymarket's quarterly FLB trend (Figure 6 of arXiv 2609.12878) values were not recoverable from the text.
