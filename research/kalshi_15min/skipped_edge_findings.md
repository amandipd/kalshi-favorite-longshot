# The 16 fifteen-minute series the bot skips: is there an edge? (Oct 24)

**No. Nothing here is worth trading, and nothing should change before Nov 27.**

Kalshi runs 35 fifteen-minute series. The bot asks for 19 — crypto, metals and energy, `bot.py`'s
`EDGE_GROUPS` — and skips 16. This replays the live entry rule on all 16 on their own candle history,
with the same code and the same economics as `strategies_backtest.py`.

    python scan_skipped.py      which skipped series have ever settled a market
    python fetch_skipped.py     their minute 1-15 bid/ask history -> minutes_skipped.csv
    python skipped_edge.py      the live rule on them -> skipped_edge.json

## What there was to test

Five of the 16 have **never run a single market**: Crypto Comparison, the Dow, the S&P 500, the
Nasdaq 100 and USDMXN. They are listed in the catalog and nothing else. The other 11 settled 39,238
markets between them, and 38,335 had candles to read:

| Group | Series | Settled markets | Span |
|---|---|---|---|
| Coin race | KXCRYPTOLEAD15M | 29,646 | Aug 20 – Oct 25 |
| FX majors | EURUSD, GBPUSD, USDJPY | 2,063 each | Sep 23 – Oct 23 |
| FX minors | AUDUSD, USDCAD | 1,124 each | Oct 7 – Oct 23 |
| Rates | 2yr, 5yr, 10yr, 30yr yields | 235 each | Oct 19 – Oct 23 |
| Energy | KXBRENT15M | 215 | Oct 21 – Oct 24 |

## The control: the harness is the existing backtest

The same code on the series the bot does trade reproduces `strategies.json` to the cent, twice:

| Rule | Mine | `strategies.json` |
|---|---|---|
| 92c floor, no skips (`vb92`) | 51,345 bets, −$764.37 | 51,345 bets, −$764.37 |
| 90c floor, skip both signs (`vfsl`) | 36,673 bets, +$3,182.88 | 36,673 bets, +$3,182.88 |

## The floor alone loses in every group

At the 92c floor and nothing else, every skipped group loses, most of them heavily. 17,167 bets:

| Group | Bets | Cents per $1 | t | Mean spread at entry |
|---|---|---|---|---|
| Coin race | 14,678 | **−2.59c** | −14.3 | 7.0c |
| FX majors | 1,561 | **−2.23c** | −3.7 | 3.7c |
| AUDUSD + USDCAD + Brent | 723 | **−3.26c** | −3.4 | 9.4c |
| Treasury yields | 205 | **−26.18c** | −8.0 | 45.6c |

(cents per $1 staked, 0.4c over the ask where live fills land.) The yields are not a market: a 45c
spread means there is no book to trade against.

This is not the bot's rule, though. On the bot's own markets the 92c floor alone earns −0.15c/$1 —
the edge is almost entirely in the two warning signs the bot skips on, not in the price floor.

## The full live rule: the filters cut 92% of the bets

With both signs skipped — the favourite's own ask 2c or more over its bid, and a favourite that was a
coin flip a minute or two ago or jumped 10c into minute 8 — 17,167 bets become 1,338. These markets
are too wide to pass:

| Group | Bets | Cents per $1 | t | 95% CI |
|---|---|---|---|---|
| Coin race | 711 | +0.72c | +1.65 | [−0.13, +1.57] |
| FX majors | 416 | +0.74c | +0.99 | [−0.72, +2.20] |
| AUDUSD + USDCAD | 203 | −2.17c | −1.37 | [−5.27, +0.93] |
| Brent | 3 | — | — | — |
| Treasury yields | 5 | — | — | — |
| **What the bot trades** | **30,375** | **+0.43c** | **+4.16** | **[+0.23, +0.63]** |

Both point estimates sit near the bot's own and both intervals cross zero. On their face, Coin Race
and the FX majors are maybes.

## Why they are not even maybes

**The whole positive result is 110 bets in one band with one loss.**

| | Bets | Losses | Cents per $1 |
|---|---|---|---|
| Skipped series, 92–94c | 110 | **1** | +6.08c |
| Skipped series, 94c and up | 1,228 | 27 | **−0.22c** |
| The bot's own markets, 92–94c | 6,329 | 345 | +0.82c |

At 92–94c the price implies about 7 losses in 110 bets. One is luck, and it is carrying everything:
take that band out and the other 1,228 bets lose money.

The bands also tell the story. On the bot's own markets the edge falls smoothly as the favourite gets
dearer — +0.82c, +0.48c, +0.27c, +0.20c — which is what a favourite-longshot edge looks like. The
skipped series have no shape at all: +6.08c, −1.44c, −0.03c, +0.00c.

## Other reasons to leave them alone

- **The volume is not worth it.** 1,127 qualifying bets (Coin Race plus FX majors) against the bot's
  30,375 — under 4% more bets, for an unproven edge.
- **Coin Race bets move together.** Five markets a window and exactly one coin leads, so 696 of its
  711 bets are NO bets and one of a window's NO bets must lose. The filters leave only 1.2 bets a
  window, which mutes it, but at the bot's real size with a window cap it is a correlation the
  backtest's flat $10 hides.
- **The FX majors have one month of history**, and the minors two weeks.
- **Depth is unrecorded.** `depth_books.py` has never covered any of these series, so even the
  surviving 1c-spread bets have no measured book behind them. The candle ask is not a fill.
- **The six-week test runs to Nov 27.** Adding a market restarts that clock.

## Brent, separately

`KXBRENT15M` is skipped by accident, not by choice: `group_of()` matches WTI, NATGAS and OIL, so
Brent falls to the `"commodities"` catch-all and never reaches `EDGE_GROUPS`. It is a real market on
WTI's schedule, but it launched on Oct 21 — 215 settled markets, and 3 that pass the live rule. There
is nothing to measure yet. Worth re-running after Nov 27, when there is a month of it.

## If this is picked up again

Re-run `scan_skipped.py` then `fetch_skipped.py` (it resumes, so it only pulls what is new) and
`skipped_edge.py`. The two to look at are Coin Race and the three FX majors, and the question to ask
is whether the 92–94c band still carries the whole result.
