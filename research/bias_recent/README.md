# Has the favourite bias faded?

## Question

From Oct 20, 2026 the live bot lost about as often as prices predicted. Was that the bot's own bad stretch (how it
bought, the prices it paid), or had favourites stopped beating their prices across all of Kalshi's 15-minute
markets? Scoring the bot's rule on every market, not just the bot's own bets, separates the two. The reading
("faded", "still there" or unclear) was fixed in `PREREG.md` before any data was downloaded.

## How to run it

From this folder. It needs the strategy lab's past data, `../kalshi_15min/lab/markets.npz` (built by
`../kalshi_15min/lab/build_markets.py` from the 15-minute history; see `../kalshi_15min/README.md`).

    python fetch_recent.py                 # every market in the bot's 16 series, Oct 9 to 29 2026 -> recent_minutes.csv
    python score.py                        # the pre-set reading and the splits -> score.json
    python score.py live_bets.json         # adds the check against the bot's own bets
    python bad_days.py live_bets.json      # were the last two weeks matched by the rule, and were past stretches as bad?

`live_bets.json` is a dump of the live bot's settled bets from its private ledger, so the last two lines can't be
run from this repository. `score.json` keeps the result.

## What it found

The bias had not faded. Over Oct 9 to 29 the bot's rule, applied to every market, made about 0.81 cents of profit
for every dollar bet (range 0.12 to 1.50), in line with the long-run past (0.79). All of it came in the first 11
days; from Oct 20 the whole market was flat, not just the bot. The live bot's own bets did almost exactly what the
rule did on the same prices, so the slump was the market's, not the bot's execution. A later check (`bad_days.py`)
found the backtest reproduces the live slump, and that no 15-day stretch since Jul 18 had been as bad. Write-ups:
`reports/` ("Has the favourite bias faded Oct 30" and "Last two weeks vs the backtest Nov 3").
