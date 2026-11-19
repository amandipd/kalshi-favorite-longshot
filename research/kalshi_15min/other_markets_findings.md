# Other markets: first results (Oct 12 2026)

`python other_markets.py` on the finished `other_hours.csv` (199,738 markets that closed Jul 23 - Sep 30, the history
before Jul 23 isn't in Kalshi's store; 298,183 bets across 206 series). Full output: `other_markets_output.txt`.
Rule: buy the favourite at 90-99.9c, $10 a bet, series fee, filled 0.4c worse than the ask, held to settlement.

## What the table says

- **Every bet, no screen: it loses.** Almost every category and checkpoint is negative, many by 20-90c a $10 bet. Those
  asks are mostly on thin books (a wide bid-ask gap), so the recorded price isn't one you could buy at.
- **Only where the bid is within 3c of the ask, a few categories are positive in both halves** (Jul-Aug 31 and Sep 1 on).
  Read off the full table, so these are candidates, not results (PLAN_OTHER_MARKETS.md step 5):

| Candidate (liquid only) | Bets | Per $10 | 95% range (all dates) | Jul-Aug31 / Sep1 on |
|---|---|---|---|---|
| Weather, hourly, 30 min before | 5,857 | +7.1c | +3.6 to +10.6 | +6.8c / +7.8c |
| Weather, hourly, 10 min before | 3,508 | +6.5c | +2.3 to +10.8 | +6.0c / +7.3c |
| Weather, hourly, 45 min before | 6,125 | +4.6c | +0.8 to +8.4 | +4.7c / +4.5c |
| Economics, daily, 1 h before | 1,788 | +13.3c | +10.7 to +15.9 | +19.5c / +12.5c |
| Economics, daily, 3 h before | 1,947 | +7.4c | +2.9 to +11.9 | +11.0c / +6.9c |
| Commodities, daily, 1 h before | 813 | +14.6c | +5.8 to +23.4 | +15.9c / +12.3c |
| Commodities, hourly, 5 min before | 3,076 | +6.6c | +1.7 to +11.5 | +8.1c / +5.3c |

- **Hourly crypto, liquid: no edge** (-10.5c to +6.4c, ranges straddle zero, first half negative). Same as the 15-minute markets.
- **Financials, liquid:** ranges all straddle zero.
- **Sports daily, about -400c a bet: a quote quirk, not a bug.** It's all KXCS2MAP (Counter-Strike map winner). The
  settlements are sound (each map has one YES and one NO). But before a map starts, the book sits at placeholder
  quotes like 3c bid / 95c ask. Both sides then look like 95c+ favourites, and they win 50% of the time when the
  bid-ask gap is over 80c, against 98% when it's 3c or less. The liquid screen drops them.
- **BNB (KXBNB, KXBNBD), liquid: +15c to +29c, but Sep 1 on only** (no Jul-Aug history), so no out-of-sample test yet.

## The plan's pass test (added Oct 12, `pass_test()` in other_markets.py)

Liquid bets only. Candidates were chosen mechanically on closes before Sep 1 alone: 200+ bets, +2c or more a $10 bet,
95% range above zero. Then the Sep 1 to Sep 30 half was read once. 7 of the 96 groups were chosen; **4 passed**:

| Candidate | Before Sep 1 | Sep 1 on: bets | Per $10 | 95% range | Series | Days | Worst day | |
|---|---|---|---|---|---|---|---|---|
| Weather, hourly, 10 min before | 2,117, +6.0c | 1,391 | +7.3c | +1.0 to +13.6 | 9 | 30 | 9% | **PASS** |
| Weather, hourly, 30 min before | 3,886, +6.8c | 1,971 | +7.8c | +1.4 to +14.2 | 9 | 30 | 10% | **PASS** |
| Economics, daily, 1 h before | 202, +19.5c | 1,586 | +12.5c | +9.9 to +15.0 | 26 | 30 | 3% | **PASS** |
| Economics, daily, 2 h before | 209, +16.0c | 1,625 | +6.8c | +1.5 to +12.0 | 26 | 30 | 6% | **PASS** |
| Weather, daily, 2 h before | 487, +13.5c | 343 | -1.2c | -19.7 to +17.4 | 34 | 29 | 8% | fail: under +2c, range, under 1,000 bets |
| Commodities, daily, 1 h before | 510, +15.9c | 303 | +12.3c | -3.8 to +28.5 | 5 | 20 | 7% | fail: range, under 1,000 bets |
| Commodities, hourly, 10 min before | 1,266, +9.8c | 1,451 | -0.4c | -8.0 to +7.2 | 3 | 25 | 12% | fail: under +2c, range |

What the passes are, and why to be careful:

- **Two families of markets, not four:**
  - The weather rows are Kalshi's "Hourly Directional Temperature" markets (Miami, LA, NYC, Chicago, Austin, DC). Their
    series moved to new tickers in September (KXTEMPMIAH, KXTEMPLAXHS, ...). Miami is half the test bets.
  - The economics rows are the AAA gas-price markets (national and 25 states). They all close at 11:59 pm ET.
  - 10 and 30 minutes are the same markets read twice, as are 1 h and 2 h; a bot would pick one checkpoint of each.
- **Picking up pennies.** The median price paid is 98-99c, and the bets win 98.4% (weather) and 99.7% (gas) of the time.
  So the result rests on a handful of losses: 5 of 1,586 for gas at 1 h, since one loss costs about what 70-200 wins
  make (a win at 98-99c pays 5-14c). A day when gas jumps and every state market loses at once (they close together) hasn't happened in the sample.
- **Gas was thin before Sep 1:** 202 and 209 bets, just over the 200 needed, mostly the national market. The state
  markets grew in September.
- **The two weather lower bounds are barely above zero** (+1.0c, +1.4c), with 7 candidates read on the test half.
- **Small money:** about +$5 a day for weather at 30 min and +$7 a day for gas at 1 h, at $10 a bet.
- Not chosen, so not tested: hourly crypto (first half negative), BNB (no first-half bets), commodities hourly at 5 min
  (its first-half range touched zero).

**Not done:** the depth check: does $10 fill at the recorded ask? Median market volume is about 1,100
contracts for gas and 400-650 for weather. Plan "If something passes", step 1. No bot change.

## Depth check, part 1: the trade tape (Oct 12, `depth_tape.py`)

Does $10 fill at the recorded ask? Kalshi keeps no old order books, but it does keep every trade. For each of the
12,987 bets in the four passing groups (both halves; the same bets and backtest profit as the pass test), the tape
shows what takers actually bought on the favourite's side, at the ask + 0.4c or better, in the minutes after the
checkpoint (5 min for hourly, 30 min for daily). Full output: `depth_tape_output.txt`.

| Sep 1 on | Bets | $10 traded at our price | Median $ traded | Backtest | Only bets where $10 traded | Capped at what traded |
|---|---|---|---|---|---|---|
| Weather, hourly, 30 min | 1,971 | 29% | $1 | +7.8c | -3.0c | +0.2c (+$4 total) |
| Weather, hourly, 10 min | 1,391 | 45% | $7 | +7.3c | +2.8c | +2.3c (+$32) |
| Economics, daily, 2 h | 1,625 | 23% | $0 | +6.8c | +6.0c | +1.7c (+$28) |
| Economics, daily, 1 h | 1,586 | 8% | $0 | +12.5c | +4.5c | +0.6c (+$9) |

- **$10 rarely traded at our price**, and the median bet saw $0-7. The backtest's edge assumes every $10 fills.
- **Capped at what demonstrably traded, the edge nearly vanishes:** +0.2c to +2.3c a bet, $4-32 over the month per group.
- **This is a floor, not a verdict:** the tape shows only orders someone took, not resting ones nobody wanted. The live
  books say depth varies a lot: in the first 40 recorded temperature books, one 99c favourite had $1,200 on offer and
  another $0.51.
- The bets where $10 did trade were no better (weather 30 min: -3.0c), a hint that fills come when the price is about
  to turn, as on the 15-minute markets. Noisy: these are 98-99c bets where a few losses swing the mean.

## Depth check, part 2: live order books (running Oct 13 03:37 - Oct 20 03:37 UTC, `depth_books.py record`)

The full book at every checkpoint for the four groups' series, one week. `python depth_books.py report` then gives
the share of bets where $10, $25, $50 and $100 fill at the ask, and the profit at the prices the book really offered.
