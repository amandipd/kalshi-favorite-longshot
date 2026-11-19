# Pricing Kalshi contracts off other markets, and edges from how contracts settle

Researched 26 October 2026. Plain-words glosses are next to each technical term.
Kalshi taker fee used throughout: 7% × price × (1 − price) per contract, rounded up to $0.0001 per order.
That is 1.75 cents per contract at a 50c price, 0.63 cents at 90c, and about 0.2 cents at 97c.

Quick key to terms used below:
- **Digital option**: an option that pays a fixed amount if the price ends above a strike. A Kalshi "above X" contract is one.
- **Risk-neutral probability**: the odds read off prices. It includes the pay traders demand for carrying risk, so it is not the pure chance.
- **Breeden-Litzenberger / SVI**: the standard way to read the market's odds from option prices at many strikes. SVI is the smooth curve fitted across strikes first.
- **DVOL**: Deribit's 30-day bitcoin volatility index, a "VIX for bitcoin".
- **Variance (volatility) risk premium**: options usually price in more movement than actually happens. People who sell tail bets get paid for that.
- **Brier score**: a score for probability forecasts. Lower is better; 0 is perfect.
- **MAE (mean absolute error)**: the average size of a miss.
- **Out-of-sample / held-out**: tested on data the rule never saw while being built.

---

## Q1. Crypto and stock-index price markets priced from options or a volatility model: is there a gap, does it survive fees, and are tails over- or under-priced?

### Takeaway
Several open-source projects now price Kalshi bitcoin and S&P 500 contracts from options, but none has a finished, fee-included, out-of-sample result as of 26 Oct 2026. The best interim number cuts against the idea: where Kalshi and options disagreed by 3c or more, Kalshi's price was slightly more accurate (Brier 0.126 vs 0.130). Deeper markets were not the better guide. One peer-reviewed paper (2026) finds Kalshi bitcoin contracts carry their own volatility risk premium, only loosely tied to Deribit's.

### Cited findings

**Peer-reviewed / academic (strongest available)**
- Lee, Lee & Lee (2026), *International Review of Financial Analysis* vol. 119, 105433, treat Kalshi fixed-strike bitcoin contracts as cash-or-nothing digital options. They pull implied volatility, implied odds and variance measures from them. Only the abstract-level summary was readable; the full text was blocked (HTTP 403). Sources: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1057521926003601); citation confirmed via [co-author LinkedIn](https://kr.linkedin.com/in/kwanho-kim-ba428676)
- Same paper: the Kalshi bitcoin "smile" (how implied volatility changes across strikes) is roughly symmetric. That is unlike the stock-index pattern, where crash protection costs extra. Source: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1057521926003601)
- Same paper: Kalshi bitcoin contracts hold a "robust" variance risk premium (they price in more movement than happens). It is only weakly correlated with Deribit's DVOL. No size in cents or fee-included trading test was visible in the readable part. Source: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1057521926003601)
- Mohanty & Krishnamachari (arXiv, 1 Apr 2026; not peer reviewed): daily moves in Kalshi macro markets help forecast crypto's actual volatility. Data: 10 Kalshi series, 6 coins, Jan 2023 to Mar 2026. Changes in Fed-rate odds (KXFED) predict bitcoin volatility, far too strong to be luck (t = 3.63, p < 0.001). The recession market was the most stable on held-out data, with forecast error 2.1% lower than the baseline (error ratio 0.979, Clark-West p = 0.020). It adds information beyond fed funds futures and DVOL. It is a forecasting result only, with no trading test. Source: [arXiv 2604.01431](https://arxiv.org/abs/2604.01431)
- Bhaskara & Jerfy (arXiv, 13 Sep 2026): they use Kalshi bitcoin contracts as options to hedge spot bitcoin. They claim the dynamic hedge "outperforms" simple portfolios and warn that fees could erode the gain. The abstract has no numbers. Source: [arXiv 2609.14267](https://arxiv.org/abs/2609.14267)

**Open-source projects, no products sold (medium-weak: small samples, paper trading)**
- "Implied Odds" (Tave La Rocque, UBC; MIT licence, sells nothing) paper-trades Kalshi S&P 500, Nasdaq-100 and bitcoin against options. Index odds come from Cboe SPX/NDX options; bitcoin odds come from Deribit, shifted to Kalshi's hourly settle time. Rules: fees included, 100 lots, gap of at least 3c. Source: [GitHub](https://github.com/tavelarocque/implied-odds-research)
  - S&P daily range contracts over 1,129 trading days: "well calibrated" (a 70c price wins about 70% of the time). There is a small favourite-longshot bias in the final hours, but it does not pay after spread and fees.
  - Where the two venues differed by 3c or more on settled stock and bitcoin trades, Kalshi scored slightly better than options (Brier 0.126 vs 0.130). Snapshot dated 16 Oct 2026.
  - The bitcoin paper trader swung from +$2,074 to −$90 and back to about +$680 within one week. The author blames clustered bets on neighbouring strikes.
  - Execution check: about half the quoted Kalshi size was gone around 18 seconds after the snapshot.
  - Blending Kalshi's price with realised volatility beat Kalshi alone by a tiny margin on held-out data: Brier lower by 0.0017 at 3 hours (97.5% range −0.0027 to −0.0005). Its forward test is still pending.
  - The pre-registered options-vs-Kalshi verdict (rules fixed before the deciding data exists) is due **30 Nov 2026**. A "sell bitcoin downside long shots on fear days" test is due 1 Feb 2027. The README says no strategy has yet passed the bar for real money.
- japark22 "kalshi-mispricing-engine" compares Kalshi daily S&P 500 ranges (KXINX, 25-point bins) with same-day SPXW options. It runs a 6-stage funnel: raw gap ≥1c, then beat the spread, beat fees, beat option-quote uncertainty, beat model error, then real displayed size. **No results are published yet.** It reports P&L only after 40+ settled days. Source: [GitHub](https://github.com/japark22/kalshi-mispricing-engine)
  - Its power study: you cannot tell risk premium from mistakes using outcomes alone. With strong risk aversion (θ = 10), the chance of detecting it is only 26% after 2,500 trading days. At θ = 2 it is 7%. In plain words, outcome-based backtests on index ranges have almost no power. Price-based comparisons are needed. Source: [GitHub](https://github.com/japark22/kalshi-mispricing-engine)
  - Per a search summary of the repo, its option-implied uncertainty band covered the truth only 61% of the time against a stated 90% in the same-day case. So option-implied odds are noisier than they look. Source: [GitHub](https://github.com/japark22/kalshi-mispricing-engine) (from search snippet, not seen on the fetched page)
- ethan2boz007 "sp500-options-vs-kalshi": the first run was 19 Oct 2026, with no findings yet. Kalshi range midpoints add up to 1.2-1.4 instead of 1.0, because far-out ranges barely trade and their midpoints overstate tiny chances. Source: [GitHub](https://github.com/ethan2boz007-a11y/sp500-options-vs-kalshi)
- milanroundraise "kalshi-mispricing": 164 hourly KXBTCD markets over 7 days, 655 checkpoints. Kalshi-implied volatility differs from DVOL far beyond luck (p ≈ 5.6×10⁻⁹, n = 162). The error is "S-shaped", mostly because a 30-day vol index was used for contracts expiring in minutes or hours. Source: [GitHub](https://github.com/milanroundraise/kalshi-mispricing)
  - Its first trading rule won 24% of bets, and the top 5 trades made 58% of the profit. The author calls that "closer to gambling". Spread was modelled; **fees were not**. No net P&L. Source: [GitHub](https://github.com/milanroundraise/kalshi-mispricing)
- Nadimul96 "kalshi-vol-edge" priced Kalshi BTC contracts with a log-normal model and Coinbase realised volatility. It traded real money in March 2026 and ended with "a small net loss" (no figure). Source: [GitHub](https://github.com/Nadimul96/kalshi-vol-edge)
  - Backtest: 9 trades, net +$8.94 after $0.72 fees. The author says this "is not evidence of an edge".
  - Lessons: a position priced right against Binance lost $32 against BRTI. Buying hourly long shots gave 1 winner in 35 against about 5 expected (z ≈ −1.96, borderline luck). Taker fees ate the thin edges.
- BSIC (Bocconi student society, 16 Feb 2025; older evidence): one snapshot of weekly Kalshi BTC contracts against Deribit SVI-implied odds. The options gave **lower** odds than Kalshi on far strikes, by up to about 12 points at the $99,000 strike. The snapshot was taken just after listing, in thin books. No backtest. Source: [BSIC](https://bsic.it/well-can-they-predict-an-investigation-of-crypto-prediction-contracts/)

**Vendor (weak: sells subscriptions, uses affiliate links)**
- predictionmarketspicks.com "Bitcoin Edge" prices hourly KXBTCD from **IBIT ETF options**, not Deribit, using Black-Scholes N(d2). Claimed record: 586 wins, 409 losses (59%) over 995 signals, "+$52.23 at par". The page does not say whether fees and spread are included, or what stake one signal is. Last 30 days: 54-42 (56%). The record was reset in August 2026. Pro costs $111 for the first year, then $150 a year, and the page has a disclosed Kalshi referral link. Source: [predictionmarketspicks](https://predictionmarketspicks.com/tools/bitcoin-edge)
  - Its own claim: only hourly settles from 10 AM to 4 PM ET on weekdays, inside US options hours, "carry the edge". Source: [predictionmarketspicks](https://predictionmarketspicks.com/articles/how-kalshi-settles-bitcoin)
- ProCap Insights (sells research subscriptions), 29 Apr 2026: Kalshi year-end S&P "touch" contracts (pay if the index *hits* X at any time) looked 17-33 points cheap against a random-walk barrier model. Example: 7,800 touch at 37.5c against a model value of 53-70%. It relies on assumed drift and volatility, not on options prices. One snapshot. Source: [ProCap](https://www.procapinsights.com/reports/sp500-price-target-prediction-markets-wall-street-investing)

**Background on the inputs**
- Deribit DVOL was 38.28% a year on 20 Oct 2026, against actual recent volatility of about 20-25%. That is the usual premium in options. Source: [cryptoticker](https://cryptoticker.io/en/bitcoin-price-prediction-volatility-premium-20-october-2026/) (search summary)
- The Fed's Kalshi paper warns that Kalshi odds are risk-neutral (they include pay for risk). Far-tail contracts often trade little, so their prices go stale. Source: [NBER w34702](https://www.nber.org/system/files/working_papers/w34702/w34702.pdf)

### Inferences
- The "deeper market = fair price" assumption is not backed by evidence yet. The one live comparison (Implied Odds) found Kalshi slightly *more* accurate than options where the two disagreed. A bot that trades every options-vs-Kalshi gap could be trading against the better forecast.
- The one consistent finding is about **far tails**. Kalshi midpoints overstate small chances (sums of 1.2-1.4; longshots 1 in 35 against about 5 expected). That is the favourite-longshot bias again, which this project already covers. Options add little new there.
- Using a 30-day vol index (DVOL) for hourly contracts is a known trap. Any test should use short-dated Deribit expiries shifted to the Kalshi settle time, as Implied Odds does. Or it should use recent realised volatility.
- For the S&P same-day ranges, the key result is the power study. Only tests that compare prices (Kalshi vs options at the same moment) can find an edge in a reasonable time. Waiting for outcomes alone would take years.
- The 30 Nov 2026 Implied Odds verdict is the first pre-registered, fee-included result due. It is worth reading before building anything.

### Gaps
- No finished, fee-included, out-of-sample P&L for options-vs-Kalshi on crypto or indices exists yet. The first is due 30 Nov 2026.
- The size of the variance risk premium in Lee, Lee & Lee (2026) could not be read because the full text was blocked.
- No study measures whether Kalshi index range *tails* are over- or under-priced against SPX options at matching strikes. The projects that could do it have no results yet.
- No source checks whether Kalshi ETH (KXETHD) or Nasdaq (KXNASDAQ100U) are priced differently from their options.

---

## Q2. Kalshi Fed-rate and economic markets vs CME FedWatch / fed funds futures / SOFR, and inflation markets vs swaps or the Cleveland Fed nowcast: any documented, tradable gaps?

### Takeaway
Kalshi's Fed and CPI markets are at least as accurate as futures and nowcasts. They are sometimes significantly better, so using the futures as "fair value" to trade Kalshi is not supported. A data vendor found persistent gaps of 1.7-2.8 basis points in 2026. A toy fee-included strategy made money in 2 meetings, but that needed a futures hedge far too big for a small bot. Kalshi had about 140 times less depth.

### Cited findings
- Diercks (Federal Reserve Board), Katz & Wright, NBER Working Paper 34702 (Jan 2026; not peer reviewed): Kalshi data since 2022. Source: [NBER w34702](https://www.nber.org/system/files/working_papers/w34702/w34702.pdf)
  - The day before the FOMC (Fed rate meeting), the Kalshi median and mode had a perfect record. Average miss: 0.000 points against 0.010 for fed funds futures. That gap is significant at the 5% level (Diebold-Mariano test, a test of whether one forecast is really more accurate). The Kalshi *mean* tied futures at 0.010.
  - Headline CPI on release day: Kalshi median/mode missed by 0.063 points on average, against 0.081 for the Bloomberg consensus. That is significant at the 10% level. Core CPI and unemployment showed no significant difference. Kalshi was never significantly worse.
  - The Kalshi forecast for 2025 CPI "lines up fairly closely" with the one-year inflation swap. No tradable gap is reported.
  - SOFR options gave biased Fed odds for Q4 2025, because SOFR traded about 6 bp above the fed funds rate. Kalshi and fed funds futures agreed with each other. So SOFR is a poor benchmark for Kalshi Fed markets.
  - The paper also checked whether Kalshi's spread of outcomes was right. There is "some evidence of risk premia overstating the odds of higher inflation and higher unemployment". Low readings came "a little too frequently", but overall the forecasts were "fairly well calibrated".
- Lucidate Substack (UK author who does not trade; sells nothing beyond the newsletter; not peer reviewed): 37 Fed meetings, Mar 2022 to Sep 2026, 4,694 rung-days (a rung is one strike on the Fed ladder). Source: [Lucidate](https://lucidate.substack.com/p/a-dollar-bet-has-called-the-fed-as)
  - Brier score: Kalshi ladder 0.0117, CME futures (FedWatch method) 0.0126. Kalshi was better at 25 of 37 meetings.
  - When Kalshi was given a one-day handicap (using the previous night's close), it was a tie: 21-16, no better than a coin flip (sign test p = 0.51).
  - In the 30-70c zone, the Kalshi ladder priced 48c and 49% settled yes. Futures implied 48% and only 36% settled yes. Calibration error was 0.0076 for Kalshi against 0.0110 for futures.
  - Headline CPI over 56 releases: Kalshi Brier 0.065 against 0.101 for the Cleveland Fed nowcast (the author's own conversion of the nowcast into odds). Core CPI: 0.076 against 0.088.
  - Example gap: 4 Oct, Kalshi October rung 16-20c against 20c in CME November futures. The author does not treat such gaps as arbitrage. Fees are not discussed.
  - A single 50,000-contract sale moved a Kalshi rung from 67c to 48c within an hour, before any news.
- BMLL Technologies (a market-data vendor promoting its data), 1 Oct 2026: 12 FOMC meetings, May 2025 to Sep 2026. Source: [BMLL](https://www.bmlltech.com/news/market-insight/when-kalshi-and-fed-funds-futures-disagree)
  - Kalshi and fed funds futures disagreed by up to 2.8 bp on the expected decision. Ten days before the July and September 2026 meetings, futures priced more tightening on every one of 26 days. The gaps were 1.8-4.4 bp in July and 1.2-2.3 bp in September. In September 2025 the sign was reversed, so the direction is not stable.
  - Who was right: Kalshi in July (the Fed held), futures in September (the Fed hiked 25 bp).
  - Toy strategy requiring at least 0.25c net edge per Kalshi contract after costs, both legs taken at market. Modelled P&L: $3,944 in July after $1,200 fees, and $791 in September after $246 fees. Only 2 meetings.
  - Depth: about $17,500 per bp on Kalshi against about $2.5 million per bp on futures, roughly 1 to 140.
  - Futures moved about 0.6 seconds before Kalshi after the 11 Sep 2026 CPI release. The lag grew with the size of the move.
- Kalshi's own July 2026 FOMC preview: futures implied a 38% chance of a 25 bp hike against 18% on Kalshi. Kalshi is a party with an interest. Source: [Kalshi research](https://kalshi.com/research/insights/july-fomc-preview) (search summary)
- Kalshi's July CPI preview put Kalshi a tick below the Cleveland Fed nowcast: 3.3% headline and 2.4% core, against 3.4% and 2.5%. It is a one-off comparison. Source: [Kalshi research](https://kalshi.com/research/insights/july-cpi-preview) (search summary)
- The Cleveland Fed nowcast is public and simple. Core inflation is assumed to equal its trailing 12-month average. Energy comes from daily oil and weekly gasoline prices. Source: [Cleveland Fed](https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting) (search summary)

### Inferences
- "Fade Kalshi toward FedWatch" is not supported. Both the Fed paper and the Lucidate study find Kalshi at least as accurate, and better in the 30-70c zone. The same holds for "fade Kalshi CPI toward the Cleveland nowcast": the nowcast scored worse.
- The BMLL gaps of 1.7-2.8 bp are real but tiny. One fed funds futures contract is roughly $41.67 per bp, and BMLL notes $2.5 million per bp of depth. Hedging needs a futures account and much more capital. For a bot with a few thousand dollars, the trade is just a one-sided bet that futures are right. On BMLL's own two meetings that won once and lost once.
- One possibly tradable tilt: the Fed paper's evidence that Kalshi over-weights *high* inflation and unemployment outcomes. Selling those upper rungs would test it. The paper calls the effect borderline, it was not measured after fees, and the sample is small (monthly releases since 2022).
- Fed and CPI markets are slow, event-driven and thin on weekends. That is a poor match for a bot built around frequent short crypto windows.

### Gaps
- No fee-included backtest of Kalshi CPI against the Cleveland Fed nowcast or inflation swaps was found.
- No fee-included backtest of one-sided Kalshi-vs-FedWatch trades (without a futures hedge) over many meetings was found.
- No Kalshi-vs-futures study for payrolls or GDP was found. No liquid futures exist for those, so there is nothing to price against.

---

## Q3. Settlement mechanics: does the BRTI 60-second average create a last-minute edge? Other settlement quirks?

### Takeaway
The official Kalshi rules confirm that hourly and daily BTC and ETH contracts settle on the simple average of the 60 one-second BRTI values before the hour. **Trading stays open through that minute.** Once part of the average is fixed, the remaining uncertainty shrinks much faster than a spot-price model assumes. One open-source test found this "nowcast" (a live estimate of the settle) beat the Kalshi book in the last minute. But that test covered only 12 settlements, so it is a lead, not evidence.

### Cited findings
- Kalshi rules text (pulled from Kalshi's public API on 26 Oct 2026) for KXBTCD and KXBTC (range): "If the simple average of the sixty seconds of CF Benchmarks' Bitcoin Real-Time Index (BRTI) before 5 PM EDT is above 89749.99…". The secondary rule: "At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices." Sources: [Kalshi API, KXBTCD markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTCD); contract terms at [assets.kalshi.com BTC.pdf](https://assets.kalshi.com/contract_terms/BTC.pdf)
- The same API data shows KXBTCD and KXETHD trading close (`close_time`) at 21:00 UTC, which is 5:00 PM EDT, exactly the settle time. So trading continues through the whole 60-second averaging window. The settlement timer is 60 seconds and expected expiration is 5 minutes later. Source: [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTCD)
- BRTI is computed every second from the order books of the member exchanges. A book older than 30 seconds, or with no bids, no asks, or crossed prices, is dropped. Order sizes are capped at 5 standard deviations from a trimmed mean. Source: [CME/CF BRTI methodology](https://www.cmegroup.com/trading/files/bitcoin-real-time-index-methodology.pdf) (search summary)
- A June 2026 CF Benchmarks consultation proposes a new step to resolve crossed books, which are currently kept. The index formula may change. Source: [CF Benchmarks](https://www.cfbenchmarks.com/blog/announcement-of-consultation-on-changes-to-the-cme-cf-real-time-indices-methodology) (search summary)
- JihuiTanUchicago PR #160 (open source, research only, no live trading) "nowcasts" the settle from the partly fixed average. Source: [GitHub PR #160](https://github.com/JihuiTanUchicago/trading-rsi/pull/160)
  - Once part of the average is fixed, the settle's spread shrinks roughly as (time left)^1.5, not √(time left) as in a normal spot-vs-strike model.
  - A 7-exchange composite tracked official BRTI with an error of about $4 (RMSE, a typical-miss measure). One-second changes understate the real moves by about 20%, because exchanges update at different times.
  - On 12 settlements (24-25 Oct 2026), hourly KXBTC/KXBTCD in the last 60 seconds: the nowcast had a Brier score of 0.03 against 0.13 for the Kalshi book midpoint.
  - Taker simulation filling at the ask 1 second later: 13 trades, net about +$0.58 per contract in total after taker fees. The author says 12 settlements is "far too few to trust" and plans a rerun at about 100.
- For KXBTC15M, each 15-minute contract's strike is the same 60-second average taken at its open, so one contract's settle equals the next contract's strike. Source: [GitHub PR #160](https://github.com/JihuiTanUchicago/trading-rsi/pull/160)
- Basis (the gap between two prices of the same thing): Coinbase alone against BRTI showed a mean gap of $17.31 and a maximum of $52.38. Coinbase was on the wrong side of the strike in 2 of 30 settled markets (March 2026). Source: [Nadimul96 kalshi-vol-edge](https://github.com/Nadimul96/kalshi-vol-edge)
- dev.to (author promotes a GitHub repo and Telegram, sells nothing directly): Polymarket uses a Chainlink 60-second average and Kalshi a 60-second BRTI average, so short BTC contracts on the two venues are not equivalent. It mentions unnamed research on "large settlement-window gains" for a few Polymarket wallets, with no figures or sources (weak). Source: [dev.to](https://dev.to/abrownfox001/polymarket-twap60-vs-kalshi-why-settlement-design-decides-your-bot-series-14-4gl3)
- Vendor note: the last print before the close is not the settle price. The price can be above the strike at :59 and still settle NO if most of the minute was below. Source: [predictionmarketspicks](https://predictionmarketspicks.com/articles/how-kalshi-settles-bitcoin) (vendor, sells subscriptions)
- **S&P 500 settlement**: Kalshi's INX contract terms name **Kalshi itself as the "Source Agency"**. The underlying is "the price of the S&P 500 Index" at the listed time. If no data exists for that time, the latest value before it is used. Source: [Kalshi INX terms](https://assets.kalshi.com/contract_terms/INX.pdf)
  - Live market rules (26 Oct 2026) say "end-of-day S&P 500 index value". They also note: "the Exchange has modified the Source Agency and Underlying for indices markets". The API lists settlement sources as "For example, Google Finance". Source: [Kalshi API, KXINXU](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXINXU)
  - Hourly and daily S&P contracts (KXINXU, KXINX) stop trading at 20:00 UTC (4:00 PM EDT), with expected expiration at 23:00 UTC. Source: [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXINXU)
- **Gold** (KXGOLDD) settles on the close of the **Pyth** gold 1-minute candle at 5:00 PM EDT, which covers trading from 4:59:00 to 4:59:59 PM. Trading closes at 21:00 UTC, the same moment. Source: [Kalshi API, KXGOLDD](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXGOLDD)
- **WTI oil** (KXWTI) settles on the daily settlement price of the nearest WTI futures month (December 2026 at the time of checking). It rolls to the next month 2 business days before the last trading day. The series lists ICE as the source. Kalshi trading closes at 18:30 UTC, which is 2:30 PM EDT. Source: [Kalshi API, KXWTI](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXWTI)

### Inferences
- **The math of the averaging edge (the project's own working, not from a source).** Take a 60-second simple average of a random walk with per-second volatility σ.
  - Seen from the start of the window, the average's spread is σ·√(60/3) ≈ 0.58 of the end price's spread.
  - With r seconds left, the unknown part has spread σ·√(r³ / (3·60²)).
  - At bitcoin around $90,000 and about 38% annual volatility (DVOL), σ is about $6 per √second.
  - With 30 seconds left, the settle's typical miss is about **$10**. A spot model that ignores the averaging says about $33.
  - With 10 seconds left: about **$2** against about $19.
  - So in the last half-minute, a spot-based model badly overstates uncertainty. Any contract with its strike more than about $20-30 from the running average is close to decided. That holds while the BRTI rebuild error (about $4) stays small.
- This fitted the bot's setup: its server sat next to Kalshi in us-east-2, and it already handled BRTI-settled 15-minute markets. But it is in practice a **speed race**, which the project has already studied in general. The 18-second size decay seen by Implied Odds and the PR #160 one-second fill delay suggest others compete for the same quotes. Prices near 97-99c in that minute pay only about 0.2c in fees, so a 1-2c gap would survive fees if fills exist.
- The project's earlier spot-price fair-value filter (positive in backtest, not adopted) probably used a spot-style variance. Redoing it with the partly-fixed-average variance in the final minute of hourly KXBTCD/KXETHD is the most direct, testable new idea here. It needs a BRTI rebuild good to a few dollars.
- **S&P 4:00 PM close**: Kalshi stops trading at 4:00:00 PM, but the official close comes from the closing auctions. So no last-minute trading edge exists on Kalshi itself. Kalshi naming itself the Source Agency adds a small rules risk around disputes.
- **Gold at 5:00 PM EDT**: settlement uses a Pyth price at the very end of the CME metals day. If the CME daily break starts at 5 PM ET (not verified here), the settle candle falls in a thin moment. Pyth's gold feed could then drift from COMEX. This is untested.

### Gaps
- No large-sample study measures how often the last-minute Kalshi book misprices the partly fixed BRTI average, or how much size is available. The only data is PR #160's 12 settlements.
- It was not confirmed whether real-time official BRTI is available to retail bots, or only a rebuild from member-exchange feeds. PR #160 used a 7-exchange rebuild with about $4 error.
- The text of Kalshi's change to the index "Source Agency and Underlying", and its date, were not found.
- The CME gold daily-break timing, and how Pyth's gold price is built, were not verified.
- No source reported settlement disputes or index-error events on Kalshi crypto or index markets.

---

## Q4. Commodity, FX and gas markets on Kalshi priced against futures (WTI, gold, EUR/USD, RBOB): any evidence of gaps?

### Takeaway
No independent study was found. The only evidence is a vendor track record for oil with more losses than wins, plus settlement rules that make fair-value pricing from futures straightforward in principle.

### Cited findings
- KXWTI settles on the daily settlement price of the nearest WTI futures month, with a roll 2 business days before the last trade date. Settlement is rounded to 2 decimals. Source: [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXWTI)
- KXGOLDD settles on Pyth's gold 1-minute candle at 5:00 PM EDT. Source: [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXGOLDD)
- KXEURUSDH (hourly EUR/USD over/under) lists "ICE" as the source, linked to TradingView's FX_IDC feed. No market was open when checked on 26 Oct 2026. Source: [Kalshi API, series](https://api.elections.kalshi.com/trade-api/v2/series/KXEURUSDH)
- Vendor "Oil Edge" (predictionmarketspicks) compares Kalshi weekly oil ladders with USO options. Reported record: 571 graded positions, 266 won and 305 lost, described as net-positive on a small per-contract basis. Fees and spread treatment unknown. The vendor sells subscriptions, uses affiliate links, and the page was not fetched in full. Source: [predictionmarketspicks](https://predictionmarketspicks.com/tools/oil-edge) (search summary)
- The same vendor says Kalshi daily oil flow is mostly retail in 1-10 contract clips, against professional market makers in USO options. That is a claimed source of gaps, not measured. Source: [predictionmarketspicks](https://predictionmarketspicks.com/tools/oil-edge) (search summary)

### Inferences
- Because these contracts settle on a published futures settlement price or a 1-minute feed, the fair value is a digital option on that futures contract. Same-expiry options on oil (CME) or gold would give risk-neutral odds directly. The approach is easy to build but unproven.
- This project's own 18 Oct backtest (AAA gas passed; FX not yet tested) is a better guide than anything found here. FX and oil are open questions.

### Gaps
- No academic or independent study of Kalshi commodity or FX prices against futures or options.
- No information on EUR/USD contract depth or past results.
- RBOB (gasoline futures) against Kalshi gas markets: nothing found. Kalshi's gas market settles on the AAA average retail price, not RBOB, so the link is indirect.

---

## Q5. Carry / time value: Kalshi pays interest on cash and positions; Polymarket pays holding rewards. Is buying long-dated near-certain contracts a measurable carry trade?

### Takeaway
Near-certain long-dated contracts on Polymarket trade at a discount that works out to roughly a 3-7% a year required return. That is about a T-bill-like return for tying up money, not free money. Kalshi now pays 3.50% a year on positions at market value, which offsets most of that cost. No study measures realised returns after fees, or how often "near-certain" contracts fail.

### Cited findings
- Kalshi's help page (seen 26 Oct 2026, marked "Updated this week") says the interest rate is **3.50%** a year and "variable". Source: [Kalshi help](https://help.kalshi.com/navigating-the-exchange/your-portfolio/apy-on-kalshi)
  - It is paid on cash and positions. Positions are valued at last traded prices at 12 am ET.
  - It accrues daily and is paid monthly.
  - You need a $250 average monthly balance, you must be a US user, and an SSN is needed for interest above $10 a year.
  - Perps traders can get 7% under a separate program.
- Search snippets of older Kalshi help pages showed 3.25% and 4.05%. The page that showed 4.05% now returns "not found". The rate changes often. Source: [Kalshi help (old FAQ, now 404)](https://help.kalshi.com/faq/interest-apy-on-kalshi) (search summary)
- Polymarket pays 4% a year "holding rewards" on selected long-dated markets. The rate is variable and set at the company's discretion. Source: [Yahoo Finance](https://finance.yahoo.com/news/polymarket-lures-bettors-highest-4-204736721.html) (search summary)
- Gebele & Matthes (arXiv, 29 May 2026; not peer reviewed). Data: Polymarket from launch to 31 Dec 2025. Near-certainty sample: 36,349 markets and 3.7 million price observations. Carry analysis: 19.9 million trades. Sources: [arXiv 2605.31431](https://arxiv.org/abs/2605.31431); numbers from the [HTML full text](https://arxiv.org/html/2605.31431)
  - The yearly return needed to hold near-certain contracts (their "annualized settlement wedge") averages **3.06%** on the cheapest edge of prices. It is 4.36% and 6.89% on wider measures.
  - It falls sharply at short horizons, steadies by about 20 days, and bumps up again around 230-260 days.
  - Adjusting for this discount removes 48-88% of the pattern where long-dated contracts look under-confident. It removes 56-93% on held-out events.
  - Polymarket's 4% holding rewards did "not produce a comparable upward break" in the discount.
  - Short "bonding" trades (buying near-certain contracts close to settle) show a median annualised yield of 6.22% and a mean of 29.08%. The authors warn these are hour-long holds blown up to yearly rates.
  - The paper reports **no realised returns, no failure rate for near-certain contracts, and no after-fee figures**. Its example: buying NO at 96c earns about 4.2% if it pays $1, with money locked for most of a year.
- Kalshi-specific numbers were not given in the paper's cross-venue comparison (sample counts not stated). Source: [arXiv HTML](https://arxiv.org/html/2605.31431)

### Inferences
- On Kalshi, a long-dated 96c contract earns the 4c pull to $1 plus 3.50% a year on its market value. If Kalshi prices matched Polymarket's discount (about 3-7% a year), the Kalshi holder would earn roughly 6.5-10.5% a year before fees. But competing Kalshi traders also get the interest, so Kalshi prices should sit closer to $1 than Polymarket's. The extra return is likely smaller than this sum. Nobody has measured it.
- The fee hurts long holds less: buying at 96c costs about 0.27c per contract (0.07 × 0.96 × 0.04), against about 4c of pull to $1. The real risks are the "certain" outcome failing (unmeasured) and capital tied up for months. That fits poorly with a bot that recycles its bankroll every 15 minutes.
- For this project, carry matters for idle cash more than for strategy. Cash and positions above $250 already earn 3.50% on Kalshi.

### Gaps
- No study measures how often long-dated "near-certain" (95c+) Kalshi contracts actually fail, or their realised returns after fees and interest.
- No data on whether Kalshi long-dated prices sit closer to $1 than Polymarket's, which would show the interest being priced in.
- The current Kalshi rate is uncertain: 3.50% on the live page, 3.25% and 4.05% in older snippets. Check the account page.
