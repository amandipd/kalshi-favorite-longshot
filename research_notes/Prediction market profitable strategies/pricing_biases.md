# Pricing biases on prediction markets: favourite-longshot bias, endgame buying, bet-No, calibration

Research date: 25 Oct 2026. Every figure carries its date. Older findings are marked "OLDER".

Plain words used throughout:
- **Favourite / longshot**: the likely side / the unlikely side.
- **Favourite-longshot bias (FLB)**: cheap unlikely bets are overpriced, heavy favourites underpriced.
- **Calibration**: whether a 70c price really wins 70% of the time.
- **Calibration slope**: one fitted number for calibration. 1 means well calibrated. Above 1 means prices are squeezed toward 50c, so favourites are underpriced and longshots overpriced (the FLB direction). Below 1 means prices are too extreme (the reverse).
- **Maker**: a trader who posts a resting limit order and waits. **Taker**: a trader who trades at once against a posted order.
- **Taker fee**: the platform's charge for trading at once; on Kalshi it is biggest near 50c.
- **Spread**: the gap between the buy and sell price. It is what it costs to get in.
- **¢/$1**: cents of profit for every dollar bet. **Edge**: profit per contract, in cents.
- **95% CI**: the range the true number is probably in.
- **Out-of-sample**: tested on data the rule never saw while being built.
- **Brier score**: the average squared forecast error. 0 is perfect. Lower is better.
- **Equal-weighted vs pooled**: equal-weighted counts each market once. Pooled (dollar-weighted) lets big-money markets count more.

## Q1. What do calibration studies of Kalshi, Polymarket, PredictIt and Betfair show, by price level and by category?

### Takeaway
On Kalshi, the favourite-longshot bias is real and large on the longshot side. Contracts under 10c lose over 60% of the money put in, and favourites earn small positive returns before fees (Bürgi, Deng and Whelan, 2025-26). On Polymarket the bias is smaller and less stable. It shows clearly in Crypto and Politics, is absent in Sports, and some 2026 data even show the reverse (prices too extreme), led by weather markets.

### Cited findings

**Kalshi: Bürgi, Deng and Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market"**
- Versions: UCD working paper WP2025/19 (2025); CEPR Discussion Paper DP20631 (Sept 2025, revised Jan 2026); CESifo WP 12122; GWU working paper 2026-001. The data cover over 300,000 Kalshi contracts. Sources: [CEPR DP20631](https://cepr.org/publications/dp20631); [SSRN 5502658](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5502658); [GWU PDF](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Buyers of contracts under 10c lose over 60% of their money. Example from the paper: a 5c contract that wins only 2% of the time loses 60% of the money put in. Source: [UCD WP2025/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) (search snippet; full text blocked, 403)
- Contracts priced above 50c earn a small positive return, and this is beyond what luck would explain (statistically significant). Example: the 95c side of that same 5c contract wins 98% of the time, a small profit. Source: [UCD WP2025/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) (search snippet)
- Before fees, the average return on Kalshi contracts is −20%. Source: [UCD WP2025/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) (search snippet)
- Takers lose almost 32% on average; makers lose about 10% on average. Both groups show the same favourite-longshot pattern. Source: [VoxEU column, Whelan](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market) (seen only through a search summary; the page returned 403, so not checked directly)
- The bias holds across a wide range of Kalshi categories. There is "some evidence" it is shrinking over time. Source: [UCD WP2025/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) (search snippet)
- The authors' model: makers are fairly well-informed but slightly over-optimistic; a small tendency to overstate small probabilities is enough to produce the pattern. The model predicts taker loss rates rise as the contract price falls. Sources: [CEPR DP20631](https://cepr.org/publications/dp20631); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5502658)
- Kalshi itself republished this work as "the largest study on prediction markets' reliability" on 20 Aug 2026. Note: Kalshi's own research arm (set up 22 Dec 2025) promoted it. Source: [Crypto Briefing, 20 Aug 2026](https://cryptobriefing.com/kalshi-prediction-markets-reliability-study/)

**Kalshi and Polymarket by category: Le, "Decomposing Crowd Wisdom" (arXiv 2602.19520v2, 4 Aug 2026)**
- Data: Kalshi 1 Jul 2021 to 31 Dec 2025 (64.7M trades, 210,608 contracts). Polymarket 6 Mar 2023 to 31 Dec 2025 (288.7M trades, about 218,000 resolved contracts). Fitted on prices 5c-95c only. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Kalshi calibration slope by category (range across time-to-close buckets; above 1 = FLB direction). Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)

| Category (Kalshi) | Slope range | What it means in plain words |
|---|---|---|
| Politics | 0.93-1.83 | Favourites clearly underpriced, most of all far from close |
| Sports | 0.90-1.10 within 48h; 1.74 beyond 1 month | About right near the game; favourites underpriced far out |
| Crypto | 0.99-1.36 | About right at short horizons |
| Finance (indices, rates, economic data) | 0.82-1.42 | Mixed |
| Weather | 0.69-0.97 within 48h; 1.37 beyond 1 month | Near the end, prices are TOO extreme (favourites overpriced) |
| Entertainment | 0.81-1.11 | About right |

- Example: a 70c political contract one week before close wins about 83% of the time (slope about 1.83). Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Expected calibration error (the average gap between price and real win rate): Politics 0.117 (about 12 points); every other category 0.007-0.022 (about 1-2 points). Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Polymarket slopes: Politics 1.45, Sports 1.06, Crypto 1.06. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Big Kalshi political trades (over 100 contracts) are better calibrated in the FLB direction than single-contract trades (slope 1.74 vs 1.19). But once bets on the same event are counted as one (clustered on event), the 95% CI (the range the true number is probably in) is wide, 0.12 to 1.80. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- The paper makes no claim about profit after fees. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)

**Polymarket: Cardozo and Rivero-Wildemauwe, "The Favorite-Longshot Bias in Prediction Markets: Evidence from Polymarket" (arXiv 2609.12878, 11 Sep 2026)**
- Data: 588 million trades by 2.48 million accounts, 11 Nov 2022 to 29 Mar 2026. Returns are before fees and before maker rewards. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)

| Bucket | Equal-weighted per market | Pooled (dollar-weighted) | Weighted per parent event |
|---|---|---|---|
| Longshots (<10c) | −6.30 ¢/$1 (CI −8.4 to −4.2) | −19.35 ¢/$1 (CI −47.0 to +8.3) | +4.09 ¢/$1 |
| Favourites (≥90c) | +0.28 ¢/$1 (CI 0.24 to 0.31) | +0.83 ¢/$1 (CI 0.60 to 1.07) | +0.39 ¢/$1 |

- By category (equal-weighted / pooled, ¢/$1 = cents of profit for every dollar bet, before fees): Crypto longshots −14.84 / −12.63, favourites +0.64 / +0.54. Politics longshots −16.34 / −46.15, favourites +1.04 / +1.42. Sports longshots +2.43 / +18.11, favourites −0.23 / +0.14. So the bias is two-sided in Crypto and Politics and absent in Sports. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Losses are largest around 20-25c. Gains peak around 60c. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Accounts that most often buy favourites earn LESS than other accounts. Heavy longshot buyers earn about the same as others. Source: [arXiv abstract 2609.12878](https://arxiv.org/abs/2609.12878)
- The pattern is stronger in heavily traded events. The authors link this to Ottaviani and Sørensen (2010): more participation can make favourites win more often than their odds suggest. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)

**Polymarket: Qin and Yang, "Polymarket-v1 Database" (arXiv 2606.04217, June 2026)**
- Data: 21 Nov 2022 to 28 Apr 2026; 1.20 billion trade records; 1,295,860 markets. Up/Down crypto markets are left out of the main tables. Source: [arXiv 2606.04217](https://arxiv.org/html/2606.04217v1)
- Average profit per contract (payout minus price, before fees), by price: 0-10c −0.23c; 10-20c −0.19c; 20-30c −0.32c; 30-40c −0.05c; 40-50c +0.26c; 50-60c +0.15c; 60-70c +0.47c; 70-80c +0.76c; 80-90c +0.98c; 90-100c +0.56c. Source: [arXiv 2606.04217](https://arxiv.org/html/2606.04217v1)
- The authors call this a "favorite-longshot reversal". But the signs (cheap loses, expensive wins) match the classic bias. The label looks inconsistent with their own numbers. Source: [arXiv 2606.04217](https://arxiv.org/html/2606.04217v1)

**Independent GitHub studies (not peer-reviewed; reproducible code)**
- hrishi-tailor: 46,168 resolved markets (Kalshi Jul 2021 to Aug 2026; Polymarket Dec 2022 to Oct 2026). Kalshi slope rises as close nears: 1.02 at 30 days, 1.11 at 1 day, 1.22 at 1 hour. Kalshi 95c+ contracts one day out: about 46 losses expected out of 3,360, only 22 happened (favourites lose half as often as priced). Kalshi ≤5c contracts: 82 wins expected out of 6,516, only 60 happened. On Polymarket the same longshot range won MORE than priced (187 vs 116 expected). Kalshi politics is the most biased category (slope 1.28). Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- hrishi-tailor: the Kalshi bias lives in thin markets. Least-traded third: slope 1.18. Most-traded third: 1.02 (about right). Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- hrishi-tailor: Polymarket 1-day slope was 1.02 before 2026 and 0.92 in 2026 (too extreme). Without weather markets, 2026 is 0.99. Weather slope is 0.82, and weather rose from 5% to 29% of listings in 2026. Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- carol-747: 2,975 Polymarket markets with at least $50K traded, closed Jan 2025 to Oct 2026. Calibration error 1.1 points at 7 days out. Slope 1.12 (CI 1.02-1.26) at 7 days, 1.26 at 1 day. 9 of 10 price bins are consistent with the price. The author reads this as "no classic favorite-longshot bias", though a slope above 1 points the FLB way. Source: [GitHub carol-747](https://github.com/carol-747/polymarket-calibration)
- shirleyshen0106: 54,865 Polymarket markets that resolved 6 Sep to 19 Oct 2026 (six weeks only). Mid-prices 7 days out. 5-15% band priced 9.5%, won 13.2%. 15-35% priced 25.5%, won 30.1%. 65-85% priced 73.4%, won 69.5%. 85-95% and 95-100% match their prices. So this sample shows the REVERSE of the FLB (prices too extreme). The author withdrew two earlier headlines over data bugs. Source: [GitHub shirleyshen0106](https://github.com/shirleyshen0106/polymarket-calibration)
- calibration-atlas: 11,881 Polymarket markets. Political prices leaned slightly too extreme (slope 0.89, CI 0.81-0.98). Source: [GitHub Guinerve](https://github.com/Guinerve/calibration-atlas) (search snippet only). This conflicts with Le's Polymarket politics slope of 1.45. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2).

**Polymarket's own accuracy page (self-published, undated)**
- 78.2% of resolved markets resolved No; 21.8% Yes. The leading outcome was right 98.7% of the time 4 hours out, 96.6% one day out, 94.2% one week out, 90.3% one month out. Brier score (average squared forecast error, lower is better) 0.0593. No per-price numbers in text. Source: [Polymarket accuracy](https://polymarket.com/accuracy)

**Kalshi sports: Moshrefi, "Prices, Probabilities, and Parlays" (arXiv 2607.14430, 15 Jul 2026)**
- About 23 million Kalshi NBA, MLB and NHL moneyline trades, early Mar to mid-May 2026. Calibration is close to perfect with 30-240 minutes left. In the last 10 minutes it turns step-like. In the NHL's last 10 minutes, contracts priced about 10-40c almost never win. Source: [arXiv 2607.14430](https://arxiv.org/html/2607.14430v1)
- Parlays (combo bets) are overpriced. Price divided by the product of the leg prices is about 1.0 for 2-4 legs, 1.22 at 10 legs, 1.31 at 11 legs. A parlay priced 30c won about 24% of the time; one at 40c won about 30%. Source: [arXiv 2607.14430](https://arxiv.org/html/2607.14430v1)

**PredictIt**
- Zitzewitz, NBER WP 35845 (Oct 2026), data 2016-22 (OLDER data). The $850-per-contract cap limited arbitrage. PredictIt overpriced longshots more than other studied prediction markets. Bid prices across a market's contracts often summed to more than 110c, an arbitrage profit even after fees. Source: [NBER w35845](https://www.nber.org/papers/w35845)
- PredictIt's fee: 10% of profit on each winning closed position, nothing on losers, plus 5% on withdrawals. This makes some multi-outcome "arbitrage" lose money and lets mispricing persist (OLDER, 2016). Source: [Rajiv Sethi, 2016](https://rajivsethi.substack.com/p/fee-structure-distortions-in-prediction-16-04-10)
- Whelan's model: fees charged on winnings push low-probability prices below the true odds, which produces a favourite-longshot pattern after fees. Source: [CEPR DP17972](https://repec.cepr.org/repec/cpr/ceprdp/DP17972.pdf) (search snippet)

**Betfair and horse racing (OLDER literature)**
- Smith, Paton and Vaughan Williams (2006, Economica 73(292): 673-689), UK horse racing: betting exchanges show significantly lower biases than traditional bookmakers. An information-based model explains the bias better than risk-taste models. Sources: [IDEAS/RePEc](https://ideas.repec.org/a/bla/econom/v73y2006i292p673-689.html); [NTU repository](https://irep.ntu.ac.uk/id/eprint/10053/)
- Snowberg and Wolfers (2010, Journal of Political Economy 118(4): 723-746), US horse racing: longshots are overbet and favourites underbet. The cause is misjudged probabilities (as prospect theory predicts), not love of risk. Sources: [NBER w15923](https://www.nber.org/papers/w15923); [IZA DP 4884](https://iza.org/publications/dp/4884/imprint)
- Whelan (Economica, fixed-odds betting): bookmaker risk aversion plus disagreement among gamblers can produce the bias. Source: [Whelan Economica PDF](https://www.karlwhelan.com/Papers/EconomicaFinal.pdf) (search snippet)
- Most studies agree sports betting data show a strong favourite-longshot bias; its causes are still debated. Source: [arXiv 2402.02623](https://arxiv.org/pdf/2402.02623) (search snippet)

### Inferences
- Kalshi and Polymarket differ. Kalshi shows a clear, two-sided FLB (Bürgi et al.; Le; hrishi-tailor). Polymarket's bias is small, depends on how you weight markets, and may be flipping in 2026.
- On Polymarket, the longshot loss is −6.3 ¢/$1 per market but +4.1 ¢/$1 per parent event. So the loss comes from a few big multi-outcome events with many cheap options. A "fade the longshots" rule earns little unless it trades those big events.
- Two separate sources say weather prices are too extreme near the end: Kalshi weather within 48 hours (Le, slope 0.69-0.97) and Polymarket weather (hrishi-tailor, slope 0.82). In weather, cheap outcomes may be underpriced and favourites overpriced. That is the opposite of the general FLB.
- Kalshi politics is the most biased category in every source that splits it (Le; hrishi-tailor). Sports is closest to fair on both platforms.
- The bias is biggest in thin markets (hrishi-tailor), but Cardozo et al. find it stronger in heavily traded Polymarket events. These two findings conflict. They may measure different things: thin Kalshi markets vs big multi-outcome Polymarket events.

### Gaps
- The full Bürgi-Deng-Whelan paper could not be opened (PDF unreadable, mirrors blocked). So there is no bucket-by-bucket return table, no data dates, and no per-category or per-year numbers from it. The "takers −32%, makers −10%" figure is from a search summary of the VoxEU column, not checked directly.
- The Akey et al. paper (Polymarket winners and losers) and Reichenbach and Walther (SSRN 5910522, Polymarket accuracy and bias): full texts not reached.
- No Betfair returns-by-odds numbers were found. The Snowberg-Wolfers return figures by odds band were not retrieved.
- No calibration study for PredictIt after its $850 cap era was found.

## Q2. Endgame or "high-probability" buying: what do 90c-99c buys really return, and what are the tail-loss stories?

### Takeaway
Before fees, buying favourites at 90c+ has earned a small, real profit: about +0.3 to +0.8 cents for every dollar bet on Polymarket (2022-2026), more in Politics and nothing in Sports. That is smaller than one tick of spread at 95c. So a taker who crosses the spread and pays the fee nets about zero or a loss. The edge is mostly left for makers who wait to be filled. Rare resolution disputes and rule carve-outs are the tail risk.

### Cited findings

**Measured returns at 90c+**
- Polymarket, Nov 2022 to Mar 2026, before fees: favourites (≥90c) earned +0.28 ¢/$1 equal-weighted (CI 0.24-0.31), +0.83 ¢/$1 pooled (CI 0.60-1.07), +0.39 ¢/$1 per parent event. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- By category, before fees: Politics favourites +1.04 to +1.42 ¢/$1; Crypto +0.54 to +0.64; Sports −0.23 to +0.14. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Polymarket, Nov 2022 to Apr 2026: the 90-100c group earned +0.56c of profit per contract before fees; 80-90c earned +0.98c. Source: [arXiv 2606.04217](https://arxiv.org/html/2606.04217v1)
- Kalshi, Jul 2021 to Aug 2026: 95c+ contracts one day out lost 22 times out of 3,360, against about 46 expected from the price. But after spread and taker fees, buying favourites or fading longshots LOSES 0-2% per dollar. No price bucket is clearly profitable. A correction learned on older markets did not beat the market on newer ones (out-of-sample: tested on data the rule never saw). Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- Kalshi: contracts above 50c earn a small positive return before fees (Bürgi et al., 2025). Source: [UCD WP2025/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) (search snippet)
- One-day backtest, Polymarket BTC 5-minute Up/Down, 8 Sep 2026: buying the favourite in the last 60 seconds when priced 55-95c. 108 trades, 82.4% won. Edge before fees +0.7c per contract. Fees $52.90 and slippage (filling worse than the price you aimed at) $4.22 turned it into a −$15.62 net loss. The author helps maintain the dataset and backtester (open source; no paid product named). Source: [DEV Community, Oct 2026](https://dev.to/levl/two-polymarket-strategies-that-look-fine-until-you-add-fees-and-a-queue-5g4p)
- Same test, maker version (resting orders at the best bid): −$26,133 net. Prices moved against fills by about 4-4.6c per share (adverse selection: getting picked off by someone who knows more). Source: [DEV Community, Oct 2026](https://dev.to/levl/two-polymarket-strategies-that-look-fine-until-you-add-fees-and-a-queue-5g4p)
- Vendor claim: a study of 219,000 "whale" trades says +7-9% ROI on big tickets entered at 85c+. This is a vendor blog; method not checked. FLAG: vendor. Source: [Polyloly blog](https://polyloly.com/blog/where-polymarket-edge-lives-cohort-roi-analysis)
- Simple math: buying at 95c returns about 5.3% gross if it wins. One loss wipes out 19 wins at that price. FLAG: strategy-guide site. Source: [StartPolymarket "Bonding"](https://startpolymarket.com/strategies/bonding/)

**Who profits on Polymarket**
- Akey, Grégoire, Harvie and Martineau (CEPR DP21615, June 2026): 588 million trades, $67 billion volume. The top 1% of profitable users take 76.5% of profits. Winners mostly post limit orders (makers); losers mostly use market orders (takers). Source: [EconPapers DP21615](https://econpapers.repec.org/RePEc:cpr:ceprdp:21615)
- An on-chain analysis found 84.1% of 2.5 million Polymarket wallets in the red; Bloomberg (29 Apr 2026) reported over 100,000 accounts lost at least $1,000 since the start of 2025. Sources: [The Defiant, Apr 2026](https://thedefiant.io/news/research-and-opinion/polymarket-profitability-report-april-2026); [Coin360](https://coin360.com/news/polymarket-traders-losses-profit-concentration-2026-predictions); [Bloomberg, 29 Apr 2026](https://bloomberg.com/news/newsletters/2026-04-29/most-traders-lose-on-polymarket-and-winners-look-like-bots) (search snippets only; it is unclear which of these first reported the 84.1% figure)

**Tail-loss and dispute stories**
- Polymarket, "Ukraine agrees to Trump mineral deal before April?", 24-25 Mar 2025 (OLDER). A $7 million market jumped from about 9% Yes to 100% and resolved Yes though no deal was signed. Polymarket called it an "unprecedented" governance attack by a large UMA token holder. No refunds, because it "wasn't a market failure." Source: [The Block, 26 Mar 2025](https://www.theblock.co/post/348171/polymarket-says-governance-attack-by-uma-whale-to-hijack-a-bets-resolution-is-unprecedented)
- The same case: one holder cast about 5 million UMA tokens through three accounts, about 25% of the vote. Source: [Forklog](https://forklog.com/en/whale-manipulates-polymarket-prediction-markets/amp) (search snippet; crypto press)
- Polymarket "Zelenskyy suit" market, July 2025 (OLDER). The outcome was disputed again and again even though news outlets called his outfit a suit. Users called it "the biggest scam in Polymarket history"; UMA said there was "no evidence" of foul play. Source: [The Defiant](https://thedefiant.io/news/nfts-and-web3/polymarket-controversy-heats-up-after-the-zelenskyy-suit-market-resolves) (headline and subtitle only; body did not load)
- Polymarket UFO-files market, Dec 2025: about $16 million. It resolved Yes after late buying at 99-99.9c, with several disputes before it was final. Critics said whales forced a Yes without evidence. Source: [CryptoSlate](https://cryptoslate.com/polymarket-faces-major-credibility-crisis-after-whales-forced-a-yes-ufo-vote-without-evidence/) (search snippet)
- Polymarket "Strategy sells Bitcoin by May 31" dispute: two wallets reportedly netted over $299,000 and over $370,000 from voting on disputes. Source: [Cointelegraph](https://cointelegraph.com/news/polymarket-dispute-strategys-bitcoin-sale-resolves-no) (search snippet)
- Kalshi, Khamenei "out as Supreme Leader" market, early Mar 2026. After reports he was killed, Kalshi applied its death carve-out. It settled at the last traded price before the death, not at Yes. Kalshi refunded fees and net losses (a reported $2.2 million cost). A class action followed in the Central District of California, and Kalshi filed a rule change with the CFTC. Sources: [Decrypt](https://decrypt.co/360293/kalshi-sued-refusing-pay-out-prediction-market-iran-leader-death) (search snippet); [DeFi Rate](https://defirate.com/?p=6405)
- 2024 (OLDER): Biden's withdrawal crashed one trader's nomination and election positions by 99%, a $2 million loss. Not a 95c+ buy, but a "safe-looking" bet that failed. Source: [The Block](https://www.theblock.co/post/306539/polymarket-user-anonbidenbull-loses-2-million-following-bidens-withdrawal-from-race)

### Inferences
- A realistic return for a TAKER buying 90-99c favourites is about −2 to +0.5 cents for every dollar bet. Before fees the edge is about +0.3 to +1.4 ¢/$1 (Polymarket by category). The fee at 95c is about 0.2-0.35 ¢/$1 (see Q5). Crossing half of a 1c spread at 95c costs about 0.5 ¢/$1. The project's own arithmetic, from the cited numbers.
- For a MAKER (no fee on Polymarket, low or no fee on most Kalshi series, no spread paid), the same edge is roughly +0.3 to +1.4 ¢/$1 before adverse selection. Adverse selection can wipe it out, as the 5-minute BTC maker test showed.
- The best category for endgame buying is Politics, and the worst is Sports, on both data sets that split it.
- Measured past returns already include past disputes. They do not price a new kind of rule (like Kalshi's death carve-out) or a governance attack in a thin market. Endgame buyers hold many small, correlated tail risks.
- Two disputed cases (Ukraine minerals, UFO files) went to "Yes" against the "nothing happened" side. So the tail risk is not only that a favourite loses on the facts. Resolution itself can be contested.

### Gaps
- No source gives a clean, after-fee return series for "buy every 95-99c contract in its last hour" on Kalshi or Polymarket.
- Finer buckets (95-99c alone) in Cardozo et al. are in an appendix that could not be read.
- No count of how often UMA disputes flipped a 95c+ market was found.
- The Kalshi Khamenei lawsuit's current status is unknown.

## Q3. Short-term crypto markets (Kalshi 15-minute and hourly, Polymarket 5- and 15-minute Up/Down): any mispricing by price level?

### Takeaway
No peer-reviewed study tests these markets by price level. The broad crypto category looks close to well calibrated at short horizons on both platforms. Evidence on late favourites comes from small vendor or affiliate samples. Polymarket added a taker fee to 15-minute crypto in January 2026, aimed at latency arbitrage near 50c (bots trading on a few seconds' head start over the price feed).

### Cited findings
- Kalshi crypto calibration slope 0.99-1.36 (1 = well calibrated), near calibrated at short horizons; Polymarket crypto slope 1.06 (data to Dec 2025). Kalshi crypto contracts resolved Yes 40.7% of the time. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Polymarket crypto category (all crypto, not just Up/Down), Nov 2022 to Mar 2026, before fees: longshots −14.8 / −12.6 ¢/$1, favourites +0.64 / +0.54 ¢/$1 (equal-weighted / pooled). Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Polymarket crypto Up/Down markets alone looked slightly overpriced in the 35-65% band in Sep-Oct 2026. The author blames one week of correlated Bitcoin moves. Removing crypto did not change the overall shape. Source: [GitHub shirleyshen0106](https://github.com/shirleyshen0106/polymarket-calibration)
- The Polymarket-v1 database left Up/Down markets out of its return tables. Its "Price Action" group (301,304 markets) has a small typical spread (Gibbs estimate 0.0093, about 0.9c). Source: [arXiv 2606.04217](https://arxiv.org/html/2606.04217v1)
- Kalshi BTC 15-minute, 2,400 windows, 4 Sep to 23 Oct 2026. Windows that finished $50+ from the start price flipped in the last two minutes only 13 of 1,318 times (about 1%). Windows finishing within $50 flipped 230 of 1,082 times (about 21%). In the flips, the losing side was priced 70c or more with two minutes left in 55 of 83 cases (about 66%). Source: [OddsShopper, 23 Oct 2026](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged). FLAG: affiliate links and a Polymarket referral code.
- Same source, 21-23 Oct 2026 sample: 64 windows had Yes at 91c+ with two minutes left, and none lost. 66 had No at 91c+, and 2 lost. Source: [OddsShopper](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged)
- Vendor backtest, April 2026: only 102 of 4,904 Kalshi BTC 15-minute strategies made money. All 432 mean-reversion versions lost. Fading Yes below 35c and No above 65c: best version −$1,377. FLAG: vendor (Turbine sells trading research and tools). Sources: [Turbine](https://www.turbinefi.com/blog/5000-strategy-backtest-kalshi-btc-15m); [Turbine research](https://www.turbinefi.com/research/kalshi-btc-15-minute-markets-mean-revert-more-reliably-under-specif-8e46853f0bad)
- Polymarket BTC 5-minute, one day (8 Sep 2026): buying the 55-95c favourite in the last minute won 82.4% but lost money after fees (see Q2). Source: [DEV Community](https://dev.to/levl/two-polymarket-strategies-that-look-fine-until-you-add-fees-and-a-queue-5g4p)
- Polymarket fees on 15-minute crypto (BTC, ETH, SOL, XRP) started 5 Jan 2026. Peak about 3.15% of trade value at 50c. They target bots that exploited short delays between Polymarket prices and exchange spot prices. A tweet claimed one bot turned $313 into $414k in a month; the article did not verify it. Source: [Finance Magnates, 7 Jan 2026](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/)
- Kalshi and Polymarket together set a weekly crypto-contract volume record of $2.7 billion. Source: [TokenPost](https://www.tokenpost.com/news/investing/40079) (search snippet; date not seen)

### Inferences
- Within 15-minute crypto, whether a favourite loses depends mostly on how close the price sits to the line, not on the quoted price alone. A 91c favourite in a close window is riskier than a 91c favourite in a wide one.
- The near-50c latency trade was the clearest documented mispricing. The 2026 fee is largest exactly there, so that edge is likely gone for takers.
- Fees are smallest at the extremes, so late-favourite strategies are hurt least by the fee. Their main costs are spread and getting filled at all.

### Gaps
- No study measures calibration by price band for Kalshi 15-minute or hourly crypto markets specifically.
- No data on Kalshi hourly crypto (range or above/below) mispricing were found.
- OddsShopper and Turbine samples are small, short, and commercially motivated.

## Q4. "Bet No on everything" or "fade the hype": does it work?

### Takeaway
Most markets do resolve No: about 72-78%. But prices already reflect that, so blind No-betting is not a free edge. What profit exists comes from the favourite-longshot bias: buying No on a cheap Yes is the same as buying the favourite. Most of that edge sits in big multi-outcome events.

### Cited findings
- Polymarket's page: 78.2% of resolved markets resolved No (undated, self-published). Source: [Polymarket accuracy](https://polymarket.com/accuracy)
- Substack "Nothing ever happens" (12 Feb 2026): 161,638 Polymarket and Kalshi contracts from 2021-2025; about 72% resolved No. On Kalshi (1,773,486 contracts): range contracts 92.6% No; up/down "directional" contracts 48.2% No; binary contracts 73.7% No. No bettors do not beat Yes bettors; the "bet No on everything" strategy "doesn't work." Code on GitHub; no product sold. Source: [Delta Confidence Substack](https://deltaconfidence.substack.com/p/nothing-ever-happens)
- About three in four questions resolved No (OLDER, about 2024). Source: [Bankless](https://www.bankless.com/read/polymarket-beats-the-odds) (search snippet)
- Kalshi Yes rates by category (Jul 2021 to Dec 2025): Sports 41.3%, Crypto 40.7%, Politics 40.2%, Entertainment 38.0%, Finance 37.7%, Weather 24.0%. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Polymarket longshots under 10c lost 6.3 ¢/$1 per market but gained 4.1 ¢/$1 per parent event (before fees). Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Contracts priced 10-20c resolve Yes about 10-20% of the time, so the low price already reflects the low odds. Source: [Akey et al., OSC-hosted PDF](https://www.osc.ca/sites/default/files/2026-10/research-grant-competition-2026-who-wins-and-who-loses-in-prediction-markets.pdf) (search snippet; PDF blocked)
- Over 1.1 million of 1.6 million Polymarket accounts were unprofitable (WSJ, as reported). That covers all trading, not a No-only rule. Source: [Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/two-thirds-polymarket-profits-just-100500195.html) (search snippet)

### Inferences
- The high No rate comes from market design. Range and multi-outcome markets list many options, and only one can be Yes. It is not a sign that Yes is overpriced.
- "Bet No on cheap Yes" equals "buy favourites at 90c+." So its return is the Q2 number: about +0.3 to +0.8 ¢/$1 before fees on Polymarket, smaller after fees.
- The per-event result (+4.1 ¢/$1 for longshots) means fading longshots across all events evenly may earn nothing. The edge depends on trading the large, many-option events where cheap options pile up.
- In weather markets the bias may run the other way (Q1). There, fading cheap outcomes could lose.

### Gaps
- No source tests a blanket "buy No at the ask" rule after fees and spread on either platform.
- No study of "fade the hype" (selling sharp news-driven spikes) by price level was found.

## Q5. How does the taker fee (largest near 50c, small near 0c and 100c) change which biases pay?

### Takeaway
Kalshi's fee is 7% × price × (1 − price) per contract, rounded up. Per dollar bet, that works out to 7% × (1 − price). So buying at 95c costs only 0.35 cents per dollar bet, while buying at 5c costs 6.65 cents per dollar bet. The fee makes longshots even worse buys and leaves favourite-buying nearly untouched. Polymarket adopted the same shape in 2026 with category rates. Rounding up on small orders and the spread can still cost more than the favourite edge.

### Cited findings
- Kalshi taker fee = round up(0.07 × C × P × (1 − P)), with P the price in dollars and C the number of contracts. Rounded up to the next cent. Maker fee uses 0.0175 instead, on some series only. Sources: [Kalshi fee schedule PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf?) (via search); [Allium blog](https://allium.so/blog/kalshi-fees-why-the-cost-peaks-near-50-cents/)
- Secondary sources say some series have their own multiplier (a few taker-free series; combos with a 2× maker fee) and that direct API members are rounded to $0.0001, not $0.01. Check Kalshi's page. Source: [QuantVPS](https://www.quantvps.com/blog/kalshi-fees-explained) (search snippet)
- Kalshi's fee table: $1.75 per 100 contracts at 50c; $0.63 per 100 at 10c and 90c. Source: [OddsShopper](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged)
- Kalshi average fee load is about 1.2-1.3c per contract (Politics 1.18c, Sports 1.33c), from the published formula, not actual fees paid. Source: [arXiv 2602.19520](https://arxiv.org/html/2602.19520v2)
- Kalshi fees by price (the project's calculation from the formula above, before rounding):

| Buy price | Fee per contract | Fee per dollar bet |
|---|---|---|
| 5c (longshot) | 0.33c | 6.65 cents |
| 10c | 0.63c | 6.3 cents |
| 50c | 1.75c | 3.5 cents |
| 90c | 0.63c | 0.70 cents |
| 95c (favourite) | 0.33c | 0.35 cents |
| 99c | 0.07c | 0.07 cents |

- Polymarket fee = shares × rate × p × (1 − p). Makers pay nothing and get rebates. Current category rates: Crypto 0.07 (20% maker rebate); Sports 0.05 (15%); Economics, Culture, Weather, Other 0.05 (25%); Finance, Politics, Mentions, Tech 0.04 (25%); Geopolitics free. Cost per 100 shares at 95c: $0.33 Crypto, $0.24 Sports, $0.19 Politics. At 99c: $0.07, $0.05, $0.04. Page undated. Source: [Polymarket docs, fees](https://docs.polymarket.com/trading/fees)
- Polymarket timeline: 15-minute crypto fees 5 Jan 2026; sports 18 Feb 2026; all crypto by 6 Mar 2026; nearly all other categories 30 Mar 2026 (Geopolitics stays free). Blended fee about 0.76% of taker volume. Sports volume did not fall after fees. Source: [Pine Analytics, 25 Mar 2026](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Conflict: Pine Analytics lists Sports' peak rate as 0.75% and Crypto's as 1.80%. The current docs' Sports rate of 0.05 implies a 1.25c fee per share at 50c. Rates appear to have changed during 2026, or the two use different bases. Sources: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout); [Polymarket docs](https://docs.polymarket.com/trading/fees)
- Kalshi: after spread and taker fees, buying favourites or fading longshots loses 0-2% per dollar; buying 0-2c contracts at the ask loses about 89%; 10-20c loses about 34%. Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- Polymarket: longshot losses are not limited to markets with fees, so fees alone do not explain the bias. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- An Aalto University thesis argues the FLB is a liquidity premium created by tick sizes and fees, not a behaviour mistake. Source: [Aalto thesis](https://aaltodoc.aalto.fi/server/api/core/bitstreams/8635ff61-baa3-4028-8c1f-d7d4c090a733/content) (search snippet; PDF blocked)
- PredictIt (OLDER): a 10% fee on winnings makes 98c buys lose money even when certain; the problem is much smaller for longshot buyers. Source: [Rajiv Sethi, 2016](https://rajivsethi.substack.com/p/fee-structure-distortions-in-prediction-16-04-10)

### Inferences
- Kalshi's fee shape is kind to favourite buyers and harsh on longshot buyers. Under PredictIt's old profit fee it was the reverse.
- Rounding matters on small Kalshi orders. One contract at 95c has a 0.33c formula fee that rounds up to a full 1c, about 1.05 cents per dollar bet. That is three times the formula and bigger than the measured favourite edge. Bigger orders spread the rounding out.
- At 95c, a 1c tick is about 1% of the price. Paying half of a 1c spread costs about 0.5 cents per dollar bet, often more than the fee. Fill quality (getting filled at your price) matters more than the fee for favourite strategies.
- Selling longshots (the same as buying favourites) is the bias the fee leaves most intact.

### Gaps
- It was not confirmed from Kalshi's own page which series charge maker fees today, or whether direct members are rounded to $0.0001.
- No study measured realized fees paid by price bucket.

## Q6. Is the bias shrinking as volume and professional traders grow (2023 → 2026)?

### Takeaway
Probably a little, but the evidence is thin. Only one paper says the Kalshi bias is shrinking, and it gives no year-by-year numbers. Polymarket's 2026 data look less FLB-like, and even reversed in weather. Profits are increasingly taken by bot-like makers.

### Cited findings
- Kalshi: "some evidence that the bias in prices is diminishing over time." No yearly figures in the excerpt. Source: [UCD WP2025/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) (search snippet)
- Whelan's own forecast (9 Mar 2026), not a measurement: biases will decline and fees will fall. Source: [Karl Whelan blog](https://www.karlwhelan.com/presentation-of-prediction-markets-and-their-future/)
- Polymarket 1-day calibration slope was 1.02 before 2026 and 0.92 in 2026 (too extreme). Without weather, 2026 is 0.99. Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- Kalshi's bias is concentrated in its least-traded third of markets (slope 1.18 vs 1.02 for the most-traded third). Source: [GitHub hrishi-tailor](https://github.com/hrishi-tailor/prediction-market-calibration)
- Contradiction: on Polymarket the pattern is stronger in heavily traded events. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- Polymarket Sep-Oct 2026: prices too extreme, not FLB-shaped (six weeks of data). Source: [GitHub shirleyshen0106](https://github.com/shirleyshen0106/polymarket-calibration)
- Polymarket profits are highly concentrated (top 1% of winners take 76.5%), and winners mostly post limit orders. Source: [EconPapers DP21615, June 2026](https://econpapers.repec.org/RePEc:cpr:ceprdp:21615). Bloomberg's headline (29 Apr 2026): "Most traders lose on Polymarket, and winners look like bots." Source: [Bloomberg](https://bloomberg.com/news/newsletters/2026-04-29/most-traders-lose-on-polymarket-and-winners-look-like-bots)
- Volume growth: Polymarket taker volume about $160M a day (Mar 2026). Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- OLDER evidence of the same idea: when betting exchanges cut costs, they had significantly lower biases than bookmakers (UK, 2006). Source: [IDEAS/RePEc](https://ideas.repec.org/a/bla/econom/v73y2006i292p673-689.html)

### Inferences
- The sources together suggest the FLB on liquid markets is small and shrinking. It survives mainly in thin markets, politics, and big multi-outcome events.
- The return to fading longshots is moving to makers. Takers, after fees and spread, are near break-even or losing in 2026.
- Adding fees in 2026 should, in theory, widen the bias again for takers. No source has measured that yet.

### Gaps
- No study gives the same bias measure year by year (2023, 2024, 2025, 2026) on either platform.
- The Cardozo et al. time appendix (Appendix B) and the full Bürgi et al. paper were not readable, so any yearly split they contain is missing here.
- Nothing measured how the 2026 Polymarket fees changed spreads or calibration.
