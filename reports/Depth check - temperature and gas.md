# Depth check: hourly temperature and daily gas markets

*Oct 16, 2026. Data: 8,312 real Kalshi order books recorded Oct 13–16 (3.75 days, with a 2.6-hour gap on Oct 15), at the checkpoints the pass test chose. Every market has settled. Rerun with `python depth_books.py report` from `research/kalshi_15min`; the recorder runs again until Oct 20, 11:37 PM ET.*

## The answer

- **Gas: deep enough for real bets.** At the favourite's price there's a median **$1,500–1,700** on offer, and **95–97% of $100 orders** would have filled in full. Depth is not the problem.
- **Temperature: only small bets.** The median on offer is **$46–59**. $10 orders fill in full 73–80% of the time, $50 orders only about half the time, $100 orders a third.
- **The edge is still unproven for both.** Losses ran close to what the prices implied (see below). 3.75 days is far too short for 98–99¢ favourites, where one loss wipes out 50–100 wins.
- **Even if the edge holds, the money is small.** At $10–25 a bet, the best group earns about **$7–15 a day**.
- **Next:** rerun after the recorder finishes on Oct 20, which doubles the sample. Adding these markets to the bot would be a rule change, so it waits for the 6-week test to end on Nov 27.

## The numbers

"Bets" are favourites at 90–99.9¢ with a spread of 3¢ or less, the pass-test rule. "At book" means an order buys only what the book really held, up to the ask + 0.4¢. "Backtest" assumes the full $10 always fills at the ask + 0.4¢. The ± is a 95% range.

| Group | Bets | Bets/day | Lost | Implied losses | Median $ at the ask | Full fill: $10 / $25 / $50 / $100 | Profit per $10 bet at book |
|---|---|---|---|---|---|---|---|
| Temperature, 30 min before | 326 | 87 | 7 | 9.3 | $46 | 73% / 61% / 48% / 34% | **+7.9¢** ± 12.5¢ |
| Temperature, 10 min before | 197 | 53 | 5 | 5.8 | $59 | 80% / 69% / 55% / 31% | **−2.4¢** ± 22.8¢ |
| Gas, 2 h before | 146 | 39 | 1 | 1.9 | $1,702 | 98% / 98% / 98% / 95% | **+4.2¢** ± 13.6¢ |
| Gas, 1 h before | 75 | 20 | 1 | 1.0 | $1,543 | 99% / 99% / 99% / 97% | **+10.2¢** ± 3.7¢ * |
| SOFR (interest rate), daily | 3 | 1 | 0 | 0 | $1,584–2,414 | 100% | too few |
| ERCOT (Texas power), daily | 0 | — | — | — | — | — | none qualified |

\* The gas 1-hour range looks tight only because its single loss doesn't count against it in that measure. With 1 loss against 1.0 implied, there's no sign of an edge yet.

**Dollars a day at the book**, if each group's average so far held up:

| Group | $10 bets | $25 bets | $50 bets | $100 bets |
|---|---|---|---|---|
| Temperature, 30 min | +$6.83 | +$14.90 | +$27.63 | +$46.06 |
| Gas, 2 h | +$1.64 | +$4.29 | +$8.58 | +$17.49 |
| Gas, 1 h | +$2.04 | +$5.60 | +$11.46 | +$23.36 |

These are averages over a few days with wide ranges, not forecasts.

## What stands out

1. **The trade tape undercounted gas depth.** The Oct 12 tape check found a median of $0 traded at our price, because it only sees trades. The real books hold over $1,500 that nobody had taken.
2. **Temperature depth matches the tape:** small. Bets above about $25 often go part-filled.
3. **Losses ran close to the prices:**
   - temperature 30 min: 7 vs 9.3 implied;
   - temperature 10 min: 5 vs 5.8;
   - gas: 2 vs 2.9 combined.
   
   That's consistent with a small edge or none. A clear answer needs weeks, not days.
4. **Losses didn't cluster.** No hour had 2 or more temperature losses, and each gas day had at most 1. That's good for independence, but it's only 66–68 hours and 3 gas days.
5. **Gas is really only a few bets.** Gas markets settle once a day, and all states move with the national price. So the 3 days recorded are more like 3 big bets than 146 small ones.
6. **The backtest's 0.4¢ slip is too harsh** at 99¢ prices, where the whole margin is about 1¢. Real orders here would pay the ask, as the live crypto bot does.

## Compared with the bot's current markets

The live bot's crypto and commodity markets earn about +1.4¢ per $1 at 92¢ and up, and they come every 15 minutes. Temperature and gas so far run about +0.4 to +1% per $1, with a much smaller sample and either shallow books (temperature) or once-a-day bets (gas). **They'd add breadth, but not much money**, unless the full-week rerun shows a clearer edge.
