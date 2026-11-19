# Live fills: the bot's real orders against Kalshi's trade tape

The question: is there anything we can do about the contracts the bot asks for but doesn't get?

This covers the bot's 476 orders from Sep 28 to Oct 11 (the last at 03:38 UTC on Oct 12), read from `bot/state/live-prod.db`
read-only. For every market it ordered in, we fetched Kalshi's public trade tape (every trade, with its time, price
and which side the buyer took) for seconds 470-600 of the window, plus the market's result. Script:
`live_fills.py`; numbers: `live_fills.json`; tape: `tape.jsonl` (10 MB); results: `markets.json`. The three data
files are not included: they are built from the bot's private ledger.

**Prices are always on our side**, meaning the price of the side the bot bought. A NO buy goes to Kalshi as a sell of
YES at 1 minus the NO price. Kalshi reports that order's `average_fill_price` in YES terms too, so the NO price paid is
1 minus it. Fees use Kalshi's formula 0.07 x C x P x (1-P) per order, exact (not rounded up to the cent).

## What happened

| | |
|---|---|
| orders | 476 sent, 473 accepted (3 rejected on Sep 28: not enough cash) |
| contracts | 6,556 asked for, 3,576 filled (**54.5%**) |
| orders filled | 240 in full, 99 partly, 134 not at all |
| price improvement (paying less than the limit) | 106 of 339 filled orders; 0.24c a contract on average, $8.49 in all |
| real P&L | $107.52 on 3,576 contracts (+3.0c a contract) |

**As the orders grew.** Sep 28-29, at about 2 contracts an order, 76% of contracts filled. On Oct 10-11, at 15-20 an
order, 55% filled. Size matters less than that suggests, though. On Oct 10-11, orders of 11-20 contracts filled 55% and
orders of 31+ also filled 55%. Bigger orders mostly turned full fills into partial ones. The share of orders that got
nothing rose only from about 23% to 28%.

| order size | orders | filled | got nothing |
|---|---|---|---|
| up to 10 | 125 | 55% | 37 |
| 11-20 | 316 | 55% | 86 |
| 21-30 | 6 | 34% | 3 |
| 31+ | 26 | 55% | 8 |

By series: BTC fills best (81%), then XRP, ETH, ZEC and SOL (55-59%), BNB, DOGE, HYPE and NEAR (41-50%), and gold and
silver worst (24-28%, few orders).

**Why orders miss.** Other traders buy the same favourites the moment minute 8 ends. Contracts bought on our side jump
from 22-53k a second (all markets together) to 81k in second 480. The bot's order lands at a median of 482.4 s. By
then, the volume at or under our limits has halved. Of the 134 orders that got nothing, 105 saw the next trade on our
side, within 10 s, priced above our limit: 76 of them by 0.5c or less, 94 by 1c or less, 104 by 2c or less. Within the
range the bot actually sends in (481-486 s), sending earlier didn't fill better.

**Did the missed markets win anyway?** Yes, about as often as their prices said:

| orders | won | mean limit |
|---|---|---|
| filled in full | 96.3% (231/240) | 94.9c |
| filled partly | 92.9% (92/99) | 94.2c |
| got nothing | 95.5% (128/134) | 94.7c |

If all 2,980 missing contracts had filled at the bot's own limit, they would have added just **+$12 (± $45)**. That is
+0.4c a contract, against +3.0c a contract on the ones that did fill. On this sample, the misses were not money left on
the table.

## Checking the fill model (liquidity.py)

The backtest's "real liquidity" model says an order gets nothing if the price ran away first, meaning the first trade on
our side after the order (assumed at 482 s) came within 10 s and above our limit. Otherwise it gets the contracts others
bought at our limit or better in the next 30 s, or 3 if that's more. The bot's own fills are on the tape (found for all
339 filled orders, by Kalshi's timestamp), so they are taken out first. Otherwise the model would partly be "predicting"
our own trades.

| model run | contracts (real 3,576) | zero fills caught (of 134) | filled orders called zero | P&L at the limit (real $99.53) |
|---|---|---|---|---|
| send at 482 s, as the backtest does | 4,017 (+12%) | 76 | 63 | $57.60 |
| each order's real send time | 3,726 (+4%) | 105 | 65 | $86.42 |
| 482 s, our own fills left in | 4,476 (+25%) | 76 | 40 | $60.27 |

- In total, the model gets close. Per order, it is rough: it misses most zero fills or calls many filled orders zero,
  depending on the send time assumed.
- Its P&L depends on how many contracts it puts on the 22 losing markets: 149 at 482 s against 82 real. So it
  under-states P&L here ($58 vs $100). The gap is -$42 ± $37, so it could be chance.
- Across assumed send times from 481 s to 484 s, its P&L ranges from $41 to $87, with no steady trend
  (`send_sweep` in the JSON).
- liquidity.py's docstring says its check on the first 76 orders predicted 126 contracts against 130 real and caught
  10 of 17 zero fills. That doesn't replicate: with the bot's real limits on the same tape, we get 153 vs 129.5, catching
  6 of 17. liquidity.json matches our tape on when and at what price the next trade came. Its contract count differs
  because it is measured at the backtest's minute-8 candle ask (the recorded price at the end of minute 8), not the
  bot's real limit.

## What-ifs

**A higher limit.** For each order that didn't fill in full, we count the contracts others bought on our side priced
above the old limit and up to the new one, in the 30 s after the order. We take the earliest first, up to what the order
still wanted. An order gets nothing more if the price ran past even the new limit. The extra contracts are priced at
those trades' prices.

| limit raised | orders helped | extra contracts (30 s / 5 s) | avg price | won (contracts) | fees | extra P&L ± noise |
|---|---|---|---|---|---|---|
| +0.5c | 173 | 1,824 / 1,319 | 94.87c | 93.6% | $6.13 | -$29 ± $39 |
| +1c | 205 | 2,383 / 1,686 | 94.84c | 94.1% | $8.06 | -$25 ± $43 |
| +2c | 216 | 2,642 / 1,848 | 94.80c | 94.7% | $9.01 | -$11 ± $43 |
| +3c | 216 | 2,651 / 1,854 | 94.79c | 94.7% | $9.06 | -$11 ± $43 |

At about 94.8c, a contract needs to win about 95.2% of the time to pay for itself and its fee. The extra contracts won
93.6-94.7%. That is within noise of break-even, so there is no sign of profit either. The orders that got nothing were
roughly break-even (-$4 to +$8). The partly filled ones lost (-$19 to -$25), because their markets won only 91-93%.

**A second order 5 or 10 s later.** This sends a second immediate-or-cancel order for what's left, at the last price
anyone paid on our side. At 5 s it fills 1,723 more contracts at 93.6c for **+$13 ± $35**. At 10 s it fills 1,820 at
94.4c for **-$10 ± $39**. Both are noise.

## Caveats

- **Tiny sample of losses.** Only 22 of the 473 markets lost, and each loss costs about 18 wins. Every P&L above is
  within about one standard error (a measure of how far chance alone could move it) of zero. The ± figures treat orders
  as independent, but crypto favourites in a window lose together, so the real noise is larger. Use the historical tape
  to decide on a limit change. Live data can't settle a 1c-a-contract question yet.
- **30 s is generous.** An immediate-or-cancel order only meets the book at the instant it lands. Contracts that trade
  20 s later may not have been on offer then. The 5 s column is the stricter reading; it fills about 30% fewer extra
  contracts.
- A higher limit or a second order would take contracts others bought, and change what they do. That isn't modelled.
