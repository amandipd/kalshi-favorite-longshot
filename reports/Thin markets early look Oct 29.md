# Thin markets: early look, 29 October 2026

**This is not the verdict.** Recording runs to 9 November, and the final call
uses the same pass marks on all of it. Nothing was changed because of this look.
Pass marks: `research/thin_favourites/RECORDER_PREREG.md`. Raw numbers:
`research/thin_favourites/data/verdict-interim-2026-10-29.json`.

## The short version

- **Getting in looks cheap enough, and there's plenty of money on offer.** Two of
  the three pass marks pass so far.
- **The problem is spotting a quiet market in advance.** An hour before the end,
  about half the markets that look quiet go on to get busy. That fails the third
  pass mark, mostly because of tennis.
- **Not enough data for a verdict yet:** 94 usable "No" favourite markets, and
  the rules need 100. That should be reached in a day or so.

## The three pass marks so far ("No" favourites)

"No" favourite means the likely side is "No", priced 80 to 90 cents an hour
before the market closed. "Quiet" (thin) means the market traded fewer than
18,643 contracts over its whole life.

| Pass mark | Needed | So far | Passes? |
|---|---|---|---|
| Extra cost to get in, typical market, over the last traded price | 3 cents or less | 2 cents | Yes |
| Money offered within a cent of the cheapest price, typical market | $20 or more | about $1,000 | Yes |
| Markets that look quiet an hour before the end and stay quiet | 80% or more | 52% | No |

## What sits behind those numbers

**Cost to get in.** The typical market cost 2 cents more than the last traded
price. But it varies a lot. A quarter cost nothing extra. Another quarter cost
6 cents or more extra, which would eat most of the past profit on those bets.
Every market had at least something on offer.

**Money on offer.** Much deeper than feared. A quarter of markets had under $180
within a cent of the best price, and a quarter had over $2,500. Size isn't the
problem.

**Spotting quiet markets early.** This is the weak point. It differs by sport:

- Tennis: only 36% of early-quiet markets stayed quiet. Tennis matches draw
  most of their trading near the end.
- NBA: 74% stayed quiet, just under the 80% bar.
- NHL: 81%, but from only 48 markets.

The recorder's gaps don't explain it. Keeping only markets where the
recorder was running at the key moment gives 54%, about the same.

**Wins, a sanity check only.** The 94 "No" favourites won 92 times, at an
average price of 85 cents. But they come from just 61 games, and bets on the
same game move together. Two weeks is far too short to judge profit. This
number is not part of the test.

## Side facts

- **Kalshi's "game time" isn't the start time.** For NBA it is roughly the
  expected end: markets closed about 25 minutes before it. For tennis it is
  unreliable: markets closed about 3 hours before it.
- **"Yes" favourites:** 57 markets. They cost 1 cent extra to get in, typically,
  with about $800 on offer.
- **The recorder kept up.** It ran about on schedule, typically. At worst it fell
  10 times behind, around restarts.

## What it may mean (not acted on)

The past result was measured on markets known to be quiet over their whole
life. A live bot can't know that. It only sees how much has traded so far. If
tennis keeps failing the third mark, the idea may only work for NBA and NHL. Or
it may need a rule built on "quiet so far", which would be a new test with its
own pass marks, set before looking.
