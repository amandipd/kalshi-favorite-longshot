# Last-minute favourites: not a pass yet, but pointing the right way

Step 1 of the settle-average test, 26 October 2026. Nothing was built into the bot. Nothing was traded.
The script is `research/settle_average/last_minute.py`. The pass bar was written down first, in
`research/settle_average/PREREG.md`. The full output is in `research/settle_average/report.txt`.

## The answer

- **Step 1 does not pass the bar set before the results.** None of the 4 main tests was far enough from luck.
- All 4 main tests made a small profit after the fee: +0.5 to +1.9 cents per contract. Two of them came close to
  the bar but missed. The other two showed almost nothing.
- **The bigger picture fits the idea.** 90 seconds before the close, the averaging has not started yet.
  There, favourites priced 80 to 98 cents *lost* 1.6 cents per contract after the fee. That is unlikely to be luck
  (t = −2.7; a t-stat says how far from luck a result is, and about 2 is the usual bar).
- Inside the averaging minute, the same favourites *made* 2.0 cents per contract after the fee. That is far from
  luck (t = 3.8). It held on the older and newer halves of the data. It held without its best day.
- **But I found that second number after looking at the results.** So it is a lead, not proof. It needs a fresh test on
  data it has never seen. Older data exists back to December 2025, so that test is cheap.
- The switch from losing to winning happens just as the averaging minute starts. That is what the idea predicts.
  A plain "late favourites are cheap" effect would not switch on at exactly that point.

## What I tested

- **Markets.** Every settled 15-minute bitcoin and ether market from 1 September to 25 October 2026. That is 10,432
  markets over 55 days.
- **Trades.** Kalshi's public record of every trade in each market's last 100 seconds. That includes 6 million
  favourite buys in the last minute alone.
- **Only real prices.** Each trade says which side the buyer took. I used only prices that a buyer of the favourite
  really paid. So the cost of getting in (the spread, the gap between the buy and sell price) is already in the price.
- **One bet per market at each checkpoint.** At 90, 60, 45, 30, 20, 10 and 5 seconds before the close, the bet is
  the last favourite buy in the 10 seconds before that moment. No fresh price means no bet.
- **Profit** is per contract, after Kalshi's taker fee (its charge for trading, biggest near 50c).
- **Clustered on the window.** Bitcoin and ether bets in the same 15 minutes move together, so they count as one.

## The 4 main tests, picked before the results

| Test | Bets | Won, against price paid | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|---|
| 30 s left, favourites at 90-95c | 198 | won 93.4%, paid 92.4c | +0.5 cents | not far at all (0.3) |
| 30 s left, favourites at 95-98c | 293 | won 98.0%, paid 96.8c | +1.0 cents | some way, short of the bar (1.2) |
| 10 s left, favourites at 90-95c | 43 | won 95.3%, paid 93.0c | +1.9 cents | not far at all (0.6) |
| 10 s left, favourites at 95-98c | 73 | won 98.6%, paid 96.7c | +1.8 cents | some way, short of the bar (1.3) |

By the pre-set bar this is "in between": positive, but not proven. Going on is a separate decision.

The samples are small for a reason. By 30 seconds before the close, 87% of markets are already pinned at 99c
or more. A pinned price already equals the answer. Only about 9 markets a day still sit at 90 to 98 cents with
30 seconds left, and about 2 a day with 10 seconds left.

## The pattern by time left (favourites at 80-98c, found after looking)

| Time before the close | Bets | Won, against price paid | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|---|
| 90 s (averaging not started) | 2,663 | won 90.8%, paid 91.8c | −1.6 cents | unlikely to be luck (−2.7) |
| 60 s (averaging starts) | 1,806 | won 92.6%, paid 92.0c | +0.2 cents | not far at all (0.3) |
| 45 s | 1,205 | won 94.7%, paid 91.9c | +2.3 cents | far from luck (3.6) |
| 30 s | 674 | won 93.3%, paid 92.3c | +0.5 cents | not far at all (0.6) |
| 20 s | 337 | won 96.1%, paid 92.2c | +3.4 cents | far from luck (3.3) |
| 10 s | 149 | won 96.0%, paid 92.9c | +2.6 cents | some way, short of the bar (1.7) |

The rows share markets, so they are not separate proofs. The jump between 45, 30 and 20 seconds is probably noise.

Pooling 45 to 10 seconds left gives the found pattern: **+2.0 cents of profit per contract, about 2.2 cents for
every dollar bet** (t = 3.8, clustered on the window).

| Check on the found pattern | Bets | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|
| Older half of the days (train) | 1,284 | +2.0 cents | far from luck (2.8) |
| Newer half of the days (test) | 1,081 | +2.0 cents | far from luck (2.5) |
| Bitcoin only | 1,309 | +2.6 cents | far from luck (4.1) |
| Ether only | 1,056 | +1.3 cents | short of the bar (1.4) |
| Without its best day (leave-one-out) | 2,316 | +1.9 cents | far from luck (3.5) |

A train/test split builds the rule on older data and scores it once on newer data. Here both halves were looked at
together, so this is a check on consistency, not a true held-out test. Leave-one-out drops the biggest contributor
and checks that the result survives.

## The near-certain bets (98c and up)

- Favourites at 98 to 99 cents, 20 seconds left: 185 bets, **no losses**. At fair prices about 3 would have lost.
  The chance of none at fair prices is about 7%.
- Favourites at 99c and up, 10 seconds left: 2,171 bets, no losses. About 4 would have lost at fair prices. The
  chance of none is about 3%.
- With no losses, the t-stat is meaningless (the report prints t = 40 to 67). Ignore those numbers.
- The profit is tiny: about 0.15 cents for every dollar bet at 99c and up. One loss wipes out about 650 wins.
  Breaking even needs fewer than 1 loss in about 650 bets. These samples can't tell that apart from fair.

## How much money trades there

- In the last 30 to 10 seconds, about **$22 million** of favourites at 90 to 98 cents traded over the 55 days. That is
  roughly $400,000 a day. Size is not the problem.
- Weighted by contracts, those buys made +2.6 cents per contract at 90-95c (t = 3.3) and +1.2 cents at 95-98c (t = 2.3).
- So the big buyers in that window are already making money. Someone is very likely doing this already. That is
  adverse selection: getting picked off by someone who knows more than you. We would be racing them.

## What this does not answer

1. **Would the price still be there a second later?** Every price here was paid by someone else. We would be the next
   buyer, after seeing their trade. Only live order books can answer this (step 2).
2. **The found pattern was found after looking.** It needs a fresh test on unseen data.
3. **Ether is weaker** than bitcoin in every view.
4. **Before the averaging minute, favourites look overpriced** (−1.6 cents at 90 seconds). The live bot buys around
   7 minutes before the close, not 90 seconds, so this says nothing direct about the bot. It is worth knowing.

## Next step options

- **Fresh test on older data (recommended).** Same script, December 2025 to August 2026, data this test never saw.
  The rule is fixed now: favourites at 80 to 98 cents, 45 to 10 seconds before the close. The pass bar is the same
  as before. No new feeds and no new code beyond pointing at the older dates. Roughly half a day of gentle
  downloading, left running in the background.
- **Then step 2**, only if that passes: record live order books in the last 2 minutes, and rebuild the official index,
  to see if a bot arriving a second late still gets the price.
- Nothing goes live before the 6-week test ends on 27 November 2026.
