# Polymarket US 5-minute markets

## Question

Polymarket US launched 5-minute up or down markets on BTC, ETH, SOL and XRP on Oct 22, 2026. Can the Kalshi
15-minute rule (buy the favourite late in the window, skipping the two warning signs, hold to the close) be copied
there and make money after Polymarket's fees? The rule, the data and the pass bar were fixed in `PREREG.md` before
any result was read. A second pre-registration, `PREREG_FORWARD.md`, fixes a forward paper test that records only
what a bot could see in real time.

## How to run it

From this folder. Public data only (no account, no orders); outputs go next to the scripts.

    python fetch.py                        # every 5-minute market since launch, with result and price history -> markets.jsonl
    python score.py                        # the pre-registered rule and its variants -> score.json
    python settle.py                       # do these markets settle on the same numbers as Kalshi's 15-minute ones? -> settle.json
    python live.py 60                      # watch live windows for an hour -> live.jsonl
    python live_report.py                  # when each history point appears and stops changing -> live_report.json
    python peek.py                         # does the backtest's minute-4 price peek past 4:00? -> peek.json
    python forward.py record               # the forward paper test (runs up to 7 days)
    python forward_report.py               # scores it once it is done

`record.py` and `calibrate.py` were a quick check of how far a price-history point lags the order book.
`keep_running.py` is a watchdog that restarted the forward recorder when a Windows machine woke from sleep.

Tests (no network): `python -m pytest -q -p no:cacheprovider research/polymarket_5min/tests` from the repository
root.

## What it found

The settlement check passed: at every 15-minute mark from launch, the Polymarket window's close value matched
Kalshi's final value for the same coin (`settle.json`), so the two venues pay on the same index average.

A straight copy of the rule (buy at minute 3 of 5) is unclear: it made about 0.19 cents of profit for every dollar
bet after fees, with a range of minus 0.41 to 0.79, too close to zero and below the 0.5 cent bar. Without the two
filters the same favourites lost about 3 cents per dollar. Buying a minute later (minute 4 of 5) passed the
pre-set train and test split (0.95 cents per dollar on Nov 1 to 11, range 0.76 to 1.15), but that number is not
trusted: the stored minute-4 price can be up to about 8 seconds late, inside the final minute that decides the
result, and in 12 of 59 live checks a bot buying at exactly 4:00 would have bet differently or paid a different
price (`peek.json`). The forward paper test was built to settle this; its result is not recorded here. Write-ups:
`reports/` ("Polymarket 5-minute markets Nov 8" and "Polymarket 5-minute backtest Nov 10").
