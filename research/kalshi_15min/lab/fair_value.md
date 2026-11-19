# Fair value from the underlying: 15-minute crypto markets

**Question.** Can a coin's own spot price tell us which of the live bot's crypto favourites to skip, or which side to buy? The test uses a fair-value model, meaning a probability the coin finishes above its strike, worked out from where spot sits and how fast it has been moving.

**Short answer.**

- **As a filter, yes.** Skipping live-rule crypto bets the model prices below the ask added about +$280–300 on the half no setting was picked on, in both directions, and it survives spot that is a minute stale.
- **As a stand-alone strategy, no.** The model-only profits come from the spot and Kalshi prices being stamped the same second. With spot one minute old they turn into large losses.

Scripts: `fair_value.py` (analysis), `fetch_spot.py` (Coinbase candles), `fetch_strikes.py` (Kalshi strikes). Outputs: `fair_value.json` (every number), `fair_value.out.txt` (the printout). Tests: `tests/`, 14 passing. Spot data: `spot/`, gitignored.

## How these markets settle

From Kalshi's market rules (`rules_primary`):

- YES wins if the **simple average of the 60 seconds of CF Benchmarks' index (BRTI for BTC) before the close** is at least the same 60-second average **before the open**.
- `floor_strike` is that opening average. It is also the previous window's settlement value.
- Check: across 174,758 settled crypto markets, "settlement ≥ strike" matches the result 99.98% of the time.

## Coinbase vs the CF index

Coinbase is one of the index's input exchanges, not the index itself. The gap is Coinbase's average over the minute before the open, minus Kalshi's strike, in basis points (bp, hundredths of a percent).

| coin | median gap | median absolute gap | 95th pct absolute gap | Coinbase's own settlement call matches Kalshi |
|---|---|---|---|---|
| BTC | −0.7 bp | 0.9 bp | 3.1 bp | 96.8% |
| ETH | −0.7 bp | 1.1 bp | 3.8 bp | 97.2% |
| SOL / XRP / DOGE | −0.9 to −1.3 bp | 1.3–1.7 bp | 4.3–5.3 bp | 96.1–97.1% |
| BNB | −2.2 bp | 2.4 bp | 6.7 bp | **93.2%** (only 72% of minutes trade on Coinbase) |
| HYPE / ZEC | −0.8 / −1.9 bp | 2.7–2.8 bp | 8.6–8.9 bp | 96.2–96.4% |
| NEAR | **−4.9 bp** | 5.1 bp | 13.2 bp | 95.6% |

For comparison, a typical 15-minute move is 9–25 bp (median, depending on the coin). So the gap matters mainly when spot sits right on the strike.

## The model (end of minute m)

- **The formula:** P(YES) = F(x / (k·σ·√τ)), where:
  - **x** = ln(S/K).
    - **S** is the Coinbase close of the minute ending at the decision.
    - **K** is Coinbase's own average over the minute before the open. This beat Kalshi's strike as the anchor, because any steady Coinbase-vs-index gap cancels out.
  - **σ** is volatility, from an EWMA (exponentially weighted moving average) of 1-minute log returns with a 30-minute half-life. It only uses candles that closed by the decision, so there is no look-ahead.
  - **τ** = (14 − m) + 1/3 minutes. That is the time to the start of minute 15, plus a third of a minute because settlement averages over minute 15.
  - **F** is a Student-t curve with 3–6 degrees of freedom, which allows fatter tails (big moves more often) than a normal curve.
  - **k** is a scale factor of 0.65–0.75.
- **What was fitted on the train half only, by log loss** (a score that punishes confident wrong forecasts): the K source, the σ recipe, k and the tails. The choices were the same in both directions.
- **Calibration at minute 8** (lower log loss is better), on the test half:

  | | market mid | model | both together |
  |---|---|---|---|
  | test = Jul 18–Oct 8 | 0.4407 | 0.4450 | **0.4386** |
  | test = Dec 10–Jul 17 | 0.4441 | 0.4431 | **0.4391** |

  "Both together" is a logistic fit, made on the train half, that combines the market mid and the model. The model alone is about as good as the market, and together they beat it. So spot carries information the price hasn't fully absorbed at the end of the minute.

## Does the model's gap predict profit? (minute 8, live-rule crypto bets, test halves)

"Gap" = P_model(favourite) − the favourite's ask. Profit is ¢ per $10.

| gap | Jul 18–Oct 8 | Dec 10–Jul 17 |
|---|---|---|
| −0.20 to −0.10 | 149 bets, −46¢ | 91 bets, −34¢ |
| −0.10 to −0.05 | 662 bets, −34¢ (−59 to −9) | 524 bets, −20¢ |
| −0.05 to −0.02 | 1,768 bets, −6¢ | 1,619 bets, −11¢ |
| −0.02 to 0 | 3,752 bets, +4¢ | 4,198 bets, −1¢ |
| 0 to +0.02 | 6,263 bets, +8¢ | 6,527 bets, +4¢ |
| over +0.02 | 3,811 bets, **+17¢** (+9 to +25) | 2,647 bets, **+12¢** |

Profit rises with the gap in both halves. That pattern is the main evidence: it doesn't depend on any threshold.

## Backtests (minute 8)

- **Bets:** $10 in whole contracts, filled at the ask + 0.4¢, Kalshi's taker fee, held to settlement.
- **Base rule:** the live rule with its spread and late skips and the Fed blackouts.
- **Results:** crypto only, because the filter doesn't touch metals or energy.
- **Picking:** each threshold was picked on one half and tested on the other.
- **Ranges:** 95%, clustered by window.

| | test = Jul 18–Oct 8 (picked on Dec 10–Jul 17) | test = Dec 10–Jul 17 (picked on Jul 18–Oct 8) |
|---|---|---|
| (a) live rule | 16,441 bets, +5.20¢ (+0.9 to +9.6), $820 | 15,650 bets, +1.66¢ (−2.5 to +5.8), $250 |
| (b) skip if P_model < ask + margin | margin −1¢: 12,400 bets, **+9.43¢ (+5.0 to +14.0), $1,124** | margin −2¢: 13,372 bets, **+4.12¢ (0.0 to +8.2), $531** |
| (b) with spot 1 minute stale | 10,119 bets, +8.77¢, $852 | 11,048 bets, +5.70¢, $607 |
| (b2) same filter on market + model together | 13,237 bets, +10.20¢, $1,296 | 12,620 bets, +4.28¢, $519 |
| (c) model only: buy any side ≥ X under fair value | X = 10¢: 6,380 bets, +53¢, $3,333 | X = 15¢: 2,614 bets, +136¢, $3,490 |
| (c) with spot 1 minute stale | **−74¢, −$15,107** | **−99¢, −$16,168** |

What (b) would do to the whole live rule (35,793 bets, +4.47¢): Jul 18–Oct 8 goes from $1,287 to about $1,591, and Dec 10–Jul 17 from $250 to about $531.

**By coin (b, margin −1¢):**

- The gain comes from HYPE, ZEC, BNB and NEAR, plus SOL and XRP before Jul 18.
- HYPE goes from −$178 to +$15 after Jul 18, and ZEC from −$114 to +$23.
- BTC and ETH are flat to slightly worse; ETH is −$27 in each half.

**Other entry minutes, (a) → (b), test halves:**

| minute | Jul 18–Oct 8 | Dec 10–Jul 17 |
|---|---|---|
| 6 | $469 → $597 | $253 → $396 |
| 10 | −$461 → +$657 | −$30 → +$650 |
| 12 | −$1,172 → +$270 | −$1,315 → +$309 |

At minutes 10 and 12 the filter turns a losing rule into a winning one, but at minute 12 it keeps only 3–5k of about 37k bets.

## Caveats

1. **Timing.** Both prices are "end of minute" stamps, and their alignment within the minute is unknown. Model-only (c) lives on that alignment: it is chasing Kalshi quotes that haven't caught up with the last seconds of spot, which a fill would likely not get. Filter (b) only removes bets, and it holds with spot a minute stale.
2. **What was fitted.** Model choices (2 K sources × 5 σ recipes × 41 scales × 6 tail shapes) and margins were fitted on the train half. The gap-bucket pattern holding in both halves is the stronger evidence.
3. **The live bot would need a spot feed.** Using this live means a real-time Coinbase price and a 30-minute EWMA of volatility at 8:00. bot/ is untouched.
4. **Thin coins.** BNB trades in only 72% of minutes on Coinbase, and NEAR sits about 5 bp below the index. A multi-exchange price would match the index better.
5. **Fills.** Fills are not checked against the trade tape. Filter (b) needs no extra liquidity.
