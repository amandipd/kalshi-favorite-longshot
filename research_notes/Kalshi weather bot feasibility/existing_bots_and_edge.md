# Existing weather bots and the evidence on edge (Kalshi and Polymarket weather markets)

Research date: 25 Oct 2026. Every claim says which year it is from.
Labels used on each finding, so hard evidence and hype stay apart:

- **[HARD]**: a paper, or a backtest with its method shown and real market prices.
- **[SELF-PUB BACKTEST]**: one person's backtest, method shown, not reviewed by anyone else.
- **[LIVE, SELF-REPORTED]**: real money, but only the author's word for it.
- **[ANECDOTE]**: a news story, interview or screenshot. No method, no audit.
- **[MARKETING]**: the source sells a bot, course, tool or tip jar.

Plain words for terms used below:

- **Edge**: profit per contract, in cents.
- **Calibration**: whether a 70c price really wins 70% of the time.
- **Favourite-longshot bias**: cheap unlikely bets are overpriced, heavy favourites underpriced.
- **Out-of-sample**: tested on data the rule never saw while being built.
- **Walk-forward**: each day is tested using only data from before that day. It is a strict kind of out-of-sample test.
- **Maker / taker**: a maker posts a resting order and waits. A taker fills against someone else's order right away and pays the taker fee.
- **Taker fee**: Kalshi's charge for trading, biggest near 50c. On Kalshi it is 7% × price × (1 − price).
- **RMSE (root-mean-square error)**: the typical size of a forecast miss, in °F. Lower is better.
- **Brier score**: an accuracy score for probability forecasts. 0 is perfect, 0.25 is a coin flip. Lower is better.
- **Log loss**: another accuracy score for probabilities. Lower is better. It punishes confident wrong calls very hard.
- **ECE (expected calibration error)**: the average gap between the price and the real win rate. 0 means perfectly calibrated.
- **NBM (National Blend of Models)**: the National Weather Service's automatic mix of many weather models. It is the best free single forecast.
- **MOS / LAMP**: statistical fixes that turn raw model output into a forecast for one weather station. LAMP updates every hour using the latest observations.
- **HRRR**: a fast-updating, fine-grid US weather model.
- **Ensemble**: many runs of one model with small tweaks. The spread of the runs gives a range of outcomes.
- **METAR**: the hourly weather report from an airport station.
- **Kelly**: the bet size that grows money fastest without risking ruin.

---

## Q1. Who has built public weather bots or forecast models, and what data and models do they use?

### Takeaway
Dozens of open-source weather bots exist (2025-2026). Almost all use the same free inputs: NWS forecasts, or GFS/ECMWF models and ensembles pulled through Open-Meteo, turned into bracket chances with a bell-curve error model. Almost none trade real money, and none publish audited profit. The few that tested themselves honestly against the market lost.

### Cited findings

**GitHub bots: Kalshi (all 2025-2026; none show audited profit)**

| Repo | What it uses | Real money? | Trust level |
|---|---|---|---|
| suislanchez/polymarket-kalshi-weather-bot (fork: kurs0n) | 31-run GFS ensemble via Open-Meteo. Trades when its edge beats 8%. Kelly sizing at 15% of full Kelly. | No. Its README says it "does not place real trades or use real money" | Its "$1.8k highest profits" tag has no logs or screenshots behind it. Most likely paper. 793 stars |
| Stewyboy1990/weatheredge-bot | 82 GFS + ECMWF ensemble runs, NWS bias fix, quarter Kelly, 8% minimum edge | Not stated | No results shown |
| Schmiedey/kalshi-weather | GFS, ECMWF, ICON turned into bracket chances. Longshot strategy | Paper only | No results shown |
| urm8/weatherbots | Several forecast sources, scored by past error. City bias fix for NYC, Chicago, Austin, Miami. Stop-losses | Not stated | No results shown |
| watkast, dhilandonkey-png, ethanterrero | NWS forecasts. Trades when the gap beats about 8c after fees | watkast and dhilandonkey: paper only | No results shown |

Sources: [suislanchez](https://github.com/suislanchez/polymarket-kalshi-weather-bot); [kurs0n](https://github.com/kurs0n/polymarket-kalshi-weather-bot); [Stewyboy1990](https://github.com/Stewyboy1990/weatheredge-bot); [Schmiedey](https://github.com/Schmiedey/kalshi-weather); [urm8](https://github.com/urm8/weatherbots); [watkast](https://github.com/watkast/kalshi-weather-bot); [dhilandonkey-png](https://github.com/dhilandonkey-png/kalshi-weather-bot); [ethanterrero](https://github.com/ethanterrero/Kalshi-Weather-Bot/blob/main/README.md); [Deegan4](https://github.com/Deegan4/polymarket-kalshi-weather-bot)

**GitHub bots: Polymarket (2025-2026)**
- tobiasbischoff/polymarket-weather-bot uses NOAA and Open-Meteo forecasts. nikitailin-cs/polymarket-weather-bot uses ECMWF ensembles and paper-trades by default. braindeadpt and 0xNorex are paper-trading bots with Kelly sizing. None show audited results. [MARKETING-free but unverified]. Sources: [tobiasbischoff](https://github.com/tobiasbischoff/polymarket-weather-bot); [nikitailin-cs](https://github.com/nikitailin-cs/polymarket-weather-bot); [braindeadpt](https://github.com/braindeadpt/weatherbot-Polymarket); [0xNorex](https://github.com/0xNorex/pm-bot)
- An "OpenClaw" AI-agent skill called polymarket-weather-trader copies the gopfan2 rule using NOAA data. It is listed on agent-skill directories, with no results. [MARKETING] Source: a practitioner's write-up (not linked)
- jattree/weather-edge (Sep 2026) is the most careful Polymarket bot found. It used 6 to 8 models per city via Open-Meteo, a 30-day bias fix against airport METAR readings, EMOS (a statistical spread fix) and a skill-weighted blend, across 24 cities. It is now retired and published as a post-mortem. [LIVE, SELF-REPORTED]. Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)

**Backtests that set out to test the market (2026)**
- MiguelTheGamer/kalshi-weather-backtest asks "Can free weather data beat Kalshi's temperature markets?" Its answer is no. It averages GFS, ECMWF and ICON, fits a bell-curve error on a rolling 60 days, and adds live airport readings for same-day tests. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- A DEV Community post by "myfirstcodeo" (23 Sep 2026) tested Open-Meteo GFS/ECMWF forecasts with a city-by-city bias and a bell-curve error model, across 24 cities. The author also sells a $29 product. [SELF-PUB BACKTEST + MARKETING] Source: [dev.to](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c)

**Blogs, posts and video (2025-2026)**
- "MAXIMUS" (Northlake Labs, 23 Feb 2026) ran a bot on NWS ensemble forecasts with a bell-curve error model. It bought NO on daily high contracts. It looks like an AI-agent-written blog with a tip jar. [LIVE, SELF-REPORTED + MARKETING]. Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Bot for Kalshi's strategy guide (2026) uses Open-Meteo highs with an assumed ±2.7°F error. It scanned 84 live contracts and reports no realized results. The site sells a $99-a-month plan. [MARKETING] Source: [botforkalshi.com](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy)
- Paid or freemium "edge finder" tools exist: Kalshi Weather Edge, PredictionMarketsPicks' weather tool, the Celsi scanner, WeatherBot. None show audited results. [MARKETING] Sources: [kalshiweatheredge.com](https://www.kalshiweatheredge.com/); [predictionmarketspicks.com](https://predictionmarketspicks.com/tools/weather); [weatherbot.bot](https://weatherbot.bot/); [Celsi on AlternativeTo](https://alternativeto.net/software/celsi)
- A YouTube video is titled "How Trading Bots Make $10K+ Monthly Predicting the Weather on Polymarket". Only the title was seen. [ANECDOTE] Source: [YouTube](https://www.youtube.com/watch?v=86xl8sINErw)
- A Dev Genius blog claims bots turned $1,000 into $24,000 on London weather since April 2025, and made $65,000 across New York, London and Seoul. No proof is shown. [ANECDOTE] Source: [Dev Genius](https://blog.devgenius.io/found-the-weather-trading-bots-quietly-making-24-000-on-polymarket-and-built-one-myself-for-free-120bd34d6f09?gi=711cd7e9209b)
- An X article titled "The complete guide to trading weather markets like a quant" by polydao exists. It was not read. [UNREAD] Source: [X / polydao](https://x.com/polydao/article/2041113454023475370)

**Human traders' own data (Atmos feature, 30 Sep 2025)** [ANECDOTE]
- One trader with a geoscience master's (pseudonym "Joel Montrose") traded Miami daily highs from late 2024. He pulled data from regional Mesonet sensor networks, then learned Python to build a model. Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)
- A New York software engineer (pseudonym "Tucker Keating") wrote a script to scrape public temperature readings faster than others. Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)

### Inferences
- The public bot scene is crowded and copycat. Most repos are forks or near-copies of one design: free model, bell-curve error, an 8% edge trigger, Kelly sizing. If that design worked, it would be competed away fast, because anyone can run it.
- GitHub stars measure interest, not profit. The most-starred repo (793 stars) trades only paper money.
- No public bot uses paid data, private station feeds, or the NBM's own probability products in a published, tested way. The serious academic work (Q2) uses NBM, LAMP and HRRR, which the hobby bots mostly skip.

### Gaps
- Reddit (r/Kalshi, r/algotrading, r/weather) could not be searched. Two Reddit-targeted searches returned no Reddit pages. Reddit opinion is not covered here.
- Hacker News: no threads on Kalshi weather bots were found.
- X/Twitter: only one article title was found. X threads were not readable.
- No public bot was found that shows a long, real-money track record with fills and fees.

---

## Q2. What results have been reported, and how believable are they? Is there a study of weather market accuracy, calibration or the favourite-longshot bias?

### Takeaway
The hard evidence all points one way. Kalshi's daily high prices are more accurate than every free public forecast, by about 10% against the best one (2026 paper). Three separate 2026 backtests and two real-money post-mortems found that public-forecast bots lose money after fees. The only positive numbers come from screenshots, marketing, or very thin slices. One academic study (2021 to April 2025 data) finds the favourite-longshot bias exists in weather markets too, but is milder than across Kalshi as a whole.

### Cited findings

**The main academic study: "Prediction Markets Beat the Weather Forecast on Tomorrow's High Temperature" (Alexander W. Crosier, arXiv, 21 Sep 2026)** [HARD]
- Data: Kalshi daily high markets in 7 cities. NYC and Chicago from Jan 2022, Miami and Austin from May 2023, Philadelphia and Denver from Nov 2024, Los Angeles from Jan 2025. 7,590 city-days in total, up to 12 Aug 2026. Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- Method: the market forecast is the average temperature implied by the mid-prices of all the brackets. It is compared with six public products: NDFD (the official human-edited NWS forecast), NBM, LAMP, GFS MOS, HRRR and ECMWF. It is also compared with a best-fit blend of all six, rebuilt each day using only past data. The test that the gap is not luck is the Diebold-Mariano test (it checks whether one forecast's misses are really smaller than another's). Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- Headline: at the end of its first trading hour, the market's typical miss (RMSE) is about 10% smaller than the best single public product, the NBM. Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)

| Forecast | Typical miss, day before at 11am ET (RMSE, °F) | Typical miss, morning of the day (RMSE, °F) | How much bigger its miss is than the market's (morning of the day) |
|---|---|---|---|
| Kalshi market | 2.44 | 1.88 | (the yardstick) |
| NBM, the best free single forecast | 2.70 | 2.12 | 11.4% bigger |
| NDFD, the official NWS forecast | 2.83 | 2.33 | 19.3% bigger |
| ECMWF, bias-fixed | 3.31 | 2.68 | 30.6% bigger |
| Best blend of all six, built only on past days | 2.45 | 1.90 | 3.0% bigger, and only weakly beyond luck (passes at the 10% level, not the usual 5%) |

Source for the table: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)

- The market beats NBM in every city except Miami. Miami's NBM miss is only about 1.6°F, against 2.6 to 3.5°F elsewhere. Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- The market's lead is biggest in winter in Philadelphia, Chicago and NYC. From November to June it beats NBM by 10-16%. From July to October the lead shrinks to 1-4%. Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- The paper does not study calibration, the favourite-longshot bias, fees, or trading profit. It uses mid-prices, not real fills. Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- It mentions a second, similar study (Brown, 2026) with "broadly similar but smaller margins". Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)

**The favourite-longshot bias on Kalshi, including weather: "Makers and Takers: The Economics of the Kalshi Prediction Market" (Bürgi, Deng and Whelan; UCD 2025 working paper, GWU version Feb 2026)** [HARD]
- Data: 46,282 contracts from 12,403 events, 2021 to April 2025. Only markets with at least $1,000 traded and a final spread of 20c or less. Over 300,000 prices counting both sides. Profits are before fees. Source: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Across all of Kalshi: contracts under 10c lose over 60% of the money put in. Contracts above 50c earn a small positive return that is beyond luck. The average return on all contracts is about −20%. Source: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- The bias shows up for both makers and takers, but more strongly for prices takers accept. Source: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Weather breakout (Table 8, "Climate & Weather", 29,924 price observations): the fitted line for profit per contract is −0.997 + 0.031 × price, in cents. The all-Kalshi line is −1.736 + 0.034 × price. Both reject "prices are fair" strongly. Source: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- The bias looks weaker in 2025 than in earlier years, across all categories. The 2025 slope is 0.021 and only weakly beyond luck. Source: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)

**Backtests of public-forecast bots on Kalshi (2026)**
- MiguelTheGamer (May-Oct 2026, about 48 settled days per city, NYC/Chicago/Miami): it buys at the ask, pays the taker fee, sizes at quarter Kelly, and scores walk-forward. The market had lower log loss than the model in every test. The day before at 3pm in NYC, the market scored 0.95 against the model's 1.22, and the simulated return was −14% of money staked. The morning of the day, it was 0.81 against 1.06, for −9%. Mixing the model with the market never beat the market alone. "The market won every cell." [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- Same repo, live readings added: by 5pm local the market's log loss was 0.03 in NYC and Chicago, against a model log loss of 0.50 to 0.65. In plain words, prices have almost locked in the answer by late afternoon. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- Same repo: the best combination of every bracket lost 5c after fees, so there was no free-money arbitrage. One lucky slice (Chicago 3pm, +$78 on $113 staked) came from 4 winners in 24 tries. The author calls it noise. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- DEV Community, myfirstcodeo (25 Jul-22 Sep 2026, 24 cities, 1,317 city-days, 7,902 markets). The model was fit on the first 30 days and scored on the last 30. Brier score: market 0.1195, model 0.1466, base rate 0.1541. Lower is better, so the market wins clearly. The market won in every city and every price band. [SELF-PUB BACKTEST] Source: [dev.to](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c)
- Same post, trading at the ask with fees: buying YES on model disagreements lost 37.7% of money staked (689 trades, −$2,583.61). Buying NO lost 7.2% (787 trades, −$550.88). Every price band lost money. When the model said 50-70% and the market disagreed, the event happened only 25-36% of the time. [SELF-PUB BACKTEST] Source: [dev.to](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c)

**Backtests and live results on Polymarket (2026)**
- jattree/weather-edge (Sep 2026, 697 events scored 36 hours before close): log loss was 1.31 for the market, 1.59 for the model, and 1.95 for an AI decision model. The market gave the winning bucket 32.8% on average; the model gave it 25.7%. A simulated taker strategy with a 1c half-spread and fees lost 13.9% ± 5.3% per trade over 1,905 trades. [SELF-PUB BACKTEST] Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)
- Its live run went from $210 to $51.61, a 75.4% loss. The author blames much of this on software bugs. One bug sold winners and kept losers. Another used the UTC day instead of the local day. [LIVE, SELF-REPORTED]. Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)
- The author's summary: model error (about 1.4°C) is wider than a bucket (about 1.1°C), and the market's implied temperature was about 0.2°C off, against 0.8°C for raw models. The 1.4°C and 1.1°C figures came from a search summary of the repo, not the page read directly. Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)

**Live real-money losses on Kalshi (2026)**
- MAXIMUS (23 Feb 2026): 0 wins, 32 losses, "a few hundred dollars" lost. It blames three things: real forecast misses have fatter tails than a bell curve (its "90% sure" trades were more like 75-80%); fees ate cheap contracts; and faster bots reacted to NWS updates within seconds. [LIVE, SELF-REPORTED + MARKETING]. Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)

**Calibration studies**
- CalibShi (Zerve notebook, 22 Mar 2026): 8,494 settled NYC daily high markets (KXHIGHNY). Raw prices had an ECE of 0.016, meaning prices were off from real win rates by about 1.6 points on average. A fitted correction cut that to 0.001. It is one city, the period is not stated, it does not say whether the test was out-of-sample, and it ignores fees. [SELF-PUB BACKTEST] Source: [Zerve gallery](https://www.zerve.ai/gallery/85cce830-f612-4b23-8b78-34d7da65a2c6)
- Kalshi's own calibration post (20 Aug 2026) used over 2.2 million data points. It says elections, politics and finance have the strongest forecasts. It gives no weather numbers and does not mention the favourite-longshot bias. [MARKETING: Kalshi grading itself]. Source: [Kalshi News](https://news.kalshi.com/p/prediction-market-calibration-how-accurate-is-kalshi)
- MiguelTheGamer's study across all Kalshi markets, not just weather (about 11,000 snapshots, 24h and 2h before close): buying NO on longshots lost 2-8% after fees in every price bucket, in both halves of the sample. Contracts priced 10-20c won 16-18% of the time, which is about fair. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)

**Positive claims (all weak)**
- Polymarket wallet "$88K weather strategy" (Medium, Mountain Movers): profile shows about $88,481 profit on about $3.3 million traded, so roughly 2.7c of profit for every dollar traded. The article could not be opened (blocked). The numbers come from the search summary of its text and from a profile page, not an audit. [ANECDOTE] Source: [Medium](https://medium.com/mountain-movers/inside-the-data-behind-polymarkets-viral-88k-weather-prediction-trading-strategy-and-results-2e65a8389f37)
- One real Polymarket account named "@weather-bot" showed −$109.62 on $144.37 traded when checked through a web search. [ANECDOTE] Source: [Polymarket @weather-bot](https://polymarket.com/@weather-bot)
- A sales page says buying NO in the 88-95c band "historically returned 1.5-2.4% per trade after fees" when the forecast cushion is over 2°F. No sample or source is given. [MARKETING] Source: [search summary of weather strategy guides](https://pillarlabai.com/blog/how-to-trade-temperature-markets-kalshi/) (exact page not confirmed)

### Inferences
- Rough reading of the Bürgi weather line (arithmetic done for this note on their fitted straight line; before fees; 2021-April 2025):
  - A 5c weather contract would lose about 0.8c, which is about 17% of the money put in. The all-Kalshi line gives about 31%.
  - A 95c weather contract would make about 1.9c, which is about 2 cents of profit for every dollar bet. The all-Kalshi line gives about 1.6c.
  - The weather line crosses zero at about 32c, against about 51c for all of Kalshi.
  - Caveats: it is a straight line through all prices, before fees, on last-traded prices, and on older data. At 95c the taker fee is about 0.3c per contract. So a small favourite edge may survive fees in this older data, but it is thin.
- The 2026 backtests (MiguelTheGamer, all categories) found buying favourites at the ask lost 2-8% after fees. That clashes with the Bürgi pre-fee result. Likely reasons: fees, buying at the ask instead of last trade, newer data (2026), and the bias fading. This conflict is not settled by any source.
- For this project: the bot's current edge is buying heavy favourites in crypto 15-minute markets. Weather favourites showed a milder version of the same bias in 2021-2025 data. No source tests a favourites-only rule on weather after fees with recent data. That is the open question worth testing, not "beat the forecast".
- Three separate 2026 backtests, two different venues, and two live losses agree. A bot that turns public forecasts into probabilities and takes the ask does not beat these markets. This is about as strong as hobby evidence gets.

### Gaps
- The "Brown (2026)" study named in the Crosier paper could not be found.
- No study of rain market (KXRAIN) accuracy or calibration was found.
- No study of hourly temperature market accuracy was found.
- No published, method-shown profit record for any weather trader, on either venue, was found.
- Kalshi's "Weathering the Storm" research page returned "too many requests" and could not be read. A search summary claimed it shows daily weather market accuracy rising from 83.3% one day out to 88.3% at twelve hours. This is unverified and should not be used without reading the page: [Kalshi research](https://kalshi.com/research/insights/hedging-climate-risk).

---

## Q3. Who are the big players? Are there professional weather traders, market makers or firms? Does Kalshi have a market maker program for weather?

### Takeaway
No public source names a professional firm (energy desk, weather-derivatives shop or market-making firm) trading Kalshi weather. Kalshi does pay for liquidity in some weather series. Its Liquidity Provider Program lists Hourly Weather, Hourly Temp and Daily Rain, each with one designated provider, through 31 Dec 2026. Daily high temperature is not on that list. The best-known "big players" are pseudonymous Polymarket wallets, and their numbers come from screenshots.

### Cited findings
- Kalshi's Liquidity Provider Program page (seen Oct 2026, "updated this week") lists these weather series, each with one designated provider and an end date of 31 Dec 2026: Hourly Weather; Hourly Temp (KXTEMPMIAH, KXTEMPNYCH, KXTEMPLAH, KXTEMPCHIH); Daily Rain (KXRAIN). No daily high temperature series is listed. Source: [Kalshi help: Liquidity Provider Program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program)
- To be a designated provider, you must sign a Market Maker Agreement. Providers win the slot in an auction by bidding the lowest reward they would accept. The reward size and the quoting rules are not public. Source: [Kalshi help: Liquidity Provider Program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program)
- Kalshi's general market maker program offers lower fees and adjusted position limits in exchange for quoting and volume duties. Approval depends on money, experience and reputation. Source: [Kalshi help: market maker program](https://help.kalshi.com/markets/market-maker-program) (via search summary)
- A Sports Illustrated review says a Liquidity Incentive Program ran through 1 Sep 2026. That conflicts with the help page's 31 Dec 2026 date. The help page is likely newer. Source: [SI review](https://www.si.com/prediction-markets/reviews/kalshi) (via search summary)
- Named human traders on Kalshi weather (Atmos, 30 Sep 2025) [ANECDOTE]:
  - Shannon Magiera started trading Chicago and Denver highs in 2022 with $50. She said she was "making a living" by late 2024, then joined Kalshi's operations team.
  - Scott Owens trades $150,000 to $200,000 a year across many markets, including hurricanes.
  - "Joel Montrose" (pseudonym) bet $200-500 a day on Miami highs and sometimes cleared $3,000 in a day.
  - The article names no firms, energy traders or market makers.
  - Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)
- Polymarket "whales" (Odaily / Foresight News via KuCoin, 6 Feb 2026) [ANECDOTE, screenshots only]:
  - "neobrother": over $20,000 profit by laddering cheap YES bets (0.2c to 15c) across neighbouring temperature buckets, for example Buenos Aires.
  - "Hans323": a reported $1.11 million profit from a $92,632 bet on a London temperature outcome priced at about 8%.
  - The article does not say any figures were checked on-chain. Claims that these traders use automation or "data scraping teams" are the writer's guesses.
  - Source: [KuCoin News (Odaily)](https://www.kucoin.com/news/flash/traders-on-polymarket-earn-millions-by-predicting-weather)
- "gopfan2" on Polymarket is reported to have made over $2 million, mostly from weather. The reported rule: buy YES under 15c, buy NO over 45c, risk about $1 a position. This comes from secondary write-ups and skill listings, not checked records. [ANECDOTE] Sources: [KuCoin News](https://www.kucoin.com/news/flash/two-top-traders-on-polymarket-earn-millions-by-predicting-weather) (via search summary); [Phemex News](https://phemex.com/news/article/polymarket-traders-profit-from-weather-predictions-58213)
- In the Atmos piece, traders placed large bets minutes before the hourly Central Park (KNYC) reading was posted. One trader suspected someone had faster data. [ANECDOTE] Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)

### Inferences
- Kalshi pays a provider to quote hourly temperature and daily rain. That suggests those series do not attract enough natural liquidity on their own. The daily high series, which is not on the list, probably does.
- One designated provider per weather series means a single firm likely sets the resting quotes there. A new maker would be competing with that one firm for queue position.
- The famous Polymarket wins (Hans323, neobrother) are big payoffs on cheap longshots. That is the opposite of what the hard data says works (cheap longshots lose on average). These are likely survivor stories: we hear about the winners, not the many who lost on the same kind of bet.
- No energy or weather-derivatives desk is publicly known to trade Kalshi weather. Contract sizes and depth are likely too small for them. This is a guess, not a sourced fact.

### Gaps
- The identity of the designated liquidity providers in weather series is not public.
- No source shows how much of weather volume comes from makers versus takers, or from bots versus people.
- No source names a professional firm in Kalshi weather markets.
- The reward size in the Liquidity Provider Program is not published.

---

## Q4. Where does the edge come from, according to people who have made money?

### Takeaway
Not from better free forecasts. The market already beats those, and it leads the NBM rather than following it (2026 paper). The edges people describe are about the last few hours and the fine print: faster live readings near the close, knowing exactly which station and rounding rule settles the contract, and resting orders as a maker. All of these are anecdotal or thin. One "edge" is plain cheating: a Paris airport sensor was likely heated to move a Polymarket market (April 2026).

### Cited findings

**Reacting to new model runs (for example the 00z and 12z runs): the evidence says this is already priced in**
- The NBM moves toward the market about four times as far as the market moves toward the NBM. A one-step disagreement (1.49°F) moves the next NBM by 0.063°F. A typical NBM update (0.43°F) moves the market by only 0.016°F. Both effects are far beyond luck (t = 15.9 and t = 11.9; about 2 is the usual bar). [HARD] Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- In Chicago, a 1°F NBM update was preceded by a 0.011°F market move in the 45 minutes before it posted, and followed by only 0.007°F. There is no jump when the NBM is published. [HARD] Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- MAXIMUS says fast bots reacted to NWS updates within seconds, so its slower bot was trading on stale prices. [LIVE, SELF-REPORTED]. Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)

**Live observations near the close**
- In the paper, much of the public forecasts' daytime improvement comes from LAMP, which uses live readings. Without LAMP, the market's lead over the best blend grows from about 3% to 3.3%, 4.7% and 6.4% at the three check times. [HARD] Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- By 5pm local, market prices have almost locked in the answer (log loss 0.03 in NYC and Chicago). A model with live airport readings still lost to the market at 11am, 1pm, 3pm and 5pm. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- An Iowa State Mesonet scientist called NOAA's Daily Summary Message a "cheat code" for predicting highs, because it gives earlier, more exact readings. [ANECDOTE] Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)
- Traders scraped readings faster than others, or used Mesonet sensor networks. Large bets appeared minutes before hourly readings posted. [ANECDOTE] Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)

**Settlement-rule quirks**
- Kalshi settles on one named station, not "the city". A city-centre forecast can be about 1°F off the station, which can flip an integer bracket. Source: [Bot for Kalshi guide](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy) [MARKETING, but the point is factual]
- The official daily high is usually 0-2°F above the highest hourly airport reading. Across 204 station-days in NYC, Chicago and Miami, it matched the hourly high 39% of the time, was 1°F higher 52% of the time, and 2°F higher 7% of the time. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- NWS daily climate reports use local standard time. During daylight saving time the "day" runs from 1:00am to 12:59am the next day. Settlement can be delayed if the high clashes with the 6- or 24-hour METAR highs, or if the final high is lower than the early report. Source: [Kalshi help: Weather Markets (22 Jul 2026)](https://help.kalshi.com/en/articles/13823837-weather-markets)
- Hourly temperature markets settle on The Weather Company's value, about 25-35 minutes after close. Early readings can differ from the final value because of rounding and unit conversion. Source: [Kalshi help: Weather Markets](https://help.kalshi.com/en/articles/13823837-weather-markets)
- Station errors of 1-2°F are minor for science but decide bets. Mesowest data is "provisional". A reading rounded from 71 to 72 degrees can decide a contract. [ANECDOTE] Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)
- Polymarket weather markets resolve to the value Weather Underground shows for an airport station (for example KLGA, KORD, London City). Hong Kong uses the Hong Kong Observatory. Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)
- Getting this wrong is a common way to lose. jattree's bot used the UTC day instead of the local day, had three wrong stations, and backtested against gridded data instead of the airport reading. Source: [jattree/weather-edge](https://github.com/jattree/weather-edge)

**Settlement source change on Kalshi (Aug 2026): sources conflict**
- On 27 Aug 2026 Kalshi announced a deal with The Weather Company. The Weather Company now verifies outcomes, and in return shows Kalshi odds in its app. Sources: [Bloomberg](https://www.bloomberg.com/news/articles/2026-08-27/kalshi-weather-odds-are-coming-to-a-weather-app-near-you); [Artemis](https://www.artemis.bm/news/prediction-market-kalshi-partners-with-the-weather-company-for-weather-hedge-settlements/)
- The Crosier paper says Kalshi switched daily high settlement from NWS to The Weather Company after 12 Aug 2026. NextPredict says from 14 Aug. Turbine FI dates it to 27 Aug. Sources: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1); [NextPredict](https://nextpredict.io/prediction-markets/weather/); [Turbine FI](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026)
- Kalshi's own help page (dated 22 Jul 2026, before the deal) still says daily highs settle on the NWS climate report. Source: [Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets)
- The DEV backtest found Kalshi's settled value matched the NWS climate report on 1,316 of 1,317 city-days, from 25 Jul to 22 Sep 2026. That includes weeks after the reported switch. Source: [dev.to](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c)
- Precipitation and snow still settle on NWS reports, per Turbine FI. Source: [Turbine FI](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026)

**Market making (resting orders)**
- Across all Kalshi maker fills studied (1,500 markets, about 950,000 fills, fees and adverse selection counted), makers roughly broke even: −0.9% ± 3.1%. By category: sports −1.2%, crypto −0.2%, commodities +0.2%. Weather was not broken out. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- Resting orders on the 97-99c side made +0.9% ± 0.2%, and +1.2% in sports, positive in both halves of the sample. The author says this profit goes to makers already at the front of the queue. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)
- The author's bottom line: the only edge found was about 1c won per trade against about 98c risked on the favourite side, mostly for makers at the front of the queue. Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)

**Longshot ladders (Polymarket)**
- neobrother's ladder and gopfan2's "YES under 15c" rule are the most-copied ideas. The theory is that traders pile into the most likely bucket and leave the neighbouring buckets too cheap. No checked results exist. [ANECDOTE] Source: [KuCoin News](https://www.kucoin.com/news/flash/traders-on-polymarket-earn-millions-by-predicting-weather)

**Fees on cheap contracts**
- A fee of about 1c on a 5c contract eats most of any edge. MAXIMUS now refuses contracts under about 15c. [LIVE, SELF-REPORTED]. Source: [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)
- Longshot buyers' losses mostly go to spreads and fees, not to the traders on the other side. [SELF-PUB BACKTEST] Source: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)

**Manipulation (April 2026, Polymarket Paris)**
- Météo-France filed a criminal complaint about the Charles de Gaulle airport sensor used for Polymarket's Paris temperature markets. On 6 April the reading jumped from 16.9°C to 21.9°C in 12 minutes. A similar jump happened on 15 April. A heating device near the probe was the most likely cause, per a meteorologist; the "hair dryer" story is unconfirmed. Sources: [Euronews (23 Apr 2026)](https://www.euronews.com/business/2026/04/23/hair-dryer-trick-behind-25000-win-france-probes-potential-weather-data-scam-linked-to-poly); [Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/france-probes-weather-data-tampering-075950500.html)
- Reported winnings conflict: about $14,000 on 6 April in one report, about $34,000 across both days in others, and almost €30,000 in Euronews. Sources: [Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/trader-manipulates-city-weather-sensor-165804921.html); [Euronews](https://www.euronews.com/business/2026/04/23/hair-dryer-trick-behind-25000-win-france-probes-potential-weather-data-scam-linked-to-poly)
- Polymarket's Paris markets moved to the Le Bourget airport station on 19 April 2026. Source: [BeInCrypto](https://beincrypto.com/polymarket-hair-dryer-weather-sensor-oracle-problem/) (via search summary)
- Kalshi tightened its weather settlement rules on 3 Sep 2026, citing manipulation concerns after the Paris case. This comes from a search summary; the article itself was blocked. Source: [Prediction News](https://predictionnews.com/story/kalshi-lists-daily-high-temperature-market-for-new-york-city)

### Inferences
- "Be faster to the new model run" looks dead for daily highs. The market moves before the NBM does, not after.
- What is left for a small bot is the end of the day and the fine print: exact station readings, the official-high-versus-hourly-reading gap, the 1am-to-12:59am window, and rounding. These are real but small, and by about 5pm local the market already prices them (log loss 0.03).
- Resting orders on near-certain outcomes is the one edge with a measured number (+0.9%, all categories). It depends on queue position, which a newcomer will not have, and weather was not broken out.
- The settlement source change in Aug 2026 is a possible short-lived edge. If The Weather Company's value sometimes differs from the NWS climate report, a trader who knows the new source best gains for a while. The DEV data (1,316 of 1,317 days matching NWS) suggests the two rarely differ in practice.

### Gaps
- No public, checked case of someone making steady money from settlement quirks or live readings was found. It is all interviews.
- No study measures how fast Kalshi weather prices react to an hourly METAR or to the NOAA Daily Summary Message.
- The exact date and wording of Kalshi's switch to The Weather Company for daily highs could not be confirmed from a Kalshi page.
- Kalshi's 3 Sep 2026 rule change could not be read directly.

---

## Q5. What happened to the edge as volume grew from 2024 to 2026? Has it been competed away?

### Takeaway
Volume grew fast: Kalshi says weather volume is up about 500% on last year, with $564 million traded by July 2026. No study tracks weather edge over time. The indirect signs all point to a tighter market: the favourite-longshot bias was weaker in 2025 across Kalshi, early thin markets were the ones dropped for being too wide, and every 2026 backtest of the simple bot design lost. Claims of how fast edges shrank come from unsourced marketing pages.

### Cited findings
- Kalshi says weather and climate volume is up 500% on a year earlier. It traded $564 million in 2026 by July, passing all of 2025 by March, and expects about $1.1 billion this year. Some outlets call the $1.1 billion a yearly pace, not a full-year total. [Company figures]. Sources: [Benzinga](https://www.benzinga.com/markets/prediction-markets/26/08/61471630/kalshi-teams-with-the-weather-company-expects-1-1b-weather-trading-volume-in-2026) (via search summary); [Techmeme / WSJ](https://www.techmeme.com/260827/p26)
- Over $125 million was bet on weather in the first nine months of 2025, nearly double the 2023 total. Over $234 million had been bet on climate since weather trading began in July 2021. Source: [Atmos (Sep 2025)](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)
- Weather is still small next to sports, which is about half of Kalshi's activity. Source: [Bloomberg via Insurance Journal](https://www.insurancejournal.com/news/international/2026/08/28/883211.htm) (via search summary)
- A volume tracker reports $115 million in weather volume for 24 Sep-23 Oct 2026, "about 0.1%" of the total. These two numbers cannot both be right for a platform Kalshi's size, so this tracker is not trusted here. Source: [DeFi Rate](https://defirate.com/prediction-markets/volume/kalshi/) (via search summary)
- In the Crosier paper, the markets dropped for being too wide or too thin were mostly from 2022-2024. Liquidity improved over time. Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- Across all Kalshi categories, the favourite-longshot bias was weaker in 2025 than in 2021-2024 (2025 slope 0.021, only weakly beyond luck). Source: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- A marketing page says edges on thin Polymarket weather markets (under $10,000 volume) can reach 5-12 points, but shrink to 2-5 points on markets over $50,000. It also says thin books can move 2-4 points against a fill. No data is shown. [MARKETING] Source: [Laika Labs](https://laikalabs.ai/prediction-markets/polymarket-weather-trading-bot) (via search summary)
- Another guide says the general arbitrage window fell from about 12.3 seconds in 2024 to 2.7 seconds in 2026. It is not weather-specific and is unsourced. [MARKETING] Source: [Aurpay](https://aurpay.net/aurspace/openclaw-ai-trading-skills-complete-guide-2026/) (via search summary)
- A Miami trader in Sep 2025 said the money now flowing into these markets far exceeds what any agency spends on forecasting. [ANECDOTE] Source: [Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)
- Every 2026 public-forecast bot test lost: MiguelTheGamer (May-Oct 2026), DEV (Jul-Sep 2026), jattree (Sep 2026), MAXIMUS (live, early 2026). Sources are in Q2.

### Inferences
- The Atmos traders who say they made money all started in 2022 to late 2024, when markets were thinner and wider. The people testing in 2026 all lost. That pattern fits an edge that has been competed away, but it is not proof. Different people, different skill, different methods.
- The market's lead over public forecasts is biggest in winter and in hard-to-forecast cities. If any forecasting edge is left, it is more likely in winter cold-season markets than summer ones. But beating the market there means beating the traders, not the NBM.
- Newer and less-traded series (hourly temperature, rain, newly listed cities, Polymarket's foreign cities) are where thin-market edges would last longest. Kalshi paying a liquidity provider for hourly temperature and rain fits that picture.
- The project's own scan on 25 Oct 2026 found 152 open weather markets, with only daily rain and big-city daily highs actually trading at 1c spreads. That fits the outside evidence: the liquid series are tight, and the others are thin.

### Gaps
- No time-series study of weather-market edge, spread or depth over 2023-2026 was found.
- No independent figure for 2025 full-year Kalshi weather volume was found.
- No data on Polymarket weather volume over time was found.
- No source measures how many bots trade Kalshi weather.

---

## Q6. What do academic and industry studies say about weather derivatives, and about markets versus NWS forecasts?

### Takeaway
The only direct study of Kalshi weather prices against NWS forecasts (Crosier, Sep 2026) finds the market more accurate than every NWS product, by about 10% against the NBM, but only about 3-4% better than a smart blend of public forecasts. Older work on CME temperature futures found those markets broadly efficient and quick to absorb forecasts. No study compares rain market prices with NWS rain probabilities.

### Cited findings
- Crosier (Sep 2026): the market beats NDFD, NBM, LAMP, GFS MOS, HRRR and ECMWF at every check time. Against an out-of-sample blend of all six, the lead is only 3.1%, 4.3% and 3.0%. The last of these passes only the weaker 10% bar. [HARD] Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- Crosier: if the liquidity screens are removed, the market's lead over the blend on the morning of the day is no longer beyond luck. [HARD] Source: [arXiv 2609.23969](https://arxiv.org/html/2609.23969v1)
- Bürgi, Deng and Whelan (2025-2026): Kalshi prices get more accurate as close nears, but show a favourite-longshot bias in every category, including Climate & Weather (details in Q2). [HARD] Sources: [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf); [VoxEU summary](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)
- Chincarini (2009) tested CME heating and cooling degree-day futures in 18 US cities. He found them generally efficient despite thin trading, with risk premiums that do not look like normal speculator pay. [HARD, older]. Source: [EFMA 2009 paper](https://www.efmaefm.org/0efmameetings/EFMA%20ANNUAL%20MEETINGS/2009-Milan/papers/EFMA2009_0595_fullpaper.pdf) (via search summary)
- A Humboldt University study found CME prices for two monthly temperature indexes generally beat forecasts built from weather data. [HARD, older]. Source: [HU Berlin edoc](https://edoc.hu-berlin.de/bitstreams/03f4b6ce-a8a7-4f1f-924d-c6046ff9c98a/download) (via search summary)
- Dorfleitner and Wimmer (2010, Journal of Banking & Finance) found weather forecasts move CME temperature futures prices up to 11 days ahead. [HARD, older]. Source: [Uni Regensburg](https://epub.uni-regensburg.de/9816/2/CMEtalk.pdf) (via search summary)
- Oetomo and Stevenson (2005) found models priced heating-degree futures better than the market, but cooling-degree futures worse. The results are mixed. [HARD, older]. Source: [RePEc](https://ideas.repec.org/a/sae/emffin/v4y2005i2p101-133.html) (via search summary)
- Kalshi's own calibration report (Aug 2026) covers all markets and gives no weather breakdown. Source: [Kalshi News](https://news.kalshi.com/p/prediction-market-calibration-how-accurate-is-kalshi)

### Inferences
- Thirty years of weather-futures research and the one 2026 Kalshi paper agree. Weather markets soak up public forecasts fast. Beating them needs information the public forecasts lack, not a better way of reading the same forecasts.
- The market's small lead over a well-built blend (3-4%) suggests a team using NBM, LAMP and HRRR together, with careful station work, would come close to the market. "Close" is not enough, though: after the spread and the taker fee, a bot that is only as good as the market loses money.

### Gaps
- No study compares Kalshi rain market prices with the NWS probability of precipitation. This was searched for and not found.
- The CME weather-futures studies were read only through search summaries, not in full.
- No academic study of Polymarket weather markets was found.
