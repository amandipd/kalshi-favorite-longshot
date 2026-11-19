# Kalshi 15-minute markets: bias replication and strategy research

Research run 2026-09-22/23; every backtest rebuilt on Sep 29 on every market since the first one,
Jul 18 to Sep 29 (74 days). Question: does the favorite-longshot bias found in the main study also
exist in Kalshi's 15-minute up/down markets, and can it be traded after real costs?

**Where it stands (Oct 11).** The history now runs from the first 15-minute market, Dec 10, 2025, to
Oct 11, 2026 (refreshed on the evening of Oct 11). Kalshi's historical endpoint filled in every crypto
market before Jul 18 (`fetch_pre.py`), and the trade tape around every live-rule bet since Dec 10 is in
`liquidity.json` (36,588 bets). `findings.json`, `key_stats.json`, `sizing.json`, `all_markets.json`,
`by_month.json` and `strategies.json` were rebuilt on Oct 10 over the history as it stood then, to
Oct 8. Sections 1-4 and the tables after section 7 are still from the Sep 29 rebuild over
Jul 18 to Sep 29, so rerunning a script gives different numbers from them;
[section 5](#5-before-jul-18-dec-10-2025-to-jul-17-2026) has the Oct 10 numbers and
[section 6](#6-where-to-start-buying-90-or-higher) the Oct 11 test of a higher lowest price, both to
Oct 8, and section 7 the live bot's real orders against the refreshed history. The seven months
before Jul 18 were never used to choose a rule. Over them, the rule the
live bot trades (90-99.9¢ favorites at minute 8, skipping both warning signs and the Fed afternoons)
made **+1.7¢ per $10 bet** with live-like fills (95% range −2.5¢ to +5.8¢): positive, but too small
to tell from zero on that stretch alone. Over the whole history it made **+4.5¢** (+1.8¢ to +7.3¢).
The plain rule, every 90-99.9¢ favorite, lost 11.1¢ a bet before Jul 18, because spreads were wide.
The paper trader that ran the rule from Sep 24 was retired on Oct 9. Since then the real-money bot in
[`bot/`](../../bot/) has traded it. Its first 488 real orders ([section 7](#7-the-live-bots-real-fills-live_fillspy))
got 54% of the contracts they asked for, at about the recorded ask, and on the markets both bought the
bot made what the backtest said it would.

**Short answer:** the bias is there: 90¢+ favorites won 95.8% of the time against 94.4% priced.
Buying 70¢ favorites doesn't survive fees. Buying **heavy favorites (90¢+)** at the recorded ask,
fees included, made **+3.6¢ per $10 bet** over all 74 days (95% range −0.4¢ to +7.6¢), and about
−0.4¢ with live-like fills. That is break-even, not an edge: it lost in the five weeks no rule was
chosen on (−5.9¢ a bet with live-like fills, Jul 18 to Aug 23) and made money after (+3.9¢). Started
on Jul 18, every sized account went broke by mid-August; started on Aug 24, they survive. Filtering
thin markets didn't help in a fair test; skipping wide spreads and late favorites did in both halves
(`findings.py`).

## This folder

The scripts sit in one flat folder on purpose. They import each other by module name and read and write their
data in the working directory, and the tests import them the same way, so run everything from this folder:

    cd research/kalshi_15min
    python -m pytest -q -p no:cacheprovider tests          # or, from the repository root: research/kalshi_15min/tests

The tests build a small synthetic market history in a temporary folder and never touch the network or the real
data. `lab/` holds the Oct 11 strategy lab (`lab/REPORT.md`), with its own tests in `lab/tests/` and
`lab/test_edge_map.py`. The [files table](#files) below says what each script does.

**The data is not in the repository.** Every minute file, snapshot, quote file and trade tape is rebuilt from
Kalshi's public API, with no account or key. In this order, from this folder (the long ones are resumable):

1. `python fetch_all15.py`: the 15-minute series (`universe.json`, kept) and `minutes_new.csv`.
2. `python backtest_large.py`, `python fetch_30d.py`, `python fetch_quotes.py`, `python fetch_minutes.py`: the first
   samples, `snapshots_8min.csv`, `snapshots_30d.csv`, `quotes_30d.csv` and `minutes_30d.csv` (only `thin.py` and
   the early scripts need the first three).
3. `python fetch_history.py`: every market from Jul 18 to the last full day, `minutes_ext.csv`.
4. `python fetch_pre.py`: every crypto market before Jul 18, `minutes_pre.csv` (7 to 11 hours).
5. `python history.py`: joins the minute files into `snapshots_all.csv`.
6. `python liquidity.py fetch TAPE 2025-12-10`, then `python liquidity.py reduce TAPE 2025-12-10`: the trade tape
   around every live-rule bet (about 110 MB, kept anywhere outside the repository) and `liquidity.json`.
7. `python strategies_backtest.py`: every account replayed, `strategies.json` (about 25 MB). The bot's dashboard
   reads it; without it the dashboard's replay panels stay empty.

The other studies' inputs come the same way: `fetch_other.py list` and `fetch_other.py candles` for the hourly,
daily and weekly markets (`other_markets.json`, `other_hours*.csv`), `fetch_skipped.py` for the 15-minute series the
bot skips (`minutes_skipped.csv`), and `lab/build_markets.py` then `lab/edge_map.py` for the lab (`lab/markets.npz`,
`lab/edge_map.json`). The small JSON results the text quotes (`findings.json`, `key_stats.json`, `sizing.json`,
`by_month.json`, `all_markets.json`, `price_floor.json` and the like) are kept.

Some numbers below come from the live bot's own orders: `live_fills.py`, `live_losses.py`, `lab/live_fills/` and
`lab/fast_entry/timing.py` read its order ledger (a SQLite file, opened read-only). The ledger and the files built
from it (`live_fills.json`, `live_losses.json`, `lab/live_fills/*.json`, `lab/fast_entry/timing.json`) are not
included, so those results can be read here but not rebuilt. `strategies_backtest.py` leaves out the two "live
fills" accounts when `live_fills.json` is missing.

## Data

The files named here are rebuilt by the scripts (see above); none of them is in the repository.

- 16 live 15-minute series: BTC, ETH, SOL, BNB, XRP, HYPE, NEAR, DOGE, ZEC,
  gold, silver, platinum, copper, palladium, natural gas, WTI. Crypto markets run
  24/7; the others go dark on weekends.
- Every market is sampled at the **8-minute mark**, from Kalshi's public API:
  last traded price, best bid/ask, volume, and the final result.
- `minutes_30d.csv`, `minutes_new.csv`, `minutes_ext.csv`: every minute (last trade, bid, ask) of
  every 15-minute market from Jul 18. `fetch_history.py` brings them up to the last full day (on
  Oct 11, to the end of Oct 11 UTC: 5,378 more markets), and `history.py` joins them with
  `minutes_pre.csv`, one row per market.
- `minutes_pre.csv` (from `fetch_pre.py`): the same for every crypto market before Jul 18, back to
  each series' first: BTC and ETH from Dec 10, 2025, SOL Jan 9, XRP Feb 11, BNB Mar 7, DOGE and HYPE
  Mar 18, NEAR and ZEC Jun 30 (111,226 markets; 285 had no price history). The first three files were
  listed from Kalshi's live endpoint, whose live/historical cutoff sat near Jul 18 when they were built,
  so the history looked as if it began there. Kalshi's historical endpoint lists the rest. Metals and
  energy really did begin later, on Jul 31. The file also holds 855 crypto markets that opened on
  Jul 18 UTC (95 windows × 9 series) and that none of the other files had. `history.py` adds them, so
  every Jul 18 to Aug 23 figure moved slightly on Oct 10.
- `snapshots_all.csv` (from `history.py`): **203,028 markets** in crypto, metals and energy, from the
  first window (11:15 pm ET on Dec 10, 2025) to Oct 8, 2026, at minute 8. It was last written on
  Oct 10; the minute files now run to Oct 11, and `history.py` brings it up to them. Every backtest
  reads this or the minute files, so each covers the whole history.
- The original samples, kept for `thin.py`: `snapshots_8min.csv` (26,883 markets over 26 days),
  `snapshots_30d.csv` (35,605 markets, Aug 24 to Sep 23) and `quotes_30d.csv` (bid/ask, volume and
  time since the last trade for the 13,629 markets whose favorite was at 85¢+).

## 1. The bias replicates

How often contracts actually resolved YES, compared with their price at minute
8 (80,524 markets, Jul 18 to Sep 29, `analyze.py`):

| Price band | n | Priced | Actually happened | Gap (pts) |
|---|---|---|---|---|
| 0-10¢ | 9,779 | 5.57% | 4.50% | −1.07 |
| 10-20¢ | 8,854 | 14.47% | 12.65% | −1.82 |
| 20-30¢ | 7,821 | 24.38% | 22.22% | −2.16 |
| 30-40¢ | 6,739 | 34.40% | 33.21% | −1.19 |
| 40-50¢ | 6,304 | 44.55% | 43.42% | −1.13 |
| 50-60¢ | 6,143 | 54.47% | 54.78% | +0.31 |
| 60-70¢ | 6,801 | 64.60% | 66.17% | +1.56 |
| 70-80¢ | 7,644 | 74.65% | 75.68% | +1.03 |
| 80-90¢ | 8,983 | 84.70% | 86.02% | +1.32 |
| 90-100¢ | 11,456 | 94.36% | 95.80% | +1.44 |

It's the same shape as the main study: longshots are overpriced, favorites
underpriced, and the sign flips near 50¢. This is a different instrument on a
timescale about 250 times shorter.

## 2. Costs are the whole game

- **Taker fee** (paid when you fill instantly at the listed price):
  `ceil(M × 0.07 × contracts × P × (1−P))`, rounded **up to the cent per
  order**. **Maker fee** (for resting orders that wait to be filled): 25% of that.
  The multiplier M is 1.0 for standard markets and higher for crypto; the exact
  crypto value is unconfirmed, because the fee PDF is behind bot protection.
- Per dollar staked the taker fee is `0.07 × (1−P)`: **2.1% at 70¢, 0.4% at
  94¢**. The edge is roughly 2% per dollar in both bands, so fees wipe out the
  70¢ trade but leave most of the 90¢+ one.
- The cent rounding kills small orders. On a $1 bet at 70¢ the 2.1¢ fee is
  charged as 3¢, which is 3% of the stake against a 2.15% edge.
- Bets placed in the same window move together: +0.30 correlation, because
  crypto series move as a group. Worst case seen: 11 favorites lost in a single
  15-minute window.
- **Live, the fee isn't rounded up.** The bot's first 488 orders paid $13.53 in
  fees, against $13.52 from the formula with no rounding and $15.48 rounded up
  to the cent per order (section 7). So the backtests' cent rounding overstates
  the fee, most on small orders. Only the live-fills accounts charge it exactly.

## 3. Strategy results, Jul 18 to Sep 29 (74 days)

Bet the favored side at minute 8, priced by its last trade, hold to settlement (`simulate2.py`).

| Strategy | No fees | Taker fees | Fees + 1¢ worse fill |
|---|---|---|---|
| 70¢ favorites, $24, 1/24 of bankroll per bet | $1,535 | broke Jul 28 | broke Jul 25 |
| 70¢ favorites, $240, $10 per bet | $3,094 | broke Jul 20 | broke Jul 20 |
| 90¢+ favorites, $24, 1/24 per bet | $1,477,400 | broke Aug 3 | broke Jul 28 |
| 90¢+ favorites, $240, $10 per bet | $3,353 | $2,369 | broke Jul 30 |

At the last trade price the 90¢+ trade makes +9.7¢ a $10 bet with fees (95% CI +5.7¢ to +13.7¢,
`check_ab.py`), but that price isn't the one you pay. The real ask at minute 8 averaged 0.38¢ above
the last trade (median 0.1¢) and was at or below it 41.6% of the time (`sim_real.py`), and a single
cent more turns the whole history to −0.2¢ a bet.

### At the real ask, over the whole history

Buy the favorite whenever its **ask** is 90-99.9¢ at minute 8; $10 per trade; taker fee included
(`minutes.py`, `sim_real.py`, `findings.py`).

| | |
|---|---|
| Bets / win rate | 24,158 / 95.1% (break-even needs 94.8%) |
| Profit per $10 bet | **+3.6¢** (95% range −0.4¢ to +7.6¢, clustered by window) |
| First half / second half | −1.9¢ / +8.1¢ a bet |
| With live-like fills (0.4¢ a contract worse) | −0.4¢ a bet: −5.9¢ Jul 18 to Aug 23, +3.9¢ Aug 24 to Sep 29 |
| $240 at $10 a bet, from Jul 18 | broke by Jul 30, at every crypto fee multiplier from 1× to 2× |
| From Aug 24, live-like fills | $762, +3.9¢ a bet, worst drop 35% (`strategies_backtest.py`) |
| Weeks with a profit | 7 of 12; the week of Jul 27 alone lost $457 (favorites won 92.8%) |
| Worst 15 minutes | −$110 (the Sep 16 Fed decision, 11 of 14 lost) |

## 4. Thin-market filters (Aug 24 to Sep 23 only)

These need the volume and time since the last trade that only `quotes_30d.csv` records, so `thin.py`
stays on those 30 days. The full history's spreads and price moves are tested in `stress_signals.py`
and `findings.py`.

- **Stale prices:** a non-issue. Every 90¢+ market traded in minute 8.
- **Volume:** in the full sample, profit per bet rises steadily from the
  quietest fifth of markets (+2.7¢) to the busiest (+18.3¢).
- **But it doesn't survive out of sample.** Of 96 filter combinations, the best
  one on the first half was "skip the quietest 40%". On the second half it made
  +7.4¢ per bet, against +7.8¢ with no filter. Over the full month it ended at
  $996 versus $1,164, though its max drawdown was lower (20% vs 27%).
- **Leads for future testing** (spotted in the full sample, so not proven):
  - spread wider than 2¢: −7.6¢/bet (1,222 bets)
  - favorite jumped more than 5¢ in the last minute: +1.4¢ (3,401 bets)
  - last trade outside the current quotes: +5.5¢, vs +10.6¢ inside
  - HYPE: −17.2¢. One significant series out of 16 is roughly what chance
    would produce.

## 5. Before Jul 18: Dec 10, 2025 to Jul 17, 2026

Rebuilt Oct 10. Every rule in this research was chosen on Jul 18 to Sep 29, so the seven months before
Jul 18 test them on markets none of them saw. Only crypto traded then (9 coin series). Per $10 bet,
with live-like fills (the recorded ask plus 0.4¢ a contract, and the taker fee), 95% range clustered by
window (`by_month.py`):

| Per $10 bet | Dec 10 to Jul 17 | Jul 18 to Aug 23 | Aug 24 to Oct 8 | Whole history |
|---|---|---|---|---|
| Plain rule: every 90-99.9¢ favorite at minute 8 | **−11.1¢** (−14.5 to −7.7) | −5.9¢ (−11.8 to +0.0) | +2.8¢ (−1.9 to +7.5) | −6.5¢ (−9.1 to −4.0) |
| Live rule: the same, skipping both warning signs and the Fed afternoons | **+1.7¢** (−2.5 to +5.8) | +5.4¢ (−1.1 to +11.8) | +7.5¢ (+2.8 to +12.1) | **+4.5¢** (+1.8 to +7.3) |

| | Plain rule, Dec 10 to Jul 17 | Live rule, Dec 10 to Jul 17 | Live rule, whole history |
|---|---|---|---|
| Bets | 36,445 | 15,650 | 35,793 |
| Won vs the all-in cost | 94.40% vs 95.45% | 96.26% vs 96.10% | 96.20% vs 95.78% |
| One-bet Kelly | −23.0% | +4.2% | +10.1% |
| Average spread | 4.42¢ | 0.85¢ | |
| At $10 a bet | −$4,047.62 | +$263.83 | |

**The answer.** Before Jul 18 the live rule's edge is positive but small, and that stretch alone can't
tell it from zero. Over the whole history it is clearly positive. The bias was there all along:
crypto favorites at 90%+, priced at the mid, were priced 94.5% and won 95.8% over the whole history
(`all_markets.py`). What changed is the spread. The plain rule's average spread fell from 12.5¢ in
December to 0.8¢ in October, and before July paying the ask cost more than the bias paid.

**The spread filter is what saves it.** The plain rule before Jul 18, by fifth of the gap between ask
and bid at minute 8 (`stress_signals.py`):

| Gap at minute 8 | ≤ 0.3¢ | 0.3-0.9¢ | 0.9-1.7¢ | 1.7-3¢ | 3¢ or more |
|---|---|---|---|---|---|
| Per $10 bet | +1.0¢ (−6.9 to +9.0) | +6.1¢ (+0.7 to +11.4) | −0.8¢ | −6.9¢ (−12.4 to −1.4) | **−34.0¢** (−40.0 to −28.1, 10,930 bets) |

So skipping wide spreads turns the plain rule's −11.1¢ into roughly break-even. Over the same months,
favorites whose lowest price in minutes 1-8 stayed at 65.5¢ or higher made −2.3¢, against −23.4¢ for
those that dipped to 43.5¢ or below, and bets in the US news slots made −37.1¢ (872 bets).

**By month**, per $10 bet (live rule bets in brackets). Only August and September have 95% ranges
wholly above zero:

| | Dec | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct (to the 8th) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Live rule | +4.1¢ (37) | +10.1¢ (452) | +5.9¢ (1,120) | −7.2¢ (2,031) | +7.5¢ (2,822) | −4.4¢ (2,899) | +6.0¢ (3,533) | +1.3¢ (5,033) | +8.9¢ (6,637) | +7.1¢ (8,700) | +3.5¢ (2,529) |
| Plain rule | −17.6¢ | −12.5¢ | −7.6¢ | −22.3¢ | −12.7¢ | −10.5¢ | +1.9¢ | −13.7¢ | −1.3¢ | +3.5¢ | −0.6¢ |

By market, the live rule before Jul 18: DOGE +11.1¢ (+2.5 to +19.6), ETH +5.6¢, SOL +1.8¢,
XRP +1.3¢, BTC +0.1¢, BNB −1.6¢, ZEC −4.0¢ (108 bets), HYPE −8.3¢, NEAR −30.4¢ (82 bets).

**The live bot, replayed from Dec 10** (`strategies.json`, `starts.dec10`): $225, 3% a bet, at most 20%
a window, whole contracts, no cap on an order's size (as the bot has traded since Oct 10), both warning
signs and the Fed afternoons skipped. The `livecap` accounts ("The live bot · $10 cap") are the same with
the old cap of $10 an order.

| From $225 on Dec 10 | On Jul 17 | Per $10 bet to Jul 17 | Worst drop to Jul 17 | On Oct 11 |
|---|---|---|---|---|
| **Live fills** (`livefit`, section 7) | $1,062.98 | +6.2¢ (+2.0 to +10.3) | 27.9% | $4,745.71 (worst drop 27.9%) |
| **Real liquidity** (`liveliq`) | $288.77 | +3.3¢ (−1.1 to +7.7) | 40% ($402 on May 9 → $243 on Jul 9) | $872.03 (worst drop 46.5%) |
| Live-like fills, every order filled in full | $284.24 | +1.5¢ (−2.6 to +5.7) | 59% ($401 on May 9 → $165 on Jun 7) | $13,788.83 |
| The recorded ask, every order filled in full | $1,914.42 | +5.8¢ (+1.7 to +10.0) | | $1,114,254 |
| $10 cap: real liquidity | $312.55 | +3.3¢ (−1.1 to +7.7) | 36.5% ($406 on May 9 → $258 on Jun 3) | $727.01 on Oct 8 (not rerun) |
| $10 cap: live-like fills | $288.46 | +1.5¢ (−2.6 to +5.7) | 58% ($396 on May 9 → $166 on Jun 7) | $1,700.91 |
| $10 cap: the recorded ask | $1,024.90 | +5.6¢ (+1.4 to +9.7) | 32% | $3,276.28 |

Without a cap, an account filled in full compounds into orders far bigger than the book ever held, so
$13,789 and $1.1 million can't be reached. The two realistic rows bracket the truth:
- **Real liquidity** gives each order only what the trade tape shows others traded at the candle ask. It
  undercounts: on the live bot's own orders it predicted 2,104 contracts against 2,970 real.
- **Live fills** gives each order what the live bot's real orders of that size got in that market, at the
  ask (what live fills really paid), with the exact fee. It caps every order at the biggest fills live
  orders have shown, so its growth after about $1,000 is an assumption, not a measurement: asked 1.96
  million contracts over the history, it expects 464,000 (24%).

Rerun on Oct 11 with the data through Oct 11 (`live_fills.py`, then `strategies_backtest.py`).

"Real liquidity" fills at the recorded ask, but each order only as far as the trade tape says others
traded at that price or better (`liquidity.py`). Over the whole history 24,493 of the 35,793 orders
filled at least in part (9,003 of them only in part), for 51% of the contracts asked for (221,751 of
434,443). The 11,300 orders that got nothing would have won 96.4% of the time, so the misses aren't
picked-out losers. Like for like at the recorded ask, the tape cuts Dec 10 to Jul 17 from +5.8¢ to +3.3¢
a bet, and the whole history from +9.9¢ to +2.3¢, with the one-bet Kelly from 18.0% to 9.7% (from Jul 18:
+9.9¢ to +3.3¢, from Aug 24: +9.9¢ to +3.5¢, half the contracts filled in both; `key_stats.json`,
`realFills`). Real liquidity beats live-like fills before July only because it has no 0.4¢ slip.
The live bot's own orders are a check on both ([section 7](#7-the-live-bots-real-fills-live_fillspy)):
they got 54% of the contracts they asked for, at about the recorded ask, with no slip.

**Halts.** The live bot's three money halts, replayed window by window with no order cap: with
live-like fills from Dec 10, the halt for a 35% fall within 24 hours fires once, on Jul 8, 2026 (a 35.9%
fall). From Jul 18 the worst 24 hours is 34.8% (Jul 30), so it never fires, and from Aug 24 the worst is
31.5% (Sep 28). The half-the-start halt never fires (lowest $165 against a $112.50 floor), and no window
had more than 6 losses. Filled in full at the recorded ask it fires on Jul 8 from Dec 10, and on Jul 30
from Jul 18 (35.1%). With real liquidity it never fires (worst 26.1%). With the old $10 cap the worst
24 hours were 35.4% (Jul 8), 34.8% and 21.8%. The bot checks after each bet, not each window, so Jul
30's 34.8% might have tripped it. The
row "24-hour rule loosened to 35%" in `findings.json`'s halts stops on Jan 9 at half the start, but
that row is the plain rule at the bot's sizing from $100, not the live bot.

**Worst 24 hours, in every run** (Oct 12). Each run in `strategies.json` now carries the deepest fall
from a high within any 24 hours, the measure the live bot's 35% halt watches (`bot.py`, `check_halts`):
`worst24hPct` as a share of that high, `worst24h` in dollars, and `worst24hAt`, the close of the window
where it hit bottom (UTC; `None` if it never fell). It's counted window by window, since a window's bets
all settle at its close, and the high includes the bankroll held when those 24 hours began. The
Strategies view shows it beside the worst drop over the whole history. Rerun on Oct 12, it gives the
same figures as the halt replay above:

| The live bot | From Dec 10 | From Jul 18 | From Aug 24 |
|---|---|---|---|
| Live-like fills, every order filled in full | −35.9% (Jul 8) | −34.8% (Jul 30) | −31.5% (Sep 28) |
| **Live fills** (`livefit`) | −20.0% (Jul 8) | −23.0% (Jul 30) | −14.8% (Sep 2) |
| **Real liquidity** (`liveliq`) | −26.1% (Jul 8) | −23.5% (Sep 28) | −23.7% (Sep 28) |
| All three lab changes (`live3x`), live-like fills | −27.0% (Sep 29) | −27.0% (Sep 29) | −26.8% (Sep 29) |
| All three · live fills (`live3xfit`) | −16.0% (May 22) | −12.2% (Jul 30) | −9.2% (Sep 10) |

**Sizing, stops and selling early** test the plain rule, so over the longer history they now say no
size or stop works for it:

- `sizing.py`: one-bet Kelly −4.7% at the recorded ask (won 94.71% against a cost of 94.95%), −13.7%
  with realistic fills and −22.1% under stress. Resampled 30 days from $240 at 3% a bet and 20% a
  window, realistic fills: a 96% chance of a loss and 30% of going broke; at 90 days, 98% broke. The
  live rule's Kelly fractions are the ones above.
- `risk_rules.py`: from Dec 10 and from Jul 18 the plain rule goes broke or stops under every
  profit-taking rule and every stop. Only from Aug 24 does it end up ($10 a bet, nothing taken out:
  $719). The best stop from Dec 10, the rising floor at 70% of the peak (Grossman-Zhou), keeps $180 of
  $240. Losses still don't cluster usefully: the day after a −$30 day made −10.6¢ a bet, against −8.7¢
  after any other day.
- `exit_timing.py`: over 64,434 favorites, holding to settlement beat selling at the bid in every
  minute from 9 to 14 and every bid band, with every 95% range above zero. Hold.

## 6. Where to start buying: 90¢ or higher?

Run Oct 11. Live, the bot's 90-91¢ bets had gone 37 won, 10 lost (−$5.97), 10 of its 15 losses, while
every band from 92¢ up made money. `price_floor.py` replays the live rule (`strategies_backtest.LIVE`)
over the whole history, about 36,000 bets, with only the lowest price changed: 90, 91, 92, 93 or 95¢
(→ `price_floor.json`, drawn at the bottom of the bot dashboard's Research tab, Edge view).
That live count rounded the price paid. Banded as the backtest bands its bets, by the ask the bot saw
when it decided (orders often fill below it), the live 90-91¢ bets were 47 won, 11 lost, −$0.15 on
Oct 11: about break-even, against +$31 to +$41 for 92-94¢ and 95-97¢.

**By price band**, at $10 a bet with live-like fills: 90-91¢ made **+6.6¢** a bet (−1.1 to +14.3,
6,291 bets, rerun with the data through Oct 11), as much as any band. It lost only from Sep 24 on (−8.4¢), when 95-97¢ lost too.

**With real liquidity** (the trade tape around every live-rule bet since Dec 10): in every band the
orders that didn't fill won more often than the ones that did. That is adverse selection: an order fills
most easily when other traders are keen to sell, and they're keener when the favorite is likelier to
lose. The gap is about 2 points from 90¢ to 94¢ (90-91¢: 91.7% of filled orders won, against 93.5% of
unfilled ones; 92-94¢: 94.2% against 96.0%) and a few tenths from 95¢ up. With real fills 90-91¢ makes
+3.4¢ a bet and 92-94¢ +2.1¢, against +5.3¢ to +6.6¢ from 95¢ up, though the ranges overlap (Oct 8 run).
The live bot's own orders don't show this gap so far: its missed orders won 95.3% of the time, the same as
its filled ones (section 7).

**At the bot's own sizing** from $500 on Dec 10 (3% a bet, at most 20% a window, whole contracts),
with real liquidity:

| Lowest price | 90¢ | 91¢ | 92¢ | 93¢ | 95¢ |
|---|---|---|---|---|---|
| On Oct 11 (rerun with the data through Oct 11) | $1,308 | $1,251 | $1,497 | $1,879 | $1,696 |
| Worst drop | 49% | 42% | 46% | 33% | 23% |

The order changes from one period to the next, and with every order filled in full it reverses. So
there is no clear evidence that a higher floor earns more; what it does buy is smaller swings. The bot
still buys from 90¢.

## 7. The live bot's real fills (`live_fills.py`)

Run Oct 11, on the data refreshed that evening (to the end of Oct 11 UTC). The live bot sends one
immediate-or-cancel order per bet: an order that takes whatever the book has at its price right away and
cancels the rest. It goes about 2 seconds after minute 8, with its limit at the ask the bot saw, so it
often gets only part of what it asks for, or nothing. Every backtest but the real-liquidity ones fills
each order in full. `live_fills.py` reads the bot's ledger (`bot/state/live-prod.db`, opened read-only
and copied into memory at once, so the bot is never held up), sets each real order against the research
data, and writes `live_fills.json`. The first run covered **488 orders, Sep 28 to Oct 12 UTC**.

**What the orders got.** 246 filled in full, 102 in part and 140 not at all: **3,724 of the 6,882
contracts asked for (54.1%)**.

- By size (contracts asked for): 1-5 got 72%, 6-15 52%, 16-30 55%, 31+ 49% (only 30 orders).
- By group: crypto 54%, metals 44%, energy 71%.
- By price band (the order's limit): 90-91¢ 52%, 92-94¢ 49%, 95¢+ 58%.
- By market: among the coins, BTC filled best (79%) and NEAR worst (41%).

**Price.** Fills averaged 0.23¢ a contract under the bot's limit, and the limit averaged 0.21¢ over the
candle ask (the ask recorded in the research data at the end of minute 8). So on the 319 orders with
both, fills came to **about 0.00¢ over the candle ask**. The backtests' "live-like fills" charge 0.4¢ a
contract over it, which is too pessimistic: live fills cost what the candle ask says.

**Which orders miss.** The orders that got nothing would have won as often as the ones that filled:
122 of 128 (95.3%) against 324 of 340 (95.3%). So no adverse selection shows: the filled orders aren't
the worse bets, as the trade tape found them to be from 90¢ to 94¢ (section 6). This is on far fewer bets.

**Fees.** $13.53 paid, against $13.52 from Kalshi's formula, 7% × contracts × price × (1 − price), and
$15.48 with the backtests' rounding up to the cent on every order. Kalshi charges the exact fee.

**The trade-tape model.** `liquidity.py`'s fill rule, used at the candle ask as the real-liquidity
accounts use it, covers 421 of the orders. It predicts 2,104 contracts against 2,970 real: it
undercounts, because the bot's limit sits slightly above the candle ask. It said "nothing" on 220 of
those orders, and 130 of them got some; it said "some" on 201, and 32 of them got nothing. For a market
the bot traded, the raw tape holds the bot's own fills too; the lab's check in `lab/live_fills/` takes
them out.

**The fill table ("depth").** The live-fills accounts need to know what an order of any size can expect.
Each real order says how many contracts were waiting at the bot's price, but not always exactly:

- one that filled in part shows it exactly: the book had what it got;
- one that got nothing shows the book had none;
- one that filled in full shows only that there were at least that many. That's a censored count: a
  floor, not the real number.

Kaplan-Meier, the estimate medical studies use when some patients are still alive at the end (they only
show they lived at least that long), is made for counts like that. It gives the chance the book had at
least 1 contract, at least 2, and so on, and adding up the first c of those chances gives what an order
for c contracts gets on average. Over all 488 orders the book had at least one contract 71% of the time;
an order for 10 contracts expects 6.2, and one for 30 expects 16.3. A market with 15 or more live orders
(`MIN_ORDERS`) gets its own table; one with fewer uses its group's, and a group with fewer uses the table
from every order. Today every coin has its own table, and metals and energy use their group's. A table
stops at the most its market's orders have shown, and asking for more adds nothing: in SOL, XRP, HYPE and
NEAR that's 18 contracts.

**The live-fills accounts.** With `live_fills.json` present, `strategies_backtest.py` adds two:
"The live bot · live fills" (`livefit`) and "The live bot · all three · live fills" (`live3xfit`, with
the Oct 11 lab's three changes). Each is "The live bot" or "The live bot · all three" with one change:
every order gets the expected
fill from its market's table (so it can be part of a contract), at the minute-8 ask plus the gap real
fills paid over it (about 0.00¢ now), with Kalshi's fee charged exactly. The Fills switch on the
dashboard doesn't change them. On the Research tab each has a "Filled like live orders" panel: orders
sent, the share of contracts they can expect to fill, and the orders expected to get nothing. Until Oct
12 the dashboard left these figures (`liveFit`) out of what it sends the page, so the panel never showed;
it shows once the dashboard runs the Oct 12 code. It's today's books applied to the whole history; the
real-liquidity accounts use each market's own trades instead.

**The backtest against the bot, market by market.** Over the 186 windows the bot was running (it logs a
decision for every market it looks at, so a window with none is one it didn't see):

- The backtest's live rule picked 447 markets. The bot ordered 421 of them, all on the same side.
- 26 only the backtest picked: 8 while the bot was halted, 11 where the bot saw a warning sign at its
  moment, 6 outside the 90-99.9¢ band at the bot's price, and 1 with no decision logged.
- 67 only the bot ordered: 41 after the data ends, 11 outside the band at the candle, and 15 with a
  warning sign at the candle.
- **On the 299 markets both bought and the bot filled, the backtest made +15.5¢ per $10 and the bot
  +16.1¢.** On the same markets, the live bot's execution matches the backtest.
- The 20 filled bets only the bot made (the candle rule wouldn't have made them) won 15 of 20:
  −$1.19 on $111, a small sample. Counted as $10 bets each, they pull the bot's average over all its
  319 filled bets down to +2.8¢ (the backtest's over its 447: +14.3¢).

**The lab's changes on the live bets.** The live bets each would have dropped, and the real profit they
made (so the profit the change would have given up):

| Change | Filled bets dropped | Won | Profit given up |
|---|---|---|---|
| Skip HYPE | 41 | 39 | $8.86 |
| Skip the 9:30 ET window | 0 | | $0 |
| At most 3 crypto bets a window | 107 | 98 | $28.07 |
| All three | 126 | 117 | $30.92 |

So far, on live data, each would have cost money. But the live bets have had only 16 losses in all, so
this is no verdict. The lab's own results (`lab/REPORT.md`) are on the history to Oct 8.

**Caveats.** 488 orders and 16 losses is a small sample. The fill table applies today's order books to
the whole history, back to December. And fills on larger orders are uncertain: only 30 orders were for
31 contracts or more.

**To rerun**, from this folder:

1. `python fetch_history.py` (while the bot runs, keep it off minutes 7:50-9:20 of each quarter hour,
   when the bot orders)
2. `python liquidity.py fetch ../../data/liquidity_tape.jsonl 2025-12-10`, then
   `python liquidity.py reduce ../../data/liquidity_tape.jsonl 2025-12-10`
3. `python live_fills.py` (or `python live_fills.py LEDGER.db` for another ledger)
4. `python strategies_backtest.py`, which reads `live_fills.json` and `liquidity.json` at start

On Oct 11 the first two added 5,378 markets to `minutes_ext.csv` and 795 bets to `liquidity.json`, which
now covers 36,588 live-rule bets.

## Caveats

1. The 90¢+ rule was chosen on Aug 24 to Sep 23, and the warning signs the live bot skips on
   Jul 18 to Sep 29. The seven months before Jul 18 are the one stretch no rule saw: the plain rule
   lost 11.1¢ a bet there, and the live rule made +1.7¢, too little to tell from zero (section 5).
2. The history is ten months, Dec 10, 2025 to Oct 11, 2026, with only crypto before Jul 18. The live
   rule's months range from −7.2¢ to +10.1¢ a bet, and only August and September are clearly
   positive. Which kind of month comes next is the whole question.
3. Kalshi's catalog lists a fee multiplier of 1 for every 15-minute series, crypto included
   (`universe.json`). The 2× crypto fee in the stress scenarios is a what-if, not today's fee.
4. Historical data shows the best price but not the size available at it. The trade tape bounds it
   from below (`liquidity.py`): filled only as far as others traded at the bot's price or better,
   the live bot gets 51% of the contracts it asks for since Dec 10 (section 5). The book may have
   held more than traded. The bot's real orders got 54% (section 7), but that's two weeks of today's
   books, and only 30 of its orders were for 31 contracts or more. On price, its fills came to about
   the recorded ask, so the 0.4¢ slip in "live-like fills" is on the cautious side.
5. Losses cluster in time. Size bets per window, not per bet.

## Next steps

Done since the first version of this list:

- **Forward paper trading** ran from Sep 24 to Oct 9, then gave way to real orders (`bot/`).
- **The crypto fee multiplier** is 1, from Kalshi's own catalog (caveat 3).
- **The leads** were tested on the full history (`stress_signals.py`, `findings.py`). Favorites with a
  2¢+ spread, and favorites that were 50¢ or under at minute 6 or 7 or jumped 10¢+ in minute 8, lost
  money in both halves. The bot skips both since Oct 9.
- **The history before Jul 18** (Oct 10): every crypto market back to Dec 10, 2025 (section 5).
- **Real liquidity** (Oct 10): `liquidity.py` read Kalshi's trade tape around every live-rule entry
  since Dec 10, and `strategies_backtest.py` replays "The live bot · real liquidity" from it. The bot's
  first 76 real orders had got 70% of the contracts they asked for; the tape gives 51% over the whole
  history (section 5).
- **Live fills** (Oct 11): `live_fills.py` sets the bot's first 488 real orders against the research,
  and `strategies_backtest.py` replays "The live bot · live fills" and "The live bot · all three · live
  fills" from them (section 7).

Still open:

1. **Kalshi's other markets.** The same rule on hourly, daily and weekly markets:
   [`PLAN_OTHER_MARKETS.md`](PLAN_OTHER_MARKETS.md).
2. Build a fair-value model: estimate each contract's probability from the
   underlying price's distance to the strike and its volatility, and trade only
   where Kalshi's price is off by more than costs.
3. Test maker (resting limit) orders, using the same trade tape as `liquidity.py`.

## Files

Run from this folder. The fetch scripts read Kalshi's public API; no key is
needed. Each takes 30 to 60 minutes. Their output files are not in the repository (see [this folder](#this-folder)).

| Script | What it does |
|---|---|
| `check_series.py` | Which 15-minute series exist |
| `backtest_70pct.py` | First small 70¢ test (2,400 markets) |
| `backtest_large.py` | Fetch → `snapshots_8min.csv` |
| `analyze.py` | Calibration table, 70¢ edge, fee sweep |
| `by_band_fees.py` | Net edge by price band, taker vs maker |
| `compounding.py` | Per-trade vs per-day, Kelly sizing, correlation test |
| `fetch_30d.py` | Fetch → `snapshots_30d.csv` |
| `simulate.py` | $24 bankroll sim, 70¢ favorites |
| `simulate2.py` | 70¢ vs 90¢+, $24 vs $240/$10 sims |
| `check_ab.py` | Significance, halves, fee-multiplier checks |
| `fetch_quotes.py` | Fetch → `quotes_30d.csv` (resumable) |
| `sim_real.py` | Sims filled at the real ask |
| `thin.py` | Thin-market buckets and out-of-sample filter test (Aug 24 to Sep 23: needs volume) |
| `fetch_minutes.py` | Fetch every minute 1-15 of every market → `minutes_30d.csv` (one batch request per window, resumable) |
| `minutes.py` | Profit by entry minute and price bin, fair test of the best minute |
| `sizing.py` | Bet size as a share of bankroll: every day since Dec 10, 2025, 30- and 90-day resampled runs, window caps, fee stress → `sizing.json` |
| `fetch_all15.py` | Every 15-minute series in Kalshi's catalog → `universe.json`; every minute of the ones outside the original 16 → `minutes_new.csv` |
| `fetch_history.py` | Every 15-minute market from Jul 18 up to the last full day → `minutes_ext.csv` (resumable) |
| `fetch_pre.py` | Every crypto market before Jul 18, back to the first on Dec 10, 2025, from Kalshi's historical endpoint → `minutes_pre.csv` (7-11 hours; resumable, and quiet while the live bot orders) |
| `history.py` | Joins the four minute files, one row per market (every backtest reads it), and writes `snapshots_all.csv` |
| `strategies_backtest.py` | Every paper strategy replayed over every window since Dec 10, 2025 with the paper trader's own rules, started on Dec 10, Jul 18 and Aug 24 → `strategies.json`; each run carries its worst drop, worst 15 minutes and, since Oct 12, its worst 24 hours (`worst24hPct`, `worst24h`, `worst24hAt`: what the live bot's 35% halt watches; checked by hand and against a brute force in `tests/test_worst_24h.py`) |
| `risk_rules.py` | Taking profit out and stop rules, on the real history from Dec 10, Jul 18 and Aug 24 and on 400 made-up 90-day histories in two worlds (edge real, edge about zero) |
| `findings.py` | What the live bot's research found, in one run → `findings.json`: halts at the bot's own sizing, every rule for selling a position early, what losing bets' prices did, the warning signs before buying, and how losses cluster, on three parts of the history (Dec 10 to Jul 17, Jul 18 to Aug 23, Aug 24 on) and the paper trader's forward days |
| `by_month.py` | The minute-8 rule, plain and as the live bot trades it, by part of the history and by month since Dec 10: bets, win rate against the all-in cost, profit per $10 bet with a 95% range, the one-bet Kelly fraction and the average spread → `by_month.json` |
| `exit_timing.py` | When to sell a favorite that turned: win rate against the bid it could be sold for at every minute 9-14, the crossing law for a fair price, every sell-under-x rule, and buying more on the dip |
| `stress_signals.py` | Warning signs visible at minute 8 (gap between buy and sell price, recent moves, crypto volatility, the clock, recent losses), by fifths in each of the three parts of the history |
| `key_stats.py` | The replication's key numbers for the bot dashboard's Research tab: calibration at minute 8, the one-bet Kelly fraction per fill scenario, the regime change, stops and selling under 90¢ → `key_stats.json` |
| `all_markets.py` | The minute-8 rule by market group, spreads and mid-price calibration, co-losses, group caps → `all_markets.json` |
| `liquidity.py` | How much of each live-rule order the book could really have filled, from Kalshi's trade tape (from Jul 18, or from an earlier start date given after the file name): `fetch` → a raw tape file (~110 MB, kept out of the repo), `reduce` → `liquidity.json`, which `strategies_backtest.py` reads for "The live bot · real liquidity" |
| `live_fills.py` | The live bot's real orders against the research (section 7): reads its ledger (`bot/state/live-prod.db`, or another named after the script) read-only, and writes how the orders filled, the price gaps, win rates and fees, breakdowns by band, size, market and group, a check of the trade-tape model, the fill table, a market-by-market replay of the backtest against the bot, and the lab's changes on the live bets → `live_fills.json`, which `strategies_backtest.py` reads for the two "live fills" accounts (rerun it afterwards) |
| `fetch_other.py` | Kalshi's hourly, daily and weekly markets: `list` → `other_markets.json`, `candles` → `other_hours.csv` (both too big for git) |
| `other_markets.py` | The favorites rule on those markets, by category, frequency and time before close (`PLAN_OTHER_MARKETS.md`) |
| `price_floor.py` | The live bot's rule with only its lowest price changed (90, 91, 92, 93 or 95¢): profit per $10 bet by price band and period, which orders the trade tape says would have filled and how often they won, and each floor at the bot's own sizing from $500 → `price_floor.json` (about 4 minutes; it reads only minutes 6-8 and favorites at 90¢+, so it needs little memory) |
| `filter_search.py` | Eight richer entry filters against the bot's two warning signs, fixed in `FILTER_SEARCH_PREREG.md` before scoring → `filter_search.json` |
| `threshold_search.py` | Whether the warning signs' three cut-offs (2¢ spread, 10¢ jump, 50¢) are the right ones, fixed in `THRESHOLD_SEARCH_PREREG.md` → `threshold_search.json` |
| `band_weight_test.py` | Sizing bets by price band against flat sizing, weights fitted on the first half and scored on the second → `band_weight_test.json` |
| `live_losses.py` | How the live bot's losses happened and the skip rule they suggested, tested on the backtest (reads the bot's ledger; its outputs are not included) |
| `scan_skipped.py`, `fetch_skipped.py`, `skipped_edge.py` | The 15-minute series the bot skips: which have settled markets (`skipped_scan.json`), their minute history (`minutes_skipped.csv`), and the live rule replayed on them (`skipped_edge.json`, `skipped_edge_findings.md`) |
| `depth_tape.py`, `depth_books.py` | The depth check for the other markets that passed (`other_markets_findings.md`): did $10 really trade at the backtest's price on the trade tape, and a week of recorded order books |
| `venue_books.py` | A week of Gemini Predictions and Polymarket US order books: how deep their 90 to 99¢ favourites are, and whether they win more often than priced → `venue_books_report.json` |
| `lab/` | The Oct 11 strategy lab: edge map, fair value from the spot price, fills and limit prices, maker orders, fast entry timing, and the live fills check (`lab/REPORT.md`) |

## Bet sizing (`sizing.py`)

Flat $10 bets earn about the same dollars every month, so the return shrinks as
the bankroll grows. `sizing.py` replays every day since Jul 18 at different bet
sizes, as a share of the bankroll, and resamples whole days into 400 alternative
runs. The "realistic" case adds the 0.4¢-a-contract gap between live fills and
candle asks.

- **One-bet Kelly** (the size that maximizes long-run growth if each bet stood
  alone) is 6.4% of bankroll per bet at the recorded ask, and **below zero with
  realistic fills** (−1.4%): over the whole history a live-like fill costs more
  than the favorites win, so the growth-maximizing bet is none.
- **In order, every rule goes broke** from Jul 18 at realistic fills, and at the
  recorded ask everything at 3% a bet or more does too; only 1-2% a bet survive.
- **The window cap still helps most:** 3% of bankroll per bet with at most 20%
  across a window has the best median of the percentage rules, but no size turns
  a break-even trade into a winning one.

| Realistic, from $240 | 30 days: median | chance of a 50% drop | 90 days: median | worst 10% of runs | chance of a 50% drop |
|---|---|---|---|---|---|
| Flat $10 | $111 | 82% | $0 | $0 | 95% |
| 1/24 of bankroll | $60 | 98% | $0 | $0 | 100% |
| 3% per bet | $119 | 88% | $0 | $0 | 100% |
| 3% per bet, window ≤ 20% | $132 | 82% | $0 | $0 | 100% |

At the recorded ask the same rule's 30-day median is $409, and with a 2× crypto
fee every rule loses in the median run. Bets under about $5 also lose a noticeable share to the fee's
round-up to the cent. None of this accounts for order-book depth: the live
trader's $10 orders already walk 2-5 price levels in ETH, NEAR and HYPE, so
larger bets will fill worse than modeled.

## Every 15-minute market (`fetch_all15.py`, `all_markets.py`)

Kalshi's catalog lists 30 series as 15-minute. 20 have traded: the original
16, Coin Race (five markets a window on which of BTC, ETH, SOL, XRP and HYPE
gains most, since Aug 20) and EUR/USD, GBP/USD and USD/JPY (since Sep 23,
weekdays only). The S&P 500, Nasdaq 100, four Treasury yields and three more
coins are listed but haven't launched. Every series lists a fee multiplier of
1, crypto included.

| Group | Bets at minute 8 | Per $10 bet, live-like fills | Average spread | 90%+ favorites at the mid: priced → won |
|---|---|---|---|---|
| Crypto (74 days) | 20,642 | −1.3¢ | 2.0¢ | 94.5% → 95.7% |
| Metals (58 days) | 3,016 | +0.1¢ | 2.6¢ | 94.2% → 96.1% |
| Energy (59 days) | 1,667 | −6.5¢ | 2.7¢ | 94.1% → 95.9% |
| Coin Race (39 days) | 9,469 | **−29.8¢** | **10.3¢** | 95.2% → 96.5% |
| FX (6 days) | 357 | **−62.9¢** | **9.6¢** | 94.7% → 92.9% |

At the mid price, favorites win more often than priced in every group but FX,
which has only 6 days. Coin Race and FX spreads are 4-5× wider, though, so
buying at the ask gives away more than the edge. Buying the underdog in Coin
Race loses too. Over the whole history no group clears its costs with live-like
fills: metals breaks even, crypto and energy lose.

Losses cluster within groups: when one crypto favorite loses, another in the
same window loses 33% of the time (4.9% normally, 6.6×); metals 7.8×, energy
8.5×. Crypto and metals barely move together (1.1×). Over the whole history,
capping crypto at one bet a window (edge groups only) lost −$214 instead of
−$595 with no cap: −2.1¢ a bet against −2.3¢, and a worst window of −$40 instead
of −$110. At $240 and $10 a bet both went broke by Jul 31.

## The six paper strategies, backtested (`strategies_backtest.py`)

Each paper-trading account replayed over every window since Jul 18 from $240, with the paper
trader's strategies, sizing, group limits and broke rule (`STRATEGIES` in the script), with live-like fills
(0.4¢ a contract worse than the recorded ask). These tables are from the Sep 29 rebuild. Since then
the "Every market" account and the 12-hour pause replay have been taken out of
`strategies_backtest.py`, and the live bot's own rule ("The live bot"), sell-under-90¢ accounts and
one-change variants have been added, with copies of the live bot filled by the trade tape ("real
liquidity", section 5) and by its own real orders ("live fills", section 7); the dashboard's Research tab
shows the current replay.

| Strategy | Started Jul 18 | Started Aug 24 | Worst drop from Aug 24 |
|---|---|---|---|
| $10 a bet | broke Jul 30 | $762 (+3.9¢ a bet) | 35% |
| 1/24 of bankroll | broke Aug 1 | $633 (+1.3¢) | 59% |
| 3% a bet, 20% a window | broke Aug 1 | $734 (+2.8¢) | 37% |
| 1 crypto bet a window | broke Jul 31 | $497 (+4.1¢) | 29% |
| Every market | broke Jul 30 | broke Aug 26 | 100% |
| Minute 5 · $10 a bet | broke Jul 28 | $541 (+6.6¢) | 48% |

The 5 weeks before Aug 24 were never used to choose a rule, so they're the fair test, and the
rules fail it: every account started on Jul 18 went broke by Aug 1 (at the recorded ask, 3% a bet
lasted to Aug 17). Most of the damage was one week (Jul 27 to Aug 2), when 90¢+ favorites won 92.8%
of the time: −25.8¢ a bet, −$457 at $10 a bet. 7 of the 12 weeks were profitable at $10 a bet; the
other losing weeks were Jul 20-26, Aug 10-16, Sep 14-20 and Sep 28-29.

**With a 12-hour pause.** The same replays, but whenever a window closes with the bankroll 20% or more
below its highest point in the last 24 hours, no bets for 12 hours; then trading carries on and the
24 hours count from the restart. Live-like fills:

| Strategy | From Jul 18, paused (without) | From Aug 24, paused (without) | Pauses from Aug 24 |
|---|---|---|---|
| $10 a bet | broke Aug 4 (Jul 30) | broke Sep 17 ($762) | 24 |
| 1/24 of bankroll | broke Aug 4 (Aug 1) | $93 ($633) | 20 |
| 3% a bet, 20% a window | broke Aug 4 (Aug 1) | $621 ($734) | 8 |
| 3% a bet, 20% a window · $100 | broke Aug 1 (Jul 31) | $111 ($150) | 5 |
| 1 crypto bet a window | broke Aug 5 (Jul 31) | $482 ($497) | 3 |
| Every market | broke Aug 4 (Jul 30) | broke Sep 1 (Aug 26) | 14 |
| Minute 5 · $10 a bet | broke Aug 1 (Jul 28) | $556 ($541) | 4 |

From Jul 18 the pause only puts off going broke, by 1-5 days. From Aug 24 it lowers the end of every
account that survives without it except minute 5, and sends $10 a bet broke. It skips the rebounds: the $10 account's second pause came at $147, when without pauses
it was already back at $247. Losses here don't come in runs (see below), so the hours after a bad day
are no worse than any others, and sitting them out gives up their profit. At a flat $10 a bet it is
worst of all: as the bankroll shrinks, 20% becomes two or three losing bets, so it pauses more and more.

## Stops, halts and warning signs (`risk_rules.py`, `stress_signals.py`)

**Stop-losses.** A stop can only add value when losses come in runs; on random
ups and downs it lowers returns ([Kaminski & Lo][kl]). Losses here don't run:
the day after a day worse than −$30 averaged +0.0¢ a $10 bet, against −1.8¢
after any other day, and the 4 hours after a window with 3+ losses averaged
+6.0¢. `risk_rules.py` replays each rule on the real history (Jul 18 to Sep 29)
and on 400 made-up 90-day histories stitched from random 5-day stretches, in two
worlds: the whole history (edge about zero, −0.4¢ a bet) and Aug 24 on (about
+4¢). Median take-home from $240:

| Rule | Edge real | Edge about zero |
|---|---|---|
| $10 a bet, no stop | $1,649 | $8 |
| Stop for good at half the money put in (−$120) | $1,641 | $115 |
| Stop for good 50% below the peak | $1,603 | $158 |
| Stop for good 30% below the peak | $228 | $192 |
| Pause for the rest of the day after −$40 | $625 | $7 |
| Pause while the last 24 h is −$60 or worse | $1,036 | $10 |
| 3% a bet, 20% a window, no stop | $7,094 | $51 |

A stop measured from the money put in is almost free when the edge is real and
keeps about half when it isn't. Stops measured from the peak, and pauses, fire
on normal swings: the live $10 account has already fallen 38% from a peak and
recovered, and at 3% a bet the worst 24 hours since Aug 24 were −32% (Sep 28-29). That is
also why prop-firm limits (4-6% a day, 6-12% in all; [The5ers][p5]) don't fit
this strategy.

**Taking profit out.** At a flat $10 a bet, money beyond what the account needs
earns nothing, so a weekly sweep changes nothing when the edge is real ($1,647
vs $1,649 sweeping everything over $240) and locks in early gains when it isn't
($122 vs $8). With 3% sizing, sweeping slows compounding: half the new profit
weekly ends at $2,681, every 4 weeks $3,669, never $7,094.

**Warning signs at minute 8.** `stress_signals.py` measures what the trader can
see before betting, splits the 24,158 historical bets into fifths by each, and
counts a sign only if it holds both before Aug 24 and after. One does: a wide
gap between buy and sell price. Favorites whose ask was 2¢ or more above the bid
made −29.7¢ a $10 bet before Aug 24 (95% range −41 to −18) and −12.1¢ after
(−25 to +0.4). They are about one bet in five. Without them, Jul 18 to Aug 23
goes from −$623 to +$211 at $10 a bet, and Aug 24 to Sep 29 from +$522 to +$760
(`findings.py`, which also finds late or jumpy favorites losing in both halves).
The live bot has skipped both signs since Oct 9 (`bot/README.md`, "What it buys").

How far crypto prices moved in the first 8 minutes, the hour of day, the 8:30
and 10:00 ET data releases, weekends and recent losses showed nothing
consistent, and the worst days had ordinary price movement. The 9:30 ET stock
open window lost money in both halves, but on only 260 bets. The exception is
scheduled news: the worst window in the history was the Sep 16 Fed decision
(2:30 pm ET, 11 of 14 bets lost, −$110), though the Jul 29 decision went fine.
Crypto can fall 14% in hours and altcoins 40% or more ([Oct 10, 2025][oct10]),
so the halts below react to results and to Kalshi's own health rather than try
to predict events.

**Sources**

- Kaminski & Lo, [When Do Stop-Loss Rules Stop Losses?][kl] (Journal of Financial Markets, 2014)
- Grossman & Zhou, [Optimal Investment Strategies for Controlling Drawdowns][gz] (Mathematical Finance, 1993): the floor-that-rises-with-the-peak rule tested in `risk_rules.py`
- FIA, [Best Practices for Automated Trading Risk Controls and System Safeguards][fia]: kill switches and profit-and-loss limits
- SEC, [Knight Capital charged under the Market Access Rule][knight]: $440M lost in 45 minutes without a working kill switch
- Investor.gov, [Stock market circuit breakers][cb]: tiered 7/13/20% halts
- The5ers, [Prop firm drawdown rules][p5]
- Kalshi, [Maintenance and pauses][kd] (Thursdays 3-5 am ET) and `GET /exchange/status`
- GV Wire, [Kalshi trading temporarily halted][gv] (Apr 2026, unscheduled)
- CF Benchmarks, [Kalshi's crypto contracts settle on CF Benchmarks indices][cfb]
- Bitcoin.com, [The Oct 10, 2025 liquidation cascade][oct10]
- Federal Reserve, [FOMC meeting calendar][fomc]

[kl]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338
[gz]: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9965.1993.tb00044.x
[fia]: https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf
[knight]: https://www.sec.gov/newsroom/press-releases/2013-222
[cb]: https://www.investor.gov/introduction-investing/investing-basics/glossary/stock-market-circuit-breakers
[p5]: https://the5ers.com/prop-firm-drawdown-rules-explained-daily-max-and-trailing-limits-in-2026/
[kd]: https://docs.kalshi.com/getting_started/maintenance_and_pauses
[gv]: https://gvwire.com/2026/04/15/kalshi-trading-temporarily-halted-website-shows/
[cfb]: https://www.cfbenchmarks.com/blog/kalshi-leads-surging-crypto-event-contract-market-powered-by-cf-benchmarks
[oct10]: https://news.bitcoin.com/learning-insights/crypto-liquidation-cascades-explained/
[fomc]: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

## When to sell a favorite that turned (`exit_timing.py`)

Theory says to hold. If the price is a fair win probability (a martingale), the
optional stopping theorem gives every selling rule the same expected payout as
holding, so a sale only pays the spread and the fee; stop-losses add value only
when prices trend ([Kaminski & Lo][kl]), and the best time to sell an asset
with a good enough drift is the end of the horizon ([Shiryaev, Xu & Zhou][sxz]).
Selling would pay only where a collapsed favorite trades above its real chance,
as losing teams did in the last 15 minutes of games on InTrade ([Page][yogi]).

Here it never does. Across 24,158 minute-8 favorites (Jul 18 to Sep 29), at every
minute from 9 to 14 and every 5-10¢ band of the bid, positions won at least as
often as the bid less the fee would pay: none of the 70-odd cells says sell, and
most say hold with room to spare (bid 30-40¢ at minute 10: won 65%). Collapsed
favorites are underpriced at the bid, the overreaction to surprising events seen
in in-play betting ([Choi & Hui][ch]). Every rule of the form "sell the first
time the bid is at or under x from minute m" lost against holding, in both
halves of the history; the least bad, under 5¢ from minute 14, still lost $217
on $10 bets. Buying another $10 at the ask on the dip didn't reliably pay either:
the spread on a collapsed favorite is wide, and the result flips between the two
halves (−102¢ to +30¢ a bet before Aug 24, +44¢ to +424¢ after) with every 95%
range spanning zero. The real chance sits between the bid and the ask: hold.

[sxz]: https://www.tandfonline.com/doi/abs/10.1080/14697680802563732
[yogi]: https://www.tandfonline.com/doi/full/10.1080/00036846.2010.498578
[ch]: https://www.sciencedirect.com/science/article/abs/pii/S0167268114000481

## Paper trading (retired)

A paper trader (`paper/paper_trader.py`) ran the strategy live without placing orders from Sep 24 until
Oct 9, 2026, when paper trading stopped and it was removed with its database. It is not part of this
repository. Its accounts' rules live on in `strategies_backtest.py` (`STRATEGIES`), which
`risk_rules.py` and `stress_signals.py` read; `findings.py` still reports forward days when a `paper/paper.db`
is present, and none now.
