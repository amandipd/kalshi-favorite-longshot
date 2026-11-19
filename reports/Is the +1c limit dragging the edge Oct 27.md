# Is the +1 cent limit dragging the edge down? (Oct 27)

**Short answer: no. The extra contracts it buys earned about the same as the rest: close to nothing. What fell since Oct 20 is the edge (the bot's profit source) on every contract, including the ones the old limit would have bought too.**

## What was checked

Since Oct 20 at 7:26 PM ET, each order may pay up to 1 cent over the price the bot saw (the +1 cent limit). The first such order went out at 7:53 PM. Before that, orders paid at most the price the bot saw.

Every live contract since the live start (Oct 15) was split by what it paid:

- **At or under the price the bot saw.** The old limit would have bought these too.
- **Above the price the bot saw.** Only the +1 cent limit could buy these. These are the "extra" contracts.

For each group: profit for every dollar bet, and how far that is from luck. Bets in the same 15-minute window count together, since they move together. Fees are included. Data: the live ledger's bets, fills and decisions, read-only.

## Before the +1 cent limit (Oct 15 to Oct 20, 7:53 PM ET)

- 931 bets, 11,243 contracts, $10,853 bet.
- Profit: +$182.33. That is +1.68 cents for every dollar bet.
- Far from luck (t = 2.99, where about 2 is the usual bar).
- Lost 17 bets where prices predicted 34. That is unusually few losses.

## Since the +1 cent limit

All contracts:

- 1,469 bets, 23,406 contracts, $22,537 bet.
- Profit: +$33.93. That is +0.15 cents for every dollar bet. Not far from luck at all (t = 0.21).
- Lost 51 bets where prices predicted 56.

Split by what each contract paid:

- **At or under the seen price:** +$29.32 on $15,886. That is +0.18 cents for every dollar bet (t = 0.23). Lost 41 where prices predicted 46.
- **Above the seen price (the extras):** +$4.61 on $6,651. That is +0.07 cents for every dollar bet (t = 0.07). Lost 18 where prices predicted 19.

280 bets got every contract above the seen price. The old limit would have bought nothing on those. They made +$3.64.

Most extra contracts paid only a little more than the seen price: most often 0.1 to 0.3 cents over, rarely the full cent.

## What it means

- **The +1 cent limit is not the problem.** Its extra contracts earn about the same as the rest. Both are close to zero, and the gap between them is tiny next to luck.
- **In dollars it added a little.** Without it, the bot would have made about $29 since Oct 20 instead of about $34.
- **But the extras are not the win the paper test promised.** The paper test (Oct 12 to 20) showed +1.34 cents for every dollar bet on extra contracts. Live, they have been about break-even. So right now the limit adds volume and swings, but not much profit.
- **The real change is in the base edge.** Contracts the old limit would also have bought fell from +1.68 cents per dollar (before Oct 20) to +0.18 cents (since). That drop of 1.5 cents scores 1.5 on the luck measure (t = 1.54), under the bar of 2. So it could still be luck. The first five days lost only half the bets prices predicted, which is lucky even for a bot with an edge.
- **Day by day it is mixed.** The base contracts had good days since Oct 20 (Oct 24: +2.36 cents per dollar) and bad ones (Oct 27 so far: −3.78 cents). There is no steady slide.

## What to do

- **Nothing before Nov 27.** The +1 cent limit is not hurting. Removing it mid-test would change the setup again and muddy the result.
- **At Nov 27, judge the two groups apart**, as the test plan already says:
  - The base contracts tell you whether the edge is real.
  - The extras tell you whether the +1 cent limit is worth keeping. If they are still about break-even, it adds swings for no gain, and turning it off would be reasonable.
- Any Nov 27 bet-size rule should use the base contracts' result.

A one-off script, not in the repo. Ledger read-only. Nothing in `bot/` was touched.
