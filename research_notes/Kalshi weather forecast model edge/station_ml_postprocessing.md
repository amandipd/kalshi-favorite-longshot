# Station-level ML post-processing and forecast blending for daily high/low temperature and daily rain (state of the art 2022 to Oct 2026)

Research date: 26 Oct 2026. Every claim below has a source and a date. Plain-words meanings of the terms used:

- **RMSE** (root-mean-square error): the typical miss in °F, with big misses counted extra. **MAE** (mean absolute error): the average miss in °F.
- **CRPS** (continuous ranked probability score): a score for a whole forecast range instead of one number. It works like MAE but for probability forecasts. Same units as the variable. Lower is better.
- **EMOS / NGR** (ensemble model output statistics / non-homogeneous Gaussian regression): fit a bell curve whose centre and width are straight-line functions of the model forecasts.
- **QRF** (quantile regression forest): a random forest that outputs a range, not one number.
- **DRN** (distributional regression network): a small neural net that outputs the centre and width of a bell curve.
- **BQN** (Bernstein quantile network): a neural net that outputs a flexible set of percentiles.
- **Brier score**: the squared error of a yes/no probability. 0 is perfect. Always saying 50% scores 0.25.
- **Out-of-sample**: tested on data the rule never saw while being built.
- **Calibration**: whether a 70% forecast really comes true 70% of the time.

---

## 1. Methods and their measured gains for station max/min temperature

### Takeaway
Against a raw model, ML post-processing cuts the probability-forecast error (CRPS) by about 15% to 33%. Against a forecast that is already well post-processed, the extra gain from fancier ML is small: about 3% to 13%. The NBM is already post-processed and blended. So a small team should expect single-digit % gains over NBM from ML itself. The biggest cheap gain is a simple blend of public forecasts: about 9% lower RMSE than NBM alone (2.70°F down to 2.45°F the day before). That simple blend lands at market level (2.44°F), not below it.

### Cited findings
**The classic benchmark: Rasp & Lerch (2018), 537 German stations, 2 m temperature, 2-day forecasts, test year 2016.** CRPS in °C (lower is better). Source: [Rasp & Lerch 2018, MWR 146:3885, ar5iv](https://ar5iv.labs.arxiv.org/html/1805.09091):

| Method (plain words) | CRPS, 1 yr training | CRPS, 9 yr training |
|---|---|---|
| Raw ensemble (no fixing) | 1.16 | 1.16 |
| EMOS, one fit for all stations | 1.01 | 1.00 |
| EMOS, a fit per station | 0.90 | 0.90 |
| EMOS with boosting (picks inputs automatically) | 0.85 | 0.80 |
| QRF (random forest range) | 0.95 | 0.81 |
| Neural net, no station ID | 0.92 | 0.91 |
| Neural net with station "embeddings" (a learned ID code per station) = the DRN | 0.82 | 0.78 |

- The DRN beat the raw ensemble by about 29% (1-yr training) and the best classical method (boosted EMOS) by about 3%. Source: [Rasp & Lerch 2018](https://ar5iv.labs.arxiv.org/html/1805.09091).
- Over a per-station EMOS (closest analogue to an already-calibrated product), the DRN gain was 9% to 13% (0.90 → 0.82 or 0.78). This is arithmetic from the table above, not a figure the paper states. Source: [Rasp & Lerch 2018](https://ar5iv.labs.arxiv.org/html/1805.09091).
- **Transformer (Dec 2024, EUPPBench, ECMWF ensemble over Europe, gridded not stations):** CRPS raw 1.008 K, classical member-by-member method 0.889 K, transformer 0.841 K. That is 16.5% better than raw and about 5% better than the classical method. Source: [Self-attentive Transformer, arXiv 2412.13957](https://arxiv.org/pdf/2412.13957).
- **Tree methods (Czech study, hourly 2 m temperature):** QRF and NGBoost (natural gradient boosting, a boosted-tree method that outputs a distribution) were best at 1-2 days. Plain EMOS won at 8-10 days. Source: [ASEP record, Czech Academy of Sciences](https://asep.lib.cas.cz/arl-cav/en/detail-cav_un_epca-0570950-Postprocessing-of-Ensemble-Weather-Forecast-Using-Decision-TreeBased-Probabilistic-Forecasting-Meth).
- **Gradient-boosted mixture models (Dec 2024, German stations):** "substantially outperform state-of-the-art postprocessing models" for 2 m temperature. The abstract gives no numbers. Source: [arXiv 2412.09583](https://arxiv.org/abs/2412.09583).
- **Forecast blending (the most relevant US number), Crosier, arXiv 2609.23969, 20-21 Sep 2026.** Seven Kalshi cities, 7,590 city-days, Jan 2022 to 12 Aug 2026. Day-ahead RMSE at the market's first trading hour (11:00 ET the day before): NBM 2.70°F, LAMP (de-biased) 2.83, NDFD (the official human-edited NWS forecast) 2.83, GFS MOS 3.17, HRRR (de-biased) 3.32, ECMWF (de-biased) 3.31. A least-squares blend of all six, refit daily per city on past days only (out-of-sample): 2.45°F. The Kalshi market: 2.44°F. Source: [Crosier 2026, arXiv HTML](https://arxiv.org/html/2609.23969v1).
- Same paper, later times: evening before (19:00 local) NBM 2.45, blend 2.25, market 2.21. At the NBM's final bulletin on the target morning: NBM 2.12, blend 1.90, market 1.88. The market's lead over the blend was 3.1%, 4.3% and 3.0%. The last one was significant only at the 10% level (weak evidence). Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- **A plain average did as well as the fitted blend.** Equal weights scored 2.43°F vs 2.45°F for fitted weights at the opening hour. They tied in the evening (2.25 vs 2.25) and were a shade worse at the final bulletin (1.900 vs 1.895). On those matched days the market scored 2.38°F, so its lead over the plain average was 2.1%. Source: [Crosier 2026, Appendix B.2](https://arxiv.org/html/2609.23969v1).
- **How NBM itself blends:** NBM blends many models and weights them by recent MAE. It bias-corrects and downscales to a 2.5 km grid. Source: [NWS/MDL Veenhuis 2015 slides](https://www.weather.gov/media/mdl/Veenhuis_Presentation2015.pdf). In 2016 verification, the blend beat each of its bias-corrected parts. The day-4 NBM was as good as the day-2 bias-corrected GFS. Source: [MDL, AMS 2017 NBM verification slides](https://www.weather.gov/media/mdl/AMS2017-NBMVerification.pdf).
- **AI weather models as inputs.** Australia's Bureau of Meteorology ran its operational IMPROVER post-processing on ECMWF's AIFS AI model, verified at 569 stations (Apr-Jul 2024). AIFS beat HRES for temperature after the first few lead days. Blending AIFS with ENS and HRES gave significantly lower MSE and CRPS than an NWP-only blend. No exact % was published. Source: [Trotta et al., BoM, arXiv 2504.12672, Apr 2025](https://arxiv.org/html/2504.12672v1).
- At 183 Norwegian stations, Pangu-Weather (an AI model) was slightly better than ECMWF models for 2 m temperature. Post-processing gave big gains for every model, largest for coarse global models. Source: [Nonlinear Processes in Geophysics 31:247, 2024](https://npg.copernicus.org/articles/31/247/2024/).
- **End-to-end AI station forecasts:** Aardvark Weather (Nature, Mar 2025) station temperature MAE was "on par with station-corrected HRES" out to 10 days. Source: [NCI docs summary](https://test-template-2026.readthedocs.io/en/latest/aardvark.html). It reportedly matched NDFD in the US. Sources: [alphaXiv summary of the preprint](https://alphaxiv.org/overview/2404.00411v3); [Turing Institute](https://www.turing.ac.uk/news/publications/end-end-data-driven-weather-prediction).
- Google says MetNet-3 (2023) beats HRRR and ENS up to 24 h ahead for core surface variables, including temperature. It is Google's own claim, and no temperature-only number was found. Source: [Google Research blog](https://research.google/blog/metnet-3-a-state-of-the-art-neural-weather-model-available-in-google-products/).

### Inferences
- NBM is already a calibrated, bias-corrected, multi-model blend. The right comparison for "ML on top of NBM" is the per-station-EMOS → DRN step (9-13%), not raw → DRN (29-33%). In practice, a small team's ML on top of NBM plus other public models will most likely land 8-12% below NBM RMSE. That is about 2.4°F day-ahead across these cities, which is market level.
- Crosier's linear blend already captures most of that gain. A plain average matched fitted weights. So the hard part is not the ML method. It is finding information the public stack does not have.
- In this setting, fancy methods (DRN, BQN, transformers) mainly pay off when pooling many stations (hundreds) to learn shared patterns. With 4-7 Kalshi stations, a per-station linear blend or EMOS plus a few features is the realistic best.

### Gaps
- No published head-to-head of ML post-processing applied on top of NBM at US ASOS stations, with MAE/RMSE in °F, was found. No AMS paper in 2022-2026 turned up for this exact setup.
- BQN (Bremnes 2020; Schulz & Lerch 2022) and analog-ensemble temperature results were not checked for this note. Schulz & Lerch's comparison was for wind gusts, not temperature.
- No exact °F skill numbers for MetNet-3 or AIFS on US daily max temperature were found.

---

## 2. Rain: calibrated probability of measurable rain (≥0.01 inch) for a whole calendar day

### Takeaway
NBM PoP (probability of precipitation) is built with quantile mapping on a short 60-day training window. NWS 1-3 day PoPs have been found well calibrated. Private apps (The Weather Channel) showed a "wet bias" at low probabilities. ML gives modest gains: about 8-11% better Brier score in one logistic-regression study, and better results for a CNN in another. No published Brier score or calibration numbers were found for NBM's daily (24 h) PoP at single stations.

### Cited findings
- **How NBM makes PoP12** (the chance of rain in a 12-hour block): quantile-mapped US and Canadian models, using CDFs (cumulative distribution functions, i.e. the share of past values below each level) from the past 60 days. Probability = share of ensemble members with rain, then spatially smoothed. 60 days alone was judged too short, so "supplemental" look-alike locations are added to the training data. Source: [Hamill et al. 2017, MWR, NOAA repository](https://repository.library.noaa.gov/view/noaa/28094). PoP12 entered NBM in v2.0, 15 Nov 2016. Source: [MDL AMS 2017 slides](https://www.weather.gov/media/mdl/AMS2017-NBMVerification.pdf).
- A 2023 follow-up for GEFSv12 rain in NBM was "significantly more reliable and skillful than raw ensemble-derived probabilities". Source: [Stovern & Hamill 2023, via NOAA repository search](https://repository.library.noaa.gov/view/noaa/54781).
- **Private vs NWS calibration (older):** The Weather Channel PoPs from 0.4 to 0.9 were well calibrated. Below 0.3 and above 0.9 they were not, with a bias toward rain, worst in April-September. Study: 42 US sites, 14 months. Source: [Bickel & Kim 2008](https://utw10181.utweb.utexas.edu/Papers/TWC_Calibration.pdf). A 2009 follow-up found NWS 1-3 day PoPs well calibrated but with some bias. Source: [AMS 2010 annual meeting paper](https://ams.confex.com/ams/90annual/webprogram/Paper161669.html). Wikipedia's claim that NWS PoPs are "unbiased" conflicts mildly with that. Source: [Wikipedia: Wet bias](https://en.wikipedia.org/wiki/Wet_bias).
- A local NWS study (Pocatello/Elko, Jan 2008) found a strong wet bias in official PoP12, GFS and SREF. NAM was dry above 30%. Source: [NWS Western Region TA 08-03](https://www.weather.gov/media/wrh/online_publications/TAs/TA0803.pdf).
- **ML gains for rain probability:** spatial logistic regression ("Max-and-Smooth") improved Brier score by 8.5% to 11.1% over standard fitting. Source: [arXiv 2209.00477](https://arxiv.org/pdf/2209.00477). Over China, a CNN beat a shallow neural net, a CSG-EMOS (a censored, shifted gamma curve fit) and the raw ensemble on CRPS and Brier score, mostly for heavy rain. Source: [Ji et al. 2022, Frontiers in Earth Science](https://www.frontiersin.org/articles/10.3389/feart.2022.978041/full). An analog-ensemble + CNN hybrid beat other analog methods by 0-60% on Brier skill for heavy rain (gridded). Source: [Sha et al. 2022, NCAR OpenSky](https://cisl.ucar.edu/opensky-publications/articles:25801/a-hybrid-analog-ensemble-convolutional-neural-network-method-for-post-processing-precipitation-forecasts).
- "MOS random forests" (weather-adapted regression coefficients) worked well for daily rain with little tuning. Source: [NPG 30:503, 2023](https://npg.copernicus.org/articles/30/503/2023/npg-30-503-2023.xml).
- ForecastWatch's 2024 provider study scores PoP as one of five measures. The Weather Channel ranked first for "icon precipitation". No PoP numbers are on the public page. Source: [ForecastWatch, 31 Jul 2025](https://forecastwatch.com/2025/07/31/new-report-analysis-of-2024-one-to-five-day-out-forecasts/).

### Inferences
- Daily rain yes/no is a binary event, so the method choice matters less than for temperature. Logistic regression or isotonic regression (a fit that only forces higher inputs to give higher probabilities) on NBM PoP plus a few model inputs is the standard small-team approach.
- Expected gains over an already-calibrated NBM PoP are likely single-digit % in Brier score. The ≥0.01 inch threshold is very sensitive to trace amounts and pop-up showers at one gauge. That makes a point forecast noisy, especially in summer convection (Miami, Austin).
- NBM issues 12-hour PoP blocks. A calendar-day PoP needs combining two blocks, which are not independent. That mapping itself is a calibration step a team must fit.

### Gaps
- No published Brier or calibration numbers for NBM v4/v5 PoP at single stations were found. MDL's Verification Viewer may hold them but was not reached.
- No study of daily (midnight-to-midnight, local standard time) PoP calibration for Kalshi rain markets was found.
- No station-level 2022-2026 head-to-head of gradient boosting vs logistic regression for ≥0.01 inch daily rain was found.

---

## 3. Which inputs add skill beyond NBM, and which station types are hardest

### Takeaway
The proven extra inputs are: (a) live observations at short range (the LAMP effect), (b) more models in a blend, now including AI models like AIFS, (c) per-station bias fixes for raw models, which run 1-5°F cold at stations. Hardest stations: cold-front cities in winter (NYC, Philadelphia, Chicago), mountain-terrain Denver, and coastal LAX. In those places the market beats NBM by the most. Miami is the easiest (NBM RMSE 1.6°F), and there the market barely beats NBM at all.

### Cited findings
- **Live observations drive the public forecasts' gains during the day.** LAMP (the NWS hourly guidance that uses live station observations) was the biggest reason the public blend closed in on the market. Dropping LAMP from the blend raised the market's lead from 3.1/4.3/3.0% to 3.3/4.7/6.4% at the three time points. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- **Raw models run cold at stations.** Taking the max of hourly values understates the daily high. Grid cells also miss local conditions. HRRR ran up to about 2°F cold, ECMWF 1-5°F, LAMP 1-2°F, depending on the city. Each was fixed with its 365-day trailing mean error. Source: [Crosier 2026, Appendix A.3](https://arxiv.org/html/2609.23969v1).
- **Most useful features in a neural post-processor** (permutation importance = how much the score worsens when one input is scrambled): the mean model temperature forecast first, then station height and model terrain height, then incoming sunlight and 850 hPa humidity (a stand-in for cloud cover). Ensemble spread was not useful; its link to actual error was weak (correlation 0.15). Source: [Rasp & Lerch 2018](https://ar5iv.labs.arxiv.org/html/1805.09091).
- **AI models add skill in a blend:** AIFS + ENS + HRES beat ENS + HRES significantly on MSE and CRPS at 569 stations. Source: [BoM, arXiv 2504.12672, Apr 2025](https://arxiv.org/html/2504.12672v1).
- **Hardest cities and seasons (Crosier, Sep 2026).** Day-before NBM RMSE was 1.6°F in Miami vs 2.6-3.5°F in the other six cities. The market's lead over NBM was 10-16% in Nov-Jun (when NBM error was 3°F or more) and 1-4% in Jul-Oct. Each extra 1°F of NBM error added about 6 percentage points to the market's lead (R² = 0.22, i.e. this explains about a fifth of the variation). Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- Market's lead over NBM at the opening hour, by season, as read from Crosier's Figure 4. The rows are assumed to follow the left panel's city order. Grey (not significant) cells are not marked in the text. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1):

| City (station) | Winter | Spring | Summer | Fall |
|---|---|---|---|---|
| New York (Central Park) | +15% | +12% | +8% | +6% |
| Chicago (Midway) | +16% | +12% | +6% | +12% |
| Miami (Miami Intl) | +6% | −2% | −4% | −5% |
| Austin (Bergstrom) | +7% | +5% | +4% | +4% |
| Philadelphia (PHL) | +18% | +16% | +3% | +8% |
| Denver (DEN) | +14% | +10% | +6% | +6% |
| Los Angeles (LAX) | +10% | +14% | +14% | +17% |

(Positive = the market's error is that much smaller than NBM's. Negative = NBM was better.)
- In Miami, traders stayed within 2°F of NBM on 98% of days. In Chicago they strayed 2°F or more on 20% of days. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- **Coastal and lakeshore problems are flagged in NBM itself.** NBM v5.0.14 (live 28 Jul 2026) fixed "anomalous" temperature and dewpoint guidance, worst in seasonal transitions, in coastal areas and along the Great Lakes shores. Source: [NWS SCN 26-70](https://www.weather.gov/media/notification/pdf_2026/scn26-70_nbmv5.0.14.pdf).
- **LAX sea breeze / marine layer:** MOS max-temperature guidance at LAX had a large warm bias in 2001, tied to sea-breeze timing and low cloud, both hard to predict (old models). Source: [Taylor, AMS 2003](https://weather.ou.edu/~aataylor/research/ams2003.html). A May 2026 NWS Los Angeles discussion describes marine-layer cloud holding highs in the upper 50s to low 70s. Source: [NWS LOX AFD, 13 May 2026](https://dd.meteo.gc.ca/today/bulletins/alphanumeric/20260513/FX/KLOX/09/FXUS66_KLOX_130930___63367).
- A practitioner bot builder (Feb 2026) blacklisted LA (marine layer) and Miami (cloud dynamics) as cities where models struggled. Source: [Weather Station Advisor, Mar-Jun 2026, citing Chris Dodds](https://weatherstationadvisor.com/home-weather-station-prediction-market/).
- **Central Park micro-climate:** on 24 Jul 2022, sensors in Central Park woodland read about 10°F cooler than street-tree sensors; sensors on lawns about 5°F cooler. The cooling was stronger at night. Source: [Central Park Conservancy Climate Lab](https://www.centralparknyc.org/central-park-climate-lab-cooling-study). A hobbyist found Central Park ran about 1.1°F cooler than a nearby Weather Underground station on southerly-wind days and 0.4°F warmer on strong northwest-wind days (2 months of data; anecdotal). Source: [Weather Station Advisor, Mar 2026](https://weatherstationadvisor.com/home-weather-station-prediction-market/).

### Inferences
- The cheapest proven extra input is recent observations: the day's temperatures so far, the last few days' forecast errors, and nearby stations. This matters most on the target day. Day-before forecasts (when Kalshi opens) gain less from observations.
- Nearby mesonets (NYS Mesonet, Synoptic) could help with fronts and sea breezes, but no measured gain for daily max at a single airport was found. Treat them as a hypothesis.
- LAX is a two-sided case. Public guidance is weak there (market lead 10-17% every season). The market has found local knowledge the public stack lacks. A model that learns marine-layer signals (onshore pressure gradient such as LAX-Daggett, inversion height, low cloud) is where a small team might add something. It is also where the market is already strongest relative to NBM.
- Miami is the reverse: NBM is already very good, and the market adds little or nothing. Edge from a better model there would come in tiny amounts. Because errors are small (about 1.6°F), the most likely bracket has a high probability (about 47% for a 2°F bracket under a bell curve), so prices are sharp.
- Midway sits near Lake Michigan, and the NBM v5.0.14 lakeshore fix suggests lake-breeze errors are a known NBM weakness there.

### Gaps
- No measured skill gain from mesonet data, satellite, or soil moisture for single-station next-day max temperature was found.
- Whether the Central Park ASOS itself runs cool vs its surroundings (siting bias) was not confirmed by any source found.
- Crosier's per-city RMSE values for each forecast appear only in a figure; the text gives no per-city table.

---

## 4. Training data needs and pitfalls

### Takeaway
Simple linear blends and EMOS work with about 1 year of data per station. Tree and neural methods need several years and usually many stations pooled together. A single station has only 365 cases a year. NBM has structural breaks (v4.1, v5.0 on 5 May 2026, v5.0.14 on 28 Jul 2026), and Kalshi's settlement source changed around 12-14 Aug 2026. Both break the link between old training data and today's errors. The largest practical risks are labelling mistakes (wrong day window, wrong truth source, wrong bracket edges), not the choice of model.

### Cited findings
- **Data length:** in Rasp & Lerch, linear methods gained almost nothing from 9 years vs 1 year. Boosted EMOS and the neural nets improved 4-5%. QRF improved most (0.95 → 0.81, about 15%) because it needs a minimum amount of data. One year of 537 stations was about 181,000 training cases. Source: [Rasp & Lerch 2018](https://ar5iv.labs.arxiv.org/html/1805.09091).
- **Training windows:** training over multiple years (with seasonal terms) beat the classical sliding window of only the most recent days. This held at plains, foreland and mountain stations. Source: [Lang, Lerch et al. 2020, NPG 27:23](https://npg.copernicus.org/articles/27/23/2020/).
- **NBM's own short memory:** NBM PoP uses 60-day CDFs plus look-alike locations. Source: [Hamill et al. 2017](https://repository.library.noaa.gov/view/noaa/28094). The v5.0.14 temperature fix (28 Jul 2026) added the current forecast to the quantile-mapping training sample. It gave more weight to recent days, widened the mapped range from the 10th-90th to the 2nd-98th percentiles, replaced the tail regression with a mean bias fix, and removed ACCESS model inputs. Source: [NWS SCN 26-70](https://www.weather.gov/media/notification/pdf_2026/scn26-70_nbmv5.0.14.pdf).
- **NBM version breaks:** v5.0 went live 5 May 2026 (delayed from April). Its main focus was more probabilistic products and aligning the single-number and probability calculations. Sources: [MDL NBM v5.0 announcement](https://vlab.noaa.gov/web/mdl/-/national-blend-of-models-nbm-upgraded-to-version-5.0-1); [SCN 26-24](https://www.weather.gov/media/notification/pdf_2026/scn26-24_Updated_NBM_V5.0_aac.pdf). A bug-fix followed on 18 Jun 2026. Source: [SCN 26-58](https://www.weather.gov/media/notification/pdf_2026/scn26-58_Blendv5.0_bug_fix.pdf). NBM v4.1 recalibrated max/min temperature inputs to METAR station observations instead of the URMA grid analysis. Source: [SCN 22-131](https://www.weather.gov/media/notification/pdf2/scn22-131_nbm_v4.1.pdf).
- **As-issued archives used by Crosier:** NBM station bulletins and NDFD from NOAA Open Data Dissemination buckets; GFS MOS and LAMP from the Iowa Environmental Mesonet (IEM); HRRR and ECMWF from their open-data archives. IEM keeps only the 00/06/12/18 UTC LAMP cycles, so the freshest archived LAMP was 2 hours old at market open. Source: [Crosier 2026, Appendix A.3](https://arxiv.org/html/2609.23969v1).
- **Daytime vs calendar-day max:** NBM, NDFD and MOS forecast a daytime max. Kalshi settles on the full calendar-day max. On 4.6% of days the high fell outside the daytime window. Source: [Crosier 2026, Appendix A.2](https://arxiv.org/html/2609.23969v1).
- **Local standard time:** NWS climate reports use local standard time. During daylight saving the "day" runs 1:00 AM to 12:59 AM the next day. Source: [Weather Station Advisor, citing Kalshi help docs](https://weatherstationadvisor.com/home-weather-station-prediction-market/).
- **Settlement source change:** Kalshi moved from the NWS climate report to The Weather Company after 12 Aug 2026. Source: [Crosier 2026, footnote 2](https://arxiv.org/html/2609.23969v1). Gizmodo reports NYC market notes saying Weather Company settlement starts 14 Aug. Sources: [Gizmodo, Aug 2026](https://gizmodo.com/kalshi-teams-up-with-the-weather-co-on-markets-that-are-nearly-impossible-to-insider-trade-2000803871); [Artemis](https://artemis.bm/news/prediction-market-kalshi-partners-with-the-weather-company-for-weather-hedge-settlements). Kalshi's help centre still said daily high/low markets settle on the NWS climate report, so it may be out of date. Source: [Kalshi help: Weather markets](https://help.kalshi.com/en/articles/13823837-weather-markets).
- **Practitioner labelling pitfalls (a practitioner's write-up, unverified, mid-2026):** Kalshi brackets cover two whole °F values, both included (B74.5 = 74 and 75). Treating them as 1°F half-open windows made a "+1640%" phantom backtest edge. Scoring against a home-made truth instead of the venue's result flipped about 10% of outcomes. Building features on UTC days instead of local-standard-time days cost about 14 percentage points of accuracy. Assuming fills at 1¢ asks overstated profit about 23×. The ticker date is the settlement date; `close_time` falls on the next UTC day. Kalshi uses KNYC (Central Park) while Polymarket uses KLGA (LaGuardia). Source: a practitioner's write-up (not linked).
- **Liquidity and history:** Crosier's quality screens dropped 14% of observations, mostly from 2022-2024. Without the screens, the market's lead over the public blend shrank to 1.9/3.2/0.7%. Source: [Crosier 2026, Appendix B.2](https://arxiv.org/html/2609.23969v1). Market histories are short: LAX 585 days, Philadelphia and Denver 631, Miami 1,189, NYC and Chicago 1,684. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).

### Inferences
- A single station with 2-4 years of as-issued NBM is about 700-1,500 cases. That supports a linear blend or EMOS with a handful of inputs and seasonal terms. A per-station gradient-boosting model or neural net with many inputs is likely to overfit. Pooling several stations (with a station ID input) is the way to use ML.
- Given the 5 May and 28 Jul 2026 NBM changes, NBM's error pattern after July 2026 has under 3 months of history. Any model leaning on "NBM's usual bias" needs recency weighting or a version flag, and should be re-checked out-of-sample after each version change.
- The Weather Company settlement switch means labels before and after mid-Aug 2026 may differ on some days (rounding, conversion, backup stations). Check this before training on post-switch data.
- Use only as-issued forecasts with timestamps (NOAA ODD buckets, IEM). Re-run or reanalysis-based forecasts leak future knowledge.

### Gaps
- The exact years IEM's NBM/MOS text archives begin could not be confirmed (the research plan assumed 2018-2020). The IEM MOS dataset page was not reached.
- No source quantified how often Weather Company settlement values differ from the NWS climate report.
- No study measured how much a single US station's post-processing skill drops after an NBM version change.

---

## 5. Practitioner evidence: competitions, provider verification, trader writeups

### Takeaway
Consumer providers' next-day high-temperature MAE is about 2.5-3°F. Differences between top providers are a few tenths of a degree. Two 2026 studies of prediction markets (Kalshi; ForecastEx) find the market beats every single public product by 10-25%, but beats a blend of them by only about 2-4%. Trader writeups of model-vs-market bots show big backtest win rates that collapsed live. No public writeup was found showing a model beating Kalshi temperature prices after fees.

### Cited findings
- **ForecastWatch:** global 2015 high-temperature MAE (1-5 days out): AccuWeather 2.799°F, The Weather Channel 2.869, Weather Underground 2.872, Intellicast 3.091, Foreca 3.097, Dark Sky 3.715. Source: [ForecastWatch 2015 report hosted by AccuWeather](https://corporate.accuweather.com/wp-content/uploads/sites/3/2022/03/AccuWeather_Success_2015_ForecastWatch_Temperature_Report.pdf). US Jan-Jun 2015: about 1°F between best and worst provider; 4.7 million forecasts at 792 US sites. Source: [ForecastWatch US high temps Jan-Jun 2015](https://forecastwatch.com/wp-content/uploads/USHighTempsJanJun2015.pdf).
- One-day-out high-temperature errors averaged under 3°F by 2016, with about 33% improvement from 2005 to 2016 (nearly 200 million checks at about 800 sites). Source: [ForecastWatch 12-year study](https://forecastwatch.com/downloads/forecastwatch-data-analysis-report-12-year-forecast-accuracy/).
- 2024 (published 31 Jul 2025): 15 providers plus persistence (tomorrow = today). The Weather Channel ranked first for global high temperature. Microsoft ranked first overall (79.51%), TWC second (79.23%), Foreca third (77.69%). No MAE numbers or NWS/NBM comparison on the public page. Source: [ForecastWatch 2025](https://forecastwatch.com/2025/07/31/new-report-analysis-of-2024-one-to-five-day-out-forecasts/).
- A 2020-2024 single-station study (Mount Washington summit) found GFS MOS, NAM MOS and NBM within 1°F MAE of each other, rising from about 2°F to 3°F with lead time. Source: [Mount Washington Observatory](https://mountwashington.org/wp-content/uploads/2024/08/KMWN_MOS_Verification.pdf).
- **ForecastEx markets (Patrick Brown, Interactive Brokers articles, 2026):** through 14 Apr 2026, ForecastEx beat NWS LAMP in 20 of 23 cities, with a median gain of about 17.2%. By Sep 2026, at meaningful lead times, ForecastEx had 21-25% lower daily-high errors than the next-best of twenty alternatives. Sources: [IBKR Campus, Apr 2026](https://www.interactivebrokers.com/campus/traders-insight/april-13-2026-update-prediction-markets-might-already-be-the-best-source-for-todays-weather-forecast/); [IBKR Campus series](https://www.interactivebrokers.com/campus/traders-insight/ibkr-climate-energy/prediction-markets-might-already-be-the-best-source-for-todays-weather-forecast/). Pages returned 403 to direct fetch; figures are from search snippets. Published by the broker that runs these markets, so not independent. Crosier says Brown's working paper (18 Sep 2026, 24 sites, seven months) finds the market ahead of a de-biased combination "by a much smaller margin". Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- **Information flow:** NBM revisions move toward the market about four times as far as the market moves toward NBM. A typical 1.49°F disagreement moved NBM 0.063°F. A typical 0.43°F NBM revision moved the market 0.016°F. In Chicago, after a 1°F NBM revision, the market moved only about 2% of it, with no jump at release. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- **Trader writeups:** Chris Dodds' GFS-based Kalshi bot (Feb 2026 writeup): backtest 678 days with an 86% win rate selling overpriced brackets; about 60% live; returns fell below breakeven and he shut it down. His conclusion: the model "doesn't reliably tell you which bracket will actually win". Source: [Weather Station Advisor, citing Dodds](https://weatherstationadvisor.com/home-weather-station-prediction-market/) (secondary source; the original was not found).
- A 14-day paper test (1-14 Mar 2026, Central Park) picked 14 of 14 brackets with a GFS ensemble plus a local bias fix vs 9 of 14 for the market favourite. The author called this "too good" and expected 60-70% over a longer run. Source: [Weather Station Advisor, Mar 2026](https://weatherstationadvisor.com/home-weather-station-prediction-market/).
- An open-source bot (GFS 31-member ensemble via Open-Meteo, trades when the gap exceeds 8%, bets 15% fractional Kelly; Kelly is the bet size that grows money fastest without risking ruin) publishes no backtest. Source: [GitHub suislanchez/polymarket-kalshi-weather-bot](https://github.com/suislanchez/polymarket-kalshi-weather-bot).
- A practitioner's write-up reports per-city out-of-sample Brier scores of 0.07-0.14 for its bracket probabilities vs 0.25 for climatology. It argues "forecast skill isn't trading edge" because markets already price weather models. It says the practical edge is maker-side fading of longshot brackets, with no figure given. Source: a practitioner's write-up (not linked). Unverified.
- Bot for Kalshi's "weather edge" demo defines edge as model-vs-market disagreement, not proven profit. It uses city-centre coordinates while Kalshi settles on one station. Source: [botforkalshi.com](https://www.botforkalshi.com/tools/kalshi-weather-edge).
- A July 2026 commentary piece says AI-model forecasts for NYC highs track the market closely. Source: [Stokastic](https://www.stokastic.com/articles/prediction-markets/nyc-high-temp-tomorrow-model-verdict). Low evidential weight.

### Inferences
- The ForecastWatch numbers (about 2.8°F MAE, 1-5 days, older years) and Crosier's numbers (NBM about 2.7°F RMSE day-ahead) put public skill in the same zone. The best consumer providers and NBM differ by tenths of a degree, not degrees.
- The pattern across trader writeups: backtests look great, live results fade. That matches adverse selection (getting picked off by someone who knows more). When a public-data model disagrees with the price, the market is often right.

### Gaps
- No Kaggle or other public competition on US station daily max/min temperature or daily PoP from 2022-2026 was found. WeatherBench 2 is gridded.
- No ForecastWatch/ForecastAdvisor numbers comparing private providers with NWS/NBM at Kalshi stations were reached. A ForecastAdvisor city page returned 404.
- No writeup with out-of-sample, after-fee profits from a model vs Kalshi temperature prices was found.

---

## 6. Bottom line: can a realistic ML blend beat ~2.44°F day-ahead RMSE (market level), and is that enough after a 1¢ spread and the taker fee?

### Takeaway
Probably not by a margin that pays. A well-built public blend reaches about 2.43-2.45°F, roughly the market's level, and it does not beat the market on matched days (market 2.38°F vs plain average 2.43°F). ML on top could add a few % in hard seasons and cities. But the market already contains the public forecasts. So the only real edge is information or speed the market lacks. If a team truly had a forecast 3% better than the market using extra information, a best-case calculation gives roughly 2¢ profit per contract after costs. Real-world adverse selection and thin depth would likely eat most of that.

### Cited findings
- The market (2.44°F) vs out-of-sample public blend (2.45°F) at market open. On matched days the market scored 2.38°F vs 2.43°F (plain average) and 2.45°F (fitted blend). Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- The market's lead is biggest when weather is hardest (Nov-Jun, frontal cities, LAX). It is smallest or absent in Miami and in Jul-Oct. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- Without liquidity screens, the market's lead over the public blend falls to 1.9/3.2/0.7%. The target-morning lead is not significant (could be luck). Source: [Crosier 2026, Appendix B.2](https://arxiv.org/html/2609.23969v1).
- The market does not react to NBM updates; NBM drifts toward the market. Source: [Crosier 2026](https://arxiv.org/html/2609.23969v1).
- The best ML methods beat a per-station calibrated method by about 3-13% CRPS (European stations, pooled hundreds of stations). Sources: [Rasp & Lerch 2018](https://ar5iv.labs.arxiv.org/html/1805.09091); [arXiv 2412.13957](https://arxiv.org/pdf/2412.13957).
- Fee assumption: Kalshi taker fee = 0.07 × p × (1 − p) per contract. The project's own order records (Oct 2026) show fees round up per order to $0.0001, so rounding is negligible for multi-contract orders (a project finding, not a web source).

### Inferences
**Costs on 2°F brackets.** These are the project's own calculations from the fee formula above and a 1¢ spread (buying at the ask pays the midpoint plus 0.5¢):

| Bracket price (chance) | Taker fee per contract | Half the spread | Total cost per contract |
|---|---|---|---|
| 10¢ (10%) | 0.63¢ | 0.5¢ | about 1.1¢ |
| 32¢ (32%, a typical top bracket when the miss is about 2.4°F) | 1.52¢ | 0.5¢ | about 2.0¢ |
| 50¢ (50%) | 1.75¢ | 0.5¢ | about 2.25¢ |

- With a typical miss of 2.44°F (and a bell-shaped error), the most likely 2°F bracket wins only about 32% of the time. In Miami (about 1.6°F) it is about 47%.

**Best-case edge simulation** (the project's own Monte Carlo, 20,000 simulated days per row). Assumptions:
  - The trader knows everything the market knows, plus extra.
  - Both forecasts are bell-shaped and perfectly calibrated.
  - Fills happen at the midpoint plus 0.5¢, with unlimited depth.
  - The trader buys YES or NO on any bracket whose edge beats the costs above.

Under these assumptions, a forecast X% better than the market means the two forecasts typically differ by d = √(2.44² − RMSE²).

| Trader's RMSE vs market's 2.44°F | Typical gap from market | Trades per day | Profit per contract after costs | Cents of profit for every dollar bet |
|---|---|---|---|---|
| 2.42°F (0.8% better) | 0.31°F | 2.4 | about 1.1¢ | about 2.1¢ |
| 2.37°F (2.9% better) | 0.58°F | 4.1 | about 1.9¢ | about 3.6¢ |
| 2.30°F (5.7% better) | 0.81°F | 5.1 | about 2.8¢ | about 5.2¢ |
| 2.20°F (9.8% better) | 1.06°F | 5.8 | about 3.5¢ | about 6.3¢ |

- **This is an upper bound, not a forecast of profit.** The key assumption (knowing everything the market knows) is false for a public-data model. In reality you must blend your model with the market price. Then your true edge is only the information the market lacks.
  - Example: combine the market (2.44°F) with a public blend (2.45°F) whose errors are 90% correlated with the market's. The combined forecast is only about 2.38°F (2.4% better). At 95% correlation it is about 2.41°F (1.1% better).
  - If the market already contains all public information, as Crosier's theory says, a public-only blend adds about nothing.
- Practitioner evidence (Dodds: 86% backtest → about 60% live → shut down) shows live disagreement with the price is often adverse selection, not edge.
- **Where a small team might still look:**
  1. On the target day, using live observations faster than the market. The LAMP effect shows observations matter most then. IEM's archive has only 6-hourly LAMP, so an hourly self-built version could be fresher.
  2. LAX marine-layer days and frontal winter days, where errors are large. But that is also where the market already adds the most.
  3. Thin, early, or stale books, where the market mean is noisy. But Crosier's screens show thin books are mostly a 2022-2024 thing.
- **The decisive test a team should run before building ML:** an "encompassing" test. Regress the observed high on the market's implied mean plus the team's blend, out-of-sample. If the blend gets near-zero weight, there is no edge to trade, however good the model's RMSE looks against NBM.
- Project context (not a web source): the project's own 26 Oct 2026 test of buying daily-high favourites failed (−24.5¢ per $10). That fits the view that public-forecast edge in these markets is already priced.

### Gaps
- No published out-of-sample test of whether a public forecast blend adds information beyond the Kalshi price (the encompassing regression) was found. Crosier compares accuracy but does not regress the outcome on both.
- No source gave real depth (how much money can be traded before moving the price) on Kalshi temperature brackets, so the simulation's "unlimited depth at mid + 0.5¢" is untested.
- The market's bracket prices may carry a favourite-longshot bias (cheap unlikely bets overpriced, heavy favourites underpriced) that is separate from forecast skill. No calibration study of Kalshi temperature bracket prices was found. Crosier did none.
- Min-temperature and rain-market equivalents of Crosier's study were not found.
