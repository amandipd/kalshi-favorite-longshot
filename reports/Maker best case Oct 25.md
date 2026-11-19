# Waiting at the bid vs buying the ask: best and worst case (Oct 25)

## The answer

- **No clear win.** Waiting at the bid lands somewhere between a bit better and clearly worse than the bot's way.
  The bid is the best price a buyer is offering. The bot buys at the ask, the cheapest price a seller will take.
- **Best case: 16% more money.** Over 1,697 past markets at 15 contracts each, it makes $267. Buying the ask
  makes $231. The extra $36 is probably real: the range the true number is probably in is +$11 to +$62.
- **Worst case: 24% less money.** It makes $175, so $56 less. The range the true number is probably in is
  −$86 to −$26.
- **The truth sits between the two.** Where depends on how many orders were waiting at the bid ahead of ours.
  Kalshi's trade history cannot show that. Only the order book can: the list of orders waiting to buy and sell.
- **Getting picked off is real, but small.** Getting picked off means getting filled by someone who knows more than
  you. Orders that got filled (got their contracts) won 96.6% to 97.0% of the time. All markets won 97.3%.
  The Oct 11 test said 89% to 92%.
- **What decides it is the markets the waiting order misses.** It never fills in 11% to 21% of markets. Every one
  of those markets won. Missing them costs about as much as the cheaper price saves.
- **What to do:** keep buying the ask for now. The order-book recorder (`maker_shadow.py`) can measure the line at
  the bid. That will settle which end of the range is true.

## What was tested

The bot is a **taker**. A taker buys right away from someone already waiting to sell. The bot acts at minute 8 of
each 15-minute market. It buys the favourite (the likely side) when its ask is 92 to 99.9 cents. The ask is the
cheapest price a seller will take. It pays up to 1 cent over the ask. It also pays the taker fee (Kalshi's charge
for trading, biggest near 50 cents).

A **maker** leaves a waiting order and lets a seller come to it. The pretend maker order here:

- At minute 8, wait to buy 15 contracts of the favourite at its **bid**. The bid is the best price a buyer is
  offering. Above 90 cents, prices move in steps of a tenth of a cent. Here the bid was most often just 0.1 cent
  under the ask (a third of markets). It was a full 1 cent under in about one market in 8.
- Hold whatever fills until the market closes.
- Makers pay no fee on these 16 series. Kalshi lists all 16 as fee type "quadratic", which charges takers only.

Kalshi keeps every trade, but not the order book. So the test reads every trade from minute 8 to the close. It
looks for sellers of the favourite. On Kalshi, buying the other side is the same as selling the favourite to a
waiting buyer. Two cases:

- **Best case (front of the line).** Orders waiting at the same price fill in the order they arrived. Here our
  order is first. Every contract sold at our price or lower fills us, up to 15.
- **Worst case (back of the line).** Our order is last. Only sales below our price fill us. A sale below our price
  means every order at our price, ours included, had already filled.

A filled contract makes (1 − our price) if the favourite wins. It loses our price if it loses.

The comparison is the taker on the same markets:

- Where the bot bought, we use its own average price, for 15 contracts, with the fee for 15.
- Where it skipped, we use 15 contracts at the ask, with the fee.

## What was fetched

- **Period:** the server era only, since the bot moved to a server near Kalshi's. That is Oct 16 1:23 AM to
  Oct 25 8:08 PM ET. That era has exact timing.
- **Markets:** 1,697 of the 2,739 in-band server-era markets. In-band means the favourite's ask was 92 to 99.9 cents.
  - The bot's own buys: 1,405 of 1,919 (73%).
  - Markets the bot skipped, was halted on, or hit an error: 292 of 820 (36%).
  - Both were picked in a shuffled order, so they spread evenly over the 10 days.
- **BTC was sampled.** BTC markets have about 9 pages of trades each, against about 1 for most others. Only one BTC
  window in 5 was fetched. 29 BTC markets are in the 1,697.
- **The home-PC era was not fetched.** That is Sep 28 to Oct 15, when the bot ran on a home PC. There was no time.
- **Why so little:** Kalshi refused about half of all requests for going too fast. Another fetcher was using
  the same allowance at the same time. About 5,600 requests got 2,926 pages, holding about 2 million trades.
- **Losses:** the favourite lost in 45 of the 1,697 markets. The markets fall in 587 different 15-minute windows.

## 1. How often the waiting order filled

| Case | Got any fill | Got all 15 contracts | Time to first fill (middle market) |
|---|---|---|---|
| Best case (front of the line) | 88.7% of markets | 86.0% | 2.5 seconds after minute 8 |
| Worst case (back of the line) | 79.1% of markets | 77.5% | 7.1 seconds after minute 8 |

- Fills come fast. Half the fills come within 2.5 seconds (best case) or 7 seconds (worst case).
- A lot sells at our price or lower. In the middle market, sellers sold 977 contracts at or under our price after
  minute 8. So our 15 fills easily if we are near the front.
- The worst case still fills often. Above 90 cents, prices move in steps of 0.1 cent. A sale just 0.1 cent under
  our price counts.

## 2. Who won

| Group of markets | Favourite won |
|---|---|
| Filled, best case (front of the line) | 97.0% |
| Filled, worst case (back of the line) | 96.6% |
| Never filled (either case) | 100% |
| All 1,697 markets | 97.3% |
| The bot's own buys (1,405 markets) | 97.7% |

- Filled orders win a little less often than all markets. That is the picking off.
- In the markets where nobody sold to us, nobody wanted to sell the favourite cheaply. It won every time.

## 3. Profit

All at 15 contracts a market, over the same 1,697 markets.

| Way of buying | Profit | Cents of profit for every dollar bet | Range the true number is probably in |
|---|---|---|---|
| Buy the ask (the taker) | $231 | +0.94 | −0.16 to +2.04 |
| Wait at the bid, best case | $267 | +1.26 | −0.01 to +2.53 |
| Wait at the bid, worst case | $175 | +0.92 | −0.48 to +2.32 |

The ranges above are wide because 45 losses in 10 days is a small number. Luck in a few losses moves them a lot.
The difference between the two ways is much better measured. Both lose on the same markets, so that luck cancels.

| Waiting order minus buying the ask | Extra profit | Range the true number is probably in | Extra cents of profit for every dollar bet | Range it is probably in |
|---|---|---|---|---|
| Best case (front of the line) | +$36 (+16%) | +$11 to +$62 | +0.32 | +0.13 to +0.51 |
| Worst case (back of the line) | −$56 (−24%) | −$86 to −$26 | −0.03 | −0.35 to +0.30 |

- Per dollar bet, the worst case is a tie. It loses in dollars because it bets less. It fills in only 79% of
  markets. It puts $19,071 to work, against $24,484 for the ask.
- The ranges count each 15-minute window once. Markets in the same window move together, so they are not
  separate pieces of evidence.

## 4. Why the two cases differ: the saving against the picking off

- **The saving.** On the markets the waiting order fills, it pays the bid instead of the ask, and no fee. That is
  worth +0.72 cents for every dollar bet, in both cases.
- **The picking off.** The markets it fills are worse markets. Buying the ask made +0.94 cents for every dollar
  bet over all markets. On only the markets the waiting order filled, buying the ask made +0.54 (best case) or
  +0.20 (worst case). So the fills cost 0.40 to 0.74 cents for every dollar bet.
- **Net:** +0.72 − 0.40 = +0.32 in the best case. +0.72 − 0.74 = about 0 in the worst case.

## 5. What the price did after a fill

This checks for getting picked off. It compares the favourite's last trade price after our first fill with our
price, in cents. "All markets" is the same measure taken from minute 8 in every market.

| Time after the fill | Best case | Worst case | All markets, from minute 8 |
|---|---|---|---|
| 5 seconds | −0.04 cents | −0.38 cents | +0.40 cents |
| 30 seconds | −0.19 cents | −0.69 cents | +0.35 cents |
| 60 seconds | −0.03 cents | −0.45 cents | +0.25 cents |
| Share 0.5 cents or more under our price at 60 seconds | 23% of fills | 27% of fills | 21% of markets |

- After a fill, the favourite trades about half a cent (best case) to one cent (worst case) lower than usual.
- Part of that gap is built in. A fill means the last trade was a sale at the bid, so the next price starts low.
- So the picking off is mild. The price usually holds. It does not usually collapse after we fill.

## 6. By price band

A band is a price range, like favourites priced 92 to 95 cents. Here the band is set by the favourite's ask at
minute 8.

| Band | Markets | Favourite won, when filled (best / worst case) | Extra cents of profit for every dollar bet, best case (range it is probably in) | Same, worst case (range it is probably in) |
|---|---|---|---|---|
| 92 to 95 cents | 514 | 94.6% / 94.0% | +0.17 (−0.31 to +0.65) | −0.41 (−1.12 to +0.30) |
| 95 to 98 cents | 696 | 97.7% / 97.5% | +0.43 (+0.25 to +0.61) | +0.16 (−0.15 to +0.46) |
| 98 cents and up | 487 | 98.4% / 98.2% | +0.37 (+0.20 to +0.53) | +0.12 (−0.27 to +0.52) |

"Extra" means waiting at the bid minus buying the ask. In dollars, at 15 contracts:

| Band | Buy the ask | Waiting order, best case | Waiting order, worst case |
|---|---|---|---|
| 92 to 95 cents | $114 | $106 | $65 |
| 95 to 98 cents | $134 | $153 | $116 |
| 98 cents and up | −$17 | $9 | −$7 |

- 92 to 95 cents is the worst band for waiting. Even the best case makes less money there. Filled orders there
  win only 94% of the time, against 100% for the ones that never fill.
- 95 cents and up is where waiting looks best. In the best case it clearly beats the ask there. In the worst case
  it is a tie per dollar.

## 7. By group

| Group | Markets | Got any fill (best / worst case) | Extra cents of profit for every dollar bet, best case (range it is probably in) | Same, worst case (range it is probably in) |
|---|---|---|---|---|
| Crypto | 1,261 | 88.5% / 82.1% | +0.14 (−0.09 to +0.37) | −0.02 (−0.36 to +0.31) |
| Metals | 312 | 88.1% / 69.6% | +0.95 (+0.64 to +1.26) | +0.52 (−0.23 to +1.27) |
| Energy | 124 | 92.7% / 72.6% | +0.49 (+0.05 to +0.92) | −0.63 (−2.02 to +0.75) |

In dollars, at 15 contracts:

| Group | Buy the ask | Waiting order, best case | Waiting order, worst case |
|---|---|---|---|
| Crypto | $104 | $112 | $81 |
| Metals | $99 | $122 | $83 |
| Energy | $28 | $33 | $12 |

- Crypto, the bulk of the bot's bets, is close to a tie per dollar in both cases.
- Metals looks best. But metals has only 312 markets. The worst case fills just 70% of them there.
- Crypto includes only 29 BTC markets (one window in 5 was fetched).

## 8. At the bot's own bet sizes

Here each waiting order is for the same number of contracts the bot really bought. It covers the 1,405 markets the
bot bought. The taker side is the bot's real profit, with its real prices, sizes and fees.

| Way of buying | Profit | Compared with the bot |
|---|---|---|
| The bot, as it really traded | $212 | — |
| Waiting at the bid, best case | $235 | +$23 (+11%), range +$3 to +$43 |
| Waiting at the bid, worst case | $164 | −$48 (−23%), range −$73 to −$23 |

The bot made +1.13 cents of profit for every dollar bet on these markets. The range the true number is probably in
is −0.02 to +2.28. Its favourites won 97.7% of the time.

## 9. Markets the bot skipped

This is the sample of 292 server-era markets the bot did not buy, at 15 contracts each. For these, "buy the ask" is
pretend: the bot did not do it.

| Why the bot did not buy | Markets | Buy the ask | Waiting order, best case | Waiting order, worst case |
|---|---|---|---|---|
| A warning sign (wide spread or a late jump) | 155 | $23 | $36 | $20 |
| Nobody was selling at its price | 96 | −$7 | −$12 | −$13 |
| The bot was halted | 28 | −$13 | −$16 | −$19 |
| Its order was refused (an error) | 13 | $2 | $4 | $2 |

- The spread is the gap between the buy and sell price — what it costs to get in. A wide spread means a big
  saving for a waiting order. That is why warning-sign markets do better for it in the best case.
- "Nobody selling at its price" markets lost money every way. The waiting order would have filled in 79% to 85% of
  them, and done worse than the ask. These favourites won only 95.8% of the time.
- These are small samples. Read them as hints, not results.

## 10. Why the Oct 11 test said "clearly worse"

The Oct 11 test (`research/kalshi_15min/lab/maker.py`, REPORT.md section 3d) used the same order: wait at the
favourite's bid at minute 8. It found:

- The order filled in 35% to 45% of markets. Here it fills in 79% to 89%.
- Filled orders won 89% to 92%. Here they win 96.6% to 97.0%.
- Every version lost 20 to 50 cents per $10 bet, which is 2 to 5 cents for every dollar bet. Here the waiting
  order makes about the same as the ask (worst case) or a bit more (best case).

Why the difference:

- **Oct 11 could only see a fill when the price itself fell to our order.** It had only each minute's closing
  prices. A minute had to close with the ask down at our bid. That mostly happens when the favourite weakens. So it
  counted mostly the bad fills.
- **The trade history sees the sellers who hit the bid while the price stays put.** Most fills here come in the
  first few seconds, in markets where the price then holds. Those markets mostly win. Oct 11 missed them.
- Oct 11 also used an older period (July to October), a wider band (90 to 99.9 cents), and $10 bets. The 90 to 92
  cent favourites were the weakest group then. They are out of the band now.

Oct 11's own note said its fill rule missed quick dips that bounce back. So it said the real loss was "probably
smaller". This test confirms that, and by a lot.

## 11. Limits

- **The line at the bid is unknown.** This is the big one. The two cases are its two ends. The order-book recorder
  can measure how much was waiting at the bid at minute 8.
- **The worst case might be a little too gloomy.** It ignores sales at exactly our price once the line ahead
  cleared. Those would have filled us too.
- **Both cases assume our order was waiting from minute 8 exactly.** Orders from the bot's server land in about
  0.12 seconds. So this hardly matters.
- **History does not react to us.** A real waiting order could change what others do. At 15 contracts, against
  about 1,000 sold at our price in a typical market, the effect should be small.
- **Ten days, 45 losses.** That is why the profit ranges are wide. The difference ranges are tighter, because both
  ways lose on the same markets.
- **Sampled data.** BTC is one window in 5. The bot's buys are 73% of the server era. Its skips are 36%. The home-PC
  era is not in. The shuffled order means the sample should not lean toward any date.
- **No maker fee.** If Kalshi ever adds its maker fee to these series, the waiting order loses a little more.

## Files

- Code: `research/maker_shadow/past_trades.py`. Tests: `research/maker_shadow/tests/test_past_trades.py`
  (47 tests, all passing).
- Raw trade pages, gzipped: `research/maker_shadow/data/past_trades/pages/` (gitignored, 60 MB).
- Results: `research/maker_shadow/data/past_trades/summary.json` (all numbers above) and `scored.jsonl` (one line
  a market).
- To fetch more (it carries on where it stopped), then rescore:

```
cd research/maker_shadow
LEDGER_JSON=<the ledger dump> python past_trades.py fetch 60        # 60 minutes, priority order
LEDGER_JSON=<the ledger dump> python past_trades.py results         # results for any new skipped markets
LEDGER_JSON=<the ledger dump> python past_trades.py score
```
