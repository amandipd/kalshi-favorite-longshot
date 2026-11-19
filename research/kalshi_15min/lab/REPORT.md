# Strategy lab, Oct 11 2026

Two questions: should the bot be seeing losing trades, and which prediction-market strategies make sense? The work
came in four parts:
- Part 1: live losses, limit orders, market-by-market checks, and this write-up
- Part 2: online research
- Part 3: the edge map, timing and concentration
- Part 4: fair value from the spot price

Every backtest uses the same conventions:
- data: lab/markets.npz, every 15-minute market from Dec 10 2025 to Oct 8 2026
- helpers: lab/common.py, which reproduces strategies.json exactly
- $10 a bet in whole contracts
- fills at the ask plus 0.4¢, with Kalshi's taker fee
- results in cents per $10 staked, with a 95% range clustered by window
- "pre" means Dec 10 to Jul 17, which no rule was chosen on; "post" means Jul 18 to Oct 8

## 1. Losing trades are part of the strategy

- **The arithmetic.** At 95¢ you risk 95¢ to make 5¢, so one loss wipes out about 19 wins (about 9 at 90¢). The bot
  only makes money if it wins more often than the price implies. The backtest says it does, by about 1.4 points
  (96.4% won against a 95.0% average price, outside HYPE and ZEC). The profit is the gap between those two numbers,
  not the absence of losses.
- **Live so far (331 settled bets, Sep 28 to Oct 11).**
  - Record: 315 won, 16 lost, +28¢ per $10.
  - Applying the backtest's win rate at each price to the bot's actual bets predicts about 13 losses (90% range 8-19).
    Fair prices would mean 18. Sixteen is ordinary.
  - The +28¢ per $10 is luck on top of the edge. One bet's result swings about ±230¢ per $10, so 331 bets pin the
    average only to about ±25¢.
- **How much a normal stretch hurts (backtest, live rule, 3% a bet, from Dec 10).**
  - About 1 day in 3 lost money (109 of 303).
  - The worst single 15-minute window cost 17% of the bankroll.
  - The deepest fall from a peak was 40-60%, depending on the start date.
- **Telling luck from a broken edge.** To separate a +4.5¢ edge from zero takes about 10,000-14,000 bets. The upper
  figure allows for losses arriving together in the same window. That's roughly 3 months at today's ~135 bets a day.
  - Until then, the useful check is losses against expected losses, as above.
  - Real warning signs:
    - a win rate below the break-even price over a few thousand bets
    - losses bunching where the backtest has none
- **The one spot to watch: the 90¢ band.** 37 live bets, 8 lost, against about 3 expected (backtest fills limited by
  the trade tape).
  - Luck alone gives about a 1% chance. Because this band was picked as the worst of six after looking, the honest
    figure is nearer 5%.
  - Every band from 92¢ up lost less often than expected.
  - The Oct 11 price-floor study found no long-run problem at 90-91¢. Keep watching; if it continues, test a 91¢
    floor.

## 2. What other traders do (part 2: lab/web_research.md, with sources)

- **The published evidence on the favourite-longshot bias.**
  - Bürgi-Deng-Whelan studied Kalshi, 2021 to Apr 2025. Contracts above 70¢ earn small but real returns after the
    taker fee, and crypto has the steepest bias of any category. But the bias is shrinking (its 2025 slope is about
    half of 2024's), and the study leaves out markets open under 24 hours, so not ours.
  - A Sep 2026 Polymarket paper found buys at 90¢+ earn about +0.8¢ per dollar, about +8¢ per $10. That's the same
    size as ours.
  - Average returns in that Kalshi study: makers −9.6%, takers −31.5%. Most traders lose.
- **Our own trend.** The live rule's gap between win rate and break-even, by month, ran +0.4 to +1.0 points in most
  months, negative in March and May, and +0.7 to +0.9 in Aug-Sep. There's no clear shrinking yet, but it's noisy
  month to month.
- **Losses, with numbers.**
  - Break-even loss rates: 9.4% at 90¢, 4.7% at 95¢, 2.8% at 97¢.
  - In 100 bets, 8 losses is the 1-in-20 bad case and 10 the 1-in-100.
  - Proving a +0.45% edge takes about 9,000-14,000 bets.
  - A sequential test (SPRT: a running check that stops as soon as the evidence is clear) would spot a real break
    much sooner: about 400 bets if favourites start winning 2 points less than their price, about 900 at 1 point.
  - 3% a bet is about ⅓ of the Kelly size (the growth-maximising bet) if the edge is real.
- **What others do.**
  - **Market making** (resting orders, earning the spread): makers pay no fee on our 16 markets. Kalshi also pays a
    liquidity incentive for resting orders on 15-minute palladium, copper, platinum and natural gas: $20 a window
    each, until Jan 1 2027. But our test shows resting orders on favourites get adversely selected (3d).
  - **Arbitrage:** YES+NO can't be split on Kalshi, which has one shared book. Kalshi against Polymarket isn't a true
    arbitrage, because they settle on different prices. Bots took most of Polymarket's.
  - **Latency trading** on Polymarket's 15-minute crypto markets died with its 2026 taker fees.
  - **Fair-value models** work best as a filter, which matches 3b.
  - **Copy-trading:** no evidence it works.
- **Settlement.**
  - Crypto uses a 60-second average of the CF index; a tie goes to YES.
  - Metals and energy use one Pyth 1-minute close at each end, with no averaging, so a single late tick can flip
    them.
- **Fees.** Kalshi charges direct members the exact fee, rounded to $0.0001, not rounded up to the cent. The bot's
  fills confirm it: $12.96 paid against $12.94 exact and $14.85 rounded up, over 337 bets. So every backtest here
  overstates fees by about 0.6¢ per $10. The real edge is that much better than shown.
- **A correction to part 2.** Its starting assumption was that one loss costs about 10 wins; at the bot's average 94.6¢ it's
  about 19, as section 1 says.

## 3a. Where the edge lives (part 3: lab/edge_map.py and edge_map.md)

- **Keep minute 8 and the 90-99.9¢ band.**
  - By entry minute: minutes 5-9 all make money, but later is worse in both halves. From minute 10 on, the price
    has caught up with how often favourites win (minute 13: 98.6% won at 98.7¢). Minutes 12-13 lose in both halves.
  - Minute 5 looks better on paper (+7.7 | +8.6¢) but has a third as many bets, and its range covers minute 8's.
  - Narrowing the band fails out of sample: the half before Jul 18 would drop 90-94¢, and those bets then made
    +11.1¢ after Jul 18.
  - 85-90¢ disagrees between halves (−5.2 | +7.6).
- **The filters are what make it pay.** Without the spread and late-favourite skips, every minute and band loses
  before Jul 18.
- **The underdog side is the mirror image.** Buying the underdog loses about $5 per $10 bet: underdogs won 5.3% at an
  8.5¢ ask. That's the longshot half of the bias.
- **Timing.**
  - Hour of day and weekends are noise.
  - **The weekday 9:30 ET window**, when US stocks open, lost −40.9¢ per $10 (range −80 to −2, 416 bets). It was
    first flagged in September on Jul-Sep data, so the Dec-Jul half is a true test, and it lost there too (−52¢).
    About 30 time slots were checked, so treat it as likely, not proven.
  - The 8:30/10:00 data-release windows lean negative but don't pass the bar.
- **Crypto losses come in clusters.**
  - When one crypto bet loses, another in the same window loses 36% of the time, against a base rate of 3.8%.
  - 43% of losses come in windows that lose two or more bets.
  - Capping a window at **3 crypto bets, keeping the tightest spreads**, cuts the worst window from −17.7% to −9.0%
    and the deepest fall by 7-8 points in both halves. The bets it drops made about nothing.
  - Shrinking every bet instead (a 9% window cap) ends lower for the same worst window.

## 3b. Fair value from the spot price (part 4: lab/fair_value.py and fair_value.md)

- **How these markets settle.** YES wins if the average of CF Benchmarks' index over the last 60 seconds is at or
  above the same average over the 60 seconds before the open. Kalshi's floor_strike is that opening average, and it
  matched 99.98% of 174,758 markets.
- **The model.** Fair value = the chance the coin stays on its side of the strike over the time left. It uses:
  - the distance from the strike, measured in "how much this coin usually moves in that time"
  - volatility from Coinbase 1-minute candles, with fat tails allowed for
  - settings fitted on one half of the history and tested on the other
- **Calibration** (how well a price predicts the result): the model alone is about as good as the market's mid.
  The two together beat the mid in both halves. So spot adds a little information the quotes don't hold yet.
- **As a skip filter on the live rule (crypto, minute 8).** Skip a favourite when the model says it's worth 1-2¢
  less than its ask, with the margin chosen on the other half:
  - tested Jul 18 to Oct 8: $820 → $1,124 (+5.2¢ → +9.4¢ per $10)
  - tested Dec 10 to Jul 17: $250 → $531 (+1.7¢ → +4.1¢)
  - With spot a full minute stale it still helps ($852 and $607).
  - The profit rises steadily with the model's gap in both halves. That's the strongest evidence that this isn't
    luck.
  - The gain comes from HYPE, ZEC, BNB and NEAR, the thinner coins. On BTC and ETH it's flat. So it's a more general
    version of "skip HYPE".
- **Model-only trading looks huge (+53¢ / +136¢ per $10) but is a timing artifact.** With spot one minute stale it
  loses −74¢ / −99¢: it was buying quotes that hadn't caught up within the same second. Not tradable.
- **To use it live** the bot would need a live spot feed (Coinbase), which brings new ways to fail (feed outages,
  lag). Its fills haven't been checked against the trade tape yet.

## 3c. The candidates, replayed in full (strategies_backtest.py, now in the Research tab)

There are five new accounts. Each is the live bot with one change: livenh skips HYPE, liveno skips the 9:30 open, and
livec3 allows 3 crypto bets a window. live3x applies all three, and live3xliq is live3x with real liquidity. All were
replayed by the same code as "The live bot". They appear as variants under "Show variants".

Per $10 bet, live-like fills:

| Account | Bets | Whole history | Before Jul 18 | Jul 18 to Aug 23 | Aug 24 to Sep 23 | Sep 24 on | $ at $10 a bet |
|---|---|---|---|---|---|---|---|
| The live bot | 35,793 | +4.5¢ | +1.7 | +5.3 | +9.2 | +4.4 | $1,536 |
| skip HYPE | 32,580 | +5.7¢ | +2.4 | +5.8 | +12.2 | +6.2 | $1,799 |
| skip the 9:30 open | 35,377 | +5.0¢ | +2.3 | +6.2 | +9.8 | +4.1 | $1,697 |
| 3 crypto bets a window | 28,369 | +5.1¢ | +1.9 | +6.6 | +10.1 | +6.7 | $1,390 |
| **all three** | 26,422 | **+6.7¢** | +3.5 | +7.7 | +12.8 | +7.8 | $1,709 |
| live bot · real liquidity | 24,493 | +3.2¢ | | | | | $581 |
| **all three · real liquidity** | 18,047 | **+6.9¢** | | | | | **$943** |

The bankroll replays from $225 at the bot's sizing assume every order fills in full, so their dollar endings are far
too high. The real-liquidity pair is the honest comparison:
- From Dec 10: the live bot ends at **$711** with a 46% deepest fall; all three end at **$1,887** with a 31% deepest
  fall.
- From Aug 24: $434 (45%) against $679 (26%).

## 3d. Limit orders instead of buying the ask: clearly worse (lab/maker.py)

The test: rest a buy for the favourite at minute 8, either at its bid, a cent over it, or a tenth of a cent under the
ask, and hold whatever fills.

The result: orders fill almost only when the favourite weakens, which is adverse selection (you get filled when you're
wrong).
- Filled orders won 89-93%; unfilled ones would have won 99.9%. Buying the ask wins 96.2%.
- Every version lost 20-50¢ per $10 in both halves, with or without a maker fee.
- The fill rule uses minute-close quotes, so it misses quick dips that bounce back. The real loss is probably smaller,
  but the sign is not in doubt.

## 3e. Market by market, second chances, choppy markets (lab/extras.py)

- **HYPE has no favourite bias.** The live rule's HYPE favourites won 94.7% at a 94.8¢ average ask, so the fee makes
  them a loser.
  - HYPE: −8.5¢ per $10 over 3,213 bets (pre −8.3, post −8.6).
  - With fills limited by the trade tape: −15¢.
  - Skipping HYPE takes the live rule from +4.47¢ to +5.74¢ per $10, and from $1,536 to $1,799 at $10 a bet
    (tape fills: +3.2¢ → +4.9¢, $581 → $824).
  - ZEC looks similar (−8.4¢), but it had only 108 bets before Jul 18, so the evidence is thinner.
  - Caveat: HYPE was the worst of 16 markets. Picking the worst of 16 gives about a 7% chance of a dip this big by
    luck. What supports it is that it lost in both halves.
- **Second chances lose.** A market that missed minute 8 and qualified later made +1.7¢ at minute 9 and −4 to −5¢ at
  minutes 10-12. Adding them drags the rule to −0.4¢. Keep the single entry at minute 8.
- **The choppy-market filter doesn't help.** Skipping favourites whose mid swung a lot over minutes 1-8 raises the
  profit per bet but drops bets that still make money. Total dollars fall, and the halves disagree.

## 4. Recommended strategy

**Keep the core. It's what the evidence supports:**
- buy the favourite at the end of minute 8 when its ask is 90-99.9¢
- skip 2¢+ spreads and late favourites
- skip the Fed afternoons
- buy at the ask with immediate-or-cancel orders
- hold to the close

Changes that don't hold up:
- later entries, second chances, a wider band
- limit orders: adverse selection
- trading on a spot model alone: a timing artifact

**Then add, in this order. Each was checked on both halves of the history:**
1. **At most 3 crypto bets a window, keeping the tightest spreads.** It's risk control. The coins lose together, and
   this halves the worst window (−17.7% → −9%) and trims the deepest fall in both halves, at almost no cost. Simple
   to build.
2. **Skip HYPE.** Its favourites carry no bias, so the fee makes them a steady loser. That held in both halves and
   is worse with real fills. Watch ZEC, which looks similar on less data.
3. **Skip the weekday 9:30 ET window,** when US stocks open. It lost in both halves, but on only 416 bets, so the
   evidence is thinner. It would be built like the Fed blackouts.

All three together, with fills limited by the trade tape:
- +3.2¢ → +6.9¢ per $10
- $581 → $943 at $10 a bet
- from Dec 10 at $225: $711 → $1,887, with the deepest fall 46% → 31%

**Next research step: the spot-price filter.** It's the strongest new signal, but the bot would need a live Coinbase
feed. The safe way in is to log what it would have skipped, with no money on it, for a couple of weeks, then compare.

**Caveat.** All of these were found by studying the same history. The live record is the real test. The check in
section 1, losses against expected losses, is how to watch it. Changing the bot means tests first, and a restart
outside the minutes when it places orders.

## Files

Everything below is in research/kalshi_15min/lab/:
- markets.npz (built by build_markets.py), common.py, web_research.md (online research with sources)
- maker.py, extras.py, edge_map.py (+ .md, test_edge_map.py), fair_value.py (+ .md, fetch_spot.py, fetch_strikes.py,
  tests/)

Elsewhere:
- strategies_backtest.py: the five candidates
- strategies.json, regenerated
- the dashboard's Research tab text and its tests (the tab has since been removed)
- new tests in tests/test_strategies_backtest.py and tests/test_real_liquidity.py

## 5. Unfilled contracts: raise the order's limit by about 1¢ (lab/fills.py, fills.json)

**The problem.** The bot sends one immediate-or-cancel order about 2 s after minute 8. Its limit is the ask it saw.
- When the price ticks up in those 2 s, the order gets nothing.
- When the book is thin, it gets only part.
- Kalshi's trade tape says that at $30 orders it gets only about 43% of the contracts it asks
  for, and nothing at all on about 1 order in 3.
- The orders that miss are mostly winners. The price ran away because the favourite was getting stronger.

**The test.** Raise the limit by X above the ask it saw, and replay all 35,793 live-rule bets on the tape.
- Contracts at the old price are charged the old price.
- Extra contracts are charged the tape's own dearer prices.
- An immediate-or-cancel order can only take what's on the book at that moment. So the dearer trades count only
  within W seconds of the order, with W from a generous 30 s down to a strict 2 s.
- Kalshi's exact fee is used.

| $30 orders, limit raised by | Contracts filled (strict to generous) | Profit per $10 | Total ($) | Extra contracts, profit per $10: strict (before Jul 18 / after), generous (before / after) |
|---|---|---|---|---|
| +0 (today) | 43% | +2.2¢ | $998 | - |
| +0.5¢ | 55% to 63% | +3.6 to +5.0¢ | $2,101 to $3,308 | +8.6¢ (+8.5 / +8.7), +11.2¢ (+9.9 / +11.7) |
| **+1¢** | **60% to 74%** | **+4.3 to +6.4¢** | **$2,717 to $4,943** | **+9.6¢ (+5.0 / +11.5), +12.3¢ (+8.3 / +14.2)** |
| +2¢ | 63% to 80% | +4.5 to +6.8¢ | $2,982 to $5,766 | +9.7¢ (+3.8 / +12.2), +12.2¢ (+7.2 / +14.7) |
| +3¢ | 63% to 82% | +4.6 to +6.9¢ | $3,070 to $6,002 | +9.9¢ (+5.0 / +12.0), +12.2¢ (+8.1 / +14.3) |

Strict: dearer trades count only within 2 s of the order. Generous: within 30 s.

- The extra contracts won 96.0-96.8% at about 94.7-95.4¢, so they earn more than the bot's average bet, in both
  halves.
- Most of the gain comes by +1¢; +2-3¢ adds a little more.
- At $10 orders the gain is smaller but the same shape. At $100 orders it matters more: today's limit loses there
  (−0.4¢), and +1¢ makes it +2.3 to +5.7¢.

**Caveats.**
- The tape shows trades, not the order book. The model was checked only at today's limit (126 vs 130 contracts on the
  first 76 real orders), never with a higher one.
- A raised limit pays up to X more on some contracts. Capping it at 99.9¢ keeps it from paying $1.
- Changing the bot's order price is a bot.py change: tests first, and a restart outside the entry minutes.

**Live check (lab/live_fills/: the bot's own 473 orders, Sep 28 to Oct 11, against the tape).**
- **Real fills:** 54.5% of contracts filled. 240 orders filled in full, 99 in part and 134 got nothing.
- **Why they miss:** other traders buy these favourites at exactly the minute-8 mark (480 s). The bot's order lands at
  about 482.4 s, by which time half the volume at its price is gone.
- **What +1¢ would have done:** caught 94 of the 134 orders that got nothing.
- **But no profit shows yet.** On these orders the extra contracts come out at −$25 ± $43 at +1¢ and −$11 ± $43 at
  +2¢.
  - That's noise either way: the whole sample has only 22 losing markets.
  - Markets where the bot got part of its order won only 92.9% (7 losses in 99, against about 3 expected from the
    history).
- **The model is optimistic.** On these orders it predicts 4-12% more contracts than really filled. Its old check
  (126 vs 130) doesn't replicate on the larger sample (153 vs 130 on the same 76 orders).
- **The historical split at $30 orders:**
  - Orders that fill in full win 95.35% at a 95.0¢ ask, about break-even. Full fills are the adversely selected
    ones.
  - Extra contracts at +1¢ earned +9 to +11¢ per $10 on orders that got nothing, and +17¢ on part-filled ones.
  - Both were positive before and after Jul 18.
- **Verdict:**
  - History says a 1¢ higher limit pays; two weeks of live orders can't confirm it yet.
  - The downside looks small, roughly break-even on the extra contracts, and the upside is large.
  - So it's a cheap, reversible experiment. Run it for about 1,000 orders and compare.
  - Sending at 480.0 s would attack the root cause, but that's a latency race with other bots and a bigger change.

**Other fixes, and why they're weaker.**
- A second order a few seconds later does about the same as a raised limit, with more moving parts.
- Resting orders for the rest get adversely selected (3d).
- Sending faster than ~2 s helps only the orders lost to that delay.
