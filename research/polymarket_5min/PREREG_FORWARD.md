# Forward paper test of the minute-4 rule, with no peeking. Rules and pass bar, fixed before it starts (13 Nov 2026)

**Why.** The backtest (`reports/Polymarket 5-minute backtest Nov 10.md`) found that buying the favourite at minute 4
of 5 made +0.95 cents for every dollar bet on held-out days. But its minute-4 price is the history point's final value,
which keeps updating until about 8 seconds after 4:00. Those seconds fall inside the 60-second settlement average,
so the backtest may peek. In 12 of 59 live checks a bot buying at 4:00 would have bet differently or paid a different
price. This test records, live, only what a bot could see before 4:00, and scores that. Nothing is traded. It was
set up on Nov 10.

## What is recorded (`forward.py`, on a local machine)

- Every 5-minute window on Polymarket US, for BTC, ETH, SOL and XRP.
- **Two price polls** a window, at about 3:46 and 3:54 server time. Each asks the public price history from 2 minutes
  before the window up to that second. Server time comes from the response's Date header, not the local clock.
- **One order-book read** at about 3:50, for depth only. The CDN caches it for up to 30 s.
- Results are not read by the recorder.

## The bet (the rule from the backtest's grid pick, unchanged)

- **What it sees:** the latest poll whose server time is **at most 3:58** (238 s) into the window. In it, the point
  stamped 3:00 is the book at about 3:46-3:50. That is earlier than 4:00, the safe direction.
- **The rule:** `score.rule(M=4, lo=0.90)`. The favourite (the side with the higher ask) at 90-99c; the bot's spread
  sign (skip at 2c or more); its late sign (skip if the mid was 50c or under at the end of minute 2 or 3, or rose 10c
  or more since the end of minute 3). These are the same functions the backtest used.
- **The price paid:** that favourite's ask, as seen. $10 a bet, fractional contracts, held to the result.
- **The fee:** Θ = 0.085 (tier 2), rounded to the nearest cent per order, half to even (`score.bet`).
- A market with no visible poll by 3:58, or no minute-4 point in it, is no bet. It is counted, not guessed.

## How long

At least 72 hours from the first record **and** at least 1,000 bets. If 72 hours pass with fewer, it keeps going
until 1,000 bets, but never past 7 days. The machine sleeping makes gaps. Those windows are simply not recorded.
A watchdog task restarts the recorder within about 5 minutes of a wake.

## The pass bar

Profit for every dollar bet, after fees, with its 95% range (the range the true number is probably in) clustered by
window: bets in the same 5 minutes count as one.

- **PASS:** profit above **+0.5 cents** for every dollar bet, and the whole range above zero.
- **FAIL:** profit at or below zero, or the top of the range below +0.5 cents.
- Anything else: **UNCLEAR**, reported with its range.

## Reported, not part of the reading

- **The peek effect:** the same markets scored at the history's final minute-4 value, as the backtest would have
  scored them. The gap between the two numbers is what the peeking was worth.
- Losses against what the prices implied; each coin; Yes against No; the 99c bets alone.
- Dropping the coin that earned the most, and separately the best day.
- Depth: dollars on offer at the favourite's ask in the 3:50 book reads (stale up to 30 s).
- Coverage: windows recorded out of windows that passed.
- **No mid-run look at results.** `forward_report.py --health` prints counts and coverage only.

## Not touched

`bot/`, both servers, the Kalshi paper run. Public Polymarket US GETs only, about 12 a window. No account, no orders.
