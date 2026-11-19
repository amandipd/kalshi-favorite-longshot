# Last-minute favourites: the fresh test fails, and the idea closes

This is the fresh test of the settle-average idea, run on 29 October 2026. Nothing was built into the bot and nothing
was traded. The pass bar was written on 27 October, before any of this data was downloaded. It is in
`research/settle_average/PREREG_FRESH.md`. The full output is in `research/settle_average/fresh_report.txt`.

## The answer

- **It fails the bar that was set beforehand.** Bought inside the last minute, favourites priced 80 to 98 cents
  *lost* 1.5 cents per contract after the fee. That is about 1.6 cents lost for every dollar bet.
- The loss is not luck. It is far from luck in the wrong direction (t = −4.5). A t-stat says how far from luck a
  result is. About 2 is the usual bar, and this is past it on the losing side.
- The bar says a fail closes the idea. **Step 2 (recording live order books) should not go ahead.**
- **The other half of the prediction failed too.** Ninety seconds before the close, before the averaging starts,
  step 1 found favourites losing 1.6 cents. Here they came out about even (−0.05 cents, which is nothing).
- So the +2.0 cents that step 1 found in September and October did not show up in the nine months before them.
  It was most likely a lucky stretch, or a short-lived effect that we cannot count on.

## What was tested

- **Markets.** Every settled 15-minute bitcoin and ether market from 10 December 2025 (the first one Kalshi listed)
  to 31 August 2026. That is 49,181 markets over 265 days. None of them were used in step 1.
- **The rule, fixed before the download.** At 45, 30, 20 and 10 seconds before the close, the bet is the last price
  a buyer of the favourite really paid in the 10 seconds before that moment. Only favourites at 80c up to just under
  98c count. Profit is per contract, after Kalshi's taker fee (its charge for trading, biggest near 50c).
- **Clustered on the window.** Bitcoin and ether bets in the same 15 minutes tend to move together, so they count
  as one when judging luck.
- That gave **10,240 bets**, about four times step 1's 2,365.

## The pass bar, check by check

| Check | Bets | Profit per contract, after fee | How far from luck (t; about 2 is the bar) | Passed? |
|---|---|---|---|---|
| Whole period: needs a profit, past the bar | 10,240 | lost 1.5 cents | far from luck, losing side (−4.5) | no |
| Older half of the days: needs a profit | 4,797 | lost 3.6 cents | far from luck, losing side (−6.9) | no |
| Newer half of the days: needs a profit | 5,443 | made 0.3 cents | not far at all (0.8) | yes, only a profit was needed |
| Without the single best day (9 July): needs a profit (leave-one-out) | 10,189 | lost 1.5 cents | far from luck, losing side (−4.6) | no |

Leave-one-out means dropping the biggest contributor and checking that the result survives.
A fail needs only a loss or a t under 1, and the whole period has both.

## Bitcoin and ether apart

| Coin | Bets | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|
| Bitcoin | 5,696 | lost 0.7 cents | some way, short of the bar (−1.7) |
| Ether | 4,544 | lost 2.4 cents | far from luck, losing side (−4.8) |

As in step 1, ether is the weaker of the two. But this time bitcoin loses as well.

## Month by month

| Month | Bets | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|
| December 2025 | 273 | lost 5.4 cents | far from luck, losing side (−2.4) |
| January 2026 | 1,201 | lost 7.0 cents | far from luck, losing side (−6.3) |
| February | 1,256 | lost 4.5 cents | far from luck, losing side (−4.1) |
| March | 1,158 | lost 0.3 cents | not far at all (−0.4) |
| April | 1,424 | lost 1.2 cents | some way, short of the bar (−1.4) |
| May | 1,382 | made 0.4 cents | not far at all (0.5) |
| June | 1,113 | made 1.0 cent | some way, short of the bar (1.1) |
| July | 1,134 | made 1.5 cents | just short of the bar (2.0) |
| August | 1,299 | lost 0.8 cents | not far at all (−0.9) |
| *Step 1: Sep to Oct 25* | *2,365* | *made 2.0 cents* | *far from luck (3.8)* |

- **December to February were bad.** Favourites won only 86 to 88% of the time when they cost about 92.5 cents.
  Those markets were new and thinly traded.
- **Leaving out those three months does not rescue the rule.** From March to August it comes out at zero
  (+0.04 cents per contract over 7,510 bets, t = 0.1, nothing at all).
- **May to August was slightly positive**: +0.5 cents per contract over 4,928 bets. That is short of the bar
  (t = 1.1), and August itself lost.
- You could read the months as an edge that only began around May. But that story was picked after looking at the
  results, which is exactly the trap this fresh test exists to avoid. Even on that reading, May to August made about
  a quarter of what step 1 found.

## By price range (reported only)

| Favourites priced | Bets | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|
| 80 to 90 cents | 2,506 | lost 2.3 cents | far from luck, losing side (−2.9) |
| 90 to 95 cents | 3,200 | lost 2.4 cents | far from luck, losing side (−4.3) |
| 95 to 98 cents | 4,534 | lost 0.4 cents | not far at all (−1.2) |

No price range is profitable.

## Step 1's four main tests, on the new data (reported only)

| Test | Bets | Profit per contract, after fee | How far from luck (t; about 2 is the bar) |
|---|---|---|---|
| 30 s left, favourites at 90-95c | 877 | lost 1.2 cents | some way, short of the bar (−1.3) |
| 30 s left, favourites at 95-98c | 1,244 | lost 0.1 cents | not far at all (−0.2) |
| 10 s left, favourites at 90-95c | 327 | lost 4.5 cents | far from luck, losing side (−2.6) |
| 10 s left, favourites at 95-98c | 495 | lost 0.1 cents | not far at all (−0.1) |

In step 1 all four were small profits. Here all four are losses.

## Checks on the data

- **Every day saved.** All 265 days from the first market (10 December 2025) to 31 August 2026 were downloaded.
  Some days have fewer markets, for example the weekly Thursday maintenance pause.
- **Close times are right.** Each market's ticker contains its closing time. All 49,181 match the time used here.
- **Results are Kalshi's own.** The yes/no outcome comes from Kalshi's result field, saved on 11 October. It agrees
  with the final index value against the strike for all but 4 markets. Those 4 are on 13 April and have a broken
  strike in Kalshi's data. 4 markets out of 49,181 cannot move the answer.
- **The market list was checked before use.** It matched Kalshi's live listing on all 13,671 markets the two had in
  common.
- Favourites won 91.4% of the time at an average price of 92.4 cents. That is close to fair, which is what clean data
  should look like. Broken results would show up as a win rate far from the price.

## What this means

- **The settle-average idea closes here, as the bar said it would.** No step 2, and no live order book recorder for it.
- **Nothing changes in the live bot.** The bot buys around 7 minutes before the close, not in the last minute, so this
  test says nothing about its edge either way.
- **The lesson.** Step 1 looked strong: far from luck, and it held on both halves and without its best day. It still
  did not survive data it had never seen. A pattern found after looking can pass every check on its own data and
  still be luck. That is why the fresh test was worth the download.
- **One thing worth noticing, not acting on.** The rule did better from May onward, and best in September and
  October. If someone wanted to come back to this, the only fair test would be on data from after 25 October that
  nobody has looked at yet, with the bar written first. I would not spend time on it before the 6-week test ends on
  27 November 2026.

## Files

- `research/settle_average/PREREG_FRESH.md`: the pass bar, written 27 October before the download.
- `research/settle_average/last_minute.py`: the script (`python last_minute.py fresh`).
- `research/settle_average/fresh_report.txt` and `fresh.json`: the full output.
- `research/settle_average/tape_old/`: the downloaded trades, 116 MB, kept out of git.
