# Sell the other coins when one turns: pass bar, fixed before any result (28 Oct 2026)

**Question.** The bot buys crypto favourites at minute 8 and holds them to the close. Crypto coins move together, so
several of its bets in one window can flip at once (live: Oct 21, 08:30 UTC and Oct 23, 01:30 UTC). When one held
coin's favourite collapses during minutes 9 to 14, does selling the bot's other crypto favourites in that window, on
the same side, beat holding them?

**What is already known (not retested).** Selling a favourite after its own price collapses lost to holding at every
minute and price level (`research/kalshi_15min/exit_timing.py`, README "When to sell a favorite that turned").
This test is different: it sells the coins that have NOT collapsed yet, using another coin's collapse as the warning.

**Data.** `research/kalshi_15min/lab/markets.npz`: every crypto 15-minute market, Dec 10 2025 to Oct 8 2026, with
the bid and ask at the end of each minute. Nothing from the live test.

**The bot's bets.** `lab/common.py` `live_rule(d, lo=0.92)`: favourites 92 to 99.9c at the end of minute 8, both
warning signs skipped, Fed blackouts skipped. Crypto only. $10 a bet at the minute-8 ask plus 0.4c, whole
contracts. Same as `reports/Crypto flips and No vs Yes in past data Oct 28.md`.

**The rule, fixed now.**

- A window qualifies if the bot holds 2 or more crypto bets in it.
- At the end of each minute m = 9, 10, ..., 14, read each held coin's own bid (the price it could be sold for now).
- A coin has **turned** when its own bid is at or below T.
- **Trigger:** the first minute m at which at least K held coins have turned.
- **Action at the trigger:** every other held crypto coin on the **same side** (Yes or No) as a turned coin, and not
  itself turned, is sold at its own bid at the end of minute m, paying Kalshi's taker fee on the sale
  (`common.fee`). Turned coins are held (selling them is already known to lose). Coins on the other side are held.
- **Score:** for each sold position, (bid x contracts - sale fee) minus what holding pays (contracts if it won, else
  0). Summed per window. Positive = selling beat holding.

**Main cells (picked now, so the result can't pick them).**

| Cell | K (coins turned) | T (bid at or below) |
|---|---|---|
| 1 | 1 | 70c |
| 2 | 1 | 50c |
| 3 | 2 | 70c |
| 4 | 2 | 50c |

**Pass.** At least one main cell has all three:

1. Selling beats holding in total dollars, far from luck: t above 2, clustered on the window (each window is one
   unit).
2. Selling beats holding on both the older half and the newer half of the days (split at the middle day).
3. Selling still beats holding after dropping its single best day.

**Fail.** Every main cell loses to holding, or has t under 1.

**In between.** Positive with t between 1 and 2: reported as unclear. Going on is a separate decision.

**Reported but not part of the bar.** T = 80c and T = 30c for K = 1 and 2; how often each cell triggers; the sold
coins' average bid against how often they went on to win; Jul 18 onward alone (more coins a window).

**Known bias, in selling's favour.** The sale is booked at the same minute-end bid that the trigger is read from.
A real bot would see the trigger and sell a moment later, often at a lower bid, and only as deep as the book allows.
So a fail is solid; a pass would still need a live-book check before any bot change.

**Not touched.** `bot/`, the live server, and the live ledger. Analysis only.
