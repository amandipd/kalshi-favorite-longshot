# The weather crowd beats every free forecast

*Research synthesis, 25 Oct 2026. Desk research only. Nothing was built or traded, and the live bot was not touched.*

We can build a Kalshi weather bot cheaply, and free data gives decent probabilities. But a bot that tries to out-forecast the market will very likely lose money. All the data it needs is free. The settlement rules can be read down to the station and the minute. The problem is the competition. A September 2026 study compared Kalshi's daily-high prices with six free forecasts. The prices missed the true high by about 10% less than the best one. That is the National Blend of Models (NBM) from NOAA, the US weather agency ([Crosier 2026](https://arxiv.org/html/2609.23969v1)). Three 2026 backtests of forecast-driven bots lost 7% to 38% of the money staked. Two small real-money bots lost too. No public weather bot shows audited profit. One narrow question is still open, and it suits our current bot. Late in the day, do heavy favourites (the likely side) win more often than their price says, after fees? Kalshi data from 2021 to April 2025 hints yes, but only before fees. Our own October test of the same idea on hourly temperature markets failed. **My advice: skip the forecast bot.** Instead, run one desk-only backtest of our favourite rule on daily rain and big-city daily highs. Freeze the rule first. Then use a train/test split (build the rule on older data, score it once on newer data). Nothing should go live before the 6-week test ends on 27 Nov.

## Free public data covers everything a model needs

**The answer key is free and arrives the same day.** Kalshi's daily markets settle on the National Weather Service (NWS) Daily Climate Report (CLI: the official daily high, low and rain total for one weather station). The Iowa Environmental Mesonet (IEM, a free university weather archive) serves these reports as clean data. A test pull on 25 Oct 2026 already held that day's Central Park report. Full years go back to 2004 ([IEM CLI JSON](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2026); [2004 test](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2004)). The other options are slower. NOAA's long-term daily archive ran about 3 days behind in a test ([NCEI](https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094728&startDate=2026-10-10&endDate=2026-10-25&dataTypes=TMAX,TMIN,PRCP&units=standard)). The NWS's own API (its data feed for programs) keeps observations for only 7 days ([NWS API docs](https://www.weather.gov/documentation/services-web-api)).

**Only one free source gives real probabilities for the daily high and low.** It is the NBM, the National Weather Service's automatic mix of many weather models. Its station bulletins give a range, not just one number. The probability bulletin lists percentiles of the high. (The 10th percentile is the value the high should beat 9 times in 10.) For Central Park on 26 Oct 2026, it gave an average of 68°F. It expected the high to land between 67°F and 70°F on 8 days in 10 ([NBP file](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20261025/12/text/blend_nbptx.t12z); [MDL text products](https://vlab.noaa.gov/web/mdl/nbm-text-products)). Amazon's public cloud (AWS) keeps every NBM run since 18 May 2020 ([AWS registry](https://registry.opendata.aws/noaa-nbm/); [bucket listing](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=blend.)). IEM keeps a simpler bulletin back to November 2018. It includes the forecast's typical error size ([IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)).

The rest of the free menu mostly gives one number for temperature. Most sources do give a real rain chance (PoP, probability of precipitation: the chance of at least 0.01 inch at a point). The table sums up what matters for a backtest.

| Source | What it gives, in plain words | Past forecasts kept since | Cost |
|---|---|---|---|
| IEM climate reports (CLI) | The official answer: high, low and rain per station | 2004 (Central Park) | Free |
| NBM station bulletins and map-wide grids | A forecast range for the high and low; rain chance for 1, 6, 12 and 24 hours | May 2020 on AWS; Nov 2018 on IEM (simpler bulletin) | Free |
| GFS MOS (older NWS station forecast) | One number for the high and low; a real rain chance | Dec 2003 (IEM) | Free |
| LAMP (NWS station forecast, updated hourly with live readings) | One number, refreshed through the day | Jul 2020 (IEM) | Free |
| Official NWS forecast | One number for the high and low; 12-hour rain chance | 2005 as text (IEM); 2020 as grids (AWS) | Free |
| Raw ensembles from the US (GEFS) and European (ECMWF) models: many runs of one model with small tweaks | A spread of outcomes, not yet adjusted to one station | 2017 (GEFS); Jan 2023 (ECMWF) | Free |
| Open-Meteo (easy one-call weather API) | Many models at one point | Mostly Jan 2024 for honest day-ahead values | Free tier bans commercial use; about $29 or $99 a month to trade |

Sources for the table: [IEM MOS archive](https://mesonet.agron.iastate.edu/mos/), [IEM forecast text archive](https://mesonet.agron.iastate.edu/api/1/nws/afos/list.json?pil=PFMOKX&date=2025-10-25), [NCEI NDFD](https://www.ncei.noaa.gov/node/765), [GEFS on AWS](https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5), [ECMWF on AWS](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5), [Open-Meteo Previous Runs](https://open-meteo.com/en/docs/previous-runs-api), [Open-Meteo pricing](https://open-meteo.com/en/pricing), [Open-Meteo prices](https://openmeteo.substack.com/p/api-subscriptions-for-commercial).

Paid data buys convenience, not better probabilities. The real catch is licences. Open-Meteo's free tier is for non-commercial use, and trading counts as commercial ([Open-Meteo pricing](https://open-meteo.com/en/pricing)). Synoptic, a weather data company, has the same limit on its free tier ([Synoptic pricing](https://synopticdata.com/pricing/)). A live bot can run on NOAA and IEM feeds alone.

**Three things in the data can fool a backtest.** First, the models change. NBM version 5.0 went live on 5 May 2026. A temperature fix followed on 28 Jul 2026 ([MDL NBM versions](https://vlab.noaa.gov/web/mdl/nbm-versions)). IEM's bulletin times moved the same day in May ([IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)). The NAM model and its station forecasts retire with the new RRFS model, now set for 3 Nov 2026 ([SCN 26-48](https://www.weather.gov/media/notification/pdf_2026/scn26-048_Updated_RRFS_and_REFS_Implementation.aaf.pdf)). West Palm Beach's station code changed from KPBI to KDJT around 5 Oct 2026 ([SCN 26-88](https://www.weather.gov/media/notification/pdf_2026/scn26-88_LAMP_GFSMOS_KDJT.pdf)). A backtest across these dates mixes different forecasts. Second, one popular archive cheats by accident. Open-Meteo's Historical Forecast API stitches together the first hours of each newest run ([Open-Meteo docs](https://open-meteo.com/en/docs/historical-forecast-api)). That looks far better than any forecast you could have traded on a day ahead. Third, forecast windows don't match the market's day. The NBM's "daily high" covers only daytime hours. The market's day runs midnight to midnight. On 4.6% of days the high fell outside the daytime window, for example at night before a cold front ([Crosier 2026](https://arxiv.org/html/2609.23969v1)).

## Settlement hangs on one airport, a standard-time day and whole degrees

### The source changed in August, but the number did not

Since mid-August 2026, the daily high, daily low and daily rain markets settle "according to The Weather Company" ([Kalshi API, KXHIGHNY rules](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open); [series list](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)). But each rule still names one NWS climate-report station, such as CLINYC for Central Park. Kalshi's notice says The Weather Company uses the NWS as its main source ([WeatherEdge blog, quoting Kalshi](https://www.prilo-weatheredge.com/blog/kalshi-weather-company-settlement-still-nws)). So in practice the answer is still the NWS climate-report number. One backtest checked this directly. **Kalshi's settled value matched the NWS report on 1,316 of 1,317 city-days**, from 25 Jul to 22 Sep 2026. That window runs weeks past the switch ([dev.to backtest](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c)). A gap between the two sources is still a small, real risk. We could not read weather.com/kalshi directly, because the page only loads in a full browser.

The sources disagree on several settlement details. The table lists the conflicts and which side to trust.

| Question | What the sources say | What to trust |
|---|---|---|
| When did the switch to The Weather Company happen? | After 12 Aug (the study). 14 Aug (Kalshi market notes; NextPredict). 27 Aug (Turbine guide; also the public announcement day) | 14 Aug: two sources and the market notes agree |
| Do Kalshi's own documents agree? | Live market rules name The Weather Company. The filed rulebook (Dec 2025) and help center (Jul 2026) still say NWS | The live rules text in each market |
| Does rain still settle on the NWS? | One guide says yes. The live rain rules name The Weather Company | The live rules. The number is the NWS report either way |
| Does a "trace" of rain (too little to measure) count as rain? | Earlier notes left it open. The live rule says trace and missing data count as 0 inches | Trace means No |
| When does trading stop? | Rule text says 11:59 PM local. The API close is midnight standard time, which is 1:00 AM in summer | The API close time |
| Do hourly airport readings match the official high? | One practitioner says 100%. Our 2024–2025 check says exactly on only 32–43% of days | Our check (see below) |
| How does the station store temperature? | One unofficial site says tenths of °C. The NWS says whole °F | The NWS |

Sources for the table: [Crosier 2026](https://arxiv.org/html/2609.23969v1); [WeatherEdge blog](https://www.prilo-weatheredge.com/blog/kalshi-weather-company-settlement-still-nws); [NextPredict](https://nextpredict.io/prediction-markets/weather/); [Turbine guide](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026); [Gizmodo](https://gizmodo.com/kalshi-teams-up-with-the-weather-co-on-markets-that-are-nearly-impossible-to-insider-trade-2000803871); [GLOBALTEMPERATURE rulebook](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf); [Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets); [KXRAIN rules](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open); a practitioner's write-up (not linked); [NWS Phoenix](https://www.weather.gov/psr/HiResASOS); [clilax.com](https://www.clilax.com/).

**Each market settles on one station, and the city name can mislead.** The table shows the traps that matter most ([Kalshi API, market rules](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793077199&max_close_ts=1793077201&limit=1000); [IEM station list](https://mesonet.agron.iastate.edu/nws/clitable.php); [AirlineGeeks](https://airlinegeeks.com/?p=100577)).

| City | Kalshi temperature station | The trap |
|---|---|---|
| New York | Central Park | Not LaGuardia or JFK. Polymarket uses LaGuardia |
| Chicago | Midway airport | Kalshi's Chicago rain market uses O'Hare |
| Los Angeles | LAX airport, on the coast | Not downtown |
| Houston | Hobby airport | Not Bush Intercontinental |
| Dallas | Dallas/Fort Worth airport | Polymarket uses Love Field |
| Austin | Austin-Bergstrom airport | Not Camp Mabry |
| West Palm Beach (rain only) | Code CLIDJT | Airport renamed July 2026; code changed from PBI |

### The day runs on standard time and settles the next morning

The market's "day" is midnight to midnight local standard time (LST: the clock with no daylight saving shift). In summer, that means 1:00 AM to 12:59 AM by the wall clock ([Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets); [IEM](https://mesonet.agron.iastate.edu/nws/clitable.php)). So the first hour after midnight belongs to the day before. This matters most for daily lows. A cold front at 12:30 AM in summer sets the previous day's low. Trading runs to the end of that day. That is midnight standard time in each city, which is 1:00 AM on the summer clock ([Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)).

The answer comes from the overnight climate report. It is issued between 12:30 and 5:00 AM local time ([NWS Burlington](https://weather.gov/btv/product_descriptions)). Kalshi then settles at the first 7 or 8 AM Eastern after it. For example, all New York markets for 24 Oct settled at 7:18 AM on 25 Oct ([Kalshi API, KXHIGHNY-26OCT24](https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=KXHIGHNY-26OCT24&limit=20)). The afternoon report, stamped "valid as of 4 PM", is not the final number. Corrections after settlement don't count ([GLOBALTEMPERATURE rulebook](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)). If temperature data is missing, Kalshi picks a "last fair price" by its own judgment. **If rain data is missing, it counts as zero, so No wins** ([KXRAIN rules](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)).

Each city-day of highs or lows has six contracts. Four cover two whole degrees each, both ends included, such as 74°F to 75°F. Two tails cover "73° or below" and "76° or above" ([Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)). Rain is one Yes/No contract per city, in 35 cities on 26 Oct 2026. Yes needs more than 0 inches, which means at least 0.01 inch. Melted snow and sleet count ([RAINGLOBALPERIOD rulebook](https://assets.kalshi.com/regulatory/product-certifications/RAINGLOBALPERIOD.pdf)). **The rain market closes early once rain falls** ([KXRAIN rules](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)). So nobody can buy a "Yes" that is already known. "No" is only certain when the day ends.

### Rounding makes the official high beat the hourly readings

**The official high often beats every hourly reading.** Airport stations (ASOS: the automated airport weather station) keep temperature internally in whole °F. The daily high is the highest of short running averages ([NWS Phoenix](https://www.weather.gov/psr/HiResASOS)). The hourly report (METAR: the coded airport weather report) is only a snapshot, taken near 51 to 53 minutes past the hour. Its precise part (the T-group: the reading in tenths of a degree Celsius) misses peaks between hours ([IEM](https://www.mesonet.agron.iastate.edu/onsite/news.phtml?id=1469)). Those peaks show up in the "6-hour maximum" group. It is sent with the reports near 00, 06, 12 and 18 UTC (world standard time). The 5-minute reports carry whole °C only. Converting them back can show a high 1°F too warm ([NWS Phoenix](https://www.weather.gov/psr/HiResASOS)).

Our own check on 2024–2025 IEM data shows the size of the gap ([IEM CLI](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024); [IEM ASOS](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py); [check scripts](<../research_notes/Kalshi weather bot feasibility/scripts/>)). The official high averaged 0.7 to 0.8°F above the highest hourly reading. It was at least 1°F higher on 57% of days in New York, 68% in Miami and 64% in LA. Adding the 6-hour maximum groups closed the gap. **With them, we matched the official high exactly on 94% to 99% of days in 2025.** A separate 204-day check found the same pattern ([MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)). This has caught traders out. On 9 Jun 2026, Chicago Midway settled at 88°F, while the widely seen afternoon report said 87°F. The evening 6-hour maximum showed 88°F ([WeatherEdge blog](https://www.prilo-weatheredge.com/blog/why-chicago-midway-settled-88-not-87)). That case comes from a vendor blog, so treat it as one example.

### Fees are standard, and other venues settle differently

All 458 weather series charge the standard taker fee (Kalshi's charge for trading, biggest near 50c) ([Kalshi series list](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)). The fee is 7% × price × (1 − price) per contract ([Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)). No weather discount or rebate was found. Sources disagree on maker fees (fees for posting an order that waits to be filled). Most markets charge none, but some sources quote a quarter of the taker rate. The table shows what the taker fee means for a buyer.

| Price paid | Fee per contract | Win rate needed just to break even |
|---|---|---|
| 10c | 0.63 cents | 10.6% |
| 50c | 1.75 cents | 51.8% |
| 90c | 0.63 cents | 90.6% |
| 95c | 0.33 cents | 95.3% |

A 1-cent spread (the gap between the buy and sell price, what it costs to get in) adds about half a cent more. That is measured against the mid-price (the midpoint between the buy and sell prices).

The hourly temperature markets for Miami and New York are a different product. They settle on a Kalshi index that averages several airports' 1-minute readings ([MIAWINDEX](https://assets.kalshi.com/regulatory/product-certifications/MIAWINDEX.pdf); [NYCWINDEX](https://assets.kalshi.com/regulatory/product-certifications/NYCWINDEX.pdf)). The New York index uses eight stations and leaves out Central Park. A single-station model will be off there. Polymarket's daily temperature markets differ too. They use the highest hourly reading only, at a different airport, on the local clock day, including daylight saving ([Polymarket rules](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-26-2026)). So the two venues are not the same bet. Arbitrage between them (locking in a sure profit across venues) is not exact.

## Every honest 2026 test of a forecast bot lost money

### Hard evidence: the crowd out-forecasts NOAA

The strongest evidence is a September 2026 study of 7,590 city-days of Kalshi daily-high markets in 7 cities ([Crosier 2026](https://arxiv.org/html/2609.23969v1)). It turned each day's bracket prices into one forecast of the high. Then it compared that with six public forecasts. **The market won at every time checked.**

| Forecast | Typical size of a miss, day before at 11 AM Eastern (RMSE, °F) | Typical size of a miss, morning of the day (RMSE, °F) |
|---|---|---|
| Kalshi market prices | 2.44 | 1.88 |
| Best blend of all six public forecasts, built only on past days | 2.45 | 1.90 |
| NBM, the best single free forecast | 2.70 | 2.12 |
| Official NWS forecast | 2.83 | 2.33 |
| ECMWF (European model), with its average error removed | 3.31 | 2.68 |

RMSE (root-mean-square error) is the usual size of a miss, with big misses counting extra. Lower is better. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).

On the morning of the day, the market's typical miss was about 11% smaller than the NBM's. The best blend came within about 3%. Even that small gap is only weakly beyond luck. It passes a loose 1-in-10 test, not the usual 1-in-20 bar. The market's lead was biggest from November to June, at 10–16% over the NBM. It shrank to 1–4% from July to October. Miami was the one city where the market did not beat the NBM.

**The NBM follows the market, not the other way round.** The NBM moves toward the market about four times as far as the market moves toward the NBM. Both effects are far beyond luck (t = 15.9 and 11.9; about 2 is the usual bar). Prices don't jump when a new NBM run posts ([Crosier 2026](https://arxiv.org/html/2609.23969v1)). In plain words, the crowd already knows what the next forecast will say. Racing to trade on new model runs is a dead end. The study does not measure fees, fills or profit, so it can't say whether favourites are mispriced.

### Self-published tests: forecast bots lose after costs

Every 2026 test that turned free forecasts into bracket chances and traded at the ask (the price you pay to buy right now) lost money. None is peer-reviewed. But they agree with each other and with the study above.

| Test | Kind of evidence | What happened |
|---|---|---|
| MiguelTheGamer: Kalshi NYC, Chicago, Miami, May–Oct 2026 | One person's backtest, method shown | Market more accurate in every test. Trades at the ask lost 9–14% of money staked. Mixing model and market never beat the market alone |
| DEV Community post: 24 Kalshi cities, Jul–Sep 2026 (author sells a $29 product) | One person's backtest, method shown | Buying Yes lost 38% of money staked over 689 trades. Buying No lost 7% over 787 trades. Every price band lost |
| jattree: Polymarket, 24 cities, 2026 | Backtest plus real money, self-reported | Simulated trades lost about 14% each, give or take 5%. Live money fell from $210 to $52, partly from bugs |
| MAXIMUS: Kalshi daily highs, early 2026 (blog with a tip jar) | Real money, self-reported | 0 wins and 32 losses; "a few hundred dollars" lost |

Sources: [MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest); [dev.to](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c); [jattree](https://github.com/jattree/weather-edge); [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/).

The DEV test makes the gap concrete. It used the Brier score (the average squared miss of a probability; 0 is perfect, lower is better). The market scored 0.120. The model scored 0.147. Just guessing the usual frequency scored 0.154. So **the model barely beat a blind guess, while the market was far better.** When the model said 50–70% and the market disagreed, the event happened only 25–36% of the time ([dev.to](https://dev.to/myfirstcodeo/i-backtested-a-forecast-based-model-against-kalshis-temperature-markets-the-market-won-heres-442c)). MAXIMUS blamed fat tails (big misses happen more often than a bell curve predicts). Its "90% sure" trades really won about 75–80% of the time.

**By late afternoon, prices are already near the answer.** A model with live airport readings still lost to the market at 11 AM, 1 PM, 3 PM and 5 PM. By 5 PM, prices in New York and Chicago were almost certain and almost always right ([MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)). On the evening of 25 Oct 2026, New York's winning bracket traded at 99–100c ([Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)). That is a pinned price (a price already equal to the answer, so useless as a forecast). One self-published calibration check (whether a 70c price really wins 70% of the time) fits this picture. It covered 8,494 New York markets. Prices were off from real win rates by only about 1.6 percentage points on average (ECE = 0.016). That check gives no dates and ignores fees ([Zerve](https://www.zerve.ai/gallery/85cce830-f612-4b23-8b78-34d7da65a2c6)).

### The one hopeful sign: weather favourites, before fees

One academic study gives a reason for hope, and it fits our bot. Bürgi, Deng and Whelan studied Kalshi prices from 2021 to April 2025 ([GWU working paper](https://www2.gwu.edu/~forcpgm/2026-001.pdf)). They found the favourite-longshot bias (cheap unlikely bets are overpriced, heavy favourites underpriced) in every category, including weather. Their fitted line for weather says average profit before fees rises with price. Our reading of that line puts the break-even near 32c. **A 95c weather contract made about 1.9 cents of edge (profit per contract, in cents) before fees.** That is about 2 cents of profit for every dollar bet. The taker fee at 95c is about 0.3 cents, so a thin edge might survive. The bias in weather was milder than across Kalshi as a whole.

Three things cut against it, and this is the main conflict in the evidence. The study ends in April 2025, and the bias had weakened across Kalshi by 2025. It used last-traded prices, not the ask a taker pays. And newer tests disagree. A 2026 check across all Kalshi categories found that buying favourites at the ask lost 2% to 8% after fees ([MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)). **Our own October test of the same idea on Kalshi hourly temperature markets failed.** At 30 minutes before the close, 36 favourites lost against 33.3 losses implied by their prices (the number the prices predicted). That came to −0.88 cents for every dollar bet ([Oct 18 backtest](<Other markets backtest Oct 18.md>)). No source has tested a favourites-only rule on daily rain or daily highs, after fees, on recent data. That is the open question.

### Anecdotes and ads: the success stories

Everything else positive is an anecdote or an ad. A 2025 magazine feature profiles Kalshi weather traders who say they made a living. All of them started between 2022 and 2024, when markets were thinner ([Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)). Famous Polymarket wins come from screenshots, such as a reported $1.11 million on a London longshot (the unlikely side) ([KuCoin/Odaily](https://www.kucoin.com/news/flash/traders-on-polymarket-earn-millions-by-predicting-weather)). Those are survivor stories. The hard data says cheap longshots lose on average. The most-starred open-source bot, with 793 stars, says it trades no real money ([suislanchez](https://github.com/suislanchez/polymarket-kalshi-weather-bot)). Dozens of paid "edge finder" tools show no audited results.

### Where any edge might hide, and who is already there

People who describe a working edge point to three places, all small. One is the fine print near the close: the 6-hour maximum group, rounding, and the 1 AM day boundary. The second is resting orders as a maker (someone who posts an order and waits, instead of paying the taker fee). Across Kalshi, resting orders on the 97–99c side made about +0.9% of the money risked. Most of that went to traders already first in line, and weather was not broken out ([MiguelTheGamer](https://github.com/MiguelTheGamer/kalshi-weather-backtest)). The third is thin, newly listed series.

All three face strong rivals. Kalshi says weather volume is up about 500% on a year ago, with $564 million traded by July 2026. Those are company figures ([Benzinga](https://www.benzinga.com/markets/prediction-markets/26/08/61471630/kalshi-teams-with-the-weather-company-expects-1-1b-weather-trading-volume-in-2026)). Kalshi pays one firm each to keep orders posted in daily rain and hourly temperature, through 31 Dec 2026 ([Kalshi liquidity program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program)). One review says that program ended on 1 Sep 2026, but the help page looks newer ([SI](https://www.si.com/prediction-markets/reviews/kalshi)). One bot's post-mortem says faster bots reacted to NWS updates within seconds ([Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/)). Traders in the magazine piece scraped readings faster than others ([Atmos](https://atmos.earth/art-and-culture/the-climate-casino-inside-the-markets-betting-on-our-planets-future/)). A slow bot faces adverse selection (getting picked off by someone who knows more than you).

## A first model takes days; an honest backtest takes care

### Build order: answer key, NBM baseline, then fix the width

If we build a model, the standard recipe is simple. Step one is the answer key: IEM climate reports for the exact station in each market's rules. Step two is a baseline. Take the NBM's average and spread for the high, draw a bell curve, and read off each bracket's chance. Step three is a fix called EMOS (ensemble model output statistics: a correction that adjusts a forecast's average and width using its recent misses). Fit it on a rolling 40 to 60 days ([Gneiting et al. 2005](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf)). This is a few days of Python work.

**Width matters as much as the middle.** Kalshi brackets are 2°F wide. Good day-ahead forecasts still miss by 2.4 to 2.7°F typically. A model that is too sure of itself will badly misprice the middle brackets. In the classic EMOS study, the raw forecast's middle-two-thirds range caught the truth only 29% of the time. It should have caught it 67% of the time. Fixing only the average barely helped. Fitting the width brought it to 69% ([Gneiting et al. 2005](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf)). Fancier tools, such as neural networks, cut errors by about another 10%. They need years of data to do it ([Rasp & Lerch 2018](https://arxiv.org/pdf/1805.09091v1)).

### Same-day updates start from the high so far

During the day, a model should start from the high so far. The final high is the high so far plus whatever rise is left. Our 2024–2025 check shows how fast the answer firms up. The table gives the share of days when the official high ended no more than 1°F above the highest reading so far ([IEM CLI](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024); [IEM ASOS](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py)).

| By this standard-time hour | New York (Central Park) | Miami | Los Angeles (LAX) |
|---|---|---|---|
| 10 AM | 13% of days | 8% | 14% |
| Noon | 30% | 44% | 58% |
| 2 PM (3 PM on the summer clock) | 72% | 79% | 82% |
| 4 PM | 87% | 87% | 85% |

A late rise of 3°F or more after 2 PM standard time still happened on 10% of New York days. It happened on 5% of Miami days and 4% of LA days. New York winters are the hardest. The late rise varied almost twice as much in December to February as in June to August. **The "high so far" must include the 6-hour maximum groups.** Without them, it runs about 0.7 to 0.8°F low. That is a third to half of a bracket.

### Rain needs a whole-day chance

Rain needs its own model. The NWS rain chance is for 0.01 inch or more at a point, usually over 12 hours ([NWS Albany](https://weather.gov/media/aly/FactSheets/WhatDoesProbabilityofPrecipitationMean.pdf)). That matches Kalshi's rule, since a trace counts as No. But Kalshi's window is the whole standard-time day. A full day is wetter than either half. In one large study, 12-hour rain events happened 22% of the time, and 24-hour events 31% ([Bickel et al. 2011](https://utw10181.utweb.utexas.edu/Papers/NWS_Calibration.pdf)). The same study found NWS rain chances ran a little low.

The standard fix is logistic regression (a formula that turns forecast inputs into a probability, fitted on past outcomes) ([Hamill et al. 2004](https://psl.noaa.gov/psd1/pubs/2004/details/hamill_01abs.html)). Feed it the NBM's 6-hour or 1-hour rain chances, stitched into the standard-time day. Don't multiply two 12-hour chances as if they were unrelated. Wet spells come together, so that overstates the daily chance. For scale, Central Park and Miami each had measurable rain on 34% of days in 2024–2025. LAX had it on 10% ([IEM CLI](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024)). Trace-only days count as No. They were 11% of days in New York and Miami.

### Six rules for an honest backtest

Score forecasts with tools that can't be gamed. Use the Brier score for each contract. Use log loss (a score that punishes confident wrong calls very hard) as a second check ([scoringrules](https://github.com/frazane/scoringrules)). Check calibration (whether a 70c price really wins 70% of the time) with a simple chart of forecast against outcome. The yardstick is the market price at the same moment, not the long-run average. One practitioner warns that beating the long-run average does not mean making money at market prices (a practitioner's write-up, not linked). A trade only makes sense when the model's chance beats the ask plus the fee.

The backtest is where most weather bots fooled themselves. Six rules keep it honest. **First**, use forecasts exactly as published, stamped by release time, not model run time. IEM stores its bulletins as issued ([IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)). **Second**, take prices from Kalshi's historical endpoints ([Kalshi historical data docs](https://docs.kalshi.com/getting_started/historical_data)). Fill at the real ask, with real depth (how much money you can trade before moving the price), never at the mid-price. **Third**, read each market's own station and source from its rules. Check every settled value against the climate report. **Fourth**, use a train/test split. Build on older data, then score once on the next 12 months, so every season gets tested ([Rasp & Lerch 2018](https://arxiv.org/pdf/1805.09091v1)). **Fifth**, count bets as clustered (bets on the same event move together, so they count as one, not many). All brackets of one city-day are one bet. One storm can hit several cities on one date ([Crosier 2026](https://arxiv.org/html/2609.23969v1)). **Sixth**, finish with leave-one-out (drop the biggest contributor and check the result survives), by city and by month.

The traps are well known. One practitioner reports a fake "+1,640%" backtest from a bracket-edge mistake: both ends of a bracket count, not just one. The same source says counting days in UTC instead of standard time cost about 14 points of accuracy. It also says assuming fills at 1c asks overstated profit about 23 times (the same write-up). Those figures are unverified. But one real bot did lose money from a UTC-day bug and three wrong stations ([jattree](https://github.com/jattree/weather-edge)). History is also short in places. New York and Chicago daily-high markets go back to January 2022, but LA only to January 2025 ([Crosier 2026](https://arxiv.org/html/2609.23969v1)). The current daily rain rulebook was filed only in June 2026, so rain history may be just months long ([RAINGLOBALPERIOD rulebook](https://assets.kalshi.com/regulatory/product-certifications/RAINGLOBALPERIOD.pdf)). Check the first listing date before planning a split.

## Thin books, rule changes and faster rivals are the main risks

| Risk | Why it matters | How to guard against it |
|---|---|---|
| No edge after costs | The market beats free forecasts. Every 2026 forecast-bot test lost | Test only the favourite rule. Demand a profit on data the rule never saw while being built, after fees |
| Thin order books (few offers waiting to be filled) | Hourly temperature had only about $50 on offer at the favourite's price. Daily lows trade 1,000–18,000 contracts a day, with 6–18c spreads | Record real order books before trusting any backtest |
| Rule and source changes | The source switched in Aug 2026. Kalshi's documents lag. Kalshi sets a "last fair price" if data is missing | Read each market's rules text. Check every settled value |
| Station and day mistakes | A wrong station, a UTC day or a missed 6-hour maximum flips outcomes | Build station and day handling from the rules, writing the tests first |
| Losses that come together | One storm hits many cities. All brackets of a city-day move together | Cap the total stake per date, not per market |
| Faster rivals | Bots react within seconds. A paid firm posts orders in rain | Avoid any plan that depends on speed |
| Sensor tampering | A Paris airport sensor was likely heated to move a Polymarket market in April 2026 | Watch for sudden spikes at the station |
| Model upgrades | NBM 5.0 (May 2026); NAM retirement (Nov 2026) | Split results by model version. Refit after upgrades |

Sources: [Depth check](<Depth check - temperature and gas.md>); our 25 Oct live scan of all 458 weather series; [GLOBALTEMPERATURE rulebook](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf); [jattree](https://github.com/jattree/weather-edge); [Northlake Labs](https://www.northlakelabs.com/max/blog/kalshi-weather-postmortem-and-pivot/); [Kalshi liquidity program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program); [Euronews](https://www.euronews.com/business/2026/04/23/hair-dryer-trick-behind-25000-win-france-probes-potential-weather-data-scam-linked-to-poly); [NPR via STLPR](https://www.stlpr.org/npr/2026-04-23/french-police-probe-suspected-weather-device-tampering-after-odd-polymarket-bet); [MDL NBM versions](https://vlab.noaa.gov/web/mdl/nbm-versions); [SCN 26-48](https://www.weather.gov/media/notification/pdf_2026/scn26-048_Updated_RRFS_and_REFS_Implementation.aaf.pdf).

**Favourite-buying has a lopsided payoff.** At 95c, one loss wipes out about 20 wins after fees. At 98c, one loss wipes out about 50. So a few extra losses decide the whole result. That is why the test needs many independent days, not many contracts.

**Depth for the liquid weather series is still unmeasured.** Our 25 Oct scan found only two kinds of weather market with real trading (our 25 Oct live scan of all 458 weather series). Daily rain traded about 480,000 contracts in 24 hours across all its cities. Each contract pays $1 if right. Miami, New York and LA daily highs traded 110,000–150,000 each. Other cities' highs traded 3,000–55,000. Spreads were about 1 cent. Busy trading does not prove there is money on offer at the favourite's price. Our earlier depth check on hourly temperature found only about $50 there ([Depth check](<Depth check - temperature and gas.md>)).

## Recommendation: test our favourite rule, skip the forecast bot

**Do not build a bot that tries to out-forecast Kalshi's daily weather markets.** It would be cheap to build, and it would very likely lose. The hard evidence and every honest 2026 test agree.

**Do run one cheap desk test that fits what our bot already does.** The question: late in the climate day, do favourites priced 90c or more win more often than their price says, after fees? Daily rain is the best place to look. It is the busiest weather series, and nobody has studied it. Its history may be short, so part of its test may have to use fresh data from November. Big-city daily highs come second. Skip daily lows, hourly temperature, and the monthly, snow and climate series. They are thin, with wide spreads. Skip Polymarket weather too, since it is a different bet.

My honest guess is that this test fails. Our hourly temperature test failed in October. Sports failed too. The 2025 data shows the bias fading. But the test costs only a few days of desk work on free data. A clean fail closes the weather question for good. A pass would add small money, not a second engine. For scale, the gas rule that passed was first put at about $4 a day at $10 bets ([Oct 18 backtest](<Other markets backtest Oct 18.md>)). Our 25 Oct recheck cut that to about $28 a month under the bot's 10% cap on money per window.

| Step | What to do | Done when |
|---|---|---|
| 1. Freeze the rule | Write the rule down before looking at any data. For example: favourite side priced 90–99c, spread 2c or less, at two fixed checkpoints late in each climate day | The rule is committed to the repo with a date |
| 2. Pull the data slowly | Settled daily rain and big-city daily-high markets with price history, from Kalshi's historical endpoints. IEM climate reports and hourly reports for each station. Check for other running Kalshi fetches first: they share one rate limit (Kalshi's cap on requests per minute) | Every market has its station, source and settled value stored |
| 3. Check settlement | Match each settled value to the NWS climate report. Report Aug 2026 onward separately | Every mismatch is counted and explained |
| 4. Score the plain rule | Highs: build on data up to Oct 2025, then score once on Nov 2025–Oct 2026, so every season is tested. Rain: split its shorter history the same way, or score on fresh data from November. Report losses against the number the prices implied, cents of profit for every dollar bet at the ask after fees, and a 95% range (the range the true number is probably in) clustered by date | The bottom of the range is above zero, and it survives leave-one-out by city and month |
| 5. Score one filter | Add one observation check: skip favourites that the high so far (with 6-hour maximums) or the rain so far puts at risk. Same split, scored once | Same bar as step 4 |
| 6. Measure depth | Record real order books for rain and three big-city highs at the checkpoints, for 2 weeks | Median money on offer at the favourite's price supports $25 bets |
| 7. Decide after 27 Nov | Nothing goes live before the 6-week test ends | Adopt only if step 4 or 5 passes and step 6 passes |

Build the NBM probability model only if step 4 or 5 passes. Even then, use it only to skip bets, not as a reason to trade on its own. Don't pay for data. NOAA and IEM cover everything this plan needs.

## Conclusion

The weather crowd has become a better forecaster than NOAA's best product, and NOAA's blend now drifts toward the crowd. That changes the question. It is no longer "can we forecast weather better?" It is "does the crowd misprice near-certainty?" That is a question about traders, not about weather. Our crypto edge is that kind of edge. Sports and hourly temperature have now failed the same test. So daily rain and highs are a clean check. Is the favourite edge a habit across Kalshi, or a quirk of crypto?

The fine print decides more contracts than the forecast does. A standard-time day, a 6-hour maximum group and one named airport flip outcomes that a better model would never catch. Any weather code we write should be built around those rules first, and the forecast second.
