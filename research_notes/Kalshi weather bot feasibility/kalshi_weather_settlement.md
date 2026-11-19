# How Kalshi's daily weather markets settle, and the quirks that matter for a trading model

Research date: 25 Oct 2026. Kalshi API pulls were made about 03:50-04:10 UTC on 26 Oct 2026 (about 23 requests, several hit HTTP 429 "too many requests" and were backed off). Raw API dumps and contract PDFs were saved locally at the time. They are not in the repo.

Plain-words key for terms used throughout:
- **CLI** = the NWS "Daily Climate Report". It is a text bulletin each NWS office issues per station with the day's official high, low and rain.
- **ASOS** = the automated airport weather station (NWS/FAA) that produces the numbers in the CLI.
- **METAR** = the coded airport weather report the station sends, normally once an hour. **SPECI** = an extra, unscheduled METAR sent when weather changes fast.
- **T-group** = the part of an hourly METAR's remarks that gives temperature in tenths of a degree Celsius (for example `T03060222` = 30.6 °C).
- **LST** = local standard time, meaning the clock with no daylight saving shift.
- **DSM** = Daily Summary Message, a short machine bulletin from the station sent just after local midnight with the day's high and low.

---

## 1. What official source does each market settle on, and which exact weather station per city?

### Takeaway
Since mid-August 2026, Kalshi's active daily high and low temperature markets (KXHIGH*, KXLOWT*) and the daily rain market (KXRAIN) settle "according to The Weather Company" at weather.com/kalshi. The rules still name an NWS CLI station code, such as CLINYC for Central Park, as the thing being measured. The Weather Company says it uses the NWS as its main underlying source. So in practice the settled number is still the NWS CLI value for one named airport or park station. The hourly markets for Miami and NYC (KXTEMPMIAH, KXTEMPNYCHS) are different. They settle on a Kalshi-built "Weather Index", which is an average of several airport stations' 1-minute readings delivered by Synoptic Data.

### Cited findings

**Source switch (NWS to The Weather Company)**
- Every active daily high/low series checked (KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHLAX, KXHIGHDEN, KXHIGHAUS, KXHIGHPHIL, all KXHIGHT* and KXLOWT* US cities) lists its settlement source as "The Weather Company", https://weather.com/kalshi. Contract rulebook: GLOBALTEMPERATURE.pdf. Source: [Kalshi API, series list](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)
- Live rule text, KXHIGHNY for 26 Oct 2026: "If the maximum temperature recorded at New York City (CLINYC) for Oct 26, 2026, is greater than 75° fahrenheit according to The Weather Company, then the market resolves to Yes." Source: [Kalshi API, KXHIGHNY markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- Secondary rule text: AccuWeather or Google Weather "may help guide your decision". But the official value is "the maximum/minimum temperature as reported by the Weather Company". Source: [Kalshi API, KXHIGHNY markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- Kalshi market notes said that starting **14 Aug 2026**, the NYC daily-high market would settle on The Weather Company's data instead of the NWS. The partnership was announced publicly on 27 Aug 2026. Sources: [Gizmodo, 27 Aug 2026](https://gizmodo.com/kalshi-teams-up-with-the-weather-co-on-markets-that-are-nearly-impossible-to-insider-trade-2000803871); same 14 Aug date in [WeatherEdge blog, 17 Aug 2026](https://www.prilo-weatheredge.com/blog/kalshi-weather-company-settlement-still-nws)
- Conflict on the date: one third-party guide says the change took effect "as of August 27, 2026". Source: [Turbine blog, updated 21 Oct 2026](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026). The 14 Aug date has two sources and matches the market notes, so it is more likely right.
- Kalshi's notice, as quoted by a vendor blog, said: "The Weather Company utilizes NWS as its primary underlying source." The blog reads this as "the real source didn't change": the number is still the CLI value. This is the blog author's reading, not checked against data. Source: [WeatherEdge blog](https://www.prilo-weatheredge.com/blog/kalshi-weather-company-settlement-still-nws)
- Kalshi says The Weather Company provides "the authoritative observation data used to settle these markets" under "a consistent, documented methodology for each market type". It gives no station or method detail. Source: [Kalshi news, 27 Aug 2026](https://news.kalshi.com/p/kalshi-weather-company-partnership)
- Documents disagree with each other. The GLOBALTEMPERATURE rulebook (filed 8 Dec 2025) names the Source Agencies "in hierarchical order" as the National Weather Service, then the national weather service for the area. It does not name The Weather Company. The live market rules do name The Weather Company. Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf). A third-party guide notes the same lag and advises trusting the market's rules field over the PDF. Source: [Turbine blog](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026)
- Kalshi's help center (last updated 22 Jul 2026, before the switch) still says daily markets "settle based on the final climate report issued by the National Weather Service (NWS)". Source: [Kalshi Help: Weather Markets](https://help.kalshi.com/en/articles/13823837-weather-markets)
- The weather.com/kalshi page is a JavaScript app. Its page title has two parts, "Climate Data Portal" and "Official Climate Reports". It has tabs for Hourly Temps, Daily Climate, Weekly Avg, Degree Days and Snowfall, plus a Domestic/International toggle. The values could not be read with a plain page fetch. Source: [weather.com/kalshi](https://weather.com/kalshi)
- Older, non-KX series (HIGHNY, HIGHCHI, HIGHMIA, HIGHAUS) and a few others (KXHIGHHOU/KXHIGHOU, KXHIGHTEMPDEN) still list the NWS CLI page as their source in series metadata. These are older listings, not the active daily series. Source: [Kalshi API, series list](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)
- History: the original 2021 NYC high contract (NHIGH) named the NWS Daily Climate Report for Central Park, "Yesterday" section, "Maximum" row, as the underlying. Source: [NHIGH.pdf](https://assets.kalshi.com/regulatory/product-certifications/NHIGH.pdf)

**City-to-station table (daily high and low temperature)**

Station codes come from each market's live rule text for the 26 Oct 2026 events. Sources: [Kalshi API, markets closing 05:00Z](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793077199&max_close_ts=1793077201&limit=1000), [06:00Z](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793080799&max_close_ts=1793080801&limit=1000), [07:00Z](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793084399&max_close_ts=1793084401&limit=1000), [08:00Z](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793087999&max_close_ts=1793088001&limit=1000). Station names and ICAO airport codes (the 4-letter "K..." ID) come from the Iowa Environmental Mesonet's CLI site list. Source: [IEM CLI table](https://mesonet.agron.iastate.edu/nws/clitable.php). Several mappings are also confirmed by [Turbine blog](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026).

| Series (high / low) | City | Rule's CLI code | Station (ICAO code) | Watch out for |
|---|---|---|---|---|
| KXHIGHNY / KXLOWTNYC | New York | CLINYC | Central Park (KNYC) | Not LaGuardia or JFK. Polymarket uses LaGuardia. |
| KXHIGHCHI / KXLOWTCHI | Chicago | CLIMDW | Midway (KMDW) | Not O'Hare. Kalshi's Chicago **rain** market uses O'Hare. |
| KXHIGHMIA / KXLOWTMIA | Miami | CLIMIA | Miami Intl Airport (KMIA) | |
| KXHIGHLAX / KXLOWTLAX | Los Angeles | CLILAX | LAX airport (KLAX) | Not downtown LA (USC). |
| KXHIGHDEN / KXLOWTDEN | Denver | CLIDEN | Denver Intl Airport (KDEN) | |
| KXHIGHAUS / KXLOWTAUS | Austin | CLIAUS | Austin-Bergstrom (KAUS) | Not Camp Mabry (KATT). |
| KXHIGHPHIL / KXLOWTPHIL | Philadelphia | CLIPHL | Philadelphia Intl (KPHL) | |
| KXHIGHTBOS / KXLOWTBOS | Boston | CLIBOS | Logan Intl (KBOS) | |
| KXHIGHTATL / KXLOWTATL | Atlanta | CLIATL | Atlanta Intl (KATL) | |
| KXHIGHTDC / KXLOWTDC | Washington DC | CLIDCA | Reagan National (KDCA) | |
| KXHIGHTEWR / KXLOWTEWR | Newark | CLIEWR | Newark Intl (KEWR) | |
| KXHIGHTTTN / KXLOWTTTN | Trenton | CLITTN | Trenton-Mercer (KTTN) | |
| KXHIGHTSDF / KXLOWTSDF | Louisville | CLISDF | Louisville Standiford (KSDF) | |
| KXHIGHTSATX / KXLOWTSATX | San Antonio | CLISAT | San Antonio Intl (KSAT) | |
| KXHIGHTOKC / KXLOWTOKC | Oklahoma City | CLIOKC | Oklahoma City (KOKC) | IEM labels it "(AWOS)". |
| KXHIGHTNOLA / KXLOWTNOLA | New Orleans | CLIMSY | New Orleans airport (KMSY) | |
| KXHIGHTMIN / KXLOWTMIN | Minneapolis | CLIMSP | Minneapolis airport (KMSP) | |
| KXHIGHTHOU / KXLOWTHOU | Houston | CLIHOU | Hobby Airport (KHOU) | Not Bush Intercontinental (IAH). |
| KXHIGHTDAL / KXLOWTDAL | Dallas | CLIDFW | Dallas/Fort Worth airport (KDFW) | Polymarket uses Love Field (KDAL). |
| KXHIGHTPHX / KXLOWTPHX | Phoenix | CLIPHX | Sky Harbor (KPHX) | Arizona has no daylight saving. |
| KXHIGHTSFO / KXLOWTSFO | San Francisco | CLISFO | SFO airport (KSFO) | Airport, not downtown. |
| KXHIGHTSEA / KXLOWTSEA | Seattle | CLISEA | Sea-Tac (KSEA) | |
| KXHIGHTSAN / KXLOWTSAN | San Diego | CLISAN | Lindbergh Field (KSAN) | |
| KXHIGHTLV / KXLOWTLV | Las Vegas | CLILAS | Las Vegas airport (KLAS) | |

- Kalshi also lists international daily high/low series on The Weather Company: London, Paris, Amsterdam, Hong Kong, Shanghai, Tokyo, Seoul, Toronto, Mexico City and others. They use rulebooks GLOBALTEMPERATURECELSIUS or INTERNATIONALTEMPERATURE. Some are in Celsius. Source: [Kalshi API, series list](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)
- The rulebook default: where a city has several stations and Kalshi does not name one, "the designated 'official' or 'primary' station for that location as determined by the Source Agencies shall be used". Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)

**Rain market (KXRAIN, "Will it rain in <city> on <date>?")**
- On 26 Oct 2026 there are 35 city markets. Each rule reads "If the total precipitation at CLI<code> in <city> in <date> is strictly greater than 0 inches, then the market resolves to Yes". The source is The Weather Company. Source: [Kalshi API, KXRAIN markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open) and close-time window pulls above.
- Cities and codes: ABQ (CLIABQ), ATL, AUS, BOS, **Chicago = CLIORD (O'Hare)**, College Station (CLICLL), Columbus (CLICMH), Dallas (CLIDFW), DC (CLIDCA), DEN, Detroit (CLIDTW), EWR, Houston (CLIHOU), Indianapolis (CLIIND), LAX, Lexington (CLILEX), Las Vegas (CLILAS), MIA, Minneapolis (CLIMSP), Milwaukee (CLIMKE), New Orleans (CLIMSY), NYC (CLINYC), OKC, Philadelphia (CLIPHL), PHX, Pittsburgh (CLIPIT), Providence (CLIPVD), San Antonio (CLISAT), SEA, SFO, Springfield (CLISGF), St. Louis (CLISTL), Tampa (CLITPA), Trenton (CLITTN), **West Palm Beach = CLIDJT**. Source: the same API sources.
- "DJT" is the new FAA code for Palm Beach International. The airport was renamed President Donald J. Trump International Airport on 9 July 2026, and the FAA code changed from PBI to DJT. Passenger booking systems switched on 18 Aug 2026. Sources: [AirlineGeeks](https://airlinegeeks.com/?p=100577); [Khaleej Times/AFP](https://www.khaleejtimes.com/world/americas/palm-beach-florida-airport-changes-name-donald-trump)

**Hourly temperature markets (KXTEMPMIAH, KXTEMPNYCHS)**
- KXTEMPMIAH rule: "If the temperature recorded at Miami, FL for Oct 26, 2026 at 12 AM EDT as reported by Synoptic Data, is above 77.99°, then the market resolves to Yes." The value is "calculated in accordance with the Kalshi Weather Index Methodology". NWS Climate Reports "are not authoritative and will not be used". Source: [Kalshi API, KXTEMPMIAH](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTEMPMIAH&status=open)
- Miami index (rulebook dated 12 Aug 2026): five ASOS stations, each weighted 0.20. They are KMIA (Miami Intl), KOPF (Opa-locka), KFLL (Fort Lauderdale-Hollywood), KFXE (Fort Lauderdale Executive) and KPMP (Pompano Beach). Each station's 1-minute record ("KMIA1M" and so on) comes via Synoptic Data's high-frequency ASOS feed. A station can fall back to its own official METAR if the 1-minute reading fails. Source: [MIAWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/MIAWINDEX.pdf)
- NYC index (rulebook dated 9 Sep 2026): eight stations, each weighted 0.125. They are KLGA, KEWR, KTEB, KCDW, KHPN, KFRG, KSMQ and KISP. **Central Park (KNYC) is not one of them.** Source: [NYCWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/NYCWINDEX.pdf)
- How the index works. Each station's reading is adjusted by a fixed offset. Example: Miami KOPF −0.5 °C; NYC KLGA/KEWR/KTEB +1.0 °C, KHPN/KSMQ −1.0 °C. Offsets are re-estimated weekly. The adjusted readings are then averaged. A minute only gets a value if enough stations report: at least 4 of 5 in Miami, at least 7 of 8 in NYC. Values are published to 0.01 °F. Sources: [MIAWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/MIAWINDEX.pdf); [NYCWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/NYCWINDEX.pdf)
- The live index can be read at `GET /live_data/weather/{city}` (example city: `miami`). The spec lists no authentication. It returns minute points with value, status (normal/degraded) and number of contributing stations. A `detailed=true` flag adds each station's reading. Source: [Kalshi API docs: Get Weather Index](https://docs.kalshi.com/api-reference/live-data/get-weather-index)
- An older NYC hourly series, KXTEMPNYCH, settled on "The Weather Company (for coordinates KNYC)", that is, Central Park. The newest market returned was for 10 Sep 2026 and is finalized, so it looks replaced by KXTEMPNYCHS. Source: [Kalshi API, KXTEMPNYCH](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTEMPNYCH&limit=3). The July 2026 help center described hourly markets as settling on The Weather Company's reading for a named station, for example KORD for Chicago. Source: [Kalshi Help](https://help.kalshi.com/en/articles/13823837-weather-markets)

### Inferences
- For KXHIGH/KXLOWT, the model's target should be the NWS CLI daily max or min, in whole °F, for the station in the table. The Weather Company is the official publisher, but its stated main input is the NWS. Any gap between weather.com/kalshi and the NWS CLI is a small but real risk. No such gaps were documented.
- Chicago and Dallas show the main trap. The same city name maps to different stations across markets and venues. Chicago temperature uses Midway, but Chicago rain uses O'Hare, and Polymarket uses O'Hare for temperature.
- The hourly NYC and Miami markets are a different product. They track a multi-station average, not one station. A single-station forecast model will be biased for them unless it models the whole index.

### Gaps
- Could not read weather.com/kalshi data (JavaScript only). So it is unconfirmed whether its "Daily Climate" values always equal the NWS CLI, or how it labels preliminary versus final values.
- Kalshi's exact 14 Aug 2026 notice text was seen only as quoted by a vendor blog.
- KXTEMPNYCHS live rule text was not pulled. The API returned 429 twice, then 0 open markets. Its rules are inferred from the NYCWINDEX rulebook.

---

## 2. What time window is a "day", when does trading stop, and how and when does it settle? What if the report is late, revised, or missing?

### Takeaway
The "day" is midnight to midnight **local standard time**. During daylight saving that means 1:00 AM to 12:59 AM local clock time, so the climate day runs into the first hour of the next calendar day. The API close time matches this: 05:00 UTC, which is 1:00 AM EDT. The rule prose says "11:59 PM local time", which conflicts. Daily markets settle off the first official report after the day ends. In practice that is the CLI issued between 12:30 and 5:00 AM local, and Kalshi settles at the first 7:00 or 8:00 AM ET after it. Example: NYC 24 Oct settled at 7:18 AM EDT on 25 Oct. Revisions after expiration do not count. Missing temperature data means Kalshi picks a "last fair price". Missing rain data counts as 0 inches, which means No.

### Cited findings

**Day window (local standard time)**
- The CLI covers midnight to midnight local standard time: "during daylight saving time, this period is from 1 AM to 1 AM local daylight time!" Source: [IEM CLI table](https://mesonet.agron.iastate.edu/nws/clitable.php)
- Kalshi's help center says the same. During daylight saving the high is "recorded between 1:00 AM and 12:59 AM local time the following day". Source: [Kalshi Help](https://help.kalshi.com/en/articles/13823837-weather-markets)
- The NWS LA office says the times of the daily high and low are "always in local standard time (which means it is an hour earlier than daylight saving time)". This is a national standard for climate reports. Source: [NWS Los Angeles, ASOS temperature](https://www.weather.gov/lox/asostemperature)
- ASOS daily extremes are "reported between 0000 LST and 2359 LST". Source: [NWS Phoenix, High-res ASOS](https://www.weather.gov/psr/HiResASOS)
- Kalshi's LOCALTEMPERATURE rulebook (5 Mar 2026) writes this in: "All time periods are interpreted in the local standard time of <area> unless otherwise specified. The end of <time period> is defined as 11:59:59 PM local standard time". Source: [LOCALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/LOCALTEMPERATURE.pdf). The GLOBALTEMPERATURE rulebook, which the active KXHIGH series point to, does not mention LST. Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)
- The live NYC CLI header shows LST in use: "VALID TODAY AS OF 0400 PM LOCAL TIME", with "(LST)" in the column header, while sunrise and sunset are given in EDT. Source: [NWS OKX CLI NYC, 25 Oct 2026](https://forecast.weather.gov/product.php?site=OKX&product=CLI&issuedby=NYC)

**Listing, last trading time, close**
- KXHIGHNY 26 Oct 2026 markets: open 25 Oct 14:00Z (10 AM EDT the day before); `close_time` 27 Oct 05:00Z (1:00 AM EDT, which is midnight EST); `expected_expiration_time` 27 Oct 19:00Z; `latest_expiration_time` 2 Nov 14:00Z (one week later); `settlement_timer_seconds` 300. Source: [Kalshi API, KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- The rule prose for the same market: "The Last Trading Time will be 11:59 PM local time on October 26, 2026 regardless of any data releases or events occurring. Expiration will occur on the sooner of the first 7:00 or 8:00 AM ET following the release of the data for October 26, 2026, or one week after October 26, 2026." Source: [Kalshi API, KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- Close times step by time zone, each at local standard midnight: Eastern cities 05:00Z, Central 06:00Z, Mountain 07:00Z (Denver; Phoenix too, which is always on MST), Pacific 08:00Z. Source: [Kalshi API close-time windows](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793077199&max_close_ts=1793077201&limit=1000)
- A third-party guide also records the KXHIGHNY close as 1:00 AM ET the day after, and says to trust the API fields over prose. Source: [Turbine blog](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026)
- KXRAIN 26 Oct markets: open 25 Oct 09:10Z; close at local standard midnight (same 05/06/07/08Z pattern); `can_close_early` true, "This market will close and expire early if the event occurs"; `settlement_timer_seconds` 1800. Source: [Kalshi API, KXRAIN](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)
- KXTEMPMIAH, the hourly market for 12 AM EDT 26 Oct: opens 03:00Z, closes 04:00Z (the settlement minute), expected expiration 04:05Z, `settlement_timer_seconds` 3600. Hourly times are on the local **daylight** clock ("12am EDT"). Source: [Kalshi API, KXTEMPMIAH](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTEMPMIAH&status=open)

**When the data comes out and when Kalshi settles**
- The CLI "is issued at least twice daily". "The first mandatory issuance will be between 12:30 a.m. and 5:00 a.m. local time" and covers the previous day. The second is in the late afternoon or early evening, "typically between 3:00 p.m. and 5:30 p.m. local time", and covers the current day so far. Source: [NWS Burlington product descriptions](https://weather.gov/btv/product_descriptions)
- The ASOS sends the precise high and low for the previous day "at around 1am". Source: [NWS Los Angeles](https://www.weather.gov/lox/asostemperature)
- Observed: all six KXHIGHNY 24 Oct markets settled at 25 Oct 11:18:27Z (7:18 AM EDT), with `expiration_value` 60.00. The "59° to 60°" bracket won. Source: [Kalshi API, KXHIGHNY-26OCT24](https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=KXHIGHNY-26OCT24&limit=20)
- Hourly markets settle "approximately 25-35 minutes after the market closes". Source: [Kalshi Help](https://help.kalshi.com/en/articles/13823837-weather-markets)

**Preliminary versus final, revisions, errors**
- Current KXHIGH rule: "Preliminary Weather Company data may be subject to rounding and conversion differences from the final reported value." If Kalshi finds "a material error in the initial non-preliminary publication", expiration "may be held until the publication of a non-materially-erroneous data revision or until the Expiration Date, whichever comes first. If no data is available at the end of this period, all markets will resolve to the last fair price determined by Kalshi." Also: "a status of 'Final' on weather.com/kalshi is provided for convenience only, and does not guarantee data to be error-free". Source: [Kalshi API, KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- Rulebook: "Only the first official non-preliminary report published by the Source Agencies that includes the relevant data will be used for resolution. Revisions after the Expiration Date are not included". "Contract resolution is based on the full precision reported by the Source Agency." Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)
- LOCALTEMPERATURE rulebook: the first release counts "except where that data is retracted, corrected, or identified as erroneous by the Source Agency or the Exchange prior to the Expiration Date". Corrections made after expiration "shall not be considered". If the primary source is missing, Kalshi "may use data from the next Source Agency in the hierarchy". Source: [LOCALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/LOCALTEMPERATURE.pdf)
- Before the switch, Kalshi warned that settlement "may be delayed" if (a) the CLI high "is not consistent with 6-hr or 24-hr highs reported by METAR", or (b) the final CLI high "is lower than previous preliminary report". Source: [Kalshi Help](https://help.kalshi.com/en/articles/13823837-weather-markets)
- Under the old 2021 NHIGH contract, revisions made between the last trading time and expiration "may be taken into account". Revisions after expiration were ignored. Source: [NHIGH.pdf](https://assets.kalshi.com/regulatory/product-certifications/NHIGH.pdf)
- The CLI shows missing data as "MM" and trace rain as "T". Source: [NWS OKX CLI NYC](https://forecast.weather.gov/product.php?site=OKX&product=CLI&issuedby=NYC)

**Missing data**
- Temperature: "If no data is available for <time period> by the Expiration Date, all strikes shall resolve to the last fair price as determined in the sole discretion of the Exchange." Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)
- Rain: "'Trace' amounts (T) and missing daily precipitation values are counted as 0 inches." Sources: [Kalshi API, KXRAIN](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open); same in [RAINGLOBALPERIOD.pdf](https://assets.kalshi.com/regulatory/product-certifications/RAINGLOBALPERIOD.pdf) (filed 4 Jun 2026)
- Hourly index: if no valid index reading exists within the 60 minutes before the settlement time, the outcome "cannot be determined" and goes to Kalshi's review process (Rule 7.1). Source: [MIAWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/MIAWINDEX.pdf)

### Inferences
- During daylight saving (now until early November), the KXHIGH/KXLOWT climate day includes the first hour after calendar midnight. This matters most for **lows**. A cold front arriving at 12:30 AM EDT sets the previous day's low. A model built on calendar-day hourly data will mislabel those hours.
- Trading runs right to the end of the climate day (1:00 AM EDT), so the last hour can still move a low market.
- The afternoon CLI ("VALID TODAY AS OF 0400 PM") is not the settlement number. The settling report is the overnight one. A model or bot must not treat the afternoon report as final.
- Missing rain data counts as 0, which means "No" wins. So a station outage favours No holders on rain, while it sends temperature markets to a judgment-call price.

### Gaps
- No public record was found of a KXHIGH market held for a "material error" or resolved to "last fair price" after the switch.
- How fast weather.com/kalshi posts the overnight value compared with the NWS CLI is unknown.

---

## 3. How are the temperature brackets built, and how is the rain market defined?

### Takeaway
Each city-day for highs and lows has six contracts: four 2-degree bins (both ends included, whole °F) plus an "X or below" and a "Y or above" tail. Rain is a single Yes/No per city: Yes if total precipitation is strictly above 0 inches. In practice that means at least 0.01 inch, because a trace counts as 0. Melted snow and sleet count. The rain market closes early as soon as rain happens. Hourly markets are a ladder of "above X.99°" thresholds.

### Cited findings
- KXHIGHNY 26 Oct 2026 has six markets: "67° or below" (strike_type less, cap 68), "68° to 69°", "70° to 71°", "72° to 73°", "74° to 75°" (strike_type between, e.g. floor 74 / cap 75), and "76° or above" (strike_type greater, floor 75). Source: [Kalshi API, KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- KXLOWTNYC 26 Oct 2026 uses the same layout: "43° or below", 44-45, 46-47, 48-49, 50-51, "52° or above". Source: [Kalshi API, markets closing 05:00Z](https://api.elections.kalshi.com/trade-api/v2/markets?min_close_ts=1793077199&max_close_ts=1793077201&limit=1000)
- Rulebook meanings: "'Above' means greater than (>) ... 'between' means within an inclusive range (≥ lower bound and ≤ upper bound)". Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)
- Ladders are in whole degrees. "Above 70°" is shown as "71° or above". Source: [Turbine blog](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026)
- Prices run from $0.01 to $0.99 in 1-cent steps ("linear_cent"). The position accountability level is $25,000 per strike per member. That is the size above which Kalshi can ask questions about a position. Sources: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf); [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- Rain rule: "strictly greater than 0 inches" (strike_type greater, floor_strike 0). Trace and missing values count as 0. Source: [Kalshi API, KXRAIN](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)
- Rain rulebook: "'Total precipitation' means the sum of all liquid-equivalent rainfall and melted frozen precipitation (including snow, sleet, and hail)". "Forecast or projected precipitation values do not count". "Corrections shall not supersede earlier values, unless initial values released are preliminary". The latest expiration is one week after the period ends. Source: [RAINGLOBALPERIOD.pdf](https://assets.kalshi.com/regulatory/product-certifications/RAINGLOBALPERIOD.pdf)
- Hourly Miami ladder for 12 AM EDT 26 Oct: ten "above" strikes from 68.99 to 77.99 ("69° or above" up to "78° or above"). Because the index has 0.01 °F precision, "above 77.99" means 78.00 or higher. Source: [Kalshi API, KXTEMPMIAH](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTEMPMIAH&status=open)
- For hourly "at" contracts, the settling value is "the canonical Index observation with the greatest event time t such that t is at or before the settlement time and no more than 60 minutes before". It is set no earlier than 5 minutes after the settlement time. Source: [MIAWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/MIAWINDEX.pdf)

### Inferences
- Bin edges at whole degrees plus the CLI's whole-°F rounding mean a true peak of 69.4 °F and one of 69.6 °F land in different bins (69 vs 70). The rounding step described in Q4 drives this.
- The rain "Yes" side has no value left once rain is recorded, because the market closes early. A "known Yes" can't be traded after the fact. The "No" side is only certain once the climate day ends.

### Gaps
- The exact trigger and timing of the rain market's early close was not documented. It is unknown whether it uses a preliminary METAR rain amount, a weather.com/kalshi update, or a manual action. A settled KXRAIN event pull was rate-limited (HTTP 429).
- Bracket widths for other cities were not checked one by one. The NYC high and NYC low both use 2-degree bins.

---

## 4. Rounding and measurement quirks: why the official number can differ from apps and hourly reports

### Takeaway
ASOS works internally in **whole °F**. It averages 1-minute readings, and the official daily max and min come from those internal averages, not from the hourly reports. The routine 5-minute reports carry only **whole °C**, which is about a 1.8 °F step, so converting them back to °F can show a value a degree too high. The hourly METAR T-group (tenths of °C) is precise, but it is only a snapshot near :51-:53 past the hour. Brief peaks between hours show up only in the 6-hour max group, the 24-hour group or the DSM. That is why the CLI max can be higher than every hourly reading. A real June 2026 Chicago Midway case caught traders out this way.

### Cited findings
- "it is observed every 10 seconds in tenths of a degree Fahrenheit", "averaged and stored internally as whole degrees Fahrenheit every minute", and "the one minute observations are aggregated into rolling 5-minute averages (stored each minute)". Source: [NWS Phoenix, High-res ASOS](https://www.weather.gov/psr/HiResASOS)
- "The daily high/low temperatures are the highest/lowest of the rolling 5-minute averages", "with the time attributed to the last occurrence". Source: [NWS Phoenix](https://www.weather.gov/psr/HiResASOS)
- Conflict on averaging length: the Iowa Environmental Mesonet says official temperatures for daily max/min summaries are "2 minute averages of 2-5 second sampled data", in whole °F. Source: [IEM, "Wagering on ASOS Temperatures", Dec 2024](https://www.mesonet.agron.iastate.edu/onsite/news.phtml?id=1469). Both sources agree the daily extremes come from internal averaged whole-°F values.
- Hourly METARs carry temperature "in both whole degrees Centigrade and as tenths of a degree Centigrade". 5-minute METARs are "stored only with temperature in whole degrees Centigrade", "converted from the rolling 5-minute average in whole degrees Fahrenheit". Source: [NWS Phoenix](https://www.weather.gov/psr/HiResASOS)
- Worked example: a 5-minute average peak of 116 °F "equates to 46.7 °C and rounds to 47 °C". Converted back, that is 117 °F, but "these are not valid temperatures as they are erroneously high due to conversion and rounding processes". The real high is 116 °F. Source: [NWS Phoenix](https://www.weather.gov/psr/HiResASOS)
- The 5-minute report "only has a precision to the nearest whole degree Celsius and may not match what is being tracked internally". Highs and lows "could also occur in between the 5-minute observations". The hourly report at LAX goes out at 53 minutes past the hour. Source: [NWS Los Angeles](https://www.weather.gov/lox/asostemperature)
- The hourly report time is set between :50 and :59. The temperature is labelled as the top of the hour but was taken a few minutes earlier. SPECI reports in active weather can cause the routine report to be skipped. The DSM "usually arrives before the CLI" with a reliable max and min. CLI and CF6 get "some manual quality control in some instances". Source: [IEM news 1469](https://www.mesonet.agron.iastate.edu/onsite/news.phtml?id=1469)
- IEM's own audit tool leaves out high-frequency MADIS 1-minute data, because it is in whole °C and doesn't use the standard 2-minute averaging. It notes "It is sometimes vague what happens with the METAR report that occurs just before midnight local". Source: [IEM CLI audit](https://mesonet.agron.iastate.edu/nws/cli-audit/)
- METAR remark groups: the 6-hour max group `1snTxTxTx` (tenths °C) appears in the 00, 06, 12 and 18 UTC reports. The 24-hour group `4snTxTxTxsnTnTnTn` carries both max and min and appears in the report at midnight local standard time. Sources: [Bemidji State METAR key](https://cs.bemidjistate.edu/fneville/cs3507DB/windMetadata.htm); [NWS METAR decode key](https://www.weather.gov/media/wrh/mesowest/metar_decode_key.pdf)

**A real case where traders got caught: Chicago Midway, 9 Jun 2026** (vendor blog, treat with care)
- KXHIGHCHI settled in the 88-89 bin, while a widely seen report showed 87 °F. The afternoon CLI ("VALID TODAY AS OF 0400 PM LOCAL TIME") had a max of 87 at 2:59 PM. The 6:53 PM METAR remarks had `T03060222 10311`. That decodes to an hourly reading of 30.6 °C (87.0 °F) and a 6-hour max of 31.1 °C (88 °F). The final CLI showed 88. The blog's lesson: check the "VALID AS OF" stamp, and use the 6-hour max group to catch peaks between hours. Source: [WeatherEdge, 10 Jun 2026](https://www.prilo-weatheredge.com/blog/why-chicago-midway-settled-88-not-87)
- The same blog has a post titled "Houston Said 93. The Bay Breeze Said 92." (25 Jun 2026) about another surprise settlement. Not read in full. Source: [WeatherEdge blog index](https://www.prilo-weatheredge.com/blog)

**Conflicting third-party claim**
- One site (clilax.com, which says it is not affiliated with any exchange or agency) says the ASOS sensor "reports in tenths of a degree Celsius", converted to °F and rounded half-up (17.8 °C gives 64 °F). It also says public apps can inflate readings through repeated rounding (77.6 °F shown as 78.8 °F, while the official value is 78 °F). Source: [clilax.com](https://www.clilax.com/). This conflicts with the NWS Phoenix page, which says ASOS stores whole °F internally. Prefer the NWS source.

**Other measurement risk**
- Single-station settlement can be tampered with. In April 2026, Météo-France filed a criminal complaint after suspicious spikes at its Paris-CDG sensor on 6 and 15 April. On 15 April the reading reportedly jumped from about 16 °C to 22 °C at 9:30 PM and fell back within about 30 minutes. One Polymarket account reportedly turned about $119 into about $21,398. Polymarket then moved Paris settlement to Le Bourget. Sources: [NPR via St. Louis Public Radio, 23 Apr 2026](https://www.stlpr.org/npr/2026-04-23/french-police-probe-suspected-weather-device-tampering-after-odd-polymarket-bet); [DL News](https://dlnews.com/articles/defi/french-meteorological-agency-is-investigating-tampering-amid-big-polymarket-bets/)

### Inferences
- Because ASOS stores whole °F, the hourly tenths-°C T-group should map back to exactly one whole °F value. One °F is 0.56 °C, which is bigger than the 0.1 °C step. Example: 88 °F = 31.1 °C, 87 °F = 30.6 °C, matching the Chicago METAR. This is an inference from the NWS Phoenix description. IEM warns the T-group is not fully documented and has seen it differ from the whole-°C body value. Test it on history before relying on it.
- The best real-time view of "the official max so far" is the larger of: (a) every hourly T-group converted to °F, (b) the 6-hour max groups at 00/06/12/18Z, and (c) the 24-hour group and DSM after LST midnight. Whole-°C 5-minute or 1-minute values should be treated only as a range of about ±1 °F.
- Weather apps (Google, Apple, AccuWeather) often use other stations, model blends, or converted whole-°C values. Gaps of 1-2 °F against the CLI should be expected.

### Gaps
- Could not find the official ASOS User's Guide text that settles the 2-minute versus 5-minute question for the daily max and min.
- No source measured how often the CLI max beats the highest hourly T-group, or by how much. That would need a backtest on IEM METAR plus CLI archives.
- Reddit and X threads about settlement disputes did not turn up in search. The only "caught out" case found is the vendor-blog Chicago example.

---

## 5. Can intraday observations reveal the answer before the market closes, and how fast is that data public?

### Takeaway
Often yes for highs, and markets already price it in. By late evening the 25 Oct NYC winning bin was trading at 99-100 cents after the 4 PM CLI showed 64 °F. Hourly METARs are free and public within a few minutes. The 1-minute high-frequency ASOS feed arrives in 2-5 minutes when it works, but it is whole °C, experimental, and was down from October 2023 to January 2026. The archived 1-minute data from NCEI is 12-36 hours late. Rain "Yes" can't be traded after the fact, because the market closes early when rain happens.

### Cited findings
- Example: around 23:52 EDT on 25 Oct 2026, the KXHIGHNY 25 Oct "64° to 65°" bin was bid 0.99 / asked 1.00. Every other bin was at 0.00-0.02. Source: [Kalshi API, KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open). The 4:33 PM EDT CLI that day showed a max of 64 at 2:59 PM. Source: [NWS OKX CLI NYC](https://forecast.weather.gov/product.php?site=OKX&product=CLI&issuedby=NYC)
- The KXHIGH rules say the last trading time holds "regardless of any data releases or events occurring". There is no early close when the high is already known. Source: [Kalshi API, KXHIGHNY](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY&status=open)
- Standard METAR/SPECI reports reach Synoptic's platform within about 3 minutes of sampling in most conditions. The 5-minute HFMETAR product is slower, 5-9 minutes or more. Source: [Synoptic docs: ASOS/AWOS METAR](https://docs.synopticdata.com/services/asos-awos-united-states-metar) (summary via search; page not fetched in full)
- High-frequency (1-minute) ASOS: "usually arrives with between 2 and 5 minutes latency". "Temperatures are expressed in whole degrees celsius". It comes "via NOAA's MADIS service". It "was unavailable from its source between October 2023 and January 2026". It is "considered experimental", and outages of "brief to several-day" are "not uncommon". Source: [Synoptic docs: High-frequency ASOS](https://docs.synopticdata.com/services/high-frequency-asos)
- NCEI's 1-minute dataset is whole °F, "does not use two minute averaging", and arrives 12-36 hours late. Daily max and min computed from it by hand won't match the official values. Source: [IEM news 1469](https://www.mesonet.agron.iastate.edu/onsite/news.phtml?id=1469)
- The NWS Phoenix high-res ASOS page is "updated every 5-10 minutes" and labelled preliminary and experimental. Source: [NWS Phoenix](https://www.weather.gov/psr/HiResASOS)
- A vendor tested one-minute observations against seven cities over one year. It found they predicted the settled high about as often as the precise hourly feed, sometimes more often. It argued no single feed is an edge by itself. Source: [WeatherEdge, 7 Jul 2026](https://www.prilo-weatheredge.com/blog/faster-weather-data-omo-not-the-edge)
- For the Kalshi hourly index, any reading received more than 300 seconds after its minute is excluded. The live index is public at `/live_data/weather/{city}`. Sources: [MIAWINDEX.pdf](https://assets.kalshi.com/regulatory/product-certifications/MIAWINDEX.pdf); [Kalshi API docs](https://docs.kalshi.com/api-reference/live-data/get-weather-index)

### Inferences
- For daily highs, the answer is usually settled by late afternoon local time, and the market follows the public hourly METAR within minutes. A slow bot won't find free money in a "known" high. Any edge would have to come from (a) the rare late peaks caught only by the 6-hour or 24-hour groups, (b) the whole-degree rounding edge cases, or (c) forecasting before the peak.
- Lows are harder to call early. They often happen near dawn, but can be set late at night or in the 12-1 AM EDT hour during daylight saving.
- For the Kalshi hourly index markets, the index itself is public through Kalshi's API in near real time. The settling minute must be at or before the settlement time, and the market closes at that time. So "knowing the answer" in advance is limited to the last few minutes' trend.

### Gaps
- The exact public latency of METARs on aviationweather.gov (which Polymarket uses) or api.weather.gov was not measured here.
- No source covered how fast the overnight CLI appears on weather.com/kalshi compared with NWS servers.

---

## 6. Fees: does the normal taker fee apply? Any maker fees, rebates, or fee-free weather promotions?

### Takeaway
Yes, the normal formula applies. All 458 Kalshi "Climate and Weather" series carry fee type "quadratic" with multiplier 1. That is the standard taker fee of 0.07 × contracts × price × (1 − price), rounded up, so it is biggest near 50 cents. No weather-specific maker fee, rebate or promotion was found.

### Cited findings
- Every series in the Climate and Weather category (458 series, including all KXHIGH*, KXLOW*, KXTEMP*, KXRAIN*) returns `fee_type: quadratic`, `fee_multiplier: 1`. Source: [Kalshi API, series list](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)
- Taker fee formula: 0.07 × contracts × P × (1 − P), rounded up, where P is the price in dollars. The daily-high series list it with multiplier 1. Sources: [Turbine blog](https://www.turbinefi.com/blog/how-to-trade-kalshi-weather-markets-2026); formula also given in [Kalshi fee schedule PDF (via search)](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- Maker fees, where they apply, use 0.0175 in place of 0.07. Most markets charge no maker fee. Cancelling a resting order is free. Sources: [Kalshi fee schedule (via search)](https://kalshi.com/docs/kalshi-fee-schedule.pdf); [QuantVPS](https://www.quantvps.com/blog/kalshi-fees-explained)
- The rulebooks say only that members "will be charged fees in accordance with Rule 3.13", in amounts that "may be revised from time to time". Source: [GLOBALTEMPERATURE.pdf](https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf)
- The project's own check (25 Oct 2026) found that Kalshi fees round up to $0.0001 per order, not to the cent. Source: the project's own measurements.

### Inferences
- At a 50-cent price the taker fee is about 1.75 cents per contract. At 90 or 10 cents it is about 0.63 cents. Favourite-buying in weather costs the same as in crypto.
- The "quadratic" label (not a maker-fee variant) suggests resting orders pay no fee on weather series. This could not be confirmed on the fee schedule page, because it returned HTTP 429.

### Gaps
- The official fee schedule PDF could not be fetched directly (HTTP 429). It is unconfirmed whether any weather series is on Kalshi's maker-fee list or in a liquidity incentive programme.
- No fee-free weather promotion was found in 2026 sources.

---

## 7. For comparison: how Polymarket's weather markets settle (as of Oct 2026)

### Takeaway
Polymarket runs daily highest and lowest temperature markets for about 50 cities. As of October 2026 they settle on **raw hourly METAR T-groups** from the Aviation Weather Center for one airport. They ignore SPECI reports and the 6-hour max groups. Days are defined on the **local clock including daylight saving**, not LST. The airports often differ from Kalshi's (NYC LaGuardia vs Kalshi's Central Park; Chicago O'Hare vs Midway; Dallas Love Field vs DFW). This weather market showed a zero fee rate.

### Cited findings
- Polymarket NYC 26 Oct 2026 rule: resolves to "the highest temperature reported in the hourly temperature remark of any routine (METAR) observation for LaGuardia Airport (KLGA) on that date, in tenths of a degree Celsius as reported. A report whose line begins with SPECI is a special observation and does not count." If the T-group is missing, the whole-°C body value is used. Source: [Polymarket Gamma API, NYC 26 Oct](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-26-2026)
- Conversion: °F = °C × 9/5 + 32, rounded to the nearest whole degree, with exact halves rounded up. Examples: 18.3 °C → 64.94 → 65 °F; 17.8 °C → 64.04 → 64 °F. Day: "An observation counts if its time stamp, converted to the station's local time (including any daylight-saving shift in effect), falls on the observation date." Source: [Polymarket Gamma API](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-26-2026)
- Timing and backups: the market resolves at the first METAR of the following day, or by 11:59 PM ET the next day. Corrections count until the next day's first data point. If no AWC data exists, the Weather Underground Daily Observations table is used. If neither has data, the market resolves to the lowest bin. Clearly wrong or tampered data can hold the market open up to 7 days. Source: [Polymarket Gamma API](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-26-2026)
- Bins: 11 outcomes in 2 °F steps with tails (e.g. "59°F or below" … "78°F or higher"). Price tick is 0.001. Fee schedule `{rate: 0, takerOnly: true, rebateRate: 0}`, `feeType: zero_fees`. Source: [Polymarket Gamma API](https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-26-2026)
- US airports used in open markets on 25-26 Oct 2026: NYC KLGA, Miami KMIA, Chicago KORD, Dallas KDAL, Houston KHOU, Atlanta KATL, Austin KAUS, Denver KDEN, Seattle KSEA, Los Angeles KLAX, San Francisco KSFO. Abroad: London City (EGLC), Paris Le Bourget (LFPB), Toronto (CYYZ), Tokyo Haneda (RJTT), Seoul Incheon (RKSI) and others. A few Chinese cities (Jinan, Zhengzhou) still use Weather Underground history pages. Source: [Polymarket Gamma API, daily-temperature tag](https://gamma-api.polymarket.com/events?tag_slug=daily-temperature&active=true&closed=false&limit=200)
- Rules changed over 2026. Earlier NYC markets settled on Weather Underground's KLGA daily history page in whole °F, per mirror sites. Sources: [accrue.com mirror](https://accrue.com/e/highest-temperature-in-nyc-on-may-27-2026); [polyguana mirror](https://polyguana.com/market/3614350). Paris moved from CDG to Le Bourget after the April 2026 tampering complaint. Source: [NPR via STLPR](https://www.stlpr.org/npr/2026-04-23/french-police-probe-suspected-weather-device-tampering-after-odd-polymarket-bet)

### Inferences
- Polymarket's NYC high equals the highest hourly T-group at LaGuardia. It leaves out peaks between hours that the CLI catches. So for the same station it would come out equal to or below the CLI max. Kalshi's NYC market is a different station anyway (Central Park), so the two venues are not the same bet, and cross-venue arbitrage is not exact.
- Polymarket's day uses the daylight clock (midnight to midnight EDT), while Kalshi's uses LST (1 AM to 1 AM EDT). For lows, the two can differ on the same station.

### Gaps
- Polymarket's own rules page was read through its public Gamma API, not the website. The fee fields are inconsistent (`feesEnabled: true` with `rate: 0`), so the zero-fee reading should be checked.
- No check was made of whether Polymarket US (the US-regulated venue) lists weather markets.
