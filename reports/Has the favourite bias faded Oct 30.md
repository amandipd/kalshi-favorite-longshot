# Has the favourite bias faded? Checked on all of Kalshi's 15-minute markets (Oct 30)

**Short answer: no, it hasn't gone away. Over the last three weeks (Oct 9 to 29), the bot's rule applied to every market made about what it made in the past. But all of that came in the first 11 days. Since Oct 20 the whole market has been flat, not just the bot. And the live bot did almost exactly what the rule did on Kalshi's own prices, so the bot is working as designed. The bad stretch is the market's, not the bot's.**

## The question

Since Oct 20 the live bot has lost about as often as prices predicted. Two possible reasons:

- **The bot's own problem:** how it buys (timing, prices paid, the +1 cent limit).
- **The market's problem:** the favourite bias (cheap unlikely bets overpriced, heavy favourites underpriced) has weakened, so there is less edge (profit source) for anyone.

Looking at every market, not just the bot's bets, separates the two.

## How it was tested

- **The pass bar was written first** (`research/bias_recent/PREREG.md`, 30 Oct 2026, 4:58 PM EDT, before any data was downloaded). Its fingerprint (sha256): `828d1676e13dd97a22275385ee7eb285381b4431972eda410c153c1792c673fa`. Unchanged after.
- **Recent data:** every settled market in the 16 series the bot trades, windows opening Oct 9 to Oct 29 (UTC). 27,609 markets, minute by minute, from Kalshi's own price history, using the research's own download code.
- **Past data:** the same kind of record, Dec 2025 to Oct 8 (`research/kalshi_15min/lab/markets.npz`).
- **The bets scored:** the bot's rule. Favourites (the likely side) priced 92 to 99.9 cents at minute 8, skipping the two warning signs (a wide gap between buy and sell price, or a big late price move) and the Fed announcement. $10 a bet at the recorded price, fee included.
- **How it would be read (fixed in advance):** "faded" if the recent result is clearly below the long-run past (+0.80 cents for every dollar bet). "Still there" if it is clearly above zero. "Clearly" means the range the true number is probably in (95% range) sits wholly on one side.

## The pre-set result: still there

| Data | Bets | Cents of profit for every dollar bet (range it's probably in) | Losses (prices predicted) | Losses as a share of predicted (under 1 = edge) |
|---|---|---|---|---|
| Past, whole history | 29,667 | +0.79 (+0.53 to +1.05) | 891 (1,213.5) | 0.73 |
| Past, Aug 24 to Oct 8 | 10,585 | +1.15 (+0.73 to +1.57) | 298 (450.3) | 0.66 |
| **Recent, Oct 9 to 29** | **5,319** | **+0.81 (+0.12 to +1.50)** | **150 (208.1)** | **0.72** |

- The whole range is above zero, so the reading is **"still there"**.
- The recent result matches the long-run past almost exactly. Favourites lost 72% as often as their prices said.

## But it all came before Oct 20

This split was set in advance as "reported, not part of the reading".

- **Oct 9 to 19:** +1.65 cents for every dollar bet (range +0.99 to +2.31). Favourites lost 57 where prices predicted 108.8. A very strong stretch.
- **Oct 20 to 29:** −0.06 cents for every dollar bet (range −1.28 to +1.16). Favourites lost 93 where prices predicted 99.3. Flat.
- **Plain favourites, with no warning signs skipped, show the same:** +1.59 cents before Oct 20, +0.24 cents after.
- **The market can't know about the bot's changes.** The live +1 cent limit started on Oct 20, but the whole market went flat at the same time. So the +1 cent limit is not why the bot went flat.
- **Flat spells like this have happened before.** Of all 10-day stretches since Jul 18, about 1 in 9 (11%) were this flat or worse. The typical 10 days made about +1.06 cents for every dollar bet.

## The live bot did what the rule did

The same rule on Kalshi's recorded prices, against the live bot's own ledger, over the same windows (Oct 16, 1:15 AM ET to Oct 29, 8 PM ET):

- **The rule on Kalshi's prices:** +0.26 cents for every dollar bet. Lost 114 where prices predicted 133.4.
- **The live bot:** +0.29 cents for every dollar bet. Lost 93 where prices predicted 112.7.
- **2,983 markets both bet on.** They had the same result every time. The live bot paid only 0.07 cents more per contract on average. So the +1 cent limit and the bot's timing cost almost nothing.
- **519 markets the rule took and the bot didn't** (mostly the 7-hour listing outage on Oct 24, the Thursday maintenance halt, and the bot's own real-time warning signs). Those lost slightly (−0.67 cents for every dollar bet), so missing them didn't hurt.
- **Bottom line: the bot is buying what it should, at about the right price.** Its results follow the market's.

## Crypto-wide flips really are more common lately

A crypto-wide flip is a window where several crypto favourites lose at once because the coins move together.

- **Windows with 5 or more crypto losses, across the whole market:**
  - Recent: 4 in 21 days (Oct 21 4:30 AM, Oct 22 9:45 AM, Oct 22 9:30 PM, Oct 29 5:30 PM ET). About 1.3 a week.
  - Past, Aug 24 to Oct 8: 2 in 46 days. About 0.3 a week.
  - At the past rate, 4 or more in 3 weeks happens about 1 time in 50 to 70.
  - The live bot skipped the Oct 22 9:45 AM one.
- **Windows with 3 or more crypto losses:** about 2.3 a week, recent and past alike. So it is only the very big flips that are up.
- **Part of the reason:** more coins are favourites at once. The rule now averages 3.5 crypto bets per window, against 3.1 in the past.

## Yes side and No side, market-wide

- Yes-side favourites: +1.55 cents for every dollar bet (lost 57 where prices predicted 105.0).
- No-side favourites: +0.07 cents (lost 93 where prices predicted 103.1).
- The No side is weaker across the whole market too, not just for the bot. The past data found the same tilt, smaller (about 0.4 cents).

## What it means

- **The edge isn't gone.** Three weeks of the whole market look like the long-run past.
- **The last 10 days are a flat spell for everyone.** It is the kind that has happened about 1 time in 9. It isn't the bot, and it isn't the +1 cent limit.
- **The real change is the big crypto flips.** They are coming about four times as often as in the past. If that lasts, they eat a big share of the edge. That is the thing to watch, and the per-window limit is the lever to test after Nov 27.
- **Nothing to change before Nov 27.**

## Files

- `research/bias_recent/PREREG.md`: the pass bar, written before any data.
- `research/bias_recent/fetch_recent.py`: downloads the recent markets into `recent_minutes.csv` (not kept in git; rerun to rebuild).
- `research/bias_recent/score.py`: scores everything once and writes `score.json`. The live comparison reads a read-only pull of the live ledger.
- Analysis only. Nothing in `bot/`, the live server, or `research/kalshi_15min` was changed.
