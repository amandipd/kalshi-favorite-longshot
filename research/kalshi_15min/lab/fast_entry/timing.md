# Fast entry: when the rush comes, what landing earlier is worth, and how long the test needs

Oct 11, 2026. Script: `timing.py` (about a minute: `python research/kalshi_15min/lab/fast_entry/timing.py`); numbers:
`timing.json` (not included; it is built from the bot's private ledger). It only reads three sources:

- the historical tape: `data/liquidity_tape.jsonl`, 35,793 live-rule bets from Dec 10 to Oct 8, the favourite's side, timed to the ms
- the live tape: `../live_fills/tape.jsonl`, the 473 markets the bot ordered in from Sep 28 to Oct 11, both sides, timed to the µs
- the bot's 496 orders in `bot/state/live-prod.db`, opened read-only

The bot's own fills are taken out of both tapes. Times are seconds after the window opened. **The mark** is 480.0 s,
when minute 8 ends. **Fill share** = contracts filled ÷ contracts asked for. **Cheap volume** = contracts others bought
on our side at or under our limit.

## What this means for fast entry

- **Where to land.** The rush starts 10–30 ms after the mark, and no home connection beats that. But the cheap volume
  comes out slowly: 10% of what trades in 480–486 s is gone by 480.2 s, 18% by 480.5 s, and 58% by 482.4 s (where the
  bot lands today). **Landing by about 480.2–480.5 s beats most of it.**
- **What the tape model says it's worth, at today's limit.** Landing at 480.2 s instead of 482.4 s adds +9 points of
  fill share on the historical bets and +12 to +17 on the bot's own recent orders, and +4.3¢ of P&L per $10.
- **With +1¢ in both arms (the plan), the gain is only +4 to +6 points (historical) and +3 to +4 (the bot's orders),
  and +1.7¢ per $10.** The +1¢ limit already catches most of the same misses. These are upper bounds: before about
  480.5 s the model counts the rush's own trades as ours, and its P&L is noisier than its ± says.
- **The live 2.4 s** (mean 2.61 s): 1.37 s waiting for the 3 s loop to wake, 0.77 s of PC clock offset plus the work
  before the first order, and 0.48 s queueing behind the window's earlier orders (0.22 s each). Fast entry removes
  nearly all of it. The PC clock drifts about 0.5 s a day, so ClockSync matters.
- **Live data can't measure the effect yet.** A second of step lag changes fill share by −1 ± 3 points, and each place
  later in the queue by −2.6 ± 1.5. Only 12 live orders have landed before 480.5 s.
- **How long the experiment needs.** Window fill share has a spread (standard deviation) of 0.30, and the bot orders in
  44 windows a day. Detecting +10 points needs about 150 windows per arm (7 days); +15 needs about 67 (3 days). The
  model's +3 points under +1¢ needs about 450 per arm (3 weeks), and the plan's 50 per arm only detects +17. A sharper
  outcome is the share filled at or under the ask the bot saw, which is what the old limit would have filled: about
  +16 points, so about 55 windows per arm (2–3 days).

## 1. When the rush happens

### Second 480, tenth by tenth

Each 100 ms bucket's share of the contracts bought on our side in second 480:

| tenth | historical, all | historical, Sep 24–Oct 8 | live tape, Sep 28–Oct 11 |
|---|---|---|---|
| 480.0–480.1 | 10.9% | 13.7% | 20.4% |
| 480.1–480.2 | 14.8% | 12.0% | 12.2% |
| 480.2–480.3 | 9.3% | 5.7% | 2.8% |
| 480.3–480.4 | 9.6% | 9.9% | 12.8% |
| 480.4–480.5 | 10.9% | 17.4% | 13.5% |
| 480.5–480.6 | 8.6% | 8.2% | 12.5% |
| 480.6–480.7 | 9.6% | 8.2% | 10.0% |
| 480.7–480.8 | 8.8% | 7.8% | 5.1% |
| 480.8–480.9 | 9.4% | 9.0% | 6.1% |
| 480.9–481.0 | 8.0% | 8.0% | 4.4% |

The rush has grown. Second 480's volume against second 479's was:

- 1.39× in Dec–Jul
- 1.03× in Jul 18–Aug 23
- 1.81× in Aug 24–Sep 23
- 1.76× in Sep 24–Oct 8
- **2.48×** on the live tape

### Contracts per 100 ms

- A **taker order** is an incoming order that trades. One taker order can hit several resting offers at once, and they
  all share its timestamp, so the table counts distinct timestamps.
- The **median per market is 0 in every bucket**, because most markets don't trade in a given tenth. The median column
  is therefore over the markets that traded in that tenth.

| tenth | hist. contracts | hist. cheap | hist. taker orders | hist. median | live contracts | live cheap | live taker orders | live median |
|---|---|---|---|---|---|---|---|---|
| 478–480, per 100 ms | 230k | 153k | 2,387 | 13 | 2,709 | 2,201 | 49 | 12 |
| 480.0 | 374k | 242k | 7,319 | 13 | 16,472 | 13,235 | 335 | 30 |
| 480.1 | 506k | 263k | 8,680 | 11 | 9,822 | 7,220 | 222 | 30 |
| 480.2 | 318k | 173k | 6,686 | 10 | 2,288 | 1,930 | 161 | 4 |
| 480.3 | 328k | 166k | 5,720 | 10 | 10,330 | 5,570 | 110 | 9 |
| 480.4 | 371k | 158k | 5,073 | 10 | 10,910 | 7,272 | 112 | 18 |
| 480.5 | 294k | 134k | 4,625 | 10 | 10,094 | 7,500 | 133 | 15 |
| 480.6–480.9, per 100 ms | 306k | 149k | 4,465 | 10 | 5,160 | 4,657 | 89 | 10 |
| 481–482, per 100 ms | 276k | 132k | 3,820 | 10 | 5,215 | 3,899 | 104 | 10 |
| 482–483, per 100 ms | 278k | 127k | 3,317 | 12 | 5,662 | 3,163 | 78 | 18 |
| 483–486, per 100 ms | 274k | 114k | 2,998 | 12 | 4,880 | 2,154 | 70 | 14 |

On the historical tape the cheap volume rises only about 1.6× over the pre-mark rate, and only for 200 ms. Most of
the rush's extra volume is at prices above the old ask: the price moving up.

### The first 150 ms, 10 ms at a time (trades)

| from | historical trades | historical contracts | live trades | live contracts |
|---|---|---|---|---|
| 479.90–480.00, per 10 ms | 538 | — | 9 | — |
| 480.00 | 500 | 17k | 11 | 102 |
| 480.01 | 671 | 20k | 68 | 2,361 |
| 480.02 | 842 | 21k | 146 | 4,566 |
| 480.03 | 1,065 | 37k | 70 | 1,698 |
| 480.05 | 1,498 | 36k | 66 | 778 |
| 480.07 | 2,103 | 46k | 57 | 737 |
| 480.09 | 2,431 | 63k | 75 | 1,287 |
| 480.11 | 2,244 | 85k | 49 | 1,066 |
| 480.13 | 1,803 | 53k | 57 | 1,199 |
| 480.15 | 1,616 | 34k | 86 | 970 |

**There is no spike at exactly 480.000.**

- Historical: 40 trades in that millisecond, against 100 a millisecond on average over 479.9–480.1.
- Live: none.

**The rush starts 10–20 ms after the mark.** On the live tape it peaks at 480.01–480.03, with the first big trade at
480.014 (1,142 contracts). On the historical tape it peaks at 480.06–480.11.

That fits low-latency bots that fire on the mark (on a synced clock, or on the minute closing) plus a network hop.
Orders stamped on the mark itself don't show up. Our order round trip is about 90 ms (the gap after an order that got
nothing), so the best fast entry can do is land at about 480.1–480.3.

### How much of the cheap volume is gone by each time

The share of cheap volume traded from 480.0 s up to each time:

| by | live, of 480–486 s | historical, of 480–486 s | live, of 480–510 s | historical, of 480–510 s | historical, average per market (480–510) |
|---|---|---|---|---|---|
| 480.2 | 10.4% | 6.5% | 3.4% | 1.7% | 9.0% |
| 480.5 | 17.9% | 12.9% | 5.8% | 3.4% | 14.6% |
| 481 | 31.2% | 22.3% | 10.1% | 5.9% | 20.8% |
| 482 | 51.0% | 39.3% | 16.6% | 10.4% | 29.0% |
| 482.4 | 58.2% | 45.9% | 18.9% | 12.1% | 31.5% |

### Is the resolution really to the millisecond?

Yes. Each test below would show a pile-up if the clock were coarser than it claims:

| tape | test | result | expected if genuine |
|---|---|---|---|
| historical (ms) | each period's last ms digit | 9.9–10.1% each, all four periods | 10% each |
| historical (ms) | trades at an exact whole second | 0.097% | 0.1% |
| live (µs) | last µs digit | 9.8–10.2% each | 10% each |
| live (µs) | trades at an exact whole ms | 0.113% | 0.1% |

The bot's own `ts_ms` is whole milliseconds.

## 2. Fills against landing time (historical tape)

**The model** is `fills.py`'s, with the landing time as a parameter. Its order is **immediate-or-cancel (IOC)**: it
takes what is on offer the moment it lands, and the rest is cancelled.

- **Nothing fills** if the first trade on our side within 10 s of landing is above the limit (the price ran away).
- **Otherwise** it fills min(wanted, max(V, 3)) contracts, where V is the cheap volume in the 30 s after landing.
- **Prices:** contracts at the old limit or better are charged the old limit. With +1¢, the dearer ones are charged
  their own price, cheapest first.
- **The orders:** $30 each (want = floor(30 / top)), at two limits: top (the minute-8 ask) and top + 1¢, capped at 99.9¢.
- **P&L** uses Kalshi's exact fee.

**Its limit: the tape shows trades, not the order book.**

- The model assumes that everything cheap traded after we land was on offer to us.
- Landing before the rush, that includes the rush's own trades, which we'd be racing other traders for. **So estimates
  below about 480.5 s are optimistic upper bounds.**
- 30 s is also generous for an order that only sees the instant it lands.

Three stricter variants:

| variant | what it counts |
|---|---|
| `tape` | `fills.py`: all cheap volume in 30 s |
| `split` | half of each cheap trade: we race the taker who took it and win half the time |
| `book1s` | only the cheap volume in the 1 s after landing: liquidity added later wasn't there when we landed |
| `book1s_split` | both |

### The `tape` model across landing times

P&L is in ¢ per $10 paid, shown as all (Dec–Jul half / Jul 18–Oct 8 half):

| landing | fill share, top | any fill, top | P&L, top | fill share, +1¢ | any fill, +1¢ | P&L, +1¢ |
|---|---|---|---|---|---|---|
| 480.0 | 57.7% | 88.3% | +5.9 (+3.4 / +7.7) | 79.1% | 99.2% | +7.7 (+4.2 / +10.0) |
| 480.1 | 54.4% | 83.8% | +5.3 (+2.9 / +7.1) | 78.5% | 98.9% | +7.8 (+4.2 / +10.1) |
| 480.2 | 51.7% | 80.0% | +5.1 (+4.0 / +6.0) | 77.9% | 98.5% | +7.7 (+4.3 / +9.9) |
| 480.3 | 50.4% | 78.0% | +5.2 (+3.9 / +6.2) | 77.6% | 98.3% | +7.6 (+4.2 / +9.8) |
| 480.5 | 48.7% | 75.6% | +4.7 (+2.9 / +6.0) | 76.9% | 97.9% | +7.5 (+4.0 / +9.7) |
| 481.0 | 46.1% | 72.2% | +3.6 (+2.3 / +4.6) | 75.4% | 96.9% | +7.0 (+3.8 / +9.2) |
| 481.5 | 44.3% | 69.9% | +2.5 (+1.0 / +3.7) | 74.3% | 96.0% | +6.7 (+3.3 / +8.9) |
| 482.0 | 43.2% | 68.4% | +2.2 (+0.6 / +3.5) | 73.5% | 95.3% | +6.4 (+3.1 / +8.4) |
| **482.4 (today)** | **42.4%** | **67.5%** | **+0.8 (−1.0 / +2.2)** | **72.7%** | **94.7%** | **+6.1 (+2.6 / +8.3)** |
| 483.0 | 41.6% | 66.5% | +0.5 (−1.8 / +2.4) | 71.8% | 94.0% | +6.0 (+2.8 / +8.1) |
| 484.0 | 40.5% | 65.1% | −0.1 (−3.2 / +2.4) | 70.2% | 92.6% | +5.6 (+2.6 / +7.5) |

The curve is steepest before 480.5 s. Landing at 480.2 s gets about 60% of the gain of landing at 480.0 s. The P&L
rises because the extra fills are in markets that are about to run away, and those are mostly winners. Its mirror image
is **adverse selection**: a slow buyer mostly fills where nobody else wants to buy. Both halves of the history show the
same trend.

### Against today (482.4 s), every variant

Each cell is the fill-share change and the P&L change in $ (35,793 bets, $30 orders) ± a standard error clustered by
window:

| variant | limit | fill share at 482.4 | landing 480.2 | landing 480.5 | landing 481.0 |
|---|---|---|---|---|---|
| tape | top | 42.4% | +9.3 pts, +$2,448 ± 448 | +6.3 pts, +$2,038 ± 419 | +3.7 pts, +$1,398 ± 355 |
| tape | +1¢ | 72.7% | +5.2 pts, +$1,683 ± 284 | +4.2 pts, +$1,399 ± 270 | +2.7 pts, +$959 ± 224 |
| split | top | 37.3% | +7.9 pts, +$2,095 ± 415 | +5.3 pts, +$1,691 ± 392 | +3.2 pts, +$1,173 ± 333 |
| split | +1¢ | 66.0% | +4.9 pts, +$1,430 ± 268 | +4.0 pts, +$1,156 ± 255 | +2.6 pts, +$753 ± 211 |
| book1s | top | 15.2% | +6.3 pts, +$1,542 ± 425 | +4.3 pts, +$1,297 ± 401 | +2.3 pts, +$949 ± 371 |
| book1s | +1¢ | 25.2% | +5.7 pts, +$1,350 ± 455 | +4.2 pts, +$1,075 ± 438 | +2.1 pts, +$462 ± 415 |
| book1s_split | top | 13.4% | +4.7 pts, +$1,133 ± 382 | +3.3 pts, +$942 ± 361 | +1.8 pts, +$803 ± 327 |
| book1s_split | +1¢ | 22.0% | +4.2 pts, +$1,044 ± 409 | +3.3 pts, +$892 ± 388 | +1.7 pts, +$400 ± 364 |

For scale, +$1,683 over 35,793 orders is about 5¢ an order.

**The ± understates the P&L noise.** Only about 5% of bets lose, and each loss costs about 18 wins, so a handful of
losing markets moves the P&L. The curve has jumps no timing could cause: `tape`/top drops $641 ± 198 between 482.0 and
482.4 s. Treat the direction as solid and the size as rough.

### Which variant is right? A check on the bot's own orders

This runs the model on the bot's 473 orders with their own limits, sizes and landing times, on the live tape with their
fills taken out. Reality: **54.5%** of contracts filled, 71.7% of orders got something, 134 got nothing.

| variant | real landing, top | all at 480.2, top | all at 480.5, top | all at 482.4, top | real landing, +1¢ | all at 480.2, +1¢ | all at 480.5, +1¢ | all at 482.4, +1¢ |
|---|---|---|---|---|---|---|---|---|
| tape | 56.8% | 73.4% | 70.2% | 60.0% | 93.1% | 96.1% | 96.3% | 92.5% |
| split | 53.4% | 68.4% | 64.9% | 56.4% | 90.5% | 93.7% | 93.9% | 89.9% |
| book1s | 29.6% | 45.1% | 40.5% | 31.6% | 48.4% | 53.5% | 50.6% | 45.6% |
| book1s_split | 27.1% | 39.2% | 36.4% | 29.2% | 44.6% | 47.3% | 45.9% | 41.6% |

- At the bot's real landing times, `tape` (56.8%) and `split` (53.4%) bracket reality (54.5%). The 1 s variants are
  far too strict. Every variant catches 105 of the 134 zero fills.
- Moved to 480.2 s, the calibrated variants add **+15 to +17 points** at the bot's limit, but only **+3 points** with
  +1¢.
- This check is only at today's landing times. Whether the model holds at 480.2 s is untested: 12 live orders have
  landed before 480.5 s.

## 3. The live breakdown (493 accepted orders, 144 windows, Sep 28–Oct 11)

- **Step lag** = `orders.ts` − open − 480, on the PC's clock: when the loop's step began.
- **Landing** = `ts_ms` / 1000 − open − 480, on Kalshi's clock.
- **Send delay** = landing − step lag. It mixes the two clocks.

|   | p10 | median | p90 | mean |
|---|---|---|---|---|
| step lag (PC) | 0.24 | 1.37 | 2.65 | 1.59 |
| landing (Kalshi) | 0.98 | 2.44 | 4.28 | 2.82 |
| send delay (raw) | 0.29 | 0.97 | 2.53 | 1.24 |
| gap to the order before | 0.09 | 0.20 | 0.30 | 0.22 |
| rank in the window | 1 | 3 | 6 | 3.2 |

Two windows had steps that began late (7 s and 36 s after the mark) and are left out below. The first orders' step
lag is uniform over 0–3 s (27, 24, 27, 20, 17 and 26 per half second), as a 3 s loop would give.

**Where the mean 2.61 s goes** (an exact split of the mean):

| part | seconds | share | what fast entry does to it |
|---|---|---|---|
| waiting for the 3 s loop (step lag) | 1.37 | 52% | an alarm at the mark |
| PC clock offset + the work before the first order (housekeeping, markets, books, minute prices, balance, the send) | 0.77 | 29% | prep at 450 s; ClockSync |
| queueing behind earlier orders | 0.48 | 18% | all orders sent at once |

The queue costs 0.22 s per order ahead: 0.09 s if that order got nothing (just its round trip), and 0.21 s if it filled
(the bot reads its fills before going on).

**The PC clock drifts, so the middle row can't be split further.**

- The first order's raw delay (Kalshi's clock minus the PC's) was 1.2–1.5 s on Sep 28–29 and about 0 on Oct 9. It
  then climbed steadily, to about 0.9 s by the evening of Oct 11.
- The gaps between orders, which use Kalshi's clock alone, stayed flat at 0.09 and 0.20 s.
- A raw delay of −0.13 s (Oct 9) is impossible for the work before an order. So the PC clock was then ahead of Kalshi,
  and it has slipped about 0.4–0.5 s a day since, unless that work also grew.
- The 0.155 s SNTP reading holds only for Oct 11 evening. A fixed offset would have been off by up to about 1 s, so on
  Oct 9–10 some steps may have read the books before minute 8 had closed.
- This is why ClockSync, and logging the send and answer times (`send_all` does), matter.

| half day | first order's raw delay, median (p10) | gap after a fill | gap after nothing |
|---|---|---|---|
| Sep 28 am | 1.47 (1.38) | 0.25 | 0.16 |
| Sep 29 pm | 1.24 (1.19) | 0.16 | 0.07 |
| Oct 9 pm | −0.01 (−0.13) | 0.20 | 0.09 |
| Oct 10 am | 0.24 (0.11) | 0.20 | 0.09 |
| Oct 10 pm | 0.49 (0.28) | 0.23 | 0.11 |
| Oct 11 am | 0.49 (0.41) | 0.21 | 0.09 |
| Oct 11 pm | 0.93 (0.78) | 0.21 | 0.09 |

### By rank in the window

Medians, with p10–p90 in brackets. Fill share ± a standard error clustered by window:

| rank | orders | landing | step lag | send delay | gap | fill share | got nothing |
|---|---|---|---|---|---|---|---|
| 1 | 144 | 2.05 (0.78–3.44) | 1.40 | 0.51 (0.09–1.43) | — | 52.4% ± 4.2 | 39 |
| 2 | 96 | 2.24 (0.89–3.67) | 1.38 | 0.70 (0.29–1.65) | 0.20 | 59.0% ± 5.3 | 27 |
| 3 | 75 | 2.36 (1.02–3.98) | 1.29 | 0.90 (0.47–1.88) | 0.19 | 56.9% ± 5.8 | 18 |
| 4 | 59 | 2.52 (1.30–4.05) | 1.28 | 1.29 (0.58–2.25) | 0.21 | 61.8% ± 7.1 | 17 |
| 5 | 46 | 2.79 (1.44–4.32) | 1.22 | 1.42 (0.70–3.00) | 0.20 | 42.7% ± 7.7 | 15 |
| 6–7 | 49 | 3.00 (1.71–5.08) | 1.16 | 1.72 (0.97–3.73) | 0.19 | 54.0% ± 7.7 | 14 |
| 8+ | 24 | 4.68 (2.12–7.31) | 1.59 | 2.78 (1.56–4.63) | 0.19 | 39.9% ± 10.2 | 10 |

### By landing time (s after the mark)

| landing | orders | of them first in their window | fill share | got nothing |
|---|---|---|---|---|
| under 1.0 | 52 | 24 | 51.5% ± 7.1 | 16 |
| 1.0–1.5 | 52 | 22 | 52.1% ± 6.3 | 15 |
| 1.5–2.0 | 73 | 23 | 56.5% ± 7.3 | 20 |
| 2.0–2.5 | 77 | 23 | 62.8% ± 5.8 | 19 |
| 2.5–3.0 | 72 | 19 | 53.1% ± 6.8 | 22 |
| 3.0–3.5 | 65 | 19 | 57.2% ± 5.5 | 14 |
| 3.5–4.5 | 60 | 8 | 43.9% ± 5.9 | 20 |
| 4.5 and over | 42 | 6 | 59.9% ± 10.5 | 14 |

### Do later orders in a window fill worse? (natural experiments)

A **natural experiment** is variation the bot creates by accident, which works almost like a coin flip. Two kinds exist
here:

1. **Rank.** Within a window, an order's place in the queue depends on which other markets happened to qualify.
2. **Step lag.** Across windows, it depends on where the 3 s loop happened to wake, and it moves every order in the
   window, and the book read, together.

The bot sends in Kalshi's series order, and series fill very differently (BTC 79%, NEAR 41%). So each regression
holds the series fixed, and the window too where it can. A **fixed effect** is a separate baseline for each window or
series, so only differences within it count. Weighted by contracts asked; standard errors clustered by window:

| comparison | fixed effects | estimate | z |
|---|---|---|---|
| per place later in the queue (0.22 s each) | window + series | −2.6 ± 1.5 pts | −1.7 |
| the same, per second (rank as instrument) | window + series | −11.7 ± 6.7 pts/s | −1.7 |
| rank 5 / 6–7 / 8+ vs rank 1 | window + series | −13 ± 10 / −13 ± 10 / −27 ± 12 pts | — |
| per second of step lag, all orders | series + rank + day | −1.1 ± 2.7 pts/s | −0.4 |
| per second of step lag, first orders only | series | +5.5 ± 4.5 pts/s | +1.2 |
| first order minus the later ones, same window | none | −0.7 ± 5.4 pts | — |

- **Maybe a little, but it's not proven.** The queue estimate is negative but under 2 standard errors.
- Ranks 2–4 look like rank 1. The drop shows up at rank 5 and beyond, where there are few orders.
- The step lag shows no effect, with a range that includes the model's −2 to −5 pts/s.
- Regressing on landing time directly gives −19.8 ± 6.9 pts/s, but it is biased. The gap after an order is longer
  when that order filled, so landing later partly just means "the order before filled". Rank doesn't have that problem.

## 4. Power: how long the experiment needs

**Power** is the chance that a real effect of a given size shows up as significant. Here the bar is 80% power at
2 standard errors, with the standard error clustered by window, the unit the coin is flipped on.

- The formula is windows per arm = 2 × (2 + 0.84)² × σ² / Δ².
- σ is the spread of window fill share around the overall ratio, weighted by contracts.
- The two arms share the days, so days = 2 × windows per arm ÷ windows a day.

Over the last 3 days the bot ordered in **44.0 windows a day** (3.2 orders each, 141 orders a day). Window fill share
had a mean of 51%, a median of 50% and a p10–p90 range of 0–100%; σ = **0.30**. All 14 days give σ = 0.31, at a
slower pace.

| effect to detect | windows per arm | days at 44 a day |
|---|---|---|
| +5 pts | 595 | 27 |
| +10 pts | 149 | 6.8 |
| +15 pts | 67 | 3.0 |
| what 50 windows per arm can detect (the plan's minimum) | 50 | 2.3 |

At 50 windows per arm, only effects of +17 points or more show up reliably.

Three refinements:

- **With +1¢ in both arms (the plan).** The tape model on the bot's own orders puts fill share at 93% today and 96% at
  480.2 s: an effect of about +3 points. The spread shrinks too (σ ≈ 0.16), so it needs about **450 windows per arm,
  20 days**. At 50 windows per arm the chance of seeing it is about 15%, so the verdict would most likely say "no clear
  difference" even if fast entry works as modelled. This σ comes from the model, not from real fills.
- **A sharper outcome.** Under +1¢ the order takes the cheapest offers first. So the contracts it fills at or under the
  ask it saw are exactly what an order at the old limit would have filled. That fill share has the model effect of
  about +16 points (σ 0.30) and needs about **55 windows per arm, 2–3 days**. It can be computed from the fills table's
  prices. The catch: the two arms read their asks at different times (480.0x vs about 481.7), so this measures "filled
  at the price seen", not "filled at the same price".
- **Randomising each market instead of each window** barely helps (+10 pts: 5.3 days instead of 6.8). Orders in the
  same window are almost as different from each other as from orders in other windows (σ 0.45 vs 0.46 per order).
  Holding the series fixed cuts the windows needed by only about 4%.

## Caveats

- **Trades, not the book.** Every tape estimate takes what traded as what was on offer. Landing before the rush, we'd
  be racing the traders whose trades we are counting. The `split` variant covers one half-and-half version of that
  race, not a race we always lose.
- **The limit.** Historically it is the minute-8 candle's ask (the ask recorded at the end of minute 8, about 480.0).
  For the live bot it is the ask it saw at about 481.5–482. On the 71 live orders that are in both datasets, the two
  agree in the median (mean +0.1¢; 32% higher, 24% lower).
- **What fast entry changes besides timing isn't modelled.** Books read at 480.0x can change which markets qualify. And
  other traders may react to a faster bot.
- **Losses are rare.** P&L estimates move with a handful of losing markets; use them for direction, not size.
- **The live sample is small.** 144 windows, almost all from the last 3 days, and only 12 orders before 480.5 s. The
  model's prediction for fast entry is an extrapolation it hasn't been checked on.
