# Does the bot's rule work on Polymarket US 5-minute markets? Rules and pass bar, fixed before any result is read (8 Nov 2026)

**Question.** Can the existing Kalshi strategy be copied to the 5-minute crypto markets on Polymarket US?
Polymarket US launched 5-minute up/down markets on BTC, ETH, SOL and XRP on Oct 22, 2026. Our rule was built on
Kalshi's 15-minute markets and has never seen these. Does it make money here, after Polymarket's fees?

Written while `fetch.py` was still downloading. No result, price path or outcome had been read when this was fixed.
The only 5-minute data seen so far: the field layout of one market (BTC and ETH 04:35 UTC Nov 9) while working out
the API.

## Data

- Every Polymarket US 5-minute up/down market on BTC, ETH, SOL and XRP from Oct 22 2026 12:00 UTC (the first ones)
  to about Nov 9 2026 04:40 UTC, from the public API (`fetch.py` writes `markets.jsonl`). Nothing filtered by result.
- Prices: `/v1/price-history`, one point a minute. `longPrice` is the Yes ask. `shortPrice` is the No ask
  (1 minus the Yes bid). So both sides' bid and ask are known each minute.
- Results: the market's own resolution (`outcomePrices`), with its open and close values.

**Data end, moved (Nov 11, 04:50 UTC, still before any result was read).** The app closed on Nov 9 at about
05:51 UTC with the download 71% done (to Nov 4 02:35 UTC). `fetch.py` resumed on Nov 10 and runs to 10 minutes
before it started, so the data now ends about Nov 11 04:35 UTC instead of Nov 9. Nothing else changes; the test half
(Nov 1 on) is simply longer.

**Timing.** An earlier check (Oct 18, 15-minute markets) found that a point stamped T shows the book about 60 s later,
like a candle stamped at its start that holds its closing value. So "the end of minute k" will be read from the point
stamped (k − 1) × 60 s after the window opens. This is confirmed or corrected before scoring, using prices only:
`record.py` saves live books for a few hours, and each history stamp is compared with the live book at the same time
and 60 s later. Whichever offset matches more often is used. No outcome is looked at to decide this.

**Timing, confirmed (Nov 9, about 05:45 UTC, before any result was read).** `record.py`'s cached book reads proved
unreliable (the CDN served stale and empty books), so `live.py` polled the live price history instead, every 10 s, for
45 minutes (36-40 points per stamp). Each point first appears about 8 s after its stamp and keeps changing until about
60-68 s after it. So its final value is the book at the end of that minute: the point stamped (k − 1) × 60 is the book
at the end of minute k. **The 60 s offset stands.** (`live_timing.jsonl`, `live_timing_report.json`.)

## The rule scored (the main test): a literal copy

The research's own Kalshi rule (`research/kalshi_15min/lab/common.py`, `live_rule` with its `spread_sign` and
`late_sign`), unchanged except for the entry minute and the price cap:

- **Entry:** the end of **minute 3 of 5** (60% through the window). The bot buys at the end of minute 8 of 15 (53%).
  Minute 3 is the nearest whole minute.
- **The favourite:** the side with the higher ask at entry. Bet when its ask is **92c to 99c** (the live floor;
  Polymarket's top price is 99c).
- **Spread sign:** skip when the favourite's ask is 2c or more over its bid at entry.
- **Late sign:** skip when its mid is 50c or under at minute 1 or minute 2, or rose 10c or more in minute 3.
  (Same code as Kalshi's: M − 1 and M − 2, M = 3.)
- **Fed blackout:** skip windows overlapping the Oct 28 2026 Fed decision, 2:00-3:30 PM ET, as the bot does.
- **Bet:** $10 at the recorded ask, fractional contracts (Polymarket allows 0.01), held to the result.
- **Fee:** Polymarket US taker fee Θ × contracts × p × (1 − p), rounded to the nearest cent per order (banker's
  rounding). **Main Θ = 0.085** (tier 2: $10k-$50k of taker volume a month, about the bot's past pace). The other
  tiers are reported: 0.0695, 0.075, 0.095 (a small new account after its first week).
- Markets missing a price at minute 1, 2 or 3, or with no result, are left out and counted.

## The main number

Profit for every dollar bet, after fees, with its 95% range (the range the true number is probably in), clustered by
window: every bet in the same 5-minute window counts as one, because the four coins move together.

Since the rule was fixed on Kalshi data and has never seen Polymarket's, every day here is out of sample for it.

## How it will be read

- **PASS** needs all three:
  1. profit above **+0.5c for every dollar bet**;
  2. the 95% range entirely above zero;
  3. leave-one-out: still above zero after dropping the coin that earned the most, and separately after dropping the
     best day.
- **FAIL:** profit at or below zero, or the top of the 95% range below +0.5c.
- Anything else: **UNCLEAR** (not enough data yet), reported with its range.

## Reported, not part of the reading

- The plain favourite (92-99c, no signs): bets, losses against what the prices implied.
- Calibration: by price band, how often the favourite won against its price.
- Each coin; Yes against No; Oct 22-31 against Nov 1 on.
- Every fee tier; one tick (1c) worse fills; breakeven slippage (how much worse fills can get before all profit goes).
- Entry at minute 2 and minute 4; a 90c floor; the late sign checked at minute 2 only.
- Bets a day, and depth (contracts on offer at the favourite's ask near minute 3) from `record.py`.
- **Settlement:** at every 15-minute mark, the Polymarket 5-minute close against Kalshi's 15-minute final value for the
  same coin and time. Same index means they should match.

## If the main test is not a PASS

Variants may be explored, but only one way: chosen on **Oct 22-31** (train), then scored **once** on **Nov 1 on**
(test). The grid, fixed now: entry minute {2, 3, 4} × signs {as Kalshi, late sign at M − 1 only, none} × floor
{90c, 92c, 95c}, at Θ = 0.085. Pick the best train profit per dollar with at least 100 train bets. It passes only if
its test result meets the same three conditions as above.

## Not touched

`bot/`, the live and paper servers, `research/kalshi_15min` (imported read-only). No account, no orders. Public
Polymarket US data only.
