# Free and cheap US weather data for a Kalshi daily-weather probability model

Scope: daily high temperature, daily low temperature, and "will it rain today" in US cities.
Researched 25 Oct 2026. "Tested" means a single test request was made on that date to confirm the endpoint works.
Plain-words key for terms used below:
- **PoP** (probability of precipitation): the chance of at least 0.01 inch of rain or melted snow in a time window.
- **QPF** (quantitative precipitation forecast): the forecast rain amount.
- **Percentile**: the 10th percentile high is the value the high should beat 90% of the time.
- **Ensemble**: the same model run many times with small changes; the spread of the runs shows the uncertainty.
- **Deterministic**: a single best-guess number, with no uncertainty attached.
- **Calibrated**: adjusted so a 70% forecast really happens about 70% of the time.
- **GRIB2**: the standard binary file format for weather model grids. Needs a library (eccodes, cfgrib, Herbie) to read.
- **Archive / backtest**: stored past forecasts, so we can score what was forecast against what happened.
- **CLI** (NWS Daily Climate Report): the official daily high, low and rain total for a station. Kalshi daily temperature markets settle on it.

---

## 1. NWS API (api.weather.gov)

### Takeaway
Free, no API key, but a User-Agent header is required and the rate limit is secret. The raw gridpoint endpoint does include max temperature, min temperature, PoP and QPF (tested). It only serves the current forecast: there is no archive of past forecasts, and observations are kept for 7 days only. For past official NWS forecasts, use the IEM text archive (Point Forecast Matrices, back to 2005) or the NDFD archive (AWS from 2020, NCEI from 2004).

### Cited findings
- Base URL is `https://api.weather.gov`. Main paths: `/points/{lat},{lon}` (returns the office and grid cell), `/gridpoints/{office}/{x},{y}/forecast` (12-hour periods), `/forecast/hourly`, the raw grid via the `forecastGridData` link, and `/stations/{id}/observations` plus `/observations/latest`. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Auth: "A User Agent is required to identify your application." Example header `User-Agent: (myweatherapp.com, contact@myweatherapp.com)`. The docs say this "will be replaced with an API key in the future" (no date given). Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Rate limit: "The rate limit is not public information." Over-limit requests get an error and can be retried, "typically within 5 seconds." Proxies are more likely to hit the limit. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Formats: GeoJSON (default), JSON-LD, and DWML XML for `/forecast` and `/forecast/hourly`, chosen with the `Accept` header. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Caching: apps may cache a location's grid cell, but the office and grid x/y can change, so re-check `/points` from time to time. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Tested: `/points/40.7789,-73.9692` (Central Park, NYC) returned office OKX, grid 34,45, with forecast, hourly and raw-grid URLs. Source: [test request](https://api.weather.gov/points/40.7789,-73.9692)
- Tested: the raw grid `https://api.weather.gov/gridpoints/OKX/34,45` returned 59 data layers. These include `temperature`, `maxTemperature`, `minTemperature`, `probabilityOfPrecipitation`, `quantitativePrecipitation`, `probabilityOfThunder`, `skyCover` and `dewpoint`. Values are in degrees C and mm, each tied to an ISO-8601 time interval. Example: maxTemperature valid `2026-10-26T12:00+00:00/PT13H` (a 13-hour daytime window) = 20.6 C. PoP came as 6-hour intervals (`PT6H`), with long runs of equal values merged (e.g. `P6DT6H` = 0%). The grid's updateTime was 18:19 UTC. Source: [test request](https://api.weather.gov/gridpoints/OKX/34,45)
- Observations are retained for 7 days. Upstream observations may be delayed up to 20 minutes by MADIS quality control. Station 24-hour max/min fields are always null for stations outside the Central time zone, due to an upstream MADIS bug. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Recent dated changes from the docs' change log: 7 Jan 2026, forecasts no longer include past periods. 15 Dec 2025, an entry about observation precipitation being rounded down to the nearest centimeter. 2 Oct 2025, wind gust values no longer always null. 22 May 2025, PoP values under 20% in the 12-hour forecast no longer show as null. Page last updated 24 Mar 2026. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- **Archive of official NWS forecasts (text):** IEM stores NWS Point Forecast Matrices (PFM, the NWS office's own table of max/min, 12-hour PoP and QPF per town). Tested: 3 PFMOKX products on 25 Oct 2025, and a PFM for "CENTRAL PARK-NEW YORK NY" issued 1 Jan 2005. Sources: [IEM AFOS list API](https://mesonet.agron.iastate.edu/api/1/nws/afos/list.json?pil=PFMOKX&date=2025-10-25); [IEM retrieve 2005](https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=PFMOKX&sdate=2005-01-01&edate=2005-01-02&limit=1&fmt=text)
- **Archive of official NWS forecasts (grids):** The NWS gridded forecast (NDFD, the grid behind the API) is on AWS in bucket `noaa-ndfd-pds`, with folders per element including `wmo/maxt/`, `wmo/mint/`, `wmo/pop12/`, `wmo/qpf/`, `wmo/sky/` (tested listing). Source: [bucket listing](https://noaa-ndfd-pds.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=wmo/). An NCEI summary says the AWS copy runs from 16 Apr 2020, and NCEI holds NDFD from 6 Jun 2004 (older data via the AIRS request system, one day per request). Sources: [NCEI NDFD page](https://www.ncei.noaa.gov/node/765); [NCEI THREDDS NDFD](https://www.ncei.noaa.gov/thredds/catalog/model/ndfd.html)

### Inferences
- The NWS forecast is deterministic for temperature (one high, one low) but gives PoP for rain. It is the "official" human-edited forecast, so it is a strong baseline to beat, not a probability source for temperature.
- The NWS maxTemperature window in the test was 12:00 UTC + 13 hours (about 7 AM to 8 PM Eastern Standard Time). The CLI high covers midnight to midnight local standard time. The two can differ on days with a front passing at night. A model must handle this mismatch.
- The IEM PFM archive is the cheapest way to backtest the official NWS forecast at the exact settlement station. It is text, so it needs a parser.

### Gaps
- The actual NWS API rate limit is not published. No date for the planned API key.
- The 15 Dec 2025 "rounded down to the nearest centimeter" entry was read through a page summary. Check the raw docs before trusting API observation rain totals for 0.01-inch questions. The CLI is the safer rain source anyway.
- The exact NDFD start date on AWS (16 Apr 2020) came from an NCEI summary page; the folder dates were not listed in this pass.

---

## 2. NOAA National Blend of Models (NBM)

### Takeaway
NBM is the best free source of true, calibrated probabilities for this job. Its GRIB2 "qmd" files hold full percentile curves and exceedance probabilities for the daily max and min temperature, plus probabilities of at least 0.01 inch of rain for 1, 6, 12 and 24-hour windows. The NBP text bulletin gives the 10th, 25th, 50th, 75th and 90th percentile of the high and low at 9,000+ stations. AWS keeps the GRIB2 and all five text bulletins back to 18 May 2020. Big caution: NBM version 5.0 went live on 5 May 2026 and changed things, so a backtest spans several model versions.

### Cited findings
- AWS buckets: `noaa-nbm-grib2-pds` (GRIB2) and `noaa-nbm-pds` (Cloud-Optimized GeoTIFF), both us-east-1, updated "once per hour". SNS topics announce new files. NOAA open data "can be used as desired" with attribution requested. Source: [AWS Registry: NBM](https://registry.opendata.aws/noaa-nbm/)
- Tested: the earliest GRIB2 folder is `blend.20200518/`. In 2020 a run folder held `grib2/` and `text/`. From at least June 2021 it holds `core/` (deterministic fields), `qmd/` (percentiles and probabilities) and `text/`. Sources: [bucket listing](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=blend.); [2021 layout](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=blend.20210601/12/)
- Tested: each run's `text/` folder has `blend_nbhtx`, `blend_nbstx`, `blend_nbetx`, `blend_nbxtx` and `blend_nbptx` files (about 27-30 MB each, all stations in one file). The same five files exist for 2020-06-01 and 2023-06-01 runs. Source: [2026 text listing](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&prefix=blend.20261025/12/text/)
- Tested: the qmd file `blend.t12z.qmd.f042.co.grib2` has "TMP:2 m above ground:24-42 hour max fcst" (the daytime high window) as probability-below/above thresholds (e.g. <255.372 K up to >322.039 K) plus percentile levels 0%, 5%, 10% ... 100%. Precipitation has "prob >0.254" mm (= 0.01 inch, the PoP threshold) and higher thresholds, plus 0-100% percentile levels, for windows like 24-30 h. Sources: [qmd idx file](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20261025/12/qmd/blend.t12z.qmd.f042.co.grib2.idx); [qmd f030 idx](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20261025/12/qmd/blend.t12z.qmd.f030.co.grib2.idx)
- Tested: in June 2021 the same max-temperature percentiles came in 1% steps (1%, 2%, ... level) instead of today's 5% steps. Source: [2021 qmd idx](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20210601/12/qmd/blend.t12z.qmd.f042.co.grib2.idx)
- Tested: the `core` file has "TMAX ... 24-36 hour max fcst" plus its "ens std dev" (standard deviation, i.e. the typical forecast error size), and PoP ("APCP ... prob >0.254") for 1, 6 and 12-hour windows. Source: [core idx](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20261025/12/core/blend.t12z.core.f036.co.grib2.idx)
- Text bulletins: NBH hourly, hours 1-25. NBS 3-hourly, hours 6-72. NBE 12-hourly, hours 24-192. NBX 12-hourly, hours 204-264. NBP (probabilistic) 12-hourly, hours 24-264. Over 9,000 land and marine stations, taken from the nearest usable grid point. Cycles 01, 07, 13, 19 UTC go out at set windows (e.g. 12:55-13:00 UTC); other hourly cycles go at HH:30-HH:40. Source: [MDL NBM Text Products](https://vlab.noaa.gov/web/mdl/nbm-text-products)
- NBP elements: TXNP1/2/5/7/9 = the 10th, 25th, 50th, 75th and 90th percentiles of min/max temperature. TXNMN = mean. TXNSD = standard deviation. Source: [MDL NBM Text Products](https://vlab.noaa.gov/web/mdl/nbm-text-products)
- Tested: the NBP block for KNYC (Central Park), 12 UTC 25 Oct 2026 run, for the Monday 26 Oct high: mean 68 F, standard deviation 1, 10th percentile 67, 90th percentile 70. It also has 24-hour rain amount percentiles (Q24P1-9). Source: [NBP file](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20261025/12/text/blend_nbptx.t12z)
- Tested: IEM's parsed NBS for KNYC has columns `txn` (max/min temp), `xnd` (its standard deviation), `tsd` (hourly temp standard deviation), `p06`/`p12`/`p24` (PoP), `q06`/`q12`/`q24` (QPF), among others. Source: [IEM mos.json NBS KNYC](https://mesonet.agron.iastate.edu/api/1/mos.json?station=KNYC&model=NBS)
- IEM archives NBS from 7 Nov 2018 and NBE from 23 Jul 2020. The archived cycles moved from 01/07/13/19 UTC to 00/06/12/18 UTC on 5 May 2026 (the v5.0 date). Source: [IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)
- Version history: v3.2 on 19 Feb 2020 (probabilistic max/min percentiles for the lower 48 states, plus a probabilistic text product). v4.0 on 29 Sep 2020 (percentiles and exceedance values, temperature standard deviations, 2,000+ new text stations). v4.1 on 17 Jan 2023. v4.2 on 15 May 2024. v4.3 (notice 15 Apr 2025, minor). v5.0 operational 5 May 2026, with a 28 Jul 2026 update to improve temperatures in seasonal transitions. Source: [MDL NBM Versions](https://vlab.noaa.gov/web/mdl/nbm-versions)
- v5.0 (5 May 2026): NDFD elements become "fully probabilistic" for all domains except Oceanic. Deterministic and probabilistic values are aligned for most elements. Hourly products extended from 36 to 48 hours. AI models ECAIGS and AIGFS added as inputs. v5.1 planned for fall 2026, including "mitigation of seasonal transition biases". Source: [MDL v5.0 announcement](https://vlab.noaa.gov/web/mdl/-/national-blend-of-models-nbm-upgraded-to-version-5.0-1)
- v5.0 date slipped several times (30 Apr, 21 Apr, 23 Apr, then 5 May 2026). A bug fix (SCN 26-58) took effect 18 Jun 2026, covering text bulletin formatting and QPF timing/metadata, among others. Sources: [SCN 26-24 v5.0](https://www.weather.gov/media/notification/pdf_2026/scn26-24_Updated_NBM_V5.0_aac.pdf); [SCN 26-58 bug fix](https://www.weather.gov/media/notification/pdf_2026/scn26-58_Blendv5.0_bug_fix.pdf)
- Open-Meteo also serves NBM point data in its Historical Forecast API from 8 Oct 2024. Source: [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api)

### Inferences
- For the high/low markets, the NBP percentiles (or the qmd GRIB2 percentiles) can be turned straight into a probability for each Kalshi bracket. The NBS `xnd` standard deviation allows a simple bell-curve version back to 2018 via IEM.
- Backtests should be split by NBM version: v4.0 (Sep 2020), v4.1 (Jan 2023), v4.2 (May 2024), v5.0 (May 2026), plus the July 2026 temperature update. The v5.0 period is under 6 months old, so its own track record is short.
- The percentile step change (1% in 2021, 5% now) means a GRIB2 parser must read the levels from each file, not assume them.
- NBM's daytime max window in the qmd file was 24-42 hours from a 12 UTC run (12 UTC to 06 UTC). That is not the CLI's midnight-to-midnight local standard time day. Hourly temperature percentiles cannot simply be combined into a percentile of the daily max, so the window mismatch needs either an adjustment or a bias model fitted against CLI results.
- Pulling one station from the text archive means downloading a ~30 MB file per run. A year of one cycle a day is about 11 GB per bulletin type. IEM's NBS/NBE JSON avoids that for those two bulletins (NBP is not in IEM's list).

### Gaps
- IEM does not list NBP or NBH in its archive, so the 2018-2020 NBP history is not available there. Whether NBP percentiles existed in the 2020 AWS text files was not checked line by line.
- The exact meaning of the v5.0 text-bulletin change table (which elements were added versus removed) could not be read, because the page marks it by colour only.
- No official statement on how far back NOAA intends to keep the AWS NBM archive.

---

## 3. MOS and LAMP (statistical guidance) and the IEM MOS archive

### Takeaway
GFS MOS (MAV short range, MEX extended) is a statistical correction of the GFS model at each station. It gives a single max/min temperature (deterministic) but true probabilities for rain (6- and 12-hour PoP). IEM has a free archive of GFS MOS back to 16 Dec 2003, with a simple CSV/JSON API. NAM MOS is being retired along with the NAM model when RRFS goes live (latest notice: 3 Nov 2026).

### Cited findings
- MAV P12 = probability of at least 0.01 inch of liquid-equivalent precipitation in a 12-hour period. Windows run 6-18, 18-30, 30-42, 42-54 and 54-66 hours after 00 and 12 UTC. Missing values show as 999. (Source is a 2004 MDL bulletin). Sources: [MDL TPB 05-01](https://vlab.noaa.gov/documents/6609493/36173388/mdltpb05-01.pdf); [MAV card](https://vlab.noaa.gov/web/mdl/mav-card)
- MAV N/X = nighttime minimum / daytime maximum temperature; MEX uses the same X/N definition. Sources: [MAV card](https://www.nws.noaa.gov/mdl/synop/mavcard.php); [MEX card](https://vlab.noaa.gov/web/mdl/mex-card)
- IEM MOS archive ranges: AVN 1 Jun 2000 - 16 Dec 2003; ETA 24 Feb 2002 - 9 Dec 2008; GFS 16 Dec 2003 - now; NAM 9 Dec 2008 - now; GFS LAMP (LAV) 12 Jul 2020 - now; GFS extended (MEX) 12 Jul 2020 - now; NBS and NBE as in section 2. Source: [IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)
- IEM access: `/api/1/mos.txt` (CSV) and `/api/1/mos.json` with `station`, `model` and optional `runtime`. Examples: `https://mesonet.agron.iastate.edu/api/1/mos.txt?station=KAMW&runtime=2009-01-10%2012:00Z&model=GFS` and `https://mesonet.agron.iastate.edu/api/1/mos.json?station=KAMW&model=GFS`. Raw text via `/cgi-bin/afos/retrieve.py?pil=LAVDSM` (LAMP for Des Moines). Source: [IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)
- NAM retirement: SCN 26-47 (updated 9 Sep 2026) set 14 Oct 2026 for retiring NAM, SREF, HREF, HiresW and all NAM MOS products. Some LAMP products that used NAM MOS switch to GFS MOS as a temporary fix. Source: [SCN 26-47 updated](https://www.weather.gov/media/notification/pdf_2026/SCN26-47_Updated_Retire_NAM_SREF_HREF_HiresW_NAM_MOS.aab.pdf)
- RRFS/REFS go-live (which replaces NAM, HREF, SREF, HiresW, with retirements on the same day) was moved to 3 Nov 2026 by a notice dated 15 Oct 2026. Earlier dates were 31 Aug, 6 Oct and 14 Oct. A parallel feed has been on NOMADS since 12 Aug 2026. RRFS v1 is not meant to replace HRRR. Sources: [SCN 26-48 updated](https://www.weather.gov/media/notification/pdf_2026/scn26-048_Updated_RRFS_and_REFS_Implementation.aaf.pdf); [GSL RRFS v1](https://gsl.noaa.gov/rrfs/rrfsv1/)
- SCN 26-89: downstream model changes from RRFS and the NAM retirement start with the 12 UTC run on 3 Nov 2026. SCN 26-88: station ID change KPBI to KDJT for GFS MOS and LAMP, around 5 Oct 2026. Sources: [SCN 26-89](https://www.weather.gov/media/notification/pdf_2026/scn26-89_RRFS_Downstream.pdf); [SCN 26-88](https://www.weather.gov/media/notification/pdf_2026/scn26-88_LAMP_GFSMOS_KDJT.pdf)
- IEM's NBM page lists only NBS/NBE, not NAM MOS replacements; NAM rows run to "Realtime" as of this check. Source: [IEM MOS archive](https://mesonet.agron.iastate.edu/mos/)

### Inferences
- GFS MOS is the longest free station-level forecast archive (22+ years). It is ideal for building a "forecast error" model: compare the MOS high to the CLI high to learn how big misses are by city and season. That error model turns a single number into a probability.
- PoP12 from MOS is directly usable for "any rain" questions, but its 12-hour windows (e.g. 12-00 UTC) do not line up with the CLI calendar day; two windows need combining.
- NAM MOS history (2008-2026) stays useful for backtests, but there will be no live NAM MOS after the retirement, so it should not be a live model input.
- Because the NAM retirement date moved with RRFS, the NAM MOS feed may still run until 3 Nov 2026.

### Gaps
- The exact clock hours of MOS "daytime max" and "nighttime min" (commonly stated as 7 AM-7 PM and 7 PM-8 AM local standard time) were not confirmed from a primary page in this pass; the MDL MAV page that was tried returned 404.
- LAMP's element list (hourly temperature, 1/6/12-hour PoP) was not confirmed from MDL docs in this pass.
- Whether the NAM retirement actually happened on 14 Oct or moved to 3 Nov was not confirmed by a final notice.

---

## 4. Raw model data: HRRR, GFS, GEFS, ECMWF IFS/AIFS, cloud buckets, Herbie

### Takeaway
All the main US and ECMWF model grids are free on public cloud buckets, with long archives on AWS: HRRR from 30 Jul 2014, GEFS from 1 Jan 2017 (plus a 2000-2020 reforecast), NBM from 18 May 2020, and ECMWF open data from 18 Jan 2023. ECMWF made its whole real-time catalogue open (CC-BY-4.0) on 1 Oct 2025, but only a popular subset is free to download, and its own portal keeps only the last 12 runs. The AWS mirror keeps older runs. Herbie (latest 2026.9.2, 27 Sep 2026) downloads all of these with one Python call.

### Cited findings
- Tested bucket starts (earliest folder): `noaa-hrrr-bdp-pds` = `hrrr.20140730/`; `noaa-gefs-pds` = `gefs.20170101/`; `noaa-nbm-grib2-pds` = `blend.20200518/`; `ecmwf-forecasts` = `20230118/`. Sources: [HRRR](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5); [GEFS](https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5); [NBM](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5); [ECMWF on AWS](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5)
- Tested: the GEFS v12 reforecast (past re-runs of today's ensemble, made for calibration) is in `noaa-gefs-retrospective/GEFSv12/reforecast/` with year folders 2000 to 2020. Source: [bucket listing](https://noaa-gefs-retrospective.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=GEFSv12/reforecast/)
- Tested: ECMWF on AWS still holds 2024 runs (e.g. `20240101/00z/0p4-beta/enfo/` ensemble files). A 2026 run has `aifs-ens/`, `aifs-single/`, `ifs/0p1/` and `ifs/0p25/`. Sources: [2024 listing](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=20240101/00z/); [2026 listing](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=20261025/00z/)
- AWS registry: bucket `ecmwf-forecasts` (eu-central-1), no account needed (`aws s3 ls --no-sign-request s3://ecmwf-forecasts/`), CC-BY-4.0. It gives no promised retention period. Source: [AWS Registry: ECMWF](https://registry.opendata.aws/ecmwf-forecasts/)
- ECMWF open data: free subset of IFS and AIFS, including ensemble products (means, standard deviations, probabilities). 0.25 degree; from 20 Oct 2026, IFS also at 0.1 degree, published about 2 hours after the 0.25 degree data. AIFS released as soon as produced; IFS 0.25 at the end of the dissemination schedule. Portal keeps "the most recent 12 forecast runs" (about 2-3 days), with a cap of 500-2000 simultaneous connections. Hosted on data.ecmwf.int and copied to AWS, Azure and Google Cloud. The `ecmwf-opendata` Python client can pull from any of them. Source: [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data)
- 1 Oct 2025: ECMWF made its entire Real-time Catalogue open under CC-BY-4.0 with no information cost; delivery of the full high-volume catalogue may carry service charges, so only a popular subset is free on the portal. Sources: [ECMWF announcement](https://www.ecmwf.int/node/29497); [Science Business](https://sciencebusiness.net/network-updates/ecmwf-makes-its-entire-real-time-catalogue-open-all)
- Herbie: Python package for downloading model data. Supports HRRR, RAP, GFS, GEFS, AIGFS, AIGEFS, HGEFS, NBM, RRFS/REFS, RTMA/URMA, HAFS, CFS, ECMWF open data (IFS and AIFS), NAVGEM and HRDPS. Searches AWS, Google Cloud, NOMADS and Azure. Example: `Herbie('2021-01-01 12:00', model='hrrr').xarray("TMP:2 m")`. Source: [Herbie docs](https://herbie.readthedocs.io/en/latest/)
- Herbie latest release tag 2026.9.2, published 27 Sep 2026. Source: [GitHub API](https://api.github.com/repos/blaylockbk/Herbie/releases/latest)
- RRFS and REFS operational data have their own AWS registry entry (`noaa-rrfs-ops`). Source: [AWS Registry: RRFS](https://registry.opendata.aws/noaa-rrfs-ops/)

### Inferences
- True ensemble probabilities with a usable history: ECMWF ENS (51 members) on AWS since Jan 2023, and GEFS (31 members) on AWS since 2017. Raw ensembles are not calibrated at a single station, so they need a correction step (for example fitted against CLI results) before trading.
- ECMWF's portal is fine for live use but useless for history; the AWS bucket is the archive. Its resolution changed over time (0.4 degree "beta" in early 2024, 0.25 degree later, 0.1 degree from Oct 2026), which is another break in a backtest.
- HRRR is deterministic (one run), but its hourly updates and 3 km grid make it useful for same-day high/low and rain timing.
- For a small trader, starting with point extracts (NBM text, IEM MOS, Open-Meteo) is far cheaper than processing grids. Grids are only worth it if a custom ensemble blend is the plan.

### Gaps
- The exact date ECMWF's AWS files switched from 0.4 to 0.25 degree was not checked (Open-Meteo lists its IFS 0.25 degree archive from 3 Feb 2024; see section 5).
- The Google Cloud and Azure bucket names and archive depths were not checked.
- NOMADS real-time retention (how many days it keeps) was not checked.

---

## 5. Open-Meteo

### Takeaway
The easiest point API, with five useful endpoints: forecast, ensemble, historical forecast, previous runs and single runs. The ensemble API only keeps 3 past days of members, so it cannot backtest ensemble probabilities. For day-ahead backtests use Previous Runs (lead day 1-7, most models from Jan 2024) or Single Runs (whole past runs, most models from 2 Apr 2026). The free tier is non-commercial only; trading is commercial use, so a paid plan is needed (Standard about $29/month, Professional about $99/month, and historical/ensemble access needs Professional).

### Cited findings
- Historical Forecast API: `https://historical-forecast-api.open-meteo.com/v1/forecast`. Built by stitching the first few hours of each model run into one continuous series; not suited to long series because model versions change. Model start dates include HRRR 1 Jan 2018, GFS 23 Mar 2021, NBM 8 Oct 2024, NAM 1 Sep 2025, AIGFS/HGEFS 7 Jan 2026, ECMWF IFS 0.25 degree 3 Feb 2024, ECMWF IFS HRES 9 km 1 Jan 2017, AIFS 20 Feb 2025. Daily variables include max/min 2 m temperature and precipitation probability max. Source: [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api)
- Tested: NBM daily values at Central Park for 18-22 Oct 2026 = highs 59.3, 61.3, 66.5, 61.6, 65.3 F, PoP max 0 each day. Source: [test request](https://historical-forecast-api.open-meteo.com/v1/forecast?latitude=40.7789&longitude=-73.9692&start_date=2026-10-18&end_date=2026-10-22&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&models=ncep_nbm_conus&temperature_unit=fahrenheit&timezone=America/New_York). Actual GHCN-Daily highs for those days were 57, 62, 67, 62, 67 F, with 0.00 inch rain. Source: [NCEI test request](https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094728&startDate=2026-10-10&endDate=2026-10-25&dataTypes=TMAX,TMIN,PRCP&units=standard)
- Previous Runs API: `https://previous-runs-api.open-meteo.com/v1/forecast`. Variables with suffix `_previous_day1` ... `_previous_day7` give the value forecast 1-7 days before. Most models from Jan 2024; GFS 2 m temperature from Mar 2021; JMA from 2018. More history can be rebuilt on request. Example: `...?latitude=52.52&longitude=13.41&hourly=temperature_2m,temperature_2m_previous_day1&past_days=7&forecast_days=1`. Source: [Open-Meteo Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api)
- Tested: Previous Runs returned GFS `temperature_2m_previous_day1` and `_previous_day2` for Central Park. Source: [test request](https://previous-runs-api.open-meteo.com/v1/forecast?latitude=40.7789&longitude=-73.9692&hourly=temperature_2m,temperature_2m_previous_day1,temperature_2m_previous_day2&past_days=2&forecast_days=1&models=gfs_seamless&temperature_unit=fahrenheit)
- Single Runs API: `https://single-runs-api.open-meteo.com/v1/forecast` with `run=YYYY-MM-DDTHH:MM`. ECMWF IFS HRES 9 km from 14 Mar 2024; most other models from 2 Apr 2026. Runs appear about 4-6 hours after start time for global models, 1-3 hours for regional. Source: [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api)
- Ensemble API: `https://ensemble-api.open-meteo.com/v1/ensemble`. Models include GFS ensemble 0.25 degree (31 members, 10 days), GFS ensemble 0.5 degree (31, 35 days), AIGFS (31), ECMWF IFS 0.25 degree (51, 15 days), ECMWF AIFS (51), GEM (21), Google WeatherNext 2 (64 members, 15 days), among others. Only "up to three days" of past ensemble data via `past_days`; means and spreads kept longer via an Ensemble Mean API. Source: [Open-Meteo Ensemble API](https://open-meteo.com/en/docs/ensemble-api)
- Free tier: 600 calls/minute, 5,000/hour, 10,000/day, 300,000/month, non-commercial only. Commercial: API Standard 1M calls/month, Professional 5M, Enterprise 50M+. A call with more than 10 variables or more than 2 weeks counts as more than one call. Historical, climate, ensemble and satellite APIs need Professional or higher. Source: [Open-Meteo Pricing](https://open-meteo.com/en/pricing)
- Prices: Standard $29/month, Professional $99/month. Source: [Open-Meteo Substack](https://openmeteo.substack.com/p/api-subscriptions-for-commercial). A June 2026 third-party listing gives 29 and 99 EUR. Source: [ki-syndikat](https://www.ki-syndikat.de/tools/open-meteo/). Another listing (€4.99) conflicts and looks unreliable. Source: [apispine](https://apispine.com/open-meteo/pricing)

### Inferences
- The Historical Forecast API is a "very short lead" series (each value is from the newest run). It looks better than a real day-ahead forecast would, so it should not be used to judge day-ahead skill.
- Previous Runs day-1 values are the closest thing to an honest day-ahead backtest from Open-Meteo, but they are values at a lead time, not the PoP or percentiles we need.
- Open-Meteo is good for fast prototyping and multi-model comparison. For true probability history, NBM files on AWS are better and free.
- Kalshi trading is commercial use, so the free tier's licence does not cover it. Professional ($99/month) appears needed if historical or ensemble endpoints are used.

### Gaps
- Pricing page did not show dollar figures directly; the $29/$99 figures come from Open-Meteo's own Substack post and a third party.
- How long the Ensemble Mean API keeps data is not stated.
- Whether Previous Runs carries `precipitation_probability` for NBM was not tested.

---

## 6. Observations (the "what actually happened" side)

### Takeaway
Kalshi daily high/low markets settle on the final NWS Daily Climate Report (CLI). IEM has a free, parsed, same-day CLI archive (Central Park back to 2004). This is the best truth source. IEM's ASOS archive is near real time (10-minute sync), with 1-minute data from 2000. The NWS API keeps only 7 days of observations. NCEI GHCN-Daily ran about 3 days behind in a test. Synoptic's free tier is non-commercial.

### Cited findings
- Kalshi: "Daily high/low temperature markets settle based on the final climate report issued by the National Weather Service (NWS)", typically released the next morning. NWS climate reports use local standard time, so during daylight saving time the day runs 1:00 AM to 12:59 AM local time. Settlement can be delayed if the final high is lower than an earlier preliminary report. Hourly temperature markets settle on The Weather Company data. Source: [Kalshi Help: Weather Markets](https://help.kalshi.com/markets/popular-markets/weather-markets)
- Tested: IEM CLI JSON `https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2026` returned 298 days, including 25 Oct 2026 (same day). Fields include `high`, `low`, `high_time`, `low_time`, `precip`, `snow`, normals, records, and a link to the raw CLI text (`/api/1/nwstext/202610252033-KOKX-CDUS41-CLINYC`). Source: [test request](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2026)
- Tested: the same endpoint has full years for KNYC from 2004 onward (366 rows in 2004); 2000 returned nothing. Source: [2004 test](https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2004)
- IEM ASOS/AWOS/METAR archive: synced from real-time ingest every 10 minutes. Limits: with no station picked, up to a 24-hour period of all data; with stations picked, "1,000 station years" per request. Backend `/cgi-bin/request/asos.py` (help at `?help`). US ASOS 1-minute data from 2000 (`/request/asos/1min.phtml`), with "very little quality control". Source: [IEM ASOS download](https://mesonet.agron.iastate.edu/request/download.phtml)
- IEM API v1 (OpenAPI) includes `/api/1/daily.{fmt}`, `/api/1/obhistory.{fmt}`, `/api/1/currents.{fmt}`, `/api/1/mos.{fmt}`, `/api/1/nwstext/{product_id}`, `/api/1/nws/afos/list.{fmt}` and `/api/1/asos_interval_summary.{fmt}` (tested listing). Source: [IEM OpenAPI](https://mesonet.agron.iastate.edu/api/1/openapi.json)
- NWS API observations: kept 7 days; MADIS QC delay up to 20 minutes; 24-hour max/min null outside the Central time zone. Source: [NWS API docs](https://www.weather.gov/documentation/services-web-api)
- Tested: NCEI GHCN-Daily for Central Park (USW00094728), queried 25 Oct 2026, had data only through 22 Oct 2026 (about 3 days behind). Endpoint `https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=...&dataTypes=TMAX,TMIN,PRCP` returns CSV, no key needed. Source: [test request](https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094728&startDate=2026-10-10&endDate=2026-10-25&dataTypes=TMAX,TMIN,PRCP&units=standard)
- Synoptic (MesoWest): Open Access tier for researchers and academics (non-commercial); commercial pricing by quote; 14-day free trial. Source: [Synoptic pricing](https://synopticdata.com/pricing/). Launched in 2022 with no data volume limits for public data. Source: [Business Wire 2022](https://www.businesswire.com/news/home/20220315005424/en/Synoptic-Data-PBC-Launches-New-Open-Access-Weather-Data-Service). A third-party package page says free use was capped at 5,000 requests and 5 million service units a month (may be out of date). Source: [SynopticPy](https://pypi.org/project/SynopticPy/0.0.7)

### Inferences
- Use IEM CLI JSON as the label for every backtest: it is the settlement number, it is free, and it goes back 20+ years for big stations.
- For live trading during the day, IEM's ASOS feed (10-minute sync) or the NWS API's latest observation show how high the temperature has already gone. The running max matters a lot late in the day.
- The CLI high can be higher than the highest hourly METAR reading, because the CLI uses continuous readings between the hourly reports. A model fitted on hourly METAR maxes may under-predict the CLI high. (Inference, not checked in this pass.)
- GHCN-Daily is fine for long history but too slow for settlement checks.

### Gaps
- Kalshi's settlement rules for the rain markets (for example, whether a "trace" counts) were not found on the help page.
- The station list for each Kalshi city was not confirmed from Kalshi's own rules. A web-search summary mentioned third-party pages mapping KXHIGHNY to KNYC (Central Park) and KXHIGHCHI to KMDW (Midway), but no source stating it could be opened, so treat it as unverified.
- IEM's 1-minute ASOS update delay was not stated.
- Synoptic's current free limits are not published on its pricing page.

---

## 7. Commercial options (brief)

### Takeaway
None of the paid options adds true probabilities that NBM does not already give for free. Visual Crossing is the cheapest paid source of archived forecasts. Tomorrow.io and Meteomatics have small free tiers. The Weather Company matters mainly because it settles Kalshi's hourly temperature markets; its prices are not public.

### Cited findings
- Tomorrow.io free plan: 500 requests/day, 25/hour, 3/second; no monthly cap. Source: [Tomorrow.io support: free limits](https://support.tomorrow.io/hc/en-us/articles/20273728362644-Free-API-Plan-Rate-Limits). Paid tiers priced by call volume; figures not published in the pages found. Source: [Tomorrow.io pricing overview](https://support.tomorrow.io/hc/en-us/articles/23554984091156-Tomorrow-io-Pricing-Overview)
- Visual Crossing: pay-as-you-go $0.0001 per record, no minimum; free accounts capped at 1,000 records/day. Historical forecast queries are billed per record returned. Example: 2 years of hourly data for one place = $1.75. Sources: [Visual Crossing pricing](https://www.visualcrossing.com/weather-data-pricing/); [Visual Crossing cost blog](https://www.visualcrossing.com/resources/blog/what-will-my-weather-data-cost/). Third-party listing: Professional $35/month (10M records), Corporate $150/month (unverified). Source: [ki-syndikat](https://www.ki-syndikat.de/tools/visual-crossing/)
- Visual Crossing Historical Forecast API: `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/api/v1/historicalforecast/[location]/byrun/[start]/[end]` or `/bytarget/`. Needs a "Historical Forecast Addon" subscription. Source: [Visual Crossing Historical Forecast API](https://www.visualcrossing.com/resources/documentation/weather-api/historical-forecast-api/). Forecasts are stored from the full model runs at midnight UTC each day. Source: [Visual Crossing how-to](https://www.visualcrossing.com/resources/documentation/weather-data/how-to-query-weather-forecasts-from-the-past-historical-forecasts/)
- Meteomatics free Basic: 500 requests/day, 15 basic parameters, 10-day forecast, 24 hours of history, strictly non-commercial. Paid plans by quote. Source: [Meteomatics free account](https://www.meteomatics.com/en/api-entry-level/)
- The Weather Company: Kalshi hourly temperature markets settle on its readings (e.g. KORD for Chicago). Source: [Kalshi Help: Weather Markets](https://help.kalshi.com/markets/popular-markets/weather-markets)

### Inferences
- Visual Crossing's archived forecasts are single numbers (one stored run per day), so they help only as another baseline.
- For a small budget, free NOAA data plus maybe Open-Meteo Professional covers almost everything.

### Gaps
- The Weather Company API prices were not found.
- Visual Crossing's historical-forecast archive start date and add-on price were not stated on its docs page.
- Tomorrow.io and Meteomatics paid prices are not published.

---

## 8. Which sources give true probabilities vs a single number?

### Takeaway
Only NBM gives free, calibrated percentiles for daily max/min temperature at stations, with an archive (AWS from May 2020; IEM NBS standard deviations from Nov 2018). Raw ensembles (GEFS, ECMWF ENS, AIFS ENS) give real spread but need calibration. Almost every source gives a true probability for rain (PoP); for temperature, NWS, MOS, HRRR and most APIs give one number only.

### Cited findings

| Source | Temperature output | Rain output | Past-forecast archive |
|---|---|---|---|
| NBM GRIB2 qmd | Percentiles 0-100% plus exceedance odds for daily max/min | PoP (>=0.01 in) for 1/6/12/24 h, rain amount percentiles | AWS from 18 May 2020 |
| NBM text (NBP, NBS, NBE) | NBP: 10/25/50/75/90th percentiles, mean, spread. NBS/NBE: high/low plus standard deviation | PoP 6/12/24 h, rain amount | AWS from May 2020; IEM NBS from Nov 2018 |
| NWS official (API, NDFD, PFM) | One number (high, low) | 12-hour PoP, rain amount | IEM PFM text from 2005; NDFD on AWS from 2020, NCEI from 2004 |
| GFS MOS / LAMP | One number (N/X) | PoP 6/12 h | IEM: GFS MOS from Dec 2003; LAMP from Jul 2020 |
| GEFS, ECMWF ENS, AIFS ENS (raw ensembles) | 31 / 51 / 51 members (spread, not calibrated) | Members, plus ECMWF probability products | AWS: GEFS from 2017 (reforecast 2000-2020); ECMWF from Jan 2023 |

Sources for the table, by row. NBM: [AWS NBM listing](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5), [qmd idx](https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20261025/12/qmd/blend.t12z.qmd.f042.co.grib2.idx), [MDL text products](https://vlab.noaa.gov/web/mdl/nbm-text-products), [IEM MOS](https://mesonet.agron.iastate.edu/mos/). NWS: [NWS API docs](https://www.weather.gov/documentation/services-web-api), [NCEI NDFD](https://www.ncei.noaa.gov/node/765), [IEM PFM 2005](https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=PFMOKX&sdate=2005-01-01&edate=2005-01-02&limit=1&fmt=text). MOS: [MDL TPB 05-01](https://vlab.noaa.gov/documents/6609493/36173388/mdltpb05-01.pdf), [IEM MOS](https://mesonet.agron.iastate.edu/mos/). Ensembles: [Open-Meteo Ensemble API](https://open-meteo.com/en/docs/ensemble-api), [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data), [GEFS listing](https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5), [GEFS reforecast listing](https://noaa-gefs-retrospective.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=GEFSv12/reforecast/), [ECMWF AWS listing](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5).

Single-number-only sources:
- HRRR (one deterministic run, hourly), AWS from 30 Jul 2014. Source: [HRRR listing](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&delimiter=/&max-keys=5)
- Open-Meteo forecast / historical forecast / previous runs / single runs give model values (PoP is included for some models). Ensemble members are only kept 3 days back. Sources: [Open-Meteo Ensemble API](https://open-meteo.com/en/docs/ensemble-api); [Open-Meteo Previous Runs](https://open-meteo.com/en/docs/previous-runs-api)
- Visual Crossing historical forecasts (one stored run per day). Source: [Visual Crossing how-to](https://www.visualcrossing.com/resources/documentation/weather-data/how-to-query-weather-forecasts-from-the-past-historical-forecasts/)

### Inferences
- A sensible build order: (1) labels from IEM CLI; (2) baseline probability from NBM NBP percentiles or NBS standard deviation; (3) check calibration (does a 70% bracket really win 70% of the time?) against CLI by city, season and NBM version; (4) only then add ECMWF ENS or GEFS members if NBM looks miscalibrated.
- For rain markets, NBM's 1-hour or 6-hour PoP grids can be combined to cover the exact CLI calendar day; MOS and NWS PoP12 windows only roughly match it.
- The free data is good enough that the edge, if any, will come from handling the CLI day window, station quirks and version changes carefully, not from buying data.

### Gaps
- No public study was found in this pass measuring NBM percentile calibration at the Kalshi settlement stations.
- Whether the NBP percentiles are available for every Kalshi city station (and from which date) was only checked for KNYC.
