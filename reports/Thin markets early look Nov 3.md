# Thin markets: second early look, 3 November 2026

**Interim, but the outcome is now close to settled.** Recording runs to 9
November, and the final call uses the same pass marks on all of it. Nothing was
changed because of this look. Pass marks: `research/thin_favourites/RECORDER_PREREG.md`.
Raw numbers: `research/thin_favourites/data/verdict-interim-2026-11-03.json`.
First look: `reports/Thin markets early look Oct 29.md`.

## The short version

- **There's enough data now:** 297 usable "No" favourite markets. The rules need
  100.
- **Getting in is cheap enough, and there's plenty of money on offer.** Those two
  pass marks pass, as on 29 October.
- **A bot still can't tell early which markets will stay quiet.** Only 58% do.
  The bar is 80%. Under the rules, that one failure shelves the idea.
- **It's very unlikely to flip by 9 November.** It's based on over 5,000 markets.
  Six more days can't move 58% to 80%.

## The three pass marks ("No" favourites)

"No" favourite means the likely side is "No", priced 80 to 90 cents an hour
before the market closed. "Quiet" (thin) means fewer than 18,643 contracts
traded over the market's whole life.

| Pass mark | Needed | 29 Oct | 3 Nov | Passes? |
|---|---|---|---|---|
| Extra cost to get in, typical market, over the last traded price | 3 cents or less | 2 cents | 2 cents | Yes |
| Money offered within a cent of the cheapest price, typical market | $20 or more | about $1,000 | about $780 | Yes |
| Markets quiet an hour before the end that stay quiet | 80% or more | 52% | 58% | No |

## Spotting quiet markets early, by sport

This counts only markets where the recorder was running at the key moment.

| Sport | Markets | Share that stayed quiet | Clears the 80% bar? |
|---|---|---|---|
| NHL | 228 | 88% | Yes |
| College basketball | 157 | 80% | Just, from only a week |
| NBA | 2,346 | 74% | No, close |
| NFL | 126 | 70% | No |
| Tennis | 1,925 | 35% | No, far off |

Tennis is the big problem, and it's a large share of the markets. Tennis trading
piles up near the end of a match.

## Cost and money, in more detail

- **Extra cost to get in:** a quarter of markets cost nothing extra. Half cost 2
  cents or less. A quarter cost 5 cents or more. NBA and NHL were cheapest, at
  about 1 cent typically.
- **Money on offer:** a quarter of markets had under $175 within a cent of the
  best price, and a quarter had over $2,500.
- **Every market had something on offer.**

## Wins, a sanity check only, not a pass mark

- The 297 "No" favourites won 283 times, about 95%, at an average price of 85
  cents. They come from 174 games, and 12 of those games had a loss.
- At an 85-cent price, about 15% should lose. That would be roughly 26 games, so
  this looks better than the price.
- **But it uses hindsight.** These markets were picked because they stayed quiet
  to the end, which a bot can't know in advance. That is exactly what pass mark
  3 tests, and it failed.
- The "Yes" favourites won about 94% at 85 cents, from 149 games.

## What it means

The idea as written fails: a live bot can't pick out the markets that made the
past profit. Two narrower ideas are left, and neither has been tested yet:

1. **NHL only, and maybe NBA.** Spotting quiet markets early works there, or
   nearly.
2. **"Quiet so far" as the rule.** A bot buys when the market looks quiet an hour
   before the end, then lives with the ones that get busy. Whether that still
   pays is the open question.

Either would be a **new test**. It would need its own pass marks written down
first, and it would be scored only on markets that close after that. The data
used here can't fairly test an idea it suggested.

## Side facts

- Kalshi's listed "game time" is roughly the expected end, not the start. NBA
  markets closed about 25 minutes before it, and tennis about 2.7 hours before it.
- The recorder kept to its schedule, typically. At worst it fell about 10 times
  behind, around restarts.
