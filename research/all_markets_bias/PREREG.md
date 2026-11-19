# All-markets favourite-longshot map: pre-registration

Fixed 29 Oct 2026 (04:15 UTC), before any trade or outcome for this study was pulled. The plan in words is
`PLAN.md`. Nothing below changes after the pull starts. Anything decided later is labelled "added after the pull"
in the report.

## Question

Across every Kalshi series, where are favourites (the likely side) underpriced, so that buying them at a price a
real buyer paid, and holding to settlement, makes money after Kalshi's taker fee?

## Data

- **Universe:** every series in Kalshi's `/series` list on 28 Oct 2026, except combo series (ticker starting
  `KXMVE`, or markets carrying an `mve_collection_ticker`) and series with zero lifetime volume.
- **Markets kept:** binary, result `yes` or `no`, closing from 2025-11-01 00:00 UTC to 2026-10-28 00:00 UTC.
- **Listing, newer part:** `/markets?status=settled&mve_filter=exclude`, exchange-wide, one UTC day at a time.
- **Listing, older part (settled before Kalshi's 29 Aug archive line):** `/historical/markets` per series, 200
  a page, newest first, stopping at a close before 2025-11-01 or after **25 pages**. A series that hits the page
  cap is sampled from its newest 5,000 archived markets only. The report lists those series.
- **Halves, by each market's own close time:** train 2025-11-01 to 2026-08-01; test 2026-08-01 to 2026-10-28.
- **Sample:** per series and half, up to **40 events** at random, then up to **5 markets per event** at random.
  Seeded (`20261029`) on series, half and event ticker only. It never reads results. If the dry run says the
  pull would take over 2 days, the cap drops to 25 events. Nothing else may change.

## Checkpoints and prices

- **Checkpoints:** 1, 2, 4, 8, 12, 24, 48, 72, 168, 336 and 720 hours before close, each kept only if it falls
  after the market opened. A market living under 2 hours also gets `half`, the midpoint of its life.
- **Trades used:** each trade's time, Yes price, size and `taker_side` (the side the buyer took).
- **Favourite at a checkpoint:** the side the latest trade at or before it priced above 50c. Exactly 50c: no bet.
- **Entry price:** the latest trade at or before the checkpoint whose buyer took the favourite side, at most 60
  minutes old. Its price is what that buyer paid (the Yes price, or 100 minus it for No). None: no bet. The
  market is still counted in retention (the share of markets we actually get a usable price for).
- **Money near the entry:** dollars that favourite-side buyers paid at up to 1c above the entry price in the 60
  minutes up to the checkpoint. A floor where the fetched trades do not reach back 60 minutes.

## Scoring

- **Fee:** 0.07 x p x (1 - p) x the series' `fee_multiplier`, per contract, unrounded.
- **Return per $1 bet:** (payout - price - fee) / (price + fee), payout $1 on a win, $0 on a loss. A cell's
  score is the mean over its bets: cents of profit for every dollar bet, after the fee.
- **Profit per contract:** payout - price - fee, in cents. This is the breakeven slippage (how much worse fills
  can get before all the profit is gone).
- **Main measure:** entry prices from 70c up to, not including, 99c. Bands 70-80, 80-90, 90-95, 95-99.
  50-70 and 99c-and-up are reported, never scored for a pass.
- **Ranges:** 95% range from the cluster-robust standard error of the mean, clustered on event (bets on the same
  event move together, so they count as one, not many): mean +/- 1.96 SE, with SE^2 = G/(G-1) x sum over events
  of (sum of the event's deviations from the mean)^2 / N^2.
- **Cells:** a category at a checkpoint, or a series at a checkpoint. A market counts at most once per cell.

## Candidates (train half only)

A cell is a candidate if, on train, it has **100+ events**, its mean return per $1 is above zero, and its range's
lower end is above zero. Series cells need the same, on their own events.

## Pass (test half, read once)

A candidate passes only if, on test:

1. it has 100+ events;
2. its mean return per $1 is above zero and its range's lower end is above zero;
3. **band leave-one-out:** dropping each of the four bands in turn leaves the mean above zero and the lower end
   above zero, every time;
4. for a category cell, dropping its biggest series (most bets in the cell) leaves the mean above zero and the
   lower end above zero.

A pass is called **"room to spare"** if its test profit per contract is at least 1 cent, enough for fills worse
than the last buyer got (the live bot's fills land 0.4c worse than quotes).

A pass is **flagged as lonely** if both neighbouring checkpoints with 100+ test events score at or below zero.

## Luck

The report states the number of candidate cells and the number of passes luck alone would give: each candidate
has about a 2.5% chance of a lower end above zero on test by luck.

## Also reported, never part of a pass

- Each category's calibration (whether a 70c price really wins 70% of the time) by band, both halves.
- Yes favourites against No favourites, per category.
- Retention per category and checkpoint.
- Contracts traded per day per series (newer part of the listing, complete) and money near the entry.
- Today's spread (the gap between the buy and sell price): three sweeps of every open non-combo market's best bid
  and ask, at least 6 hours apart. Median spread per category and series, for markets whose favourite is 70c to
  99c, by time left to close.
- Rows already scored by earlier work (AAA gas, weather, the 15-minute series) are marked.

## Known weak spots, stated before the results

- Closing time is the actual close. Markets that can close early (an answer arriving early) are measured back
  from when the answer came, which a live trader would not know.
- The fee multiplier is today's; some series may have had a different one in the past.
- Someone else paid the entry price. We would be the next buyer.
