# Weather favourites test: daily highs fail, rain is too thin to judge

*Oct 26, 2026. Desk test only. Nothing was traded and the live bot was not touched.
Rule frozen and committed before any new data was pulled: `research/weather_favourites/PREREG.md` (commit 4700898).
Scoring code and its 55 tests were committed before any result existed (commit fc319ed).*

## The answer

- **Daily highs fail, clearly.** Heavy favourites (the likely side) lost far more often than their price said.
  The rule lost about 2.5 cents for every dollar bet. The likely range is entirely below zero.
- **Daily rain is "not enough data yet".** Only 110 bets qualified on fresh data. The bar was 1,000.
  At about 4 bets a day, reaching 1,000 would take about 8 months. Even if it passed, it would earn pennies a day.
- **So the favourite rule does not carry over to weather.** Gas is still the only other market where it works.

## What was tested

The rule, as frozen: 6 hours before each market closes, buy the favourite if it costs 90c to 99.9c and the
spread (the gap between the buy and sell price, what it costs to get in) is 3c or less. Each bet is $10. The fill
is 0.4c worse than the quote. Kalshi's taker fee (Kalshi's charge for trading, biggest near 50c) is rounded up.
Each bet is held to the end.

It ran on every settled market in two families:

- **Daily rain:** `KXRAIN`, every city.
- **Daily highs:** all 24 daily high temperature series.

Test data is data nobody on this project had scored before:

- **Older:** Jul 18, 2025 to Jul 17, 2026.
- **Recent:** Sep 30 to Oct 24, 2026.

Jul 18 to Sep 29 had already been looked at in the Oct 18 run. It is shown below, but it does not count.

All 44,262 markets were pulled, and no request failed.

**Settlement check:** Kalshi's settled high matched the weather service's daily climate report on 5,349 of 5,352
city-days. The 3 misses were each 1°F. Rain matched on 851 of 851 city-days.

## Results

"Lost vs priced" compares the real losses with the number the prices predicted.
"Per $10 bet" is the average profit on a $10 bet, after fees.
The range is the 95% range (the range the true number is probably in). It is clustered by date: all bets on one
date count as one, because one weather system moves many cities at once.

| Test data, 6 hours before close | Bets (dates) | Lost vs priced | Per $10 bet (range) | Verdict |
|---|---|---|---|---|
| Daily highs | 1,113 (278) | 48 vs 28.7 | −24.5c (−40.1 to −8.9) | **Fail** |
| Daily highs, Miami + NYC + LA only | 294 (154) | 19 vs 8.0 | −45.5c (−82.5 to −8.4) | Worse |
| Daily rain | 110 (25) | 2 vs 3.3 | +6.3c (−18.4 to +30.9) | **Not enough data** |

For scale, −24.5c per $10 bet means losing about 2.5 cents for every dollar bet.

**The highs failed every pass rule:**

- The profit was negative, and the range was below zero.
- Every price band lost money, from 90–95c down to 99–99.9c.
- Both the older and the recent data lost money.

| Daily highs, by price band | Bets | Lost | Loss rate vs break-even | Per $10 bet |
|---|---|---|---|---|
| 90–95c | 124 | 18 | 14.5% vs 6.9% | −88.4c |
| 95–97c | 109 | 7 | 6.4% vs 4.1% | −28.0c |
| 97–99c | 442 | 16 | 3.6% vs 2.0% | −19.1c |
| 99–99.9c | 438 | 7 | 1.6% vs 0.6% | −11.0c |

"Break-even" is the loss rate at which the bets would just pay for themselves. Every band lost about twice as often
as it could afford.

**The seen period looked better than the test, as usual.** Rain made +17.1c per $10 bet there (332 bets), and highs
made +2.6c (160 bets). Neither held up on data the rule had never seen.

**The 2-hour checkpoint** (reported alongside, and unable to change the verdict) told the same story. Highs lost
14.8c per $10 bet on 237 bets. Rain lost 17.2c on 77 bets.

## Why the highs lose: a lead, not a finding

This was explored after the verdict, so it proves nothing on its own.

On 33 city-days, at least one favourite lost. On **32 of those 33**, the official high came in *above* the
bracket the market favoured at 6 PM. Here are three examples:

- **New York, Oct 13:** "70°F or below" traded at 97c. The official high was 71°F.
- **New York, Jul 14:** "89°F or below" traded at 93c. The official high was 90°F.
- **Chicago, Jun 28:** "81°F or below" traded at 91c. The official high was 82°F.

**Caveat, added later on Oct 26:** this pattern is partly automatic. By 6 PM, the high so far is a floor, so a
favourite like "70°F or below" can only lose upward. The real question is whether the extra degree was already
measured and public at 6 PM. See `Kalshi weather forecast model edge.md`, step 1 of its plan.

This fits the settlement quirk from the research report. The official high is often 1°F above the highest hourly
reading. The true peak shows up only in the airport's "6-hour maximum" report or the overnight climate report. At
6 PM, many traders seem to price off the hourly readings, and they lose that extra degree.

That points the other way from our bot. The edge, if any, is in betting the high comes in a degree warmer than the
crowd thinks, not in buying the crowd's favourite. Testing it would need its own frozen rule, the 6-hour maximum
data, and fresh data. It may also be what faster, quirk-aware traders already do.

## What this means

- **Close daily highs for the favourite rule.** The prereg says a fail ends it.
- **Rain stays open only on paper.** The prereg says to re-score it, unchanged, on new data. At about 4 bets a day,
  that takes months. Even at the seen period's best rate, it would make well under $1 a day at $10 bets.
  My advice is to treat it as closed too.
- **Nothing changes for the live bot.** The 6-week test still runs to Nov 27.

## Files

- Rule: `research/weather_favourites/PREREG.md`
- Code and tests: `research/weather_favourites/` (`fetch.py`, `score.py`, `check.py`, `tests/`)
- Raw data and full output (not committed): `research/weather_favourites/data/` (`score_output.txt`,
  `result.json`, `settlement_check.json`)
