# Fresh test pass bar, fixed before any download (27 Oct 2026)

**Why.** Step 1 (PREREG.md, Sep 1 to Oct 25 2026) ended "in between". Its 4 main cells were positive but not far
from luck. Looking further, I found a pooled pattern: favourites bought inside the averaging minute made +2.0 cents
per contract after the fee. I found it after seeing the results, so it must be scored once on data it never saw.

**Data.** Every settled KXBTC15M and KXETH15M market that closed from 1 Dec 2025 00:00 UTC up to (not including)
1 Sep 2026 00:00 UTC. Kalshi's public trade tape of each market's last 100 seconds. Nothing from step 1 is reused.

**The rule, fixed now.** Exactly the step 1 "bets" view, with nothing tuned:

- checkpoints 45, 30, 20 and 10 seconds before the close
- at each, the last favourite buy in the 10 seconds before it (a price a buyer of the favourite really paid)
- favourites priced 80c or more and under 98c
- profit per contract after Kalshi's taker fee, 0.07 x price x (1 - price), unrounded
- t clustered on the 15-minute window (BTC and ETH in the same window count as one)

A market can give up to 4 bets, one per checkpoint. The clustering handles that.

**Pass.** All three:

1. Profit per contract after the fee above zero, far from luck (t above 2).
2. Above zero on both the older half and the newer half of the days (split at the middle day).
3. Above zero without its single best day.

**Fail.** Profit at or below zero, or t under 1. The idea closes.

**In between.** Anything else. Going on is a separate decision.

**Reported but not part of the bar.**

- The other half of the prediction: the same favourites 90 seconds before the close, before the averaging starts.
  Step 1 found them losing (−1.6 cents per contract).
- BTC and ETH apart, and each month apart, to see if the pattern is shrinking.
- The 4 step 1 main cells (30 s and 10 s left, 90-95c and 95-98c), for comparison.

**Known limit.** Same as step 1: every price was paid by someone else. A bot arriving a second later may find it gone.
Only step 2 (live order books) answers that, and it would be a separate decision.
