# The opening price of a newly listed market: what is being tested, written before any result is read

*Oct 25, 2026. Written and saved before the first opening price is fetched, for the same reason as
`../kalshi_15min/FILTER_SEARCH_PREREG.md` and `THRESHOLD_SEARCH_PREREG.md`: the thin-volume result that motivates this
test had its price band and its liquidity cut chosen **after** the data was seen, so on its own it is
a lead and not a finding.*

## The question

The study prices every market at the last trade one hour before close. Nobody has ever looked at the
other end of a market's life. The question is narrow:

**Is a market's opening price more mispriced than its price near close, and in the same direction?**

The thesis under test is that a brand-new market has thin or absent liquidity and an uncalibrated
price, and that the mispricing favours the favourite until the book deepens.

## What motivated it, and what is wrong with that motivation

Exploratory cut on `data/processed/contracts.parquet`, Oct 25. Edge is realized frequency minus mean
price, in cents per contract, at the T-1h price:

| price band | thinnest volume third | thickest volume third |
|---|---|---|
| 60-80c | +3.3c | −1.1c |
| **80-90c** | **+5.1c** | −1.9c |
| 90-95c | −1.6c | −2.2c |
| 95-100c | −0.6c | −0.6c |

Three things are wrong with it as evidence:

1. The **80-90c band and the volume terciles were both chosen after seeing the table.**
2. **Volume is the market's whole-life total**, which is not knowable at entry. It is a proxy for
   "never got liquid", not for "young".
3. It is priced at T-1h, so it says nothing about the opening price at all.

This test fixes (3) and pre-commits (1) and (2) in advance.

## The primary hypothesis, fixed now

**H1.** At the opening price, favourites priced **80-90c** resolve YES **more** often than their price
implies, by more than the fee, out of sample.

One band, one direction, one number. Everything else below is secondary and labelled as such.

## What counts as the opening price

The **first trade** at or after `open_time`, within a window of `open_time + W`.

`W` is swept over **1h, 6h, 24h, 72h**, with the primary chosen the same way the T-1h horizon was
chosen in ADR 003 (maximise `retention × (1 − pinned rate)`), and that choice is made on the
**train half only**. A pilot market had zero trades in its first hour and its first trade at
+1h 0m 35s, so short windows will lose a lot of sample; that trade-off is exactly what the sweep is
for.

## Secondary, pre-registered as secondary

- Bands 60-80c, 90-95c, 95-100c. Reported with the same correction, never promoted to the headline.
- The same test on the **last** trade in the opening window, to separate "the first print was odd"
  from "the market was mispriced for the whole opening window".
- Opening price versus T-1h price on the same markets, which is the convergence question.

## The liquidity cut, defined on entry-time information only

Whole-life volume is banned. The thin/thick split is **the number of trades in the opening window**,
cut at its terciles, because that is knowable at the moment of entry. If that proxy fails to
reproduce the thin/thick divergence above, that is a result and it is reported as one.

## Method, fixed in advance

1. Fetch the opening-window trades for every settled binary market already in the raw layer.
2. Split by `close_ts` at its **60th percentile**, the same cut the main study and backtest use, so
   the boundary is inherited rather than chosen here.
3. On the **train half only**: choose `W`, and record every value tried.
4. Score H1 **once** on the test half.
5. Every interval and p-value **clusters on `event_ticker`** (Liang-Zeger for standard errors), and
   bands are **Benjamini-Hochberg corrected** across all bands reported in a table.
6. Fees at Kalshi's taker schedule, `ceil(0.07 × C × P × (1−P))`, as in `kalshi_calibration/strategy/backtest.py`.

## The decision rule, so the answer cannot be argued afterwards

H1 **passes** only if all four hold on the **test half**:

- bias > 0,
- t > 2 with clustering on event,
- bias still positive after the taker fee,
- and it survives **leave-one-series-out**: dropping the two largest contributing series does not
  flip the sign.

Anything less is a fail. A fail is a publishable result and ends the strategy work.

## Selection bias, which is the most likely way this misleads us

Only markets that traded in the opening window get an opening price. Quiet markets drop out. This is
the same shape of trap as the pinned-price problem that forced the T-1h horizon in the first place.

Reported **before** any edge number, and treated as a blocker if it is bad:

- retention: share of markets with at least one trade in the window, overall and per category;
- how the dropouts differ from the keepers on price, lifetime, category and series;
- time from `open_time` to first trade, as a distribution.

If retention is heavily skewed by category or series, the edge estimate is contaminated and gets
reported as contaminated.

## What this test cannot settle

It cannot measure the **spread at the open**, because historical data carries no book: over half of
settled snapshots quote 0.0000/1.0000. So even a pass does not mean tradeable. The net edge at T-1h
is about 4c with about 4c of breakeven slippage, and a thin book can be 3-5c wide. Only forward
order-book collection answers that, and it is a separate piece of work.

Nothing goes live before **27 November** regardless of the result, so the six-week test on the live
bot stays clean.
