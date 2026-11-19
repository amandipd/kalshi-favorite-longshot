# Kalshi vs Polymarket US: BTC 15-minute markets

*Oct 16, 2026. Data: the venue recorder's Polymarket US books and results (Oct 13 3:53 PM – Oct 16 3:20 AM ET, with a gap Oct 15 10:42 PM – Oct 16 1:18 AM), plus Kalshi's KXBTC15M results and 1-minute quotes for the same windows. Scripts were one-off files, not in the repo.*

## The answer

1. **They settle the same, almost always.** In all 206 fifteen-minute windows both exchanges settled, the target price, the final price and the result matched to the cent. All 51 one-hour Polymarket windows matched Kalshi's numbers at the same hour marks. A wider check back to Polymarket's launch tells the same story with one exception. In its first three days (Sep 22–24), Polymarket sampled the price one second late, and **1 of 209 windows settled opposite ways**, so both legs of a pair lost. Since Sep 28, 1,720 boundaries in a row have matched to the cent. So it's close to a lock, not a perfect one. Kalshi has no 1-hour up/down market, so only the 15-minute windows can be paired.
2. **Arbitrage: not proven, and probably too thin.** Under a fair test, a typical Up + Down pair cost **0.8–1.4¢ more than the $1 it pays**, after fees. Only about **2%** of moments stayed profitable once Kalshi's price movement inside the minute was allowed for. The big "gaps" in the raw data came from stale Polymarket books. To test it properly, you'd need both live books at the same instant, which means Polymarket's WebSocket and an account.
3. **The favourite strategy on Polymarket US: same bets, a bit dearer, much deeper.** Because both settle on the same number, a Polymarket favourite wins exactly when the Kalshi one does. At minute 8, Polymarket's favourite cost **0.32¢ more** on average (range +0.08 to +0.56¢), and fees are about the same. But Polymarket showed a median of **about 3,800 contracts** at the favourite's price, where the Kalshi bot gets 13–25 at a time. Expect a thinner edge per dollar and far more room to bet. It's BTC only: about 18 bets a day.

## 1. Settlement: same index, same numbers

Kalshi's rule: Yes if the simple average of the 60 seconds of CF Benchmarks' BRTI before the close is **at least** the same average before the open. (BRTI is CF Benchmarks' real-time bitcoin price index.)

| Check | Windows | Matched |
|---|---|---|
| 15-min target price (start value) | 206 | 206 |
| 15-min final value | 206 | 206 |
| 15-min result (Up/Down) | 206 | 206 |
| 1-hour start and final value vs Kalshi's 15-min values at those times | 51 | 51 |

Polymarket gave no numbers on 2 of the 206 windows. Their results still matched. No window ended in an exact tie. The closest finish was $0.03 from the target, and 2 finished within $1. **A tie is the one place the two could differ** (see the rules section).

## 2. Arbitrage: the gaps don't survive a fair test

**How a pair works.** Buy Kalshi Up at its ask and Polymarket Down at its ask, or the other way round. One side pays $1. Profit = $1 − both prices − both fees. Both exchanges charge about 7% × price × (1 − price) per contract, so fees are largest near 50/50 (about 1.75¢ a side) and small near 95/5.

**The raw comparison is misleading.** Matching each Polymarket book to Kalshi's quote at the nearest minute mark (within 15 s), 30% of moments looked profitable after fees. Some "profits" were 60–70¢. Those were not real:

- **Polymarket's public data is cached.** A book read through the public website was a median **15 seconds old**, and only 14% were under 3 seconds old.
- **One window's Polymarket book sat frozen** at 72¢ for 8 minutes while Kalshi's price fell from 44¢ to 0¢. Nobody could have traded against that.
- **Prices move fast near 50/50.** A few seconds' difference between the two quotes is enough to fake a 1–2¢ gap.

**The fair test.** Polymarket books 5 seconds old or less, Kalshi quotes within 5 seconds, and the last minute left out:

| Rule for a match | Pairs | Windows | Profit > 0 after fees | Still > 0 at Kalshi's worst quote that minute | Median pair after fees |
|---|---|---|---|---|---|
| PM ≤ 3 s old, Kalshi within 3 s | 40 | 9 | 20% | 0% | −0.81¢ |
| PM ≤ 3 s old, Kalshi within 5 s | 101 | 15 | 20% | 2% | −1.37¢ |
| PM ≤ 5 s old, Kalshi within 5 s | 166 | 22 | 18% | 2% | −1.42¢ |

On average, the two exchanges' mid prices agree (median gap 0.00¢), and both spreads are usually 1¢. A pair therefore usually costs about $1.01 plus fees. **A real gap would need the prices to drift 2–4¢ apart and stay there long enough to buy both sides.** We can't rule out short gaps, but nothing here shows them, and fast bots would be racing for any that exist.

**Other catches:**

- **Leg risk.** You buy one side and miss the other. The Kalshi bot fills only about 60% of what it asks for.
- **Cash on both exchanges.** Each pair ties up about $1 of cash per contract, split across two accounts.
- **Rule mismatches.** Ties, halts and voided markets; see below.

## 3. The favourite strategy on Polymarket US

At minute 8 of each window, buy the favourite if it costs 92¢ or more. This is the live bot's rule, applied to Polymarket's book nearest to minute 8. That book was a median 7 s from minute 8 and about 15 s old.

| | Bets (of 205 windows) | Lost | Implied losses | ¢ per $1 |
|---|---|---|---|---|
| Polymarket US, its own 92¢+ favourites | 39 | 1 | 1.8 | +1.76 |
| Kalshi, same windows, its own 92¢+ favourites | 34 | 1 | 1.5 | +1.20 |

That's far too few bets to judge win rates. The useful comparison is **price, since outcomes are identical**:

- **Same window, same side, both at 92¢ or more (34 pairs):** Polymarket was dearer in 21, cheaper in 10 and equal in 3. The mean gap was **+0.32¢** (95% range +0.08 to +0.56¢).
- **Fees:** Kalshi 0.29¢ vs Polymarket 0.27¢ per contract at these prices.
- **Price steps:** Polymarket only quoted whole cents. Kalshi uses 0.1¢ steps above 90¢.
- **Size on offer at the favourite's price on Polymarket:** median about 3,800 contracts, ranging from 465 to 17,495.

**What that implies.** Kalshi's BTC favourites at 92¢+ earned **+0.93¢ per $1** in the backtest (Dec 10 – Oct 12, 4,651 bets, ±0.5¢ a contract), and **+1.60¢** from Aug 12. Live, 71 BTC bets made +3.55¢ per $1, with 0 losses against 2.7 implied, which is luck. Subtract Polymarket's ~0.3¢ higher price and **a Polymarket favourite should earn roughly +0.6 to +1.3¢ per $1**. That's thinner per dollar. But with thousands of contracts on offer, it could carry much bigger bets than Kalshi's thin books allow.

Before trusting the depth number, three caveats:

1. The books came through a cache and were about 15 s old.
2. The size field's units weren't checked against a real order.
3. Big quotes from market makers can vanish when you try to take them.

## Rules side by side

From each exchange's own docs and rules, checked Oct 16. Kalshi's newest fee page couldn't be loaded, so its fee row comes from the Feb 2026 schedule.

| | Kalshi KXBTC15M | Polymarket US BTC Up/Down |
|---|---|---|
| Index | CF Benchmarks BRTI | BRTI. A press report saying Chainlink is wrong. |
| Value at a time T | Simple average of the 60 seconds of BRTI before T, to 2 decimals | 60 one-second prices before T, to 2 decimals |
| Start ("target") price | Same average at the window's start = the last window's final value | Same |
| Exact tie | "At least" means **Yes/Up** | "A flat print settles Up" |
| Windows | :00/:15/:30/:45 UTC. The ticker shows the **close** time in **Eastern** time | Same windows. The name shows the **start** time in **UTC** |
| Taker fee | 7% × price × (1 − price), rounded up to the cent, with rounding tracked per order | 6.95% × price × (1 − price), rounded to the nearest cent |
| Maker fee | None | A rebate now. From Oct 19 it's tiered, and zero under $10M of maker volume a month |
| Price step | 0.1¢ under 10¢ and over 90¢, 1¢ between | 1¢ |
| Missing index data | The market resolves **No** | Settlement waits; the exchange may decide by review |
| Weekly downtime | Thursday 3–5 AM ET | Thursday 6–8 AM ET; no windows overlap it |
| 1-hour up/down | **None** (only fixed-strike and range markets) | Yes |

**Ways a pair could still lose on both sides, most likely first:**

1. **Polymarket's price sample slips.** This has happened twice: the Sep 22–24 launch bug, and one second on Sep 28. A slip only flips a result when the window moved less than the error, usually a few cents to a few dollars.
2. **An index outage.** Kalshi resolves No, while Polymarket waits or reviews. The safe way round is Kalshi Down + Polymarket Up. The other way round can lose both legs.
3. **A manual review or "obvious error" reversal on one exchange only.**
4. **A busted trade on one leg.** Polymarket can cancel fills more than 20¢ from fair value, which would leave you holding one unhedged side.
5. **A halt that leaves you half-filled.**

**Data access on Polymarket US.** The public book and price feeds are cached for up to 30 seconds, which explains the 15-second-old books above. Trade history and the live WebSocket both need an account and API key. Stored market data is kept for 45 days.

**Not verified:** which US states Polymarket US blocks. One third-party list includes **Ohio**, where Kalshi's servers (and so any server placed near them) sit. Check that before building anything there.

## What it would take

- **To test arbitrage properly:** record both exchanges' live books at the same instant. That means Kalshi's WebSocket plus Polymarket US's WebSocket, which needs a Polymarket US account and API key. Ideally both run from a server near Kalshi's.
- **To trade the favourite strategy on Polymarket US:**
  - an account and funding (card and ACH deposits take 3–4 business days to clear);
  - checking whether Polymarket US allows trading from the server's location;
  - an order client for Polymarket US's API;
  - checking that the quoted size really fills at minute 8;
  - deciding how cash is split between exchanges.
- **The live Kalshi bot doesn't change.** The 6-week test runs unchanged to Nov 27.
- **The recorder stopped** at 3:20 AM ET on Oct 16. Restarting it adds data until Oct 20.
