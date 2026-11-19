# Sell the other coins when one turns: FAIL (Oct 28)

**Short answer: it doesn't work. By the time one coin's favourite (the likely side) collapses, Kalshi has already marked the other coins down 4 to 10 cents in the same minute. After that, they win about as often as their new price says. Selling them then just pays the spread (the gap between the buy and sell price) and a second fee, for nothing. All four pre-set versions failed the pass bar written down before the test.**

## The question

The bot buys crypto favourites at minute 8 and holds them to the close. Crypto coins move together, so several bets in one window can flip at once (live: Oct 21, 4:30 AM ET and Oct 22, 9:30 PM ET). The idea: when one held coin collapses during minutes 9 to 14, sell the others before they flip too.

An Oct 9 study already found that selling a coin after its *own* price collapses always loses to holding. This test is different. It sells the coins that have *not* collapsed yet, using another coin as the warning.

## How it was tested

- **The pass bar was written first** (`research/contagion_exit/PREREG.md`, 28 Oct 2026, 6:37 PM EDT, before any result). Its fingerprint (sha256) at that time: `30652b5808779e0126facb7391f77d67aca017e1249c82ccb8bafa0820e2790d`. It was not changed after.
- **Data:** every crypto 15-minute market from Dec 20, 2025 to Oct 8, 2026, with the buy and sell price at the end of each minute (`research/kalshi_15min/lab/markets.npz`). Nothing from the live test.
- **The bot's bets:** the live rule rebuilt (favourites 92 to 99.9 cents at minute 8, both warning signs, Fed blackouts). 26,686 crypto bets of $10. 6,166 windows held 2 or more crypto bets.
- **The rule:** at the first minute from 9 to 14 when at least K held coins can only be sold for T or less (the coin has "turned"), sell every other held coin on the same side that has not turned. Sell at that minute's bid (the price someone will pay now), less Kalshi's fee. Hold the turned coins.
- **The score:** money from selling, minus what holding to the close paid. Positive means selling did better.
- **Pass needed all three:** far from luck (a t-score above 2, where about 2 is the usual bar, counting each window once), better than holding in both the older and newer half of the days (split at May 15), and still better after dropping its single best day.
- **This setup favours selling.** It sells at the same minute-end price the warning is read from. A real bot would sell a moment later, at a worse price, and only as many contracts as buyers want. So a fail here is solid.

## Results

"Sell minus hold" is the extra money selling made over holding, in dollars, over the whole 10 months at $10 a bet. Negative means holding was better.

| Version | Windows it fired in | Sell minus hold | How far from luck (2 is the bar) | Verdict |
|---|---|---|---|---|
| 1 coin turned, sells at 70c or less | 687 | −$84.57 | −0.62 | Fail |
| 1 coin turned, sells at 50c or less | 454 | +$11.34 | +0.09 | Fail |
| 2 coins turned, sells at 70c or less | 164 | −$10.20 | −0.15 | Fail |
| 2 coins turned, sells at 50c or less | 101 | +$10.82 | +0.17 | Fail |

- No version comes near the luck bar. The two that are slightly positive turn negative when their best day is dropped (−$43.13 and −$19.80).
- The extra versions, reported but not part of the bar, also fail. At 80c, selling loses $197.81 for one coin and $32.11 for two. At 30c it is +$2.65 and −$47.47.
- For scale: the bot's crypto bets themselves made +$795.33 over the same 10 months at $10 a bet. The best selling version changes that by about $11.

## Why it fails

**The other coins are already marked down when the warning comes.** Price paid at minute 8, and the price they could be sold for at the trigger:

- 1 coin turned, 70c: bought at 96.6c, sell price 92.8c. Already down 3.8 cents.
- 1 coin turned, 50c: bought at 96.6c, sell price 90.3c. Down 6.3 cents.
- 2 coins turned, 70c: bought at 97.0c, sell price 91.2c. Down 5.8 cents.
- 2 coins turned, 50c: bought at 97.0c, sell price 86.6c. Down 10.5 cents.

**And at that new price, they are fairly priced.** How often the sold coins went on to win, against their sell price:

- Sell price 92.8c: won 92.8% of the time.
- Sell price 90.3c: won 89.6%.
- Sell price 91.2c: won 90.9%.
- Sell price 86.6c: won 85.4%.

The win rate matches the price almost exactly. Kalshi's market makers watch all the coins and re-price them together within the same minute. There is no slow price left to catch. Selling at a fair price still costs the fee, so holding comes out ahead or even.

## What it means

- **Crypto-wide flips can't be dodged by selling mid-window,** at least not at minute-by-minute speed. Faster (seconds) would need live order-book data and a bot that can sell. Even then the market makers would likely move first.
- **This closes the "watch minutes 8 to 15" idea for selling.** Together with the Oct 9 exit study, every selling rule tested has lost to holding.
- **The crypto-wide windows stay a cost of the strategy.** The past data shows the edge (the bot's profit source) already pays for them (`reports/Crypto flips and No vs Yes in past data Oct 28.md`).
- **Nothing changes in the bot.**

## Files

- `research/contagion_exit/PREREG.md`: the pass bar, written before any result.
- `research/contagion_exit/contagion_exit.py`: the test. `python contagion_exit.py` prints every version and writes `contagion_exit.json`.
- Analysis only. Nothing in `bot/`, the live server, or the live ledger was touched.
