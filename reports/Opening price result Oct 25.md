# The opening price of a new Kalshi market: result

Test run 25 October 2026. Pre-registered in `research/opening_price/PREREG.md`
before any data was fetched. 30,000 markets drawn at random, seed `20261025`.

---

## Verdict: the hypothesis fails, in the opposite direction

The thesis was that a brand-new market prices its favourite **too cheaply**,
because nobody is trading it yet. The opposite is true, and strongly.

At the first trade after a market opens, favourites are **overpriced in every
band we can read**. Gross is cents per contract before fees; net is after
Kalshi's taker fee. Negative means buying the favourite loses money.

| Opening price | markets | priced | won | net | t |
|---|---|---|---|---|---|
| 60–80c | 2,824 | 0.692 | 0.671 | **−3.55c** | −2.25 |
| 80–90c | 1,239 | 0.844 | 0.811 | **−4.19c** | −2.85 |
| 90–95c | 452 | 0.923 | 0.816 | **−11.16c** | −5.66 |
| 95–100c | 638 | 0.968 | 0.900 | **−7.02c** | −5.44 |

`t` is how far the result sits from luck; about 2 is the usual bar, so these are
not noise.

The pre-registration said H1 passes only if the gap is positive. It is negative
in all four bands on the train half, so **H1 fails at the first hurdle and the
test half was not scored.** 10,324 markets remain unread, as designed.

## The same markets, later in their life, run the other way

This is the control that makes the result trustworthy. Identical markets,
identical code, identical clustering — only the price column changes:

| Price band | at the OPEN | at T−1h |
|---|---|---|
| 60–80c | −2.06c | **+4.62c** (t = 4.43) |
| 80–90c | −3.27c | +1.51c |
| 90–95c | −10.66c | −0.25c |

The T−1h column reproduces the favourite edge the September study found. So the
pipeline is reading prices and outcomes correctly; the negative opening result is
not a sign error or a bad join.

**The favourite edge is real but it is not there at the open.** It appears later.
At the open the favourite is dear, and it gets cheaper, and somewhere before the
last hour it crosses into being too cheap.

## The strongest clue: markets that trade *fast* are the worst

Splitting the train half by how long the market waited for its first trade:

| Opening price | fast to trade | slow to trade |
|---|---|---|
| 60–80c | −4.14c | −0.45c |
| 80–90c | **−6.78c** | −1.17c (t = −0.59) |
| 90–95c | **−16.64c** | −3.72c |

Markets that trade almost immediately have the most overpriced favourites.
Markets that sit quiet for hours are close to fairly priced.

That points at a mechanism rather than a statistical accident: the first trade in
a new market looks like somebody in a hurry paying over the odds for the obvious
side. It fits the Stanford finding (Bartlett 2026, 41.6m trades) that traders
systematically overbet YES, and it fits a taker crossing a wide, barely-formed
book.

## What we also learned about the opening window

**It is mostly empty.** Median wait from a market opening to its first trade is
**4 hours 28 minutes**.

| Traded within | share of all markets |
|---|---|
| 15 minutes | 10.0% |
| 1 hour | 19.9% |
| 6 hours | 49.1% |
| 24 hours | 83.1% |

So "catch the mispricing in the opening minutes" describes about one market in
ten. For the rest there is nothing to trade against for hours.

**Retention: 85.4%** — the share of markets we got a usable opening price for,
25,621 of 30,000. 2,093 never traded within 72 hours; 2,286 were too busy for the
fetch to reach their open.

**Retention is very uneven by category**, and Crypto is the worst:

| Category | priced |
|---|---|
| Sports | 89.9% |
| Politics | 84.4% |
| Economics | 65.7% |
| Crypto | **19.7%** |

## The selection problem, stated plainly

The markets we could not price are **not** like the ones we could. They settled
yes 33.4% of the time against 45.6% for the ones we priced.

That is a real difference and it has to be on the record. It does not rescue the
hypothesis — a gap of that size cannot turn −11c into a positive — but any
future use of this dataset has to carry the caveat. One series is nearly absent:
85% of `KXSHIBA` markets dropped out, which is most of why Crypto retention is
20%.

## Is the reverse tradeable? Probably not, and we cannot tell from here

An 11-cent overpricing invites the obvious question: sell the favourite instead.
Two reasons not to get excited.

1. **We already tested the flip side and it lost.** The 16 October flip-side test
   found that buying the underdog of a bad band loses in every band once spread
   and fees are paid.
2. **The "opening price" is one trade, not a price you could get.** If the first
   print lands at 92c inside a book quoting 85 bid and 95 ask, there was never a
   chance to sell at 92c. The measured gap may simply *be* the spread.

That second point is the same unmeasured number that has limited this work from
the start. Only live order-book collection at the open can settle it.

## What this closes, and what it leaves open

**Closed.** Backing the favourite in a newly listed market. It loses, out of
sample, before costs, in every band, with a mechanism that explains why. The
pre-registration said a fail is a result and ends the strategy work.

**Left open.** Whether the first print's distance from fair value is spread or
genuine mispricing. That needs the forward order-book collector, which was always
the more expensive of the two paths.

**Unchanged.** The live bot. Nothing here argues for a change to it, and the
six-week test runs to 27 November as planned.

## Cost of finding out

90 minutes of downloading across two workers, against the 8.8 hours a full run
would have taken. The staged approach paid for itself: the answer was clear at
30,000 markets, so the other 113,000 were never needed.

Method notes: the thin/thick split uses **trades per hour in the opening window**
rather than the raw count the pre-registration specified, because markets
answered at different window widths give counts that are not comparable. Declared
as a change from plan. All intervals cluster on `event_ticker`. Outcomes come
from the raw layer, not `contracts.parquet`, so the sample is not narrowed by the
study's own T−1h exclusion.
