# Modeling and backtest methods: turning weather forecasts into calibrated probabilities for Kalshi daily high, low and rain markets

Scope: how to build a first probability model for one weather station's daily high, daily low and "rain today", and how to test it honestly against past outcomes and past Kalshi prices. Researched 25 Oct 2026.

Plain-words key used below:
- **Calibration**: whether a 70% forecast really comes true 70% of the time.
- **Post-processing**: a statistics layer that corrects a weather model's raw output using its past errors.
- **CRPS (continuous ranked probability score)**: a score for a whole forecast distribution. Lower is better. It is in the same units as the forecast (°F or °C), and for a single-number forecast it equals the plain average miss.
- **RMSE (root mean square error)**: the typical size of a miss, with big misses counting extra. **MAE (mean absolute error)**: the plain average size of a miss.
- **Out-of-sample / held-out**: tested on data the rule never saw while being built.
- **LST (local standard time)**: clock time with no daylight saving shift.

---

## 1. Which post-processing methods are simplest and most effective for a single station's daily high and low, and how good are they?

### Takeaway
The simple method is also the standard one. Take a good forecast, correct its average error over a recent window, and fit a bell curve (a normal distribution) whose width is tuned to minimize CRPS. This is called EMOS or NGR. It fixes most of the miscalibration in raw model output. Fancier tools (boosting, neural networks) cut errors by another 10-20%, but they need years of data. The bigger finding: the Kalshi market's own implied forecast of the high already beats NOAA's best public forecast (the National Blend of Models, NBM) by about 10%. So a model built only on public forecasts is unlikely to beat the market on the middle of the distribution.

### Cited findings

**EMOS / NGR (the recommended starting point)**
- EMOS (ensemble model output statistics) gives a normal distribution. Its middle is a bias-corrected weighted average of the forecast inputs. Its spread (variance) is a straight-line function of how much the inputs disagree (ensemble variance). The weights are fitted by "minimum CRPS estimation", which picks the values that give the best CRPS on the training data. Source: [Gneiting et al. 2005, Monthly Weather Review](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).
- The same method is also called non-homogeneous Gaussian regression (NGR): "Gaussian" means bell curve, "non-homogeneous" means the width changes day to day. Source: [IMPROVER (UK Met Office) docs](https://improver.readthedocs.io/en/stable/improver.calibration.emos_calibration.html).
- How much it helps, for 48-hour surface temperature forecasts in the US Pacific Northwest (spring 2000). Source: [Gneiting et al. 2005, Table 7](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf):

| Forecast | How often truth fell in the middle-two-thirds range (should be 66.7%) | CRPS (°C/K, lower is better) |
|---|---|---|
| Raw ensemble | 28.7% (far too narrow) | 2.07 |
| Bias-corrected ensemble | 31.1% (still far too narrow) | 1.89 |
| EMOS | 68.6% (about right) | 1.61 |

- So the raw model was badly over-confident. Correcting only the average error barely fixed that. Fitting the width is what fixed it. The single-number forecast also improved a little: the average miss (MAE) went from 2.49 (raw mean) to 2.28 (bias-corrected) to 2.23 (EMOS). Source: [Gneiting et al. 2005, Table 6](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).
- Training window: the paper used a sliding window of the 40 most recent days. Windows shorter than 30 days gave ranges that were too narrow. Beyond about 45 days, skill fell slowly "as a result of seasonally varying model biases". Source: [Gneiting et al. 2005](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).
- Fitting by minimum CRPS gave sharper and better-calibrated ranges than fitting by maximum likelihood (the textbook method). Maximum likelihood gave ranges that were too wide: 72.7% coverage against a 66.7% target, versus 68.6% for minimum CRPS. Source: [Gneiting et al. 2005, Table 2](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).

**Fancier methods, and how much more they buy**
- Germany, 537 stations, ECMWF 50-member ensemble, 2-m temperature, tested on all of 2016. Mean CRPS in °C. Source: [Rasp & Lerch 2018, Table 2](https://arxiv.org/pdf/1805.09091v1):

| Method | Trained on 2015 only | Trained on 2007-2015 |
|---|---|---|
| Raw ensemble | 1.16 | 1.16 |
| EMOS, one model for all stations | 1.01 | 1.00 |
| EMOS, separate model per station | 0.90 | 0.90 |
| Per-station EMOS + boosting (a method that adds extra inputs one at a time) | 0.85 | 0.80 |
| Quantile regression forest (a tree-based method) | 0.95 | 0.81 |
| Neural network with extra inputs + station identity | 0.82 | 0.78 |

- Reading that table: one global EMOS cut CRPS by 13%. Fitting per station cut it about 10% more. The best neural network cut another ~13% beyond per-station EMOS, but only with 9 years of training data. The tree and boosting methods gained most from the longer history. Source: [Rasp & Lerch 2018](https://arxiv.org/pdf/1805.09091v1).
- Per-station EMOS trained on a window of days around today's date from all previous years scored 0.88, slightly better than 0.90. Source: [Rasp & Lerch 2018](https://arxiv.org/pdf/1805.09091v1).
- Bayesian model averaging (BMA): the forecast is a mix of bell curves, one centred on each bias-corrected input model, weighted by each model's past accuracy. It was first built for roughly bell-shaped errors such as surface temperature. Sources: [Raftery et al. 2005 (PDF)](https://w2w.meteo.physik.lmu.de/publications/previous_publications/gneiting_2005b.pdf); [record](https://heibib.ub.uni-heidelberg.de/search/Record/1428576878).
- Analog ensemble: find past days when the model's forecast looked like today's, and use what actually happened on those days as the forecast spread. Tested on 0-48 hour 2-m temperature and wind at 550 US stations (April-July 2011), with 12-15 months of training. It was reliable and matched or beat a 21-member ensemble and logistic regression. Source: [Delle Monache et al. 2013](https://opensky.library.ucar.edu/islandora/object/articles%3A12922).
- Small training sets are enough for short-range temperature. Long reforecast archives mainly help longer leads and heavy precipitation. Source: [Hamill & Hagedorn, ECMWF](https://www.ecmwf.int/sites/default/files/elibrary/2007/15580-exploring-ensemble-forecast-calibration-issues-using-reforecast-data-sets.pdf).
- A 2021 review covers the full range, from basic bias correction to methods that adjust the whole distribution. It lists "handling model changes" as a main open problem. Source: [Vannitsem et al. 2021, BAMS (preprint)](https://arxiv.org/abs/2004.06582).

**NBM already publishes a distribution for the high and low**
- The NBM station bulletins carry the high/low (TXN) and its standard deviation (XND, a measure of spread in °F) in the 3-hourly "NBS" and 12-hourly "NBE" bulletins. The probabilistic "NBP" bulletin carries the mean (TXNMN), standard deviation (TXNSD) and the 10th, 25th, 50th, 75th and 90th percentiles of the high/low. These come from quantile mapping (QMD) and cover the lower 48 states and Alaska. Source: [NBM v4.3 text bulletin card](https://vlab.noaa.gov/web/mdl/nbm-textcard-v4.3).
- Probabilistic high/low percentiles and standard deviations were added in NBM v3.2 (Feb 2020) and v4.0 (Sep 2020). Source: [NBM versions](https://vlab.noaa.gov/web/mdl/nbm-versions). v4.0 listed 5th-95th percentiles. Source: [NBM v4.0 elements](https://weather.gov/media/mdl/nbm/docs_v40/All_NBM_v40_Wx_Elements.pdf). v4.2 lists 1st-99th percentiles of the high. Source: [NBM v4.2 elements](https://vlab.noaa.gov/web/mdl/nbm-v4.2-weather-elements).

**How accurate are today's forecasts of the daily high (°F)?**
- The best recent source is a Sept 2026 study of Kalshi high-temperature markets in 7 cities (7,590 city-days, Jan 2022 to 12 Aug 2026). Pooled RMSE in °F at three times. Source: [Crosier 2026, arXiv](https://arxiv.org/html/2609.23969v1):

| Forecast | Day before, 11:00 ET | Day before, 19:00 local | Target day, 13:00 UTC |
|---|---|---|---|
| Kalshi market (implied average) | 2.44 | 2.21 | 1.88 |
| NBM (best public product) | 2.70 | 2.45 | 2.12 |
| LAMP (NWS hourly-updated guidance), de-biased | 2.83 | 2.63 | 2.19 |
| GFS MOS (older NWS statistical guidance) | 3.17 | 2.95 | 2.69 |
| HRRR (NOAA hourly short-range model), de-biased | 3.32 | 3.07 | 2.63 |

- Same study: ECMWF (de-biased) scored 3.31 / 3.16 / 2.68 and NDFD (the official NWS forecast) 2.83 / 2.66 / 2.33. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- The market beat NBM by about 10% overall, and in 6 of 7 cities. Miami was the exception. Miami's NBM error was only 1.6°F the morning before, versus 2.6-3.5°F elsewhere. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- NBM moved toward the market about four times as far as the market moved toward NBM. The market did not jump when NBM updates were posted. Source: [Crosier 2026](https://arxiv.org/abs/2609.23969).
- An out-of-sample combination of all the public products still did not beat the market. The paper lists it at 2.45 / 2.25 / 1.90, with a gap that is "significant only at 10%" (weak evidence by the usual standard). Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- Older single-office figures, for scale only: in Wichita, summer 2000, MOS missed the day-1 high by 3.52°F on average versus 2.43°F for local forecasters. Source: [NWS Central Region ARP 24-05](https://www.weather.gov/media/crh/publications/ARP/arp24-05.pdf). NWS found MOS day-2 forecasts had become about as accurate as day-1 forecasts were 10-15 years earlier. Source: [Ruth et al. 2009](https://www.weather.gov/media/mdl/Ruth2009ThePerformance_rev.pdf).

### Inferences
- A practical first model, in order:
  1. **Baseline**: NBM mean and standard deviation for the high (TXN/XND or TXNMN/TXNSD) → normal distribution → probability for each bracket. This needs no fitting and gives a benchmark.
  2. **EMOS recalibration**: middle = a + b × NBM mean (optionally + c × another model). Spread = sqrt(d + e × NBM variance). Fit a-e by minimum CRPS on a rolling 40-60 day window, or on a window of dates around today's date from past years. This is a few days of work in Python (scipy.optimize plus the closed-form normal CRPS; see section 4).
  3. **Later**: per-station boosting or a quantile regression forest, only once there are 2+ years of archived inputs.
- Kalshi brackets are about 2°F wide, and typical day-ahead errors are about 2-2.7°F RMSE. So the width of the distribution matters as much as its centre. An over-confident model will badly misprice the middle brackets.
- Because the market already beats NBM by ~10%, the edge is unlikely to come from a better day-ahead average. More likely sources: getting the width and tails right, same-day observations (section 3), and the market's price biases (section 4).
- Miami is the easiest city to forecast (NBM error 1.6°F), so the market and NBM are both tight there. That leaves the least room for a model edge.

### Gaps
- No current nationwide NWS figure for day-1 high-temperature MAE in °F was found. The NWS MDL verification pages were not reached.
- No study was found applying EMOS to NBM at Central Park (KNYC), Miami (KMIA) or LAX specifically.
- No dedicated source was found for plain quantile regression on station temperature; only the quantile regression forest numbers above.

---

## 2. How well calibrated is NWS/NBM rain probability, how do you calibrate it, and how does "rain today" differ from PoP?

### Takeaway
NWS "probability of precipitation" (PoP) is the chance of at least 0.01 inch at a point, usually over a 12-hour period. Kalshi's "rain today" is a full-day event (by the station's standard-time calendar day) at one gauge. A full-day chance is higher than either 12-hour chance. Historically NWS PoPs ran a little low. The standard fix is logistic regression: a formula that turns forecast inputs into a probability, fitted on past outcomes. One big open question: whether a "trace" day (rain too small to measure) counts as rain. Trace days were 11% of all days in NYC and Miami in 2024-25.

### Cited findings
- PoP definition: "measurable" means 0.01 inch or more; PoP is the chance at any one point, not the share of the area that gets rain. Source: [NWS Albany fact sheet](https://weather.gov/media/aly/FactSheets/WhatDoesProbabilityofPrecipitationMean.pdf). The period is normally 12 hours unless stated. Source: [NWS Binghamton forecast terms](https://www.weather.gov/bgm/forecast_terms).
- NWS PoP calibration, from almost 13 million PoPs at 734 US stations (Nov 2008-Oct 2010). Source: [Bickel, Floehr & Kim 2011, Monthly Weather Review](https://utw10181.utweb.utexas.edu/Papers/NWS_Calibration.pdf):
  - The NWS under-forecast on average. Example: 3-day warm-season PoPs averaged 15.8%, but rain fell 21.9% of the time.
  - 12-hour events happened 22% of the time. 24-hour events (from a provider that issued 24-hour PoPs) happened 31% of the time. This shows how much a longer window raises the chance.
  - Day-1 NWS PoPs of 40-80% would be better calibrated if shifted up by about 5 points. Part of the cause is rounding to tenths: a "40%" covers 40-50%.
  - The NWS does not show 0% PoPs, and rarely 10%.
- Older studies: ECMWF MOS 12-hour PoP was very reliable, while NDFD and GFS MOS 12-hour PoP under-forecast the higher categories. Source: [Huntemann, NWS MDL](https://www.weather.gov/media/mdl/AMSGlahnSymp2015_Huntemann_paper.pdf).
- NBM 12-hour PoP is made by quantile mapping the ensemble with the past 60 days of data (borrowing extra nearby locations because 60 days alone is too few), then adding random "dressing" noise (Hamill et al. 2017). A 2023 follow-up using GEFSv12 reforecasts (Dec 2017-Nov 2019) gave forecasts that were "significantly more reliable and skillful" than raw ensemble probabilities, mostly at short leads and for light rain. Sources: [NOAA repository, Hamill et al.](https://repository.library.noaa.gov/view/noaa/28094); [NOAA repository, Stovern, Hamill & Smith 2023](https://repository.library.noaa.gov/view/noaa/54781). (A web search returned both records together; which link holds which paper was not checked.)
- In NBM, fields without an analysis, such as PoP, are "expert"-weighted rather than weighted by recent skill. Source: [NWS NBM user webinar, Apr 2026](https://www.weather.gov/media/wrn/calendar/NBMUserWebinar4-15-26.pdf).
- NBM bulletins: 1-hour PoP (P01) is in the hourly NBH bulletin. 6- and 12-hour PoP (P06, P12) are in NBS. 24-hour PoP (P24) appears only in the very-long-range NBX bulletin. Source: [NBM v4.3 text card](https://vlab.noaa.gov/web/mdl/nbm-textcard-v4.3). So there is no ready-made short-range 24-hour PoP.
- Logistic regression on the ensemble mean has long been used to turn ensemble rain forecasts into calibrated probabilities (23 winters, 1979-2001). Source: [Hamill, Whitaker & Wei 2004](https://psl.noaa.gov/psd1/pubs/2004/details/hamill_01abs.html).
- Raw ensemble "share of members with rain" was not particularly skillful for the ECMWF ensemble. A calibrated older GFS beat it. Source: [Hamill & Hagedorn, ECMWF](https://www.ecmwf.int/sites/default/files/elibrary/2007/15580-exploring-ensemble-forecast-calibration-issues-using-reforecast-data-sets.pdf).
- Kalshi daily NYC rain: a third-party listing of the 8 Jun 2026 contract says it resolves Yes if Central Park's recorded precipitation for the date is "above zero", per the NWS climate report. If that report is inconclusive, Kalshi falls back on the NWS hourly time series ("Weather" and "1 Hour Precip"). Source: [Solflare listing of KXRAINNYC-26JUN08](https://www.solflare.com/prediction/climate-and-weather/event/KXRAINNYC-26JUN08/). This is not Kalshi's own rulebook.
- Kalshi's monthly NYC rain contract (RAINNYCM) was amended on 21 Aug 2026. Its source is now "in hierarchical order, the National Weather Service and The Weather Company (TWC)". A 2 Sep 2026 amendment says only the first non-preliminary value counts, unless Kalshi judges it a serious error (the filing's words: "material error"). Sources: [CFTC filing 21 Aug 2026](https://www.cftc.gov/filings/orgrules/rules08212619089.pdf); [CFTC filing 2 Sep 2026](https://www.cftc.gov/filings/orgrules/rules09022622986.pdf).
- Base rates, computed for this note from the official NWS daily climate reports (2024-2025, via the [IEM CLI archive](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024)):

| Station | Days with 0.01 inch or more | Days with only a trace |
|---|---|---|
| NYC Central Park | 34% | 11% |
| Miami | 34% | 11% |
| Los Angeles (LAX) | 10% | 4% |

### Inferences
- A daily-rain model needs a calendar-day (LST) probability. The NBM 12-hour periods (00-12 UTC and 12-00 UTC) do not line up with the LST day: Eastern standard midnight is 05 UTC and Pacific is 08 UTC. Stitch the day from 6-hour or 1-hour PoPs, or let a regression learn the mapping.
- Do not combine two 12-hour PoPs as if they were independent: 1 − (1 − p1)(1 − p2). Wet periods tend to come together, so that formula overstates the daily chance. Fit instead: P(rain today) = logistic(a + b·logit(p_day) + c·logit(p_night) + d·QPF), using past CLI outcomes. (QPF means forecast rain amount; logit is the log-odds transform.)
- Score it against a climatology baseline (the share of wet days for that station and month), using the Brier skill score (section 4).
- The trace rule decides about 1 day in 9 in NYC and Miami. If trace counts as Yes for Kalshi but not for the PoP definition (0.01 inch), a PoP-based model will be biased low on exactly those days. Confirm the rule before building.

### Gaps
- No NBM-specific PoP reliability study for NYC, Miami or other Kalshi rain cities was found.
- Kalshi's current daily rain rulebook (whether "T" counts as above zero, which source applies after Aug 2026) was not read directly.

---

## 3. How do you update during the day with live observations, and how much uncertainty is gone by 2pm?

### Takeaway
Most of the uncertainty about the daily high is gone by early afternoon. Before 2pm standard time (3pm in summer), the official high ended within 1°F of the highest hourly reading so far on 72-82% of days. A big trap: hourly METAR readings miss the true peak. The official high was on average 0.7-0.8°F above the highest hourly reading, and at least 1°F above it on 56-68% of days. The METAR "6-hour maximum" remark fixes this: with it, the official high was matched exactly on 94-99% of days. A same-day model should be "the high so far, plus a forecast of the remaining rise", with a spread that shrinks as the day goes on.

### Cited findings

**Own check on public data (computed for this note).** Data: official daily highs from NWS climate reports and all routine and special METAR reports, 2024-2025, from the Iowa Environmental Mesonet ([CLI archive](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024); [ASOS download](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py)). About 725-729 days per station. Hours are LST. Scripts: `research_notes/Kalshi weather bot feasibility/scripts/intraday_high_check.py` and `metar_6hr_max_check.py`.

- Share of days when the official high ended up no more than 1°F above the highest hourly reading so far:

| Before this LST hour | NYC Central Park | Miami | LAX |
|---|---|---|---|
| 10:00 | 13% | 8% | 14% |
| 12:00 | 30% | 44% | 58% |
| 14:00 (3pm summer clock) | 72% | 79% | 82% |
| 16:00 | 87% | 87% | 85% |

- Average remaining rise before 14:00 LST: NYC 1.22°F (spread, standard deviation, 1.28), Miami 1.03°F (0.86), LAX 0.95°F (0.96). By 16:00 it is about 0.8°F everywhere. That is almost exactly the hourly-reading gap below, so the real remaining rise is close to zero by then.
- A rise of 3°F or more after 14:00 LST happened on 10% of days in NYC, 5% in Miami and 4% in LAX.
- NYC winter is harder than summer. Before 14:00 LST, the spread of the remaining rise was 1.82°F in Dec-Feb versus 1.01°F in Jun-Aug (fronts can push the high late or early).
- Hourly readings miss the peak. The official high minus the highest METAR reading of the day averaged 0.66°F (NYC), 0.82°F (Miami) and 0.84°F (LAX). It was at least 1°F on 57%, 68% and 64% of days. It was almost never below zero (0% after rounding).
- The METAR 6-hour maximum remark (the "1snnn" group, in tenths of °C) closes the gap. In 2025, the larger of the hourly readings and the 6-hour maximums inside the LST day matched the official high exactly on 94% of days (NYC), 99% (Miami) and 99% (LAX). It was within 1°F on 99-100% of days.

**Published sources**
- LAMP is NWS guidance that updates every hour. It mixes the latest observations, MOS and model output. It covers 1-25 hours ahead, and its gridded temperatures are valid at the top of each hour. Source: [NWS LAMP status, 2016](https://www.weather.gov/media/mdl/pres/Ghirardelli_LAMP_StatusPlans_NWA_2016_Final.pdf). LAMP beat GFS MOS for visibility at 1-9 hours and for cloud ceiling over all 25 hours. No temperature comparison was found. Source: [Ghirardelli & Rudack 2010](https://www.weather.gov/media/mdl/pub/Ghirardelli_Rudack_LAMPvNWP_2010.pdf).
- The hourly NBM bulletin (NBH) gives hourly temperature (TMP) and its standard deviation (TSD) for 1-25 hours. Source: [NBM v4.3 text card](https://vlab.noaa.gov/web/mdl/nbm-textcard-v4.3).
- Taking the highest of a model's hourly temperatures runs cold, for three reasons. The highest of hourly averages is below the average highest. The real peak can fall between hours. Grids miss station detail. Cold bias found: HRRR up to about 2°F, ECMWF 1-5°F, LAMP 1-2°F, depending on city. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- The daily-max fields in NBM, NDFD and GFS MOS cover only the daytime. On 4.6% of days the high fell outside that window, for example at night ahead of a cold front. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- Daily highs usually come in the afternoon because air temperature lags the sun. Fronts, thunderstorms and heavy rain can move them to other times. Source: [Hong Kong Observatory](https://www.hko.gov.hk/en/education/weather/sunshine-and-uv/00692-What-time-in-a-day-is-highest-lowest-air-temperature.html).
- The Kalshi day uses standard time. During daylight saving time the high is counted from 1:00 AM to 12:59 AM the next day, local clock time. Source: [Kalshi help: weather markets](https://help.kalshi.com/en/articles/13823837-weather-markets).
- One practitioner recipe (not peer-reviewed, not checked): limit the forecast high to between the observed high and observed + 3°F per remaining hour; shrink the spread with the square root of hours left divided by 24 (with a floor of about 0.5°F); optionally blend 50/50 with HRRR. Source: a practitioner's write-up (not linked).

### Inferences
- A workable same-day model: final high = max(high so far, high so far + R), where R is the remaining rise. Fit R's distribution from history by LST hour, month and the gap between the forecast high (NBM/LAMP for the remaining hours) and the high so far. The tables above are the no-forecast baseline.
- Use the 6-hour maximum remarks and any special reports, not just hourly readings. Otherwise the "high so far" is biased about 0.7-0.8°F low, which is a third to half of a 2°F bracket.
- The 6-hour maximum for the window ending 18 UTC (7am-1pm Eastern standard time) arrives at about 17:51 UTC. That gives the true peak through 1pm EST. The afternoon window's maximum arrives only at about 23:51 UTC.
- For the daily low, the same logic runs in reverse, but lows often fall near midnight or dawn, so the useful same-day period is different. This was not checked.
- Because the market reacts slowly to forecast updates (section 1), same-day observations may be where a model can be fastest. This is a hypothesis, not tested here.

### Gaps
- No published study of the same-day conditional distribution of the daily high was found. The numbers above are this note's own two-year check.
- It was not checked whether ASOS 1-minute or 5-minute data is available in real time for these stations. The IEM 5-minute feed returned no extra temperature readings for them.
- LAMP and NBM hourly temperature MAE for the first few hours was not found.

---

## 4. How should forecasts be scored, compared with market prices, and turned into expected profit after fees and spread?

### Takeaway
Score every forecast with a proper scoring rule, meaning one you cannot game by shading your forecast. Use the Brier score or log loss for each bracket or rain contract, and CRPS for the whole temperature distribution. Check calibration with reliability diagrams. Compare model and market on the same timestamps. Turn the market's bracket prices into a distribution the same way for every snapshot. Profit per contract = model probability − price paid − fee. The fee is 0.07 × price × (1 − price), at most 1.75 cents at 50 cents. Buying at the ask also costs half the spread. Past Kalshi data, including weather, shows a favourite-longshot bias: cheap unlikely bets are overpriced and heavy favourites slightly underpriced.

### Cited findings
- Brier score = the average squared gap between forecast probability and outcome (1 or 0). The Brier skill score compares it with always forecasting the base rate (historical frequency). Source: [Kavish Muthum, Kalshi weather calibration](https://www.cs.utexas.edu/~kavish/blog/kalshi-weather-calibration.html).
- The Brier score splits into three parts: how hard the event is to forecast, reliability (calibration) and resolution (how much forecasts vary with the outcome). Source: [Bickel et al. 2011, eq. 3](https://utw10181.utweb.utexas.edu/Papers/NWS_Calibration.pdf).
- Proper scoring rules reward sharpness (narrow forecasts) only when the forecast is also calibrated. The normal distribution's CRPS has a closed form, which makes fitting fast. Calibration tools: verification rank histograms and PIT histograms, which should look flat. Source: [Gneiting et al. 2005](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).
- CRPS of a normal forecast with middle µ and spread σ, for outcome y: CRPS = σ·[z(2Φ(z) − 1) + 2φ(z) − 1/√π], where z = (y − µ)/σ. Source: [Rasp & Lerch 2018, eq. B2](https://arxiv.org/pdf/1805.09091v1). Fitting by CRPS is the safer choice, because it is less thrown off by a few big misses. Fitting by log score is the same as maximum likelihood. Source: [same](https://arxiv.org/pdf/1805.09091v1).
- Python: `scoringrules` covers Brier, CRPS, log score, energy and variogram scores, with numba/jax/pytorch/tensorflow backends. Source: [scoringrules GitHub](https://github.com/frazane/scoringrules). `properscoring` covers CRPS (ensemble, normal, numerical) and Brier, but not log score. Source: [properscoring GitHub](https://github.com/TheClimateCorporation/properscoring).
- Turning bracket prices into a distribution, as done in the 7-city study. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1):
  - Use each bracket's bid-ask midpoint as its probability, spread evenly across the bracket.
  - Give the open-ended tails probability that falls off geometrically (ratio 0.55 per degree, so 95% of tail mass is within 5°F of the last bracket).
  - Liquidity screens: at least 3 quoted brackets, spread no more than 50 cents, and midpoints summing to between 0.7 and 1.3. About 86% of snapshots passed.
- Another study used Kalshi 1-minute candlesticks, took midpoints from bid and ask, and scored calibration at any time from noon the day before to 9pm ET on the day. Source: [Kavish Muthum](https://www.cs.utexas.edu/~kavish/blog/kalshi-weather-calibration.html). That write-up gives no numeric results.
- The sum of Yes prices across an event's brackets is normally above 1.0 (the "overround"). Well above 1.1 suggests mispricing or a data error. Source: a practitioner's write-up (not linked).
- Kalshi fee: round up(M × 0.07 × C × P × (1 − P)), where C = contracts, P = price in dollars and M = a per-series multiplier (default 1). This is quoted from Kalshi's fee schedule effective 7 July 2026 by secondary sources. Sources: [allium.so](https://allium.so/blog/kalshi-fees-why-the-cost-peaks-near-50-cents/); [chudi.dev](https://chudi.dev/blog/kalshi-fees); [QuantVPS](https://www.quantvps.com/blog/kalshi-fees-explained). One source says direct members are rounded to $0.0001 and accounts cleared through a futures broker to $0.01. Sources differ on maker fees (zero on most markets versus 0.0175 in place of 0.07).
- Kalshi began charging makers after April 2025. Before that, only takers paid, rounded up to the cent. With that rounding, the fee on 100 contracts at 50c was 1.77% of the price instead of 1.75%. Source: [Bürgi, Deng & Whelan 2026](https://www2.gwu.edu/~forcpgm/2026-001.pdf).
- Expected profit per contract for a taker buying Yes at price P with belief π: π − P − fee(P). For a maker posting a bid that fills with probability θ: θ × (π − bid). Source: [Bürgi, Deng & Whelan 2026, eqs. 5-6](https://www2.gwu.edu/~forcpgm/2026-001.pdf).
- Favourite-longshot bias on Kalshi (300,000+ contracts, 2021-April 2025): low-price contracts win far less often than needed to break even after fees; high-price ones win more often and earn small positive returns. Makers earn more than takers. In the "Climate & Weather" group (29,924 contracts), pre-fee profit = −0.997 + 0.031 × price, with prices quoted in cents. Source: [Bürgi, Deng & Whelan 2026, Table 8](https://www2.gwu.edu/~forcpgm/2026-001.pdf).
- A practitioner reports per-city out-of-sample Brier scores of 0.07-0.14 for bracket forecasts (climatology about 0.25). They warn that beating climatology does not mean making money at market prices. They say the practical edge is maker-side fading of overpriced longshot brackets. Source: a practitioner's write-up (not linked), not verified.

### Inferences
- Fee and break-even per contract at a few prices (computed from the formula above, ignoring rounding):

| Price paid | Fee per contract | Win chance needed to break even |
|---|---|---|
| 10c | 0.63 cents | 10.6% |
| 30c | 1.47 cents | 31.5% |
| 50c | 1.75 cents | 51.8% |
| 70c | 1.47 cents | 71.5% |
| 90c | 0.63 cents | 90.6% |

- With a 1-cent spread, buying at the ask costs another half cent compared with the midpoint. So against the midpoint, a taker needs the model to be about 1-2.3 percentage points above the market, depending on price.
- If fees round up to the cent per order, a single-contract order always pays at least 1 cent. That is fatal at 5-10c prices. The project's own 25 Oct check found rounding to $0.0001 per order, which matches the "direct member" claim above.
- If the regression units are cents, the weather break-even sits near 32c. Below that, buyers lost before fees (about −0.7c per contract at 10c). Above it, they gained (about +1.8c per contract at 90c). That is the same direction as the project's main bot finding. This is an inference from the table, not a stated result.
- Comparing model and market: score both on identical snapshots (for example, every hour from listing to close). Normalize market midpoints to sum to 1. Floor probabilities at about 0.5% before log loss so one zero does not dominate. Report Brier, log loss and CRPS (or its bracket version, the ranked probability score).
- Treat all brackets of one city-day as one bet, and same-day bets across cities as linked. Weather errors are correlated across nearby cities, which is why the 7-city study averaged across cities by date ([Crosier 2026](https://arxiv.org/html/2609.23969v1)). Otherwise significance will be overstated (the project's "clustered on event" rule).
- Profit test: for each snapshot, the trade is Yes when model p > ask + fee(ask), and No when (1 − p) > No ask + fee. Simulate at the actual ask with the actual depth, not the midpoint.

### Gaps
- Kalshi's official fee schedule PDF was not read directly. The formula and rounding come from secondary sources and the GWU paper.
- No published numbers were found on the calibration of Kalshi temperature brackets by price band. The UT Austin study gives method only.

---

## 5. How do you design an honest backtest: which archives, where to get Kalshi prices and outcomes, and how to split train and test?

### Takeaway
Use forecasts exactly as they were published at the time. IEM's text archives of NBM, MOS and LAMP station bulletins are the easiest honest source, going back to 2018-2020. Open-Meteo's "Previous Runs" API gives fixed-lead forecasts but mostly only from 2024. Its "Historical Forecast" API stitches runs together, which leaks future data for day-ahead tests. Kalshi serves settled markets and candlesticks through its historical endpoints. The official outcomes come from the NWS climate reports, archived by IEM. Build on older data and score once on newer data, covering at least one full year so every season is tested.

### Cited findings

**Forecast archives**

| Archive | What it holds | Available from | Honest for a day-ahead test? |
|---|---|---|---|
| IEM MOS archive | Station text bulletins: GFS MOS, NAM MOS, LAMP, NBM (NBS, NBE) | GFS 16 Dec 2003; NAM 9 Dec 2008; LAMP 12 Jul 2020; NBS 7 Nov 2018; NBE 23 Jul 2020 | Yes. These are the bulletins as issued |
| Open-Meteo Previous Runs | Hourly values from the run made 1-7 days before | Most models Jan 2024; GFS 2-m temperature Mar 2021 | Yes for fixed leads |
| Open-Meteo Single Runs | The whole forecast of one chosen run | ECMWF IFS HRES from 14 Mar 2024 | Yes |
| Open-Meteo Historical Forecast | One continuous series stitched from many runs | Varies | No for day-ahead (see below) |
| GEFSv12 reforecast (AWS) | 5-member reforecasts, once daily, to 16 days | 2000-2019 on AWS (1989-2019 overall) | Yes, but older model and coarse |

- IEM MOS archive dates and API, for example `/api/1/mos.txt?station=KAMW&runtime=2009-01-10%2012:00Z&model=GFS` (CSV) or `mos.json`. The NBM bulletin cycles changed from 01/07/13/19 UTC to 00/06/12/18 UTC on 5 May 2026. LAMP is archived only for the 00/06/12/18 cycles. Source: [IEM MOS page](https://mesonet.agron.iastate.edu/mos/).
- Open-Meteo Previous Runs: `previous_day1` is the value predicted 24 hours before. Most models are archived from January 2024 and GFS 2-m temperature from March 2021. It includes NBM, HRRR, ECMWF, GFS and others, plus a GEFS ensemble mean. Source: [Open-Meteo Previous Runs docs](https://open-meteo.com/en/docs/previous-runs-api).
- Open-Meteo Historical Forecast "combines multiple runs of a weather model into one continuous time-series". Sources: [Open-Meteo Substack](https://openmeteo.substack.com/p/introducing-the-historical-forecast); [docs](https://open-meteo.com/en/docs/historical-forecast-api). Single Runs takes a `run=` parameter. Source: [docs](https://open-meteo.com/en/docs/single-runs-api).
- NBM GRIB2 files are on AWS in bucket `noaa-nbm-grib2-pds`, organized by run date and cycle, listable without an account. NOAA describes it as the historical archive; NOMADS keeps only 1-2 days. Source: [AWS registry: NOAA NBM](https://registry.opendata.aws/noaa-nbm). The archive's start date was not found.
- GEFSv12 reforecast: 1989-2019, about 25 km grid, once per day to 16 days with 5 members (11 members to 35 days on Wednesdays). Source: [UCAR dataset page](https://ckanprod-alma.ucar.edu/dataset/gefsv12-reforecast-dataset-for-supporting-subseasonal-and-hydrometeorological-applications). AWS describes its copy as 2000-2019. Source: [AWS registry](https://registry.opendata.aws/noaa-gefs-reforecast).
- Herbie is a Python package that downloads HRRR, RAP, GFS, GEFS, NBM, RRFS, ECMWF IFS/AIFS and more from NOMADS, AWS, Google, Azure and ECMWF Open Data. It can fetch only chosen variables (for example `":TMP:2 m"`). Source: [Herbie GitHub](https://github.com/blaylockbk/Herbie).
- An open-source Kalshi/Polymarket weather bot uses the 31-member GFS ensemble from Open-Meteo to estimate the chance of passing temperature thresholds, and trades when its edge is over 8%. Its "simulation mode" is forward paper trading, not a historical backtest. Source: [suislanchez/polymarket-kalshi-weather-bot](https://github.com/suislanchez/polymarket-kalshi-weather-bot).

**Outcomes**
- IEM serves parsed NWS climate reports as JSON: daily high, low, precipitation, the time of the high and a link to the original report. Source: [IEM CLI JSON, example](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024). Used for section 3 in this note.

**Kalshi prices**
- Kalshi splits data into live and historical tiers. `GET /historical/cutoff` returns the moving cutoff times. Settled markets older than the cutoff, and their candlesticks, are only at `GET /historical/markets`, `GET /historical/markets/{ticker}` and `GET /historical/markets/{ticker}/candlesticks`. Old trades are at `GET /historical/trades`. Historical endpoints page with the same cursor method as live ones. Sources: [Kalshi docs: historical data](https://docs.kalshi.com/getting_started/historical_data); [cutoff endpoint](https://docs.kalshi.com/api-reference/historical/get-historical-cutoff-timestamps).
- The docs page does not state candlestick intervals, authentication or how far back the archive goes. Source: [Kalshi docs](https://docs.kalshi.com/getting_started/historical_data).
- How much Kalshi high-temperature history exists, by city (start of the 7-city study's sample, ending 12 Aug 2026): NYC (Central Park) and Chicago (Midway) from Jan 2022, 1,684 days; Miami and Austin from May 2023; Philadelphia and Denver from Nov 2024; Los Angeles (LAX) from Jan 2025, 585 days. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).

**Train/test split and seasons**
- EMOS biases change with the season. Skill dropped once the training window ran past about 45 days. Source: [Gneiting et al. 2005](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).
- The German study held out a whole calendar year (2016) as its test set to "mimic operational conditions". Source: [Rasp & Lerch 2018](https://arxiv.org/pdf/1805.09091v1).
- The market's edge over NBM changes with the season: 10-16% better from November to June, when NBM error is 3°F or more, but only 1-4% better from July to October. Each extra degree of NBM error adds about 6 points to the market's advantage. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).

### Inferences
- Recommended data stack for a first build: IEM NBM bulletins (NBS/NBE/NBP if archived) plus IEM LAMP for the forecast; IEM CLI for outcomes; Kalshi historical candlesticks for prices. All are free and lookahead-free when timestamps are handled correctly.
- The usable test window is short where markets are young. LA has about 1.5 years of history, and some forecast archives start in 2024. A clean split: build the model and choose settings on data up to a cutoff date, then score once on the following 12 months.
- Seasonality: either fit separate seasonal models, or use a rolling window and let it adapt. Then report test results by season. A model tuned in summer is likely to be over-confident in winter, when errors are larger (NYC spread almost doubled in winter in section 3).
- Time-stamp every forecast by its release time, not its model run time. NBM and LAMP bulletins come out some time after the run hour. In the backtest, trade only on bulletins already public at the snapshot time.
- Pull Kalshi data slowly and cache it, rather than hitting the API in bulk.

### Gaps
- Whether IEM archives the NBP (percentile) bulletin, or only NBS/NBE, was not confirmed.
- The start date of the NBM AWS archive and the Kalshi candlestick intervals and retention were not confirmed.
- Exact NBM bulletin release delays after each cycle were not found.

---

## 6. What are the known pitfalls?

### Takeaway
The traps that most often fake an edge: using the wrong settlement source or day window; getting bracket edges off by one; scoring against hourly readings instead of the official report; forecasts that were not public yet at trade time; and fills at prices nobody would have given you. Station quirks (coastal LAX, tree-shaded Central Park) and model upgrades shift biases, so fit per station and refit after upgrades.

### Cited findings
- **Settlement source may have changed in Aug 2026.** The 7-city study says Kalshi switched its high-temperature settlement source to The Weather Company after 12 Aug 2026, so the study kept only NWS-settled contracts. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1). Kalshi's help page still names the NWS Daily Climate Report. Source: [Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets). The monthly NYC rain contract now lists NWS first and TWC second. Source: [CFTC filing](https://www.cftc.gov/filings/orgrules/rules08212619089.pdf). These sources conflict and need checking per market.
- Kalshi's hourly temperature markets settle on The Weather Company's readings, not NWS reports. Source: [Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets).
- Settlement can be delayed if the final report's high is lower than the preliminary one, or does not agree with the METAR 6- or 24-hour highs. Source: [Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets).
- **Day window**: standard time all year, so 1:00 AM to 12:59 AM local clock time during daylight saving time. Source: [Kalshi help](https://help.kalshi.com/en/articles/13823837-weather-markets). Polymarket uses local clock time, so the two venues' days differ. Source: a practitioner's write-up (not linked).
- **Bracket edges**: a bracket covers two whole degrees, both ends included (for example 74 and 75). Treating it as a half-open range produced a "+1640%" fake backtest. Whether a threshold contract is "greater" or "less" cannot be read from the ticker. The date is in the ticker, not in `close_time`, which is the next day in UTC. Source: a practitioner's write-up (not linked).
- **Other backtest traps from the same practitioner**: the wrong settlement source "flips ~10% of outcomes"; adding up days in UTC instead of LST "cost ~14 percentage points of accuracy"; assuming fills at 1c asks over-credits profit about 23 times; a clock mismatch between fill time and feature time leaks the future. Source: a practitioner's write-up (not linked). The same page claims IEM ASOS data "matches CLI 100%". This note's check contradicts that for hourly readings (section 3): only 32-42% exact.
- **Daytime-only max fields** miss the high on 4.6% of days. **Highest-hourly-temperature methods** run 1-5°F cold. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- **LAMP archive lag**: only the 00/06/12/18 UTC cycles are archived, so the freshest archived LAMP is 2-4 hours old at some snapshots. Sources: [Crosier 2026](https://arxiv.org/html/2609.23969v1); [IEM MOS page](https://mesonet.agron.iastate.edu/mos/).
- **Station microclimates**: the NYC market settles at Central Park, Chicago at Midway and Los Angeles at LAX airport (coastal), not a downtown site. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1). Central Park's sensor is "surrounded by temperature-lowering trees", per a 2016 press report. Source: [NY Post via Climate Signals](https://www.climatesignals.org/headlines/citys-stifling-heat-wave-finally-nearing-end). NWS warns the Central Park record "may include data from more than one, possibly incompatible location". Source: [NWS OKX](https://www.weather.gov/media/okx/Climate/CentralPark/DailyHighestMaxT.pdf). Polymarket uses LaGuardia for NYC. Source: a practitioner's write-up (not linked).
- **Model upgrades**: NBM v4.1 (17 Jan 2023), v4.2 (15 May 2024), v4.3 (notice dated 15 Apr 2025), v5.0 (operational by 5 May 2026), and a 28 Jul 2026 update "to improve temperatures during seasonal transition periods". Source: [NBM versions](https://vlab.noaa.gov/web/mdl/nbm-versions). The IEM bulletin cycle times changed on 5 May 2026. Source: [IEM MOS page](https://mesonet.agron.iastate.edu/mos/). Handling model changes is a known open problem. Source: [Vannitsem et al. 2021](https://arxiv.org/abs/2004.06582).
- **Sensor changes** can shift readings. At Syracuse, new ASOS temperature sensors reduced biases from the older HO83 sensor. Source: [NOAA repository](https://repository.library.noaa.gov/view/noaa/6724).
- **Seasonal bias drift** limits training windows to about 30-45 days for simple EMOS. Source: [Gneiting et al. 2005](https://sites.stat.washington.edu/raftery/Research/PDF/gneiting2005.pdf).
- **Correlated errors across cities**: the 7-city study averaged across cities by date for its tests because errors were correlated. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).

### Inferences
- Read each market's own settlement source, station and window from the Kalshi API for every historical market, and label outcomes from that source. Do not assume one source for the whole history, especially across Aug 2026.
- Overfitting risk is high: 30+ cities × 6 brackets × many hours × several model choices. Pick the model on the build period only, then score the test period once (a train/test split). Use the "drop the biggest contributor" check (leave-one-out): if the profit depends on one city or one month, it is probably luck.
- After each NBM upgrade, expect the bias and spread fits to drift. A rolling 40-60 day window adapts on its own. A long fixed training set does not.
- The intraday high-so-far must include special reports and 6-hour maximums. Otherwise a backtest will think the high has been "reached" when it has not.

### Gaps
- No study was found that measures how much the Central Park trees bias the high.
- No measure was found of LAX's coastal effect versus inland LA, beyond its role as the settlement station.
- Whether the Aug 2026 source change applied to all daily high/low and rain markets, or only some, was not confirmed from Kalshi's rulebooks.
