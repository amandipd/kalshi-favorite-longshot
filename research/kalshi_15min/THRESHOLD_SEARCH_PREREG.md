# Re-tuning the two filters' thresholds: what is being tested, written before any result is read

*Oct 25, 2026. Written and saved before the first score, for the same reason as FILTER_SEARCH_PREREG.md: four
results on Oct 24 looked positive and were hollow, each because a choice was made after the data was seen.*

## The question

The live bot's edge is in its two warning signs, not its price floor — on held-out data the 92c floor alone
returns **−0.272c per $1** and adding both signs turns that into **+0.524c**. Yesterday's search asked whether
*different* features beat them; all eight failed. This asks a narrower question that has never been asked:

**Are the two signs we already have set at the right thresholds?**

## What the thresholds are now

From `strategies_backtest.skipped`, mirrored in `bot.warning`, at entry minute M = 8 on the favourite's own
quote. Three numbers, each chosen once in October and never revisited:

| | now | what it does |
|---|---|---|
| **spread cut** | **2c** | skip when the favourite's ask is this far or further above its bid |
| **jump cut** | **10c** | skip when its mid rose this much or more during minute 8 |
| **coin-flip cut** | **50c** | skip when its mid was this or lower at minute 6 or 7 |

## What will be searched

Each threshold on its own, with the other two held at today's value. One at a time rather than a full grid:
3 × 6 = 18 fits instead of 216, which keeps the multiple-testing risk small and readable.

- **spread cut:** 1, 1.5, 2, 2.5, 3, 4 cents, and off
- **jump cut:** 5, 7.5, 10, 12.5, 15, 20 cents, and off
- **coin-flip cut:** 40, 45, 50, 55, 60 cents, and off

## Method, fixed in advance

1. Split the history by date at its midpoint: first half train, second half test.
2. On the **train half only**, score every value of each threshold.
3. Pick the best value for each threshold **by total profit at $10 flat staking**, which trades edge against
   bet count without letting either dominate. Record every value tried.
4. Score the chosen combination **once** on the test half, against today's settings on the same windows and
   the same fills.
5. Report for every variant: cents per $1, bet count, total profit, the 95% interval clustered by window,
   and the deepest fall.

## Why the criterion is total profit, not cents per $1

Cents per $1 alone would always favour the tightest threshold, because skipping more bets raises the average
while shrinking the business — the trap band weighting fell into, where "Kelly sizing" turned out to be "bet
half as much" in disguise. Total profit at a flat stake is edge multiplied by volume, so a threshold only
wins by being better overall rather than just pickier.

Bet count is reported beside every number so the trade-off stays visible.

## Stop rule

If no threshold beats today's value on the test half, today's settings stand and the search ends. No second
pass, no widening of the grid after seeing the answer, and the count of values tried is reported either way.

## Prior

Low to moderate. These numbers came out of the October warning-sign work, so they are not arbitrary — but
they were picked once, on a single period, and the three of them were never scored against alternatives. The
cheapest possibility is that one is slightly mis-set and a few per cent of profit is sitting there. The most
likely outcome, on yesterday's evidence, is that they are already about right.
