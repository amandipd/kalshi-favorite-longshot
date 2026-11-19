# Crypto-wide flips and No vs Yes, checked on past data (Oct 28)

**Short answer:**

- **Crypto-wide flips are normal.** In the past data, a window where 3 or more crypto bets lose together came about once every 3 days. One with 5 or more came about once every 3 weeks. Live had two 5-plus windows in under 2 weeks. That is unlucky timing (roughly 1 two-week stretch in 4 to 10), not a new risk. The backtests already include these.
- **The No side really is a little weaker, but only a little.** Past No-side favourites made about 0.4 cents less for every dollar bet than Yes-side ones. Live, the gap is about 6 times bigger. A gap that big showed up in about 1 in 5 past two-week stretches. So the live gap is mostly luck on top of a small, real tilt.
- **Neither is a reason to change the bot before Nov 27.**

One more thing came out of this, about the Nov 27 line. See "Context: what the past data says the edge is" at the end.

## What was done

- **Data:** the research's own record of every 15-minute crypto, metals and energy market from Dec 10, 2025 to Oct 8, 2026 (`research/kalshi_15min/lab/markets.npz`, about 204,000 markets). Nothing from the live test is in it, so it is a fair comparison.
- **The bot's rule, rebuilt:** favourites (the likely side) priced 92 to 99.9 cents at minute 8, both warning signs (a wide gap between buy and sell price, or a big late price move), and the Fed-announcement blackouts. That gives 29,667 past bets from Dec 20 on.
- **Fills:** $10 bets at 0.4 cents worse than the recorded price. That is the research's usual "live-like fills" setting (`lab/common.py`).
- **"Prices predicted"** means: for each bet, 1 minus the price paid, added up. A 95-cent price means a 5% chance of losing.
- **"Ratio"** is losses divided by what prices predicted. Under 1 means the bot lost less often than the market expected. That gap is the edge (the bot's profit source).
- **What "Yes" and "No" mean here.** A crypto market's Yes side wins if the coin ends the 15 minutes at or above where it started. So a Yes favourite at minute 8 means the coin is up so far. A No favourite means it is down so far. A No-side loss means the coin was down at minute 8 and bounced back by the close.

## 1. Crypto-wide flips

A "flip" here is a window where several of the bot's crypto bets lose at once. Crypto coins move together, so one sharp market move can flip several favourites in the same window.

**How often, in the past data:**

| Period | Crypto bets per window (average) | 3 or more losses in one window | 5 or more losses in one window |
|---|---|---|---|
| Whole history (293 days) | 2.5 | 49 times, about every 6 days | 6 times, about every 49 days |
| Since Jul 18 (83 days) | 2.8 | 25 times, about every 3.3 days | 4 times, about every 21 days |
| Since Aug 24 (46 days) | 3.1 | 15 times, about every 3.1 days | 2 times, about every 23 days |
| **Live test (12.7 days)** | 3.4 | 3 times | 2 times |

- **They got more common as the bot bet more coins per window.** NEAR and ZEC were added Jun 30. More bets per window means more ways for one move to hit several at once. Live, the bot averages 3.4 crypto bets per window, a little more than the recent past.
- **3-plus windows: live is normal.** At the recent past rate, about 4 were expected in 12.7 days. Live had 3. Since Jul 18, 86% of 12.7-day stretches had 3 or more.
- **5-plus windows: live is unlucky, not strange.** At the recent past rate, about 0.6 were expected in 12.7 days. Live had 2. Since Jul 18, 29% of 12.7-day stretches had 2 or more. Using the Aug 24 onward rate alone, it is about 1 in 10.
- **They hold about the same share of losses.** In the past, windows with 3 or more crypto losses held 22% of all crypto losses (since Jul 18). Live: 25%.
- **They hit both sides about equally.** Past 3-plus windows: 28 all-No, 21 all-Yes. Past 5-plus windows: 3 all-No, 3 all-Yes. Live: two No-side (Oct 21, Oct 22) and one Yes-side (Oct 28, 2:15 PM).
- **Losses bunch up far more than chance would.** If each loss were independent, the past data would have had less than 1 window with 3 or more crypto losses in 10 months. It had 49. That is the same bunching the Oct 21 loss-clustering study found.

**What it means:** the two big October windows are the kind of event the strategy always had. The past edge already pays for them. Live just got two close together.

## 2. No side vs Yes side

**Whole past history, with fills 0.4 cents worse than recorded:**

| Bets | Lost (prices predicted) | Ratio (under 1 = edge) | Cents of profit for every dollar bet | How far from luck (about 2 is the usual bar) |
|---|---|---|---|---|
| Yes side, 15,190 bets | 422 (555.8) | 0.76 | +0.61 | 3.5 |
| No side, 14,477 bets | 469 (539.3) | 0.87 | +0.19 | 1.0 |

**By market type (cents of profit for every dollar bet):**

- Crypto: Yes +0.47, No +0.14.
- Metals: Yes +1.85, No +0.58.
- Energy: Yes +1.59, No +1.01.

**By period (cents of profit for every dollar bet):**

- Dec 10 to Jul 17: Yes +0.56, No −0.14.
- Jul 18 to Aug 23: Yes +0.10, No +0.39. The one period where No did better.
- Aug 24 to Sep 23: Yes +0.95, No +0.57.
- Sep 24 to Oct 8: Yes +0.91, No +0.54.
- Crypto by month: Yes did better in 7 of 10 months (December 2025 had too few bets to count).

**How sure:**

- Yes beat No by about 0.41 cents for every dollar bet over the whole history.
- The range the true gap is probably in (95% range, from resampling whole days) runs from −0.11 to +0.92 cents. In 94% of resamples, Yes came out ahead.
- So there is probably a real, small tilt toward the No side being weaker. It is not certain. Why it happens is not known. One possible reason: coins that dip early may bounce back a little more often than coins that rise early fall back. That is a guess, not tested here.

**Live vs past:**

- Live since Oct 15: Yes lost 27 where prices predicted 52.6 (ratio 0.51, +1.68 cents for every dollar bet). No lost 53 where prices predicted 49.4 (ratio 1.07, −0.77 cents).
- So the live gap is about 2.45 cents for every dollar bet. The past gap is about 0.41. Live is about 6 times bigger.
- **How often did a gap this big show up in the past?** All 12.7-day stretches were checked, one starting every 6 hours. In 18% of them, the No side's ratio was 0.56 or more above the Yes side's, as big as live. In 4% it went the other way just as far. The typical stretch had No about 0.14 above Yes.

**What it means:**

- A two-week gap this big happens about 1 time in 5. Most of the live gap is luck, sitting on top of a small real tilt.
- **Skipping No-side bets is not supported.** In the past, No-side bets still made a small profit, +0.50 cents for every dollar bet since Jul 18 (about 1.9 on the luck scale). Dropping them would have cost money. The Oct 24 filter search also found that extra entry filters lost to the bot's two warning signs when tested on fresh data.
- If wanted, a "No side only above some price" rule could be tested properly after Nov 27. That would need its pass mark written down first, before looking at results.

## Context: what the past data says the edge is

This came out of rebuilding the rule. It matters for the Nov 27 decision.

The 1 cent line for Nov 27 (set Oct 27) was based on the backtests' "about 1.1 cents of profit for every dollar bet". That figure is the best recent stretch at the best fill assumption. Over the longer past it is lower:

| Period | Cents of profit for every dollar bet, at the recorded price | Same, with fills 0.4 cents worse |
|---|---|---|
| Whole history, Dec 2025 to Oct 8 | +0.80 | +0.41 |
| Since Jul 18 | +0.97 | +0.58 |
| Since Aug 24 | +1.16 | +0.76 |

- The live bot's base orders fill at about the recorded price (Oct 11 live-fills check), so the first column is closer to live.
- Live so far: +0.47 cents since Oct 15. Since Oct 20, 0.00 cents, or +0.52 cents without the two big crypto windows.
- So live is inside the range of the longer past, and below the best recent stretch.
- **For Nov 27:** a 1 cent reading would mean the bot is doing as well as its best past stretch. That is a high bar. But a reading of 0.5 to 0.8 cents would still match the long-run past, not a broken strategy. The plan already says that range means "keep running and check again later".

## Scripts

`flips.py` and `flips2.py`, one-off scripts not in the repo. They read `research/kalshi_15min/lab/markets.npz` with the research's helpers (`lab/common.py`) and the live pull `last48.json`. Analysis only. Nothing in `bot/` or the live server was touched.
