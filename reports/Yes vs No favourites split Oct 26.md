# Thin favourites: the "No" side earns twice as much

Research pass, 26 October 2026. Nothing built, nothing traded. Scripts are in
`research/thin_favourites/` (run from the repo root).

## The answer

The Oct 25 result (+5.1 cents of profit per contract) only ever counted "Yes"
favourites. This data stores the Yes price, and the old filter looked for Yes
priced 80 to 90 cents. "No" favourites were never in it.

When I add them, the "No" side is the stronger one. Thin "No" favourites priced
80 to 90 cents made about **8 cents of profit per contract**. Thin "Yes"
favourites made about **4 cents**. Both used only prices someone actually paid.

This fits the outside research from today: traders overpay for "Yes".

## What I tested

- **Data:** the 100,210-contract sample on disk. The price is the last trade
  at or before one hour before close.
- **Thin** means the least-traded third of markets, by volume over the whole
  market's life. That is hindsight. A live bot can't know it at entry.
- **Edge** means profit per contract, in cents, before Kalshi's fee.
- **Rebuild check:** the old script gave the same answer again: 2,046
  contracts, +5.10 cents, far too big to be luck (t = 7.31). The t-stat says how
  far from luck a result is; about 2 is the usual bar.
- **Clustered on event:** bets on the same event move together, so they count
  as one, not many.

## The one fix that matters: who set the price

Each price comes from a real trade. Some were set by a "Yes" buyer and some by a
"No" buyer. If a "Yes" buyer set a 15c price, a "No" buyer would have paid more
than 85c. So the fair test keeps only prices a favourite buyer actually paid.

| Group (thin, 80-90c) | Contracts | Profit per contract, before fee | Far from luck? (t; about 2 is the bar) |
|---|---|---|---|
| "No" favourite, price paid by a No buyer | 1,505 | +8.1 cents | Yes, t = 11.5 |
| "Yes" favourite, price paid by a Yes buyer | 1,493 | +3.9 cents | Yes, t = 4.7 |

## The usual checks, on the fair prices

A train/test split builds the rule on older data and scores it once on newer
data. Here the cut is 20 April 2026. Leave-one-out drops the biggest
contributors and checks the result survives. Here it drops the 2 biggest series.

| Check | "No" favourite | "Yes" favourite |
|---|---|---|
| Older data (train) | +8.4 cents per contract | +3.8 cents per contract |
| Newer data (test) | +7.8 cents per contract | +3.9 cents per contract |
| Drop the 2 biggest series | +8.7 cents per contract | +4.5 cents per contract |

Both pass all three. The "No" side is about twice as big every time.

## How old were the prices?

The typical price was 4 minutes old at the one-hour mark. Three in four were
under 14 minutes old. So these are mostly live prices, not stale ones.

- **"No" favourites** hold up at every age: +8.6 cents per contract when under
  10 minutes old, +5.9 cents when over an hour old.
- **"Yes" favourites** fade with age: +5.6 cents per contract when under 10
  minutes old, then −2.8 cents when over an hour old.

## Sports vs the rest: too small to say

Over 96% of these contracts are sports. On the fair prices, only 19 "No" and 39
"Yes" non-sports contracts remain. That is too few to judge. Using all prices,
non-sports look bigger (+10 to +13 cents per contract), but on about 100
contracts each.

The "No" side here is mostly the dull outcome in sports. Most of it is "the
team won't win by more than X", "the total won't go over X", or a tennis
player's opponent winning. The biggest series are NBA and MLB spreads and
totals, and small ITF tennis matches.

## Money, roughly

The taker fee is Kalshi's charge for trading, biggest near 50c. At 85c it is
about 0.9 cents per contract. That leaves about **+7.2 cents per contract** on
the "No" side. That is about 8.5 cents of profit for every dollar bet, before
the spread.

## What this does not answer yet

1. **The spread when we arrive.** The spread is the gap between the buy and sell
   price, what it costs to get in. These prices were paid by someone else just
   before. We would be the next buyer, and a thin book may have moved.
2. **"Thin" is hindsight.** Volume over the whole life isn't known at entry. A
   live rule needs a volume-so-far or depth measure, which is weaker.
3. **Size.** Thin markets hold little money. Capacity is likely tens of dollars
   per market, as the Oct 25 report found.
4. **Mention markets are not in this sample.** The outside study's biggest "Yes"
   overpricing is there. Testing them needs new data pulled from Kalshi.

## What it changes

- The new-listings idea should test **both sides**, and lean to "No" favourites.
  The Oct 25 design already said to prefer No where it is the same bet.
- The forward order-book recorder in the Oct 25 plan is still the next step.
  It is the only way to measure the spread when we arrive.
- Nothing goes live before the 6-week test ends on 27 November.
