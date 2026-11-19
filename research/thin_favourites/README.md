# Thin favourites

## Question

In the main study's sample, thin (little-traded) sports markets whose favourite was priced 80 to 90 cents an hour
before the close looked underpriced, most of all when the favourite was the "No" side (about 8.1 cents per contract
on prices a No buyer really paid). Historical data shows trades, not order books, so it can't say whether a bot
could actually get in at those prices. This study recorded the live order books of thin sports markets for about
two weeks to find out.

`side_split.py` and `price_age.py` are the desk checks that led here (Yes against No favourites, and how stale the
hour-before price was). `RECORDER_PLAN.md` describes the recorder; `RECORDER_PREREG.md` fixes three pass marks
before any data, all of which had to pass on No favourites:

1. Cost to get in: the median extra cost over the checkpoint price is 3 cents or less.
2. Money on offer: the median dollars within a cent of the cheapest offer is $20 or more.
3. Spotting thin early: at least 80% of markets that look thin an hour before the close stay thin.

## How to run it

`side_split.py` and `price_age.py` run from the repository root on the main study's processed data
(`data/processed/contracts.parquet` and `data/raw_trades/kalshi/T1h/`). The recorder and the verdict run from this
folder, read only public data (no key) and write to `data/`, which is not committed:

    python thin_books.py record            # two weeks of order books; record 3 for three days
    python thin_report.py                  # the verdict against the pass marks

`keep_running.py` is a watchdog that restarted the recorder when a Windows machine woke from sleep.

Tests (no network): `python -m pytest -q -p no:cacheprovider research/thin_favourites/tests` from the repository
root.

## What it found

Shelved. The recorder ran from Oct 26 to Nov 9, 2026. By the second interim look (Nov 3, 297 usable No-favourite
markets against the 100 needed) the first two marks passed comfortably: getting in cost about 2 cents over the
checkpoint price, and several hundred dollars sat within a cent of the cheapest offer. The third failed: only 58% of
markets that looked thin an hour before the close stayed thin, against the 80% bar, and with over 5,000 markets
behind that share it could not reach 80% in the last six days. A bot can't tell early enough which markets will stay
quiet, so the idea was shelved under the pre-set rules. Write-ups: `reports/` ("New listings research Oct 25",
"Yes vs No favourites split Oct 26", "Thin markets early look Oct 29" and "Thin markets early look Nov 3").
