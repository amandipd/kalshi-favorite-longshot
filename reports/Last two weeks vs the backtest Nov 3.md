# The last two weeks against the backtest (Nov 3)

**Short answer: yes, the backtest (the bot's rule replayed on Kalshi's own recorded prices) shows the same last two weeks. It lost about as much as the live bot did, day by day. So the live losses are what the strategy itself did, not a bot fault. But the past data has almost nothing like it. Two-week stretches this bad happened only in the early months (about 1 in 25, all before mid-July), and none since. And windows where 6 or more bets lost together never happened once in 10 months of past data. In the last two weeks there were four.**

## 1. Did the backtest replicate the last two weeks?

The rule replayed on every market in the bot's 16 series, Oct 20 to Nov 3, using Kalshi's recorded minute-by-minute prices. It's the same method as all the earlier backtests (`research/bias_recent/bad_days.py`). Against it, the live bot's own ledger.

| Day (local time) | Rule: lost (prices predicted) | Rule: cents of profit per dollar bet | Live: lost (prices predicted) | Live: cents of profit per dollar bet |
|---|---|---|---|---|
| Tue Oct 20 | 8 (11.0) | +0.76 | 6 (8.8) | +0.90 |
| Wed Oct 21 | 9 (9.7) | −0.02 | 9 (9.3) | −0.22 |
| Thu Oct 22 | 16 (11.4) | −1.90 | 8 (7.9) | +0.49 |
| Fri Oct 23 | 6 (8.2) | +0.72 | 6 (7.9) | +0.78 |
| Sat Oct 24 | 5 (7.5) | +1.07 | 4 (5.0) | +0.89 |
| Sun Oct 25 | 3 (7.6) | +2.16 | 3 (7.6) | +2.16 |
| Mon Oct 26 | 9 (11.2) | +0.49 | 9 (10.8) | +0.52 |
| Tue Oct 27 | 12 (10.0) | −1.13 | 12 (9.8) | −1.41 |
| Wed Oct 28 | 12 (11.3) | −0.56 | 11 (10.9) | −0.61 |
| Thu Oct 29 | 15 (10.6) | −1.90 | 14 (9.9) | −2.08 |
| Fri Oct 30 | 11 (9.1) | −1.23 | 11 (9.2) | −1.16 |
| Sat Oct 31 | 4 (8.0) | +1.80 | 4 (7.8) | +1.68 |
| Sun Nov 1 | 6 (8.9) | +0.96 | 6 (8.8) | +0.92 |
| Mon Nov 2 | 16 (11.3) | −1.94 | 17 (11.4) | −2.22 |
| Tue Nov 3 (to 7 AM) | 8 (3.7) | −4.35 | 9 (3.6) | −5.96 |

- **Totals:** the rule lost 140 bets where prices predicted 139.5, −0.33 cents for every dollar bet. The live bot lost 129 where prices predicted 128.9, −0.30 cents.
- **The two match day by day.** The one real gap is Thu Oct 22: the rule took a 7-loss crypto window at 6:45 AM that the live bot's real-time warning signs skipped. That saved the live bot money that day.
- **So the backtest method reproduces the live result.** The losses come from the strategy and the market, not from how the bot traded.

## 2. Were there days this bad in the past?

The past data is the rule on Dec 20, 2025 to Oct 19, 2026 (only days with 50 or more bets).

- **Single days.** The live bot's worst day (Nov 3, −5.96 cents for every dollar bet, on 107 bets before the live test ended) was matched or beaten on 3 of 223 past days (1.3%): Jun 18, May 21 and Jul 30. Since Aug 24, the worst past day was Sep 28 at −3.56 cents. Nov 2 (−2.22 cents live) would have been the second-worst day since Aug 24.
- **Bad days came close together this time.** In these 15 days, four days were at −1.9 cents or worse (Oct 22 for the rule, Oct 29, Nov 2, Nov 3). In the 57 days from Aug 24 to Oct 19 there was one.
- **Losing days in general:** 30% of past days lost money over the whole history; 18% since Aug 24. In the last two weeks it was 7 of 15 days (47%).

## 3. Were there two-week stretches this bad?

All 15-day stretches (the length of Oct 20 to Nov 3), one starting each day:

| Past period | 15-day stretches | Share that lost money | Share as bad as the last two weeks (−0.33 cents) | Worst one (cents per dollar bet) |
|---|---|---|---|---|
| Whole history | 159 | 11% | 4% | −0.89 |
| Since Jul 18 | 80 | 5% | 0% | −0.14 |
| Since Aug 24 | 43 | 0% | 0% | +0.81 |

- **Two weeks this bad did happen, but only in the early months** (before mid-July, when the bot's rule covered fewer coins). About 1 in 25 stretches then.
- **Not once since mid-July.** The worst 15 days from Jul 18 to Oct 19 were −0.14 cents for every dollar bet. From Aug 24 on, every 15-day stretch made money, the worst +0.81 cents.

## 4. The pile-ups had no past match at all

A pile-up is a window where many bets lose at once, because the markets moved together.

| Period | Windows with 6+ losses | Windows with 3+ metals losses |
|---|---|---|
| Past, whole history (293 days) | 0 | 0 |
| Past, Aug 24 to Oct 8 (46 days) | 0 | 0 |
| Recent, Oct 9 to 19 (11 days) | 0 | 1 |
| **Recent, Oct 20 to Nov 3 (14 days)** | **4** | **2** |

- The four 6-plus windows: Oct 22 at 6:45 AM (7 lost), Oct 22 at 6:30 PM (7), Oct 29 at 2:30 PM (6), Nov 3 at 5:15 AM (6).
- Metals pile-ups only became possible once there were five metals series (platinum and palladium started Sep 17). Even so, none happened before Oct.

## What it means

- **The live bot was not unlucky against its own backtest.** The backtest, run on the same days, loses the same way.
- **What changed is the market.** The kind of day that drove the losses (many markets flipping in the same 15 minutes, now metals too) never showed up in 10 months of past data, and showed up four times in two weeks.
- **That is the key question for any restart.** If these pile-ups were a short burst, the long-run past (about +0.4 to +0.8 cents for every dollar bet) is still the best guide. If they are the new normal, the backtests overstate the edge (the bot's profit source), because they never saw them.
- **What would show which:** a few more weeks of Kalshi's prices, checked the same way (no bot needed, and no money at risk). If 6-plus pile-ups keep coming more than once every week or two, the market has changed.

## Files

- `research/bias_recent/bad_days.py`: this analysis. It reads Kalshi's prices for Oct 9 to Nov 3 (`recent_minutes.csv`, `recent_minutes_nov.csv`, rebuilt by `fetch_recent.py`), the past file `research/kalshi_15min/lab/markets.npz`, and a read-only pull of the live ledger.
- Nothing in `bot/` or on the server was changed.
