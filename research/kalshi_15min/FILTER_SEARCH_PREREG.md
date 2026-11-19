# Entry-filter search: what is being tested, written down before any result is read

*Oct 24, 2026. This file is the pre-registration. It is written and committed before the first score is
computed, so that what gets reported cannot be chosen after seeing the answer. Three results earlier today
(Coin Race, the 26 state gas series, daily diesel) were positive on their face and hollow underneath, in each
case because a slice was picked after the data was seen. This is the guard against repeating that.*

## The question

The live bot's edge does not come from its 92c price floor. Scored on the bot's own markets, the floor alone
returns **−0.15c per $1 staked**. Essentially all of the edge comes from the two warning signs the bot skips
on. Those two filters read six numbers out of the sixteen available at the entry minute.

**Can any feature of the first eight minutes' quote path beat the two filters the bot uses today?**

## What the bot does now (`strategies_backtest.skipped`, mirrored in `bot.warning`)

At entry minute M = 8, on the favourite's own quote:

- **`spread`** — skip when the favourite's ask is 2c or more above its bid at minute 8.
- **`late`** — skip when its mid rose 10c or more during minute 8, or when its mid was 50c or under at
  minute 6 or minute 7.

## The eight candidate features

All are computable at the end of minute 8 from minutes 1–8 only. None may read minute 9 or later, the
settlement, or anything else unavailable to the live bot at the moment it sizes an order.

Replacements for the spread sign (it is a thin-book proxy):

1. **`mean_spread_5_8`** — mean of (own ask − own bid) over minutes 5–8. A market tight all window is not the
   same as one tight at the instant it was read.
2. **`rel_spread`** — the minute-8 spread divided by that series' median minute-8 spread. 2c means something
   different in BTC than in ZEC; the current filter treats them alike. **The per-series medians are computed
   on the train half only** and reused unchanged on the test half.
3. **`spread_trend`** — spread at minute 8 minus spread at minute 5. Narrowing into entry versus widening.

Replacements for the late sign (it asks whether the favourite is settled):

4. **`fav_minutes`** — how many of minutes 1–8 this side was the favourite. The current filter looks two
   minutes back; this counts the whole path.
5. **`travel`** — sum of |mid(k) − mid(k−1)| over minutes 2–8. Did the price sit at 95c or wander there?
6. **`worst_dip`** — mid at minute 8 minus the lowest mid over minutes 1–8.
7. **`since_coinflip`** — minutes since the mid was last 50c or under (8 if never). A continuous form of the
   current 50c check.

Not covered by either sign:

8. **`staleness`** — consecutive minutes ending at minute 8 whose (bid, ask) is unchanged. An unmoving quote
   may not be a real one, and its "favourite" may be a ghost.

## Method, fixed in advance

1. Split the history by date at its midpoint. The first half is train, the second is test.
2. On the **train half only**, for each feature, search thresholds for the one that most improves cents per
   $1 **while keeping at least as many bets as the current two filters keep**. Record every threshold tried.
3. Choose **at most two** new features, on the train half alone.
4. Score **once** on the test half, against the current two filters on the same windows and the same fills.
5. Report, for every variant: cents per $1, bet count, the 95% interval clustered by window, and the deepest
   fall.

## The control that decides it

**Bet count is reported beside every result.** A filter that appears better by betting less is not better —
that is precisely the trap band weighting fell into earlier today, where "Kelly sizing" turned out to be
"stake half as much" in disguise. To pass, a candidate must earn more per dollar **at the same or a higher
bet count** than the current filters, by a margin wider than its own uncertainty.

Intervals cluster by window, because bets placed in one window rise and fall together.

## Stop rule

If nothing beats the current two filters on the test half, the answer is no and the search stops there. No
features beyond the eight above, and no second pass of thresholds against the test half. The count of
thresholds tried is reported either way, so the multiple-testing risk is visible rather than hidden.

## Prior

Modest. These two filters came out of the October warning-sign work (`findings.py`), so this ground has been
searched once already; the search is for what that pass missed, not virgin territory. What keeps it worth
doing is that the filters are known to carry the entire edge while reading a fraction of the data, and that
the whole test runs on history already on disk.
