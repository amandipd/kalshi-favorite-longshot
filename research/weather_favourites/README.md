# Weather favourites

## Question

Does the favourite rule (buy the likely side at 90 cents or more, hold to settlement) carry over to Kalshi's
weather markets? Late in the climate day, do favourites on daily rain (`KXRAIN`) and the 24 daily high temperature
series win more often than their price says, after the taker fee and the spread? The rule, the checkpoints (6 hours
before the close, and 2 hours as a second look), the test data and the pass bar were fixed in `PREREG.md` before
any new price was fetched. Markets already scored in an earlier run never count.

A follow-up, `losses_check.py`, asked whether the daily-high favourites that lost at 6 PM had lost to a stale price:
had the settling temperature already been published before the checkpoint?

## How to run it

From this folder. Kalshi's public API (no key) and the Iowa Environmental Mesonet copies of the National Weather
Service climate reports; everything goes to `data/`, which is not committed.

    python fetch.py list                   # every settled market in the two families
    python fetch.py candles                # hourly bid and ask over each market's last 25 hours (resumable)
    python fetch.py cli                    # the daily climate reports the markets settle on
    python score.py                        # the frozen rule, scored once
    python check.py                        # Kalshi's settled values against the climate reports
    python losses_check.py                 # when each losing day's official high became public

Tests (no network): `python -m pytest -q -p no:cacheprovider research/weather_favourites/tests` from the repository
root.

## What it found

Daily highs fail clearly: favourites lost far more often than their price said, and the rule lost about 2.5 cents
for every dollar bet, with the whole likely range below zero. Daily rain had only 110 qualifying bets on fresh data
against a bar of 1,000 (about 8 months away at 4 bets a day), so it is "not enough data", and even a pass would earn
very little. The stale-price idea also died: on none of the 33 losing city-days was the settling high already public
at 6 PM, and 25 of the 33 were real late warming, mostly winter warm fronts at night. Write-ups: `reports/`
("Weather favourites test Oct 26" and "Kalshi weather forecast model edge").
