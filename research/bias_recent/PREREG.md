# Has the favourite bias faded since Oct 9? Pass bar, fixed before any data is fetched (30 Oct 2026)

**Question.** Since Oct 20 the live bot has lost about as often as prices predicted. Is that the bot's own bad
stretch, or have favourites stopped beating their prices across all of Kalshi's 15-minute markets? (The favourite
bias: cheap unlikely bets are overpriced and heavy favourites underpriced. It is where the bot's edge comes from.)

**Data.**

- **Recent:** every settled market in the 16 series the bot trades (9 crypto, 5 metals, 2 energy) whose window
  opened from Oct 9 2026 00:00 UTC up to Oct 30 2026 00:00 UTC (21 full days). Minute-by-minute bid and ask from
  Kalshi's candles, with the research's own code (`research/kalshi_15min/fetch_minutes.py` `fetch_window`).
  Nothing else downloaded, nothing filtered by result.
- **Past (the baseline):** `research/kalshi_15min/lab/markets.npz`, Dec 2025 to Oct 8 2026, built from the same
  candles.

**The bets scored.** The bot's rule via `lab/common.py`: `live_rule(d, lo=0.92)`. Favourites 92 to 99.9c at the end
of minute 8, both warning signs skipped, Fed blackouts skipped (the Oct 28 2026 decision is added to the blackout list
for the recent data). $10 bets, whole contracts, at the recorded ask with no extra slip, taker fee included
(`common.bet(top, wins, slip=0.0)`).

**The primary number.** Profit for every dollar bet on the recent data, with its 95% range clustered by window.

**Baselines (fixed now, from the Oct 28 rebuild at the recorded ask).** Whole history +0.80c per dollar bet;
Aug 24 to Oct 8 +1.16c.

**How it will be read.**

- **Faded:** the recent 95% range lies entirely below +0.80c (worse than the long-run past, beyond luck).
- **Still there:** the recent 95% range lies entirely above zero.
- Both can hold at once: **smaller but still there.**
- Neither: **unclear**, and the result is reported with its range.

**Reported, not part of the reading.**

- The same for plain favourites (92 to 99.9c, no warning signs), and their losses against what prices predicted.
- Oct 9 to 19 against Oct 20 to 29 (before and after the live +1 cent limit; the market doesn't know about it, so a
  difference there would be the market's, not the bot's).
- Crypto against metals and energy; Yes against No.
- Windows where 5 or more crypto favourites lost together, per week, against the past rate.
- **Execution check:** the rule on the recent data against the live bot's own result over the same windows
  (Oct 15 10:14 PM PT on). If the market's favourites did fine and the bot didn't, the problem is how the bot buys,
  not the bias.

**Not touched.** `bot/`, the live server, the live ledger (read-only for the execution check), and
`research/kalshi_15min` (its code is imported, nothing written there). Analysis only.
