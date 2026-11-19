# Why the $1,000 simulation only made money near the end, 5–6 Nov 2026

The dashboard's simulated account starts with $1,000 on 10 Dec 2025. On 5 Nov it showed $2,505, with most of the gain
in October. That October jump turned out to be a gap in our data, fixed on 6 Nov. With the gap fixed, the account ends
at **$1,651.22**, and October is an ordinary month.

## Short answer

1. **For the first seven and a half months the rule made about nothing.** The account went from $1,000 on 10 Dec to
   $998 on 31 Jul. Good months and bad months cancelled out.
2. **There were far fewer markets to bet on early on.** In December Kalshi listed 2 of the markets the bot trades. By
   September it listed 20. More markets means more bets.
3. **Metals and energy only arrived on 3 Aug, and they made most of the profit.** Gold, silver, natural gas and the
   rest earned $466 of the $651 total.
4. **The October jump was not real.** Our record of real trades, which caps how much each order could really buy,
   stopped at 11 Oct. After that the backtest let every order fill in full. Fixed on 6 Nov: with the real record, the
   account peaked at $2,038 on 20 Oct and lost about $240 from 12 Oct to 5 Nov.

## What the fix changed

| Account (started 10 Dec 2025) | Before the fix, 5 Nov | After the fix, 6 Nov | Highest point after the fix |
|---|---|---|---|
| $1,000 (the dashboard's simulation) | $2,505 | $1,651 | $2,038 on 20 Oct |
| $2,000 | $4,338 | $2,755 | $3,446 on 20 Oct |
| $10,000 | $16,015 | $10,300 | $12,300 on 20 Oct |

The deepest fall (the worst drop from a peak) stayed at about a quarter of the account in every one of them.

The $10,000 account is worth a note. Bigger orders are the ones the market can't fill, so it ends only 3% up. More
money does not mean more profit here; past a small account, the extra size simply does not get filled.

My rough estimate on 5 Nov was $2,140. The real record was harsher than that guess: more orders got nothing at all, and
the October bets that really would have filled earned less (0.33 cents of profit per dollar bet, not 0.71).

## 1. Seven months of breaking even

The rule buys favourites (the likely side) priced 92 to 99.9 cents. The edge (profit per dollar bet) is small. Over
December to July it was close to zero.

| Month | Account at the end | Profit that month | Bets | Cents of profit per dollar bet |
|---|---|---|---|---|
| Dec 2025 | $1,006 | +$6 | 28 | +3.9 (too few bets to mean much) |
| Jan 2026 | $978 | −$29 | 349 | −0.85 |
| Feb | $1,034 | +$57 | 858 | +0.65 |
| Mar | $1,009 | −$25 | 1,556 | −0.16 |
| Apr | $1,173 | +$165 | 2,049 | +0.86 |
| May | $1,084 | −$89 | 1,895 | −0.49 |
| Jun | $1,169 | +$85 | 2,231 | +0.34 |
| Jul | $998 | −$171 | 2,957 | −0.55 |
| Aug | $1,201 | +$203 | 3,559 | +0.50 |
| Sep | $1,544 | +$343 | 4,042 | +0.60 |
| Oct | $1,807 | +$263 | 3,945 | +0.33 |
| Nov (to the 5th) | $1,651 | −$155 | 467 | −1.59 |

August to October made money. Before August, months took turns. Within October, the account rose to 20 Oct and then
gave most of it back.

## 2. More markets, so more bets

The bot only bets when a market is open. Kalshi added these markets one at a time.

| Market | First bet the simulation could make |
|---|---|
| Bitcoin, Ether | 20 and 23 Dec 2025 |
| Solana | 15 Jan |
| XRP | 11 Feb |
| Dogecoin, BNB, Hyperliquid | 19 Mar |
| NEAR, Zcash | 30 Jun and 1 Jul |
| Oil (WTI), silver, gold | 3 Aug |
| Natural gas, copper | 28 Aug |
| Platinum, palladium | 18 and 21 Sep |

In December the simulation placed one bet in about every 50 windows (a window is one 15-minute market round). By
autumn it placed one or two in every window. The same small edge on many more bets adds up to more dollars.

## 3. Metals and energy carried the late months

| Kind of market | Bets | Money staked | Profit | Cents of profit per dollar bet |
|---|---|---|---|---|
| Crypto (Dec on) | 20,657 | $256,289 | +$185 | +0.07 |
| Metals (Aug on) | 2,195 | $33,858 | +$265 | +0.78 |
| Energy (Aug on) | 1,084 | $18,027 | +$201 | +1.12 |

Crypto, ten months of it, earned almost nothing: 0.07 cents for every dollar bet. Metals and energy earned about ten
times more per dollar, and they only existed for the last three months. That is most of why the profit bunches up at
the end.

The account also compounds. Each bet is 1.5% of the account, so once it has grown, every bet is bigger.

## 4. The data gap, and the fix

The simulation caps each order by Kalshi's public record of trades. If only 10 contracts really traded at our price
just after the bot would have ordered, the order gets 10, not the 40 it asked for. This stops the backtest from
imagining depth (how much money you can trade before moving the price) that was never there.

That record (`liquidity.json`) was built on 11 Oct and covered markets up to that day. The price data was refreshed on
5 Nov, but the trade record was not. For a market with no record, the backtest's rule is to fill the order in full.

| Month | Before the fix: share of orders with a trade record | Before: share of the asked amount that filled | After the fix: share that filled |
|---|---|---|---|
| Sep | 100% | 44% | 44% |
| Oct | 37% | 85% | 47% |
| Nov | 0% | 100% | 48% |

**The fix, 6 Nov.** Fetched Kalshi's trades for the 6,452 markets the rule bet on from 12 Oct to 5 Nov, added them to
the saved record (`data/liquidity_tape.jsonl`, outside the repo), rebuilt `liquidity.json` (now 43,040 markets, 19 Dec
to 5 Nov; the 36,588 older entries came out identical), and reran `strategies_backtest.py`. Its own checks passed, and
the dashboard picked up the new `strategies.json` on the server without a restart.

The research tests: 902 pass and 8 fail, and the same 8 fail with the old data put back, so the fix did not cause
them. Each passes when its file runs alone, which points to tests leaking state into one another.

## How these numbers were made

`why_late.py` and `why_late_whatif.py`, one-off scripts not in the repo, rerun the dashboard's own account (`mine4liq1k`, live
fills, from 10 Dec) with counters added. Both reruns matched the dashboard to the cent: $2,505.13 before the fix and
$1,651.22 after.
