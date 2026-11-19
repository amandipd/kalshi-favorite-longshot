# Same-day ("intraday") nowcasting for Kalshi daily high, low and rain markets

Research notes, written 26 Oct 2026. "Nowcasting" means using live observations to call the answer for today, rather than a forecast made the day before.

How to read the sources: "(search excerpt)" means the claim was seen in a search result summary, but the page itself could not be opened. Treat those as weaker. "(checked live 26 Oct 2026)" means the data was pulled directly from the named public feed on that day. Internal results from this repo are cited by file path.

Plain-words key, used throughout:
- ASOS = the automated weather station at an airport (Automated Surface Observing System).
- METAR = the standard coded weather report a station sends, normally once an hour at about :51 past.
- LST = local standard time. The climate day is always midnight to midnight standard time. In summer that is 1 AM to 1 AM on the clock.
- CLI = the NWS daily climate report. It holds the official high, low and rain.
- DSM = the ASOS Daily Summary Message, the raw machine summary the CLI is built from.
- 6-hour max/min groups = extra codes in the 00, 06, 12 and 18 UTC METARs giving the highest and lowest temperature of the past 6 hours.

---

## 1. How the official daily high is made at an ASOS station, and when each piece becomes public

### Takeaway
The official high is the highest **5-minute running average** temperature of the standard-time day, kept in whole °F inside the station. Hourly METARs only show one minute per hour, so they miss peaks between hours. That is why the official high runs about 0.7-0.8°F above the highest hourly reading. Yes, there is public data that shows the true running max before the 00 UTC group. The best is the **afternoon DSM**: two of them on a normal day at NYC and Midway (valid 3 PM and 4 PM standard time), each giving the exact whole-°F max so far and the minute it happened. The 4 PM preliminary CLI repeats this. Last of all, the **midnight-LST METAR "4-group"** (the 24-hour max) is sent at about 11:51 PM standard time. That is about 9 minutes **before** Kalshi closes.

### Cited findings

**How the station measures and averages (ASOS User's Guide, 1998; NWS office pages, undated, read Oct 2026)**
- The sensor takes about six samples a minute. These make a 1-minute average. Once a minute the station computes a 5-minute average from the last five 1-minute values (it needs at least 4 valid ones). The 5-minute average is "rounded to the nearest degree Fahrenheit, converted to the nearest 0.1 degree Celsius." Midpoints round up. Source: [ASOS User's Guide §3.1.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- Once a minute, the station uses the running 5-minute average to update the hourly max and min. It keeps each hour's max and min for 24 hours. Source: [ASOS User's Guide §3.1.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- The 6-hour max/min groups ("1snTxTxTx" and "2snTnTnTn") are built from those hourly maxima and minima, in tenths of °C. They go in the 00, 06, 12 and 18 UTC METARs. Source: [ASOS User's Guide §3.1.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- Once a minute, the station also tracks the highest and lowest temperature "so far for the current calendar day," in tenths of °C. These go in the "midnight, LST hourly METAR" as the 24-hour group (4snTxTxTx snTnTnTn). That METAR "is usually transmitted before 23:59 LST," so it can differ slightly from the DSM, which covers 00:00 to 23:59 LST. Source: [ASOS User's Guide §3.1.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- The hourly METAR carries the temperature to the nearest 0.1°C in the remarks ("T-group"). Source: [ASOS User's Guide §3.1.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- NWS Chicago agrees: about one reading every 10 seconds, stored each minute as whole °F, then "aggregated into a rolling 5-minute average." The day's high and low come from these rolling averages. A high or low can fall between METARs and never show in any of them. Hourly and special METARs are in tenths of °C, "which preserves the original °F reading." The 5-minute METARs are rounded to whole °C, so converting back to °F can be off by 1-2 degrees. Source: [NWS Chicago observations FAQ](https://www.weather.gov/lot/weather_observations_faq)
- NWS Phoenix: the daily high/low is "the highest/lowest of the rolling 5-minute averages reported between 0000 LST and 2359 LST." Its worked example: a 116°F average is 46.7°C, which rounds to 47°C, which shows as 117°F. Those "are not valid temperatures" for climate use. Source: [NWS Phoenix HiRes ASOS](https://www.weather.gov/psr/HiResASOS)
- NWS Los Angeles: the internal data "can capture highs and lows that occur between 5-minute observations." "Real-time one minute data is not publicly available." Source: [NWS Los Angeles ASOS temperature](https://www.weather.gov/lox/asostemperature)
- **Conflict.** Daryl Herzmann of the Iowa Environmental Mesonet (IEM) wrote on 4 Dec 2024 (updated 17 Dec 2024) that the official daily max/min use **2-minute** averages of 2-5 second samples, in whole °F. Source: [IEM News #1469 "Wagering on ASOS Temperatures"](https://mesonet.agron.iastate.edu/onsite/news.phtml?id=1469). The vendor minuteTemp repeats "2-minute averaged one-minute data". Source: [minuteTemp settlement docs](https://minutetemp.com/docs/market-settlement). The ASOS User's Guide and three NWS offices all say a 5-minute running average. This note could not settle the conflict.
- IEM (Dec 2024) lists the only sources with whole-°F accuracy as: the 6-hourly METAR groups, the DSM, and the CLI/CF6. It says the T-group is "not a whole-degree Fahrenheit source." It says IEM has blanked temperatures in its 5-minute data since 2016 to avoid confusion. Source: [IEM News #1469](https://mesonet.agron.iastate.edu/onsite/news.phtml?id=1469). (This partly conflicts with NWS Chicago's line that tenths-°C "preserves the original °F reading." See Inferences.)

**What the DSM and CLI contain, and when (checked live 26 Oct 2026)**
- NYC (Central Park) DSM issued 20:15 UTC on 26 Oct 2026: `KNYC DS 1500 26/10 691434/ 500722//`. That reads: valid as of 15:00 LST, max 69°F at 14:34 LST, min 50°F at 07:22 LST. Source: [api.weather.gov product](https://api.weather.gov/products/188a1349-42cd-4150-bf7c-2467ead0ab39)
- NYC DSMs over the past days came at 20:15 UTC (valid 1500 LST), 21:15 UTC (valid 1600 LST), and 05:15 UTC (full day). A second message came at 05:30 UTC each night. The one opened for this note (26 Oct) carried the summary for 21 Oct, so it looks like a re-send of an older day. Source: [api.weather.gov DSM list, NYC](https://api.weather.gov/products/types/DSM/locations/NYC)
- NYC preliminary CLI, issued 4:33 PM EDT on 26 Oct 2026: "VALID TODAY AS OF 0400 PM LOCAL TIME." Max 69°F at 2:34 PM LST. Precipitation 0.00. It matches the 1500 LST DSM. Source: [NWS CLI NYC](https://forecast.weather.gov/product.php?site=OKX&issuedby=NYC&product=CLI&format=txt&version=1&glossary=0)
- NYC CLI issue times, 23-26 Oct 2026: preliminary at 20:32-20:33 UTC each day. Final at 06:21-06:46 UTC, which is 1:21-1:46 AM EST. Source: [api.weather.gov CLI list, NYC](https://api.weather.gov/products/types/CLI/locations/NYC)
- Chicago Midway DSMs for 25 Oct 2026: `KMDW DS 1500 …741417/`, `KMDW DS 1600 …741417/`, then the full-day DSM (max 74°F at 14:17 LST). Source: [IEM text archive, DSMMDW](https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=DSMMDW&limit=4&fmt=text)
- NWS Chicago: preliminary CLIs go out "shortly after 4:30 PM CST/CDT." Full-day CLIs go out "shortly after 12:30 AM CST/1:30 AM CDT." CLI values are preliminary. NCEI does final checks "3+ months after." The DSM is "used to generate the CLI." Source: [NWS Chicago FAQ](https://www.weather.gov/lot/weather_observations_faq)
- Wethr.net (vendor guide, updated 15 Feb 2026) lists DSM release times in UTC. NYC: 20:21, 21:21, 05:17. Denver: 12:17, 22:17, 23:17, 07:17. Los Angeles: 22:08, 01:08, 08:08. 6-hour max METARs: about 23:51-23:54, 05:51-05:54, 11:51-11:54, 17:51-17:54. Source: [Wethr market bots guide](https://wethr.net/edu/market-bots)
- Wethr's NYC page gives KNYC times in UTC. DSMs: 05:13, 05:28, 20:13, 21:14. CLI: 06:36 (±11 min). 6-hour METARs: 05:51, 11:51, 17:51, 23:51. "24-hour high METAR: 04:51 UTC (±1 min)." Source: [Wethr KNYC guide](https://wethr.net/edu/market/newyork)
- The IEM says its max/min values differ from other sites mainly because it reads the DSM, which "has a reliable max/min temperature." It also uses the 6-hour METAR values. Source: [IEM News #1469](https://mesonet.agron.iastate.edu/onsite/news.phtml?id=1469)

**Kalshi's own rules (checked live 26 Oct 2026)**
- KXHIGHNY-26OCT27-T67: close_time 2026-10-28 05:00 UTC. That is midnight EST, or 1 AM EDT. The text says "The Last Trading Time will be 11:59 PM local time on October 27." It settles on "the maximum temperature recorded at New York City (CLINYC) … according to The Weather Company." Expiration is "the sooner of the first 7:00 or 8:00 AM ET following the release of the data … or one week after." Only "the initial non-preliminary publication" counts. Source: [Kalshi API, KXHIGHNY markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&limit=2)
- The Kalshi help page (22 Jul 2026) says settlement may be delayed if a high "is not consistent with 6-hr or 24-hr highs reported by METAR," or if the final NWS high is "lower than previous preliminary report." Source: [Kalshi Help: Weather Markets](https://help.kalshi.com/en/articles/13823837-weather-markets)

**Our own earlier results (internal)**
- The official CLI high averages 0.7-0.8°F above the highest hourly METAR. Adding the 6-hour max groups matched the official high on 94-99% of days. Since about 14 Aug 2026 the rules name The Weather Company, but the value still matched NWS CLI on 1,316 of 1,317 city-days. Source: `reports/Kalshi weather bot feasibility.md` and `research_notes/Kalshi weather bot feasibility/`
- 26 Oct 2026 backtest: on 32 of 33 city-days where a 90c+ favourite lost at 6 PM LST, the official high came in above the favoured bracket. Source: `reports/Weather favourites test Oct 26.md`

### Evidence timeline for one city (NYC on a daylight-time day; NYC standard time = UTC−5, clock time = UTC−4)

| What comes out | UTC | NYC clock (EDT) | What it tells you |
|---|---|---|---|
| Hourly METAR | :51 every hour | :51 every hour | Exact whole-°F reading for that one minute (T-group, in tenths °C) |
| 18Z METAR, 6-hour group | about 17:51 | about 1:51 PM | Exact max of about 7:51 AM to 1:51 PM |
| DSM no. 1 | 20:13-20:21 | about 4:15 PM | Exact official max so far (to 3 PM LST) and its minute |
| Preliminary CLI | 20:32-20:33 | about 4:33 PM | Same max, "valid as of 4 PM local" |
| DSM no. 2 | 21:14-21:21 | about 5:15 PM | Exact official max so far (to 4 PM LST) |
| 00Z METAR, 6-hour group | about 23:51 | about 7:51 PM | Exact max of about 1:51-7:51 PM |
| Midnight-LST METAR, 24-hour group | about 04:51 | about 12:51 AM | Exact max of the last 24 hours, about 9 min before close |
| Kalshi close | 05:00 | 1:00 AM | Trading stops (midnight EST) |
| Final DSM | 05:13-05:17 | about 1:15 AM | Official full-day max (raw) |
| Final CLI | 06:21-06:46 | about 2:30 AM | The settlement number |

Sources for the table: the rows above, plus [ASOS User's Guide](https://www.weather.gov/media/asos/aum-toc.pdf), [Wethr KNYC](https://wethr.net/edu/market/newyork), and the live NWS feeds cited above. Times move by one hour, relative to clock time, when clocks go back on 1 Nov 2026.

### Inferences
- **The T-group carries the exact whole-°F value.** The station rounds to whole °F first, then converts to 0.1°C. A 0.1°C step is much finer than 1°F, so the °F value can be recovered exactly. A script checked every whole °F from −40 to 130, and all map back uniquely. So hourly and special METARs give the exact whole-°F 5-minute average, but only for that one minute. IEM's warning against the T-group seems to be about which minute it shows ("top of the hour" is fuzzy, :50-:59), not about precision. This is an inference, not a stated NWS fact.
- **Why the official high beats the hourly max.** The day's max can happen in any of 1,440 minutes. The hourly METAR samples 24 of them. The 6-hour groups and the DSM capture every minute.
- **Whole-°C feeds can only sometimes split a bracket edge.** The 5-minute METARs and the 1-minute feed report whole °C. Each whole °C covers one or two whole °F values. Computed with the ASOS rounding rule, these pairs share one °C value: 60/61, 62/63, 64/65, 66/67, 69/70, 71/72, 73/74, 75/76, 78/79, 80/81, 82/83, 84/85, 87/88, 89/90, 91/92, 93/94, 96/97, 98/99. These stand alone: 59, 68, 77, 86, 95, 104. So, for example:
  - "70 or below" (edge between 70 and 71): 70°F = 21°C and 71°F = 22°C. A 22°C reading proves the high reached at least 71.
  - Midway "87 vs 88": both are 31°C. No whole-°C feed can tell them apart. Only the T-group, the 6-hour group, the DSM or the 24-hour group can. This fits the trader anecdote of Midway settling 88 when the screens said 87.
- **The 6 PM LST snapshot and our 32-of-33 finding.** At 6 PM EST (23:00 UTC), NYC has had the 3 PM and 4 PM LST DSMs, but the 00Z 6-hour group is still 51 minutes away. Central cities get the 00Z group (23:51 UTC) about 9 minutes before 6 PM CST. Mountain and Pacific cities get it 1-2 hours earlier, but it only covers to about 4:51 PM MST or 3:51 PM PST. So a 6 PM LST price in an Eastern city can be blind to a late-afternoon peak that only shows up at 23:51 UTC. A cheap next check: split the 33 losing city-days by time zone and by the CLI time of the max. If most maxes came after the last DSM before the snapshot, the losses are a "late peak the screens missed" effect.
- **A backtest of "what was knowable" is possible with free data.** IEM archives raw METAR text (with the 6-hour and 24-hour groups) and DSM text. So we could rebuild, for each minute of each past day, the best public estimate of the running max. We could then compare it with the Kalshi price at that minute.

### Gaps
- The 2-minute versus 5-minute averaging conflict is not settled. None of the NWS directives opened for this note states it.
- NWS Directive 10-1004 and Federal Meteorological Handbook No. 1 were not read directly. The DSM field layout is read from examples, not from the DSM users' guide (the copy found would not load).
- DSM coverage is patchy. api.weather.gov lists DSMs for only 159 locations. NYC is on the list. Midway, Miami, Austin, Denver and Los Angeles are not ([DSM location list](https://api.weather.gov/products/types/DSM/locations)). IEM has Midway DSMs, but none were found under DSMMIA, DSMAUS, DSMDEN or DSMLAX. Wethr still lists release times for Denver and LA, so they probably exist under other product IDs or feeds. Not confirmed.
- The Kalshi rule text ("11:59 PM local time") and the API close_time (05:00 UTC, midnight EST) disagree by an hour during daylight time. Worth confirming which one governs.
- What the Weather Company "preliminary" readings on weather.com/kalshi show during the day is unknown. The page loads its data by script, and a plain fetch saw only headings.

---

## 2. Where to get live observations fastest, how fresh they are, and the terms of use

### Takeaway
For temperature, the free routes are: hourly METARs (aviationweather.gov, tgftp, IEM); the DSM and CLI text products (api.weather.gov products endpoint, IEM text archive, or the NOAAPort/LDM data feed); and the experimental 1-minute ASOS feed (MADIS, resold by Synoptic). The 1-minute feed is only in whole °C, arrives 2-5 minutes late, and was down from Oct 2023 to Jan 2026. api.weather.gov **observations** can lag up to 20 minutes, because they wait on MADIS quality checks. The NCEI 1-minute archive is 12-36 hours late, so it is for backtests only. NWS data is open for any use. Synoptic's free tier is non-commercial only.

### Cited findings

| Source | How fresh | Temperature precision | Terms |
|---|---|---|---|
| aviationweather.gov API | Cache files rebuilt "Once a minute"; 100 requests/min limit | Raw METAR, T-group in tenths °C | Must set a User-Agent; no stated ban on commercial use |
| api.weather.gov observations | "delayed up to 20 minutes from MADIS" | Decoded values; 24h max/min null outside Central time (known bug) | "free to use for any purpose" |
| api.weather.gov products (DSM, CLI) | Product appears at issue time (checked 26 Oct 2026: DSM 20:15, CLI 20:33 UTC) | Whole °F (official) | Same open terms |
| MADIS / Synoptic 1-minute ASOS (HF-ASOS) | "usually … between 2 and 5 minutes latency" | Whole °C only | MADIS: "publicly accessible"; Synoptic free tier non-commercial |
| NCEI / IEM 1-minute archive | 12-36 hours late | Whole °F, not the official average | Archive and backtests only |

Sources for each row:
- aviationweather.gov: the METAR cache files update "Once a minute." "All requests are rate limited to 100 requests per minute." Set a custom User-Agent. "Most METARs update once per hour." Source: [aviationweather.gov Data API](https://aviationweather.gov/data/api/)
- api.weather.gov: "Observations may be delayed up to 20 minutes from MADIS, the upstream source, due to QC processing." Station observations "always show missing (null) 24h max/min temperatures for stations outside the central time zone." "All of the information presented via the API is intended to be open data, free to use for any purpose." A User-Agent with contact details is required. The rate limit is "not public." Source: [NWS API documentation](https://www.weather.gov/documentation/services-web-api)
- An NWS API maintainer wrote on 22 Oct 2025: "It may take up to 20m for Madis to finish QA after the observation is issued, and returns partial data during the process." The legacy weather.gov pages "use a direct source." A user said he takes METARs from aviationweather.gov or tgftp.nws.noaa.gov as his baseline. Source: [weather-gov/api discussion #841](https://github.com/weather-gov/api/discussions/841)
- Synoptic HF-ASOS: "usually arrives with between 2 and 5 minutes latency." Temperatures are "expressed in whole degrees celsius." Wind is a 2-minute average. "HF-ASOS data was unavailable from its source between October 2023 and January 2026." "Brief to several-day outages are not uncommon." It is "experimental," and Synoptic says "We do not recommend developing applications solely based on" it. Station IDs get a "1M" suffix (KSLC1M). A 5-minute subset (HF-METAR) has been mixed into the normal network since 2017. Source: [Synoptic HF-ASOS docs](https://docs.synopticdata.com/services/high-frequency-asos)
- Synoptic: HFMETAR latency is "5-9 minutes or more," against "within 3 minutes" for formal METARs in most conditions. Source: [Synoptic METAR docs](https://docs.synopticdata.com/services/asos-awos-united-states-metar) (search excerpt)
- Synoptic pricing: Open Access is non-commercial, aimed at researchers. Commercial use needs a paid plan, priced case by case, with a 14-day trial. Source: [Synoptic pricing](https://synopticdata.com/pricing/) (search excerpt)
- MADIS 1-minute ASOS: "All observations are publicly accessible." The data "do not conform to the METAR data standard." Data arrive on "a continuous, asynchronous schedule." The current hour is processed every 5 minutes. All 1-minute values have been processed since Nov 2017. The page was last updated 15 Mar 2017. Source: [MADIS 1-minute ASOS](https://madis.ncep.noaa.gov/madis_OMO.shtml)
- MADIS restricted data: data outside the "full distribution" category may not be redistributed, including on public web pages. Derived products are allowed if users cannot pull raw values back out. A company can get restricted data only through a government, research or education sponsor. Source: [MADIS dataset restrictions](https://madis.ncep.noaa.gov/madis_restrictions.shtml) (search excerpt)
- NCEI 1-minute data via IEM: the archive was "available up until: 25 Oct 2026" when checked on 26 Oct 2026. Temperatures are in °F. Source: [IEM 1-minute download](https://mesonet.agron.iastate.edu/request/asos/1min.phtml). In Dec 2024 IEM said NCEI adds a 12-36 hour delay "due to the manual phone collection method," and that the 1-minute values do not use the official averaging, so a hand-made max will not match the daily summary. Source: [IEM News #1469](https://mesonet.agron.iastate.edu/onsite/news.phtml?id=1469)
- The ASOS one-minute observation (OMO) is ready each minute at 23 seconds past, but in 1998 it was "generally not transmitted long-line" beyond the local FAA/NWS network. Source: [ASOS User's Guide §5.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- US ASOS hourly reports are made at about :47-:53 past the hour, so a METAR can look 30-60+ minutes old by design. Source: [ForeFlight blog, 2016](https://blog.foreflight.com/2016/11/10/aging-surface-observations/) (search excerpt)
- A 2026 Unidata mailing-list reply called tgftp.nws.noaa.gov among the lowest-latency public HTTP sources for METARs. It also said the files are rebuilt on a cycle that can add minutes. Source: [Unidata ldm-users 2026](https://mailinglists.unidata.ucar.edu/archives/ldm-users/2026/msg00032.html) (search excerpt; the page failed to load with a certificate error)
- minuteTemp (vendor, 2026) claims 1,845 stations, "240 of which report on 1-minute data." It says it updates "Every minute where 1-minute data exists" and lists "<50ms avg latency" for its API. Its free plan has a "3 min delay"; paid plans run $14.99-$89.99 a month. It shows "NWS CLI, DSM and 6-hour METAR highs, with countdowns to the next report." Source: [minuteTemp](https://minutetemp.com/)

### Inferences
- Do not use api.weather.gov *observations* for speed. Its *products* endpoint (DSM, CLI) is fine. Read METARs from aviationweather.gov or tgftp instead.
- The 1-minute feed's value is narrow. It is whole °C, 2-5 minutes late and often down. It only helps on bracket edges where the two °F values fall in different °C bins (see Section 1). It cannot help on 87/88-type edges.
- The fastest route for text products (METAR, DSM, CLI) is probably a push feed: NOAAPort, or the Unidata LDM/IDD text feed. Polling websites is slower. No measured numbers comparing them were found.
- minuteTemp's "240 stations on 1-minute data" fits the MADIS/Synoptic HF-ASOS feed. It is a reseller, not a faster source.

### Gaps
- No measured, independent numbers were found for minutes from observation to public availability on aviationweather.gov, tgftp, IEM or NOAAPort. We would have to measure it ourselves: poll each source, log when each new METAR or DSM appears, and compare with the time inside the report.
- IEM's terms of use for commercial or trading use were not checked.
- Whether aviationweather.gov's raw METAR text always keeps the 6-hour and 24-hour remark groups was not confirmed. It should, as raw METAR includes remarks, but this was not verified.

---

## 3. Daily lows: the same issues for the overnight minimum

### Takeaway
The low works the same way. It is the lowest 5-minute running average of the standard-time day. The day runs 1 AM to 1 AM on the clock in summer. The afternoon DSMs show the exact low so far (NYC on 26 Oct: 50°F at 7:22 AM LST). The trap is the end of the day. On a cold-front day the low can be set in the last hour before standard midnight. Only the midnight-LST METAR's 24-hour group shows that before the close. For Eastern, Mountain and Pacific cities, the 6-hour groups do not line up with the standard-time day.

### Cited findings
- The climate day is midnight to midnight LST. It "does not change during daylight saving time," so in summer it runs 1 AM to 1 AM. A high or low between 12:00 and 1:00 AM CDT can belong to the day before. The 6-hour data "may miss highs, lows, or precipitation that occur between the 0600Z METAR's dissemination and midnight CST." Source: [NWS Chicago FAQ](https://www.weather.gov/lot/weather_observations_faq)
- Kalshi: the NWS high is recorded "between 1:00 AM and 12:59 AM local time the following day" during daylight time. Source: [Kalshi Help: Weather Markets](https://help.kalshi.com/en/articles/13823837-weather-markets)
- The station tracks the day's lowest temperature each minute and reports it in the midnight-LST METAR (24-hour group) and in the DSM. Source: [ASOS User's Guide §3.1.2](https://www.weather.gov/media/asos/aum-toc.pdf)
- The NYC 1500 LST DSM on 26 Oct 2026 gave min 50°F at 07:22 LST. The final DSMs give the full-day min. Source: [api.weather.gov DSM, NYC](https://api.weather.gov/products/188a1349-42cd-4150-bf7c-2467ead0ab39)
- Denver has a DSM at about 12:17 UTC (5:17 AM MST). That is an early-morning summary. Source: [Wethr market bots guide](https://wethr.net/edu/market-bots)
- A Kalshi high-temperature study proposal found that 3 of the 10 worst forecast misses were days with the high set at 11 PM or midnight. Six-hourly model output and the NBM's 7 AM to 7 PM window both miss those. Source: [GitHub issue, fulton-ring/agent-content-demos #89](https://github.com/fulton-ring/agent-content-demos/issues/89) (search excerpt)
- Kalshi daily-low markets are thin: 1-18k contracts a day, with spreads (the gap between the buy and sell price) often 6-18c. Source: the project's own scan of open weather markets (25 Oct 2026).

### Inferences
- The 6-hour windows end at about :51 before 00, 06, 12 and 18 UTC. Midnight LST is 05 UTC in the East, 06 UTC in Central, 07 UTC in Mountain and 08 UTC in Pacific. So only Central-time stations have 6-hour windows that roughly match the climate day. This likely explains part of the 1-6% of days where the 6-hour groups missed the official high. Our data could confirm it.
- For lows, the morning is easy. Once the 12Z 6-hour min, a morning DSM or the afternoon DSM is out, the low so far is known exactly. The risk is a late-evening fall. The last pre-close clue is the 24-hour group at about 11:51 PM LST. It covers 24 hours ending 11:51 PM LST, so it can include the final 8 minutes of the day before.
- With 6-18c spreads, any edge in lows would have to be large to pay.

### Gaps
- No study found on how often the daily low is set in the last hour of the standard-time day, by city. IEM's CLI and METAR archive could answer it.

---

## 4. Rain today: radar and short-range nowcasting, and how KXRAIN closes early

### Takeaway
KXRAIN pays Yes if the day's official rain is **strictly above 0**. Trace counts as **No**. The market "will close and expire early if the event occurs." The rules do not say which data feed triggers the early close. The settlement source is The Weather Company's portal. On the No side, the useful tools are radar and short-range models. MRMS radar rain rate updates every 2 minutes with about 90 seconds of lag. Plain radar extrapolation stays skilful for roughly 0.5-2 hours. HRRR (15-minute output) and AI models like MetNet-3 cover longer ranges. No study was found scoring any of them on "will this one airport record 0.01 inch before midnight."

### Cited findings

**KXRAIN rules (checked live 26 Oct 2026)**
- KXRAIN-26OCT27-TTN: "If the total precipitation at CLITTN in Trenton in Oct 27, 2026 is strictly greater than 0 inches, then the market resolves to Yes." "'Trace' amounts (T) and missing daily precipitation values are counted as 0 inches." Data "can be found at https://weather.com/kalshi." early_close_condition: "This market will close and expire early if the event occurs." close_time: 2026-10-28 05:00 UTC. Source: [Kalshi API, KXRAIN markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&limit=3)
- The West Palm Beach market in the same list names station "CLIDJT," not the old Palm Beach code. Source: same as above
- Kalshi's period-rain contract (RAINGLOBALPERIOD, amended 2 Sep 2026): "'Trace' amounts (T) are counted as 0.00." Missing values count as 0. "Only initial non-preliminary reported values shall be used." If the event happens, "expiration will be moved to an earlier date and time in accordance with Rule 7.2." Expiration time is 10:00 AM ET. Source: [Kalshi CFTC filing, 2 Sep 2026](https://www.cftc.gov/filings/orgrules/rules09022622958.pdf)
- KXRAIN's close_time stays at the scheduled close even when it closes early, and its price candles keep showing 0.99-1.00 after rain. Source: the project's own weather-market research (25 Oct 2026).

**What reveals rain at the station**
- Hourly METAR "Prrrr" = rain since the last hourly report, in hundredths of an inch. It is left out if there was none. "P0000" means trace only. 3-hour and 6-hour totals ("6RRRR") go in the 03/09/15/21 and 00/06/12/18 UTC METARs. The 24-hour total ("7RRRR") goes in the 12 UTC METAR. Source: [ASOS User's Guide §3.4](https://www.weather.gov/media/asos/aum-toc.pdf)
- Rain is added up each minute and rounded to the nearest hundredth. Sources: [NWS Chicago FAQ](https://www.weather.gov/lot/weather_observations_faq); [NWS Phoenix](https://www.weather.gov/psr/HiResASOS)
- The afternoon CLI and DSM carry rain so far today (NYC 26 Oct 2026: "TODAY 0.00"). Source: [NWS CLI NYC](https://forecast.weather.gov/product.php?site=OKX&issuedby=NYC&product=CLI&format=txt&version=1&glossary=0)

**Radar and nowcasting tools (dates as given)**
- MRMS (NOAA's national radar mosaic): "PrecipRate" is a 2-minute product in mm/hr. A 1-hour radar-only rain total also updates every 2 minutes. Source: [NSSL MRMS GRIB2 tables](https://nssl.noaa.gov/projects/mrms/operational/tables.php) (search excerpt)
- A 2021 NSSL talk lists the radar rain rate and 1-hour total at a 2-minute cycle with about 90 seconds of lag. The gauge-adjusted total is hourly, with Pass 1 at 20 minutes and Pass 2 at 60 minutes. Source: [Martinaitis, 2021](https://media.cocorahs.org/docs/Martinaitis-WERA21.pdf) (search excerpt)
- MRMS is on AWS as open data, no subscription needed. Source: [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-6odvdc4md2jjc) (search excerpt)
- NEXRAD Level II (raw single-radar data) streams in real time as "chunks" to the unidata-nexrad-level2-chunks S3 bucket in us-east-1, with a notification topic. A Unidata maintainer (2020) called it "the lowest possible latency you have to the data, unless you're upstream of us." Sources: [AWS blog](https://aws.amazon.com/blogs/aws/new-aws-public-data-set-real-time-and-archived-nexrad-weather-data/); [Unidata ldm-users 2020](https://www.unidata.ucar.edu/mailing_lists/archives/ldm-users/2020/msg00065.html) (search excerpts)
- HRRR (NOAA's 3-km hourly model) runs every hour. A small subset of fields comes out at 15-minute steps through the 15-hour forecast. Source: [NWS TIN 14-32](https://www.weather.gov/media/notification/tins/tin14-32hrrr_aaa.pdf) (search excerpt)
- LAMP (NWS station guidance that updates with live observations) runs every hour. It gives a 1-hour probability of measurable rain each hour out to 25 hours, and 6-hour probabilities to 38 hours. Source: [MDL LAMP elements](https://vlab.noaa.gov/web/mdl/lamp-elements) (search excerpt)
- RRFS (NOAA's new rapid-refresh model) goes operational on 3 Nov 2026 per an NWS notice updated 15 Oct 2026. It replaces NAM, HREF, SREF and HiresW, not HRRR. Sources: [NWS SCN 26-48](https://www.weather.gov/media/notification/pdf_2026/scn26-048_Updated_RRFS_and_REFS_Implementation.aaf.pdf) (search excerpt); [NOAA GSL RRFS](https://gsl.noaa.gov/rrfs)
- MetNet-3 (Google, 2023): forecasts precipitation, wind, temperature and dew point up to 24 hours ahead, at up to 2-minute and 1-km detail. Its authors say it can "outperform … HRRR and ENS over the CONUS region" out to 24 hours. "MetNet-3 is operational and its forecasts are served in Google Search." Source: [arXiv 2306.06079](https://arxiv.org/abs/2306.06079)
- The first MetNet (2020) beat HRRR for up to 7-8 hours. Source: [arXiv 2003.12140](https://arxiv.org/abs/2003.12140) (search excerpt)
- NowcastNet (Nature, 2023) is built for lead times up to 3 hours. Expert forecasters ranked it first in 71% of cases. Source: [NowcastNet, PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356617/) (search excerpt)
- For a radar extrapolation method, the longest skilful lead time ran from about 25 to 116 minutes, depending on the event. Source: [Imhoff et al., EGU 2020](https://presentations.copernicus.org/EGU2020/EGU2020-13376_presentation.pdf) (search excerpt)

### Inferences
- Once rain is recorded, the Yes side is decided and the market closes. So the only live bet late in the day is on No, the "stays dry" side. A No bet at, say, 95c needs a better than 95% chance that no measurable rain falls before midnight standard time.
- Radar answers the next 1-2 hours well. A typical evening snapshot (6 PM LST) has 6 hours to go, which is past plain extrapolation range. That stretch needs HRRR, LAMP or an AI model.
- What closes KXRAIN early is unknown. It may be the first hourly METAR with Prrrr ≥ P0001, or a Weather Company feed. This matters, because a bot reading radar or 5-minute rain data might see rain several minutes before Kalshi closes the market.
- Our 26 Oct 2026 rain test had only 110 bets on 25 dates, which is not enough data. Any nowcasting edge on rain would need months of logging to prove.

### Gaps
- No published skill score found for "≥0.01 inch at one airport between now and midnight" from MRMS, HRRR, LAMP or MetNet.
- The exact data trigger and timing of KXRAIN's early close are not in the rules. Our own trade and candle data could estimate it by comparing close timing with the hour the METAR first showed rain.
- No measured latency figures found for the NEXRAD chunks bucket.

---

## 5. How fast Kalshi and Polymarket weather prices react to new observations

### Takeaway
**No measured study** was found of reaction speed after METARs, 6-hour groups, DSMs or the preliminary CLI. The best public evidence is a community guide (Feb 2026). It says bots trade on DSM releases, 1-minute data, the 6-hour max METARs and CLI releases. It warns traders not to leave resting orders near those release times. The one academic study (Crosier, Sep 2026) shows the market beats public forecasts. But it stops at the target morning and says nothing about afternoon reactions. No public write-up of the "official high is 1°F above the screens" effect was found, and the "prilo-weatheredge" blog could not be found.

### Cited findings
- Wethr.net (updated 15 Feb 2026) names these bot types:
  - "DSM Bot": "reacts quickly to the release of NWS Daily Summary Messages."
  - "OMO Bot": can "access the temperature readings for the minutes *between* those public reports," though "usually in Celsius."
  - "6 Hour Bot": "monitors the 6-hourly maximum temperature."
  - "CLI Bot": "There's speculation this bot type might be less active or predictable now."
  - Also a market-making "240" bot and a "1-Up" bot that improves its place in the queue.
  - Advice: avoid unprotected limit orders near DSM and 6-hour release times. No reaction times in seconds are given. Source: [Wethr market bots guide](https://wethr.net/edu/market-bots)
- Wethr also says "DSMs often report the highest temperature observed up to the report's issuance time." Source: [Wethr NWS data guide](https://wethr.net/edu/nws-data-guide)
- minuteTemp (vendor, 2026) sells per-minute station data, "60s push updates," and "countdowns to the next report" for CLI, DSM and 6-hour highs. It claims its hourly index rebuilds "about 2-3 seconds after Kalshi gets the station batch." Source: [minuteTemp](https://minutetemp.com/)
- Crosier, "Prediction Markets Beat the Weather Forecast on Tomorrow's High Temperature" (arXiv 2609.23969, Sep 2026). It covers 7 cities and 7,590 city-days to 12 Aug 2026.
  - The market's typical error (root-mean-square error) is about 10% below the NBM (the National Blend of Models, the best public forecast) after its first hour of trading. It is 11% below at the NBM's final bulletin on the target morning.
  - "The National Blend travels four times further toward the market between its postings than the market travels toward the NBM."
  - LAMP, which uses live observations, "drives the public stack's improvement the most." The authors suggest leaning on real-time observations "may be how market participants beat the public forecasts themselves."
  - The official high "is the peak of a continuous record and often falls between hours." LAMP runs 1-2°F cold for that reason.
  - Its three checkpoints are 11 AM ET the day before, 7 PM the evening before, and the 13 UTC NBM bulletin on the target day. Nothing on the target-day afternoon. Source: [arXiv 2609.23969](https://arxiv.org/abs/2609.23969)
- Patrick Brown's ForecastEx scorecards on Interactive Brokers (Mar-Aug 2026) rank ForecastEx first on mean absolute error for daily highs (about 1.25-1.43°F). They score prices from 5 PM ET the day before to 5 AM ET. They are not intraday. Source: [IBKR Traders' Insight, Apr 2026](https://www.interactivebrokers.com/campus/traders-insight/april-13-2026-update-prediction-markets-might-already-be-the-best-source-for-todays-weather-forecast/) (search excerpt)
- Settlement sources differ by venue (minuteTemp, 2026). Polymarket (international) uses the weather.gov time-series table for most cities. Polymarket US uses the NWS CLI. Robinhood/IBKR (ForecastEx) use Weather Underground. Source: [minuteTemp settlement docs](https://minutetemp.com/docs/market-settlement)
- Polymarket temperature markets resolve on the highest reading in the weather.gov time-series "Temp" column, in whole °C, once all hours are final. Source: [lines.com market pages](https://www.lines.com/prediction-markets/science/highest-temperature-in-tokyo-on-june-29-2026) (search excerpt; affiliate commentary)
- Herzmann's IEM post was titled "Wagering on ASOS Temperatures" (Dec 2024). It answers bettors' questions about why displayed temperatures differ from official ones. Source: [IEM News #1469](https://mesonet.agron.iastate.edu/onsite/news.phtml?id=1469)
- Kalshi says settlement may be held if the CLI high clashes with 6-hour or 24-hour METAR highs. So Kalshi itself checks those groups. Source: [Kalshi Help: Weather Markets](https://help.kalshi.com/en/articles/13823837-weather-markets)

### Inferences
- The release-driven bots in the Wethr guide imply that the DSM, the 6-hour max and the 24-hour group are priced in within moments by someone. The edge, if any, is not in reacting to those releases.
- Our 32-of-33 finding points somewhere else: the gap between releases. A late-afternoon peak that lands between hourly METARs, with no DSM left before the 00Z group, can go unpriced for up to an hour or more (see Section 1). The 1-minute °C feed is the only live view into that gap. It only works where the bracket edge splits two °C bins.
- With bots on the releases, a slow poller (5-60 seconds) would mostly get filled by faster traders after a release. That is adverse selection: getting picked off by someone who knows more than you.

### Gaps
- No measured reaction times (seconds) after any weather release, on any venue.
- The "prilo-weatheredge" blog and its Chicago Midway "88 not 87" story were not found. A search summary mentioned a 12 Oct 2026 write-up where Midway had already recorded 88° against a model bracket of 86-87°. It was not opened, so the settlement could not be confirmed.
- No Reddit or X threads with real data on post-release price moves were found. Our own Kalshi trade history (minute candles around 20:15, 21:15, 23:51 and 04:51 UTC for NYC) could measure this directly.

---

## 6. What a nowcasting bot would need to run, and the legal and terms-of-use concerns

### Takeaway
A minimal bot needs four feeds: (a) METARs polled every 15-30 seconds near :51 past the hour and near the synoptic hours; (b) DSM and CLI text products, polled or pushed, around the known release minutes; (c) optionally, the 1-minute °C feed; and (d) for rain, MRMS every 2 minutes. All the NWS data is free and open for any use. Synoptic's free tier, and MADIS restricted datasets, are not for commercial use. Scraping is unnecessary because official endpoints exist. The main rule-risk is Kalshi's settlement source, now The Weather Company. It has matched NWS CLI almost always so far.

### Cited findings
- aviationweather.gov limits clients to 100 requests a minute and asks for a custom User-Agent. Exceeding limits "can result in blocked access." Source: [aviationweather.gov Data API](https://aviationweather.gov/data/api/)
- api.weather.gov needs a User-Agent with contact details. Its rate limit "is not public" but "allows a generous amount for typical use." Blocks clear "typically within 5 seconds." Source: [NWS API documentation](https://www.weather.gov/documentation/services-web-api)
- NWS data via the API is "open data, free to use for any purpose." Source: [NWS API documentation](https://www.weather.gov/documentation/services-web-api)
- MADIS 1-minute ASOS is public. Other MADIS datasets carry redistribution limits, and companies need a sponsor for restricted data. Sources: [MADIS 1-minute ASOS](https://madis.ncep.noaa.gov/madis_OMO.shtml); [MADIS restrictions](https://madis.ncep.noaa.gov/madis_restrictions.shtml) (search excerpt)
- Synoptic Open Access is non-commercial. Commercial use is paid. Source: [Synoptic pricing](https://synopticdata.com/pricing/) (search excerpt)
- Synoptic says not to build an app solely on HF-ASOS, which had a 27-month outage (Oct 2023-Jan 2026). Source: [Synoptic HF-ASOS docs](https://docs.synopticdata.com/services/high-frequency-asos)
- Kalshi's API, web socket and FIX hosts are in AWS us-east-2 (Ohio). The project's live bot ran in that region while it traded. Source: the project's own network measurements (20 Oct 2026).
- The NEXRAD chunk bucket is in AWS us-east-1. Source: [AWS blog](https://aws.amazon.com/blogs/aws/new-aws-public-data-set-real-time-and-archived-nexrad-weather-data/) (search excerpt)
- Kalshi rules now name The Weather Company as the source. "Preliminary Weather Company data may be subject to rounding and conversion differences." A "Final" status on weather.com/kalshi "does not guarantee data to be error-free." Source: [Kalshi API, KXHIGHNY markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&limit=2)

### Inferences
- **Polling plan (suggested, not tested).** Poll METARs every 15-30 seconds from :50 to :58 past each hour and around 17:51, 23:51, 05:51, 11:51 UTC and the city's midnight-LST METAR. Poll DSM and CLI products every 10-15 seconds in a window around each city's known release minutes. That stays well inside aviationweather.gov's 100 requests a minute for a handful of cities.
- **For speed, a push feed beats polling.** NOAAPort or the Unidata LDM text feed would deliver METAR, DSM and CLI text without polling. Setup cost and access terms were not checked.
- **Servers.** The project's server in Ohio (us-east-2) sat next to Kalshi. The weather data hosts' locations are unknown. Most delay is in the NWS/FAA pipeline (minutes), not the network (milliseconds), so server placement matters little for the weather side.
- **A first cheap step, before building anything.** Use free IEM archives (METAR text and DSMs) to rebuild "best known max at minute t" for past days. Compare it with Kalshi minute prices from our own stored data. This would test, out of sample, whether a gap exists between releases. That means testing on data the rule never saw while being built. It needs a new pre-registration, as the 26 Oct report said.

### Gaps
- No legal opinion found on trading with NWS data. The NWS terms say any purpose. Kalshi's member rules on data sources were not reviewed.
- Polling costs and blocks on tgftp and IEM under heavy use were not tested.
