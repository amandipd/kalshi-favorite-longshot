# Opening price of a new market

## Question

The main study prices every market at its last trade an hour before close. This study looks at the other end of a
market's life: at the first trade after a market opens, before its order book fills in, are favourites priced 80
to 90 cents underpriced? An earlier look had hinted so in thin markets, but that band was picked after seeing the
data, so it needed a fresh test.

The rule, the sample and the pass bar were written down before any opening price was fetched: `PREREG.md`.

## How to run it

From the repository root, after the main study's raw data is in place (`python -m kalshi_calibration.ingest.kalshi`):

    python -m kalshi_calibration.ingest.open_trades      # each sampled market's first trade -> data/raw_trades/kalshi/OPENFIRST/
    python research/opening_price/analyze_opening.py     # retention and dropouts first, then the train half only

`analyze_opening.py` reports how many markets have a usable opening trade before it reports any edge, and it scores
only the train half. The pre-registration allows the test half to be read once, and only if the train half passes.

## What it found

It fails, in the opposite direction (25 Oct 2026, 30,000 markets drawn at random). At the first trade, favourites
are overpriced in every band that could be read. After Kalshi's taker fee, buying them lost about 3.6 cents per
contract at 60 to 80 cents, 4.2 cents at 80 to 90 cents, 11.2 cents at 90 to 95 cents and 7.0 cents at 95 cents and
up, each far from luck (t between 2.3 and 5.7 in size). The train half failed, so the test half was never scored and
the idea is closed. The full write-up is in `reports/` ("Opening price result Oct 25").
