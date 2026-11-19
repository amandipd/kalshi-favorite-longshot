# Which weather markets a forecast model could beat, and whether making beats taking (Kalshi first, Polymarket second)

Research date: Monday 26 Oct 2026. Every claim carries the date of its source.

How to read the tags:
- **[HARD]** = an academic paper or a large data study.
- **[PRIMARY]** = an official rule, doc or fee page, or a live public API read made on the research date.
- **[SELF-PUB]** = a backtest or live log that someone published about their own bot. Not audited.
- **[ANECDOTE]** = a screenshot, social post or news story about one trader.
- **[MARKETING]** = the source sells a tool, a course or a paid plan.
- **[SNIPPET]** = only a search summary was seen, not the page itself.

Plain words used throughout:
- **Maker** = you post a resting order and wait for someone to trade with it. **Taker** = you trade against an order that is already there.
- **Spread** = the gap between the buy and sell price. It is what it costs to get in.
- **Depth** = how much money you can trade before moving the price.
- **Adverse selection** = getting picked off by someone who knows more than you.
- **Taker fee** = Kalshi's charge for trading, biggest near 50c.
- **Favourite-longshot bias** = cheap unlikely bets are overpriced, heavy favourites underpriced.
- **Calibration** = whether a 70c price really wins 70% of the time.
- **Out-of-sample** = tested on data the rule never saw while being built.
- **LIP** = Kalshi's Liquidity Incentive Program. It pays people for keeping resting orders on the book.
- **LP program** = Kalshi's Liquidity Provider Program. It pays one or a few hand-picked firms per market family.

Live API reads made on the research date (a handful, with 3-second pauses):
- 6 series reads for fee type, 3 market-list reads, 1 order book, 1 daily-rain list, 2 pages of the incentive list. All public, no key. No other fetch was sharing Kalshi's rate limit at the time.
- 9 reads of Polymarket's public Gamma API (not Kalshi, so no shared rate limit).

---

## Q1. Efficiency by contract type: which weather markets get the least attention compared with how forecastable they are?

### Takeaway
Big-city daily highs are the hardest to beat. The market already forecasts better than the best free model, and every public forecast bot lost money there. The least-watched markets that still trade are **Kalshi daily lows** (thin, 6-18c spreads, yet paid the same LIP reward as highs) and **Polymarket international city highs** (London, Tokyo, Seoul; $40k-$90k per city-day, 3-7c spreads a day ahead). But no study tests either one. The only "edge" with numbers in a thin weather market (rain, NO side) shrank from about +11c to about +1c per contract within three months as volume grew.

### Cited findings

**Big-city daily highs (KXHIGH*): the most efficient**
- [HARD] Kalshi's daily-high prices miss the true high by about 10% less than the National Blend of Models (NBM, the Weather Service's best free mixed forecast). This holds already at the end of the market's first hour of trading. NBM drifts toward the market price over time, not the other way round. Paper dated 21 Sep 2026. Source: [Crosier, arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- [HARD] Same paper: the NYC market settles at Central Park, Chicago at Midway, Los Angeles at LAX, not downtown. Source: [Crosier, arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- [HARD] Kalshi's weather markets show a milder favourite-longshot bias than Kalshi overall (data 2021 to April 2025, before fees). The fitted line for profit per contract, in cents, is −0.997 + 0.031 × price for weather, against −1.736 + 0.034 × price for all of Kalshi. In plain words, weather longshots lose less than longshots elsewhere, and the break-even price is about 32c. Source: [Bürgi, Deng & Whelan, GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- [SELF-PUB] A public NYC daily-high market-making project fits calibration from quotes alone. It finds P(win) = σ(0.157 + 1.160 × logit p). That crosses fair at 27c: brackets under 27c win less often than priced, brackets over 27c win more often. In plain words, a mild favourite-longshot bias. The same repo says 33% (Oct-Mar) and 51% (Apr-Sep) of all price movement happens in the minutes right after the hourly airport report and the summary messages (":52, :53, :16, :17"). Undated README, Columbia APMA seminar, 2026. Source: [dfong03/apma2026-kalshi-weather](https://github.com/dfong03/apma2026-kalshi-weather)
- [SELF-PUB] Every public forecast-bot backtest of daily highs lost money after fees in 2026. Example: MiguelTheGamer (May-Oct 2026), "the market won every cell". jattree (Sep 2026) lost 13.9% per trade in simulation and 75% live. Already collected in this project's 25 Oct notes. Sources: [existing_bots_and_edge.md (project notes, 25 Oct 2026)](../Kalshi%20weather%20bot%20feasibility/existing_bots_and_edge.md); [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest); [jattree/weather-edge](https://github.com/jattree/weather-edge)
- [PRIMARY] This project's own desk test (26 Oct 2026): buying 90c+ daily-high favourites late in the day failed out of sample. 1,113 test bets lost 24.5 cents for every $10 bet. Source: project report `reports/Weather favourites test Oct 26.md`
- [PRIMARY] Live read, 26 Oct 2026 20:58 UTC. Tomorrow's NYC high (KXHIGHNY-26OCT27): the two live brackets were 37c bid / 38c ask and 57c / 58c, so a 1c spread. Only 25 contracts sat at the best YES bid. The top 8 price levels held about 830 contracts on the YES side and about 600 on the NO side. Each bracket had traded only 400-2,500 contracts so far. Sources: [Kalshi API, markets?event_ticker=KXHIGHNY-26OCT27](https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=KXHIGHNY-26OCT27&limit=20); [order book](https://api.elections.kalshi.com/trade-api/v2/markets/KXHIGHNY-26OCT27-B60.5/orderbook?depth=8)
- [PRIMARY] Same time, today's NYC high (almost decided): the busiest brackets were 0c/1c, 4c/7c and 93c/96c. That is a 3c spread on the brackets still in play. Busiest bracket: 53,000 contracts in 24 hours. Source: [Kalshi API, KXHIGHNY open markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)

**Daily rain (KXRAIN)**
- [PRIMARY] Live read, 26 Oct 2026 ~21:00 UTC: 70 open KXRAIN markets, 400,000 contracts traded in 24 hours. The busiest was Tampa (80,000 contracts, 13c/15c). Only 3 of the 70 had a bid between 15c and 85c. In plain words, most rain volume is in markets that are already nearly decided. Source: [Kalshi API, KXRAIN open markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)
- [SELF-PUB] An AI-agent account scanned 1,598 settled daily-rain markets (Aug-Oct 2026). It found YES was overpriced in the last ~13 hours before close. Buying NO looked like +5 to +9c per contract after fees. On 420 older markets (out-of-sample) it showed +11c. But the weekly edge fell from about +11c (July/August) to about +1c (last three weeks of October). Good candidates fell from 5-9 a day to about one a day "as volume grew". NYC-only (895 markets) and Seattle (347) showed zero or negative results. The effect seemed specific to the newer, thinner multi-city series. Source: [mirabilis-agent/lip-ledger CASE_STUDY.md (Oct 2026)](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/CASE_STUDY.md)
- [PRIMARY] This project's own rain test (26 Oct 2026) had too few bets to judge: 110 bets, +6.3c per $10 with a range of −18.4 to +30.9. Source: project report `reports/Weather favourites test Oct 26.md`

**Daily lows (KXLOWT*)**
- [PRIMARY] Live read, 26 Oct 2026: NYC low (KXLOWTNYC) busiest brackets traded 2,000-5,500 contracts in 24 hours, quoted 0c/2c and 98c/99c on a decided day. The 25 Oct scan found lows trade 1,000-18,000 contracts a day with 6-18c spreads. Sources: [Kalshi API, KXLOWTNYC open markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXLOWTNYC&status=open); the project's own scan (25 Oct 2026)
- [PRIMARY] Daily lows get the **same** LIP reward as daily highs: $20 per bracket, 6 brackets, so $120 per city-day (details in Q2). Source: [Kalshi API, incentive_programs (read 26 Oct 2026)](https://api.elections.kalshi.com/trade-api/v2/incentive_programs?status=active&limit=1000)
- [PRIMARY] Lows settle on The Weather Company, like highs. Source: [Kalshi API, series/KXLOWTNYC](https://api.elections.kalshi.com/trade-api/v2/series/KXLOWTNYC)
- [MARKETING] A paid "edge" add-on claims markets overreact to early-morning temperature drops. No backtest is shown. Source: [edge-assist addendum](https://edge-assist.duckdns.org/data-status/docs/weather/ruling/Weather%20Addendum%20%E2%80%94%20Extended%20Climate%20Markets)
- [SELF-PUB] A self-published practitioner's write-up on Kalshi weather warns that a model beating plain averages "does not guarantee positive EV at market prices". It says the practical edge is maker-side, fading overpriced longshot brackets. It also warns that 1c ask levels are often fake and that assuming you fill them over-credits profit "~23×". Source: a practitioner's write-up (not linked) [SNIPPET]

**Hourly temperature index markets (KXTEMP*H)**
- [PRIMARY] Live series read, 26 Oct 2026: KXTEMPMIAH ("Hourly Directional Miami Temperature") and KXTEMPNYCHS settle on Synoptic Data. Fee type "quadratic", multiplier 1 (taker-only fees, see Q2). Sources: [Kalshi API, series/KXTEMPMIAH](https://api.elections.kalshi.com/trade-api/v2/series/KXTEMPMIAH); [series/KXTEMPNYCHS](https://api.elections.kalshi.com/trade-api/v2/series/KXTEMPNYCHS)
- [SELF-PUB] How the index works (Oct 2026): it is the equal-weight average of one-minute ASOS (automated airport weather station) temperatures. NYC uses 8 stations, other cities 5. The data is free from Kalshi's own endpoint, with history from 28 Aug 2026. Readings reach Kalshi about 135-150 seconds after each minute. The settlement point posts 5 minutes after the minute. Because stations report whole °C, the index moves in steps of 0.225°F (NYC) or 0.36°F (5-station cities). The author replayed 4,100 settled markets and matched every result. Source: [lip-ledger WEATHER_INDEX.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/WEATHER_INDEX.md)
- [SELF-PUB] Same source: a first backtest of passive YES selling showed +9c per contract. It was wrong because it used prices from the end of the minute (lookahead, meaning it used information not yet known). A clean replay showed +5 to +14c on the first 99 fills (only at asks ≤ 65c). By 139 fills it was −0.1c per contract, with NO winning 64% of the time. Above about 65c "buyers appeared to be informed". Live day one: 64 fills, −1.8c per contract. Losses came in clusters by city-hour. The author's conclusion: when the venue publishes the settlement series, the edge is timing and queue position, not prediction. Sources: [lip-ledger WEATHER_INDEX.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/WEATHER_INDEX.md); [CASE_STUDY.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/CASE_STUDY.md)
- [PRIMARY] Live read, 26 Oct 2026: the in-play Miami hourly bracket (T80.99, closing 21:00 UTC) was 61c bid / 82c ask, a 21c spread, with 8,900 contracts traded in 24 hours. Source: [Kalshi API, KXTEMPMIAH open markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTEMPMIAH&status=open)
- [PRIMARY] This project's 18 Oct hourly-temperature test failed. Source: the project's own backtest (18 Oct 2026).

**Monthly rain and snow totals**
- [PRIMARY] Live series read, 26 Oct 2026: monthly NYC rain (KXRAINNYCM) settles on the NWS Climatological Report (Central Park), not The Weather Company. Taker-only fees. Source: [Kalshi API, series/KXRAINNYCM](https://api.elections.kalshi.com/trade-api/v2/series/KXRAINNYCM)
- [SNIPPET] Rules: total monthly rain at the named NWS station, using the first daily climate report that covers the whole month. Trace counts as zero. Liquidity examples (2026): Chicago Aug 2026 ">10 inches" 2c bid / 4c ask, about $6k for the whole family. Dallas Oct about $4,400 traded. NYC Oct about $18,000. Sources: [Kalshi KXRAINNYCM page](https://kalshi.com/markets/kxrainnycm/monthly-rain-in-new-york/kxrainnycm-26oct); [Kalshi KXRAINDALM page](https://kalshi.com/markets/kxraindalm/rain-dallas/kxraindalm-26oct); [simplefunctions Chicago Aug](https://simplefunctions.dev/markets/rain-in-chicago-in-aug-2026-kalshi-kxrainchim-26aug-10)
- [ANECDOTE] Snow spikes in storms. In the Jan 2026 NYC storm ("Fern"), NYC monthly snowfall contracts passed $720,000 in volume. Source: [PredictStreet via FinancialContent, 24 Jan 2026](https://markets.financialcontent.com/stocks/article/predictstreet-2026-1-24-traders-betting-on-snowmageddon-in-nyc-markets-price-in-major-accumulation-for-winter-storm-fern) [SNIPPET]

**Ski snowfall, heating degree days, weekly rain**
- [PRIMARY] The 25 Oct 2026 scan found ski-resort, storm and climate markets mostly trade under 5,000 contracts a day, with 20-98c spreads. Weekly average temperature and international city temperature series on Kalshi were closed. Source: the project's own scan (25 Oct 2026).
- [ANECDOTE] Kalshi and The Weather Company plan to "explore" ski-condition and marathon-weather markets (27 Aug 2026). Source: [Benzinga via Webull, 27 Aug 2026](https://www.webull.ca/news-detail/15475678967514112)

**Polymarket international city highs**
- [PRIMARY] Live Gamma API read, 26 Oct 2026. Final volumes for the 25 Oct city-high events: Tokyo $90,715; London $83,772; Seoul $78,837; Miami $57,619; Paris $43,625; NYC $42,921. Source: [Gamma API, events?slug=highest-temperature-in-london-on-october-25-2026](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-october-25-2026) (same pattern for the other cities)
- [PRIMARY] Same read, the 27 Oct events (about a day ahead). London: $12,400 traded so far. Live brackets 65c/70c (17°C), 20c/21c (18°C), 8c/13c (16°C). NYC: $8,500 traded, brackets 66c/70c, 23c/26c, 5c/10c. Seoul (nearer its date): $56,000 traded, brackets 30c/34c, 49c/52c, 11c/18c. In plain words, spreads near the money are 1-7c, wider than Kalshi's big-city highs. Sources: [Gamma API, London 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-october-27-2026); [NYC 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-27-2026); [Seoul 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-seoul-on-october-27-2026)
- [SELF-PUB] jattree's Polymarket bot (24 cities, Sep 2026): over 697 events, the market's log loss (a score where lower means better forecasts) was 1.31 against the model's 1.59. A simulated taker lost 13.9% per trade. Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)
- [ANECDOTE] A search summary says one bot README dropped "cold/volatile cities (NYC, London, Toronto, Chicago, Seoul)" because its backtest showed them unprofitable. This was not found in the README that was checked (codewithpom), so the source is unconfirmed. Source: search summary only

### Inferences
- The more attention a weather market gets, the closer it is to the best forecast. Big-city highs get the most traders, the 1c spreads and the clearest evidence that models lose. That market is not a target for a forecast model.
- Daily lows look like the best "attention gap" on Kalshi. They have the same settlement source and forecast inputs as highs. They earn the same $120-per-city-day LIP reward. Yet they trade 5-100 times less, with 6-18c spreads. But wide spreads are also what you would see if makers fear being picked off. Nobody has tested whether low prices are well calibrated.
- The rain NO-side result is the clearest warning. A thin-market edge showed up, passed one out-of-sample check, and then mostly vanished in about 12 weeks as more money came in. Expect any thin-weather edge to have a short life.
- The hourly index markets are a speed game, not a forecast game. The settlement data is public with a known 2.5-minute delay. Whoever reads Kalshi's own index fastest wins. A forecast model adds little in the last hour.
- Monthly rain and snow markets are too thin to make real money most months. A storm month can spike volume, but those weeks are when fast news traders show up.
- Polymarket international highs are less efficient-looking (wider spreads, fewer US quants). But jattree's 24-city test still found the market beat a careful multi-model blend.

### Gaps
- No study of calibration for Kalshi daily lows, monthly totals, ski, or snow markets. None was found on arXiv, SSRN or GitHub.
- No heating-degree-day (a measure of how much heating a day needs) market was found on Kalshi or Polymarket in 2026. No source describing one was found.
- No study compares Polymarket international city prices with a forecast model, other than jattree's self-published post-mortem.
- No weekly rain market was tested; the 25 Oct scan found weekly series closed.

---

## Q2. Market-making economics on Kalshi weather: fees, programs, queue, adverse selection, evidence

### Takeaway
On Kalshi weather, makers pay no fee today, takers pay up to 1.75c a contract, and Kalshi pays rewards for resting orders on every daily high and low. Kalshi's own trade data shows weather makers earned about +1.29% per trade (2021-2025, before fees). But the one public small maker in weather (an AI agent with $20) earned $20.30 in rewards and lost $36.06 to traders who picked off its orders. Rewards and spread are real. Whether a small maker keeps them depends on not being picked off around new weather data.

### Cited findings

**Fees**
- [PRIMARY] Live series reads, 26 Oct 2026, 20:5x UTC. All six weather series checked show `fee_type: "quadratic"`, `fee_multiplier: 1`: KXHIGHNY, KXRAIN, KXTEMPMIAH, KXTEMPNYCHS, KXLOWTNYC, KXRAINNYCM. Source: [Kalshi API, series/KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/series/KXHIGHNY) (same path for the others)
- [PRIMARY] This project's 9-25 Oct work found that "quadratic" means takers pay and makers don't. Series that charge makers show "quadratic_with_maker_fees". Sources: [kalshi_execution_and_api.md (project notes, 9 Oct 2026)](../Kalshi%20favorites%20bot%20improvements/kalshi_execution_and_api.md); the project's own maker research (25 Oct 2026)
- [SELF-PUB] Independent check on the hourly index series: "Makers pay 0 on these series." Taker fee is ceil(0.07 × n × p × (1 − p)) per order. Source: [lip-ledger WEATHER_INDEX.md (Oct 2026)](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/WEATHER_INDEX.md)
- [SNIPPET] Kalshi's fee PDF (effective 5 Feb 2026, per search summary) gives the taker fee as 0.07 × C × P × (1 − P). The maker fee, where it applies, is 0.0175 × C × P × (1 − P), a quarter of the taker rate. It is charged only when a resting order fills. Cancelling is free. The PDF returned "429 Too Many Requests" on 26 Oct 2026, so it was not read. Sources: [Kalshi fee schedule PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf); summary via [oddpool](https://www.oddpool.com/research/prediction-market-fees-explained)
- [PRIMARY] Kalshi rounds each order's fee up to the next $0.0001, not the next cent. Source: the project's own order records (25 Oct 2026).
- Bottom line on the "zero vs quarter rate" dispute: both are true in general. Kalshi has a quarter-rate maker fee on a list of series. Weather series are not on it as of 26 Oct 2026.

**Liquidity Incentive Program (LIP): open to most US members**
- [PRIMARY] Help page ("updated over 2 weeks ago", read 26 Oct 2026). Rules:
  - End date: 1 Jan 2027. Kalshi can change or end it at any time.
  - Who: "Most regular U.S. Kalshi members". Not affiliates, brokers' customers or non-US users.
  - The book is sampled once a second, at a random moment.
  - Target size: 100 to 20,000 contracts per side. A snapshot only counts if both sides have that much resting.
  - Reference price: the first level, counting down from the best bid, where total size reaches one fifth of the target. Orders at or better than it get full credit. Orders below it get the discount factor once per tick (1c step) away.
  - Payout: your share × the period's reward × the share of snapshots that counted. Rounded down to the cent. Minimum payout $1.
  - Daily rewards run $1 to $1,000 per market.
  Source: [Kalshi Help: Liquidity Incentive Program](https://help.kalshi.com/en/articles/13823851-liquidity-incentive-program)
- [PRIMARY] The API's `period_reward` field is in "centi-cents" (hundredths of a cent). So 1,000,000 = $100. Source: [Kalshi docs: Get Incentives](https://docs.kalshi.com/api-reference/incentive-programs/get-incentives)
- [PRIMARY] Live incentive list, read 26 Oct 2026 ~21:00 UTC (first 2,000 programs only; more pages exist). What weather markets were paying:

  | Weather market family | Reward per bracket | Brackets | Reward per city per period | Period |
  |---|---|---|---|---|
  | Daily highs, 24 cities (KXHIGH*) | $20 | 6 | $120 | about 39-42 hours (the whole life of one day's event) |
  | Daily lows, 24 cities (KXLOWT*) | $20 | 6 | $120 | about 39-42 hours |
  | Miami hourly temperature (KXTEMPMIAH) | $100 | 10 | $1,000 | 1 hour (only one hour was visible) |
  | Daily rain NYC (KXRAINDNYC) | $20 | 1 | $20 | about 154 hours |

  All had a target size of 1,000 contracts per side. All had a discount factor of 0.5, so an order one cent behind the reference price earns half credit, two cents a quarter. Example: tomorrow's NYC high brackets each pay $20 from 14:00 UTC 26 Oct to 05:00 UTC 28 Oct. Source: [Kalshi API, incentive_programs](https://api.elections.kalshi.com/trade-api/v2/incentive_programs?status=active&limit=1000)
- [SELF-PUB] The AI-agent account tested its own copy of the LIP formula on a $20 account (2-10 Oct 2026). Weekly program: predicted $4.44, paid $4.57. Three hourly programs: predicted $15.58, paid $15.73. The formula is predictable to within 1-3%. Source: [lip-ledger README](https://github.com/mirabilis-agent/lip-ledger)
- [PRIMARY / news] A different program is ending: the "Volume Incentive Program", which paid by share of trading volume (since Mar 2023). Kalshi told the CFTC it will end no earlier than 13 Oct 2026, amid wash-trading claims about ETH perpetuals, which Kalshi denies. This is not the LIP. Source: [The Block, 30 Sep 2026](https://www.theblock.co/news/business/2026-09-30-kalshi-ends-trader-incentive-program-417247)

**Liquidity Provider Program and Market Maker Program: firms only**
- [PRIMARY] LP program help page ("updated this week", read 26 Oct 2026): only members with a signed Market Maker Agreement can join. Providers are picked by auction: each bids the smallest reward it would accept. The page lists 53 active programs, all ending 31 Dec 2026. Weather ones: "Hourly Weather" (1 provider, no tickers listed); "Hourly Temp" KXTEMPMIAH, KXTEMPNYCH, KXTEMPLAH, KXTEMPCHIH (1 provider); "Daily Rain" KXRAIN (1 provider). Reward amounts and quoting duties are not on the page. Daily highs and lows are not in the LP list. Source: [Kalshi Help: Liquidity Provider Program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program)
- [SNIPPET] Kalshi's regulatory page for the same program says "There is no active bidding program." In plain words, no auction is open right now. That fits with the help page if the current slots are already filled. Source: [Kalshi regulatory: Liquidity Provider Program](https://kalshi.com/regulatory/liquidity-provider-program)
- [MARKETING] Per CFTC filings as read by a paid newsletter (May 2026): open-tier cap $1,000 per market per day; market-maker-tier cap $50,000 per series per week. Sources: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy), via [market_making.md (project notes, 25 Oct 2026)](../Prediction%20market%20profitable%20strategies/market_making.md)
- [PRIMARY] Market Maker Program (help page dated 28 Apr 2026): about 88 products, each quoted 98% of every hour. Benefits are "reduced fees" and bigger position limits. Approval depends on money, experience and reputation. Source: [Kalshi Help: How to become a market maker](https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi), via project notes

**Evidence on maker profits in weather**
- [HARD] Becker, 72.1 million Kalshi trades (Jun 2021 to Nov 2025), returns per trade before fees. Weather: takers −1.29%, makers +1.29%, a 2.57-point gap, on 4.4 million trades. Compare sports 2.23, crypto 2.69, finance 0.17. Makers started winning only after the 2024 election. Before that, takers were ahead. Write-up dated 18 Jan 2026; SSRN version 1 Aug 2026. Source: [Becker, "The Microstructure of Wealth Transfer in Prediction Markets"](https://www.jbecker.dev/research/prediction-market-microstructure)
- [SELF-PUB] Possible data issue in that study's code: GitHub issue #74 says the category script drops markets that settle at a fraction of $1. It says the rest of those are weather markets. So the weather row may leave some markets out. Source: [GitHub issue #74](https://github.com/Jon-Becker/prediction-market-analysis/issues/74)
- [HARD] Bürgi, Deng & Whelan (data to Apr 2025): takers lost about 32% per contract on average, makers about 10%. Cheap longshots drive these averages. Sources: [CEPR VoxEU](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market); [GWU WP 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- [HARD] Bartlett (Stanford, 21 Apr 2026), 41.6 million Kalshi trades. In "single-name" markets, informed traders move prices more. One-sided order flow predicts maker losses there but not in "broad-based" markets. Yet makers earn about twice as much per contract in single-name markets, because traders over-bet YES on things that mostly settle NO. The blog post does not say where weather falls. Sources: [Stanford Law blog](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/); [SSRN 6615739](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6615739)

**Adverse selection in weather, and how makers protect themselves**
- [SELF-PUB] The AI-agent case study (Oct 2026), the only first-hand weather maker log found:
  - It earned $20.30 in rewards and lost $36.06 trading over the same 8 days. The account went from $20 to about $0.10.
  - "The cheap side of a one-sided program is empty because the outcome is already decided. Quoting there gives faster traders a free option."
  - Blocks of 200-600 contracts swept its resting 1c bids within seconds. Ten-second burst sizes: 90th percentile about 1,400 contracts, 99th percentile about 6,000.
  - Being behind others in the queue did not protect it once the bigger resting orders were cancelled.
  - The $1 minimum payout wasted about half of its short quoting stints.
  - Lesson: "a verified reward model is not an edge until adverse-selection cost is measured on your own orders."
  Source: [lip-ledger CASE_STUDY.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/CASE_STUDY.md)
- [SELF-PUB] Same author, hourly index: the worst fills came 45-70 seconds after the last data arrival (just before the next burst), and right after an arrival. New readings for all cities land in a burst 15-37 seconds after each minute. Its rules after losing: quote only mid-minute, stand down after each fill, keep a price band, and cap exposure per city-hour. Source: [lip-ledger WEATHER_INDEX.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/WEATHER_INDEX.md)
- [SELF-PUB] The NYC daily-high maker project protects itself by design:
  - No quotes during station reports and daily summary messages.
  - No bids in brackets Central Park readings have already ruled out.
  - Orders expire 3 minutes after the last refresh.
  - An order group caps fills at 25 contracts per 15 seconds.
  - 10-contract quotes, 50 contracts per bracket at most, $10 daily loss limit.
  - Quote distance is set from fitted fill-rate and adverse-selection settings.
  It publishes no profit numbers. Source: [dfong03/apma2026-kalshi-weather](https://github.com/dfong03/apma2026-kalshi-weather)
- [MARKETING] A trading-tool vendor says a weather maker picked off just before a forecast model update can lose more on one trade than on 10 spread captures. Source: [TurbineFi blog (2026)](https://www.turbinefi.com/blog/why-prediction-market-trades-get-picked-off-2026) [SNIPPET], via project notes
- [PRIMARY] Kalshi's own tools that help a maker: `post_only` (never pay the taker fee), `expiration_time` on resting orders, `cancel_order_on_pause`, and order groups that cancel everything if fills pass a limit in a rolling 15 seconds. Amending keeps your place in the queue only if you lower size or change expiry. Changing price sends you to the back. Source: [Kalshi docs via kalshi_execution_and_api.md (project notes, 9 Oct 2026)](../Kalshi%20favorites%20bot%20improvements/kalshi_execution_and_api.md)

### Inferences
- In fee terms, making clearly beats taking on Kalshi weather. A taker at 50c pays 1.75c per contract. That is bigger than the whole 1c spread on big-city highs. A maker pays nothing, and may also earn LIP rewards.
- The open question is adverse selection, not fees. Weather has fixed, public moments when the answer gets clearer: the hourly airport report around :51-:53, the 6-hour summaries, and new model runs. A resting order left in place across those moments is a free option for faster traders. Both public weather maker projects pull quotes around those times. The one with a live log still lost.
- The daily high and low LIP rewards are small per bracket. $20 over about 40 hours is about 50 cents an hour per bracket, split among everyone qualifying. Across 24 cities × (highs + lows) × 6 brackets, the total is about $5,760 per day. That assumes a new program for each day's event, which the "series" label suggests but which was not confirmed across days.
- A small maker's best LIP fit is probably the daily lows. They pay the same reward as highs but have fewer resting orders competing for it. But wide spreads there may mean makers have been burned before. This needs a shadow test (post nothing; just log the book and the fills a quote would have got).
- Designated LP firms already hold Hourly Temp and Daily Rain. A retail maker in those families competes with a paid professional. That makes KXRAIN and KXTEMP*H worse targets for a small maker than daily highs or lows.
- Becker's +1.29% weather maker return is an average over all makers, mostly professionals. A small, slower maker should expect less, maybe negative, like the AI agent.

### Gaps
- Kalshi's fee PDF could not be read (HTTP 429). The "weather = maker-free" finding rests on today's live API fee type plus one self-published check, not the PDF text.
- Only 2,000 of the active incentive programs were read (more pages exist). KXRAIN and the other hourly-temperature cities did not appear in those pages, so whether they have LIP rewards today is unknown.
- Only one hour of the Miami hourly reward was visible ($1,000 across 10 strikes). Whether it runs every hour is unknown.
- LP program reward amounts and quoting duties are in a PDF appendix that was not read. Designated LP firm names are not public.
- No study splits maker profits inside weather by contract type (high vs low vs rain vs hourly).
- No direct measurement of maker losses around METAR or model-run times exists in public. dfong03 shows where prices move; it does not report losses.

---

## Q3. Capacity: realistic dollars per day for a small trader, market size, and who else trades

### Takeaway
Kalshi weather is a small corner of Kalshi: about $80 million a month in 2026, against $39-53 billion a month for all of Kalshi. Per market, the book near the best price holds only tens to a few hundred contracts. A careful small maker might realistically aim for tens of dollars a day across many cities, mostly from LIP rewards, and only if adverse selection stays near zero. A forecast-model taker has no proven positive number at all.

### Cited findings
- [ANECDOTE / news] Kalshi weather markets traded $564 million through July 2026, already more than all of 2025. Weather and climate volume is up "roughly 500%" year on year. Kalshi expects $1.1 billion in weather volume in 2026. (Benzinga citing the Wall Street Journal, 27 Aug 2026.) Source: [Benzinga via Webull](https://www.webull.ca/news-detail/15475678967514112)
- [ANECDOTE / news] All of Kalshi traded $38.67 billion in August 2026 and $52.98 billion in September (as of 29 Sep, a record). Source: [The Block, 30 Sep 2026](https://www.theblock.co/news/business/2026-09-30-kalshi-ends-trader-incentive-program-417247)
- [ANECDOTE / news] Who else trades weather:
  - Susquehanna Predictions prices and provides liquidity for Cantor Fitzgerald's institutional block trading on Kalshi, launched 19 Aug 2026.
  - Discrete, a Houston risk-management startup, did Kalshi's first private weather block trade. It pays $25,000 if Houston hits 103°F in August.
  - The Weather Company now supplies settlement data.
  - Commercial hedging "has not taken over".
  Source: [Benzinga via Webull, 27 Aug 2026](https://www.webull.ca/news-detail/15475678967514112)
- [PRIMARY] Designated providers: one each in Hourly Weather, Hourly Temp and Daily Rain (to 31 Dec 2026). Source: [Kalshi Help: LP Program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program)
- [PRIMARY] Depth near the best price (26 Oct 2026, 20:58 UTC): tomorrow's NYC high bracket had 25 contracts at the best YES bid and about 830 contracts across the top 8 bid levels. That is roughly $10 at the best price and a few hundred dollars within 8c. Source: [Kalshi API order book](https://api.elections.kalshi.com/trade-api/v2/markets/KXHIGHNY-26OCT27-B60.5/orderbook?depth=8)
- [PRIMARY] Volume per day (25-26 Oct 2026 scans). Daily rain: 400,000-480,000 contracts across about 35 cities. Miami, NYC and LA highs: 110,000-150,000 contracts each. Other highs: 3,000-55,000. Lows: 1,000-18,000. Miami hourly: about 20,000; other hourly cities: 1,000-2,000. Sources: the project's own scans (25-26 Oct 2026); [Kalshi API reads above](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)
- [SELF-PUB] The AI agent's ten-second burst sizes in the markets it quoted: 90th percentile about 1,400 contracts, 99th about 6,000. In plain words, one fast trader can take a whole small quote in one go. Source: [lip-ledger CASE_STUDY.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/CASE_STUDY.md)
- [SELF-PUB] The rain NO-side idea had 5-9 usable markets a day in Jul/Aug, about 1 a day by October. Source: [lip-ledger CASE_STUDY.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/CASE_STUDY.md)
- [PRIMARY] Polymarket city highs: $43,000-$91,000 total volume per city-day (25 Oct 2026 events). Source: [Gamma API](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-tokyo-on-october-25-2026)

### Inferences
- Weather is about 0.2% of Kalshi's volume. That is $80 million a month against $39-53 billion. So big firms have little reason to fight hard over it, beyond the paid LP slots. That is the case for a small trader. The case against is that it is also small money.
- A rough ceiling for a small maker. These are rough sums, not measurements:
  - **LIP rewards.** About $5,760 a day is offered on daily highs plus lows. Holding 10-25% of the qualifying size on a few cities might earn $20-$150 a day. The low end matches the AI agent's scale ($20 over 8 days on $20 of capital).
  - **Spread capture.** At Becker's +1.29% maker average, 5,000 contracts a day at an average 30c cost (about $1,500 turned over) is about $19 a day before any extra adverse selection.
  - **Capital needed.** Resting 250 contracts a side on 6 brackets in 10 cities locks up roughly $5,000-$10,000.
- For a taker using a forecast model, the realistic number is zero or negative on big-city highs. Every public test lost. Daily lows and Polymarket cities have no published test either way.
- Compared with the project's live crypto bot (1,918 orders in its Ohio-server period), weather making at retail scale is a side project measured in tens of dollars a day, not hundreds.

### Gaps
- No public figure for total LIP payouts in weather, or how many accounts compete for them.
- No source names the weather LP firms or says how much of weather volume they handle.
- The Kalshi dollar-volume split by weather type (highs vs rain vs lows) is not published. Only contract counts from the scan are available.
- The dollar ranges above are back-of-envelope. They need a shadow test on real books to firm up.

---

## Q4. Polymarket weather markets in 2026: types, volume, fees, settlement, US access, trader results

### Takeaway
Polymarket runs daily high (and low) temperature brackets for 30+ cities worldwide. Each city-day trades about $40,000-$90,000. Takers pay 0.05 × p × (1 − p) per share, makers pay nothing and get 25% of the fees back, and weather markets also pay liquidity rewards. Settlement is the highest hourly METAR reading at one named airport, in tenths of °C, not a Weather Underground page as older rules said. A US trader cannot legally use international Polymarket. Whether Polymarket US lists weather could not be confirmed.

### Cited findings
- [PRIMARY] Current rules text (27 Oct 2026 events, read 26 Oct 2026):
  - The market resolves on "the highest temperature reported in the hourly temperature remark of any routine (METAR) observation" at one airport: London City (EGLC), LaGuardia (KLGA), Incheon (RKSI).
  - Precision: "in tenths of a degree Celsius as reported" (the "T" group in the METAR remarks).
  - SPECI special reports do not count.
  - If a report lacks the T group, its whole-degree body temperature is used.
  Sources: [Gamma API, London 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-october-27-2026); [NYC 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-27-2026); [Seoul 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-seoul-on-october-27-2026)
- [SNIPPET] Older Polymarket weather rules (mirrored by a third-party site, undated 2026) named a Weather Underground daily history page and whole degrees Celsius. So the settlement rule changed during 2026. Source: [polyguana mirror](https://polyguana.com/market/2636640)
- [PRIMARY] Fees (docs read 26 Oct 2026; no effective date on the page): taker fee = shares × 0.05 × p × (1 − p) for weather. "Makers are never charged fees." Weather makers get a 25% rebate of taker fees. Only geopolitics is fee-free. Source: [Polymarket docs: Fees](https://docs.polymarket.com/trading/fees)
- [PRIMARY] Live Gamma data shows liquidity-reward settings on weather brackets: minimum 20 shares (50 on some edge brackets) and a maximum spread of 4.5c to qualify. Source: [Gamma API, London 27 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-october-27-2026)
- [PRIMARY] Volume: 25 Oct 2026 city-highs ranged from $42,921 (NYC) to $90,715 (Tokyo). Source: [Gamma API](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-october-25-2026)
- [SNIPPET] A news flash says Polymarket weather reached about $2 million in daily volume (date unclear, 2026). Another 2026 guide says single big-city markets "regularly clear $300,000 to $400,000" in 24 hours. Today's Gamma data does not support the second figure for late October. Sources: [KuCoin news flash](https://www.kucoin.com/news/flash/polymarket-turns-weather-forecasts-into-2m-daily-trading-market); [laikalabs guide](https://laikalabs.ai/prediction-markets/trade-polymarket-weather-markets) [MARKETING]
- [SNIPPET] Polymarket's Weather category listed 327 to 374 markets at different times in 2026, mostly temperature. Source: [Polymarket weather pages](https://polymarket.com/weather/high-temperature)
- [ANECDOTE] A copy-trading site's weather leaderboard (last 30 days, snapshot 26 Oct 2026): #1 "Poligarch" +$36,000 profit on $684,000 traded. #2 +$30,000 on $464,000. #4 +$21,000 on $1.3 million. #25 about +$6,000. In plain words, the top weather wallets make about 2-8 cents of profit for every dollar traded. The site does not say which are bots or makers. Source: [Polycopy weather leaderboard](https://polycopy.app/polymarket-leaderboard/weather)
- [ANECDOTE] Viral claims, early 2026: "Hans323" made about $1.1 million, mostly from one $92,632 bet at 8c on a London bracket. An anonymous bot turned $204 into about $24,000 on London highs. These come from X posts, with no audit. Source: [investx.fr (about Jan 2026)](https://investx.fr/en/crypto-news/polymarket-london-weather-betting/)
- [ANECDOTE] A Medium post on wallet "ShyGuy1" claims over $50,000 profit year to date, mostly Asian city temperatures. Source: search summary of [Medium: Top 5 weather market legends](https://moonsat.medium.com/top-5-weather-market-legends-on-polymarket-and-their-winning-strategies-173d79b9d082) [SNIPPET]
- [SELF-PUB] Most open-source Polymarket weather bots are paper-only. Example: codewithpom trades London, Seoul, NYC, Beijing and Miami with 100+ ensemble members. Live trading is off by default, and no results are shown. Source: [codewithpom/polymarket-weather-bot](https://github.com/codewithpom/polymarket-weather-bot)
- [PRIMARY] US access, from this project's 13 Oct 2026 notes:
  - International Polymarket has blocked US users since its 2022 CFTC settlement.
  - Polymarket US (CFTC-registered, formerly QCEX) is legal for US residents, with some state fights. Its docs then showed only hand-listed and BTC Up/Down markets in the short-term family.
  Sources: [short-term venues notes (project, 13 Oct 2026)](../Short%20term%20prediction%20market%20venues/); [The Block, 2022](https://www.theblock.co/linked/131383/following-cftc-settlement-prediction-platform-polymarket-geoblocks-trades-in-the-us)
- [SNIPPET] Conflicting: an odds aggregator lists Polymarket US as tracking an NYC high event on 7 Aug 2026. The page could not be opened to check. Source: [prediction.com (formerly predictionhunt)](https://prediction.com/odds/highest-temperature-in-nyc-on-aug-7-2026/30751)

### Inferences
- Polymarket weather is about as big per city as Kalshi's mid-tier highs. Spreads near the money are wider (1-7c). Fees are lower (0.05 against Kalshi's 0.07 rate), and makers get rebates plus rewards. On paper that is a better maker venue than taker venue too.
- The settlement switch to METAR tenths of °C matters for a model. The answer is a single airport's routine hourly readings. It is not a 6-hour max and not a daily climate report. It can differ from what the official daily high says, which can trip up models trained on daily highs.
- For a US-based trader such as this project, international Polymarket is off-limits. Unless Polymarket US lists the same city weather markets, the Polymarket idea is not usable. Check the Polymarket US app directly before spending time on it.
- The leaderboard shows real winners exist, at 2-8c per dollar. But it is a 30-day window with survivor bias: only the winners are listed. It says nothing about the typical forecast bot.

### Gaps
- Whether Polymarket US lists any weather markets today. No official source found; one aggregator hint.
- No audited Polymarket weather bot results. All profit claims are leaderboard snapshots or social posts.
- Polymarket's weather liquidity-reward pool sizes per market were not found. Only the qualifying size and spread were visible.
- No date found for when Polymarket switched from Weather Underground to METAR tenths.

---

## Q5. API and automation for a Kalshi weather market-making bot

### Takeaway
Kalshi's API has everything a small maker needs: post-only orders, self-expiring orders, batch create and cancel, order groups that auto-cancel after a burst of fills, and a WebSocket order book feed. Kalshi pays people to quote, so automated quoting is clearly allowed. The limits that bite a small account are speed and the token-bucket rate limit (about 10 orders a second on Basic, 30 on the free-to-upgrade Advanced tier). Retail accounts get no faster path.

### Cited findings
- [PRIMARY] Order types (Create Order V2): good-till-cancelled with optional `expiration_time`, immediate-or-cancel, fill-or-kill. Flags: `post_only`, a required `self_trade_prevention_type`, `cancel_order_on_pause`, `reduce_only`, `client_order_id`, `order_group_id`. Contract counts can go down to 0.01. Sources: [Kalshi docs: Create Order V2](https://docs.kalshi.com/api-reference/orders/create-order-v2.md), via [kalshi_execution_and_api.md (project, 9 Oct 2026)](../Kalshi%20favorites%20bot%20improvements/kalshi_execution_and_api.md)
- [PRIMARY] Amend: "Amending only expiry or decreasing size preserves queue position. Increasing size or changing price forfeits queue position." Source: [Kalshi docs: Amend Order](https://docs.kalshi.com/api-reference/orders/amend-order), via project notes
- [PRIMARY] Order groups: they cancel all the group's resting orders once fills pass a set number of contracts in a rolling 15 seconds. Up to 100,000 groups per user (raised 13 Aug 2026). Source: [Kalshi docs: Order Groups](https://docs.kalshi.com/getting_started/order_groups), via project notes
- [PRIMARY] Rate limits (15 Oct 2026). Most requests cost 10 tokens. Basic Write budget: 100 tokens a second, about 10 orders a second, 1 second of burst. Advanced: 300 tokens a second with 3 seconds of burst, self-serve with one API call. Higher tiers are earned by volume. A batch costs the same as single calls. Batch cancel costs 2 tokens per order. "Cancel-all costs one cancel" (3 Sep 2026). Sources: [Kalshi docs: Rate Limits](https://docs.kalshi.com/getting_started/rate_limits); [Changelog](https://docs.kalshi.com/changelog), via [kalshi_api_features.md (project, 15 Oct 2026)](../Faster%20Kalshi%20order%20sending/kalshi_api_features.md)
- [PRIMARY] WebSocket: the `orderbook_delta` channel sends a snapshot, then changes with sequence numbers. Your own `fill`, `user_orders` and `order_group_updates` channels are on the same connection. Source: [Kalshi docs: Orderbook Updates](https://docs.kalshi.com/websockets/orderbook-updates), via project notes
- [PRIMARY] Speed products (PrivateLink, VPC peering, FIX by default) start at Premier tier or above. A retail account has no faster path. Kalshi's servers are in AWS us-east-2 (Ohio), the region where this project's bot ran. Sources: [kalshi_api_features.md (project, 15 Oct 2026)](../Faster%20Kalshi%20order%20sending/kalshi_api_features.md); the project's own network measurements (20 Oct 2026)
- [SELF-PUB] The Weather Index endpoint (`/live_data/weather/{city}`) is free and needs no key. It handled 33 requests a second without a 429 error. Keeping the HTTPS connection open cut call time from about 170 ms to 40 ms. Settled weather markets paid out cash 30-60 minutes after close. Sources: [lip-ledger WEATHER_INDEX.md (Oct 2026)](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/WEATHER_INDEX.md); [Kalshi docs: Get Weather Index](https://docs.kalshi.com/api-reference/live-data/get-weather-index)
- [SELF-PUB] Speed matters for taking: at about 1 second of delay, the agent's IOC orders on stale bids got 4 fills, all losers. Faster bots take stale bids within about 0.3 seconds. Source: [lip-ledger WEATHER_INDEX.md](https://raw.githubusercontent.com/mirabilis-agent/lip-ledger/main/docs/WEATHER_INDEX.md)
- [PRIMARY] Rules: the Kalshi rulebook has Rule 5.9 (order cancellation) and Rule 5.13 (prohibited trading). Trade-cancellation rules were updated 22 Aug 2025. No spoofing or message-rate text appeared in the excerpts read. Sources: [Kalshi rulebook (CFTC filing)](https://www.cftc.gov/filings/documents/2023/orgkexkalshiexhibitm231130.pdf); [Rule 5.11 update](https://www.ingame.com/wp-content/uploads/2025/08/5.11-Update-Filing-1.pdf) [SNIPPET]
- [PRIMARY] Kalshi pays automated quoting through the LIP and LP programs (see Q2). The NYC maker project and the AI agent both quoted by API in public. Sources: [Kalshi Help: LIP](https://help.kalshi.com/en/articles/13823851-liquidity-incentive-program); [dfong03](https://github.com/dfong03/apma2026-kalshi-weather)

### Inferences
- A weather maker needs far fewer messages than a crypto maker. A city-day has 6 brackets. Quotes only need to move when data arrives (each minute for the index; each hour for METAR). The Advanced tier's 30 orders a second covers dozens of cities.
- The practical build:
  - `post_only` GTC orders with a short `expiration_time`.
  - An order group per city, so a burst of fills cancels that city's quotes.
  - Batch cancel just before :51 each hour and around model-run times.
  - Quotes pulled from brackets the observations have already ruled out.
  The project's former Ohio server sat in the same region as Kalshi's servers.
- Speed only matters for getting out of the way. A slower maker should pull quotes before known data times rather than try to react after them.

### Gaps
- No Kalshi rule text was found on message rates, order-to-trade ratios or spoofing for API users. Rule 5.13 probably covers spoofing, but its text was not read.
- `post_only` behaviour when an order would cross (reject or reprice) is not documented. This needs a demo test.
- No public timing data on how fast weather prices react to new model runs (as opposed to the hourly METAR).
