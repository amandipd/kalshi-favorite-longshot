# Step 1 pass bar, fixed before any result (26 Oct 2026)

**Question.** In the last minute of Kalshi's 15-minute bitcoin and ether markets, do favourites win more often than
their price says, after the taker fee?

**Data.** Every settled KXBTC15M and KXETH15M market from 1 Sep 2026 to 25 Oct 2026, and the public trade tape of
its last 100 seconds. Only prices a buyer of that side really paid. Script: `last_minute.py`.

**Main cells (picked now, so the result can't pick them).** The "bets" view, one bet per market:

- 30 seconds left, favourites at 90-95c
- 30 seconds left, favourites at 95-98c
- 10 seconds left, favourites at 90-95c
- 10 seconds left, favourites at 95-98c

Below 90c the fee is bigger and these markets are rarely there late. At 98c and up there is at most 2c to win.

**Pass, go to step 2.** At least one main cell has all of these:

- profit per contract after the fee above zero, far from luck (t above 2, clustered on the 15-minute window)
- above zero on both the older half and the newer half of the days
- above zero without its single best day

**Fail, stop here.** Every main cell has a profit at or below zero, or a t under 1.

**In between.** Positive but t between 1 and 2: reported as unclear. Going on is a separate decision.

**Reported but not part of the bar.**

- 90 seconds left, before the averaging minute starts. If the edge is as big there, it is a plain late-favourite
  effect, not the averaging.
- The "buys" view, every last-minute favourite buy weighted by contracts, with the dollars that traded.
- BTC and ETH apart.

**Known limit.** A price here is one a taker chose to pay. A bot arriving a second later may find it gone. Step 2
measures that with live order books.
