# Every loss in the live test so far (Oct 27, 8:06 PM ET)

**Short answer: 70 of 2,461 bets lost, costing $1,028. Prices predicted 92.5 losses, so the bot still loses fewer than prices say. Since Oct 20 that gap has nearly closed. Most of the change comes from two windows where nearly every crypto coin moved the same way at once and the bot's No-side bets lost together. Without those two windows, the bot since Oct 20 looks like its usual self.**

Data: every settled bet from the start of the server run (Oct 15) to Oct 27, 8:06 PM ET, from the live bot's ledger, read-only.

## How to read the numbers

- **"Prices predicted"** means: for each bet, 1 minus the price paid, added up. A 95-cent price means the market thinks there is a 5% chance of losing.
- **"Ratio"** is losses divided by what prices predicted. Under 1 means the bot lost less often than the market expected. That gap is the edge (the bot's profit source). The bot's backtests and its record before Oct 20 run at about 0.5 to 0.7.
- **"Chance"** is how often a slice would land this far from normal by luck alone, if it lost at the bot's test-wide rate (0.76 of prices). Low means unusual. About 60 slices were checked, so about 3 will look unusual (under 5%) by luck alone.

## The totals

- 2,461 bets settled. 2,391 won and 70 lost.
- Wins made $1,245.96. Losses cost $1,027.59. Net +$218.37, or +0.63 cents of profit for every dollar bet.
- The average win is $0.52. The average loss is $14.68. **One loss wipes out about 28 wins.** That is the nature of buying favourites (the likely side) at 92 to 99.9 cents.
- Losses have grown from about $14 to $16 early on to about $18 to $20 now. Bets are 1.5% of the account, and the account has grown.
- Lost 70 where prices predicted 92.5. Ratio 0.76.

## Before and since the +1 cent limit (Oct 20, 7:53 PM ET)

- **Before:** lost 17 where prices predicted 34.2. Ratio 0.50. +1.68 cents for every dollar bet.
- **Since:** lost 53 where prices predicted 58.3. Ratio 0.91. +0.15 cents for every dollar bet.

## The main finding: No-side bets since Oct 20, and two windows

**By side, over the whole test:**

- Yes side: lost 22 where prices predicted 47.9. Ratio 0.46. +1.97 cents for every dollar bet.
- No side: lost 48 where prices predicted 44.6. Ratio 1.08. −0.78 cents for every dollar bet.

**Split by date, the problem is only since Oct 20:**

- No side before Oct 20: lost 10 where prices predicted 17.1. Ratio 0.59. +1.00 cents for every dollar bet. Normal.
- No side since Oct 20: lost 38 where prices predicted 27.5. Ratio 1.38. −1.67 cents for every dollar bet. Chance by luck about 1 in 1,000 (0.1%). The most unusual slice found.
- Yes side since Oct 20: lost 15 where prices predicted 30.8. Ratio 0.49. +1.79 cents. Normal.
- Within the No side since Oct 20, it is mostly crypto: 28 losses where prices predicted 19.6.

**Most of it is two windows:**

- **Oct 21, 4:30 AM ET:** 5 crypto No-side bets lost together (ETH, XRP, DOGE, SOL, BTC).
- **Oct 22, 9:30 PM ET:** 7 crypto No-side bets lost together (DOGE, ZEC, HYPE, SOL, BNB, ETH, XRP), most at 95 to 99 cents.
- In both, nearly every crypto coin moved the same way late in the window. Every No-side favourite flipped at once. Together the two windows lost $142.63.
- **Leave those two windows out** (a leave-one-out check: drop the biggest contributors and see if the result survives):
  - No side since Oct 20: lost 26 where prices predicted 27.0. Ratio 0.96. −0.38 cents. Still no edge, but no longer unusual (chance 25%).
  - Everything since Oct 20: lost 41 where prices predicted 57.7. Ratio 0.71. **+0.77 cents for every dollar bet**, instead of +0.15. That is close to the bot's usual rate.

**What it means:**

- The Oct 20 drop is not a steady slide. It is mostly two rare, crypto-wide events.
- Those events are real risk, not bad data. They will happen again. The question for Nov 27 is how often.
- It is not the +1 cent limit. No-side bets lost too often whether they paid at or under the price the bot saw (24 where prices predicted 18.2) or above it (14 where prices predicted 9.3).
- It fits the Oct 21 loss-clustering study: losses bunch up in the same window. Here, 12 windows with 2 or more losses hold 32 of the 70 losses and $443 of the $1,028.

## By market type

- Crypto: lost 50 where prices predicted 67.9. Ratio 0.74. +0.68 cents for every dollar bet.
- Metals: lost 10 where prices predicted 15.0. Ratio 0.67. +1.31 cents.
- Energy: lost 10 where prices predicted 9.5. Ratio 1.05. −1.00 cents. No edge so far, but only 203 bets.

## By market

No single market stands out. Every one is within luck (chance 30% or more).

- Best: palladium (0 losses where prices predicted 1.9), DOGE (3 where 7.2), NEAR (3 where 7.3).
- Worst: oil (WTI, 6 where 4.8, −2.08 cents), Bitcoin (8 where 7.9, −0.73 cents), XRP (7 where 7.5).
- Dropping markets after the fact has cost money before (Oct 13 live check), so this is not a reason to act.

## By price paid

| Price paid | Bets | Lost (prices predicted) | Ratio (under 1 = edge) | Cents of profit per dollar bet |
|---|---|---|---|---|
| Under 92c (filled below the seen price) | 7 | 2 (0.6) | 3.40 | −17.11 |
| 92 to 93c | 213 | 16 (16.2) | 0.99 | −0.82 |
| 93 to 94c | 242 | 11 (15.9) | 0.69 | +1.89 |
| 94 to 95c | 253 | 9 (14.2) | 0.64 | +1.32 |
| 95 to 96c | 299 | 14 (13.7) | 1.02 | −0.31 |
| 96 to 97c | 359 | 6 (13.0) | 0.46 | +1.69 |
| 97 to 98c | 363 | 5 (9.4) | 0.53 | +0.79 |
| 98 to 99c | 503 | 6 (7.8) | 0.77 | +0.42 |
| 99c and up | 223 | 1 (1.8) | 0.55 | +0.27 |

- The 92 to 93 cent band (price range) has shown no edge. It was already on the watch list. The Oct 14 floor research and the Oct 25 threshold check both said to keep it.
- The 95 to 96 cent band also shows none. With eight bands, one or two looking flat is expected by luck. None is unusual (all chances 27% or more).

## By time

- **Weekends did much better:** lost 9 where prices predicted 21.7 (ratio 0.41, +1.95 cents). Weekdays lost 61 where 70.8 (ratio 0.86, +0.23 cents). Chance by luck about 7%. Worth watching, not acting on.
- **By time of day (ET):** 8 PM to midnight ET was worst, 20 losses where prices predicted 17.9 (ratio 1.11). It holds the Oct 22 window. 4 PM to 8 PM ET was best, 6 where 12.4. None is unusual (chance 11% or more).
- **By day:** Oct 27 was the worst day, 11 losses where prices predicted 6.9, −$90.83 (chance 3%). Oct 17 had no losses at all. Oct 21 and 22 were flat.

## Every loss

Times are window start, ET. "Price" is what the bot paid per contract.

| When (ET) | Market | Side | Price | Lost |
|---|---|---|---|---|
| Oct 16 Fri 1:15 AM | Natural gas | Yes | 94.0c | $14.16 |
| Oct 16 Fri 3:15 AM | Copper | Yes | 93.0c | $2.07 |
| Oct 16 Fri 4:30 AM | Gold | No | 91.1c | $14.67 |
| Oct 16 Fri 1:15 PM | Oil (WTI) | No | 93.3c | $15.00 |
| Oct 18 Sun 10:15 AM | NEAR | Yes | 92.5c | $9.09 |
| Oct 18 Sun 7:00 PM | Oil (WTI) | Yes | 92.6c | $15.82 |
| Oct 19 Mon 1:15 AM | Copper | Yes | 93.0c | $7.22 |
| Oct 19 Mon 2:00 AM | Oil (WTI) | No | 92.1c | $16.67 |
| Oct 19 Mon 6:30 AM | SOL | No | 98.9c | $15.84 |
| Oct 19 Mon 6:30 AM | HYPE | No | 95.9c | $16.35 |
| Oct 19 Mon 9:00 AM | NEAR | Yes | 95.9c | $16.35 |
| Oct 19 Mon 4:45 PM | BNB | No | 95.4c | $0.02 |
| Oct 19 Mon 4:45 PM | HYPE | No | 94.4c | $13.27 |
| Oct 19 Mon 10:00 PM | BNB | No | 96.1c | $11.56 |
| Oct 20 Tue 10:45 AM | ZEC | No | 92.6c | $13.03 |
| Oct 20 Tue 10:45 AM | ETH | No | 91.9c | $12.94 |
| Oct 20 Tue 4:30 PM | BNB | Yes | 95.2c | $1.91 |
| Oct 20 Tue 8:45 PM | DOGE | Yes | 96.2c | $17.36 |
| Oct 20 Tue 8:45 PM | ETH | Yes | 93.6c | $17.86 |
| Oct 20 Tue 11:45 PM | Natural gas | No | 92.0c | $17.58 |
| Oct 21 Wed 3:30 AM | HYPE | No | 92.0c | $17.59 |
| Oct 21 Wed 4:30 AM | ETH | No | 99.5c | $13.93 |
| Oct 21 Wed 4:30 AM | XRP | No | 96.7c | $13.57 |
| Oct 21 Wed 4:30 AM | DOGE | No | 92.8c | $13.99 |
| Oct 21 Wed 4:30 AM | SOL | No | 95.0c | $14.30 |
| Oct 21 Wed 4:30 AM | BTC | No | 95.1c | $14.31 |
| Oct 21 Wed 12:30 PM | Silver | No | 94.1c | $17.01 |
| Oct 21 Wed 12:30 PM | Gold | No | 97.9c | $16.67 |
| Oct 22 Thu 1:45 AM | BTC | No | 94.4c | $17.06 |
| Oct 22 Thu 9:30 PM | DOGE | No | 98.4c | $10.84 |
| Oct 22 Thu 9:30 PM | ZEC | No | 95.5c | $10.54 |
| Oct 22 Thu 9:30 PM | HYPE | No | 98.5c | $10.85 |
| Oct 22 Thu 9:30 PM | SOL | No | 98.8c | $10.88 |
| Oct 22 Thu 9:30 PM | BNB | No | 98.9c | $10.89 |
| Oct 22 Thu 9:30 PM | ETH | No | 98.5c | $10.85 |
| Oct 22 Thu 9:30 PM | XRP | No | 96.9c | $10.68 |
| Oct 22 Thu 9:45 PM | XRP | Yes | 94.3c | $17.04 |
| Oct 23 Fri 3:30 AM | BTC | Yes | 92.0c | $10.18 |
| Oct 23 Fri 3:30 AM | SOL | Yes | 95.2c | $10.51 |
| Oct 23 Fri 4:30 AM | ZEC | No | 94.9c | $17.14 |
| Oct 23 Fri 3:15 PM | BNB | No | 97.8c | $17.63 |
| Oct 23 Fri 10:15 PM | BTC | No | 92.0c | $17.58 |
| Oct 23 Fri 10:15 PM | ETH | No | 95.4c | $18.18 |
| Oct 24 Sat 7:15 PM | BNB | No | 96.8c | $18.44 |
| Oct 24 Sat 10:00 PM | XRP | Yes | 93.8c | $17.90 |
| Oct 24 Sat 10:00 PM | HYPE | Yes | 93.7c | $8.12 |
| Oct 24 Sat 11:15 PM | NEAR | Yes | 95.1c | $18.14 |
| Oct 25 Sun 7:30 AM | ZEC | No | 95.3c | $18.17 |
| Oct 25 Sun 2:15 PM | ZEC | Yes | 96.8c | $18.43 |
| Oct 25 Sun 11:45 PM | BTC | No | 92.4c | $18.58 |
| Oct 26 Mon 3:30 AM | HYPE | No | 96.0c | $19.25 |
| Oct 26 Mon 4:45 AM | Silver | Yes | 93.3c | $18.75 |
| Oct 26 Mon 8:15 AM | ETH | No | 93.5c | $18.79 |
| Oct 26 Mon 8:15 AM | BTC | No | 92.9c | $18.67 |
| Oct 26 Mon 10:15 AM | BTC | Yes | 92.5c | $8.37 |
| Oct 26 Mon 11:30 AM | Oil (WTI) | No | 93.9c | $13.20 |
| Oct 26 Mon 3:15 PM | XRP | Yes | 95.8c | $18.26 |
| Oct 26 Mon 9:15 PM | Gold | No | 97.1c | $10.70 |
| Oct 26 Mon 9:30 PM | Oil (WTI) | No | 92.0c | $18.50 |
| Oct 27 Tue 3:30 AM | Natural gas | No | 93.0c | $19.63 |
| Oct 27 Tue 5:45 AM | Platinum | No | 97.6c | $19.55 |
| Oct 27 Tue 8:45 AM | XRP | Yes | 95.5c | $19.16 |
| Oct 27 Tue 9:00 AM | Oil (WTI) | Yes | 92.8c | $18.65 |
| Oct 27 Tue 9:45 AM | Gold | No | 92.2c | $9.27 |
| Oct 27 Tue 10:15 AM | BNB | No | 97.0c | $18.47 |
| Oct 27 Tue 10:15 AM | BTC | No | 92.4c | $18.58 |
| Oct 27 Tue 12:00 PM | Natural gas | Yes | 94.9c | $18.10 |
| Oct 27 Tue 1:45 PM | HYPE | No | 94.0c | $16.99 |
| Oct 27 Tue 3:45 PM | XRP | No | 94.3c | $18.00 |
| Oct 27 Tue 7:30 PM | Silver | No | 94.1c | $17.95 |

Small losses ($0.02 to $9) are partly filled orders, or half-size bets when a window had many favourites.

## What to do

- **Nothing before Nov 27.** The test plan freezes the bot until then.
- **At Nov 27, read the result two ways:** with and without crypto-wide windows like Oct 21 and Oct 22. If the bot only shows an edge without them, the real question becomes how often those windows happen. That is a sizing question, not a "skip No bets" question.
- **A useful check, analysis only:** in the backtest's months of past data, how often did a whole crypto window flip against the favourites, and did No-side favourites do worse than Yes-side ones? That says whether two such windows in a week is normal or unlucky.

Scripts: `losses.py` and `losses2.py`, one-off scripts not in the repo (data `allbets.json`). Ledger read-only. Nothing in `bot/` was touched.
