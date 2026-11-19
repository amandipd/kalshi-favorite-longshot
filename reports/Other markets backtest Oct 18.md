# Other markets for the favourite strategy: overnight backtest

*Oct 18, 2026. Five candidate markets, each backtested with the same rules, mostly on fresh data the original choices never saw. Kalshi data came from public API reads overnight (at most about 1 a second, paused during the live bot's minute-8 orders). Nothing in the live bot was touched.*

## The answer

| # | Market | Verdict | Why |
|---|---|---|---|
| 1 | **Daily gas prices** (Kalshi) | **Passes again: the best add** | Fresh October data: 4 losses vs 22 implied (1-hour checkpoint). +0.9 to +1.0¢ per $1, with ranges above zero. Deep books. About $4/day at $10 bets, $10–15/day at $25 |
| 2 | **Polymarket US crypto** | **BTC yes (for extra size); ETH small; SOL/XRP not yet** | Same results as Kalshi. Favourites cost 0.1–0.4¢ more, which leaves about +0.6 to +0.9¢ per $1. BTC has thousands of dollars on offer at the favourite's price; the altcoins have $100–550 |
| 3 | **Hourly temperature** (Kalshi) | **Fails** | Fresh October data: losses matched the prices (36 vs 33 implied at the 30-minute checkpoint). Slightly negative, thin books |
| 4 | **15-minute FX** (Kalshi) | **Not yet** | About +1¢ per $1 but the range includes zero. Fills look 3–8× thinner than crypto. About 27 bets a day |
| 5 | **Late-game sports** (Kalshi) | **Fails** | 3,044 fresh bets: 241 losses vs 222 implied, −1.1¢ per $1. Sports favourites win slightly *less* often than their price says |

---

## 1. Daily gas prices: passes a second fresh test

**What was tested.** The frozen pass-test rule, unchanged since it was chosen on Jul–Aug data. At 2 hours or 1 hour before the 11:59 PM ET close, buy the favourite of each daily AAA gas-price market if it costs 90–99.9¢ and the spread is 3¢ or less. Pay the ask + 0.4¢, then hold. The rule had already passed on September. This run uses **Oct 1–17**, which no step of the process had seen. Re-running the code on September reproduced the original pass test exactly, so it's the same rule.

| Checkpoint | Bets | Lost vs implied | ¢ per $1 at ask + 0.4¢ (95% range) | ¢ per $1 at the ask | Bets a day |
|---|---|---|---|---|---|
| 2 h before close | 1,375 | **7 vs 26.3** | **+0.88** (+0.23 to +1.53) | +1.28 | 81 |
| 1 h before close | 1,148 | **4 vs 21.8** | **+1.03** (+0.36 to +1.70) | +1.43 | 68 |
| September (for comparison) | | | +0.68 / +1.25 | | |

The ranges are clustered by day, because one day's gas bets mostly move together. Both lower bounds stay above zero.

**Real order books** (Oct 13–18): a median **$1,580–1,780** was on offer at the favourite's price, and **98–99%** of $10, $25 and $50 orders would have filled in full.

**Checks:**
- 28 sampled bets matched Kalshi's official results, 0 mismatches.
- The two checkpoints share most of their markets, so run **one** of them, not both. The 1-hour checkpoint looks slightly better.

**The catches:**
1. **Only about 60% of the bets the price data shows were really buyable** a few seconds later. In the rest, one side of the real order book was empty. The dollar estimate below already allows for this.
2. **Only 17 independent days.** All of a day's gas bets ride on the same national price moves.
3. **Every loss so far came from gas rising past a line.** One sharp national jump, from a hurricane or a refinery outage, could hit many bets on the same day. That hasn't happened in the 47 days tested.
4. **Small money.** About **+$4 a day at $10 bets**, and **+$10–15 a day at $25**. Daily P&L at $10 averaged +$7, the worst day was −$16, and 2–3 of 17 days were red.
5. **The 26 newer state gas markets** (added after the pass test) show no edge yet: 358 bets, +0.16¢ per $1. Leave them out until they pass on their own.

## 2. Polymarket US crypto: works for BTC, too thin for most altcoins

**Why price is all that matters here.** Polymarket US settles on the same index as Kalshi. That held for 206 of 206 BTC windows and 165 of 165 ETH, SOL and XRP windows checked. So a Polymarket favourite wins exactly when the Kalshi one does. The only differences are **price, fees and depth**.

**What was tested.** For every window where the live bot bought a 92¢+ favourite on Kalshi at minute 8, Polymarket's price for the same side at the same moment. That's 442 BTC windows (Sep 23 – Oct 18) and 53–63 each for ETH, SOL and XRP (from their launch on Oct 15).

| Coin | Pairs | Polymarket minus Kalshi price (95% range) | Kalshi edge, ¢ per $1 | **Polymarket edge, ¢ per $1** (95% range) | Typical $ on offer at the favourite's price |
|---|---|---|---|---|---|
| BTC | 442 | +0.10¢ (+0.04 to +0.15); **+0.36¢ since Oct 15** | +0.93 | **+0.84** (+0.29 to +1.38); +0.58 at the recent gap | **$3,100–5,600** |
| ETH | 63 | +0.26¢ (+0.13 to +0.38) | +0.98 | +0.73 (+0.20 to +1.27) | $540 |
| SOL | 53 | +0.12¢ (−0.06 to +0.31) | +1.07 | +0.95 (+0.39 to +1.52) | $110 (under $100 half the time) |
| XRP | 55 | +0.06¢ (−0.14 to +0.27) | +0.98 | +0.92 (+0.32 to +1.53) | $230 (under $100 a third of the time) |

**The gap is mostly price steps.** Polymarket only quotes whole cents, while Kalshi quotes 0.1¢ steps above 90¢. In 62% of BTC pairs, Polymarket's price was just Kalshi's rounded up to the next cent. Fees are nearly identical.

**The BTC gap widened lately,** from +0.03¢ before Oct 11 to +0.36¢ after Oct 15, when one of Polymarket's maker rebates ended. More rebates change on **Oct 19**, which could thin the books further. If the gap grows past about 0.9¢, the edge is gone.

**Verdict:**
- **BTC: yes, as extra capacity.** Up to about $1–2k per window should fill at the favourite's price. Use a limit at the ask and never pay up. 1¢ more costs about 1¢ per $1, which is Polymarket's whole edge.
- **ETH:** at most about $250 per window.
- **SOL and XRP:** too thin for now.

This only matters once Kalshi can't fill bigger orders, which isn't the case yet. **Check whether Polymarket US allows trading from the bot's server location first.**

**Check:** on the dates both measurements cover (Oct 13–16), this gap (+0.27¢, 39 pairs) matches my earlier measurement from the venue recorder (+0.32¢, 34 pairs).

## 3. Hourly temperature: fails

Same frozen rule, checked 30 and 10 minutes before each hour's close, on Oct 1–17:

| Checkpoint | Bets | Lost vs implied | ¢ per $1 at ask + 0.4¢ (95% range) | September |
|---|---|---|---|---|
| 30 min | 1,204 | 36 vs 33.3 | −0.88 (−1.82 to +0.07) | +0.78 |
| 10 min | 818 | 22 vs 21.5 | −0.69 (−1.90 to +0.52) | +0.73 |

Losses matched the prices almost exactly, so there's no favourite advantage. September's small edge flipped negative. The books are thin too: a median **$47–60** at the favourite's price, and only about half of $50 orders fill. The expected result is **−$3 to −$7 a day** at $10 bets. **Drop it.**

## 4. Kalshi 15-minute FX: not yet

The bot's own rule (minute 8, 92–99.9¢, both warning-sign skips, blackouts), on Kalshi's currency up/down markets:

| Slice | Bets | Lost vs implied | ¢ per $1 (95% range) |
|---|---|---|---|
| History, Sep 23 – Oct 11 (EUR, GBP, JPY) | 212 | 4 vs 6.9 | +1.24 (−0.69 to +3.17) |
| Fresh, Oct 12–16 (all 5 pairs) | 133 | 3 vs 4.7 | +1.07 (−1.46 to +3.60) |
| **All FX** | **354** | **8 vs 12.0** | **+0.97 (−0.63 to +2.56)** |
| Crypto, same dates (for comparison) | 3,398 | 92 vs 139 | +1.19 (+0.43 to +1.94) |

**Why it isn't ready:**
1. **No built-in favourite advantage.** Across *all* FX favourites in the price band, before the spread skip, losses matched the prices exactly: 47 vs 47.1. Crypto over the same dates: 100 vs 154. The small FX profit comes only from the spread skip removing bad bets, and without that skip FX loses −2.4 to −2.9¢ per $1.
2. **Thin fills.** In the minute after entry, the trade tape shows a median of **2 contracts** traded at or under the entry price for FX, against **85** for crypto. 37.5% of FX bets saw no such trades at all.
3. **Small volume:** about 27 bets a day across 5 pairs.

**Why it was left out originally:** spreads were about 10¢ in its first week and it lost money. Spreads have since narrowed to about 2¢, and the bot's spread skip now removes the wide ones, so that old reason no longer applies. The edge just isn't proven.

Telling +1¢ per $1 apart from zero needs roughly 1,400 bets, about 7 weeks. **Rerun in 4–6 weeks.**

The stock-index and Treasury-rate 15-minute series have never listed a market, so there's nothing to test there.

## 5. Late-game sports favourites: fails, slightly the wrong way

**What was tested.** Kalshi game-winner markets in 7 sports, about 6,970 games from June 1 to Oct 17:

| Sport | Series |
|---|---|
| College football | KXNCAAFGAME |
| MLB | KXMLBGAME |
| NFL | KXNFLGAME |
| NHL | KXNHLGAME |
| WNBA | KXWNBAGAME |
| Tennis | KXATPMATCH, KXWTAMATCH |
| Soccer | KXEPLGAME, KXLALIGAGAME, KXUCLGAME, KXMLSGAME, KXWCGAME |

The rule only uses information available at the time: during the game, the **first minute** the favourite's price is in the band (90, 92, 95 or 97¢ up to 99¢), with a tight spread and real trading. Buy at that minute's price and hold. Each sport's settings were chosen on the earlier half of dates, then scored once on the later half.

| Sport | Out-of-sample bets | Lost vs implied | ¢ per $1 (95% range) |
|---|---|---|---|
| College football | 278 | 21 vs 17.5 | −1.8 (−6.1 to +2.5) |
| MLB | 680 | 50 vs 47.1 | −0.8 (−2.6 to +1.1) |
| NFL | 59 | 9.5 vs 5.0 | −8.9 (−15.3 to −2.4) |
| NHL | 170 | 11 vs 13.6 | +1.0 (−3.3 to +5.3) |
| WNBA | 145 | 13 vs 12.1 | −1.3 (−7.2 to +4.6) |
| Soccer | 354 | 30.2 vs 27.5 | −1.4 (−4.2 to +1.4) |
| Tennis | 1,358 | 106 vs 99.5 | −1.1 (−2.7 to +0.6) |
| **All sports** | **3,044** | **241 vs 222** | **−1.1 (−2.2 to −0.1)** |

**Sports favourites win slightly *less* often than their price says,** the reverse of the bias the bot uses. A rule like the bot's (92¢ and up, 2¢ spread) over all days: 6,385 bets, 446 losses vs 421 implied, **−0.9¢ per $1**. All 24 variants tested lose money, and they lose even before fees. That fits the calibration study, which found the bias weakest in sports.

**Depth is not the problem:** in most sports, $50 traded at the entry price within a few minutes. The problem is that the edge isn't there.

**Only NHL stayed positive in both halves.** But it's small (235 bets, 11 losses vs 14.5 implied), and proving a 1¢ edge would take about two seasons. **Drop sports.**

**Checks:**
- 13 sampled bets matched Kalshi's official results.
- No entry came after a market closed.
- Any timing error here would make sports look *better*, so the negative result stands.

---

## What I'd do next

1. **Gas is the one real new edge. Plan to add it after Nov 27.**
   - Use the **1-hour checkpoint only**, and only the original gas markets.
   - Treat each day's gas bets as **one bet** for sizing, because they move together. Cap the day's total stake the way the bot caps a window.
   - Before then, let the depth recorder finish (Oct 20) to measure how often the favourite is really buyable. Then build the gas path in the bot, tests first.
   - Expect about **$4/day at $10 bets, $10–15/day at $25**.
2. **Polymarket US BTC is extra room for later,** not a new edge. It's worth building only once Kalshi's books stop filling bigger BTC orders. Check access from the bot's server location first.
3. **FX: rerun in 4–6 weeks.** It needs about 1,400 bets to tell its +1¢ apart from zero.
4. **Drop temperature and sports.** Both failed on fresh data.

None of this changes the live bot before the 6-week test ends on Nov 27.

## How this was checked

- **Each rule was fixed before scoring.** The gas and temperature rules were frozen in the September pass test. FX used the live bot's exact rule. Nothing was tuned on the data it was scored on.
- **Ranges are 95%, clustered** (by day, hour or window) so correlated bets aren't counted as independent.
- **Spot checks:**
  - 28 gas bets and 13 sports bets matched Kalshi's official results.
  - The FX run reproduced exactly when rerun, and the same code reproduced the known crypto backtest (+0.8¢ per $1).
  - Polymarket's BTC price gap matched my earlier independent measurement.
- **Scripts and data were a one-off** (`other5/`), not in the repo.
