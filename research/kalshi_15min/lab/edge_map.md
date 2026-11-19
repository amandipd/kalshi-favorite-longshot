# Where the edge lives

Oct 11, 2026. `edge_map.py` writes `edge_map.json` from `markets.npz`; `test_edge_map.py` checks it against
`strategies_backtest.py`. As a check, it reproduces the live rule exactly: 35,793 bets at +4.47¢, and $500 on Dec 10
growing to $25,131.63 with a 59.7% deepest fall, the same as `strategies.json`.

How to read the numbers:

- Every figure is cents of profit per $10 bet: whole contracts, bought at the recorded ask plus 0.4¢ (a "live-like"
  fill), after the taker fee, the fee paid for filling instantly at the listed price.
- Brackets give the 95% range, clustered by window. The bets in one 15-minute window move together, so they count as
  one block.
- **pre** = Dec 10 – Jul 17. No rule was chosen on it.
- **post** = Jul 18 – Oct 8.
- **clean** = post without Aug 24 – Sep 23, the month the live filters were chosen on.
- Each rule change was chosen on one half and scored on the other, both ways round, one change at a time.

## 1. Entry minute and price

The live rule (filters on, 90–99.9¢) by entry minute:

| Minute | pre | post | clean |
|---|---|---|---|
| 5 | +7.7 [−0.9, +16.2] (4,315) | +8.6 [+0.3, +17.0] | +0.9 [−10, +12] |
| 6 | +3.7 [−3.0, +10.4] | +7.1 [+1.1, +13.2] | +2.5 |
| 7 | +3.3 [−1.8, +8.4] | +4.6 [−0.4, +9.6] | +2.3 |
| **8 (live)** | **+1.7 [−2.5, +5.8] (15,650)** | **+6.7 [+2.9, +10.5] (20,143)** | **+5.0** |
| 9 | +1.5 [−1.7, +4.8] | +3.9 [+0.7, +7.2] | +2.5 |
| 10 | −0.1 | −1.1 | −2.1 |
| 12 | −3.4 [−4.9, −1.8] | −2.8 [−4.5, −1.1] | −3.7 |
| 13 | −3.6 [−4.9, −2.4] | −5.1 [−6.5, −3.8] | −4.8 |

- **Later is worse in both halves.** From minute 10 on, the favourite's price has caught up with how often it wins.
  At minute 13 it wins 98.6% of the time and is priced at 98.7¢.
- **Earlier is no better once you count the money.** Chosen on pre, minute 5 wins and scores +8.6¢ on post, against
  +6.7¢ at minute 8. But that is on a third as many bets, and minute 5's range covers minute 8's.
- **Bands within 90–99.9¢:** pre would drop 90–94¢ (−0.2¢ and −0.5¢). On post those bets made +11.1¢
  [+4.3, +18.0], so dropping them fails out of sample. Chosen on post, nothing gets dropped. This agrees with
  `price_floor.py`.
- **85–90¢ at minute 8** is −5.2¢ on pre and +7.6¢ on post. The halves disagree, so it shouldn't be added.
- **Without the live filters** the plain rule loses at every minute and band on pre. The spread and late-favourite
  filters are what make it pay.
- **By group, post at minute 8:** crypto +5.2¢ [+1, +10], metals +12.7¢ [+4, +21], energy +14.4¢ [+4, +25]. Metals and
  energy have no pre data to check against.

## 2. The underdog: the longshot half of the bias

Buying the other side of the same minute-8 markets at its own ask loses 4–8 dollars per $10 bet:

- Plain rule: −507¢ on pre and −442¢ on post.
- Live filters: −519¢ and −492¢.
- Underdogs of 90–99.9¢ favourites won 5.3% of the time against a 7.0¢ mid and an 8.5¢ ask.

They are overpriced even at the mid (the halfway point between bid and ask), and the spread and fee then make it far
worse. The favourite won 94.7% against a 93.0¢ mid.

## 3. Timing (live rule, minute 8)

- **ET hour of day: noise.** Hours 3, 4 and 18 ET pass the bar (the sign agrees in both halves and the
  whole-history range excludes 0), but all three are positive, so none of them suggests a skip. "Skip the hours
  that lost on half A" fails on half B both ways round:
  - Chosen on pre: the skipped hours made +6.8¢ on post.
  - Chosen on post: the skipped hours made +9.6¢ on pre.
- **Weekday vs weekend: no difference.** Weekdays made +4.5¢, weekends +4.6¢.
- **Release windows (weekdays only).** The four windows that close or open on the 8:30 and 10:00 ET data releases:
  pre −19.9¢ [−50, +10], post −3.4¢ [−23, +17], whole history −10.1¢ [−27, +7] (1,238 bets). It leans the wrong way,
  but it doesn't pass the bar.
- **The 9:30 ET window, when US stocks open: −52.0¢ [−106, +2] on pre, −33.1¢ [−87, +21] on post, −40.9¢ [−80, −2]
  over the whole history (416 bets).** It passes the bar. It is also an honest out-of-sample result: the Sep research
  flagged this window on Jul 18 – Sep 29 data (README, 260 bets), and the seven untouched months confirm it. One
  caveat: about 30 time segments were looked at here.

## 4. Same-window concentration (crypto, live rule)

- 3.84% of crypto bets lose.
- **If one crypto favourite in a window loses, another in the same window loses 36% of the time.** That is 9 times
  the base rate.
- 198 windows lost 2 or more crypto bets. If the bets were independent, about 64 would have.
- 43% of all crypto losses come in windows with 2 or more losses. The worst window lost 6.

The bot's own sizing (3% a bet, at most 20% a window, whole contracts) from $500:

| Rule | $10: pre | $10: post | pre: end, deepest fall, worst window | post: end, deepest fall, worst window |
|---|---|---|---|---|
| Live rule | +1.7 | +6.7 | $737 · 59.7% · −17.7% | $16,184 · 50.7% · −17.0% |
| ≤1 crypto bet a window (dearest) | −1.4 | +7.9 | $337 · 63.0% · −3.0% | $3,934 · 26.8% · −6.0% |
| ≤2 (tightest spread) | +1.5 | +8.2 | $666 · 44.0% · −6.0% | $9,619 · 32.2% · −8.9% |
| **≤3 (tightest spread)** | **+1.9** | **+8.0** | **$806 · 52.8% · −8.9%** | **$15,049 · 42.3% · −9.0%** |
| ≤3 (dearest) | +1.4 | +7.5 | $696 · 56.8% · −8.9% | $12,517 · 40.0% · −9.0% |
| Window cap 9% instead of 20% | +1.7 | +6.7 | $775 · 54.5% · −8.9% | $9,591 · 40.0% · −9.0% |

- **≤3 with the tightest spreads is the best cap whichever half it is chosen on** (scored by end ÷ start ÷ deepest
  fall).
- It halves the worst window, from about −17.5% of the bankroll to −9%, and cuts the deepest fall by 7–8 points in
  both halves. The bets it drops made +0.4¢ on pre and +2.7¢ on post, both with ranges covering 0.
- Post ends 7% lower than the live rule, because it places fewer bets. Pre ends 9% higher.
- It beats the plain sizing fix, a 9% window cap, which has the same worst window but ends lower in both halves.
- K = 1 and 2 drop too many good bets.

## The three changes that hold up

Each was tried on its own, with live-like fills and the bot's sizing from $500. Spreads are compared to 4 decimal
places; before that fix, float noise broke ties between equal spreads at random:

1. **Skip the weekday 9:30 ET window.**
   - Per $10 bet: pre +1.7¢ → +2.3¢, post +6.7¢ → +7.2¢, whole history +4.5¢ → +5.0¢.
   - The bot's sizing from $500 on Dec 10: $25.1k → $42.7k.
   - It leaves out 416 bets in ten months.
2. **At most 3 crypto bets a window, keeping the tightest spreads.**
   - The worst window falls from −17.7% to −9.0% of the bankroll.
   - Deepest fall: pre 59.7% → 52.8%, post 50.7% → 42.3%.
   - Per $10 bet: pre +1.9¢, post +8.0¢.
3. **Keep minute 8 and the 90–99.9¢ band.** Moving later loses in both halves; moving earlier or trimming bands
   doesn't hold up out of sample.

With both 1 and 2 together: per $10 bet, pre +2.6¢ and post +8.4¢. Deepest fall: pre 52.4%, post 39.4%. Worst window:
−9.0% of the bankroll.
