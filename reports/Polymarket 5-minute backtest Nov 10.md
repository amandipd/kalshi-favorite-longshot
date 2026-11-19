# Polymarket 5-minute markets: the backtest

*Nov 10, 2026. Follows `reports/Polymarket 5-minute markets Nov 8.md`. The rules and pass bar were written down
before any result was read: `research/polymarket_5min/PREREG.md`. Public data only. No account, no orders.
Nothing in `bot/` or on the servers was touched.*

## The answer

1. **A straight copy of the bot does not pass. It is "unclear".** Buying the favourite at minute 3 of 5 with the
   bot's two filters made **+0.19 cents for every dollar bet** after fees. The range the true number is probably in
   runs from −0.41 to +0.79 cents. That is too close to zero to tell from luck, and below the +0.5 cent bar.
2. **The filters matter here too.** Without them, the same favourites **lost 3 cents for every dollar bet**.
3. **Buying one minute later (minute 4 of 5) passed the pre-set test.** It was picked on Oct 22–31, then scored once
   on Nov 1–11, which it never saw while being picked. It made **+0.95 cents for every dollar bet**, with a range of
   +0.76 to +1.15. That is about $40 a day at $10 a bet.
4. **But I don't trust the minute-4 number yet.** The backtest's minute-4 price can be up to about 8 seconds late,
   and those seconds fall inside the final minute that decides the result. In live checks, a bot buying at exactly
   4:00 would have made a different bet or paid a different price in **12 of 59** cases. So the real profit is
   probably smaller, and it could be zero.
5. **Possible next step:** a 3-day paper recorder that reads the price a bot would really see at 4:00, with no
   peeking, then scores those bets. Nothing would be traded.

## What was tested

- **Markets:** every Polymarket US 5-minute up/down market on BTC, ETH, SOL and XRP, from the first on Oct 22 to
  Nov 11. That is 22,367 markets, every one resolved. 317 windows were never listed (the launch day and a 2-hour gap
  on Nov 5).
- **Prices:** Polymarket's own price history, one point a minute, with both the buy and the sell price.
- **The main rule:** the bot's own code (`research/kalshi_15min/lab/common.py`), changed only in two ways:
  - it buys at the end of minute 3 of 5 instead of minute 8 of 15;
  - its price cap is 99c, Polymarket's top price.
- **The bet:** buy the favourite (the likely side) at 92c to 99c, $10 a bet, at the price showing.
- **Fees:** Polymarket's taker fee (its charge for buying at the posted price). It changed on Nov 6 to depend on your
  monthly volume. The main numbers use the second-cheapest tier (0.085). The other tiers are below.

## The results

**The main test: a straight copy, buying at minute 3**

| What | Bets | Cents for every dollar bet | Lost (prices implied) |
|---|---|---|---|
| The bot's rule | 2,254 | +0.19 (range −0.41 to +0.79) | 43 (52) |
| Same favourites, no filters | 11,024 | −3.04 (range −3.59 to −2.50) | 630 (338) |
| The bot's rule, fills one cent worse | 2,254 | −0.22 | 43 (52) |

- Verdict: **UNCLEAR**. It made money, but the range reaches below zero, and the best guess is under the +0.5 cent bar.
- Dropping its best coin (ETH) leaves +0.06 cents. Dropping its best day leaves +0.11 cents.
- It fell from +0.30 cents (Oct 22–31) to +0.10 cents (Nov 1–11).
- **Breakeven slippage** (how much worse fills can get before all the profit is gone): about **0.19 cents a
  contract**. Polymarket prices move in whole cents, so a fill even one cent worse turns it into a loss.
- About **116 bets a day**. BTC lost money (−0.34 cents). ETH, SOL and XRP made money, but none of them clears luck
  on its own.

**Fee tiers, straight copy (cents for every dollar bet)**

| Your monthly taker volume | Fee rate | Cents for every dollar bet |
|---|---|---|
| $250k or more (and every new account's first 7 days) | 0.0695 | +0.23 |
| $50k to $250k | 0.075 | +0.22 |
| $10k to $50k (the main number) | 0.085 | +0.19 |
| Under $10k | 0.095 | +0.17 |

Fees barely matter here. Most bets are at 98–99c, where the fee is smallest.

**The backup search: buying one minute later**

The pre-set plan said that if the straight copy didn't pass, 27 variants would be tried on Oct 22–31 only:

- buy at minute 2, 3 or 4;
- the bot's filters, a lighter late-jump filter, or no filters;
- a price floor of 90c, 92c or 95c.

The best one would then be scored once on Nov 1–11.

- **Minute 2 lost money in every version.** **Minute 3 made a little.** **Minute 4 made the most.**
- No filters lost money at every minute. So the filters are the whole edge here too, just as on Kalshi.
- The pick: **minute 4, the bot's filters, 90c floor.**

| Minute-4 pick | Bets | Cents for every dollar bet | Lost (prices implied) |
|---|---|---|---|
| Oct 22–31 (where it was picked) | 3,524 | +1.50 (range +1.26 to +1.74) | 15 (72) |
| **Nov 1–11 (scored once)** | **4,220** | **+0.95 (range +0.76 to +1.15)** | **15 (60)** |

- It meets all three pass conditions on Nov 1–11:
  - above +0.5 cents;
  - the whole range above zero;
  - still +0.88 cents after dropping XRP, its best coin, and +0.91 cents after dropping its best day.
- All four coins and both sides made money on Nov 1–11. It made money on 20 of the 21 days; the one loss was launch
  day (57 bets).
- **88% of the bets are at 99c.** Those 3,709 bets lost 5 times where 99c prices implied 37.

## Why the minute-4 result may be too good

**Where the money seems to come from.** Polymarket prices stop at 99c and move in whole cents. With a minute left, a
favourite that is really 99.8% likely still can't be priced above 99c. Buying it at 99c collects a small, steady
overpayment from people buying the 1c longshot (the unlikely side). Kalshi prices move in tenths of a cent above
90c, so this cap barely bites there. That could explain why Kalshi's last-minute favourite idea failed its fresh test
on Oct 29, while this one looks good.

**The problem: the price may peek.**

- Each minute's history point keeps updating until about 8 seconds after the minute ends. We confirmed this by
  polling live for about 80 minutes (`live_timing.jsonl`, `live.jsonl`).
- At minute 4 those 8 seconds fall **inside the settlement minute**. Polymarket, like Kalshi, settles on the average
  price over the last 60 seconds.
- So the backtest buys at a price that already knows a little about how that minute is going. The live checks
  (`peek.py`) found:
  - 31 of 68 minute-4 points changed after 4:00;
  - in 12 of 59 markets with a 90–99c favourite, a bot buying at 4:00 would have made a different bet or paid a
    different price;
  - the changes mostly moved toward more certainty (for example 88c → 98c, 97c → 99c).
- At minute 3 the same 8 seconds fall before the settlement minute, so the straight copy is barely affected.

**Other open questions:**

- **Depth** (how much money you can trade before moving the price). In 8 live books with a 92–99c favourite, the
  favourite's price had **$22 to $1,903 on offer, median about $100**. At 99c: ETH $57, SOL $151, XRP $65 and $833.
  BTC was deepest. These were read at about minute 2.5, through a cache up to 30 seconds old. So $10–$50 bets look
  fine, and $100+ often won't fill.
- **Being picked off** (adverse selection: getting picked off by someone who knows more than you). With a minute
  left, faster bots may take the 99c offers first. Only real orders can show that.
- **19 days, one stretch of market.** The Kalshi bot's own good stretches have faded before.

## Checks that passed

- **Settlement matches Kalshi exactly.** At every 15-minute mark, Polymarket's 5-minute close equals Kalshi's
  15-minute final value for the same coin: 7,390 of 7,390 checks across all four coins. The same holds for the
  starting prices: 7,361 of 7,361. XRP differs only in rounding: Polymarket keeps 5 decimals, Kalshi 4. The rules say
  BRTI-family indexes, and the data agrees.
- **Each window starts where the last one ended:** 22,266 of 22,266.
- **No duplicates, every market resolved.** The listed fee rate is 0.095 on every market.

## What I'd do next (nothing started)

1. **A 3-day paper recorder, no peeking.** At exactly 4:00 into each window, it saves the price a bot could really
   see then. That is a slightly older price than the backtest used, which is the safe direction. It also saves the
   order book. Then it scores those bets against the results. That would be about 1,200 paper bets. That is enough to
   tell +0.95 cents from zero, at about 4 cents of swing per bet.
   - It needs a machine that stays on, or the same 5-minute watchdog the thin-market recorder used.
2. **Pass bar for it, fixed before it starts:** profit above +0.5 cents for every dollar bet, with the range above
   zero.
3. **Only if it passes:** a Polymarket US account and API key, a check that the server's location can trade there, then a
   small real-money test to measure fills at 99c.

## Files

All in `research/polymarket_5min/`:

- `PREREG.md`: the rules and pass bar, with dated notes on the timing check and the moved data end.
- `fetch.py` → `markets.jsonl`: every market, its result, and its price history.
- `score.py` → `score.json`: every number above. Its tests are in `tests/test_score.py` (19 pass).
- `settle.py` → `settle.json`: the Kalshi settlement match.
- `live.py`, `live_report.py` → `live_timing_report.json`, `live_report.json`: timing and depth.
- `peek.py` → `peek.json`: the 8-second check.
- `calibrate.py`, `record.py`: first tries at the timing check, kept for the record. The CDN's cache made them
  unreliable.
