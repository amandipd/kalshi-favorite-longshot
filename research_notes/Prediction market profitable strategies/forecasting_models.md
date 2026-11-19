# Model-based forecasting strategies on prediction markets (weather, sports, economic data, elections, other)

Notes compiled 25 Oct 2026. Every figure has a date. Anything from before 2025 is marked **(older)**.

Plain words for terms used below:

- **edge**: profit per contract, in cents.
- **¢/$1**: cents of profit for every dollar bet.
- **calibration**: whether a 70c price really wins 70% of the time.
- **favourite-longshot bias**: cheap unlikely bets are overpriced, heavy favourites underpriced.
- **depth**: how much money you can trade before moving the price.
- **spread**: the gap between the buy and sell price. It is what it costs to get in.
- **taker fee**: Kalshi's charge for trading, biggest near 50c. A "taker" hits a price already on the board. A "maker" posts a price and waits.
- **adverse selection**: getting picked off by someone who knows more than you.
- **out-of-sample**: tested on data the rule never saw while being built.
- **Brier score**: a score for probability forecasts. 0 is perfect. Lower is better. Always saying 50% scores 0.25.
- **MAE (mean absolute error)**: the average size of the miss.
- **CLV (closing line value)**: did you get a better price than the last price before the game started? Sports bettors use it as the standard test of a real edge.
- **de-vig**: strip the bookmaker's built-in margin out of the odds to get fair chances.
- **calibration slope**: a score for how prices compare with results. Above 1 means prices sit too close to 50c (too timid). Below 1 means prices are too extreme (too sure).
- **95% CI**: the range the true number is probably in.

Source warnings used below: **[SELLS]** = the source sells a bot, data, picks or courses. **[AFFIL]** = earns money from sign-up links. **[SELF]** = the platform or a party with a stake grading itself.

---

## Weather: Kalshi daily high-temperature and rain markets, plus Polymarket weather. Do model traders make money? How deep are the markets? What are the settlement quirks?

### Takeaway
The best public test says Kalshi weather prices already match good weather models, so there is no edge left after fees (OddsReference, Mar-Jul 2026). Public money-makers are a handful of Polymarket accounts, and their sizes are small. The markets are thin: one big-city day trades about $22K in total, and a Swiss forecasting firm says they are too thin for a big fund.

### Cited findings

**Careful public tests (Kalshi)**
- OddsReference built a NYC high-temperature model. It blended two US weather models, GFS (54.7%) and NAM (45.3%), using NWS data and the official daily climate reports. It turned the blend into chances for each 2°F price range (published 26 Mar 2026, updated 19 Jul 2026). [AFFIL: says it "may earn a commission" on Kalshi sign-ups.] Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Sample size in that test: 1,506 NYC days and 40,032 settled Kalshi weather contracts. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- The model picked the winning range 33.0% of the time. Picking at random gets 16.7%. When the model said "over 50% likely", it won only 44.3% of the time, against 53.7% predicted. So the model was too sure of itself. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Best strategy was selling the unlikely ranges. It won 96.6% of the time. But profit was tiny: about 0.62% return as a taker and 6.22% as a maker. It collected about 5c a win and lost about 95c when wrong. The authors' own summary table shows different numbers (+0.03c taker, +0.31c maker), so the figures don't line up inside the article. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Buying the model's top two ranges lost 14.95c per day. It cost 76.5c on average but only paid off 61.55% of the time. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Their verdict: weather markets are efficient (prices already reflect the public information). No usable edge is left after fees. Any edge would need better calibration, faster reaction, or maker-fee savings. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Market behaviour in that study: prices move 1-3c after an NWS forecast update. 73% of contracts moved more than 1c within an hour of an update. The reaction takes 10-30 minutes. Most trading happens 2-4 hours before the day ends. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)

**A public loss write-up (Kalshi)**
- An AI trading-agent blog (MAXIMUS / Northlake Labs) traded Kalshi daily highs using NWS forecasts. Result: 32 trades, 0 wins, 32 losses, "a few hundred dollars" lost (post dated 23 Feb 2026). Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Cause 1: it assumed forecast misses follow a bell curve. In reality, "2-sigma" misses (big misses that a bell curve says happen 5% of the time) happened about 10-12% of the time. So a "90%" call was really closer to 75-80%. Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Cause 2: fees on cheap contracts. A 1c fee on a 5c contract is a 20% cost. The author now avoids contracts under about 15c. Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Cause 3: speed. Other bots repriced within seconds of each NWS model update. The author polled every 15-60 minutes, so it traded stale signals and became "exit liquidity". Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)

**Open-source and vendor bots**
- A public GitHub bot trades Kalshi temperature markets using the 31 runs of the GFS ensemble (a set of slightly different model runs, pulled free from Open-Meteo). The share of runs above a line becomes the chance. It trades when its edge is over 8%. It claims "highest profits $1.8k". That is self-reported. (Seen Oct 2026.) Source: [GitHub suislanchez](https://github.com/suislanchez/polymarket-kalshi-weather-bot)
- Predict & Profit sells a Kalshi weather bot built on NOAA's National Blend of Models. No return figures found. [SELLS] Source: [Predict & Profit](https://predictandprofit.io/)
- A bot-seller backtest found only 70 of 500 strategy variants ended positive. The median return was −41.61%. [SELLS] (2026, per search summary.) Source: [BotForKalshi](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy)

**Polymarket weather traders (named accounts)**
- Bloomberg (15 Apr 2026): "Hans323", a 23-year-old German law student with no weather training, was the sixth-highest all-time earner in Polymarket weather markets. He bet mainly on daily highs in London and New York. Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)
- A crypto news site said Hans323 made $1.11 million from one $92,632 bet on a London weather outcome priced at 8%. This is secondhand and unchecked. Source: [KuCoin News](https://www.kucoin.com/news/flash/traders-on-polymarket-earn-millions-by-predicting-weather)
- Bloomberg (15 Apr 2026): Finnish developer "1-800-LIQUIDITY" made about $33,000 in weather winnings since the previous October. He is writing software to automate it. Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)
- Bloomberg (15 Apr 2026): Jua, a Swiss AI weather firm, runs a small friends-and-family fund trading Polymarket high-temperature contracts. Its CEO says "relative returns are high" but the market is too thin for a large fund. Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)
- Bloomberg (15 Apr 2026): staff at Windborne Systems (an AI weather firm) traded using its own models. They learned official station readings can be noisy, for example sensors reading high in direct sun. Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)
- A Medium piece checked the wallet behind a viral "$88K weather bot". It found about $88,000 in total profit, but not a clean money machine. The biggest single win was a Paris 19°C bet bought at about 5c. (2026; page blocked, from search summary.) Source: [Medium, Mountain Movers](https://medium.com/mountain-movers/inside-the-data-behind-polymarkets-viral-88k-weather-prediction-trading-strategy-and-results-2e65a8389f37)
- Other named "legends" (gopfan2 "over $2 million", neobrother "over $20,000", WeatherHK "$15,600 in a month") come only from low-quality blogs and guides. Treat them as unverified. Source: [Medium, moonsat](https://moonsat.medium.com/top-5-weather-market-legends-on-polymarket-and-their-winning-strategies-173d79b9d082)

**Market size and depth**
- Kalshi weather volume was $564 million through July 2026. That is already more than all of 2025 (WSJ, as quoted secondhand). Source: [Webull news](https://www.webull.ca/news-detail/15475678967514112)
- Kalshi says weather and climate volume is up about 500% from a year earlier, heading to about $1.1 billion a year (company figure, 2026). [SELF] Source: [Webull news](https://www.webull.ca/news-detail/15475678967514112)
- The January 2026 snowstorm contract traded over $6 million on Kalshi, one of its biggest weather markets ever. Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)
- One NYC daily high (13 Jul 2026) traded about $22K in total across its six price ranges (third-party data site). Source: [SimpleFunctions](https://simplefunctions.dev/markets/will-the-high-temp-in-nyc-be-89-on-jul-13-2026-kalshi-kxhighny-26jul13-t89)
- Monthly rain markets are smaller. NYC May 2026 "above 3 inches" had about $3K volume, $2K on the book and a 2c spread. Whole-month families for Denver, Seattle and Austin traded about $500-$800 each (May-Jun 2026 snapshots). Source: [SimpleFunctions](https://simplefunctions.dev/markets/rain-in-nyc-in-may-2026-above-3-inches-kalshi-kxrainnycm-26may-3)
- Trading clusters in the 2-3 most likely ranges. 5.9% of contracts never traded at all, mostly unlikely ranges. Weekday volume is 2-3 times weekend volume. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Interactive Brokers' chairman said temperature contracts are its most-traded event contracts (2026). Source: [KuCoin News](https://www.kucoin.com/news/flash/traders-on-polymarket-earn-millions-by-predicting-weather)

**Settlement quirks**
- Kalshi daily high and low markets settle on the NWS final climate report, usually out the next morning. Source: [Kalshi Help](https://help.kalshi.com/markets/popular-markets/weather-markets)
- The NWS report uses local *standard* time all year. So during daylight saving time the "day" runs from 1:00 AM to 12:59 AM the next day on the clock. Source: [Kalshi Help](https://help.kalshi.com/markets/popular-markets/weather-markets)
- Kalshi can delay settlement if the high does not match the 6-hour or 24-hour highs in the airport weather reports (METAR), or if the final report is lower than an earlier draft. Source: [Kalshi Help](https://help.kalshi.com/markets/popular-markets/weather-markets)
- A forecast for the city centre can be about 1°F off the settlement station. Prices are in whole degrees, so 1°F can flip the winner. [SELLS] Source: [BotForKalshi](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy)
- In 46,248 checks, the NWS climate report differed from the NOAA reference dataset only 46 times, all by 1°F or less (99.9% agree). Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Polymarket weather markets settle on Weather Underground history pages for a named airport station, for example London City (EGLC) or LaGuardia (KLGA). They use whole degrees. Some wait for "finalized" data. Others count revisions only until the next day's first reading posts. (Market mirror site, 2026.) Source: [Polyguana](https://polyguana.com/market/2336780)

**Calibration research**
- A study of 210,608 Kalshi contracts (to 31 Dec 2025) found weather prices are too sure in the last hours. The calibration slope was 0.69 in the final hour (below 1 = prices too extreme). Beyond about a week, prices become too timid (slope 1.20-1.37). Source: [Le, arXiv 2602.19520 (Feb 2026)](https://arxiv.org/html/2602.19520v1)
- Interactive Brokers' Patrick Brown claimed market-based forecasts beat the National Weather Service (2026). This is an interested party; no method shown in the article. [SELF] Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)

### Inferences
- Public NWS and GFS data is not an edge by itself. Many bots read the same data and reprice within seconds. A slow model is the one getting picked off (adverse selection).
- The only edges with any support are small: selling unlikely ranges as a maker (about 6% return in one backtest), using your own error data instead of a bell curve, and knowing the station quirks.
- The Le study's finding (prices too extreme in the last hour) points the same way: sell the confident-but-wrong last-hour prices. This has not been tested as a trading rule.
- The Polymarket wins are real but tiny in total. Even the top account earned in the tens of thousands to low millions, and the biggest wins look like lucky cheap bets, not steady model profit.
- This matches the project's own 16 Oct 2026 depth check: Kalshi temperature had only about $50 at the ask, against $1.5K+ for gas.

### Gaps
- No audited trading record from any weather model trader. All profit numbers are self-reported or wallet-based.
- No public test using ECMWF or HRRR (other major weather models). Only GFS, NAM and NOAA blends were tested.
- No order-book depth figures per Kalshi city. Only total volume per day was found.
- No reported Polymarket disputes over Weather Underground stations were found.

---

## Sports: Kalshi and Polymarket vs sharp sportsbooks (Pinnacle, Circa, Betfair). Is copying the sharp line profitable? How efficient are prediction-market sports prices? How much of Kalshi is sports?

### Takeaway
Sports is most of the money on Kalshi: 80% of volume from Jul 2024 to Apr 2026 (Pew). Kalshi and Polymarket prices sit within about 1 point of Pinnacle's fair price, and their margins are a quarter of Pinnacle's (Oct 2026). Copying the sharp line has a small, fast-closing gap. The two public bots that tried it made about $5K and then stopped, or found no edge.

### Cited findings

**How big sports is**
- Pew Research (27 May 2026): sports was 80% of Kalshi trading volume from July 2024 to April 2026. On Polymarket it was 39%. Source: [Pew Research](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/)
- Pew Research (23 Sep 2026): Kalshi plus Polymarket volume doubled from May to July 2026, reaching $53 billion a month. Sports topped $58 billion on Kalshi across June-July 2026 (World Cup). From Pew's July table, sports was about 78% of Kalshi ($31.4B of $40.1B) and 82% of Polymarket. Source: [Pew Research](https://www.pewresearch.org/short-reads/2026/09/23/prediction-markets-trading-volume-doubled-between-may-and-july-largely-driven-by-sports/)
- The share depends on what counts as sports. Kalshi's CEO said sports was 53% for the week of 8 Jun 2026, but that leaves out combo bets ("Exotics"). With combos, lifetime share is about 85%. Source: [Next Event Horizon](https://nexteventhorizon.substack.com/p/is-sports-now-only-70-percent-of-kalshi-volume)
- Kalshi's general counsel said in May 2026 that about 70% of volume is sports. Source: [Next Event Horizon](https://nexteventhorizon.substack.com/p/is-sports-now-only-70-percent-of-kalshi-volume)

**How close prices are to sharp books**
- OddsPapi snapshot of 88 games (13 Oct 2026) [SELLS: an odds API]. The table shows each venue's built-in margin and how far its price sits from Pinnacle's fair price. Source: [OddsPapi](https://oddspapi.io/blog/polymarket-api-kalshi-api-vs-sportsbooks-the-developers-guide/)

| Venue | Built-in margin (median overround: how much the prices add up past 100%) | Gap from Pinnacle's de-vigged fair price (median, in percentage points) | Money on the thinner side at the best price (median) |
|---|---|---|---|
| Polymarket | 1.00% | 0.59 points | $221 |
| Kalshi | 1.02% | 0.75 points | $501 ($13,067 for NFL) |
| Pinnacle | 4.02% | (the benchmark) | $758 ($6,000 for NFL) |
| bet365 | 6.70% | 0.83 points | not given |

- Polymarket US quotes showed $0 fillable size in that snapshot. Source: [OddsPapi](https://oddspapi.io/blog/polymarket-api-kalshi-api-vs-sportsbooks-the-developers-guide/)
- OddsPapi (1 Oct 2026) found 42 price gaps between Polymarket and sportsbooks across 16 games. The median gap was 0.44%. The best was 1.53%. [SELLS] Source: [OddsPapi](https://oddspapi.io/blog/polymarket-arbitrage-local-bookmakers/)
- A Citizens equity analyst said Polymarket had the best price on all 104 World Cup games, with an average built-in margin of 2.7% (2026). Source: [Casino.org](https://www.casino.org/news/polymaket-leads-world-cup-pricing-as-prediction-markets-account-for-27-of-sports-betting/)
- SmartStake claims Kalshi had the sharpest MLB player-prop prices, ahead of Pinnacle, across 600 million line moves. Method not shown. [SELLS] Source: [SmartStake](https://www.smartstake.app/learn/kalshi-vs-sportsbook)

**Calibration research**
- Kalshi sports prices are close to well calibrated from 1 hour to 1 week before the end (calibration slope 0.90-1.08). Only contracts more than a month out are clearly too timid (slope 1.74). Polymarket sports averaged 1.08. Big and small trades showed no real gap. (210,608 Kalshi contracts to 31 Dec 2025.) Source: [Le, arXiv 2602.19520 (Feb 2026)](https://arxiv.org/html/2602.19520v1)
- Blockworks: across 3,100 Kalshi games and $8.5B traded, implied chances were off by 5.5% two days before games (2026; metric not fully defined). Source: [Blockworks](https://app.blockworks.com/report/from-betting-to-trading-how-kalshi-is-reshaping-sports-markets)
- A separate paper finds sportsbook markets themselves are efficient. No odds-only strategy gave long-run profit that was clearly better than luck. Source: [American Journal of Management](https://articlegateway.com/index.php/AJM/article/view/6051)

**Public attempts to copy the sharp line**
- polymm (GitHub, early 2026): a Polymarket sports bot that took de-vigged sportsbook odds as fair value. It posted orders 1c above the best bid where its edge was over 5%, then tried to buy the other side for a locked profit. Result: +$8,293 from the locked trades, −$3,184 from failed hedges, about $5K net. It stopped because it "got too slow" and faster bots picked off its orders (adverse selection). Source: [GitHub kachence/polymm](https://github.com/kachence/polymm)
- nhl-edge (GitHub, review dated 23 Oct 2026): a hobby NHL project using Pinnacle as fair value for Kalshi. Its past CLV was −1.23% (95% CI: −2.01% to −0.46%). That means it got worse prices than the close. A shadow test placed 102 resting bids and only 8 filled. Its own conclusion: "no tradable edge is established". Real money is planned for 16 Nov 2026 on a €100 bankroll. Source: [GitHub HeikkiMatias/nhl-edge #317](https://github.com/HeikkiMatias/nhl-edge/issues/317)
- Same project: the taker fee is $1.75 on 100 contracts at 50c. To clear a 2.5% hurdle it needs about a 53.0% win chance at the taker fee, or 51.7% at the maker fee. Source: [GitHub HeikkiMatias/nhl-edge #317](https://github.com/HeikkiMatias/nhl-edge/issues/317)
- A news site said a sports bot made $8 million in two months on Polymarket by trading on the delay between real events and prices (early 2026). The wallet was not checked. Treat as unconfirmed. Source: [Phemex News](https://phemex.com/news/article/sports-bot-earns-8-million-on-polymarket-by-exploiting-time-lag-55871)

**Who provides the prices**
- Kalshi signed its first big outside market maker, Susquehanna (SIG), in April 2024 **(older)**. Source: [Business Wire](https://www.businesswire.com/news/home/20240403664852/en/Kalshi-Onboards-Its-First-Dedicated-Institutional-Market-Maker)
- SIG is widely seen as Kalshi's main market maker. A Kalshi co-founder said Kalshi's own trading arm is "not profitable". Lawsuits in several states name SIG (2026). Sources: [InGame](https://www.ingame.com/kalshi-in-house-trading-arm-not-profitable/); [iGaming Business](https://igamingbusiness.com/sports-betting/class-action-suit-against-kalshi-market-makers/)

### Inferences
- The gap between Kalshi and Pinnacle is usually smaller than Kalshi's taker fee near 50c (about 1.75c a contract). So copying Pinnacle as a taker loses money on most games.
- Any copy-the-line profit comes from speed and from posting orders (maker), not from the model. Both public bots learned this.
- The big claimed sports profits (the $8M bot) come from reacting to live events faster, not from forecasting. That is a speed race against firms like SIG.
- NFL has real depth on Kalshi ($13K at the best price in one snapshot). Most other sports are a few hundred dollars.

### Gaps
- No peer-reviewed study tests Kalshi sports prices against Pinnacle's closing price.
- No data on whether Kalshi leads or follows sportsbooks on price moves.
- Nothing found on Circa or Betfair vs Kalshi specifically.
- No audited record of any sharp-copy trader on Kalshi.

---

## Economic data: CPI, jobs, Fed rate, GDP markets. Do nowcasts (Cleveland Fed inflation nowcast, CME FedWatch) beat Kalshi prices?

### Takeaway
No. The best evidence goes the other way. A Federal Reserve staff paper (Feb 2026) found Kalshi's headline CPI forecast beat the Wall Street consensus, and its Fed-rate forecast matched or beat futures. No one has published a test showing that trading against Kalshi with the Cleveland Fed nowcast or FedWatch makes money.

### Cited findings
- Federal Reserve staff paper "Kalshi and the Rise of Macro Markets" (Diercks, Katz and Wright, FEDS 2026-010, Feb 2026). It calls Kalshi a high-frequency benchmark useful to researchers and policymakers. It is not peer-reviewed and does not speak for the Fed board. Source: [Federal Reserve](https://www.federalreserve.gov/econres/feds/kalshi-and-the-rise-of-macro-markets.htm)
- Same paper, as summarized by news sites: Kalshi's headline CPI forecast beat the Bloomberg consensus by a margin the authors call statistically significant (not just luck). Average miss: 0.063 points for Kalshi vs 0.081 for Bloomberg. The PDF could not be opened to check. Sources: [Digital Today](https://www.digitaltoday.co.kr/cn/view/28372/kalshi-prediction-market-outperforms-traditional-models-on-rate-forecasts-fed-paper-finds); [Cryptopolitan](https://www.cryptopolitan.com/study-finds-kalshi-predictions-reliable/)
- Same paper: for core CPI and unemployment, Kalshi matched the professionals, with almost the same miss size. Source: [Cryptopolitan](https://www.cryptopolitan.com/study-finds-kalshi-predictions-reliable/)
- Same paper: on Fed rate decisions, Kalshi was as accurate as fed funds futures and sometimes "slightly better" (no figures in the news write-ups). Bloomberg's headline (28 Jan 2026): Kalshi Fed forecasts "are as good as Wall Street's". Three meetings ahead, Kalshi's miss size was very similar to professional forecasters. Sources: [Bloomberg](https://www.bloomberg.com/news/articles/2026-01-28/kalshi-fed-forecasts-are-as-good-as-wall-street-s-study-says); [DeFi Rate](https://defirate.com/news/federal-reserve-study-finds-kalshi-markets-rival-traditional-economic-forecast-tools/)
- Kalshi's own research says its CPI forecasts had a 40.1% smaller average miss than consensus from Feb 2023 to mid-2025. It says Kalshi was right 75% of the time when it disagreed with consensus. [SELF] Source: [Casino.org](https://www.casino.org/news/want-an-accurate-inflation-forecast-kalshi-says-it-beats-wall-street/)
- An older Kalshi post (2023) said its median CPI forecast beat the Bloomberg survey. Its own table showed the Cleveland Fed at 0.42% and Kalshi at 0.20% for a June print that came in at 0.20%. [SELF] **(older)**. Source: [Kalshi News](https://news.kalshi.com/p/kalshi-smashes-other-cpi-forecasts)
- Single months go both ways. July 2026: Kalshi priced 3.3% headline and 2.4% core, one tick under the Cleveland Fed's 3.4% and 2.5%. September 2026: the Cleveland Fed said +0.5% for the month; Kalshi's favourite was 0.6%, which was the actual print. (From search summaries; pages not opened.) Sources: [Kalshi Research](https://kalshi.com/research/insights/july-cpi-preview); [Lucidate](https://lucidate.substack.com/p/twelve-seconds-after-the-inflation)
- Nowflation's scoreboard puts the Cleveland Fed's average headline CPI miss at 0.101 points over 42 prints. It grades only one Kalshi print, so no fair comparison. [Nowflation competes as a forecaster.] Source: [Nowflation](https://nowflation.com/scoreboard)
- A Substack critic argues the Cleveland Fed nowcast is often wrong and gives months where Kalshi was closer. Small sample. Source: [Macro Models](https://macromodels.substack.com/p/reliably-bad-reliable-sources)
- The Cleveland Fed's own studies say its nowcast beats other statistical models. They do not compare it with Kalshi **(older, 2023-2024)**. Source: [Cleveland Fed](https://www.clevelandfed.org/publications/economic-commentary/2023/ec-202306-real-time-assessment-inflation-nowcasting-cleveland-fed)
- Dune (2026 meetings): Kalshi and Polymarket priced "no change" higher than CME FedWatch from about 3 months out. The gap grew with time to the meeting. Kalshi's Fed contracts traded about $12M, against hundreds of billions a day in fed funds futures. Source: [Dune (search summary; page later 404)](https://dune.com/blog/pricing-the-fed-kalshi-polymarket-cme-fedwatch)
- Semafor (6 Aug 2026): Kalshi Fed markets scored a Brier score of 0.02 just before close (very accurate). Before one 2026 meeting, Kalshi gave a hold up to 10 points more than futures did. The Fed held. [SELF: Kalshi-supplied data]. Source: [Semafor](https://semafor.com/article/08/06/2026/kalshi-banks-on-its-predictions-accuracy)
- A Kalshi study of 300,000+ contracts found a favourite-longshot bias. The authors say Kalshi prices "should not be interpreted as unbiased probability estimates" (2025-2026). Source: [CEPR DP20631](https://cepr.org/publications/dp20631)

### Inferences
- The nowcasts are public and Kalshi traders already watch them. So a nowcast is a starting point that is already in the price, not an edge.
- Fed-rate contracts are tiny next to fed funds futures. Anyone with a better Fed view uses futures, so Kalshi Fed prices likely just follow futures plus a small "no change" tilt.
- Any economic-data edge would need private data (card spending, gas prices, web prices) or speed at the release moment. No public trader shows profit from this.

### Gaps
- Could not read the Fed paper's PDF. Its exact sample period and tests are unconfirmed.
- No published backtest found of trading Kalshi CPI contracts against the Cleveland Fed nowcast (searched 25 Oct 2026). So there are no profit figures for the "nowcast vs Kalshi" strategy.
- No track record found for Kalshi jobs (payrolls) contracts vs consensus. Searches returned only copied spam pages.
- No head-to-head of Kalshi vs nowcasts on payrolls or GDP.
- No depth figures for CPI or jobs contracts at each strike.

---

## Elections and politics: did poll-aggregation models (Silver Bulletin, 538, The Economist) beat market prices historically? PredictIt studies, and 2020, 2022, 2024.

### Takeaway
Mixed, and it moved toward the markets. Models did a bit better than PredictIt in 2020-2022 Senate races. But in 2024 all models lost money traded against the market on the presidential race (Sethi et al.). Politics is now a tiny share of Kalshi volume: 0.4% in July 2026.

### Cited findings

**The "profit test": treat a model as a trader**
- Sethi and co-authors scored models by how much money a trader who believed the model would make against PredictIt. Data: The Economist, 538 and PredictIt, 2020 president and 2020/2022 Congress (ACM Collective Intelligence 2024). Sources: [MIT DSpace](https://dspace.mit.edu/handle/1721.1/155928); [Barnard](https://barnard.edu/news/professor-rajiv-sethi-and-barnard-affiliates-publish-new-research-collective-intelligence)
- An earlier version (2021) found the model made a "modest profit" in 2020 battleground states **(older)**. Source: [arXiv 2102.04936](https://arxiv.org/abs/2102.04936)
- Brier scores from that line of work (lower is better; summary of the ACM paper): **(older, 2020-2022)**. Source: [ACM via search summary](https://dl.acm.org/doi/fullHtml/10.1145/3643562.3672612)

| Race | The Economist | FiveThirtyEight | PredictIt (market) |
|---|---|---|---|
| 2020 president | 0.1450 (best) | 0.1540 | 0.1517 |
| 2020 House | not given | 0.3459 | 0.3335 (market better) |
| 2020 Senate | not given | 0.2196 (model better) | 0.2761 |
| 2022 Senate | not given | 0.1772 (model better) | 0.2276 |

- 2024: Sethi's 22 Oct 2024 update gave Trump win chances of 51% (538), 53% (Silver Bulletin), 54% (Economist), 56% (PredictIt), 59% (Kalshi), 64% (Polymarket). **(older)**. Source: [Sethi Substack](https://rajivsethi.substack.com/p/forecasting-mechanisms-another-update)
- Sethi's election-day update (5 Nov 2024) said that if Trump won, every model would lose roughly 10% on Polymarket. Trump won. **(older)**. Source: [Sethi Substack](https://rajivsethi.substack.com/p/an-election-day-update-on-forecasting)
- Final paper ("Political Prediction and the Wisdom of Crowds", ACM CI 2025): all models failed to beat the market on the headline presidential contract. Some beat it "convincingly" on less-watched races. Sources: [Barnard](https://barnard.edu/news/professor-rajiv-sethi-publishes-new-research-political-prediction-and-collective-intelligence); [Columbia stat blog](https://statmodeling.stat.columbia.edu/2025/06/17/political-prediction-and-the-wisdom-of-crowds-evaluating-an-election-forecast-over-time-by-comparing-to-betting-odds-over-time/)
- Silver joined Polymarket's advisory board in July 2024. His Silver Bulletin model was the least profitable in Sethi's tests. [Conflict of interest noted.] **(older)**. Sources: [PR Newswire](https://prnewswire.co.uk/news-releases/nate-silver-joins-polymarket-ahead-of-2024-election-as-trading-volume-tops-400m-302198438.html); [Sethi Substack](https://rajivsethi.substack.com/p/an-election-day-update-on-forecasting)

**2022 Senate, many venues (Bransfield, Dec 2022) (older)**
- Six close races: Metaculus 0.1658, Economist 0.1761, 538 0.1930, Polymarket 0.2356, PredictIt 0.2513 (Brier scores, lower is better). Every venue missed Nevada. All the betting venues also missed Georgia and Pennsylvania. Source: [Bransfield](https://mickbransfield.com/2022/12/18/did-bookmakers-prediction-markets-fare-that-badly-in-the-2022-senate-races/)
- His conclusion: markets did about as well as, or a little worse than, the models. Models scored better mostly because they were more confident when right, not because they picked more winners. Source: [Bransfield](https://mickbransfield.com/2022/12/18/did-bookmakers-prediction-markets-fare-that-badly-in-the-2022-senate-races/)

**2024 and after**
- A 2025 arXiv study found Polymarket beat polls on the 2024 presidential result, especially in swing states. Source: [arXiv 2507.08921](https://arxiv.org/html/2507.08921)
- An Undark article (May 2026, cited by the Israel Democracy Institute) found Polymarket picked the winner but did not clearly beat the statistical models on vote shares. It did poorly in thin congressional markets. Source: [Israel Democracy Institute](https://en.idi.org.il/articles/66410)
- Clinton and Huang (2025), as cited: PredictIt beat both Kalshi and Polymarket in 2024 despite much less money and tight caps. Source: [arXiv 2604.24147](https://arxiv.org/pdf/2604.24147)
- The biggest 2024 political winner was not a model trader. "Théo" (Fredi9999) made about $78.7M net by Chainalysis's count (others say $47M). He used "who are your neighbours voting for?" polls and paid for his own poll (WSJ, as reported). **(older)**. Sources: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban); [Cointelegraph](https://cointelegraph.com/news/polymarket-french-whale-donald-trump-election-odds)

**PredictIt frictions (why old markets were easy to beat on paper)**
- PredictIt capped each trader at $850 per contract. The sum of prices across outcomes often stayed above 110c, which means guaranteed profit even after fees, yet traders could not fix it (Zitzewitz, NBER w35845, Oct 2026). Source: [NBER](https://www.nber.org/papers/w35845)
- PredictIt charged 10% of profits and 5% on withdrawals **(older blog)**. Source: [LessWrong](https://www.lesswrong.com/posts/c3iQryHA4tnAvPZEv/limits-of-current-us-prediction-markets-predictit-case-study)
- After the 2020 election was called, PredictIt still gave Trump about 9% to be the next president. Weeks later you could still buy Biden for a few cents' profit **(older)**. Sources: [Astral Codex Ten](https://www.astralcodexten.com/p/congrats-to-polymarket-but-i-still); [Asterisk](https://asteriskmag.com/issues/05/prediction-markets-have-an-elections-problem-jeremiah-johnson)
- Before the 2020 vote, PredictIt priced Biden near 65% while models had him at 87-92% **(older)**. Source: [Jorge Velez Substack](https://jorgevelez.substack.com/p/severe-dislocation-between-prediction)

**Calibration research (politics)**
- Kalshi political prices are too timid at nearly every horizon. Prices sit too close to 50c (calibration slope 1.3-1.8). This is strongest for large trades. The gap between large and single trades was +0.53 (95% CI: 0.29 to 0.75). Polymarket politics was also timid (slope 1.31). (Data to 31 Dec 2025.) Source: [Le, arXiv 2602.19520 (Feb 2026)](https://arxiv.org/html/2602.19520v1)

**Size now**
- Politics was 4% of Kalshi volume and 32% of Polymarket volume (Jul 2024-Apr 2026). In July 2026 it was only 0.4% of Kalshi and 5.6% of Polymarket (computed from Pew's table). Sources: [Pew May 2026](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/); [Pew Sep 2026](https://www.pewresearch.org/short-reads/2026/09/23/prediction-markets-trading-volume-doubled-between-may-and-july-largely-driven-by-sports/)

### Inferences
- Polling models beat old PredictIt mostly because PredictIt's caps and fees kept smart money out. Those limits are gone on Kalshi and Polymarket, so the old wins don't carry over.
- In 2024 the market knew something the models didn't (polling error toward Trump). Model traders lost.
- Where models still help: low-attention races (House, state races) and long horizons, where prices are too timid. But those are the thinnest markets.
- Elections are rare. One cycle every two years is too few bets to prove an edge.

### Gaps
- No public test of Silver Bulletin or The Economist vs Kalshi prices for 2024 down-ballot races.
- Could not read the full ACM papers. The Brier table comes from a search summary.
- No 2026 midterm results yet (election is 3 Nov 2026).

---

## Other categories: box office, music charts, entertainment, gas prices, "mention" markets

### Takeaway
Very little hard evidence. These markets are small, and the edges people describe come from insider or near-insider information (early reviews, prepared remarks) more than from models. Gas prices are the one category with a clean public data source (AAA) and decent depth.

### Cited findings
- Kalshi Rotten Tomatoes markets often reach about $1 million in volume, and about $2 million for big releases. One Spider-Man title showed about $1.7 million (2025-2026). Sources: [The Ankler](https://theankler.com/kalshi-tarek-mansour-entertainment-markets-netflix-oscars/); [Kalshi culture page](https://kalshi.com/category/culture)
- The only trader result found for Rotten Tomatoes: one trader won about $3,000 betting a film would review badly (anecdote). Source: [The Ankler (via search summary)](https://theankler.com/p/gamblers-prediction-markets-entertainment-rotten-tomatoes-box-office-polymarket)
- The Ankler (9 Sep 2024) reported "gamblers are making big money" on release dates, Rotten Tomatoes scores and box office. The details are paywalled **(older)**. Source: [The Ankler](https://theankler.com/p/gamblers-prediction-markets-entertainment-rotten-tomatoes-box-office-polymarket)
- Kalshi entertainment prices are too sure at short horizons (calibration slope 0.81 in the last hour; average bias −0.085). Data to 31 Dec 2025. Source: [Le, arXiv 2602.19520 (Feb 2026)](https://arxiv.org/html/2602.19520v1)
- Mention markets pay if a CEO or speaker says a word. They usually settle on the official transcript within 24 hours. Whether "headwinds" counts for "headwind" depends on each contract's rules. Source: [DeFi Rate](https://defirate.com/odds/mention-markets/)
- DraftKings' CEO warned that company insiders, or anyone who has seen the prepared remarks, would have a big edge in earnings-call mention markets (2026). Source: [Crypto Briefing](https://cryptobriefing.com/draftkings-ceo-prediction-market-earnings-calls/)
- Guides say the tradable pattern is a speaker's habit words, found in past transcripts. No profit figures found. Source: [StockAlarm](https://pro.stockalarm.io/blog/kalshi-earnings-call-markets-ai-analysis)
- Kalshi gas markets settle on AAA's national (or state) average for a set day. One May 2026 trader piece argued a strike was overpriced because gas was already $4.49 and AAA's average moves slowly. One trader's opinion. Source: [Action Network](https://www.actionnetwork.com/prediction-markets/american-gas-prices-crash-stand-kalshi-prediction-market)
- Some long-dated gas markets are empty: one had zero 24-hour volume and $320 open interest (2026 snapshot). Source: [SimpleFunctions](https://simplefunctions.dev/markets/KXAAAGASMAXCA-26DEC31-6.60)
- Spotify and music-chart markets: no profit or depth data found.

### Inferences
- Entertainment and mention markets reward information more than models. Insider risk is high, so a model trader may be the one picked off (adverse selection).
- Gas has a slow-moving public number (AAA's daily average). That is friendly to a simple model. This matches the project's own work: hourly and daily gas passed fresh October 2026 data at about +1c/$1 (about 1 cent of profit for every dollar bet), with $1.5K+ at the ask.

### Gaps
- No documented profitable model trader in box office, music charts or mentions.
- No depth figures for Rotten Tomatoes or mention markets.

---

## Who wins: individuals or firms? What data and compute are needed? How big can these strategies get before they move prices?

### Takeaway
Firms and fast market makers take most of the money. On Polymarket the top 1% of accounts captured 76.5% of all gains, mostly by posting orders (Akey et al., 2026). Individuals win in thin niches like weather, but those niches hold only tens of thousands of dollars a day. The data is mostly free. Speed and posting orders are what cost money and effort.

### Cited findings
- Polymarket study (Akey and co-authors, 588 million trades, $67B volume, Nov 2022-Mar 2026): the top 1% of users captured 76.5% of gains. 69% of accounts lost money. Winners mostly posted limit orders (makers). Losers mostly hit existing prices (takers). Sources: [HEC Paris seminar](https://www.hec.edu/en/faculty-research/events/who-wins-and-who-loses-prediction-markets-evidence-polymarket); [Coin360 summary](https://coin360.com/news/polymarket-traders-losses-profit-concentration-2026-predictions)
- Same study: monthly winners only weakly stay winners. That may be selection, not skill. Insider trading does not explain the biggest winners. Source: [HEC Paris seminar](https://www.hec.edu/en/faculty-research/events/who-wins-and-who-loses-prediction-markets-evidence-polymarket)
- Fewer than 0.04% of Polymarket wallets took over 70% ($3.7 billion) of realized profit (DeFi Oasis, Dec 2025). Source: [Digital Today](https://www.digitaltoday.co.kr/en/view/49006/polymarket-traders-84-percent-lose-money-in-prediction-market)
- 0.55% of profitable maker wallets took 50% of profit, Dec 2025-Feb 2026 (Solidus Labs, Mar 2026). Source: [Coin360 summary](https://coin360.com/news/polymarket-traders-losses-profit-concentration-2026-predictions)
- Bloomberg: without the top winners, all other Polymarket users since early 2025 lost $131 million combined. Source: [Finance Magnates](https://www.financemagnates.com/fintech/100000-polymarket-wallets-lost-at-least-1000-bloomberg-analysis-shows/)
- Kalshi (Bürgi, Deng and Whelan, 300,000+ contracts, revised Jan-Feb 2026): takers lost almost 32% on average and makers about 10% (as summarized; PDF not readable). Buyers of contracts under 10c lost over 60%. Sources: [CEPR DP20631](https://cepr.org/publications/dp20631); [ifo/CESifo](https://www.ifo.de/en/cesifo/publications/2026/working-paper/makers-and-takers-economics-kalshi-prediction-market)
- SIG trades only where it can put the most money to work, such as NFL Sunday Night Football (2026). Source: [InGame](https://www.ingame.com/?p=38546)
- Jua's CEO: weather returns are high but too thin for a big fund (Apr 2026). Source: [Claims Journal (Bloomberg)](https://www.claimsjournal.com/news/national/2026/04/15/336839.htm)

**Data and compute**
- Weather data is free: NOAA/NWS forecasts, the National Blend of Models, and the 31-run GFS ensemble via Open-Meteo. Sources: [GitHub suislanchez](https://github.com/suislanchez/polymarket-kalshi-weather-bot); [Predict & Profit](https://predictandprofit.io/)
- Speed is the cost. In weather, bots reprice within seconds of NWS model updates (Feb 2026). Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Sports odds data is cheap: The Odds API's free tier gives five snapshots a day; paid plans start at $30 a month (Oct 2026). Source: [GitHub HeikkiMatias/nhl-edge #317](https://github.com/HeikkiMatias/nhl-edge/issues/317)
- But fresh odds and fast execution were the real edge for polymm. Its private, faster odds scraper is the part it did not publish (2026). Source: [GitHub kachence/polymm](https://github.com/kachence/polymm)

**How big it can get**
- NYC daily high: about $22K total per day across all ranges (Jul 2026). Source: [SimpleFunctions](https://simplefunctions.dev/markets/will-the-high-temp-in-nyc-be-89-on-jul-13-2026-kalshi-kxhighny-26jul13-t89)
- Sports, at the best price: Kalshi median $501, NFL $13,067 (13 Oct 2026). Source: [OddsPapi](https://oddspapi.io/blog/polymarket-api-kalshi-api-vs-sportsbooks-the-developers-guide/)
- Fed rate contracts: about $12M traded across 2026 meetings, against hundreds of billions a day in futures. Source: [Dune (search summary)](https://dune.com/blog/pricing-the-fed-kalshi-polymarket-cme-fedwatch)
- Rotten Tomatoes: about $1-2M per film. Source: [The Ankler](https://theankler.com/kalshi-tarek-mansour-entertainment-markets-netflix-oscars/)

### Inferences
- A solo trader's realistic place is a thin niche (weather, gas, small races) at small size. Those niches cap profit at small amounts.
- The deep markets (NFL, Fed) are where firms like SIG already sit, and the prices there are the hardest to beat.
- Posting orders (maker) beats hitting prices (taker) in every dataset found. A model that only takes prices starts behind.

### Gaps
- No split of Kalshi profits by category or by trader type.
- No public figures for SIG's or other firms' Kalshi profits.

---

## Is the edge fading (2023 to 2026)?

### Takeaway
Yes, by every sign found. The favourite-longshot bias on Kalshi was weaker in 2025 data. The public bots that worked in early 2026 stopped working. Careful 2026 weather tests find no edge after fees. The easy wins people remember (PredictIt 2020) came from caps and fees that no longer apply.

### Cited findings
- Kalshi's favourite-longshot bias looks weaker in 2025: the bias measure was smaller and less clearly different from zero than in earlier years (Bürgi, Deng and Whelan, revised 2026). Sources: [CEPR DP20631](https://cepr.org/publications/dp20631); [Karl Whelan](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- polymm's sports bot made money for a few months in early 2026, then stopped because faster bots arrived. Source: [GitHub kachence/polymm](https://github.com/kachence/polymm)
- OddsReference (Jul 2026 update): weather markets are efficient, no edge after fees. Source: [OddsReference](https://oddsreference.com/predictions/research/kalshi-weather-model)
- Weather bots now reprice within seconds of NWS updates (Feb 2026). Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Weather volume grew about 500% in a year (2026, company figure). More money brings more and faster traders. [SELF] Source: [Webull news](https://www.webull.ca/news-detail/15475678967514112)
- Sports price gaps vs sportsbooks were small by Oct 2026: median 0.44%, best 1.53%. [SELLS] Source: [OddsPapi](https://oddspapi.io/blog/polymarket-arbitrage-local-bookmakers/)
- Models made a "modest profit" against PredictIt in 2020 **(older)**, but all lost on the 2024 headline race. Sources: [arXiv 2102.04936](https://arxiv.org/abs/2102.04936); [Barnard](https://barnard.edu/news/professor-rajiv-sethi-publishes-new-research-political-prediction-and-collective-intelligence)
- 2020-era PredictIt mispricing was locked in by the $850 cap and 10% profit fee **(older)**. Sources: [NBER w35845](https://www.nber.org/papers/w35845); [LessWrong](https://www.lesswrong.com/posts/c3iQryHA4tnAvPZEv/limits-of-current-us-prediction-markets-predictit-case-study)
- One counter-sign: weather bot sellers still claim weather contracts are "consistently mispriced". These are sales pages. One vendor itself warns that a model-vs-market gap "is not proof of mispricing". [SELLS] Sources: [BotForKalshi](https://www.botforkalshi.com/blog/kalshi-weather-bot); [BotForKalshi tool](https://www.botforkalshi.com/tools/kalshi-weather-edge)

### Inferences
- The pattern is the same in every category. Early gaps get found, bots copy them, and the gap shrinks to about the size of the fee.
- What is left tends to be: posting orders instead of taking them, speed, private data, and markets too small for firms to bother with.

### Gaps
- No study tracks model-vs-market profit year by year for any one category on Kalshi.
- The Le calibration study does not test whether its patterns changed over time.
