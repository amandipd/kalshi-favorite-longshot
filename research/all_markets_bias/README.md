# All-markets favourite map

## Question

The earlier calibration sample covered the top 20 series in four categories and was mostly sports. Kalshi lists
over 15,000 series in 20 categories. Across all of them, where are heavy favourites underpriced, so that buying them
at a price a real buyer paid, and holding to settlement, makes money after Kalshi's taker fee? And does that hold
at several moments before the close (1 hour to 30 days), not just one?

`PLAN.md` explains the design in words. `PREREG.md` fixes the universe, the random sample, the checkpoints, the fee,
the clustered ranges and the pass bar (train half picks candidates, test half is read once) before any trade or
outcome was pulled.

## How to run it

From this folder. Everything reads Kalshi's public API (no key) and writes to `data/`, which is not committed. Each
step skips what is already on disk.

    python fetch.py series                 # every series, its category and fee multiplier
    python fetch.py list-live              # settled markets after Kalshi's archive line, a day at a time
    python fetch.py list-hist              # archived markets, per series
    python fetch.py sample                 # the pre-registered random sample (never reads a result)
    python fetch.py trades --stage 1       # trades for the 1-hour and midpoint checkpoints; --stage 2 for the rest
    python fetch.py spread                 # one sweep of today's best bid and ask
    python score.py train --labels half,1h # train cells and candidates
    python score.py test --labels half,1h  # the test half, read once per label set
    python score.py describe               # calibration, Yes vs No, retention, money and spread

The full pull was estimated at one to two days at 2 to 4 requests a second.

Tests (no network): `python -m pytest -q -p no:cacheprovider research/all_markets_bias/tests` from the repository
root.

## What it found

No result is recorded in this repository. The pre-registration, the pull and the scoring code (with 108 tests) are
here, so the study can be run as written.
