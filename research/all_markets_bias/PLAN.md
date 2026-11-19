# All-markets favourite-longshot map: plan

28 Oct 2026. Nothing has been pulled or scored yet. This is the plan only.

The question: where on Kalshi are heavy favourites underpriced (the favourite-longshot bias: cheap unlikely
bets are overpriced, heavy favourites underpriced), and where would buying them pay a taker after the taker fee
(Kalshi's charge for trading, biggest near 50c) and the spread (the gap between the buy and sell price)?

## Why new data is needed

The earlier 100,210-contract sample covers only the top 20 series in 4 categories, Dec 2025 to Jun 2026, and is
96% sports. Kalshi lists 15,462 series in 20 categories today. Most of them have never been scored.

## Data

- **Universe:** every series on Kalshi (15,462 on 28 Oct, 20 categories). Combo bets (parlays, the multi-leg
  "MVE" markets) are left out: they trade through quote requests, not a normal order book.
- **Window:** settled markets closing 1 Nov 2025 to 27 Oct 2026.
- **Sample, fixed before any outcome is read:** for each series and each half (below), up to 40 events chosen at
  random, then up to 5 markets per event at random. Fixed seed. The rule never looks at results.
- **Trades per market:** first one request for the market's newest 1,000 trades. Most markets trade fewer than
  that, so one request covers their whole life. For busier markets, one more request per checkpoint that page
  does not reach (the last 100 trades before that checkpoint). Each trade says which side the buyer took
  (`taker_side`) and what they paid.
- **Checkpoints (widened on 28 Oct from one checkpoint to many hours before close):** 11 moments before
  close, spaced wider as they go back: 1, 2, 4, 8, 12 and 24 hours, then 2, 3, 7, 14 and 30 days. A market is
  scored at every checkpoint that falls inside its life. Markets that live under 2 hours also get their halfway
  point (minute 7.5 of a 15-minute market, near the bot's minute 8).
- **Why not literally every hour:** a month-long market would count 720 times and swamp the day-long ones, the
  same outcome would be re-counted hundreds of times, and the cost would grow many times over. Checkpoints spaced
  wider as they go back still show the shape. Outside research (a 292-million-trade study) found the bias grows
  with time left, from almost none within an hour to large beyond a month, so this is worth measuring.
- **The favourite** is the side the most recent trade priced above 50c.
- **Entry price** is the last price a buyer of the favourite side really paid, no more than 60 minutes before the
  entry moment. No such trade means the market is dropped, and counted in retention (the share of markets we
  actually get a usable price for).
- **Today's spread:** a sweep of every open market's best bid and ask, a few times over a day. Cheap, a few
  hundred requests. It shows what getting in costs now, per series.
- **Money:** contracts and dollars traded per series per month, and how much changed hands near the entry price
  in the hour before it.

## Scoring

- **Profit per $1 bet** (cents of profit for every dollar bet), buying the favourite at the entry price and
  holding to settlement, after the fee 0.07 x p x (1 - p) x the series' fee multiplier.
- **Main measure:** favourites priced 70c to 99c. Bands 70-80, 80-90, 90-95, 95-99. Prices of 99c and up are
  reported apart: often a pinned price (already equal to the answer).
- **Also shown:** each category's full calibration curve (whether a 70c price really wins 70% of the time), Yes
  favourites against No favourites, and the share of markets priced.
- **Clustered on event:** bets on the same event move together, so they count as one, not many.

## Checks, fixed in a committed pre-registration before any outcome is pulled

- **Train/test split:** build on closes 1 Nov 2025 to 31 Jul 2026, score once on 1 Aug to 27 Oct 2026.
- **Cells:** each category (and each series with 100+ events) at each checkpoint is one cell. A market counts
  once per checkpoint, never twice in the same cell.
- **Candidates, chosen on train only:** a cell whose profit after the fee is above zero with its 95% range (the
  range the true number is probably in) above zero.
- **More cells mean more lucky passes.** About 20 categories times 11 checkpoints is over 200 cells. The report
  states how many passes luck alone would give, and flags a pass that shows up at one checkpoint while the
  checkpoints either side of it are flat.
- **Pass, on test:** profit after the fee above zero, range above zero, 100+ events; survives the band
  leave-one-out test (drop each price band in turn, still positive with its range above zero); and for a
  category, survives dropping its biggest series.
- **Every category and big series is still shown**, passed or not, so the map is complete.

## What it cannot answer

- **Whether we would get the same price.** Someone else paid it; we would be the next buyer. The 60-minute
  freshness cap and today's spread sweep bound this, but do not settle it.
- **Depth** (how much money you can trade before moving the price). Kalshi keeps no old order books. Trade sizes
  are a floor.
- **Some of the test window is already scored:** AAA gas, weather and the 15-minute markets. Those rows are
  marked.
- **Combo bets** are left out.

## Rate and timing

- The other jobs on the same machine then used about 15 of Kalshi's 20 requests a second: `pull_gap.py` (a separate download, not included) at 8, the
  last-minute download at 4, the thin-market recorder at 3. A probe at under 1 a second already drew
  "too many requests" errors.
- So this runs at 2 a second while `pull_gap.py` is running, and up to 4 after, backing off on any error.
- With one checkpoint this was roughly 100,000 to 150,000 requests, 10 to 20 hours. With 11 checkpoints, busy
  markets need extra requests, so roughly 2 to 3 times that: about 1 to 2 days. A dry run on a few hundred
  markets measures the real number first; if it runs long, the sample shrinks to 25 events per series per half
  rather than dropping checkpoints. The machine must stay awake.
- **Results come in stages:** the 1-hour checkpoint is scored first, so there is a usable answer before the
  long pull ends.

## Code

Tests first: fee, entry moment, favourite and entry price, freshness cap, sampling, clustered ranges, band
leave-one-out. See them fail, then implement. Everything lives in `research/all_markets_bias/`.
