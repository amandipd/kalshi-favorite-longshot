# Newly listed Kalshi markets: research summary and proposed design

Research pass, 25 October 2026. No code deployed, nothing traded.

---

## Bottom line

The thesis is half right, and the half that is right is bigger than I expected.

**Right:** thin, illiquid markets do misprice favourites, and the mispricing is
large enough to survive fees with real room to spare. On our own data, favourites
priced 80-90c in the thinnest third of markets won 5.1 cents more often than
their price implied. Fees take about 1 cent. That leaves about 4 cents of profit
for every contract bought, against the 1 cent of headroom the main study had.
It survives both robustness checks that killed earlier ideas.

**Wrong, or at least unproven:** nobody has measured *brand new* markets, us
included. What I measured is "markets that never got liquid", which is not the
same thing. And the edge sits in the 80-90c band. Above 90c, thin markets *lose*
money, which is the opposite of what the live bot trades.

**The thing that decides it:** these are thin markets, so the spread is widest
exactly where the edge is biggest. We have never measured the spread at listing.
That single unmeasured number is the whole strategy.

---

## 1. What the outside research says

I found **no study at all** on opening prices for new Kalshi listings. Not one.
The idea shows up only in vendor marketing. So the thesis is untested rather
than disproven, and we would be first.

Four findings from the literature do bear on it.

**Prices are compressed toward 50% at long horizons, and new markets are
long-horizon markets.** A 2026 study of 292 million trades found the calibration
slope rises from 0.99 within an hour of resolution to 1.32 beyond a month. Slope
above 1 means true probabilities are more extreme than prices, so favourites are
underpriced. This is a mechanism that *predicts* the thesis. A newly listed
market is usually far from resolution and thin at the same time, so both effects
push the same way.

**Market makers get picked off in exactly these markets.** A Stanford paper
(Bartlett, 2026, 41.6 million trades) finds single-name markets carry more
informed price impact than broad ones, and that one-sided order flow predicts
maker losses. If we post limit orders in a new market, we are the maker. That is
the side that loses.

**The crowd overbets YES.** The same paper finds traders systematically buy YES
in markets that mostly settle NO. Where the favourite is the YES side, we would
be joining the crowded trade. Buying the favourite as NO sits opposite them.

**Opening prices are softer than closing prices in betting markets.** This is
well documented, and a University of Georgia study found closing lines correct
much of the opening gap. But Karl Whelan's critique is right that beating the
open does not by itself prove profit.

## 2. Kalshi's listing mechanics matter more than I expected

From Kalshi's own lifecycle docs:

- A market sits in `initialized`, then flips to `active` **purely when
  open_time passes**. There is **no opening auction and no price discovery
  period**.
- So at the instant of open, the book is whatever happens to be resting. It can
  be empty. The zero-bid trap is not a theoretical risk here, it is the default
  state.
- Pausing and resuming a market **cancels every resting order**. Any limit we
  leave in a new market can vanish without being filled.
- The markets endpoint filters on creation time, so we can find brand new
  markets reliably and in advance.

That last point is the good news. "Super new" is cleanly observable, before the
fact, with one API call.

## 3. What I measured on our own data

Our 100,210-contract dataset has open and close timestamps and volume, so I
could test the thin-book half of the thesis today. Prices are at one hour before
close, not at listing, so this is a proxy and not the real test.

Edge in cents per contract, by how much the market eventually traded:

| Price band | Thin third | Thick third |
|---|---|---|
| 60-80c | **+3.3c** | -1.1c |
| 80-90c | **+5.1c** | -1.9c |
| 90-95c | -1.6c | -2.2c |
| 95-100c | -0.6c | -0.6c |

Thin and thick run in opposite directions. In liquid markets the favourite edge
is gone or negative, which is what an efficient market should look like. Narrow
to short-lived *and* thin and the 80-90c band reaches **+5.5c**.

**The 80-90c thin cell holds up.** This is where earlier ideas died, so I ran the
same two checks:

| Check | Result |
|---|---|
| Headline | +5.10c, t = 7.3, n = 2,046 |
| Drop 2 biggest series | +6.70c, so it gets *bigger* |
| Train, to 20 Apr | +5.96c, t = 5.2 |
| Test, after 20 Apr | +4.59c, t = 5.2 |

It is not one lucky series, and it does not vanish out of sample. The 60-80c band
does *not* pass: train +6.3c, test +1.9c. So 80-90c only.

**Money and capacity, which is the sobering part:**

- Gross edge +5.1c, taker fee about 1c, so **about 4c net per contract**.
- Breakeven slippage **4.1c**, four times the main study's 0.98c.
- About **11 qualifying markets a day**.
- The median market trades 5,710 contracts over its whole life. Taking 2% of
  that is roughly **$97 staked** and **$4.68 expected** per market, about **$50
  a day**. At 5% it is about $128 a day.
- 96% of these are Sports.

So: a real edge, on small money. A few hundred dollars a month at plausible size,
not a step change.

## 4. The risks that could make this worthless

1. **The spread.** Unmeasured, and decisive. 4c of headroom is good, but a thin
   book can quote 3-5c wide. Over half our settled snapshots show a $0.00/$1.00
   spread, so historical data cannot answer this. Only forward collection can.
2. **Final volume is not knowable at entry.** The filter above uses volume over
   the market's whole life. A live rule has to use depth and volume *so far*,
   which is a different and weaker signal. The edge may not survive that swap.
3. **"Never got liquid" is not "brand new."** My proxy may be measuring
   neglected markets, not young ones. Those could be different populations.
4. **Rule reinterpretation.** The Khamenei market settled at the last traded
   price before the news under a death carve-out, and a class action followed in
   March 2026. Novel markets are exactly where settlement terms are least
   tested, and that risk is concentrated in the newest listings.
5. **Adverse selection if we post limits.** Thin book, plus a resting order,
   plus informed flow is the textbook way to be picked off.
6. **The 2026 microstructure may differ.** Kalshi's liquidity incentive program
   was reported as ending around 13 October 2026 amid wash-trading allegations.
   Volume in our study window may be partly incentive-driven.
7. **It would contaminate the six-week test.** The live bot is meant to run
   unchanged to 27 November. Starting a second live strategy before then muddies
   that measurement.

## 5. Proposed design

Phased, and the first two phases trade nothing.

**Phase 0, build the dataset that does not exist.** Two collectors:

- *Backward:* a new ingestion pass that asks the historical trades endpoint for
  the **first** trades after open, instead of the last trade before close. This
  reuses `kalshi_calibration/ingest/trades.py` almost unchanged and gives us opening price
  versus outcome on markets we already catalogue. Cheap, and it directly tests
  whether brand new markets are miscalibrated.
- *Forward:* poll for unopened markets, then snapshot the **full order book** at
  open, and at +1 min, +5 min, +15 min and +1 h. This is the only way to learn
  the real spread and depth at listing. Two weeks gives a usable sample.

The forward collector answers the question that decides everything, so it goes
first.

**Phase 1, pre-register then test.** Write the hypothesis and thresholds down
before looking, the way `THRESHOLD_SEARCH_PREREG.md` does. Then test whether the
opening-price edge clears the *measured* spread, with a train/test split and
clustering on event.

**Phase 2, shadow.** Log what it would have done against live books. No orders.

**Phase 3, live, tiny, and not before 27 November** so the current test stays
clean.

Sketch of the rule to be tested, not adopted:

- Newly active markets, excluding any series the bot already trades.
- Favourite priced **80-90c only**. Not 90c+, which loses when thin.
- Limit orders only, never market orders, because the book may be empty.
- Prefer buying the favourite as **NO** where that is the same bet, to sit
  opposite the YES-overbetting crowd.
- Skip markets with novel or person-dependent settlement terms.
- Size inside the existing 1.5% / 10% framework.

## 6. What I have not done

No execution code, no live calls, nothing deployed. The analysis scripts were
one-off scripts, not in the repo. The band choice in section 3 was made after
looking at the data. The train/test split limits that, but a clean
pre-registered test still owes us a confirmation.
