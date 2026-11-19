# Live capture review: Sep 28 – Oct 13, 2026 (Oct 14 update first)

## Oct 14 update (data through Oct 14, 2:08 PM ET: 1,070 settled bets, +$146.18)

**1. The last two days had no edge, and the whole loss is under 92¢.** Oct 13–14 had 442 bets: 19 lost against 19.6 implied, −$11.77.

| Ask | Bets (all live) | Lost | Implied | P&L |
|---|---|---|---|---|
| under 92¢ | 194 | 29 | 18.0 | −$145.25 |
| 92¢ and up | 876 | 18 | 33.5 | +$291.43 (flat $10: +15.8¢ per $10 ± 6.6) |

- Oct 13–14 alone: under 92¢ made −$173 (13 lost of 69); 92¢ and up made +$162 (6 lost against 12.9).
- The 92¢ floor is already coded and tested in bot/ (Oct 14). **It takes effect only when the bot restarts.**
- **Not a whole-cent quirk.** Asks of exactly 90.0¢ were as bad as 90.1–90.9¢ live: 11 of 57 vs 9 of 54. The backtest shows no whole-cent effect at 90–95¢.
- **Adverse selection** (getting filled more often on the worse bets) **is strongest at the cheap end.** Filled 90.1–91.9¢ orders won 89.8%; unfilled ones won 93.9%.
- **Nothing else separates winners from losers above 92¢.** The spread at entry and the minute-6 price (how fast it became the favourite) were both flat.

**2. Landing late hurts outcomes, not just fills.**
- **Queue delay** is how long an order lands after the window's first order (Kalshi's timestamps). It is **+0.87 log-odds of losing per second (p = 0.004)**, controlling for price, coin and day.
  - Orders within 0.3 s of the first lost 16 against 25.5 implied; 1–3 s later, 8 against 6.3.
  - The bot sends a window's orders one after another, in Kalshi's market-list order.
- Orders that landed within 2.5 s of the mark lost 4 against 15.4 implied. The effect of absolute lateness, though, can't be separated from the day: the clock drift grows day by day.
- **Clock:** the PC's time-sync service is now running but has never synced. The PC was 1.43 s behind at 2:07 PM ET on Oct 14. The median order now lands 3.8–5.4 s after the mark.

**3. The +1¢ limit on paper, 720 orders.**
- Counting only 92¢ and up (605 orders): the fill share would rise from 60.3% to 96.6%. The extra 6,271 contracts cost +0.36¢ over the seen ask.
- Realised +$152.92 (4 lost of 269), against +$132.41 real on the same orders.
- Expected value: +$42 at the backtest's ~1.3 pt edge, −$7 at 0.5 pt.
- The verdict comes at 1,000 orders, about Oct 15–16.

**Next steps:**
1. Restart the bot to put the 92¢ floor in force.
2. Sync the clock: set a time server and resync, with admin rights.
3. Send each window's orders together rather than one after another: a bot change, tests first, not yet decided.
4. Decide on +1¢ at 1,000 orders.
5. Fast entry stays parked.

---

Data: a read-only snapshot of `bot/state/live-prod.db`, with bets settled through Oct 13, 7:30 PM ET. It covers:
- 846 settled bets;
- 4,840 bot decisions;
- 1,141 orders;
- 838 paper-experiment rows, from Oct 12, 4:38 PM ET onward.

Kalshi's results and minute candles were fetched for every market the bot looked at. Stop-loss and retry ideas were checked on the strategy lab's backtest, `lab/markets.npz` (35,793 live-rule bets, Dec 10 – Oct 8). The scratch scripts were one-off scripts, not in the repo.

Prices are the favourite's ask. "Implied losses" = Σ(1 − price): what the price alone predicts. "Per $10" = profit per $10 staked, after fees. "±" is one standard error, clustered by window (bets in the same 15 minutes count as one draw, since they move together).

## 1. Results: consistent with the backtest, slightly better

| | Bets | Lost | Implied by price | Net |
|---|---|---|---|---|
| All | 846 | 32 | 43.0 (p = 0.05) | **+$265.54** on $14,786 staked, $53.07 fees |

- At a flat $10 a bet, live made **+8.6¢ per $10 ± 9.2**. The backtest made +4.5¢ (whole history) and +6.7¢ (Jul 18 on).
- At the bot's real stakes it was +18¢ ± 8, helped by larger stakes on the later, better days.
- Over all its orders, the win rate beat the price by **+1.2 points**, or **+1.6** counting markets that went unfilled. That is the favourite–longshot bias (favourites win a bit more often than their price says) the strategy relies on.

| Band | Bets | Lost | Implied |
|---|---|---|---|
| 90–92¢ | 178 | 20 | 16.6 |
| 92–94¢ | 146 | 5 | 10.1 |
| 94–96¢ | 174 | 4 | 8.6 |
| 96–98¢ | 191 | 3 | 5.6 |
| 98–99.9¢ | 157 | 0 | 2.0 |

90–92¢ is still the only band losing more often than its price (p = 0.23), as before. The backtest doesn't support dropping it.

**Noise, not rules:**
- The slices by coin, hour, weekday or weekend, and window size all sit within chance, given how many slices were looked at.
- YES favourites lost 11 against 21.5 implied, and NO favourites 21 against 21.5. That is likely regime (crypto rose this week), not a rule.

## 2. Execution is the biggest lever

- **Fill share** (contracts filled ÷ contracts asked) was 60% from Oct 10 to 13: 51% on Oct 10, rising to 62%. 25% of orders got nothing.
- **Missed markets were better than filled ones.**
  - The 292 orders that got nothing won 97.6% of the time: 7 lost against 14.9 implied.
  - Filled at full size at the ask the bot saw, they'd have made +$223. The unfilled remainders of partial fills add +$54.
  - Those offers were gone, so this is a ceiling, not money lost. But it's about the same size as the realised P&L.
- **This is adverse selection** (getting filled more often on the worse bets). In the backtest, minute-8 bets whose ask then rose won big (+22.5¢ per $10). Rising asks are exactly when offers vanish before the bot arrives.
- **No size limit yet.** Fill share was flat across order sizes: 57–64% for $10–40 orders.

## 3. The PC clock is drifting, and the bot is entering later each day

- **The PC's time-sync service is not running.** At 7:41 PM ET on Oct 13, the PC was **1.02 s behind** time.google.com.
- **Kalshi's own timestamps** on the bot's orders show the gap between Kalshi's clock and this PC's clock growing from ~0 s (Oct 9–10) to ~1.8 s (Oct 13). That fits the 0.5 s a day of drift found on Oct 11.
- The bot times minute 8 from the PC clock (`bot.py` step). Orders now reach Kalshi a **median 4.1 s after the mark** (Oct 13), against 3.1 s on Oct 12.
- Matching each order with the book read at the mark, **each extra second of lateness costs about 2.6 points of fill share (±1.6)**.
- `lab/fast_entry/timing.md` found 58% of the cheap volume gone by 482.4 s. Left alone, the drift adds about 0.5 s a day.

## 4. The paper experiments (Oct 12, 4:38 PM – Oct 13, 7:30 PM ET; 419 orders)

**+1¢ limit (paper):**
- It would have filled **95.6% of contracts against 62.0% real**.
- The extra contracts cost only **+0.35¢** over the ask the bot saw, on average.
- Realised result: +$171.56 on the extra contracts. The real P&L on the same orders was $63.65.
- That realised figure is lucky: 1 loss in 176 orders, against about 4 expected. Expected value depends on the true edge:

| Assumed edge over the ask | Expected value of the extra contracts |
|---|---|
| 0 | −$27 |
| +0.5 pt | −$6 |
| +1.3 pt (what the backtest and live imply) | **+$26 (+6.5¢ per $10)** |

- Its own rule waits for 1,000 orders, about Oct 16.

**Fast entry (paper):**
- A book read at the mark (0.21 s after) would have filled **69.9% against 62.4%**.
- P&L would have been $132 against $64 real. Most of the difference comes from 93 orders that got nothing live but would have filled at the mark (0 lost, +$82).
- This is an upper bound: no real order lands 0.2 s after the mark.

## 5. Things that don't help

- **Stop-loss exits** (backtest, 20 versions: sell if the favourite's bid is under 30–80¢ at the end of minute 10–14):
  - They lost money in nearly every version, by up to −$932 on a $1,535 total. The one exception was +$28.
  - Sagging favourites recover more often than their bid implies, and selling pays the spread plus a second fee.
  - **Hold to settlement.**
- **Retry unfilled orders at minute 9:**
  - Live, it would have made +20¢ per $10 on 264 markets.
  - The backtest says only +2.6¢ [0.0, +5.3] against +4.5¢ at minute 8. Weak; the +1¢ limit gets the same fills cheaper.
- **Warning-sign skips** (spread ≥ 2¢, a jump of 10¢+ in minute 8, late favourite):
  - The 230 skipped in-band favourites lost 13 against 16.1 implied, about +$21 at $10 each.
  - Too few to overturn the backtest. Keep them.
- **85–90¢ favourites** (not bet): 64 lost of 512 against 66.4 implied. Fairly priced, so negative after fees. Keep the 90¢ floor.

## 6. Risk and operations

- **The window cap cut stakes on 41% of bets** (windows with 7+ bets).
  - The median window had 5.9% of the bankroll at risk; the most was 19.3%.
  - Worst window: −4.7% of the bankroll, Oct 12 at 11:30 PM ET, when platinum, gold and silver lost together. Metals move together like crypto does.
- **Missed windows:**
  - 12 of 366 windows since Oct 10 had no decisions at all: restarts on Oct 10 (9–10 PM) and Oct 11 (10:45 AM – 12:30 PM).
  - There was also a Kalshi-unreachable halt on Oct 11, 6:08–6:23 PM.
  - About 3% of windows were lost.

## Recommendations, in order

1. **Sync the clock.** Start the PC's time-sync service, set it to automatic, and resync. This needs admin rights. Do it outside :07–:10, :22–:25, :37–:40 and :52–:55. It needs no bot code change and no restart. It recovers ~1 s now and stops the drift.
2. **Let the +1¢ paper experiment reach 1,000 orders (~Oct 16).** It is pointing positive; turning it live is a separate decision.
3. **Fast entry, live:** waking at the mark instead of on the 3 s loop, with the bot keeping its own clock offset to Kalshi. Paper says +7.5 points of fill share. It is parked in `lab/fast_entry/`; not yet decided.
4. **Leave alone:** the band floor, the warning signs, holding to settlement, and coin, hour or side filters.
