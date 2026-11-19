# AI weather models vs the free NOAA National Blend (NBM) for Kalshi station highs and rain

Research date: 26 Oct 2026. Scope: daily high/low temperature and "measurable rain" at one US airport station, same-day and next-day.

Plain-words key for terms used below (repeated where they first matter):
- **Ensemble** = many runs of a model from slightly different starts; the spread gives probabilities. **Deterministic** = one single answer.
- **0.25° grid** = the model's boxes are about 28 km (17 miles) wide. A station is one point inside a box.
- **00z / 12z** = model runs started at midnight / noon UTC (8 pm / 8 am US Eastern daylight time).
- **RMSE** (root-mean-square error) = the typical size of a miss, in °F; lower is better.
- **CRPS** = an error score for a whole forecast range, not just one number; lower is better. "CRPS skill 25%" = a 25% smaller error score than the comparison.
- **Brier score** = an error score for yes/no probability forecasts (like "rain: 40%"); lower is better.
- **MOS / post-processing** = a statistical correction that turns raw model output into a station forecast.
- **Preprint** = not yet peer reviewed.

---

## 1. Which models matter, and which give probabilities (ensembles) vs one answer

### Takeaway
As of Oct 2026 the AI models that matter for a US trader are: ECMWF's AIFS (single run + 51-member ensemble, operational since 2025, free and commercial-use OK), NOAA's AIGFS / AIGEFS / HGEFS (operational since 17 Dec 2025), and Google's WeatherNext 2 (Nov 2025) and WeatherNext 3 (Sept 2026, hourly, about 5 km, trained to hit station readings). GraphCast, Pangu, Aurora and FourCastNet are now research-grade "first generation" models; ECMWF stopped running them in May 2026.

### Cited findings

**ECMWF AIFS (Europe)**
- AIFS Single (one deterministic run) has been fully operational at ECMWF since 25 Feb 2025; version 1.1.0 was released 27 Aug 2025 to fix a rain bug in the first version. Source: [AIFS update paper, arXiv 2509.18994](https://arxiv.org/html/2509.18994v1)
- AIFS ENS, the ensemble version with 51 members, went operational on 1 July 2025, running alongside the physics model IFS. Source: [ECMWF news](https://www.ecmwf.int/node/29407)
- Both were upgraded to v2 on 12 May 2026 (06 UTC run), at the same time as IFS moved to Cycle 50r1. AIFS Single v2 kept the same architecture; AIFS ENS v2 had "scientific and architectural changes" and went from 13 to 14 pressure levels. Sources: [ECMWF Confluence, AIFS Single v2](https://confluence.ecmwf.int/display/FCST/Implementation+of+AIFS+Single+v2); [ECMWF forum, 50r1 + AIFS v2](https://forum.ecmwf.int/t/ifs-cycle-50r1-and-aifs-v2-implementation-planned-for-12-may-2026/14781)
- AIFS v3 (single and ensemble) is "pencilled in" for Q4 2026, configuration not yet confirmed. Source: [ECMWF Confluence / UEF2026 slides via search](https://events.ecmwf.int/event/524/contributions/6111/attachments/3689/6234/UEF2026_ECMWF%20updates.pdf)
- With the v2 upgrade, ECMWF stopped running the third-party experimental models Aurora, FourCastNet, GraphCast and Pangu-Weather. Source: [ECMWF AIFS dataset page](https://www.ecmwf.int/en/forecasts/datasets/aifs-machine-learning-data)

**NOAA (US)**
- On 17 Dec 2025 NOAA made three AI global systems operational: AIGFS (deterministic), AIGEFS (31-member AI ensemble) and HGEFS (a 62-member "hybrid" grand ensemble merging AIGEFS with the physics GEFS). They came out of Project EAGLE. Sources: [HPCwire, 17 Dec 2025](https://www.hpcwire.com/aiwire/2025/12/17/noaa-deploys-new-generation-of-ai-driven-global-weather-models/); [ForecastWatch, 6 Jan 2026](https://forecastwatch.com/2026/01/06/noaa-launches-new-suite-of-weather-models/)
- NOAA claims: AIGFS uses "up to 99.7% less computing resources" and makes a 16-day forecast in 40 minutes; AIGEFS extends skill by "an additional 18 to 24 hours" over GEFS using 9% of the compute; HGEFS "consistently outperforms" both AI-only and physics-only ensembles. These are agency claims; ForecastWatch's page gives no independent scores. Source: [ForecastWatch](https://forecastwatch.com/2026/01/06/noaa-launches-new-suite-of-weather-models/)

**Google DeepMind / Google Research**
- GraphCast (Lam et al., Science 2023): deterministic, 0.25°, 6-hourly steps. Open-Meteo hosted it with 4 runs/day. Source: [Open-Meteo "Exploring GraphCast"](https://openmeteo.substack.com/p/exploring-graphcast)
- GenCast (Price et al., Nature, Dec 2024): diffusion ensemble; beat ECMWF's ENS on 97.2% of 1,320 targets, and 99.8% at lead times beyond 36 hours. Source: [DeepMind blog, 4 Dec 2024](https://deepmind.google/discover/blog/gencast-predicts-weather-and-the-risks-of-extreme-conditions-with-sota-accuracy/)
- WeatherNext 2, announced 17 Nov 2025: "Functional Generative Network" ensemble, 64 members in one pass, 0.25°, 6-hour steps, 15 days; 8x faster than WeatherNext Gen and better on 99.9% of tested variables/lead times *versus WeatherNext Gen* (not vs all models). Used in Search, Gemini, Pixel Weather and the Google Maps Weather API. Sources: [Google developer docs, WN2](https://developers.google.com/weathernext/guides/models-wn2); [ascii.co.uk, 18 Nov 2025](https://ascii.co.uk/news/article/news-20251118-2432a985/google-deepmind-releases-weathernext-2-ai-forecasting-model)
- WeatherNext 3, released 3 Sept 2026 (press; Google's developer page says Aug 2026): about 5 km resolution, hourly forecasts, started every hour, ingests raw hourly satellite data, 2.4x the parameters of WN2, and "trained to target specific weather data stations" (TechCrunch's example: hourly readings at Denver airport). Sources: [TechCrunch](https://techcrunch.com/?p=3160336); [WeatherNext 3 search summary / dev guide](https://developers.google.com/weathernext/guides/models?authuser=1)
- WeatherNext 3 is a 64-member raw ensemble; Earth Engine and BigQuery carry precomputed mean and percentiles on a 0.1° grid and a 0.05° "station" product. Source: [WeatherNext access guide](https://developers.google.com/weathernext/guides/access-forecast)
- Google's developer site now lists WeatherNext Gen, Graph and 2 as "previous models" with a deprecation page. Source: [WeatherNext access guide](https://developers.google.com/weathernext/guides/access-forecast)

**Microsoft, NVIDIA, Huawei**
- Microsoft Aurora (Bodnar et al., Nature, May 2025): code and weights are public; a variant gives hourly forecasts in MSN Weather. Sources: [TechCrunch, 23 May 2025](https://techcrunch.com/2025/05/23/microsoft-says-its-aurora-ai-can-accurately-predict-air-quality-typhoons-and-more/); [Microsoft blog](https://blogs.microsoft.com/on-the-issues/?p=67317)
- NVIDIA Earth-2 (Jan 2026, AMS meeting): new open models "Earth-2 Medium Range" (new "Atlas" architecture, 15-day global), "Earth-2 Nowcasting" (StormScope) and "Earth-2 Global Data Assimilation" (HealDA), alongside FourCastNet 3 and CorrDiff (downscaling). FourCastNet 3 adds probabilistic ensembles out to 60 days. Early users named: US National Weather Service, Taiwan CWA, The Weather Company. Sources: [Meteorological Technology International](https://www.meteorologicaltechnologyinternational.com/news/digital-applications/nvidia-launches-open-earth-2-model-family-for-ai-weather-forecasting.html); [NGC FourCastNet container](https://catalog.ngc.nvidia.com/orgs/nim/nvidia/containers/fourcastnet/-)
- Huawei Pangu-Weather (Bi et al., Nature 2023): deterministic; weights free but under a non-commercial licence. Sources: [IT Brief](https://itbrief.co.uk/story/huawei-s-pangu-weather-ai-model-is-now-free-for-public); [OpenI Pangu repo](https://openi.pcl.ac.cn/AI4NWP/Pangu-Weather)

**Probabilistic vs single-answer, at a glance**

| Model (owner) | One answer or ensemble | Grid size | Status, Oct 2026 |
|---|---|---|---|
| AIFS Single (ECMWF) | One answer | 0.25° (~28 km) | Operational since Feb 2025; v2 May 2026 |
| AIFS ENS (ECMWF) | Ensemble, 51 runs | 0.25° (~31 km model grid) | Operational since July 2025; v2 May 2026 |
| AIGFS / AIGEFS / HGEFS (NOAA) | One answer / 31 runs / 62 runs | 0.25° (AIGFS) | Operational since 17 Dec 2025 |
| WeatherNext 2 (Google) | Ensemble, 64 runs | 0.25° | Live Nov 2025; now "previous model" |
| WeatherNext 3 (Google) | Ensemble, 64 runs | ~5 km; 0.05° station product | Live Sept 2026 |
| GraphCast, Pangu, Aurora | One answer | 0.25° (Aurora also 0.1°) | Research; ECMWF stopped running them May 2026 |
| GenCast, FourCastNet 3 | Ensemble | 0.25° | Research / open models |

(Grid sizes from the sources above; AIGFS 0.25° from [Herbie docs](https://herbie.readthedocs.io/en/latest/gallery/noaa_models/aigfs.html).)

### Inferences
- The field split in 2025-2026: deterministic "first generation" models (GraphCast, Pangu, Aurora, FourCastNet) are now baselines. The live race is between AI **ensembles** (AIFS ENS, AIGEFS/HGEFS, WeatherNext 2/3). For Kalshi's bracket ladders, which price a whole spread of outcomes, the ensembles are the relevant ones.
- WeatherNext 3 is the only model built to forecast **station** readings directly. It is the only candidate that targets the same thing Kalshi settles on.

### Gaps
- What AIGFS is built on was not confirmed. Some reports call it GraphCast-based; the sources fetched for this note did not say.
- No primary-source specs for Aurora's licence or for whether the MSN integration still runs in 2026.
- Brightband's "Operational WeatherBench" leaderboard (owb.brightband.com) is shown only as an image; its model list and scores could not be read.

---

## 2. Accuracy vs traditional models for 2-metre temperature and rain, at day 0-2 and at stations

### Takeaway
On global grid scores, AI ensembles now beat ECMWF's physics ensemble, including for heat extremes (one Oct 2026 preprint: WeatherNext 2 has a 25% smaller error score than raw IFS ENS for 2 m temperature over land at 3 days). But there is almost no published test at **US stations, at day 0-2, against NBM or MOS**. Known weak spots for station work: smoothing, cold biases in heat waves, a 0.25° box vs one airport, 6-hourly steps that miss the daily peak, and under-forecasting heavy rain.

### Cited findings

**Temperature, grid and station**
- Wessel et al. (preprint, 14 Oct 2026), 2 m temperature over land, year 2022, 0.25°, 00 UTC runs, 12-120 h leads. Against raw ECMWF IFS ENS at 72 h: CRPS skill (smaller error score) WeatherNext 2 = 25%, WeatherGen (GenCast-based) = 17%, statistically corrected IFS (EMOS) = 14%. Source: [arXiv 2610.20519](https://arxiv.org/html/2610.20519)
- Same paper, record heat: share of records missed by *every* ensemble member was 39-45% for IFS, 9-17% for WeatherNext 2. At 5,778 weather stations (HadISD), WeatherNext 2 improved the record-heat Brier score (yes/no probability error) by 10% at 72 h and 19% at 84 h. Against ERA5 as "truth", the AI advantage shrinks and is inconsistent. Source: [arXiv 2610.20519](https://arxiv.org/html/2610.20519)
- The opposite finding for one-answer models: deterministic AI models underestimate how often and how hard record heat, cold and wind happen, with larger errors than ECMWF HRES at nearly all leads (Zhang et al.) Source: [arXiv 2508.15724](https://arxiv.org/html/2508.15724v1). Wessel et al. argue this is because single-answer AI models forecast an *average*, which is smoothed by design. Source: [arXiv 2610.20519](https://arxiv.org/html/2610.20519)
- US heat waves (60 events): both AI models and the physics GEFS ensemble run cold 5-10 days before onset; GraphCast beat GEFS and Pangu at most locations; GraphCast shows a consistent cold bias during heat waves. Source: [arXiv 2504.21195](https://arxiv.org/pdf/2504.21195)
- Station test over China, 2022-2025, same starting data for all models: GraphCast's station error score (PCRPS) was 8.0% better than GFS at 24 h after statistical correction. Model rankings did not hold steady across 2024-2025 (from search snippet; preprint). Source: [ResearchGate preprint](https://www.researchgate.net/publication/415274447_Do_AI_weather_models_forecast_extremes_better_than_GFS_A_station-based_verification_over_China_with_a_common_initialization_source_2022-2025)
- Australia, 569 automatic weather stations, Mar-Jul 2024: after the Bureau of Meteorology's standard correction system (IMPROVER), AIFS beat ECMWF HRES for temperature and dew point "after the first few lead days," with the gap widening at longer leads; at short leads post-processed AIFS was "similar to ENS". Source: [Trotta et al., arXiv 2504.12672](https://arxiv.org/html/2504.12672v1)
- NOAA poster (UIFCW, July 2026): AIGFS v1.0 reduced 2 m temperature bias over the continental US vs GFS v16; no bias sizes given; routine NOAA verification of AIGFS began 16 June 2026. Source: [NOAA EPIC poster](https://epic.noaa.gov/wp-content/uploads/2026/07/15.-Qi_Shi_UIFCW26_Poster_virtual.pdf)
- WeatherNext 3 reportedly ranked most accurate on Brightband's Operational WeatherBench for temperature, wind and humidity, and beat NWS and ECMWF forecasts (no scores published in the article). Source: [TechCrunch](https://techcrunch.com/?p=3160336)

**Rain**
- AIFS 1.1 vs IFS on 24-hour station rain totals (2023): about a one-day gain in skill (SEEPS, a standard rain score), up to 12% better at short range. But AIFS still over-predicts light rain, and under-forecasts events above 10 mm (it forecasts heavy rain less often than it happens). Source: [arXiv 2509.18994](https://arxiv.org/html/2509.18994v1)
- AIFS training to minimise squared error causes smoothing; its cloud-cover distribution is "much flatter" than observed (too few fully clear and fully overcast cases). Source: [arXiv 2509.18994](https://arxiv.org/html/2509.18994v1)
- vs a high-resolution regional physics model (WRF), 2026: at a 1 mm threshold AIFS had the best hit rate (0.835) and GraphCast the best overall hit score (CSI 0.424); at heavy rain (20 mm per 6 h) WRF won (search snippet). Source: [GMD 2026](https://gmd.copernicus.org/articles/19/9831/2026/)
- WeatherNext 3: Google says day-ahead rain forecasts are "up to 50 percent more accurate"; TechCrunch reports "60% better" than WeatherNext 2. Vendor claims, metric not stated. Sources: [TechCrunch](https://techcrunch.com/?p=3160336); [ProPakistani](https://propakistani.pk/2026/09/05/google-weathernext-3-makes-forecasts-five-times-sharper/)

**The grid-box and daily-peak problem (from the market study)**
- Raw gridded models run cold at stations when you take the highest hourly value as the daily high: in the Kalshi study, raw ECMWF ran 1-5 °F cold and HRRR up to about 2 °F cold, depending on city, and needed a rolling bias correction. Reasons: the highest of several hourly *averages* is below the true peak; the official high often falls between hours; and a grid box averages over area. Source: [Crosier, arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- AIFS open data has 6-hourly steps. Source: [ECMWF AIFS dataset page](https://www.ecmwf.int/en/forecasts/datasets/aifs-machine-learning-data); WeatherNext 2 also uses 6-hour steps (some fields hourly). Source: [Google WN2 docs](https://developers.google.com/weathernext/guides/models-wn2)

### Inferences
- A raw AI model at 0.25° and 6-hourly steps cannot see the afternoon peak at one airport. It needs station-level statistical correction (MOS-style) before it can compete with NBM. NBM already does that correction.
- The AI advantage is clearest at day 3+ and on whole-distribution scores. At day 0-1, the edge over well-corrected physics models is small or unproven. That is exactly the window Kalshi trades.
- Ensembles matter more than one-answer models for brackets: the evidence on tails (record heat) favours AI *ensembles*, and disfavours one-answer AI models.

### Gaps
- **No** peer-reviewed or agency study was found comparing any AI model against NBM, MOS or LAMP at US airport stations for daily max/min at day 0-2.
- No published station-level probability-of-rain (PoP) test for AI models in the US.
- No data on whether AIFS open data includes 6-hourly max/min temperature fields (which would help with the daily peak). The parameter list was not verified.

---

## 3. How to get the forecasts: feeds, delay, resolution, licence, archives

### Takeaway
ECMWF AIFS is the easiest: free, 0.25°, four runs a day, CC BY 4.0 (commercial use allowed), archive back to Feb 2024 (single) and July 2025 (ensemble). NOAA AIGFS is on NOMADS. Google WeatherNext is free after a sign-up form, but arrives about 7-8 hours after each run and the real-time data sits under "experimental" terms that do not clearly allow trading. Every archive mixes model versions, which weakens backtests.

### Cited findings

**ECMWF AIFS**
- Open data on a regular 0.25° grid, 6-hourly to 15 days, runs at 00/06/12/18 UTC. "Real-time open data are released as soon as the forecast is produced" (no minutes given). Source: [ECMWF AIFS dataset page](https://www.ecmwf.int/en/forecasts/datasets/aifs-machine-learning-data)
- Licence: CC BY 4.0 plus ECMWF Terms of Use; "redistribution and commercial use are allowed with appropriate attribution". Source: [ECMWF AIFS dataset page](https://www.ecmwf.int/en/forecasts/datasets/aifs-machine-learning-data)
- Archive: AIFS Single from Feb 2024, AIFS ENS from July 2025, via ECMWF's archive/MARS (registration needed). A forum reply says AIFS data is also on AWS from Feb 2025. Sources: [ECMWF dataset page](https://www.ecmwf.int/en/forecasts/datasets/aifs-machine-learning-data); [ECMWF forum](https://forum.ecmwf.int/t/aifs-historical-archive-and-hindcasts/12589)

**NOAA AIGFS family**
- NOMADS lists AIGFS as a global model updated every 6 hours, over HTTPS (no "grib filter" subsetting option listed). Source: [NOMADS](https://nomads.ncep.noaa.gov)
- Herbie (a Python download tool) supports AIGFS 0.25° pressure and surface GRIB2 files from NOMADS. Source: [Herbie docs](https://herbie.readthedocs.io/en/latest/gallery/noaa_models/aigfs.html)
- A third-party archive at UW-Madison THREDDS keeps AIGFS 0.25° files from late 2025. Source: [UW-Madison THREDDS](https://thredds.aos.wisc.edu/thredds/catalog/grib/NCEP/AIGFS/Global_0p25deg/catalog.html)

**Google WeatherNext**
- Access: one sign-up form, approved in about 5-7 business days, covers Cloud Storage, BigQuery and Earth Engine; "anyone with a Google Account" can access; no paid contract. Source: [WeatherNext access guide](https://developers.google.com/weathernext/guides/access-forecast)
- Licence: WN3 real-time data (under 1 hour old, plus future times) falls under the "GDM Real-Time Weather Forecasting Experimental Data Terms of Use"; data 1 hour old or more is CC BY 4.0. For WN2 the cut-off was 48 hours. Sources: [WeatherNext access guide](https://developers.google.com/weathernext/guides/access-forecast); [WN2 Earth Engine summary via search](https://developers.google.com/weathernext/guides/earth-engine)
- Delay after each run (target times, ±15 min, sometimes ±60 min or more). Source: [WeatherNext dissemination schedule](https://developers.google.com/weathernext/guides/dissemination):

| Model | Runs | Delay to Cloud Storage | Delay to BigQuery / Earth Engine |
|---|---|---|---|
| WeatherNext 3 | Main runs 00/06/12/18 UTC | 7 h 45 min after start time | 8 h 10 min |
| WeatherNext 3 | In-between hourly runs | 7 h 10 min | 7 h 25 min |
| WeatherNext 2 | 00/06/12/18 UTC | 6 h 50 min | 7 h 30 min |

- WeatherNext 3 also powers Google Search, Gemini, Google Maps, the Google Maps Platform Weather API and Earth Engine. Source: [WeatherNext 3 search summary](https://tribune.net.ph/2026/09/15/google-launches-weathernext-3-for-sharper-weather-forecasts)

**Third-party API and backtest archives**
- Open-Meteo served GraphCast at 0.25°, 4 runs/day, from 5 Feb 2024, but did not store GraphCast "previous runs" until later. Sources: [Open-Meteo GraphCast post](https://openmeteo.substack.com/p/exploring-graphcast); [Open-Meteo previous-runs comments](https://openmeteo.substack.com/p/weather-forecasts-from-previous-model-runs/comments)
- Open-Meteo's "Single Runs" archive (forecasts as issued, by start time) covers ECMWF IFS HRES from 14 Mar 2024 and most other models from Sept 2025; AIFS and GraphCast were not named. Source: [Open-Meteo Single Runs API](https://openmeteo.substack.com/p/single-runs-api)

**Version churn (matters for backtests)**
- AIFS Single: v1.0 Feb 2025 → v1.1 Aug 2025 (rain fix) → v2 May 2026 → v3 planned Q4 2026. Sources: [arXiv 2509.18994](https://arxiv.org/html/2509.18994v1); [ECMWF Confluence](https://confluence.ecmwf.int/display/FCST/Implementation+of+AIFS+Single+v2)
- NBM itself changed to v5.0 on 5 May 2026. Source: [NOAA MDL](https://vlab.noaa.gov/web/mdl/-/national-blend-of-models-nbm-upgraded-to-version-5.0-1)

### Inferences
- **Timing vs Kalshi.** Kalshi's daily-high market opens 10:00 am Eastern the day before ([Crosier](https://arxiv.org/pdf/2609.23969)). WeatherNext 3's 00z run lands about 07:45 UTC (3:45 am EDT); its 12z run lands about 19:45 UTC (3:45 pm EDT) the day before. For a same-day trade, the newest WeatherNext data is 7-8 hours old. NBM updates hourly and LAMP uses live observations, so a slow AI feed is behind on the target day.
- **Licence.** AIFS is cleanly usable for trading. WeatherNext real-time data's "experimental" terms need a lawyer-level read before any trading use; the historical (CC BY 4.0) data is fine for research and backtests. NOAA data is normally US-government public domain (general knowledge, not verified in this pass).
- **Honest backtest window.** For AIFS ENS you get about 15 months (July 2025 →), split across v1 and v2. For AIGFS, about 10 months. For WeatherNext 3, about 2 months. That is far too short to measure a 2-3% gain at one station.

### Gaps
- No published minutes-after-run figure for AIFS open data, or for AIGFS on NOMADS.
- The GDM experimental terms of use were not read, so whether trading on real-time WeatherNext is allowed is unknown.
- No confirmed AWS mirror for AIGFS.

---

## 4. Running the models yourself

### Takeaway
You can run AIFS ENS v2 (free weights, CC BY 4.0) on one large GPU, starting from ECMWF's free open data. But your run starts from the same data ECMWF uses, so it mostly reproduces the free public forecast. Running your own model only helps if you change something: newer inputs, more members, or station-trained correction.

### Cited findings
- AIFS ENS v2 weights: CC BY 4.0; demo code Apache 2.0; run with `anemoi-inference`; needs the atmospheric state at t−6 h and t0, which the demo pulls from ECMWF Open Data; ~31 km grid, 14 levels, 51 members, 15 days. Source: [Hugging Face, ecmwf/aifs-ens-2.0](https://huggingface.co/ecmwf/aifs-ens-2.0)
- AIFS ENS v1.0 needs 38 GB of GPU memory by default, or about 24 GB with a higher "chunk" setting (slower). Source: [Hugging Face, ecmwf/aifs-ens-1.0](https://huggingface.co/ecmwf/aifs-ens-1.0)
- An EGU 2026 abstract describes experimental half-precision (FP16) AIFS runs that could fit cheaper NVIDIA T4/L4 GPUs instead of A100s. Source: [EGU26-20505](https://meetingorganizer.copernicus.org/EGU26/EGU26-20505.html)
- A serverless recipe runs AIFS on Modal GPU containers. Source: [aifs-modal docs](https://aifs-modal.readthedocs.io/en/latest/how-it-works.html)
- One AI Weather Quest team ran a 50-member ensemble on one NVIDIA A100 on Google Cloud, with data prep moved to CPUs to save money. Source: [AI Weather Quest team page](https://aiweatherquest.ecmwf.int/team/fahamu/)
- DeepMind's repo now covers WeatherNext 2: TPUs recommended; on GPUs the full models need an H100 for memory; "Mini" models run on a P100 or a free Colab TPU; code Apache 2.0, "all other materials" CC BY 4.0. Source: [GitHub google-deepmind/graphcast](https://github.com/google-deepmind/graphcast). Older sources say GraphCast weights are CC BY-NC-SA 4.0 (no commercial use). Source: [Hugging Face mirror](https://huggingface.co:443/shermansiu/dm_graphcast). These two do not fully agree; check the weight files' own licence before commercial use.
- Pangu-Weather weights: CC BY-NC-SA 4.0, commercial use forbidden. Source: [OpenI Pangu repo](https://openi.pcl.ac.cn/AI4NWP/Pangu-Weather)
- NVIDIA FourCastNet: NVIDIA AI Foundation Models Community License; the NIM container falls under the NVIDIA AI Product Agreement. Source: [NGC catalog](https://catalog.ngc.nvidia.com/orgs/nim/nvidia/containers/fourcastnet/-)
- There is a ready plugin to run GraphCast from NOAA GFS starting data. Source: [PyPI ai-models-graphcast-gfs](https://pypi.org/project/ai-models-graphcast-gfs)
- NOAA's AIGFS runs a 16-day forecast in 40 minutes on NOAA hardware. Source: [ForecastWatch](https://forecastwatch.com/2026/01/06/noaa-launches-new-suite-of-weather-models/)

### Inferences
- Self-running only pays if it is **faster** than the public feed or uses **better inputs**. Both are hard: the start data (ECMWF or GFS analysis) itself arrives hours after the run time, and AIFS open data already appears "as soon as the forecast is produced."
- Licences rule out GraphCast-original and Pangu weights for a money-making use, unless the newer DeepMind CC BY 4.0 wording applies to the weights you use.

### Gaps
- No published minutes-per-forecast or dollars-per-run for AIFS or WeatherNext on a rented cloud GPU. No reliable figure was found.

---

## 5. Evidence that AI models add information beyond NBM / the public blend

### Takeaway
The biggest finding: **NBM v5.0 (5 May 2026) already uses two AI models, AIGFS and "ECAIGS" (very likely ECMWF's AIFS), as inputs.** So the free blend already contains AI information. Kalshi traders beat NBM by about 10% and a six-forecast public blend by about 3%; none of those six were AI models, but NBM now carries AI inside it. Outside the US, adding AIFS to a physics blend clearly helps at stations (Australia). Nobody has shown AI models add skill on top of NBM, or on top of a Kalshi price.

### Cited findings

**NBM now includes AI**
- NBM v5.0, upgraded 5 May 2026: "Addition of the ECAIGS and AIGFS artificial intelligence forecasting systems as inputs." The page does not mention AIGEFS, AIFS by that name, or GraphCast. Source: [NOAA MDL NBM v5.0](https://vlab.noaa.gov/web/mdl/-/national-blend-of-models-nbm-upgraded-to-version-5.0-1)

**The Kalshi market study (Crosier, 20-21 Sept 2026)**
- Data: 7 cities, 7,590 city-days, markets through 12 Aug 2026. Stations: Central Park, Chicago Midway, Miami Intl, Austin-Bergstrom, Philadelphia Intl, Denver Intl, LAX. Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- The six public forecasts: NDFD (the official weather.gov forecast), NBM, LAMP (hourly station guidance that uses live observations), GFS MOS, HRRR (3 km US model) and ECMWF. **No AI model was among them.** HRRR, ECMWF and LAMP were given a rolling bias correction. Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- Typical miss (RMSE, °F), from Table 2. Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969):

| Forecast | Day before, 11 am ET | Day before, 7 pm | Target day, 8:40 am ET |
|---|---|---|---|
| Kalshi market | 2.44 | 2.21 | 1.88 |
| NBM (best single public forecast) | 2.70 (market 9.8% better) | 2.45 (10.0% better) | 2.12 (11.4% better) |
| Best mix of all six, fitted on past days only | 2.45 (market 3.1% better) | 2.25 (4.3% better) | 1.90 (3.0% better; weak evidence, 10% level only) |
| Raw ECMWF, bias-corrected | 3.31 | 3.16 | 2.68 |

- On the days the blend exists, the market's RMSE is 2.38 / 2.16 / 1.84 °F. A simple equal-weight average of the six did as well as the fitted mix (2.43 vs 2.45 °F at the opening hour). Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- LAMP, which uses live observations, drives most of the public blend's improvement through the day; dropping it widens the market's lead to 3.3 / 4.7 / 6.4%. Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- The market's edge is biggest where forecasts are hardest: 10-16% better than NBM Nov-June when NBM misses by 3 °F or more; only 1-4% better July-Oct; Miami is the exception, where the market is not better. Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- Who leads whom: when NBM updates, it moves toward the market about four times as far as the market moves toward NBM; prices do not jump when NBM posts. Source: [arXiv 2609.23969](https://arxiv.org/pdf/2609.23969)
- **Settlement change:** after 12 Aug 2026 "Kalshi changed its settlement source from the National Weather Service to The Weather Company" (the study keeps only NWS-settled contracts). Source: [arXiv 2609.23969, footnote 2](https://arxiv.org/pdf/2609.23969)

**The ForecastEx comparison (Patrick Brown, Interactive Brokers, 2026)**
- Brown compared ForecastEx daily-high markets with twenty forecast products at 24 locations over seven months of 2026 (as described by Crosier). Source: [arXiv 2609.23969, related work](https://arxiv.org/pdf/2609.23969)
- His Sept 2026 article says the set includes "an AI forecasting system from" ECMWF, and ForecastEx has 21-25% lower errors than the next-best of the twenty at meaningful lead times (from search snippets; the page blocked direct reading). Source: [Interactive Brokers](https://www.interactivebrokers.com/campus/traders-insight/ibkr-climate-energy/prediction-markets-might-already-be-the-best-source-for-todays-weather-forecast/)
- His daily posts, Aug 2026: ForecastEx 7-day average miss 1.25-1.31 °F; next best was the "Aviation Forecast" (1.48-1.55 °F) or NBM (1.62 °F on 17 Aug). Sources: [IB, 3 Aug 2026](https://www.interactivebrokers.com/campus/traders-insight/prediction-market/fair-value-weather-climate-monday-august-3-2026/); [IB, 17 Aug 2026](https://www.interactivebrokers.com/campus/traders-insight/prediction-market/fair-value-weather-climate-monday-august-17-2026/)
- Caveat: these are the author's own analyses, published by the broker that runs ForecastEx; not peer reviewed.

**Blending studies with AI models (not US, not vs NBM)**
- Australia, 569 stations (Trotta et al., Bureau of Meteorology, 2025 preprint): "the blend including all three models [AIFS + ENS + HRES] is significantly better than the blend of only the two NWP models," for both squared error and CRPS (tested with Diebold-Mariano, a test of whether one forecast's errors are reliably smaller). AIFS got the largest blend weight early in the forecast for temperature. No percentage gain is stated; rain was not tested. Source: [arXiv 2504.12672](https://arxiv.org/html/2504.12672v1)
- Beijing, 2026: GraphCast and Pangu started from IFS or GFS data beat their own driving physics models for short-term temperature; a machine-learning blend of AI and physics models was built (peer reviewed, Meteorological Applications). Source: [Wiley, Met. Apps 2026](https://rmets.onlinelibrary.wiley.com/doi/10.1002/met.70238?af=R)
- NOAA's own hybrid ensemble (HGEFS = AI + physics) "consistently outperforms" either alone (agency claim). Source: [ForecastWatch](https://forecastwatch.com/2026/01/06/noaa-launches-new-suite-of-weather-models/)

### Inferences
- **AI information is already in the price.** NBM has carried AIGFS and an ECMWF AI model since May 2026. Traders read NBM. Google's WeatherNext 3 feeds Google Search, Maps and the Maps Weather API, which many people check. So "free AI forecast as a new signal" is mostly gone for the big public models.
- **Crosier's sample predates most of this.** Only about 3 months (5 May-12 Aug 2026) overlap NBM v5.0. NBM's error may now be lower than his 2.70 °F, which would shrink the market's lead over NBM, but not the market's lead over the blend.
- **What is left is small.** Even the full public blend is only 2-4% behind the market (about 0.05-0.1 °F of RMSE). An AI model would need to add more than that *on top of* NBM-with-AI to be worth trading. No study shows that.
- **Where a gap might still exist:** (a) WeatherNext 3's station-trained, hourly-started ensemble (new in Sept 2026, not in any published comparison yet); (b) AI ensemble *shape* (tails and bracket probabilities), not the single best guess, since the Wessel et al. results favour AI ensembles on extremes; (c) hard regimes (winter cold fronts in NYC, Chicago, Philadelphia), where the market's edge over NBM is biggest.
- **Settlement-source risk.** If Kalshi now settles on The Weather Company instead of the NWS climate report, a model trained or corrected against NWS observations may be aiming at a slightly different number.

### Gaps
- No study adds AIFS, AIGFS or WeatherNext to NBM or to a Kalshi price and measures the gain.
- "ECAIGS" is not defined on the NBM page; it is assumed here to be ECMWF's AIFS Single, but this was not confirmed. NBM v5.0's input weights were not found either.
- Brown's full twenty-system table could not be read, so how the ECMWF AI system ranked is unknown.
- No station-level US test of rain probability from AI models vs NBM PoP.

---

## 6. Has anyone used AI weather models for trading or prediction markets, with results?

### Takeaway
Energy-trading vendors sell AI weather models, but every accuracy claim found is their own marketing. Retail Kalshi/Polymarket weather bots mostly use the free GFS ensemble, not AI models, and report only anecdotal profits. No audited or peer-reviewed trading result from AI weather models was found.

### Cited findings
- Pelmorex "Gaia Energy" (Oct 2024): a deep-learning model for gas, power, agriculture and weather-derivative traders; claims 18x faster, more accurate than top conventional models, and insights an hour ahead of the market (vendor claim). Source: [Pelmorex press release](https://www.pelmorex.com/en/media-hub/pelmorex-corp-unveils-ai-powered-advanced-weather-modeling-built-for-energy-traders/)
- Jua pivoted from general AI weather data to energy-trading products (2024 analysis). Source: [Asymmetrix substack](https://asymmetrixintelligence.substack.com/p/company-analysis-jua)
- Spire's AI sub-seasonal product reportedly beat ECMWF's extended ensemble by 14.2% on surface temperature at 3-6 weeks (vendor-reported; wrong time scale for Kalshi). Source: [Barchart / Spire](https://www.barchart.com/story/news/2059123/spire-global-expands-energy-trading-intelligence-with-intraday-to-45-day-weather-forecasts-and-trader-grade-decision-platform)
- Climavision sells "Horizon AI" forecasts for specific sites and says they beat HRRR in major events (vendor claim). Source: [Climavision blog](https://climavision.com/blog/high-resolution-weather-data-for-energy-trading-decisions/)
- Open-source Kalshi/Polymarket weather bot: uses the 31-member GFS ensemble from Open-Meteo, trades when its estimated edge is over 8%; a listing says the author reported peak profits of $1,800 before the bot "stopped working as conditions changed". Sources: [GitHub suislanchez](https://github.com/suislanchez/polymarket-kalshi-weather-bot); [botforkalshi listing](https://www.botforkalshi.com/bot-catalog/suislanchez-weather)
- A paid bot claims "164 ensemble members across 4 forecast systems"; no verified results. Source: [search summary of bot catalog](https://www.botforkalshi.com/bot-catalog)
- A practitioner's write-up reports Brier scores (yes/no probability error) of 0.07-0.14 for its own Kalshi high/low model (0.25 = no better than climate averages), and notes beating climate averages does not mean beating market prices, since "the market already incorporates NWP". Source: a practitioner's write-up (not linked)
- The two market studies found that the market *leads* the public forecasts, not the reverse. Sources: [Crosier, arXiv 2609.23969](https://arxiv.org/pdf/2609.23969); [Interactive Brokers](https://www.interactivebrokers.com/campus/traders-insight/ibkr-climate-energy/prediction-markets-might-already-be-the-best-source-for-todays-weather-forecast/)

### Inferences
- If AI weather models gave easy profit on Kalshi, the market would not be beating NBM-with-AI and a broad blend. The market-leads-forecast result suggests some traders already use something better than public guidance. That could be AI models, private station data, or live observations.
- The vendor energy-trading pitch is about **speed** (getting a run an hour early) and **sub-seasonal** horizons. Neither maps well onto a one-station, same-day Kalshi high.

### Gaps
- No public record of a hedge fund or prop shop reporting results from GraphCast, AIFS or WeatherNext.
- No independent audit of any retail weather-bot profits.
- Brightband's live station leaderboard (owb.brightband.com) might show how WeatherNext 3 compares with NBM. It could not be read for this note.
