# The favourite rule on daily rain and daily highs: what is being tested, written before any new result is read

*Oct 25, 2026. Written and committed before any new weather price is fetched, for the same reason as
`../kalshi_15min/FILTER_SEARCH_PREREG.md` and `../opening_price/PREREG.md`: once a number has been seen, a rule
chosen after it is a lead, not a finding. Background: `reports/Kalshi weather bot feasibility.md`.*

## The question

**Late in the climate day, do favourites (the likely side) priced 90c or more win more often than their price
says, after the taker fee and the spread, on Kalshi's daily rain market and its daily high temperature markets?**

Two market families, judged separately:

- **Rain:** `KXRAIN` ("Where will it rain on <date>?"), every city in it.
- **Highs:** the 24 daily high temperature series open on Oct 25, 2026: `KXHIGHAUS`, `KXHIGHCHI`, `KXHIGHDEN`,
  `KXHIGHLAX`, `KXHIGHMIA`, `KXHIGHNY`, `KXHIGHPHIL`, `KXHIGHTATL`, `KXHIGHTBOS`, `KXHIGHTDAL`, `KXHIGHTDC`,
  `KXHIGHTEWR`, `KXHIGHTHOU`, `KXHIGHTLV`, `KXHIGHTMIN`, `KXHIGHTNOLA`, `KXHIGHTOKC`, `KXHIGHTPHX`, `KXHIGHTSAN`,
  `KXHIGHTSATX`, `KXHIGHTSDF`, `KXHIGHTSEA`, `KXHIGHTSFO`, `KXHIGHTTTN`.

Out of scope: daily lows, hourly temperature, monthly rain and snow, ski, storm and climate series (thin, wide
spreads), Polymarket, and any forecast model or weather-observation filter.

## What has already been seen, and so cannot count

The Oct 18 other-markets run (`../kalshi_15min/other_markets.py`, output in `other_markets_output.txt`) scored
this same kind of rule on every market that closed Jul 18 to Sep 29, 2026. I read these rows before writing
this file (profit per $10 bet, liquid bets only, 95% range clustered by close time):

| Rows already seen | Bets | Profit per $10 bet |
|---|---|---|
| All daily weather, 6 hours before close | 1,306 | +5.3c (−2.9 to +13.5) |
| All daily weather, 2 hours before close | 830 | +7.5c (−1.8 to +16.7) |
| All daily weather, 1 hour before close | 649 | +4.5c (−7.4 to +16.4) |
| `KXRAIN`, 6 hours before close | 312 | +16.7c (+7.1 to +26.2) |
| `KXRAIN`, 12 hours before close | 374 | +8.8c (−4.6 to +22.2) |

"All daily weather, 2 hours" failed that run's own pass test on its September half (343 bets, −1.2c).

So **climate dates Jul 18 to Sep 29, 2026 are the training half.** They are fetched again and reported, labelled
"seen", and never count toward the verdict. The 6-hour checkpoint below was picked partly because it looked best
for rain in those seen rows. That is a normal train-then-test choice, and the test data below has never been
scored by anyone on this project.

Those seen rows also have a flaw this test fixes. A rain market closes early once rain falls, so it stops quoting.
The old code carried its last quote forward, so it could "bet" on a market that had already closed.

## The test data: never scored

By **climate date** (the date in the event ticker, e.g. `KXHIGHNY-26OCT24` is Oct 24):

| Part | Highs | Rain |
|---|---|---|
| Older | Jul 18, 2025 to Jul 17, 2026 (12 months, every season once) | Jul 15 to Jul 17, 2026 (the series starts Jul 15) |
| Recent | Sep 30 to the last settled date, about Oct 24, 2026 | Same |

The verdict is read once, on Older and Recent pooled.

## The rule, frozen

For every settled market in the family:

1. **Checkpoint.** `T = close_time − 6 hours` (primary) and `close_time − 2 hours` (secondary). `close_time` is
   the end of the climate day for these markets (checked Oct 25: `KXHIGHNY` and `KXRAIN` close at local
   standard midnight; the March 2026 markets closed at 11:59 PM local clock time).
2. **Open at T.** The market must still be quoting after T: at least one hourly candle ending after T. A rain
   market that closed early before T is skipped.
3. **Quote.** The YES bid and YES ask from the last hourly candle ending at or before T (candle close values).
   Skip if the bid is 0, the ask is $1, or either is missing.
4. **Favourite.** YES costs the ask; NO costs 1 − bid. The favourite is the dearer side. Bet only if its price is
   **90c to 99.9c**.
5. **Liquidity screen.** Ask − bid **3c or less** (the gas rule's screen).
6. **Fill and fee.** Pay the price **+0.4c** (the live crypto fill gap), $10 a bet, contracts = 10 / price. Taker
   fee `ceil(0.07 × contracts × price × (1 − price))`, rounded up to the cent (cautious; Kalshi rounds to
   $0.0001). Hold to settlement; Kalshi's own `result` decides the payoff.

Every bet that passes 1 to 6 is taken. No other filter, no sizing, no tuning.

## The verdict, so it cannot be argued afterwards

Read on the **primary checkpoint (6 hours)**, test data only, each family on its own. Ranges are 95% ranges
(the range the true number is probably in), **clustered on climate date**: every bet on one date counts as one
draw, across all cities and brackets.

A family **passes** only if all of these hold:

1. **At least 1,000 bets on at least 20 climate dates.** If not, the verdict is **"not enough data yet"**, not a
   pass or a fail. Rain will probably land here, and it then gets re-scored on November's fresh data, unchanged.
2. Profit **+2c or more per $10 bet** (+0.2 cents for every dollar bet), after fee and fill gap.
3. The 95% range is **above zero**.
4. **Leave-one-out by price band** (bands 90-95c, 95-97c, 97-99c, 99-99.9c): dropping any one band keeps the
   profit positive with its range above zero.
5. **Leave-one-out by city and by month:** dropping the single biggest-profit city, and separately the single
   biggest-profit calendar month, keeps the profit positive.
6. **Both parts positive:** Older and Recent each show positive profit on their own.
7. **Worst day:** the worst climate date's loss, at $10 a bet, is under 30% of $240 (the plan's bar).

Anything less is a **fail**, and a fail ends weather favourites for this project.

Reported alongside, never able to rescue a fail: the 2-hour checkpoint; the seen half (Jul 18 to Sep 29); the
three biggest high-temperature cities alone (Miami, New York, Los Angeles); each band's loss rate against its own
break-even; losses against the number the prices implied.

## Checks reported before any profit number

- How many markets were listed, how many had candles, and how many requests failed. A failed request is
  retried and then recorded as failed, never treated as "no data".
- Settlement: each test market's `expiration_value` against the NWS daily climate report for its station
  (Iowa Environmental Mesonet archive). Every mismatch is counted. Kalshi's `result` still decides the payoff.

## Data rules

- Kalshi data is pulled at no more than 3 requests a second, after checking no other Kalshi fetch is running on
  the laptop (they share one rate limit). Nothing is sent to the live bot or the Ohio server.
- Raw data stays in `research/weather_favourites/data/`, which is not committed.
